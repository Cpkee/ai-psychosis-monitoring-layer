"""In-memory AssessmentRepository.

Atomicity is trivially true here because a dict write cannot fail halfway.
That is exactly why the PostgreSQL adapter carries the real test.
"""

from __future__ import annotations

from typing import Dict, Optional

from src.domain.assessments.records import ValidatedAssessment
from src.domain.assessments.repository import (
    AssessmentAlreadyExists,
    AssessmentNotFound,
)


class InMemoryAssessmentRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, ValidatedAssessment] = {}
        self._by_job: Dict[str, str] = {}

    def save(self, assessment: ValidatedAssessment) -> ValidatedAssessment:
        record = assessment.assessment
        if record.id in self._by_id:
            raise AssessmentAlreadyExists(
                "Assessment {!r} already exists.".format(record.id)
            )
        if record.analysis_job_id in self._by_job:
            raise AssessmentAlreadyExists(
                "Job {!r} already produced an assessment.".format(record.analysis_job_id)
            )
        self._by_id[record.id] = assessment
        self._by_job[record.analysis_job_id] = record.id
        return assessment

    def get(self, assessment_id: str) -> ValidatedAssessment:
        try:
            return self._by_id[assessment_id]
        except KeyError:
            raise AssessmentNotFound("No assessment {!r}.".format(assessment_id))

    def find_for_job(self, analysis_job_id: str) -> Optional[ValidatedAssessment]:
        assessment_id = self._by_job.get(analysis_job_id)
        return self._by_id[assessment_id] if assessment_id else None
