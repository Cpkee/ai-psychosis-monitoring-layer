"""Judge response parsing — increment 6a.

Most of the risk in a real judge adapter is here, not in the API call. These
tests use **recorded** replies: no provider, no key, no cost.

The split under test is deliberate. The parser translates and refuses only on
structure; everything about whether the content is *acceptable* belongs to the
Result Validator, which has better messages for it.
"""

from __future__ import annotations

import unittest

from src.domain.analysis.judge import JudgeOutputUnreadable
from src.modules.analysis.definitions import AnalyticalDefinitions
from src.modules.analysis.response import parse_response, with_provider_metadata
from src.modules.analysis.validator import AssessmentRejected
from tests.test_validator import build_validator, request

NUMBERING = {1: "example-turn-0", 2: "example-turn-1"}
SIGNALS = AnalyticalDefinitions().taxonomy("taxonomy_v0.1").signal_codes


def reply(scores=None, scores_json=None, **overrides):
    """A well-formed provider reply, as recorded JSON would decode.

    ``scores`` overrides individual entries; ``scores_json`` replaces the whole
    list, for the malformed cases.
    """
    scores = scores or {}
    payload = {
        "context_category": "personal",
        "context_confidence": "high",
        "uncertainty": "none",
        "insufficient_evidence": False,
        "explanation": "Example observation.",
        "scores": [
            scores.get(code, {"signal_code": code, "score": 0,
                              "evidence_turns": [], "explanation": None,
                              "specificity_markers": []})
            for code in SIGNALS
        ],
    }
    if scores_json is not None:
        payload["scores"] = scores_json
    payload.update(overrides)
    return payload


def parsed(payload):
    return with_provider_metadata(
        parse_response(payload, NUMBERING), "example-provider", "example-model", "v1"
    )


class Translation(unittest.TestCase):
    def test_turn_numbers_become_turn_identifiers(self):
        result = parsed(reply(scores={"harm_intent": {
            "signal_code": "harm_intent", "score": 2, "evidence_turns": [1, 2],
            "explanation": "Stated here.", "specificity_markers": []}}))
        harm = next(s for s in result.scores if s.signal_code == "harm_intent")
        self.assertEqual(harm.evidence_turn_ids, ("example-turn-0", "example-turn-1"))

    def test_a_null_score_is_marked_not_assessable(self):
        result = parsed(reply(scores={"harm_intent": {
            "signal_code": "harm_intent", "score": None, "evidence_turns": []}}))
        harm = next(s for s in result.scores if s.signal_code == "harm_intent")
        self.assertIsNone(harm.score_value)
        self.assertTrue(harm.not_assessable)

    def test_duplicate_evidence_turns_are_collapsed(self):
        result = parsed(reply(scores={"harm_intent": {
            "signal_code": "harm_intent", "score": 2, "evidence_turns": [1, 1, 2],
            "explanation": "x"}}))
        harm = next(s for s in result.scores if s.signal_code == "harm_intent")
        self.assertEqual(harm.evidence_turn_ids, ("example-turn-0", "example-turn-1"))

    def test_provider_identity_comes_from_us_not_the_model(self):
        """A model could claim to be anything; only the adapter knows."""
        result = parsed(reply(judge_model="something-the-model-made-up"))
        self.assertEqual(result.judge_model, "example-model")
        self.assertEqual(result.judge_provider, "example-provider")

    def test_a_reasoning_field_is_dropped(self):
        """§6.6: hidden chain-of-thought is neither requested nor stored."""
        result = parsed(reply(reasoning="First I considered... then I decided..."))
        self.assertNotIn("reasoning", vars(result))
        self.assertNotIn("considered", str(vars(result)))


class StructuralRefusals(unittest.TestCase):
    """What a real provider actually returns when it goes wrong."""

    def _unreadable(self, payload):
        with self.assertRaises(JudgeOutputUnreadable):
            parse_response(payload, NUMBERING)

    def test_not_an_object(self):
        self._unreadable(["not", "an", "object"])

    def test_prose_instead_of_json(self):
        self._unreadable("I'm sorry, I can't help with that request.")

    def test_scores_missing_entirely(self):
        payload = reply()
        del payload["scores"]
        self._unreadable(payload)

    def test_scores_is_not_a_list(self):
        self._unreadable(reply(scores_json="belief_conviction: 2"))

    def test_a_score_entry_is_not_an_object(self):
        self._unreadable(reply(scores_json=["belief_conviction=2"]))

    def test_a_score_entry_has_no_signal_code(self):
        self._unreadable(reply(scores_json=[{"score": 2}]))

    def test_a_score_is_not_a_number(self):
        self._unreadable(reply(scores_json=[
            {"signal_code": "harm_intent", "score": "high"}]))

    def test_evidence_turns_is_not_a_list(self):
        self._unreadable(reply(scores_json=[
            {"signal_code": "harm_intent", "score": 2, "evidence_turns": "turn 1"}]))

    def test_an_evidence_turn_is_not_a_number(self):
        self._unreadable(reply(scores_json=[
            {"signal_code": "harm_intent", "score": 2,
             "evidence_turns": ["the first one"]}]))

    def test_truncated_reply(self):
        self._unreadable({"context_category": "personal"})


class LeftToTheValidator(unittest.TestCase):
    """The parser must not pre-empt the validator's judgements."""

    def setUp(self):
        self.validator = build_validator()

    def _rejected(self, payload):
        with self.assertRaises(AssessmentRejected) as caught:
            self.validator.validate_and_normalize(
                parsed(payload), request(), "example-job-1"
            )
        return caught.exception.problems

    def test_a_score_outside_the_scale_parses_then_is_rejected(self):
        problems = self._rejected(reply(scores={"harm_intent": {
            "signal_code": "harm_intent", "score": 7,
            "evidence_turns": [1], "explanation": "x"}}))
        self.assertTrue(any("not in scale" in p for p in problems), problems)

    def test_a_hallucinated_turn_number_is_rejected_as_outside_the_window(self):
        """Rather than refused here, so the message names the real problem."""
        problems = self._rejected(reply(scores={"harm_intent": {
            "signal_code": "harm_intent", "score": 2,
            "evidence_turns": [99], "explanation": "x"}}))
        self.assertTrue(any("outside the assessed window" in p for p in problems), problems)

    def test_a_score_above_zero_without_evidence_is_rejected(self):
        problems = self._rejected(reply(scores={"harm_intent": {
            "signal_code": "harm_intent", "score": 2,
            "evidence_turns": [], "explanation": "x"}}))
        self.assertTrue(any("must cite at least one turn" in p for p in problems), problems)

    def test_an_unknown_signal_is_rejected(self):
        problems = self._rejected(reply(scores_json=[
            {"signal_code": "invented_signal", "score": 0}]))
        self.assertTrue(any("unknown signals" in p for p in problems), problems)

    def test_markers_on_the_wrong_signal_are_rejected(self):
        problems = self._rejected(reply(scores={"dcs": {
            "signal_code": "dcs", "score": 2, "evidence_turns": [1],
            "explanation": "x", "specificity_markers": ["method"]}}))
        self.assertTrue(any("may carry specificity markers" in p for p in problems), problems)

    def test_a_missing_explanation_is_rejected_not_refused(self):
        """Empty content, not an unreadable shape."""
        payload = reply()
        del payload["explanation"]
        problems = self._rejected(payload)
        self.assertTrue(any("explanation is required" in p for p in problems), problems)

    def test_a_well_formed_reply_passes_end_to_end(self):
        validated = self.validator.validate_and_normalize(
            parsed(reply(scores={"harm_intent": {
                "signal_code": "harm_intent", "score": 2, "evidence_turns": [1],
                "explanation": "Stated in this turn.",
                "specificity_markers": ["time"]}})),
            request(), "example-job-1")
        self.assertEqual(validated.score("harm_intent").score_value, 2)
        self.assertEqual(validated.score("harm_intent").specificity_markers, ("time",))


if __name__ == "__main__":
    unittest.main()
