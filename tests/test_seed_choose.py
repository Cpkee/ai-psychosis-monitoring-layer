"""S3 Choose — only eligible seeds can be chosen, a split never changes, gaps
are refused until accepted and then stored, and seeing a seed is recorded.

Every document, seed and manifest here is a hand-written synthetic example.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
import os
import shutil
import tempfile
import unittest

from src.adapters.memory.seeds import (
    InMemorySeedExposureRepository,
    InMemorySeedFilterRepository,
    InMemorySeedRepository,
    InMemorySeedSelectionRepository,
    InMemorySourceDocumentRepository,
)
from src.domain.seeds.overlap import EXCLUDE, KEEP
from src.domain.seeds.records import EXTRACTED
from src.domain.seeds.selection import (
    CHOOSE,
    DEVELOPMENT,
    GOLD,
    SILVER,
    CoverageCell,
)
from src.modules.seeds.choose import (
    ChoiceRefused,
    GapsNotAccepted,
    SeedChooser,
    SplitAlreadyAssigned,
    coverage,
    find_gaps,
)
from src.modules.seeds.config import CONFIG_DIR, load_coverage_targets
from src.modules.seeds.filter import SeedFilter
from src.modules.seeds.overlap_screen import OverlapScreen
from tests.contract.seed_repositories import make_document
from tests.contract.seed_repositories import make_seed as seed
from tests.test_overlap_screen import (
    CONFIG,
    EXAMPLE_HARM_TYPE,
    EXAMPLE_PROMPT,
    stand_in_manifest,
)

TARGETS = load_coverage_targets("coverage_targets_v0.1")
#: Nothing required, so a test can make a selection without gaps.
NO_TARGETS = dataclasses.replace(
    TARGETS, min_per_theme_family={}, min_per_explicitness={}, min_per_harm={},
    max_pattern_share=1.0, every_theme_family_in_splits=())
PROMPT, MODEL = "extraction_prompt_v0.1#example", "fake_v0.1"


class ChooseTest(unittest.TestCase):
    def setUp(self):
        self.documents = InMemorySourceDocumentRepository()
        self.seeds = InMemorySeedRepository()
        self.checks = InMemorySeedFilterRepository()
        self.selections = InMemorySeedSelectionRepository()
        self.exposure = InMemorySeedExposureRepository()
        self.ids = ("example-id-{}".format(n) for n in itertools.count(1))
        self.document = self.documents.save(make_document(
            status=EXTRACTED, processed_prompt_version=PROMPT, processed_model_version=MODEL))
        self.seeds.save_all((
            seed("example-a1", theme_family="A1", harm_type_candidate="stopped eating"),
            seed("example-a2", theme_family="A2", explicitness_candidate="implicit",
                 account_kind="pattern", credibility_tier="T2"),
            seed("example-a3", theme_family="A3"),
            seed("example-kept", theme_family="A3", harm_type_candidate=EXAMPLE_HARM_TYPE),
            seed("example-blocked", arc_summary=EXAMPLE_PROMPT),
        ))
        self.filter = SeedFilter(self.documents, self.seeds, self.checks,
                                 OverlapScreen(CONFIG, stand_in_manifest()),
                                 clock=self.clock, new_id=self.new_id)
        self.filter.screen_document(self.document.id)

    def clock(self):
        return "2026-01-01T00:00:00Z"

    def new_id(self):
        return next(self.ids)

    def chooser(self, targets=NO_TARGETS):
        return SeedChooser(self.filter, self.selections, self.exposure, targets,
                           self.clock, self.new_id)

    def choose(self, assign, drop=(), targets=NO_TARGETS, accept_gaps=False):
        chooser = self.chooser(targets)
        return chooser.commit(chooser.propose(assign, drop), "example-actor", accept_gaps)

    def test_only_clear_or_kept_seeds_are_candidates(self):
        ids = {c.seed.id for c in self.chooser().candidates()}
        self.assertEqual(ids, {"example-a1", "example-a2", "example-a3"})
        self.filter.review("example-kept", KEEP, "Example reason.", "example-reviewer")
        self.assertIn("example-kept", {c.seed.id for c in self.chooser().candidates()})

    def test_seeds_that_cannot_be_chosen_are_refused(self):
        for seed_id in ("example-kept", "example-blocked", "example-missing"):
            with self.subTest(seed=seed_id), self.assertRaises(ChoiceRefused):
                self.chooser().propose({seed_id: GOLD}, ())

    def test_the_first_selection_records_splits_patterns_and_coverage(self):
        selection = self.choose({"example-a1": GOLD, "example-a2": DEVELOPMENT})
        self.assertEqual((selection.selection_version, selection.supersedes), (1, None))
        self.assertEqual({(e.seed_id, e.split) for e in selection.entries},
                         {("example-a1", GOLD), ("example-a2", DEVELOPMENT)})
        self.assertEqual(selection.pattern_count, 1)
        self.assertEqual(selection.coverage_targets_version, NO_TARGETS.version)
        self.assertEqual(sum(c.unchosen for c in selection.coverage), 1)  # example-a3

    def test_a_selection_with_an_accepted_gap_stores_the_gap(self):
        chooser = self.chooser(TARGETS)
        proposal = chooser.propose({"example-a1": GOLD}, ())
        self.assertTrue(proposal.gaps)
        with self.assertRaises(GapsNotAccepted) as refused:
            chooser.commit(proposal, "example-actor", accept_gaps=False)
        self.assertEqual(refused.exception.gaps, proposal.gaps)
        self.assertIsNone(self.selections.latest())
        stored = chooser.commit(proposal, "example-actor", accept_gaps=True)
        self.assertEqual(self.selections.latest().gaps, proposal.gaps)
        self.assertEqual(stored.gaps, proposal.gaps)

    def test_no_seed_can_hold_two_splits(self):
        self.choose({"example-a1": GOLD, "example-a2": DEVELOPMENT})
        with self.assertRaises(SplitAlreadyAssigned):
            self.chooser().propose({"example-a1": SILVER}, ())
        self.choose({}, drop=("example-a1",))
        with self.assertRaises(SplitAlreadyAssigned):
            self.chooser().propose({"example-a1": SILVER}, ())
        back = self.choose({"example-a1": GOLD})
        self.assertEqual(back.selection_version, 3)
        self.assertIn(("example-a1", GOLD), {(e.seed_id, e.split) for e in back.entries})

    def test_each_selection_supersedes_the_one_before(self):
        first = self.choose({"example-a1": GOLD})
        second = self.choose({"example-a3": SILVER})
        self.assertEqual((second.selection_version, second.supersedes), (2, first.id))
        self.assertEqual({e.seed_id for e in second.entries}, {"example-a1", "example-a3"})

    def test_a_seed_that_became_ineligible_must_be_dropped_explicitly(self):
        self.filter.review("example-kept", KEEP, "Example reason.", "example-reviewer")
        self.choose({"example-kept": GOLD})
        self.filter.review("example-kept", EXCLUDE, "Example correction.", "example-reviewer",
                           correct=True)
        self.assertEqual(self.chooser().stale(), (("example-kept", "excluded"),))
        with self.assertRaises(ChoiceRefused):
            self.chooser().propose({"example-a1": GOLD}, ())
        after = self.choose({"example-a1": GOLD}, drop=("example-kept",))
        self.assertEqual([e.seed_id for e in after.entries], ["example-a1"])

    def test_requests_that_change_nothing_or_contradict_themselves_are_refused(self):
        self.choose({"example-a1": GOLD})
        for assign, drop in (({"example-a1": GOLD}, ()),          # already chosen
                             ({}, ("example-a3",)),               # not chosen
                             ({"example-a1": GOLD}, ("example-a1",)),
                             ({}, ("example-a1",))):              # nothing left
            with self.subTest(assign=assign, drop=drop), self.assertRaises(ChoiceRefused):
                self.chooser().propose(assign, drop)

    def test_seeing_or_choosing_a_seed_is_recorded(self):
        chooser = self.chooser()
        chooser.show("example-viewer")
        self.choose({"example-a1": GOLD})
        seen = {(e.seed_id, e.actor_id) for e in self.exposure.list_events()}
        self.assertEqual(seen, {("example-a1", "example-viewer"), ("example-a2", "example-viewer"),
                                ("example-a3", "example-viewer"), ("example-a1", "example-actor")})
        self.assertEqual({e.activity for e in self.exposure.list_events()}, {CHOOSE})
        self.assertEqual(
            {c.seed.id: c.seen_by for c in self.chooser().candidates()}["example-a1"],
            ("example-actor", "example-viewer"))


class Coverage(unittest.TestCase):
    def test_cells_count_splits_unchosen_kinds_and_tiers(self):
        chosen = [(seed("example-1", theme_family="A1", harm_type_candidate="example harm"), GOLD),
                  (seed("example-2", theme_family="A1", harm_type_candidate="example harm",
                        account_kind="pattern", credibility_tier="T2"), DEVELOPMENT)]
        unchosen = [seed("example-3", theme_family=None, explicitness_candidate="implicit")]
        self.assertEqual(coverage(chosen, unchosen), (
            CoverageCell("A1", "explicit", "harm_described", gold=1, silver=0, development=1,
                         unchosen=0, individual=1, pattern=1, tiers=(("T1", 1), ("T2", 1))),
            CoverageCell("none", "implicit", "no_harm_described", gold=0, silver=0,
                         development=0, unchosen=1, individual=0, pattern=0, tiers=()),
        ))


class Gaps(unittest.TestCase):
    def test_every_kind_of_gap_is_named(self):
        targets = dataclasses.replace(
            NO_TARGETS, min_per_theme_family={"A1": 1, "A2": 1},
            min_per_explicitness={"implicit": 1}, min_per_harm={"harm_described": 1},
            max_pattern_share=0.5, every_theme_family_in_splits=(GOLD,))
        chosen = [(seed("example-1", theme_family="A1", account_kind="pattern"), SILVER)]
        self.assertEqual(find_gaps(chosen, targets), (
            "theme family A2: 0 chosen, target at least 1",
            "explicitness implicit: 0 chosen, target at least 1",
            "harm harm_described: 0 chosen, target at least 1",
            "pattern seeds: 1 of 1, target at most 50%",
            "gold split has no A1 seed",
            "gold split has no A2 seed",
        ))

    def test_a_selection_meeting_every_target_has_no_gaps(self):
        targets = dataclasses.replace(NO_TARGETS, min_per_theme_family={"A1": 1},
                                      every_theme_family_in_splits=(GOLD,))
        self.assertEqual(find_gaps([(seed("example-1", theme_family="A1"), GOLD)], targets), ())

    def test_editing_a_target_without_a_rename_changes_the_targets_version(self):
        directory = tempfile.mkdtemp()
        shutil.copy(os.path.join(CONFIG_DIR, "coverage_targets_v0.1.json"), directory)
        path = os.path.join(directory, "coverage_targets_v0.1.json")
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        document["max_pattern_share"] = 0.25
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        edited = load_coverage_targets("coverage_targets_v0.1", directory)
        self.assertTrue(edited.version.startswith("coverage_targets_v0.1#"))
        self.assertNotEqual(edited.version, TARGETS.version)


if __name__ == "__main__":
    unittest.main()
