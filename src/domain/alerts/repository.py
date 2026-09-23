"""AlertRepository — the persistence seam for alerts.

Storage owns two uniqueness rules (D-6):

* one alert per evaluation — the same trajectory update, rule set and rule can
  never produce two alerts, so re-running evaluation cannot duplicate one;
* one **active** alert per session and rule — a later decision supersedes the
  active one rather than sitting beside it.
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple

from src.domain.alerts.records import Alert


class AlertNotFound(LookupError):
    """No alert exists with the given id."""


class AlertAlreadyExists(ValueError):
    """The id is taken, or this evaluation has already produced an alert."""


class ActiveAlertExists(ValueError):
    """The session already has an active alert for this rule. Supersede it first."""


class AlertAlreadySuperseded(ValueError):
    """The alert has already been superseded. Supersession happens once."""


class AlertRepository(Protocol):
    def save(self, alert: Alert) -> Alert:
        """Store an alert. Raises :class:`AlertAlreadyExists` or
        :class:`ActiveAlertExists`."""

    def active_for_session(self, session_id: str, rule_id: str) -> Optional[Alert]:
        """The alert for this session and rule that nothing has superseded."""

    def supersede(self, alert_id: str, superseded_by: str) -> Alert:
        """Mark an alert superseded. Raises :class:`AlertNotFound` or
        :class:`AlertAlreadySuperseded`."""

    def list_for_session(self, session_id: str) -> Tuple[Alert, ...]:
        """Every alert for a session, active and superseded, oldest first."""
