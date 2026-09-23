"""Result Validator — architecture.md section 6.7.

Section 6.7 requires validation failures to be *stored as processing failures,
not coerced into valid scores*. These tests exist to prove the validator
rejects rather than repairs.
"""

from __future__ import annotations

import itertools
import unittest

from src.domain.analysis.judge import JudgeRequest, RawJudgeResult, RawSignalScore
from src.modules.analysis.definitions import AnalyticalDefinitions
from src.modules.analysis.validator import AssessmentRejected, ResultValidator
from tests.contract.conversation_repository import make_turn

SIGNALS = (
    "belief_conviction", "pattern_seeking", "ai_dependency",
    "social_withdrawal", "harm_intent", "dcs", "hes", "sis", "sgq",
)


def request(**overrides) -> JudgeRequest:
    fields = dict(
        session_id="example-session-1",
        through_turn_id="example-turn-1",
        window=(
            make_turn(id="example-turn-0", turn_index=0),
            make_turn(id="example-turn-1", turn_index=1, role="assistant"),
        ),
        taxonomy_version="taxonomy_v0.1",
        scale_version="scale_0_3_v0.1",
        rubric_version="rubric_v0.1",
        rubric_instructions="example instructions",
        prompt_configuration_version="judge_v0_1",
        schema_version="assessment_v0.1",
        judge_configuration_version="fake_judge_v0.1",
    )
    fields.update(overrides)
    return JudgeRequest(**fields)


def result(scores=None, **overrides) -> RawJudgeResult:
    scores = scores if scores is not None else {}
    built = []
    for code in SIGNALS:
        spec = scores.get(code, 0)
        if isinstance(spec, RawSignalScore):
            built.append(spec)
        elif spec is None:
            built.append(RawSignalScore(signal_code=code, score_value=None, not_assessable=True))
        elif spec == 0:
            built.append(RawSignalScore(signal_code=code, score_value=0))
        else:
            built.append(RawSignalScore(
                signal_code=code, score_value=spec,
                evidence_turn_ids=("example-turn-0",),
                explanation="Example reason.",
            ))
    fields = dict(
        context_category="personal",
        scores=tuple(built),
        explanation="Example overall explanation.",
        judge_provider="example-provider",
        judge_model="example-model",
        judge_model_version="example-2026-01",
        context_confidence="high",
        uncertainty="none",
    )
    fields.update(overrides)
    return RawJudgeResult(**fields)


def build_validator() -> ResultValidator:
    counter = itertools.count(1)
    return ResultValidator(
        definitions=AnalyticalDefinitions(),
        new_id=lambda: "example-id-{}".format(next(counter)),
        clock=lambda: "2026-01-01T00:00:00Z",
    )


class ValidatorTest(unittest.TestCase):
    def setUp(self):
        self.validator = build_validator()

    def validate(self, raw, req=None):
        return self.validator.validate_and_normalize(raw, req or request(), "example-job-1")

    def rejection(self, raw, req=None):
        with self.assertRaises(AssessmentRejected) as caught:
            self.validate(raw, req)
        return caught.exception.problems

    # -- accepts ---------------------------------------------------------

    def test_a_well_formed_result_is_accepted(self):
        validated = self.validate(result(scores={"harm_intent": 2}))
        self.assertEqual(len(validated.scores), 9)
        self.assertEqual(validated.score("harm_intent").score_value, 2)
        self.assertEqual(
            [e.turn_id for e in validated.evidence_for("harm_intent")], ["example-turn-0"]
        )

    def test_all_version_fields_are_carried_onto_the_assessment(self):
        record = self.validate(result()).assessment
        self.assertEqual(record.rubric_version, "rubric_v0.1")
        self.assertEqual(record.taxonomy_version, "taxonomy_v0.1")
        self.assertEqual(record.scale_version, "scale_0_3_v0.1")
        self.assertEqual(record.prompt_configuration_version, "judge_v0_1")
        self.assertEqual(record.schema_version, "assessment_v0.1")
        self.assertEqual(record.judge_model_version, "example-2026-01")

    def test_an_unscoreable_signal_is_kept_null(self):
        validated = self.validate(result(scores={"harm_intent": None}))
        score = validated.score("harm_intent")
        self.assertIsNone(score.score_value)
        self.assertTrue(score.not_assessable)

    def test_duplicate_evidence_turns_are_collapsed(self):
        raw = result(scores={"harm_intent": RawSignalScore(
            signal_code="harm_intent", score_value=3,
            evidence_turn_ids=("example-turn-0", "example-turn-0"),
            explanation="Example reason.",
        )})
        self.assertEqual(len(self.validate(raw).evidence_for("harm_intent")), 1)

    # -- rejects ---------------------------------------------------------

    def test_a_score_outside_the_scale_is_rejected(self):
        problems = self.rejection(result(scores={"harm_intent": RawSignalScore(
            signal_code="harm_intent", score_value=7,
            evidence_turn_ids=("example-turn-0",), explanation="x")}))
        self.assertTrue(any("not in scale" in p for p in problems), problems)

    def test_a_positive_score_without_evidence_is_rejected(self):
        """Section 19 criterion 4."""
        problems = self.rejection(result(scores={"harm_intent": RawSignalScore(
            signal_code="harm_intent", score_value=3, explanation="x")}))
        self.assertTrue(any("must cite at least one turn" in p for p in problems), problems)

    def test_evidence_outside_the_window_is_rejected(self):
        problems = self.rejection(result(scores={"harm_intent": RawSignalScore(
            signal_code="harm_intent", score_value=2,
            evidence_turn_ids=("a-turn-from-another-session",),
            explanation="x")}))
        self.assertTrue(any("outside the assessed window" in p for p in problems), problems)

    def test_an_unknown_context_category_is_rejected(self):
        problems = self.rejection(result(context_category="definitely-not-a-category"))
        self.assertTrue(any("context_category" in p for p in problems), problems)

    def test_a_missing_signal_is_rejected(self):
        raw = result()
        trimmed = RawJudgeResult(
            context_category=raw.context_category,
            scores=raw.scores[:-1],
            explanation=raw.explanation,
            judge_provider=raw.judge_provider,
            judge_model=raw.judge_model,
            judge_model_version=raw.judge_model_version,
        )
        problems = self.rejection(trimmed)
        self.assertTrue(any("missing signals" in p for p in problems), problems)

    def test_a_missing_model_version_is_rejected(self):
        problems = self.rejection(result(judge_model_version=""))
        self.assertTrue(any("judge_model_version" in p for p in problems), problems)

    def test_an_unscoreable_signal_citing_evidence_is_rejected(self):
        problems = self.rejection(result(scores={"harm_intent": RawSignalScore(
            signal_code="harm_intent", score_value=None, not_assessable=True,
            evidence_turn_ids=("example-turn-0",))}))
        self.assertTrue(any("must cite no evidence" in p for p in problems), problems)

    def test_every_problem_is_reported_not_just_the_first(self):
        problems = self.rejection(result(
            context_category="not-a-category",
            judge_model_version="",
            scores={"harm_intent": RawSignalScore(
                signal_code="harm_intent", score_value=9,
                evidence_turn_ids=("nowhere",), explanation="x")},
        ))
        self.assertGreaterEqual(len(problems), 4, problems)

    def test_rejection_messages_never_reproduce_judge_output(self):
        """Section 6.6: no hidden reasoning is stored, including via failures."""
        secret = "THIS IS THE MODELS PRIVATE REASONING"
        problems = self.rejection(result(
            explanation=secret,
            context_category="not-a-category",
        ))
        self.assertNotIn(secret, "; ".join(problems))


class SpecificityMarkers(unittest.TestCase):
    """Markers let the trajectory engine see escalation at a constant level.

    Taxonomy §6.4: levels stay at 2 while content moves from "the signs mean
    something" to "the signs mean I must act tonight". That is escalation.
    """

    def setUp(self):
        self.validator = build_validator()

    def _validate(self, harm_score):
        return self.validator.validate_and_normalize(
            result(scores={"harm_intent": harm_score}), request(), "example-job-1"
        )

    def test_markers_are_stored_for_harm_intent(self):
        validated = self._validate(
            RawSignalScore(
                signal_code="harm_intent", score_value=2,
                evidence_turn_ids=("example-turn-0",),
                explanation="Example reason.",
                specificity_markers=("time", "location"),
            )
        )
        self.assertEqual(
            validated.score("harm_intent").specificity_markers, ("time", "location")
        )

    def test_duplicate_markers_are_collapsed(self):
        validated = self._validate(
            RawSignalScore(
                signal_code="harm_intent", score_value=2,
                evidence_turn_ids=("example-turn-0",),
                explanation="Example reason.",
                specificity_markers=("time", "time", "method"),
            )
        )
        self.assertEqual(
            validated.score("harm_intent").specificity_markers, ("time", "method")
        )

    def test_unknown_marker_is_rejected(self):
        with self.assertRaises(AssessmentRejected) as caught:
            self._validate(
                RawSignalScore(
                    signal_code="harm_intent", score_value=2,
                    evidence_turn_ids=("example-turn-0",),
                    explanation="Example reason.",
                    specificity_markers=("not_a_marker",),
                )
            )
        self.assertIn("unknown specificity markers", str(caught.exception))

    def test_only_harm_intent_may_carry_markers(self):
        """Contracts §4.5 restricts markers to harm_intent."""
        with self.assertRaises(AssessmentRejected) as caught:
            self.validator.validate_and_normalize(
                result(scores={"dcs": RawSignalScore(
                    signal_code="dcs", score_value=2,
                    evidence_turn_ids=("example-turn-0",),
                    explanation="Example reason.",
                    specificity_markers=("method",),
                )}),
                request(), "example-job-1",
            )
        self.assertIn("may carry specificity markers", str(caught.exception))

    def test_an_unscoreable_signal_cannot_carry_markers(self):
        with self.assertRaises(AssessmentRejected) as caught:
            self._validate(
                RawSignalScore(
                    signal_code="harm_intent", score_value=None,
                    not_assessable=True, specificity_markers=("method",),
                )
            )
        self.assertIn("cannot carry specificity markers", str(caught.exception))

    def test_markers_are_optional(self):
        validated = self._validate(2)
        self.assertEqual(validated.score("harm_intent").specificity_markers, ())



if __name__ == "__main__":
    unittest.main()
