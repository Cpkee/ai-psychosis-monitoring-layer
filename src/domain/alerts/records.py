"""Alert records — architecture.md sections 6.9 and 7.2.

An alert says a **conversation** warrants human review. It is never a
diagnosis, never a clinical stage, and never causes an automated action.

The shape is §7.2 extended with the §4.7 contract fields that the invariants
depend on (D-38): the exact scores used, the evidence turns, the context
modifier, and the versions of everything upstream. An alert that cannot say
what it was derived from is refused at construction, so it can never be stored.
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Tuple

#: Taxonomy §8, lowest first. These are review priorities, not score values,
#: so they are not tied to the provisional scale.
SEVERITIES = ("low", "medium", "high", "critical")

#: The rule's conditions were met and it assigned a severity.
RAISED = "raised"
#: Harm intent was elevated and escalating, but the companion's response could
#: not be scored, so the rule could not decide. Recorded for manual review with
#: no severity: firing would invent a finding, silence would hide one (D-39).
INDETERMINATE = "indeterminate"


def severity_rank(severity: Optional[str]) -> int:
    """Ordering for supersession. An indeterminate outcome ranks lowest."""
    return -1 if severity is None else SEVERITIES.index(severity)


@dataclasses.dataclass(frozen=True)
class AlertDecision:
    """What one rule concluded from one evaluation input. Pure data: the
    engine produces it without I/O, so it is reproducible from its inputs."""

    session_id: str
    through_turn_id: str
    rule_set_version: str
    rule_id: str
    status: str
    severity: Optional[str]
    requires_manual_review: bool
    contributing_assessment_ids: Tuple[str, ...]
    trajectory_update_id: str
    triggering_signal_score_ids: Tuple[str, ...]
    evidence_turn_ids: Tuple[str, ...]
    context_categories_present: Tuple[str, ...]
    context_modifier_applied: Optional[str]
    explanation: str
    judge_model_version: str
    rubric_version: str
    taxonomy_version: str
    trajectory_policy_version: str

    def __post_init__(self) -> None:
        problems = []
        if self.status not in (RAISED, INDETERMINATE):
            problems.append("status {!r} is not a known outcome".format(self.status))
        if (self.severity is None) != (self.status == INDETERMINATE):
            problems.append("a severity is required if and only if the alert is raised")
        if self.severity is not None and self.severity not in SEVERITIES:
            problems.append("severity {!r} is not one of {}".format(self.severity, SEVERITIES))
        if not self.evidence_turn_ids:
            problems.append("an alert must cite at least one evidence turn")
        if not self.triggering_signal_score_ids:
            problems.append("an alert must name the scores it used")
        if not self.contributing_assessment_ids:
            problems.append("an alert must name the assessments it used")
        for name in ("trajectory_update_id", "rule_set_version", "rule_id", "explanation"):
            if not getattr(self, name):
                problems.append("{} is required".format(name))
        if problems:
            raise ValueError("Invalid alert: " + "; ".join(problems) + ".")


@dataclasses.dataclass(frozen=True)
class Alert:
    """A stored decision. Append-only: ``superseded_by`` is set once, when a
    later decision for the same session and rule replaces this one."""

    id: str
    decision: AlertDecision
    created_at: str
    superseded_by: Optional[str] = None
