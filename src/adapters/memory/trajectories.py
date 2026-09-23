"""In-memory TrajectoryRepository."""

from __future__ import annotations

from typing import Dict, List, Optional

from src.domain.trajectories.records import TrajectoryUpdate
from src.domain.trajectories.repository import (
    TrajectoryUpdateAlreadyExists,
    TrajectoryUpdateNotFound,
)


class InMemoryTrajectoryRepository:
    def __init__(self) -> None:
        self._by_id: Dict[str, TrajectoryUpdate] = {}
        self._order: List[str] = []

    def save(self, update: TrajectoryUpdate) -> TrajectoryUpdate:
        if update.id in self._by_id:
            raise TrajectoryUpdateAlreadyExists(
                "Trajectory update {!r} already exists.".format(update.id)
            )
        self._by_id[update.id] = update
        self._order.append(update.id)
        return update

    def get(self, update_id: str) -> TrajectoryUpdate:
        try:
            return self._by_id[update_id]
        except KeyError:
            raise TrajectoryUpdateNotFound("No trajectory update {!r}.".format(update_id))

    def latest_for_session(self, session_id: str) -> Optional[TrajectoryUpdate]:
        for update_id in reversed(self._order):
            if self._by_id[update_id].session_id == session_id:
                return self._by_id[update_id]
        return None
