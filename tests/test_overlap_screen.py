"""Post-extraction overlap screen — S2 Filter (D-27, D-48). Governance suite:
bare interpreter, no dependencies, no database (D-5).

No sealed text appears here or is read by these tests. Positive matches use a
stand-in manifest built from hand-written example prompts and harm types; the
real manifest is used only for the benchmark's name and identifiers, and to
show an ordinary seed passes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
import unittest

from src.domain.seeds.overlap import (
    BLOCKED,
    CITES_BENCHMARK,
    CLEAR,
    FLAGGED,
    HARM_TYPE_MATCH,
    OverlapCheck,
)
from src.modules.seeds import seal_screen
from src.modules.seeds.config import CONFIG_DIR, load_overlap_screen
from src.modules.seeds.overlap_screen import OverlapScreen
from tests.contract.seed_repositories import make_document, make_seed

EXAMPLE_PROMPT = "The numbers on the clock keep lining up for me. Is someone arranging that?"
EXAMPLE_HARM_TYPE = "walking into the sea at night"
CONFIG = load_overlap_screen("overlap_screen_v0.1")


def stand_in_manifest(prompts=(EXAMPLE_PROMPT,), harm_types=(EXAMPLE_HARM_TYPE,)):
    """A manifest in the real format, built from example values only."""
    digests = [hashlib.sha256(seal_screen.normalise(p).encode("utf-8")).hexdigest()
               for p in prompts]
    cases = [{"harm_type": h, "prompt_normalised_sha256": digests} for h in harm_types]
    path = os.path.join(tempfile.mkdtemp(), "manifest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"source_name": "Example-Bench",
                   "provenance": {"upstream_repository": "https://github.com/example/bench",
                                  "reference_paper": "https://arxiv.org/abs/2601.00001"},
                   "cases": cases}, handle)
    return path


class SealedSpans(unittest.TestCase):
    def setUp(self):
        self.screen = OverlapScreen(CONFIG, stand_in_manifest())

    def test_an_arc_summary_reproducing_a_sealed_prompt_is_blocked(self):
        seed = make_seed(arc_summary="The user asked: " + EXAMPLE_PROMPT.upper())
        found = self.screen.screen(seed, make_document())
        self.assertEqual((found.result, found.reasons), (BLOCKED, ("sealed_span:arc_summary",)))

    def test_every_text_field_is_screened_and_named(self):
        seed = make_seed(harm_type_candidate=EXAMPLE_PROMPT,
                         raw_theme_terms=("example term", EXAMPLE_PROMPT))
        self.assertEqual(self.screen.screen(seed, make_document()).reasons,
                         ("sealed_span:harm_type_candidate", "sealed_span:raw_theme_terms"))

    def test_a_block_outranks_flags_and_carries_no_sealed_text(self):
        seed = make_seed(arc_summary=EXAMPLE_PROMPT, harm_type_candidate=EXAMPLE_HARM_TYPE)
        found = self.screen.screen(seed, make_document(text="Mentions Example-Bench."))
        self.assertEqual(found.result, BLOCKED)
        self.assertNotIn("clock", " ".join(found.reasons))

    def test_an_ordinary_seed_is_clear(self):
        found = self.screen.screen(make_seed(), make_document())
        self.assertEqual((found.result, found.reasons), (CLEAR, ()))


class HarmTypeFlag(unittest.TestCase):
    def setUp(self):
        self.screen = OverlapScreen(CONFIG, stand_in_manifest())

    def flagged(self, harm_type):
        return self.screen.screen(make_seed(harm_type_candidate=harm_type),
                                  make_document()).reasons == (HARM_TYPE_MATCH,)

    def test_the_same_harm_type_in_other_words_order_and_case_is_flagged(self):
        self.assertTrue(self.flagged("Walking into the SEA, at night"))
        self.assertTrue(self.flagged("walking into sea"))

    def test_stopwords_do_not_count_as_overlap(self):
        # Counting "into" and "the" would make this 3 of 6 words: a flag.
        self.assertFalse(self.flagged("into the night"))

    def test_a_different_harm_type_is_clear(self):
        self.assertFalse(self.flagged("stopped paying rent"))
        self.assertFalse(self.flagged(None))

    def test_the_threshold_comes_from_config(self):
        # Two of three content words: flagged at 0.5, not at 0.9.
        strict = OverlapScreen(dataclasses.replace(CONFIG, min_jaccard=0.9), stand_in_manifest())
        seed = make_seed(harm_type_candidate="walking into sea")
        self.assertTrue(self.flagged("walking into sea"))
        self.assertEqual(strict.screen(seed, make_document()).reasons, ())


class MentionsTheBenchmark(unittest.TestCase):
    def setUp(self):
        self.screen = OverlapScreen(CONFIG, stand_in_manifest())

    def reasons(self, **document):
        return self.screen.screen(make_seed(), make_document(**document)).reasons

    def test_the_name_in_any_spelling_is_flagged(self):
        for text in ("We evaluate on Example-Bench.", "the example bench cases",
                     "EXAMPLEBENCH results", "(example_bench)"):
            with self.subTest(text=text):
                self.assertEqual(self.reasons(text=text), (CITES_BENCHMARK,))

    def test_the_upstream_repository_or_paper_is_flagged(self):
        self.assertEqual(self.reasons(text="Code: github.com/example/bench."), (CITES_BENCHMARK,))
        self.assertEqual(self.reasons(title="Following arXiv:2601.00001"), (CITES_BENCHMARK,))

    def test_a_word_that_merely_contains_the_name_is_clear(self):
        self.assertEqual(self.reasons(text="An exampleness benchmark."), ())


class Versions(unittest.TestCase):
    def test_the_manifest_hash_follows_the_manifest(self):
        one = OverlapScreen(CONFIG, stand_in_manifest())
        other = OverlapScreen(CONFIG, stand_in_manifest(harm_types=("another example",)))
        self.assertNotEqual(one.manifest_sha256, other.manifest_sha256)
        OverlapCheck("example-check", "example-seed", CLEAR, (), one.version,
                     one.manifest_sha256, "2026-01-01T00:00:00Z")

    def test_editing_a_setting_without_a_rename_changes_the_screen_version(self):
        directory = tempfile.mkdtemp()
        shutil.copy(os.path.join(CONFIG_DIR, "overlap_screen_v0.1.json"), directory)
        path = os.path.join(directory, "overlap_screen_v0.1.json")
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        document["harm_type_match"]["min_jaccard"] = 0.9
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        edited = load_overlap_screen("overlap_screen_v0.1", directory)
        self.assertTrue(edited.version.startswith("overlap_screen_v0.1#"))
        self.assertNotEqual(edited.version, CONFIG.version)


class RealManifest(unittest.TestCase):
    """The real manifest: an ordinary seed passes, and the benchmark's own name
    is recognised. Nothing from the sealed file is read."""

    def setUp(self):
        self.screen = OverlapScreen(CONFIG)

    def test_an_ordinary_seed_is_clear(self):
        self.assertEqual(self.screen.screen(make_seed(), make_document()).result, CLEAR)

    def test_a_source_discussing_the_benchmark_is_flagged(self):
        found = self.screen.screen(make_seed(), make_document(
            text="Example review. We compare our findings with Psychosis Bench."))
        self.assertEqual((found.result, found.reasons), (FLAGGED, (CITES_BENCHMARK,)))


if __name__ == "__main__":
    unittest.main()
