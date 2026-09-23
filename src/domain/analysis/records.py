"""Analysis job records — architecture.md sections 6.4 and 7.2.

An analysis job is a durable note that a session needs analysing up to a given
turn, under a named set of artefact versions, and what state that work is in.

It exists because scoring is slow and can fail. Ingestion records the need and
returns; a worker does the work later. Without the job row, a failed analysis
would be indistinguishable from "nothing concerning found".
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Optional


class ProcessingStatus(enum.Enum):
    """Section 6.4 lifecycle.

    ``PENDING -> PROCESSING -> COMPLETED``, branching to ``DELAYED`` (retryable)
    and ``FAILED`` (terminal). ``DELAYED`` returns to ``PROCESSING`` on retry.
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"
    FAILED = "FAILED"


@dataclasses.dataclass(frozen=True)
class ArtefactVersions:
    """The versions in force when analysis is requested.

    Section 6.4 requires a job to record these. Pinning them at request time is
    what stops a later rubric change from rewriting the story of how an
    existing result was produced.
    """

    taxonomy_version: str
    scale_version: str
    rubric_version: str
    judge_configuration_version: str
    schema_version: str

    def __post_init__(self) -> None:
        missing = [
            f.name
            for f in dataclasses.fields(self)
            if not str(getattr(self, f.name) or "").strip()
        ]
        if missing:
            raise ValueError(
                "Artefact versions are required: " + ", ".join(sorted(missing))
            )


@dataclasses.dataclass(frozen=True)
class AnalysisRequest:
    """A request to analyse ``session_id`` up to and including ``through_turn_id``."""

    session_id: str
    through_turn_id: str
    versions: ArtefactVersions


@dataclasses.dataclass(frozen=True)
class AnalysisJob:
    """Fields exactly as architecture section 7.2 lists them."""

    id: str
    session_id: str
    through_turn_id: str
    status: ProcessingStatus
    attempt_count: int
    taxonomy_version: str
    scale_version: str
    rubric_version: str
    judge_configuration_version: str
    schema_version: str
    requested_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failure_code: Optional[str] = None
    #: Extends section 7.2. Holds *our own* validation messages so a failure can
    #: be diagnosed. Never provider output, which would risk retaining the
    #: hidden reasoning section 6.6 forbids.
    failure_detail: Optional[str] = None

    def __post_init__(self) -> None:
        if self.attempt_count < 0:
            raise ValueError("attempt_count must be non-negative.")
        if self.status is ProcessingStatus.FAILED and not self.failure_code:
            raise ValueError("A FAILED job must record a failure_code.")
        if self.status is ProcessingStatus.COMPLETED and not self.completed_at:
            raise ValueError("A COMPLETED job must record completed_at.")

    @property
    def versions(self) -> ArtefactVersions:
        return ArtefactVersions(
            taxonomy_version=self.taxonomy_version,
            scale_version=self.scale_version,
            rubric_version=self.rubric_version,
            judge_configuration_version=self.judge_configuration_version,
            schema_version=self.schema_version,
        )


class InvalidTransition(ValueError):
    """A job was moved between states the lifecycle does not permit."""


#: Section 6.4 lifecycle. ``DELAYED`` returns to ``PROCESSING`` on retry;
#: ``COMPLETED`` and ``FAILED`` are terminal.
TRANSITIONS = {
    ProcessingStatus.PENDING: (ProcessingStatus.PROCESSING,),
    ProcessingStatus.PROCESSING: (
        ProcessingStatus.COMPLETED,
        ProcessingStatus.DELAYED,
        ProcessingStatus.FAILED,
    ),
    ProcessingStatus.DELAYED: (ProcessingStatus.PROCESSING, ProcessingStatus.FAILED),
    ProcessingStatus.COMPLETED: (),
    ProcessingStatus.FAILED: (),
}


def _move(job: AnalysisJob, to: ProcessingStatus, **changes) -> AnalysisJob:
    if to not in TRANSITIONS[job.status]:
        raise InvalidTransition(
            "Job {!r} cannot move from {} to {}.".format(
                job.id, job.status.value, to.value
            )
        )
    return dataclasses.replace(job, status=to, **changes)


def claim(job: AnalysisJob, started_at: str) -> AnalysisJob:
    """Take a pending or delayed job for processing, recording the attempt."""
    return _move(
        job,
        ProcessingStatus.PROCESSING,
        started_at=started_at,
        attempt_count=job.attempt_count + 1,
    )


def complete(job: AnalysisJob, completed_at: str) -> AnalysisJob:
    return _move(job, ProcessingStatus.COMPLETED, completed_at=completed_at)


def delay(job: AnalysisJob, reason: str) -> AnalysisJob:
    """Defer retryable work. Distinct from failure: delay is expected."""
    return _move(job, ProcessingStatus.DELAYED, failure_detail=reason)


def fail(job: AnalysisJob, failure_code: str, detail: str) -> AnalysisJob:
    return _move(
        job, ProcessingStatus.FAILED, failure_code=failure_code, failure_detail=detail
    )
