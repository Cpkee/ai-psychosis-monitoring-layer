"""Alert Engine and rule — architecture.md §6.9, IMPLEMENTATION_FOUNDATION.md §5.

No database: the engine is pure, so every case is a table of fabricated scores
and trajectory facts. Every value is an example; thresholds are provisional
pending [OD-004].
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import unittest

from src.domain.alerts.records import INDETERMINATE, RAISED, Alert
from src.domain.assessments.records import (
    Assessment,
    EvidenceReference,
    SignalScore,
    ValidatedAssessment,
)
from src.domain.trajectories.records import (
    SignalTrajectory,
    TrajectoryState,
    TrajectoryUpdate,
)
from src.modules.alerting.engine import AlertEngine, supersedes
from src.modules.alerting.rules import (
    DEFAULT_RULES_DIR,
    AlertEvaluationInput,
    UnknownVersion,
    load_rule_set,
)

SIGNALS = ("belief_conviction", "pattern_seeking", "ai_dependency", "social_withdrawal",
           "harm_intent", "dcs", "hes", "sis", "sgq")


def assessment(harm=2, markers=(), sis=0, hes=0, context="personal") -> ValidatedAssessment:
    values = {"harm_intent": harm, "sis": sis, "hes": hes}
    scores, evidence = [], []
    for code in SIGNALS:
        value = values.get(code, 0)
        scores.append(SignalScore(
            id="example-score-{}".format(code), assessment_id="example-assessment-2",
            signal_code=code, score_value=value, scale_version="scale_0_3_v0.1",
            not_assessable=value is None,
            specificity_markers=markers if code == "harm_intent" else (),
        ))
        if value:
            evidence.append(EvidenceReference(
                assessment_id="example-assessment-2", turn_id="example-turn-2",
                signal_code=code))
    return ValidatedAssessment(
        assessment=Assessment(
            id="example-assessment-2", analysis_job_id="example-job-2",
            context_category=context, uncertainty=None, insufficient_evidence=False,
            explanation="Example.", judge_provider="example-provider",
            judge_model="example-model", judge_model_version="example-2026-01",
            rubric_version="rubric_v0.1", taxonomy_version="taxonomy_v0.1",
            scale_version="scale_0_3_v0.1", prompt_configuration_version="judge_v0_1",
            schema_version="assessment_v0.1", created_at="2026-01-01T00:00:00Z"),
        scores=tuple(scores),
        evidence=tuple(evidence),
    )


def trajectory(by_level=True, by_specificity=False, by_frequency=False) -> TrajectoryUpdate:
    escalating = by_level or by_specificity or by_frequency
    harm = SignalTrajectory(
        signal_code="harm_intent", current_level=2,
        escalation_by_level=by_level, escalation_by_specificity=by_specificity,
        escalation_by_frequency=by_frequency,
        escalation_turn_ids=("example-turn-0", "example-turn-2") if escalating else (),
    )
    return TrajectoryUpdate(
        id="example-trajectory-1", session_id="example-session-1",
        through_turn_id="example-turn-3", trajectory_policy_version="trajectory_v0.1",
        state=TrajectoryState(session_id="example-session-1", through_turn_id="example-turn-3",
                              window_definition="whole_session_v0.1", signals=(harm,)),
        input_assessment_ids=("example-assessment-1", "example-assessment-2"),
        created_at="2026-01-01T00:00:00Z",
    )


def evaluate(latest=None, movement=None, rule_set=None):
    engine = AlertEngine(rule_set or load_rule_set("alert_rules_v0.1"))
    return engine.evaluate(AlertEvaluationInput(
        latest=latest or assessment(), trajectory=movement or trajectory()))


def only(decisions):
    assert len(decisions) == 1, decisions
    return decisions[0]


class FiringConditions(unittest.TestCase):
    def test_elevated_escalating_unaddressed_harm_intent_raises_high(self):
        decision = only(evaluate())
        self.assertEqual(decision.status, RAISED)
        self.assertEqual(decision.severity, "high")
        self.assertFalse(decision.requires_manual_review)
        self.assertIsNone(decision.context_modifier_applied)

    def test_harm_intent_below_the_threshold_does_not_fire(self):
        self.assertEqual(evaluate(assessment(harm=1)), ())

    def test_a_null_harm_intent_is_never_treated_as_zero_or_as_enough(self):
        self.assertEqual(evaluate(assessment(harm=None)), ())

    def test_no_escalation_does_not_fire(self):
        self.assertEqual(evaluate(movement=trajectory(by_level=False)), ())

    def test_escalation_by_frequency_alone_is_not_this_rules_condition(self):
        self.assertEqual(
            evaluate(movement=trajectory(by_level=False, by_frequency=True)), ())

    def test_specificity_growth_at_a_constant_level_fires(self):
        """Taxonomy §6.4: specificity growth at the same level IS escalation."""
        decision = only(evaluate(movement=trajectory(by_level=False, by_specificity=True)))
        self.assertEqual(decision.status, RAISED)
        self.assertIn("by specificity", decision.explanation)

    def test_a_companion_that_suggested_support_and_did_not_enable_does_not_fire(self):
        self.assertEqual(evaluate(assessment(sis=2, hes=0)), ())

    def test_harm_enablement_fires_even_when_support_was_suggested(self):
        decision = only(evaluate(assessment(sis=2, hes=1)))
        self.assertEqual(decision.status, RAISED)
        self.assertIn("harm enablement", decision.explanation)


class Severity(unittest.TestCase):
    def test_critical_needs_the_top_level_and_specific_details(self):
        self.assertEqual(only(evaluate(assessment(harm=3))).severity, "high")
        self.assertEqual(only(evaluate(assessment(harm=2, markers=("time",)))).severity, "high")
        self.assertEqual(
            only(evaluate(assessment(harm=3, markers=("time", "location")))).severity,
            "critical")

    def test_a_nonpersonal_context_lowers_one_level_and_names_the_modifier(self):
        for context in ("fiction", "hypothetical", "attributed"):
            with self.subTest(context=context):
                decision = only(evaluate(assessment(harm=3, markers=("method",),
                                                    context=context)))
                self.assertEqual(decision.severity, "high")
                self.assertEqual(decision.context_modifier_applied, "nonpersonal-context-v0.1")
                self.assertEqual(decision.context_categories_present, (context,))

    def test_context_never_suppresses(self):
        decision = only(evaluate(assessment(harm=2, context="fiction")))
        self.assertEqual(decision.severity, "medium")

    def test_the_floor_bounds_how_far_context_can_lower_severity(self):
        rule_set = load_rule_set("alert_rules_v0.1")
        raised_floor = dataclasses.replace(
            rule_set, rules=(dataclasses.replace(rule_set.rules[0], severity_floor="high"),))
        decision = only(evaluate(assessment(context="fiction"), rule_set=raised_floor))
        self.assertEqual(decision.severity, "high")
        self.assertEqual(decision.context_modifier_applied, "nonpersonal-context-v0.1")

    def test_uncertain_context_keeps_full_severity_and_requires_review(self):
        """Taxonomy §8 rule 3: uncertainty escalates, it never de-escalates."""
        decision = only(evaluate(assessment(harm=3, markers=("time",), context="uncertain")))
        self.assertEqual(decision.severity, "critical")
        self.assertIsNone(decision.context_modifier_applied)
        self.assertTrue(decision.requires_manual_review)

    def test_spiritual_cultural_context_is_not_lowered(self):
        decision = only(evaluate(assessment(context="spiritual_cultural")))
        self.assertEqual(decision.severity, "high")
        self.assertIsNone(decision.context_modifier_applied)


class UndeterminableCompanionResponse(unittest.TestCase):
    """D-39: when SIS and HES cannot decide the third condition, record it for
    review with no severity. Firing would invent a finding; silence would hide one."""

    def test_both_null_is_indeterminate(self):
        decision = only(evaluate(assessment(sis=None, hes=None)))
        self.assertEqual(decision.status, INDETERMINATE)
        self.assertIsNone(decision.severity)
        self.assertTrue(decision.requires_manual_review)
        self.assertIn("could not be determined", decision.explanation)

    def test_a_known_value_that_decides_it_is_enough(self):
        self.assertEqual(only(evaluate(assessment(sis=None, hes=1))).status, RAISED)
        self.assertEqual(only(evaluate(assessment(sis=0, hes=None))).status, RAISED)

    def test_a_known_value_that_does_not_decide_it_leaves_it_indeterminate(self):
        self.assertEqual(only(evaluate(assessment(sis=2, hes=None))).status, INDETERMINATE)
        self.assertEqual(only(evaluate(assessment(sis=None, hes=0))).status, INDETERMINATE)

    def test_no_context_modifier_is_applied_without_a_severity(self):
        decision = only(evaluate(assessment(sis=None, hes=None, context="fiction")))
        self.assertIsNone(decision.context_modifier_applied)


class Traceability(unittest.TestCase):
    def test_the_alert_names_exactly_what_it_used(self):
        decision = only(evaluate())
        self.assertEqual(decision.triggering_signal_score_ids,
                         ("example-score-harm_intent", "example-score-sis", "example-score-hes"))
        self.assertEqual(decision.trajectory_update_id, "example-trajectory-1")
        self.assertEqual(decision.contributing_assessment_ids,
                         ("example-assessment-1", "example-assessment-2"))
        self.assertEqual(decision.rule_set_version, "alert_rules_v0.1")
        self.assertEqual(decision.through_turn_id, "example-turn-3")

    def test_evidence_is_the_union_of_escalation_turns_and_score_evidence(self):
        decision = only(evaluate(assessment(sis=2, hes=1)))
        self.assertEqual(decision.evidence_turn_ids, ("example-turn-0", "example-turn-2"))

    def test_upstream_versions_are_carried_on_the_alert(self):
        decision = only(evaluate())
        self.assertEqual(
            (decision.judge_model_version, decision.rubric_version,
             decision.taxonomy_version, decision.trajectory_policy_version),
            ("example-2026-01", "rubric_v0.1", "taxonomy_v0.1", "trajectory_v0.1"))

    def test_the_same_inputs_always_give_the_same_decision(self):
        self.assertEqual(evaluate(), evaluate())

    def test_a_trajectory_not_derived_from_the_assessment_is_refused(self):
        with self.assertRaises(ValueError):
            AlertEvaluationInput(
                latest=assessment(),
                trajectory=dataclasses.replace(trajectory(),
                                               input_assessment_ids=("example-assessment-1",)))

    def test_explanations_describe_the_conversation_not_a_person(self):
        banned = ("delusion", "psychosis", "psychotic", "diagnos", "disorder",
                  "patient", "symptom")
        cases = [
            assessment(), assessment(harm=3, markers=("time",)),
            assessment(context="fiction"), assessment(context="uncertain"),
            assessment(sis=None, hes=None), assessment(sis=2, hes=1),
        ]
        for case in cases:
            text = only(evaluate(case)).explanation.lower()
            for word in banned:
                self.assertNotIn(word, text)


class Supersession(unittest.TestCase):
    """D-39: a newer decision replaces the active alert only if at least as severe."""

    def active(self, **overrides):
        return Alert(id="example-alert-1", created_at="2026-01-01T00:00:00Z",
                     decision=dataclasses.replace(only(evaluate()), **overrides))

    def test_an_equal_or_more_severe_decision_supersedes(self):
        self.assertTrue(supersedes(only(evaluate()), self.active()))
        critical = only(evaluate(assessment(harm=3, markers=("time",))))
        self.assertTrue(supersedes(critical, self.active()))

    def test_a_less_severe_decision_does_not_downgrade_the_active_alert(self):
        medium = only(evaluate(assessment(context="fiction")))
        self.assertFalse(supersedes(medium, self.active()))

    def test_an_indeterminate_outcome_never_replaces_a_raised_alert(self):
        indeterminate = only(evaluate(assessment(sis=None, hes=None)))
        self.assertFalse(supersedes(indeterminate, self.active()))

    def test_a_raised_alert_replaces_an_indeterminate_one(self):
        active = self.active(status=INDETERMINATE, severity=None)
        self.assertTrue(supersedes(only(evaluate()), active))


class RuleSetLoading(unittest.TestCase):
    def test_the_committed_rule_set_loads_as_a_draft(self):
        rule_set = load_rule_set("alert_rules_v0.1")
        self.assertEqual(rule_set.status, "draft")
        self.assertEqual([r.RULE_ID for r in rule_set.rules], ["harm-intent-unaddressed"])

    def test_an_unknown_version_fails_closed(self):
        with self.assertRaises(UnknownVersion):
            load_rule_set("alert_rules_v9.9")

    def write(self, rules):
        directory = tempfile.mkdtemp()
        with open(os.path.join(directory, "example_rules.json"), "w") as handle:
            json.dump({"rule_set_version": "example_rules", "status": "draft",
                       "rules": rules}, handle)
        return directory

    def test_an_unknown_rule_fails_closed(self):
        directory = self.write([{"rule_id": "no-such-rule", "parameters": {}}])
        with self.assertRaises(UnknownVersion):
            load_rule_set("example_rules", directory)

    def test_a_missing_parameter_fails_closed(self):
        with open(os.path.join(DEFAULT_RULES_DIR, "alert_rules_v0.1.json")) as handle:
            entry = json.load(handle)["rules"][0]
        del entry["parameters"]["hes_min"]
        with self.assertRaises(ValueError):
            load_rule_set("example_rules", self.write([entry]))


if __name__ == "__main__":
    unittest.main()
