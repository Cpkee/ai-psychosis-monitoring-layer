"""PostgreSQL AssessmentRepository.

``save`` writes three tables inside a savepoint, so a failure part-way through
leaves nothing behind. An assessment without its evidence would be a result
nobody can check.
"""

from __future__ import annotations

from typing import Any, List, Optional

import psycopg

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

_ASSESSMENT_COLUMNS = (
    "id, analysis_job_id, context_category, context_confidence, uncertainty, "
    "insufficient_evidence, explanation, judge_provider, judge_model, "
    "judge_model_version, rubric_version, taxonomy_version, scale_version, "
    "prompt_configuration_version, schema_version, created_at"
)
_SCORE_COLUMNS = (
    "id, assessment_id, signal_code, score_value, scale_version, uncertain, "
    "not_assessable, specificity_markers"
)
_EVIDENCE_COLUMNS = "assessment_id, turn_id, signal_code, evidence_excerpt"


def _to_assessment(row: Any) -> Assessment:
    return Assessment(
        id=row[0], analysis_job_id=row[1], context_category=row[2],
        context_confidence=row[3], uncertainty=row[4],
        insufficient_evidence=row[5], explanation=row[6], judge_provider=row[7],
        judge_model=row[8], judge_model_version=row[9], rubric_version=row[10],
        taxonomy_version=row[11], scale_version=row[12],
        prompt_configuration_version=row[13], schema_version=row[14],
        created_at=row[15],
    )


class PostgresAssessmentRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def save(self, assessment: ValidatedAssessment) -> ValidatedAssessment:
        record = assessment.assessment
        try:
            # A nested transaction, so a failure in any of the three writes
            # rolls back all of them without discarding the caller's outer
            # unit of work.
            with self._connection.transaction():
                self._connection.execute(
                    "INSERT INTO assessments ({}) VALUES ({})".format(
                        _ASSESSMENT_COLUMNS, ", ".join(["%s"] * 16)
                    ),
                    (
                        record.id, record.analysis_job_id, record.context_category,
                        record.context_confidence, record.uncertainty,
                        record.insufficient_evidence, record.explanation,
                        record.judge_provider, record.judge_model,
                        record.judge_model_version, record.rubric_version,
                        record.taxonomy_version, record.scale_version,
                        record.prompt_configuration_version, record.schema_version,
                        record.created_at,
                    ),
                )
                self._connection.cursor().executemany(
                    "INSERT INTO signal_scores ({}) VALUES ({})".format(
                        _SCORE_COLUMNS, ", ".join(["%s"] * 8)
                    ),
                    [
                        (s.id, s.assessment_id, s.signal_code, s.score_value,
                         s.scale_version, s.uncertain, s.not_assessable,
                         list(s.specificity_markers))
                        for s in assessment.scores
                    ],
                )
                if assessment.evidence:
                    self._connection.cursor().executemany(
                        "INSERT INTO assessment_evidence ({}) VALUES ({})".format(
                            _EVIDENCE_COLUMNS, ", ".join(["%s"] * 4)
                        ),
                        [
                            (e.assessment_id, e.turn_id, e.signal_code,
                             e.evidence_excerpt)
                            for e in assessment.evidence
                        ],
                    )
        except psycopg.errors.UniqueViolation:
            raise AssessmentAlreadyExists(
                "An assessment already exists for id {!r} or job {!r}.".format(
                    record.id, record.analysis_job_id
                )
            )
        return assessment

    def get(self, assessment_id: str) -> ValidatedAssessment:
        row = self._connection.execute(
            "SELECT " + _ASSESSMENT_COLUMNS + " FROM assessments WHERE id = %s",
            (assessment_id,),
        ).fetchone()
        if row is None:
            raise AssessmentNotFound("No assessment {!r}.".format(assessment_id))
        return self._load_parts(_to_assessment(row))

    def find_for_job(self, analysis_job_id: str) -> Optional[ValidatedAssessment]:
        row = self._connection.execute(
            "SELECT " + _ASSESSMENT_COLUMNS
            + " FROM assessments WHERE analysis_job_id = %s",
            (analysis_job_id,),
        ).fetchone()
        return self._load_parts(_to_assessment(row)) if row is not None else None

    def _load_parts(self, record: Assessment) -> ValidatedAssessment:
        scores: List[SignalScore] = [
            SignalScore(
                id=r[0], assessment_id=r[1], signal_code=r[2], score_value=r[3],
                scale_version=r[4], uncertain=r[5], not_assessable=r[6],
                specificity_markers=tuple(r[7] or ()),
            )
            for r in self._connection.execute(
                "SELECT " + _SCORE_COLUMNS
                + " FROM signal_scores WHERE assessment_id = %s ORDER BY signal_code",
                (record.id,),
            ).fetchall()
        ]
        evidence: List[EvidenceReference] = [
            EvidenceReference(
                assessment_id=r[0], turn_id=r[1], signal_code=r[2],
                evidence_excerpt=r[3],
            )
            for r in self._connection.execute(
                "SELECT " + _EVIDENCE_COLUMNS
                + " FROM assessment_evidence WHERE assessment_id = %s "
                "ORDER BY signal_code, turn_id",
                (record.id,),
            ).fetchall()
        ]
        return ValidatedAssessment(
            assessment=record, scores=tuple(scores), evidence=tuple(evidence)
        )
