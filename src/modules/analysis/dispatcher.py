"""Analysis Job Dispatcher — architecture.md section 6.4.

Partially implemented, deliberately. ``request_analysis`` exists because the
Conversation Orchestrator needs it now. ``retry`` and ``get_status`` are
**absent rather than stubbed** until a worker exists to drive them; an absent
method is honest, a stub that returns nothing is not.
"""

from __future__ import annotations

import uuid
from typing import Callable, Optional

from src.domain.analysis.records import (
    AnalysisJob,
    AnalysisRequest,
    ArtefactVersions,
    ProcessingStatus,
)
from src.domain.analysis.repository import JobRepository


class AnalysisJobDispatcher:
    """Turns a request to analyse into a durable, idempotent job record.

    The artefact versions in force are configuration, supplied once at
    construction, so every job created by this dispatcher is pinned to the same
    set (section 6.4).
    """

    def __init__(
        self,
        jobs: JobRepository,
        versions: ArtefactVersions,
        clock: Callable[[], str],
        new_id: Optional[Callable[[], str]] = None,
    ):
        self._jobs = jobs
        self._versions = versions
        self._clock = clock
        self._new_id = new_id or (lambda: str(uuid.uuid4()))

    def request_analysis(self, session_id: str, through_turn_id: str) -> AnalysisJob:
        """Record that a session needs analysing up to ``through_turn_id``.

        Idempotent: a repeated request for the same window and version set
        returns the existing job rather than queueing the work twice
        (section 13).
        """
        request = AnalysisRequest(
            session_id=session_id,
            through_turn_id=through_turn_id,
            versions=self._versions,
        )
        existing = self._jobs.find_equivalent(request)
        if existing is not None:
            return existing

        return self._jobs.create(
            AnalysisJob(
                id=self._new_id(),
                session_id=session_id,
                through_turn_id=through_turn_id,
                status=ProcessingStatus.PENDING,
                attempt_count=0,
                taxonomy_version=self._versions.taxonomy_version,
                scale_version=self._versions.scale_version,
                rubric_version=self._versions.rubric_version,
                judge_configuration_version=self._versions.judge_configuration_version,
                schema_version=self._versions.schema_version,
                requested_at=self._clock(),
            )
        )
