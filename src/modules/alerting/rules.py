"""Alert rules and the versioned rule set that configures them.

The **logic** of a rule is code, registered under its ``rule_id``; its
**numbers** come from ``config/alert_rules/``. A threshold change is therefore a
new rule-set version and never touches a signal definition (architecture §6.9).
New logic gets a new ``rule_id``. There is deliberately no rule language: one
rule does not justify one.

Every threshold is provisional pending [OD-004].
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import ClassVar, Dict, List, Optional, Tuple

from src.domain.alerts.records import (
    INDETERMINATE,
    RAISED,
    SEVERITIES,
    AlertDecision,
)
from src.domain.assessments.records import SignalScore, ValidatedAssessment
from src.domain.trajectories.records import TrajectoryUpdate
from src.modules.analysis.definitions import REPO_ROOT, UnknownVersion

DEFAULT_RULES_DIR = os.path.join(REPO_ROOT, "config", "alert_rules")


@dataclasses.dataclass(frozen=True)
class AlertEvaluationInput:
    """The latest assessment, and the trajectory recomputed through it.

    ``latest`` must be the assessment at ``trajectory.through_turn_id``: the
    rule reads the current exchange's scores and the whole session's movement.
    """

    latest: ValidatedAssessment
    trajectory: TrajectoryUpdate

    def __post_init__(self) -> None:
        if self.latest.assessment.id not in self.trajectory.input_assessment_ids:
            raise ValueError(
                "The trajectory was not derived from the assessment being "
                "evaluated, so the alert could not be reproduced from its inputs."
            )


@dataclasses.dataclass(frozen=True)
class HarmIntentUnaddressed:
    """IMPLEMENTATION_FOUNDATION.md §5: elevated, escalating harm intent that
    the companion did not address.

    Context never suppresses: a non-personal frame lowers severity one level,
    no further than the floor, and names the modifier on the alert. Uncertain
    context is not lowered and requires manual review (taxonomy §8, rule 3).
    ``spiritual_cultural`` is not a non-personal context and is not lowered.
    """

    RULE_ID: ClassVar[str] = "harm-intent-unaddressed"

    harm_intent_min: int
    sis_unaddressed_value: int
    hes_min: int
    critical_harm_intent: int
    nonpersonal_contexts: Tuple[str, ...]
    uncertain_context: str
    context_modifier: str
    severity_floor: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "nonpersonal_contexts", tuple(self.nonpersonal_contexts))
        if self.severity_floor not in SEVERITIES:
            raise ValueError("severity_floor {!r} is not a severity.".format(self.severity_floor))

    def evaluate(
        self, subject: AlertEvaluationInput, rule_set_version: str
    ) -> Optional[AlertDecision]:
        latest = subject.latest
        harm = latest.score("harm_intent")
        # A null harm_intent means "could not tell". It is never 0, and it is
        # never enough to fire.
        if harm.score_value is None or harm.score_value < self.harm_intent_min:
            return None

        movement = subject.trajectory.state.signal("harm_intent")
        mechanisms = [
            name for name, fired in (
                ("by level", movement.escalation_by_level),
                ("by specificity", movement.escalation_by_specificity),
            ) if fired
        ]
        if not mechanisms:
            return None

        sis, hes = latest.score("sis"), latest.score("hes")
        unaddressed = self._unaddressed(sis, hes)
        if unaddressed is False:
            return None

        context = latest.assessment.context_category
        modifier = None
        if unaddressed is None:
            status, severity = INDETERMINATE, None
        else:
            status = RAISED
            severity = (
                "critical"
                if harm.score_value >= self.critical_harm_intent and harm.specificity_markers
                else "high"
            )
            if context in self.nonpersonal_contexts:
                severity = self._lower_one_level(severity)
                modifier = self.context_modifier

        triggering = (harm, sis, hes)
        return AlertDecision(
            session_id=subject.trajectory.session_id,
            through_turn_id=subject.trajectory.through_turn_id,
            rule_set_version=rule_set_version,
            rule_id=self.RULE_ID,
            status=status,
            severity=severity,
            requires_manual_review=(
                status == INDETERMINATE or context == self.uncertain_context
            ),
            contributing_assessment_ids=subject.trajectory.input_assessment_ids,
            trajectory_update_id=subject.trajectory.id,
            triggering_signal_score_ids=tuple(score.id for score in triggering),
            evidence_turn_ids=_unique(
                list(movement.escalation_turn_ids)
                + [
                    reference.turn_id
                    for score in triggering
                    for reference in latest.evidence_for(score.signal_code)
                ]
            ),
            context_categories_present=(context,),
            context_modifier_applied=modifier,
            explanation=self._explain(
                harm, mechanisms, sis, hes, context, modifier, status, severity,
                rule_set_version,
            ),
            judge_model_version=latest.assessment.judge_model_version,
            rubric_version=latest.assessment.rubric_version,
            taxonomy_version=latest.assessment.taxonomy_version,
            trajectory_policy_version=subject.trajectory.trajectory_policy_version,
        )

    def _unaddressed(self, sis: SignalScore, hes: SignalScore) -> Optional[bool]:
        """True or False when the scores decide it; None when they cannot.

        Either condition is enough on its own, so a known SIS of 0 or a known
        HES at the threshold decides the question even if the other is null.
        """
        if sis.score_value == self.sis_unaddressed_value:
            return True
        if hes.score_value is not None and hes.score_value >= self.hes_min:
            return True
        if sis.score_value is None or hes.score_value is None:
            return None
        return False

    def _lower_one_level(self, severity: str) -> str:
        lowered = SEVERITIES.index(severity) - 1
        return SEVERITIES[max(lowered, SEVERITIES.index(self.severity_floor))]

    def _explain(self, harm, mechanisms, sis, hes, context, modifier, status,
                 severity, rule_set_version) -> str:
        """Plain language, built only from the facts the alert cites."""
        detail = (
            " with specific details stated ({})".format(", ".join(harm.specificity_markers))
            if harm.specificity_markers else ""
        )
        parts = [
            "Harm intent scored {} at this exchange{}, and has escalated {} "
            "across the conversation.".format(harm.score_value, detail, " and ".join(mechanisms))
        ]
        if status == RAISED:
            reasons = []
            if sis.score_value == self.sis_unaddressed_value:
                reasons.append("suggested no support (SIS {})".format(sis.score_value))
            if hes.score_value is not None and hes.score_value >= self.hes_min:
                reasons.append("scored {} for harm enablement (HES)".format(hes.score_value))
            parts.append("The companion's response {}.".format(" and ".join(reasons)))
        else:
            parts.append(
                "Whether the companion addressed it could not be determined: "
                "SIS was {} and HES was {}.".format(_shown(sis), _shown(hes))
            )
        parts.append("Context: {}.".format(context))
        if modifier:
            parts.append(
                "A non-personal context lowered severity by one level ({}); "
                "it does not suppress the alert.".format(modifier)
            )
        if context == self.uncertain_context:
            parts.append("Context is uncertain, so severity is not lowered and "
                         "manual review is required.")
        parts.append(
            "Rule {} ({}) {}.".format(
                self.RULE_ID, rule_set_version,
                "raised severity {}".format(severity) if status == RAISED
                else "could not decide; manual review is required",
            )
        )
        return " ".join(parts)


#: Rule logic by ``rule_id``. The config chooses among these; it cannot add one.
RULE_TYPES = {HarmIntentUnaddressed.RULE_ID: HarmIntentUnaddressed}


@dataclasses.dataclass(frozen=True)
class AlertRuleSet:
    version: str
    status: str
    rules: Tuple[HarmIntentUnaddressed, ...]


def load_rule_set(version: str, rules_dir: Optional[str] = None) -> AlertRuleSet:
    """Load a rule set. Fails closed on an unknown version, an unknown rule or
    a missing or unexpected parameter: a half-configured rule never runs."""
    path = os.path.join(rules_dir or DEFAULT_RULES_DIR, "{}.json".format(version))
    if not os.path.exists(path):
        raise UnknownVersion("No alert rule set {!r}.".format(version))
    with open(path, "r", encoding="utf-8") as handle:
        document = json.load(handle)

    rules: List[HarmIntentUnaddressed] = []
    for entry in document["rules"]:
        rule_type = RULE_TYPES.get(entry["rule_id"])
        if rule_type is None:
            raise UnknownVersion("Rule set {} names unknown rule {!r}.".format(
                version, entry["rule_id"]))
        parameters: Dict = dict(entry["parameters"])
        try:
            rules.append(rule_type(**parameters))
        except TypeError as exc:
            raise ValueError("Rule {!r} in {} is misconfigured: {}".format(
                entry["rule_id"], version, exc))
    return AlertRuleSet(
        version=document["rule_set_version"], status=document["status"], rules=tuple(rules)
    )


def _unique(turn_ids: List[str]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(turn_ids))


def _shown(score: SignalScore) -> str:
    return "not assessable" if score.score_value is None else str(score.score_value)
