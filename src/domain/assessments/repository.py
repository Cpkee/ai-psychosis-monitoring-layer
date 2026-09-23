"""AssessmentRepository — the persistence seam for assessments.

The save spans three tables and **must be atomic**. An assessment stored
without its evidence rows would be a result nobody can check, breaching
architecture section 19 criterion 4.
"""

from __future__ import annotations

from typing import Optional, Protocol

from src.domain.assessments.records import ValidatedAssessment


class AssessmentNotFound(LookupError):
    """No assessment exists with the given id."""


class AssessmentAlreadyExists(ValueError):
    """An assessment with the given id, or for the given job, already exists."""


class AssessmentRepository(Protocol):
    def save(self, assessment: ValidatedAssessment) -> ValidatedAssessment:
        """Store an assessment with its scores and evidence, atomically."""

    def get(self, assessment_id: str) -> ValidatedAssessment:
        """Fetch an assessment with its parts. Raises :class:`AssessmentNotFound`."""

    def find_for_job(self, analysis_job_id: str) -> Optional[ValidatedAssessment]:
        """Return the assessment produced by a job, if it completed."""
