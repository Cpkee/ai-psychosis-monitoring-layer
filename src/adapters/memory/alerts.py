"""In-memory AlertRepository."""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional, Tuple

from src.domain.alerts.records import Alert
from src.domain.alerts.repository import (
    ActiveAlertExists,
    AlertAlreadyExists,
    AlertAlreadySuperseded,
    AlertNotFound,
)


def _evaluation_key(alert: Alert):
    decision = alert.decision
    return (decision.trajectory_update_id, decision.rule_set_version, decision.rule_id)


class InMemoryAlertRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, Alert] = {}
        self._order: List[str] = []

    def save(self, alert: Alert) -> Alert:
        if alert.id in self._by_id:
            raise AlertAlreadyExists("Alert {!r} already exists.".format(alert.id))
        if any(_evaluation_key(a) == _evaluation_key(alert) for a in self._by_id.values()):
            raise AlertAlreadyExists(
                "This evaluation already produced an alert: {!r}.".format(_evaluation_key(alert))
            )
        if alert.superseded_by is None and self.active_for_session(
            alert.decision.session_id, alert.decision.rule_id
        ) is not None:
            raise ActiveAlertExists(
                "Session {!r} already has an active {!r} alert.".format(
                    alert.decision.session_id, alert.decision.rule_id
                )
            )
        self._by_id[alert.id] = alert
        self._order.append(alert.id)
        return alert

    def active_for_session(self, session_id: str, rule_id: str) -> Optional[Alert]:
        for alert in self._by_id.values():
            if (
                alert.decision.session_id == session_id
                and alert.decision.rule_id == rule_id
                and alert.superseded_by is None
            ):
                return alert
        return None

    def supersede(self, alert_id: str, superseded_by: str) -> Alert:
        try:
            alert = self._by_id[alert_id]
        except KeyError:
            raise AlertNotFound("No alert {!r}.".format(alert_id))
        if alert.superseded_by is not None:
            raise AlertAlreadySuperseded(
                "Alert {!r} was already superseded by {!r}.".format(alert_id, alert.superseded_by)
            )
        replaced = dataclasses.replace(alert, superseded_by=superseded_by)
        self._by_id[alert_id] = replaced
        return replaced

    def list_for_session(self, session_id: str) -> Tuple[Alert, ...]:
        return tuple(
            self._by_id[alert_id]
            for alert_id in self._order
            if self._by_id[alert_id].decision.session_id == session_id
        )
