"""AlertRepository contract — run against every implementation."""

from __future__ import annotations

import dataclasses

from src.domain.alerts.records import INDETERMINATE, Alert, AlertDecision
from src.domain.alerts.repository import (
    ActiveAlertExists,
    AlertAlreadyExists,
    AlertAlreadySuperseded,
    AlertNotFound,
)

#: Trajectory updates the PostgreSQL binding stores first, for the foreign key.
TRAJECTORY_IDS = ("example-trajectory-1", "example-trajectory-2", "example-trajectory-3")


def make_decision(**overrides) -> AlertDecision:
    fields = dict(
        session_id="example-session-1",
        through_turn_id="example-turn-1",
        rule_set_version="alert_rules_v0.1",
        rule_id="harm-intent-unaddressed",
        status="raised",
        severity="critical",
        requires_manual_review=False,
        contributing_assessment_ids=("example-assessment-1", "example-assessment-2"),
        trajectory_update_id="example-trajectory-1",
        triggering_signal_score_ids=("example-score-1", "example-score-2", "example-score-3"),
        evidence_turn_ids=("example-turn-0", "example-turn-1"),
        context_categories_present=("fiction",),
        context_modifier_applied="nonpersonal-context-v0.1",
        explanation="Example explanation built from the cited facts.",
        judge_model_version="example-2026-01",
        rubric_version="rubric_v0.1",
        taxonomy_version="taxonomy_v0.1",
        trajectory_policy_version="trajectory_v0.1",
    )
    fields.update(overrides)
    return AlertDecision(**fields)


def make_alert(alert_id="example-alert-1", created_at="2026-01-01T00:00:00Z",
               **overrides) -> Alert:
    return Alert(id=alert_id, decision=make_decision(**overrides), created_at=created_at)


class AlertRepositoryContract:
    """Subclass alongside ``unittest.TestCase`` and implement :meth:`repository`."""

    def repository(self):
        raise NotImplementedError

    def test_save_and_read_back_every_field(self):
        repo = self.repository()
        saved = repo.save(make_alert())
        self.assertEqual(repo.active_for_session("example-session-1",
                                                 "harm-intent-unaddressed"), saved)
        self.assertEqual(repo.list_for_session("example-session-1"), (saved,))

    def test_an_indeterminate_outcome_round_trips_without_a_severity(self):
        repo = self.repository()
        saved = repo.save(make_alert(status=INDETERMINATE, severity=None,
                                     requires_manual_review=True,
                                     context_modifier_applied=None))
        stored = repo.list_for_session("example-session-1")[0]
        self.assertEqual(stored, saved)
        self.assertIsNone(stored.decision.severity)
        self.assertIsNone(stored.decision.context_modifier_applied)

    def test_no_active_alert_is_none(self):
        self.assertIsNone(
            self.repository().active_for_session("example-session-1", "harm-intent-unaddressed")
        )

    def test_a_second_active_alert_for_the_same_rule_is_refused(self):
        repo = self.repository()
        repo.save(make_alert())
        with self.assertRaises(ActiveAlertExists):
            repo.save(make_alert("example-alert-2", trajectory_update_id=TRAJECTORY_IDS[1]))

    def test_supersession_leaves_one_active_alert_and_keeps_the_history(self):
        repo = self.repository()
        repo.save(make_alert())
        repo.supersede("example-alert-1", "example-alert-2")
        newer = repo.save(make_alert("example-alert-2", created_at="2026-01-01T00:00:01Z",
                                     trajectory_update_id=TRAJECTORY_IDS[1]))

        self.assertEqual(
            repo.active_for_session("example-session-1", "harm-intent-unaddressed"), newer
        )
        history = repo.list_for_session("example-session-1")
        self.assertEqual([a.id for a in history], ["example-alert-1", "example-alert-2"])
        self.assertEqual(history[0].superseded_by, "example-alert-2")
        self.assertEqual(history[0].decision, make_decision())

    def test_the_same_evaluation_cannot_produce_two_alerts(self):
        """Architecture §13: re-running evaluation must not duplicate an alert."""
        repo = self.repository()
        repo.save(make_alert())
        repo.supersede("example-alert-1", "example-alert-2")
        with self.assertRaises(AlertAlreadyExists):
            repo.save(make_alert("example-alert-2"))

    def test_a_duplicate_id_is_refused(self):
        repo = self.repository()
        repo.save(make_alert())
        with self.assertRaises(AlertAlreadyExists):
            repo.save(make_alert(trajectory_update_id=TRAJECTORY_IDS[1],
                                 rule_id="another-example-rule"))

    def test_alerts_for_different_rules_are_independent(self):
        repo = self.repository()
        repo.save(make_alert())
        repo.save(make_alert("example-alert-2", rule_id="another-example-rule"))
        self.assertEqual(len(repo.list_for_session("example-session-1")), 2)

    def test_superseding_an_unknown_alert_raises(self):
        with self.assertRaises(AlertNotFound):
            self.repository().supersede("no-such-alert", "example-alert-2")

    def test_supersession_happens_once(self):
        repo = self.repository()
        repo.save(make_alert())
        repo.supersede("example-alert-1", "example-alert-2")
        repo.save(make_alert("example-alert-2", trajectory_update_id=TRAJECTORY_IDS[1]))
        with self.assertRaises(AlertAlreadySuperseded):
            repo.supersede("example-alert-1", "example-alert-3")

    def test_an_alert_without_evidence_cannot_be_constructed(self):
        """§4.7: invalid, and must not be stored — so it cannot exist."""
        for field in ("evidence_turn_ids", "triggering_signal_score_ids",
                      "contributing_assessment_ids"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                make_decision(**{field: ()})

    def test_severity_is_required_if_and_only_if_raised(self):
        with self.assertRaises(ValueError):
            make_decision(severity=None)
        with self.assertRaises(ValueError):
            make_decision(status=INDETERMINATE, severity="high")
        with self.assertRaises(ValueError):
            make_decision(severity="severe")

    def test_superseded_alerts_are_read_back_unchanged_apart_from_the_link(self):
        repo = self.repository()
        original = repo.save(make_alert())
        superseded = repo.supersede("example-alert-1", "example-alert-2")
        self.assertEqual(superseded, dataclasses.replace(original, superseded_by="example-alert-2"))
        repo.save(make_alert("example-alert-2", trajectory_update_id=TRAJECTORY_IDS[1]))
