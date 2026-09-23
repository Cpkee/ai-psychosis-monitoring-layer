"""Seal screen for collected documents — D-27. Governance suite: bare
interpreter, no dependencies, no database (D-5).

No sealed text appears here or is read by these tests. Positive matches use a
temporary manifest built from hand-written example sentences; the real manifest
is used only for its upstream identifiers and to show ordinary text passes.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest

from src.modules.seeds import seal_screen
from src.modules.seeds.seal_screen import SealScreen
from tests import test_benchmark_seal

EXAMPLE_PROMPT = "I think the lights in my kitchen are sending me a message tonight. Is that possible?"


def manifest_with(*prompts):
    """A stand-in manifest in the real format, hashing example prompts."""
    digests = [hashlib.sha256(seal_screen.normalise(p).encode("utf-8")).hexdigest()
               for p in prompts]
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, "manifest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"provenance": {"upstream_repository": "https://github.com/example/bench",
                                  "reference_paper": "https://arxiv.org/abs/2601.00001"},
                   "cases": [{"prompt_normalised_sha256": digests}]}, handle)
    return path


class SpanHashScreen(unittest.TestCase):
    def setUp(self):
        self.screen = SealScreen(max_span_sentences=6, manifest_path=manifest_with(EXAMPLE_PROMPT))

    def test_normalisation_is_identical_to_the_seal_test(self):
        for sample in ("  Mixed CASE\n\ttext  ", "a   b", "Line one.\nLine two!"):
            self.assertEqual(seal_screen.normalise(sample), test_benchmark_seal.normalise(sample))

    def test_a_document_quoting_a_prompt_is_blocked(self):
        text = ("Example article. The user wrote: " + EXAMPLE_PROMPT
                + " The chatbot agreed. Experts were concerned.")
        self.assertTrue(self.screen.screen("https://example.org/a", None, text).blocked)

    def test_case_whitespace_line_breaks_and_quotes_do_not_evade_it(self):
        text = ('Example article.\n“' + EXAMPLE_PROMPT.upper().replace(". ", ".\n   ")
                + '”\nMore text.')
        self.assertTrue(self.screen.screen("https://example.org/a", None, text).blocked)

    def test_ordinary_text_passes(self):
        text = "Example report. An older adult described a chatbot as a good listener."
        self.assertFalse(self.screen.screen("https://example.org/a", None, text).blocked)

    def test_a_block_reason_never_contains_the_matched_text(self):
        result = self.screen.screen("https://example.org/a", None, EXAMPLE_PROMPT)
        self.assertNotIn("kitchen", result.reason.lower())

    def test_span_length_is_bounded_by_configuration(self):
        narrow = SealScreen(max_span_sentences=1, manifest_path=manifest_with(EXAMPLE_PROMPT))
        self.assertFalse(narrow.screen("https://example.org/a", None, EXAMPLE_PROMPT).blocked)


class UpstreamDenylist(unittest.TestCase):
    """The real manifest: the benchmark's own repository and paper."""

    def setUp(self):
        self.screen = SealScreen(max_span_sentences=6)

    def test_the_upstream_paper_is_blocked_by_arxiv_id_in_any_version(self):
        for url, external in (("https://arxiv.org/abs/2509.10970v1", "arXiv:2509.10970v1"),
                              ("https://example.org/mirror", "DOI:10.48550/arXiv.2509.10970"),
                              ("https://arxiv.org/abs/2509.10970v3", None)):
            with self.subTest(url=url):
                self.assertTrue(self.screen.screen(url, external, "Example abstract.").blocked)

    def test_the_upstream_repository_is_blocked(self):
        self.assertTrue(self.screen.screen(
            "https://github.com/w-is-h/psychosis-bench/blob/main/README.md", None,
            "Example text.").blocked)

    def test_an_unrelated_preprint_passes(self):
        self.assertFalse(self.screen.screen(
            "https://arxiv.org/abs/2601.01234v1", "arXiv:2601.01234v1",
            "Example abstract about companion chatbots.").blocked)


if __name__ == "__main__":
    unittest.main()
