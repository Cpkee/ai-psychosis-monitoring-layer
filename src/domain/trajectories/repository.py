"""TrajectoryRepository — the persistence seam for trajectory updates."""

from __future__ import annotations

from typing import Optional, Protocol

from src.domain.trajectories.records import TrajectoryUpdate


class TrajectoryUpdateNotFound(LookupError):
    """No trajectory update exists with the given id."""


class TrajectoryUpdateAlreadyExists(ValueError):
    """An update with the given id is already stored."""


class TrajectoryRepository(Protocol):
    def save(self, update: TrajectoryUpdate) -> TrajectoryUpdate:
        """Store a trajectory update. Append-only: nothing is overwritten."""

    def get(self, update_id: str) -> TrajectoryUpdate:
        """Fetch one update. Raises :class:`TrajectoryUpdateNotFound`."""

    def latest_for_session(self, session_id: str) -> Optional[TrajectoryUpdate]:
        """The most recent update for a session, by turn order."""
