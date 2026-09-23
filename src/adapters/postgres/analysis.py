"""PostgreSQL JobRepository.

Driver exceptions are translated into the declared error modes; none escape.
"""

from __future__ import annotations

from typing import Any, List, Optional

import psycopg

from src.domain.analysis.records import AnalysisJob, AnalysisRequest, ProcessingStatus
from src.domain.analysis.repository import (
    ConcurrentJobUpdate,
    DuplicateAnalysisRequest,
    JobAlreadyExists,
    JobNotFound,
)

_COLUMNS = (
    "id, session_id, through_turn_id, status, attempt_count, taxonomy_version, "
    "scale_version, rubric_version, judge_configuration_version, schema_version, "
    "requested_at, started_at, completed_at, failure_code, failure_detail"
)
_VERSION_COLUMNS = (
    "taxonomy_version = %s AND scale_version = %s AND rubric_version = %s AND "
    "judge_configuration_version = %s AND schema_version = %s"
)


def _to_job(row: Any) -> AnalysisJob:
    return AnalysisJob(
        id=row[0], session_id=row[1], through_turn_id=row[2],
        status=ProcessingStatus(row[3]), attempt_count=row[4],
        taxonomy_version=row[5], scale_version=row[6], rubric_version=row[7],
        judge_configuration_version=row[8], schema_version=row[9],
        requested_at=row[10], started_at=row[11], completed_at=row[12],
        failure_code=row[13], failure_detail=row[14],
    )


class PostgresJobRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def create(self, job: AnalysisJob) -> AnalysisJob:
        try:
            self._connection.execute(
                "INSERT INTO analysis_jobs ({}) VALUES ({})".format(
                    _COLUMNS, ", ".join(["%s"] * 15)
                ),
                (
                    job.id, job.session_id, job.through_turn_id, job.status.value,
                    job.attempt_count, job.taxonomy_version, job.scale_version,
                    job.rubric_version, job.judge_configuration_version,
                    job.schema_version, job.requested_at, job.started_at,
                    job.completed_at, job.failure_code, job.failure_detail,
                ),
            )
        except psycopg.errors.UniqueViolation as exc:
            if getattr(exc.diag, "constraint_name", None) == "jobs_unique_request":
                raise DuplicateAnalysisRequest(
                    "An equivalent job already exists for session {!r} through "
                    "turn {!r}.".format(job.session_id, job.through_turn_id)
                )
            raise JobAlreadyExists("Job {!r} already exists.".format(job.id))
        return job

    def get(self, job_id: str) -> AnalysisJob:
        row = self._connection.execute(
            "SELECT " + _COLUMNS + " FROM analysis_jobs WHERE id = %s", (job_id,)
        ).fetchone()
        if row is None:
            raise JobNotFound("No analysis job {!r}.".format(job_id))
        return _to_job(row)

    def find_equivalent(self, request: AnalysisRequest) -> Optional[AnalysisJob]:
        versions = request.versions
        row = self._connection.execute(
            "SELECT " + _COLUMNS + " FROM analysis_jobs WHERE session_id = %s AND "
            "through_turn_id = %s AND " + _VERSION_COLUMNS,
            (
                request.session_id, request.through_turn_id,
                versions.taxonomy_version, versions.scale_version,
                versions.rubric_version, versions.judge_configuration_version,
                versions.schema_version,
            ),
        ).fetchone()
        return _to_job(row) if row is not None else None

    def update(self, job: AnalysisJob, expected_status: ProcessingStatus) -> AnalysisJob:
        # Conditional on the stored status, so two workers cannot both claim
        # the same job.
        updated = self._connection.execute(
            "UPDATE analysis_jobs SET status = %s, attempt_count = %s, "
            "started_at = %s, completed_at = %s, failure_code = %s, "
            "failure_detail = %s WHERE id = %s AND status = %s",
            (
                job.status.value, job.attempt_count, job.started_at,
                job.completed_at, job.failure_code, job.failure_detail,
                job.id, expected_status.value,
            ),
        ).rowcount
        if not updated:
            stored = self.get(job.id)
            raise ConcurrentJobUpdate(
                "Job {!r} is {}, expected {}.".format(
                    job.id, stored.status.value, expected_status.value
                )
            )
        return job

    def list_for_session(self, session_id: str) -> List[AnalysisJob]:
        rows = self._connection.execute(
            "SELECT " + _COLUMNS + " FROM analysis_jobs WHERE session_id = %s "
            "ORDER BY requested_at, id",
            (session_id,),
        ).fetchall()
        return [_to_job(row) for row in rows]
