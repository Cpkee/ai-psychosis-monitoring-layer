"""Trajectory records — architecture.md sections 6.8 and 7.2.

These describe **observed conversational change**, never a clinical
conclusion. "Recovery" means an elevated signal decreased in this conversation;
it does not establish that anyone got better.
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Tuple

from src.domain.assessments.records import ValidatedAssessment

#: Direction of change across the window (taxonomy §6.2). ``volatile`` exists so
#: oscillation is never reported as stability.
INCREASING, DECREASING, STABLE, VOLATILE = "increasing", "decreasing", "stable", "volatile"

#: What preceded an observed decrease (taxonomy §6.6). Association, never cause.
INTERVENTION, GROUNDING, NONE_OBSERVED = "intervention", "grounding", "none_observed"


@dataclasses.dataclass(frozen=True)
class AssessedExchange:
    """One assessment, positioned in the conversation."""

    turn_id: str
    turn_index: int
    assessment: ValidatedAssessment


@dataclasses.dataclass(frozen=True)
class SignalTrajectory:
    """How one signal moved across the assessed window."""

    signal_code: str

    current_level: Optional[int] = None
    current_level_turn_id: Optional[str] = None
    stale: bool = False

    change: Optional[int] = None
    change_direction: Optional[str] = None

    persistence_level: Optional[int] = None
    persistence_run_length: int = 0
    persistence_first_turn_id: Optional[str] = None
    persistence_last_turn_id: Optional[str] = None

    escalation_by_level: bool = False
    escalation_by_frequency: bool = False
    escalation_by_specificity: bool = False
    escalation_turn_ids: Tuple[str, ...] = ()

    peak_level: Optional[int] = None
    peak_turn_id: Optional[str] = None

    recovery_decrease: Optional[int] = None
    recovery_sustained_count: int = 0
    recovery_antecedent_turn_id: Optional[str] = None
    recovery_antecedent_kind: Optional[str] = None

    #: Exchanges where this signal could not be scored. Gaps, never zeros.
    null_count: int = 0

    @property
    def escalating(self) -> bool:
        """True if **any** mechanism fired. All three are reported separately."""
        return (
            self.escalation_by_level
            or self.escalation_by_frequency
            or self.escalation_by_specificity
        )


@dataclasses.dataclass(frozen=True)
class TrajectoryState:
    session_id: str
    through_turn_id: str
    window_definition: str
    signals: Tuple[SignalTrajectory, ...]

    def signal(self, signal_code: str) -> SignalTrajectory:
        for trajectory in self.signals:
            if trajectory.signal_code == signal_code:
                return trajectory
        raise KeyError(signal_code)


@dataclasses.dataclass(frozen=True)
class TrajectoryUpdate:
    """A stored derivation, with the assessments that produced it (§7.2)."""

    id: str
    session_id: str
    through_turn_id: str
    trajectory_policy_version: str
    state: TrajectoryState
    input_assessment_ids: Tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        if not self.input_assessment_ids:
            raise ValueError(
                "A trajectory update must name the assessments it was derived "
                "from, or it cannot be recomputed (§19 criterion 7)."
            )
