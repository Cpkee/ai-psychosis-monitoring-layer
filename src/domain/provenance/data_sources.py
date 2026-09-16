"""Domain types for data-source provenance and permitted use.

Implements the vocabulary required by `architecture.md`:

* section 6.1 Data Source Registry
* section 6.2 Dataset Use Gate
* section 6.14 Controlled Evaluation Runner (**type and seam only** — no
  execution path is implemented in this phase)
* section 7.2 ``data_source_versions``
* section 8 Data-Source Governance and Guardrails

These are plain domain objects. They hold no storage or provider detail, in
line with principle 3.9 (deep modules at stable seams).
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
from typing import Any, Dict, FrozenSet, Optional, Tuple


def _utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class DataUsePurpose(enum.Enum):
    """Why a caller wants a data source.

    Purposes are the unit the Dataset Use Gate authorises against. They are
    deliberately fine-grained: ``architecture.md`` section 8.1 requires that
    development, training, prompt-tuning, rubric-tuning and model-selection be
    independently refusable for a sealed source.
    """

    DEVELOPMENT = "development"
    TRAINING = "training"
    PROMPT_TUNING = "prompt_tuning"
    RUBRIC_TUNING = "rubric_tuning"
    RUBRIC_VALIDATION = "rubric_validation"
    MODEL_SELECTION = "model_selection"
    DOMAIN_REFERENCE_LABELS = "domain_reference_labels"
    TRANSFORMER_TARGET_LABELS = "transformer_target_labels"
    DOMAIN_PERFORMANCE_EVIDENCE = "domain_performance_evidence"
    INFRASTRUCTURE_FORMAT_TEST = "infrastructure_format_test"
    INTERNAL_VALIDATION = "internal_validation"
    FINAL_EVALUATION = "final_evaluation"


class ExecutionMode(enum.Enum):
    """The mode the calling process is running in.

    Section 6.2 requires ``FINAL_EVALUATION`` execution mode for
    Psychosis-Bench. Mode is a property of the *process*, distinct from the
    purpose of an individual request, so an ordinary development process
    cannot reach sealed data by naming a purpose.
    """

    DEVELOPMENT = "development"
    FINAL_EVALUATION = "final_evaluation"


class AuthorityStatus(enum.Enum):
    """What kind of truth a source carries (architecture section 7.3)."""

    RAW_SOURCE_RECORD = "raw_source_record"
    EXPERIMENT_CONFIGURATION = "experiment_configuration"
    DERIVED_ASSESSMENT = "derived_assessment"
    REVIEWER_OPINION = "reviewer_opinion"
    RELEASED_REFERENCE_LABELS = "released_reference_labels"
    EXTERNAL_BENCHMARK_STIMULUS = "external_benchmark_stimulus"
    GENERATION_INPUT = "generation_input"


@dataclasses.dataclass(frozen=True)
class DataSourceDefinition:
    """Registration input for a data source version.

    Mirrors the ``data_source_versions`` record in architecture section 7.2.
    """

    source_name: str
    source_type: str
    version: str
    provenance: str
    authority_status: AuthorityStatus
    permitted_uses: FrozenSet[DataUsePurpose]
    prohibited_uses: FrozenSet[DataUsePurpose]
    retention_class: str
    sealed: bool
    relative_path: str
    checksum_algorithm: str = "SHA-256"
    checksum: Optional[str] = None
    manifest_relative_path: Optional[str] = None
    access_policy_version: Optional[str] = None
    notes: str = ""

    def __post_init__(self) -> None:
        overlap = self.permitted_uses & self.prohibited_uses
        if overlap:
            raise ValueError(
                "A purpose cannot be both permitted and prohibited: "
                + ", ".join(sorted(p.value for p in overlap))
            )
        if self.sealed and self.permitted_uses != frozenset(
            {DataUsePurpose.FINAL_EVALUATION}
        ):
            raise ValueError(
                "A sealed source may permit only FINAL_EVALUATION. "
                "See architecture.md section 8.1."
            )


@dataclasses.dataclass(frozen=True)
class DataSourceVersion:
    """A registered data source version."""

    source_version_id: str
    definition: DataSourceDefinition
    registered_at: str = dataclasses.field(default_factory=_utc_now)

    @property
    def sealed(self) -> bool:
        return self.definition.sealed


@dataclasses.dataclass(frozen=True)
class IntegrityResult:
    ok: bool
    algorithm: str
    expected_checksum: Optional[str]
    actual_checksum: Optional[str]
    reason: Optional[str] = None
    verified_at: str = dataclasses.field(default_factory=_utc_now)


@dataclasses.dataclass(frozen=True)
class FinalEvaluationSpecification:
    """The frozen artefact versions a final-evaluation run must be tied to.

    Architecture section 6.14 lists these as *required frozen inputs*. This
    type exists so the Dataset Use Gate can refuse benchmark access when a run
    is not tied to them (section 6.2).

    **No runner is implemented.** ``prepare_run`` and ``execute`` belong to
    Phase F and are deliberately absent; defining the type now gives Phase F a
    declared seam without creating a loading path today.

    ``approved_by`` and ``approval_date`` correspond to the ``artifact_versions``
    fields in section 7.2, and carry architecture section 6.13's invariant that
    official evaluation requires independent human approval.
    """

    dataset_version: str
    dataset_checksum: str
    code_release: str
    taxonomy_version: str
    scale_definition_version: str
    rubric_release: str
    judge_configuration_version: str
    prompt_configuration_version: str
    trajectory_policy_version: str
    alert_rule_set_version: str
    evaluation_protocol_version: str
    approved_by: str
    approval_date: str

    def missing_fields(self) -> Tuple[str, ...]:
        return tuple(
            sorted(
                f.name
                for f in dataclasses.fields(self)
                if not str(getattr(self, f.name) or "").strip()
            )
        )


@dataclasses.dataclass(frozen=True)
class DataUseRequest:
    """A request to use a data source for a stated purpose."""

    source_version_id: str
    purpose: Optional[DataUsePurpose]
    execution_mode: ExecutionMode
    requested_by: str
    final_evaluation_specification: Optional[FinalEvaluationSpecification] = None


@dataclasses.dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    source_version_id: str
    purpose: Optional[DataUsePurpose]
    reasons: Tuple[str, ...]
    integrity: Optional[IntegrityResult] = None
    decided_at: str = dataclasses.field(default_factory=_utc_now)


@dataclasses.dataclass(frozen=True)
class AuthorizedDataUse:
    """Proof of authorisation, required by any adapter that reads a source.

    An adapter accepts this object rather than a path, so no reader can be
    called without the gate having allowed the use first.
    """

    source_version_id: str
    purpose: DataUsePurpose
    absolute_path: str
    integrity: IntegrityResult
    audit_event_id: str
    authorized_at: str = dataclasses.field(default_factory=_utc_now)


@dataclasses.dataclass(frozen=True)
class AuditEvent:
    """An authorisation or rejection record (architecture section 6.2)."""

    event_id: str
    event_type: str
    source_version_id: str
    purpose: Optional[str]
    execution_mode: str
    allowed: bool
    reasons: Tuple[str, ...]
    actor: str
    integrity_ok: Optional[bool] = None
    occurred_at: str = dataclasses.field(default_factory=_utc_now)

    def as_dict(self) -> Dict[str, Any]:
        record = dataclasses.asdict(self)
        record["reasons"] = list(self.reasons)
        return record


class DataUseNotAuthorized(RuntimeError):
    """Raised when a data use is refused. Carries the decision for auditing."""

    def __init__(self, decision: AuthorizationDecision):
        self.decision = decision
        super().__init__(
            "Data use refused for source {!r}, purpose {!r}: {}".format(
                decision.source_version_id,
                decision.purpose.value if decision.purpose else None,
                "; ".join(decision.reasons),
            )
        )
