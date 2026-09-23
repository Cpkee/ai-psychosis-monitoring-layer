"""Alert Engine — architecture.md section 6.9.

Applies a versioned rule set to the latest validated assessment and the
trajectory recomputed through it. Pure: no I/O, no clock, no ids. The same
inputs always give the same decisions, which is what makes every alert
reproducible from what it cites.

An alert asks a person to review a conversation. It does not diagnose anyone
and it does not act: nothing here blocks, rewrites or notifies.
"""

from __future__ import annotations

from typing import Tuple

from src.domain.alerts.records import Alert, AlertDecision, severity_rank
from src.modules.alerting.rules import AlertEvaluationInput, AlertRuleSet


class AlertEngine:
    def __init__(self, rule_set: AlertRuleSet):
        self._rule_set = rule_set

    def evaluate(self, subject: AlertEvaluationInput) -> Tuple[AlertDecision, ...]:
        """One decision per rule that fired or could not decide."""
        decisions = []
        for rule in self._rule_set.rules:
            decision = rule.evaluate(subject, self._rule_set.version)
            if decision is not None:
                decisions.append(decision)
        return tuple(decisions)


def supersedes(decision: AlertDecision, active: Alert) -> bool:
    """Whether a new decision replaces the session's active alert for its rule.

    Only if it is at least as severe (D-39). A falling score must not quietly
    downgrade what a reviewer sees: the peak stays in front of them until a
    person reviews it (taxonomy §8, rule 4), and an indeterminate outcome never
    replaces a raised one, because uncertainty escalates and never
    de-escalates. The stored assessments and trajectory still hold every later
    fact.
    """
    return severity_rank(decision.severity) >= severity_rank(active.decision.severity)
