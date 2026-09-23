"""Judge prompt rendering — increment 6a.

The prompt is a derived artefact. These tests exist mainly to catch **drift**:
the enumerable vocabularies must come from the definitions, so the prompt and
the Result Validator cannot disagree about what a valid answer looks like.
"""

from __future__ import annotations

import unittest

from src.modules.analysis.definitions import AnalyticalDefinitions
from src.modules.analysis.prompt import (
    JudgePromptLibrary,
    PromptVocabularyMissing,
    UnknownPromptVersion,
)
from tests.test_validator import request

VERSION = "judge_prompt_v0.1"
DEFS = AnalyticalDefinitions()


class Rendering(unittest.TestCase):
    def setUp(self):
        self.library = JudgePromptLibrary()
        self.rendered = self.library.render(VERSION, request(), DEFS)

    def test_no_placeholder_survives_rendering(self):
        for placeholder in ("{signal_lines}", "{context_lines}", "{score_values}",
                            "{marker_names}", "{conversation}", "{assessed_turn}"):
            self.assertNotIn(placeholder, self.rendered.text)

    def test_every_signal_in_the_taxonomy_appears(self):
        """A signal the model is never told about is one it will fail to score."""
        for code in DEFS.taxonomy("taxonomy_v0.1").signal_codes:
            self.assertIn(code, self.rendered.text)

    def test_every_context_category_appears(self):
        for code in DEFS.taxonomy("taxonomy_v0.1").context_categories:
            self.assertIn(code, self.rendered.text)

    def test_every_specificity_marker_appears(self):
        for marker in DEFS.taxonomy("taxonomy_v0.1").specificity_markers:
            self.assertIn(marker, self.rendered.text)

    def test_the_conversation_is_numbered_from_one(self):
        self.assertEqual(self.rendered.turn_ids_by_number,
                         {1: "example-turn-0", 2: "example-turn-1"})

    def test_turns_are_shown_by_number_not_identifier(self):
        """Models do not reliably echo opaque ids, so they never see them."""
        self.assertNotIn("example-turn-0", self.rendered.text)
        self.assertNotIn("example-turn-1", self.rendered.text)

    def test_the_authoring_header_is_not_shown_to_the_model(self):
        self.assertNotIn("<!--", self.rendered.text)
        self.assertNotIn("built_from_rubric", self.rendered.text)

    def test_the_content_hash_is_of_the_template_not_the_conversation(self):
        """So a released prompt cannot be edited silently, and two different
        conversations under one prompt version hash the same."""
        other = self.library.render(
            VERSION, request(through_turn_id="example-turn-0"), DEFS
        )
        self.assertEqual(other.content_hash, self.rendered.content_hash)
        self.assertEqual(self.rendered.content_hash, self.library.content_hash(VERSION))


class NothingAboutTheExperimentLeaks(unittest.TestCase):
    """RUBRIC_v0.1 §11.4: the judge must score the conversation, not the setup."""

    def test_the_prompt_carries_no_experiment_metadata(self):
        rendered = JudgePromptLibrary().render(VERSION, request(), DEFS)
        for leak in ("example-session-1", "client_companion", "sycophantic",
                     "grounded_reference", "example-scenario", "hidden_state"):
            self.assertNotIn(leak, rendered.text)

    def test_the_prompt_does_not_ask_for_reasoning(self):
        """§6.6: hidden chain-of-thought is neither requested nor stored."""
        rendered = JudgePromptLibrary().render(VERSION, request(), DEFS).text.lower()
        for phrase in ("step by step", "chain of thought", "think through",
                       "show your reasoning", "reasoning:"):
            self.assertNotIn(phrase, rendered)


class Failures(unittest.TestCase):
    def test_unknown_version_raises(self):
        with self.assertRaises(UnknownPromptVersion):
            JudgePromptLibrary().render("judge_prompt_v9.9", request(), DEFS)

    def test_a_signal_the_prompt_cannot_describe_raises(self):
        """Adding a signal to the taxonomy without describing it would leave
        the model silently unable to score it."""
        import dataclasses

        taxonomy = DEFS.taxonomy("taxonomy_v0.1")
        widened = dataclasses.replace(
            taxonomy, user_signals=list(taxonomy.user_signals) + ["brand_new_signal"]
        )

        class Stub:
            def taxonomy(self, _):
                return widened

            def scale(self, version):
                return DEFS.scale(version)

        with self.assertRaises(PromptVocabularyMissing):
            JudgePromptLibrary().render(VERSION, request(), Stub())

    def test_a_turn_outside_the_window_raises(self):
        with self.assertRaises(ValueError):
            JudgePromptLibrary().render(
                VERSION, request(through_turn_id="not-in-window"), DEFS
            )


if __name__ == "__main__":
    unittest.main()
