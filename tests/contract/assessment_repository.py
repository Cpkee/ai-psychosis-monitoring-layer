"""AssessmentRepository contract — run against every implementation."""

from __future__ import annotations

from src.domain.assessments.records import (
    Assessment,
    EvidenceReference,
    SignalScore,
    ValidatedAssessment,
)
from src.domain.assessments.repository import (
    AssessmentAlreadyExists,
    AssessmentNotFound,
)

SIGNALS = (
    "belief_conviction", "pattern_seeking", "ai_dependency",
    "social_withdrawal", "harm_intent", "dcs", "hes", "sis", "sgq",
)


def make_assessment(assessment_id="example-assessment-1", job_id="example-job-1",
                    scored=None, evidence_turn="example-turn-1", markers=()):
    scored = scored if scored is not None else {"harm_intent": 2}
    record = Assessment(
        id=assessment_id,
        analysis_job_id=job_id,
        context_category="personal",
        context_confidence="high",
        uncertainty="none",
        insufficient_evidence=False,
        explanation="Example explanation.",
        judge_provider="example-provider",
        judge_model="example-model",
        judge_model_version="example-2026-01",
        rubric_version="rubric_v0.1",
        taxonomy_version="taxonomy_v0.1",
        scale_version="scale_0_3_v0.1",
        prompt_configuration_version="judge_v0_1",
        schema_version="assessment_v0.1",
        created_at="2026-01-01T00:00:00Z",
    )
    def _score(code):
        value = scored.get(code, 0)
        return SignalScore(
            id="{}-{}".format(assessment_id, code),
            assessment_id=assessment_id,
            signal_code=code,
            score_value=value,
            scale_version="scale_0_3_v0.1",
            not_assessable=value is None,
            specificity_markers=tuple(markers) if code == "harm_intent" else (),
        )

    scores = tuple(_score(code) for code in SIGNALS)
    evidence = tuple(
        EvidenceReference(
            assessment_id=assessment_id, turn_id=evidence_turn, signal_code=code
        )
        for code, value in scored.items()
        if value
    )
    return ValidatedAssessment(assessment=record, scores=scores, evidence=evidence)


class AssessmentRepositoryContract:
    """Subclass alongside ``unittest.TestCase`` and implement :meth:`repository`."""

    def repository(self):
        raise NotImplementedError

    def test_save_and_get_round_trips_all_three_parts(self):
        repo = self.repository()
        saved = repo.save(make_assessment())
        loaded = repo.get(saved.assessment.id)
        self.assertEqual(loaded.assessment, saved.assessment)
        self.assertEqual(len(loaded.scores), 9)
        self.assertEqual(len(loaded.evidence), 1)

    def test_get_unknown_raises(self):
        with self.assertRaises(AssessmentNotFound):
            self.repository().get("no-such-assessment")

    def test_find_for_job(self):
        repo = self.repository()
        saved = repo.save(make_assessment())
        self.assertEqual(repo.find_for_job("example-job-1").assessment, saved.assessment)
        self.assertIsNone(repo.find_for_job("example-job-2"))

    def test_a_job_produces_at_most_one_assessment(self):
        repo = self.repository()
        repo.save(make_assessment())
        with self.assertRaises(AssessmentAlreadyExists):
            repo.save(make_assessment(assessment_id="example-assessment-2"))

    def test_unscoreable_signal_round_trips_as_null_not_zero(self):
        """The rule that matters most: "could not tell" never becomes zero."""
        repo = self.repository()
        repo.save(make_assessment(scored={"harm_intent": None}))
        loaded = repo.get("example-assessment-1")
        harm = loaded.score("harm_intent")
        self.assertIsNone(harm.score_value)
        self.assertTrue(harm.not_assessable)
        self.assertNotEqual(harm.score_value, 0)

    def test_every_version_field_survives_storage(self):
        """Section 19 criterion 3."""
        repo = self.repository()
        repo.save(make_assessment())
        stored = repo.get("example-assessment-1").assessment
        for field in (
            "rubric_version", "taxonomy_version", "scale_version",
            "prompt_configuration_version", "schema_version",
            "judge_model_version", "judge_provider",
        ):
            with self.subTest(field=field):
                self.assertTrue(getattr(stored, field))

    def test_evidence_is_traceable_to_a_turn(self):
        repo = self.repository()
        repo.save(make_assessment())
        evidence = repo.get("example-assessment-1").evidence_for("harm_intent")
        self.assertEqual([e.turn_id for e in evidence], ["example-turn-1"])

    def test_specificity_markers_survive_a_round_trip(self):
        """Without these the trajectory engine cannot see escalation at a
        constant level, which is the pattern taxonomy §6.4 calls out."""
        repo = self.repository()
        repo.save(make_assessment(markers=("time", "location")))
        stored = repo.get("example-assessment-1")
        self.assertEqual(
            stored.score("harm_intent").specificity_markers, ("time", "location")
        )

    def test_absent_markers_round_trip_as_empty(self):
        repo = self.repository()
        repo.save(make_assessment())
        stored = repo.get("example-assessment-1")
        self.assertEqual(stored.score("harm_intent").specificity_markers, ())
        self.assertEqual(stored.score("dcs").specificity_markers, ())
