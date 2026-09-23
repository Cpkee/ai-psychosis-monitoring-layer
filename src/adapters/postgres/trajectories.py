"""PostgreSQL TrajectoryRepository.

Architecture §7.2 splits a trajectory update into ``state_json`` and
``derived_facts_json``. The split is meaningful rather than cosmetic: state is
what was **observed** (levels, peaks, gaps), derived facts are what was
**concluded** from it (change, persistence, escalation, recovery). Keeping them
apart makes a recomputation easy to compare against what was stored.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Dict, Optional

import psycopg

from src.domain.trajectories.records import (
    SignalTrajectory,
    TrajectoryState,
    TrajectoryUpdate,
)
from src.domain.trajectories.repository import (
    TrajectoryUpdateAlreadyExists,
    TrajectoryUpdateNotFound,
)

_COLUMNS = (
    "id, session_id, through_turn_id, trajectory_policy_version, "
    "window_definition, state_json, derived_facts_json, input_assessment_ids, "
    "created_at"
)
#: Fields describing what was observed; the rest are conclusions drawn from them.
_OBSERVED = (
    "current_level", "current_level_turn_id", "stale",
    "peak_level", "peak_turn_id", "null_count",
)


def _split(trajectory: SignalTrajectory):
    fields = dataclasses.asdict(trajectory)
    fields.pop("signal_code")
    observed = {k: v for k, v in fields.items() if k in _OBSERVED}
    derived = {k: v for k, v in fields.items() if k not in _OBSERVED}
    return observed, derived


def _merge(code: str, observed: Dict[str, Any], derived: Dict[str, Any]) -> SignalTrajectory:
    fields = dict(observed)
    fields.update(derived)
    if "escalation_turn_ids" in fields:
        fields["escalation_turn_ids"] = tuple(fields["escalation_turn_ids"] or ())
    return SignalTrajectory(signal_code=code, **fields)


class PostgresTrajectoryRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def save(self, update: TrajectoryUpdate) -> TrajectoryUpdate:
        # JSON arrays, not objects: JSONB does not preserve object key order,
        # and signal order is part of the result.
        state = []
        derived = []
        for trajectory in update.state.signals:
            observed_fields, derived_fields = _split(trajectory)
            observed_fields["signal_code"] = trajectory.signal_code
            derived_fields["signal_code"] = trajectory.signal_code
            state.append(observed_fields)
            derived.append(derived_fields)
        try:
            self._connection.execute(
                "INSERT INTO trajectory_updates ({}) VALUES ({})".format(
                    _COLUMNS, ", ".join(["%s"] * 9)
                ),
                (
                    update.id, update.session_id, update.through_turn_id,
                    update.trajectory_policy_version,
                    update.state.window_definition,
                    json.dumps(state), json.dumps(derived),
                    list(update.input_assessment_ids), update.created_at,
                ),
            )
        except psycopg.errors.UniqueViolation:
            raise TrajectoryUpdateAlreadyExists(
                "Trajectory update {!r} already exists.".format(update.id)
            )
        return update

    def get(self, update_id: str) -> TrajectoryUpdate:
        row = self._connection.execute(
            "SELECT " + _COLUMNS + " FROM trajectory_updates WHERE id = %s",
            (update_id,),
        ).fetchone()
        if row is None:
            raise TrajectoryUpdateNotFound("No trajectory update {!r}.".format(update_id))
        return self._to_update(row)

    def latest_for_session(self, session_id: str) -> Optional[TrajectoryUpdate]:
        row = self._connection.execute(
            "SELECT " + _COLUMNS + " FROM trajectory_updates WHERE session_id = %s "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return self._to_update(row) if row is not None else None

    @staticmethod
    def _to_update(row: Any) -> TrajectoryUpdate:
        state_json, derived_json = row[5], row[6]
        derived_by_code = {entry["signal_code"]: entry for entry in derived_json}
        return TrajectoryUpdate(
            id=row[0], session_id=row[1], through_turn_id=row[2],
            trajectory_policy_version=row[3],
            state=TrajectoryState(
                session_id=row[1],
                through_turn_id=row[2],
                window_definition=row[4],
                signals=tuple(
                    _merge(
                        entry["signal_code"],
                        {k: v for k, v in entry.items() if k != "signal_code"},
                        {
                            k: v
                            for k, v in derived_by_code[entry["signal_code"]].items()
                            if k != "signal_code"
                        },
                    )
                    for entry in state_json
                ),
            ),
            input_assessment_ids=tuple(row[7] or ()),
            created_at=row[8],
        )
