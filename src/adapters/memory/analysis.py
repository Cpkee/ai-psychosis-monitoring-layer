"""In-memory JobRepository."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.domain.analysis.records import AnalysisJob, AnalysisRequest, ProcessingStatus
from src.domain.analysis.repository import (
    ConcurrentJobUpdate,
    DuplicateAnalysisRequest,
    JobAlreadyExists,
    JobNotFound,
)


def _request_key(session_id: str, through_turn_id: str, versions) -> Tuple[str, ...]:
    return (
        session_id,
        through_turn_id,
        versions.taxonomy_version,
        versions.scale_version,
        versions.rubric_version,
        versions.judge_configuration_version,
        versions.schema_version,
    )


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._jobs: Dict[str, AnalysisJob] = {}
        self._order: List[str] = []

    def create(self, job: AnalysisJob) -> AnalysisJob:
        if job.id in self._jobs:
            raise JobAlreadyExists("Job {!r} already exists.".format(job.id))
        key = _request_key(job.session_id, job.through_turn_id, job.versions)
        for existing in self._jobs.values():
            if _request_key(existing.session_id, existing.through_turn_id, existing.versions) == key:
                raise DuplicateAnalysisRequest(
                    "An equivalent job already exists for session {!r} through "
                    "turn {!r}.".format(job.session_id, job.through_turn_id)
                )
        self._jobs[job.id] = job
        self._order.append(job.id)
        return job

    def get(self, job_id: str) -> AnalysisJob:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise JobNotFound("No analysis job {!r}.".format(job_id))

    def find_equivalent(self, request: AnalysisRequest) -> Optional[AnalysisJob]:
        key = _request_key(request.session_id, request.through_turn_id, request.versions)
        for job_id in self._order:
            job = self._jobs[job_id]
            if _request_key(job.session_id, job.through_turn_id, job.versions) == key:
                return job
        return None

    def update(self, job: AnalysisJob, expected_status: ProcessingStatus) -> AnalysisJob:
        stored = self.get(job.id)
        if stored.status is not expected_status:
            raise ConcurrentJobUpdate(
                "Job {!r} is {}, expected {}.".format(
                    job.id, stored.status.value, expected_status.value
                )
            )
        self._jobs[job.id] = job
        return job

    def list_for_session(self, session_id: str) -> List[AnalysisJob]:
        return [self._jobs[i] for i in self._order if self._jobs[i].session_id == session_id]
