"""Dataset Use Gate — architecture.md section 6.2.

Enforces source permissions before data reaches a workflow.

Behaviour required by the architecture:

* Fail closed when the source is unregistered, its purpose is unspecified, or
  integrity validation fails.
* Emit an audit event for every authorisation **and** rejection.
* Require ``FINAL_EVALUATION`` execution mode for Psychosis-Bench.
* Refuse benchmark access when the run is not tied to frozen artefact versions.

This is the only path by which a reader may obtain an :class:`AuthorizedDataUse`.
Adapters accept that object rather than a path, so there is no loading path
that bypasses this gate.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from src.domain.provenance.data_sources import (
    AuditEvent,
    AuthorizationDecision,
    AuthorizedDataUse,
    DataUseNotAuthorized,
    DataUsePurpose,
    DataUseRequest,
    ExecutionMode,
    IntegrityResult,
)
from src.modules.source_registry.registry import DataSourceRegistry


class InMemoryAuditSink:
    """Collects authorisation and rejection events.

    Architecture section 6.2 requires an event for every decision. Persisting
    them is a deployment concern; nothing in this phase reads them back, so no
    persistent sink exists yet.
    """

    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


class DatasetUseGate:
    """The single authorisation seam for every data source."""

    def __init__(
        self,
        registry: Optional[DataSourceRegistry] = None,
        audit_sink: Optional[InMemoryAuditSink] = None,
    ):
        self._registry = registry or DataSourceRegistry()
        self._audit = audit_sink or InMemoryAuditSink()

    @property
    def registry(self) -> DataSourceRegistry:
        return self._registry

    def decide(self, request: DataUseRequest) -> AuthorizationDecision:
        """Evaluate a request and emit an audit event. Never raises on refusal."""
        reasons: List[str] = []
        integrity: Optional[IntegrityResult] = None

        permission = self._registry.authorize_use(
            request.source_version_id, request.purpose
        )
        reasons.extend(permission.reasons)

        source = None
        if not any("Unregistered data source" in reason for reason in reasons):
            source = self._registry.get_source(request.source_version_id)

        if source is not None and source.sealed:
            reasons.extend(self._sealed_source_reasons(request))

        if source is not None:
            integrity = self._registry.verify_integrity(request.source_version_id)
            if not integrity.ok:
                reasons.append(
                    "Integrity verification failed: {}".format(
                        integrity.reason or "unknown reason"
                    )
                )

        decision = AuthorizationDecision(
            allowed=not reasons,
            source_version_id=request.source_version_id,
            purpose=request.purpose,
            reasons=tuple(reasons),
            integrity=integrity,
        )
        self._emit(request, decision)
        return decision

    def authorize(self, request: DataUseRequest) -> AuthorizedDataUse:
        """Authorise a data use, or raise :class:`DataUseNotAuthorized`.

        This is the interface named in architecture section 6.2.
        """
        decision = self.decide(request)
        if not decision.allowed:
            raise DataUseNotAuthorized(decision)

        assert decision.purpose is not None
        assert decision.integrity is not None
        return AuthorizedDataUse(
            source_version_id=request.source_version_id,
            purpose=decision.purpose,
            absolute_path=self._registry.absolute_path(request.source_version_id),
            integrity=decision.integrity,
            audit_event_id=self._last_event_id,
        )

    # -- internals -------------------------------------------------------

    def _sealed_source_reasons(self, request: DataUseRequest) -> List[str]:
        reasons: List[str] = []

        if request.execution_mode is not ExecutionMode.FINAL_EVALUATION:
            reasons.append(
                "Sealed sources require FINAL_EVALUATION execution mode; this "
                "process is running in {} mode.".format(request.execution_mode.value)
            )

        specification = request.final_evaluation_specification
        if specification is None:
            reasons.append(
                "Sealed access requires a FinalEvaluationSpecification tying "
                "the run to frozen artefact versions (architecture.md section 6.14)."
            )
        else:
            missing = specification.missing_fields()
            if missing:
                reasons.append(
                    "FinalEvaluationSpecification is incomplete. Missing frozen "
                    "inputs: " + ", ".join(missing)
                )
        return reasons

    def _emit(self, request: DataUseRequest, decision: AuthorizationDecision) -> None:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type="data_use_authorization" if decision.allowed else "data_use_rejection",
            source_version_id=request.source_version_id,
            purpose=request.purpose.value if request.purpose else None,
            execution_mode=request.execution_mode.value,
            allowed=decision.allowed,
            reasons=decision.reasons,
            actor=request.requested_by,
            integrity_ok=decision.integrity.ok if decision.integrity else None,
        )
        self._last_event_id = event.event_id
        self._audit.record(event)

    _last_event_id: str = ""


def development_request(
    source_version_id: str, purpose: DataUsePurpose, requested_by: str = "developer"
) -> DataUseRequest:
    """Convenience constructor for an ordinary development-mode request."""
    return DataUseRequest(
        source_version_id=source_version_id,
        purpose=purpose,
        execution_mode=ExecutionMode.DEVELOPMENT,
        requested_by=requested_by,
    )
