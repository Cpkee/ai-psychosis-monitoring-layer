"""PostgreSQL AlertRepository.

Both uniqueness rules are expressed in the schema: a unique constraint for
"one alert per evaluation" and a partial unique index for "one active alert per
session and rule". The adapter tells them apart by constraint name so each
surfaces as its own declared error.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

import psycopg

from src.domain.alerts.records import Alert, AlertDecision
from src.domain.alerts.repository import (
    ActiveAlertExists,
    AlertAlreadyExists,
    AlertAlreadySuperseded,
    AlertNotFound,
)

_DECISION_FIELDS = (
    "session_id", "through_turn_id", "rule_set_version", "rule_id", "status",
    "severity", "requires_manual_review", "contributing_assessment_ids",
    "trajectory_update_id", "triggering_signal_score_ids", "evidence_turn_ids",
    "context_categories_present", "context_modifier_applied", "explanation",
    "judge_model_version", "rubric_version", "taxonomy_version",
    "trajectory_policy_version",
)
_ARRAY_FIELDS = {
    "contributing_assessment_ids", "triggering_signal_score_ids",
    "evidence_turn_ids", "context_categories_present",
}
_COLUMNS = ("id",) + _DECISION_FIELDS + ("created_at", "superseded_by")
_SELECT = "SELECT " + ", ".join(_COLUMNS) + " FROM alerts"

ACTIVE_INDEX = "alerts_one_active_per_rule"


class PostgresAlertRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def save(self, alert: Alert) -> Alert:
        decision = alert.decision
        values = [alert.id]
        for name in _DECISION_FIELDS:
            value = getattr(decision, name)
            values.append(list(value) if name in _ARRAY_FIELDS else value)
        values += [alert.created_at, alert.superseded_by]
        try:
            self._connection.execute(
                "INSERT INTO alerts ({}) VALUES ({})".format(
                    ", ".join(_COLUMNS), ", ".join(["%s"] * len(_COLUMNS))
                ),
                values,
            )
        except psycopg.errors.UniqueViolation as exc:
            if exc.diag.constraint_name == ACTIVE_INDEX:
                raise ActiveAlertExists(
                    "Session {!r} already has an active {!r} alert.".format(
                        decision.session_id, decision.rule_id
                    )
                )
            raise AlertAlreadyExists(
                "Alert {!r} or its evaluation already exists.".format(alert.id)
            )
        return alert

    def active_for_session(self, session_id: str, rule_id: str) -> Optional[Alert]:
        row = self._connection.execute(
            _SELECT + " WHERE session_id = %s AND rule_id = %s AND superseded_by IS NULL",
            (session_id, rule_id),
        ).fetchone()
        return self._to_alert(row) if row is not None else None

    def supersede(self, alert_id: str, superseded_by: str) -> Alert:
        row = self._connection.execute(
            "UPDATE alerts SET superseded_by = %s "
            "WHERE id = %s AND superseded_by IS NULL RETURNING " + ", ".join(_COLUMNS),
            (superseded_by, alert_id),
        ).fetchone()
        if row is not None:
            return self._to_alert(row)
        existing = self._connection.execute(
            "SELECT superseded_by FROM alerts WHERE id = %s", (alert_id,)
        ).fetchone()
        if existing is None:
            raise AlertNotFound("No alert {!r}.".format(alert_id))
        raise AlertAlreadySuperseded(
            "Alert {!r} was already superseded by {!r}.".format(alert_id, existing[0])
        )

    def list_for_session(self, session_id: str) -> Tuple[Alert, ...]:
        rows = self._connection.execute(
            _SELECT + " WHERE session_id = %s ORDER BY created_at, id", (session_id,)
        ).fetchall()
        return tuple(self._to_alert(row) for row in rows)

    @staticmethod
    def _to_alert(row: Any) -> Alert:
        fields = dict(zip(_COLUMNS, row))
        decision = {
            name: tuple(fields[name] or ()) if name in _ARRAY_FIELDS else fields[name]
            for name in _DECISION_FIELDS
        }
        return Alert(
            id=fields["id"],
            decision=AlertDecision(**decision),
            created_at=fields["created_at"],
            superseded_by=fields["superseded_by"],
        )
