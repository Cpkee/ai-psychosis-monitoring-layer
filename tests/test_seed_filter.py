"""S2 Filter — only current seeds are screened, screening is idempotent, and a
flag needs a person's decision before the seed can be chosen.

Every document, seed and manifest here is a hand-written synthetic example.
"""

from __future__ import annotations

import dataclasses
import itertools
import unittest

from src.adapters.memory.seeds import (
    InMemorySeedFilterRepository,
    InMemorySeedRepository,
    InMemorySourceDocumentRepository,
)
from src.domain.seeds.overlap import (
    AWAITING_REVIEW,
    BLOCKED,
    CITES_BENCHMARK,
    CLEAR,
    EXCLUDE,
    EXCLUDED,
    HARM_TYPE_MATCH,
    KEEP,
    KEPT,
    UNSCREENED,
)
from src.domain.seeds.records import EXTRACTED, SCREENED
from src.modules.seeds.filter import (
    AlreadyReviewed,
    NotAwaitingReview,
    NothingToCorrect,
    SeedFilter,
    UnknownSeed,
)
from src.modules.seeds.overlap_screen import OverlapScreen
from tests.contract.seed_repositories import make_document, make_seed
from tests.test_overlap_screen import (
    CONFIG,
    EXAMPLE_HARM_TYPE,
    EXAMPLE_PROMPT,
    stand_in_manifest,
)

PROMPT, MODEL = "extraction_prompt_v0.1#example", "fake_v0.1"


class FilterTest(unittest.TestCase):
    def setUp(self):
        self.documents = InMemorySourceDocumentRepository()
        self.seeds = InMemorySeedRepository()
        self.checks = InMemorySeedFilterRepository()
        self.manifest = stand_in_manifest()
        self.ids = ("example-id-{}".format(n) for n in itertools.count(1))
        self.document = self.documents.save(make_document(
            status=EXTRACTED, processed_prompt_version=PROMPT, processed_model_version=MODEL))
        self.seeds.save_all((
            make_seed("example-clear"),
            make_seed("example-flagged", harm_type_candidate=EXAMPLE_HARM_TYPE),
            make_seed("example-blocked", arc_summary=EXAMPLE_PROMPT),
        ))

    def seed_filter(self, config=CONFIG):
        return SeedFilter(self.documents, self.seeds, self.checks,
                          OverlapScreen(config, self.manifest),
                          clock=lambda: "2026-01-01T00:00:00Z", new_id=lambda: next(self.ids))

    def statuses(self, seed_filter=None):
        return {s.seed.id: s.status for s in (seed_filter or self.seed_filter()).seeds()}

    def screened(self):
        seed_filter = self.seed_filter()
        seed_filter.screen_document(self.document.id)
        return seed_filter

    def test_before_screening_every_seed_is_unscreened_and_none_is_eligible(self):
        screened = self.seed_filter().seeds()
        self.assertEqual({s.status for s in screened}, {UNSCREENED})
        self.assertFalse(any(s.eligible for s in screened))

    def test_screening_sorts_seeds_into_clear_flagged_and_blocked(self):
        seed_filter = self.screened()
        self.assertEqual(self.statuses(seed_filter), {
            "example-clear": CLEAR, "example-flagged": AWAITING_REVIEW,
            "example-blocked": BLOCKED})
        self.assertEqual([s.seed.id for s in seed_filter.seeds() if s.eligible],
                         ["example-clear"])

    def test_screening_again_under_the_same_screen_records_nothing_new(self):
        first = self.screened().screen_document(self.document.id)
        again = self.seed_filter().screen_document(self.document.id)
        self.assertEqual(again, first)
        self.assertEqual(len(self.checks.list_checks(CONFIG.version,
                                                     first[0].manifest_sha256)), 3)

    def test_a_document_not_extracted_has_nothing_to_screen(self):
        other = self.documents.save(make_document("example-document-2", text="Other example.",
                                                  status=SCREENED))
        self.assertEqual(self.seed_filter().screen_document(other.id), ())

    def test_only_the_current_extraction_is_screened_or_listed(self):
        """D-45: seeds from an earlier extraction are history."""
        self.seeds.save_all((make_seed("example-new", extraction_model_version="fake_v0.2"),))
        self.documents.update(dataclasses.replace(self.document,
                                                  processed_model_version="fake_v0.2"), EXTRACTED)
        checks = self.seed_filter().screen_document(self.document.id)
        self.assertEqual([c.seed_id for c in checks], ["example-new"])
        self.assertEqual(self.statuses(), {"example-new": CLEAR})

    def test_keep_makes_a_flagged_seed_eligible_and_exclude_does_not(self):
        seed_filter = self.screened()
        review = seed_filter.review("example-flagged", KEEP, "Example reason.", "example-actor")
        self.assertIsNone(review.supersedes)
        self.assertEqual(self.statuses()["example-flagged"], KEPT)
        seed_filter.review("example-flagged", EXCLUDE, "Example correction.", "example-actor",
                           correct=True)
        self.assertEqual(self.statuses()["example-flagged"], EXCLUDED)

    def test_changing_a_decision_must_be_asked_for_and_keeps_the_original(self):
        seed_filter = self.screened()
        first = seed_filter.review("example-flagged", KEEP, "Example reason.", "example-actor")
        with self.assertRaises(AlreadyReviewed):
            seed_filter.review("example-flagged", EXCLUDE, "Example reason.", "example-actor")
        corrected = seed_filter.review("example-flagged", EXCLUDE, "Example correction.",
                                       "example-other-actor", correct=True)
        self.assertEqual(corrected.supersedes, first.id)

    def test_a_correction_needs_an_earlier_decision(self):
        with self.assertRaises(NothingToCorrect):
            self.screened().review("example-flagged", KEEP, "Example reason.", "example-actor",
                                   correct=True)

    def test_only_a_flag_can_be_reviewed(self):
        seed_filter = self.seed_filter()
        with self.assertRaises(NotAwaitingReview):  # not screened yet
            seed_filter.review("example-flagged", KEEP, "Example reason.", "example-actor")
        seed_filter.screen_document(self.document.id)
        for seed_id in ("example-clear", "example-blocked"):
            with self.subTest(seed=seed_id), self.assertRaises(NotAwaitingReview):
                seed_filter.review(seed_id, KEEP, "Example reason.", "example-actor")
        with self.assertRaises(UnknownSeed):
            seed_filter.review("example-missing", KEEP, "Example reason.", "example-actor")

    def test_a_new_screen_version_needs_a_fresh_decision(self):
        self.screened().review("example-flagged", KEEP, "Example reason.", "example-actor")
        edited = dataclasses.replace(CONFIG, version=CONFIG.version + "-edited")
        stricter = self.seed_filter(edited)
        self.assertEqual(self.statuses(stricter)["example-flagged"], UNSCREENED)
        stricter.screen_document(self.document.id)
        self.assertEqual(self.statuses(stricter)["example-flagged"], AWAITING_REVIEW)

    def test_a_check_records_reason_codes_never_sealed_text(self):
        checks = self.screened().screen_document(self.document.id)
        allowed = {HARM_TYPE_MATCH, CITES_BENCHMARK, "sealed_span:arc_summary",
                   "sealed_span:harm_type_candidate", "sealed_span:raw_theme_terms"}
        reasons = [r for c in checks for r in c.reasons]
        self.assertTrue(reasons)
        self.assertLessEqual(set(reasons), allowed)


if __name__ == "__main__":
    unittest.main()
