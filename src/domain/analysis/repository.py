"""JobRepository — the persistence seam for analysis jobs.

Same shape as ``ConversationRepository``: one interface, declared error modes,
two adapters, one shared contract suite.
"""

from __future__ import annotations

from typing import List, Optional, Protocol

from src.domain.analysis.records import (
    AnalysisJob,
    AnalysisRequest,
    ProcessingStatus,
)


class JobNotFound(LookupError):
    """No analysis job exists with the given id."""


class JobAlreadyExists(ValueError):
    """A job with the given id is already stored."""


class DuplicateAnalysisRequest(ValueError):
    """An equivalent job already exists for this window and version set.

    Architecture section 13: analysis jobs are unique for the same session
    window and artefact-version set.
    """


class ConcurrentJobUpdate(ValueError):
    """The job was not in the expected state, so another worker changed it."""


class JobRepository(Protocol):
    def create(self, job: AnalysisJob) -> AnalysisJob:
        """Store a new job. Raises :class:`JobAlreadyExists` or
        :class:`DuplicateAnalysisRequest`."""

    def get(self, job_id: str) -> AnalysisJob:
        """Fetch a job. Raises :class:`JobNotFound`."""

    def find_equivalent(self, request: AnalysisRequest) -> Optional[AnalysisJob]:
        """Return the job already covering this window and version set, if any.

        This is what makes ``request_analysis`` idempotent: a retried ingestion
        must not queue the same work twice.
        """

    def update(
        self, job: AnalysisJob, expected_status: "ProcessingStatus"
    ) -> AnalysisJob:
        """Persist a state change, only if the stored status still matches.

        The conditional is what stops two workers from both claiming the same
        job. Raises :class:`ConcurrentJobUpdate` when it does not match.
        """

    def list_for_session(self, session_id: str) -> List[AnalysisJob]:
        """Return the session's jobs, oldest request first."""
