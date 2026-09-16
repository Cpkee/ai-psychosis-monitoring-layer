"""PostgreSQL ConversationRepository.

Same interface and same declared error modes as the in-memory adapter; the
shared contract suite runs against both. Driver exceptions never escape:
architecture section 3.9 requires callers to depend on declared error modes,
not storage details.

The connection is supplied by the caller, so several repositories can share one
transaction (see :func:`src.adapters.postgres.connection.unit_of_work`).
"""

from __future__ import annotations

from typing import List, Optional

import psycopg
from psycopg.rows import class_row

from src.domain.conversations.records import Session, Turn
from src.domain.conversations.repository import (
    DuplicateTurnIndex,
    IdempotencyConflict,
    SessionAlreadyExists,
    SessionClosed,
    SessionNotFound,
)

_SESSION_COLUMNS = (
    "id, run_id, external_session_id, source_version_id, scenario_id, "
    "raw_theme_label, canonical_theme_label, theme_mapping_version, "
    "companion_condition, created_at, closed_at"
)
_TURN_COLUMNS = (
    "id, session_id, turn_index, role, message, timestamp, idempotency_key, "
    "model_name, model_version, source_payload_reference"
)
_IDENTITY = ("session_id", "turn_index", "role", "message")


class PostgresConversationRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def create_session(self, session: Session) -> Session:
        try:
            self._connection.execute(
                "INSERT INTO sessions ({}) VALUES ({})".format(
                    _SESSION_COLUMNS, ", ".join(["%s"] * 11)
                ),
                (
                    session.id, session.run_id, session.external_session_id,
                    session.source_version_id, session.scenario_id,
                    session.raw_theme_label, session.canonical_theme_label,
                    session.theme_mapping_version, session.companion_condition,
                    session.created_at, session.closed_at,
                ),
            )
        except psycopg.errors.UniqueViolation:
            raise SessionAlreadyExists("Session {!r} already exists.".format(session.id))
        return session

    def get_session(self, session_id: str) -> Session:
        session = self._find_session(session_id)
        if session is None:
            raise SessionNotFound("No session {!r}.".format(session_id))
        return session

    def close_session(self, session_id: str, closed_at: str) -> Session:
        # Only the first closure wins, so repeated calls are idempotent.
        with self._connection.cursor(row_factory=class_row(Session)) as cursor:
            cursor.execute(
                "UPDATE sessions SET closed_at = %s WHERE id = %s AND closed_at IS NULL "
                "RETURNING " + _SESSION_COLUMNS,
                (closed_at, session_id),
            )
            updated = cursor.fetchone()
        return updated if updated is not None else self.get_session(session_id)

    def append_turn(self, turn: Turn) -> Turn:
        session = self.get_session(turn.session_id)

        replayed = self._replay(turn)
        if replayed is not None:
            return replayed

        if session.closed_at is not None:
            raise SessionClosed("Session {!r} is closed.".format(turn.session_id))

        try:
            self._connection.execute(
                "INSERT INTO turns ({}) VALUES ({})".format(
                    _TURN_COLUMNS, ", ".join(["%s"] * 10)
                ),
                (
                    turn.id, turn.session_id, turn.turn_index, turn.role,
                    turn.message, turn.timestamp, turn.idempotency_key,
                    turn.model_name, turn.model_version,
                    turn.source_payload_reference,
                ),
            )
        except psycopg.errors.UniqueViolation as exc:
            constraint = getattr(exc.diag, "constraint_name", None)
            if constraint == "turns_unique_index":
                raise DuplicateTurnIndex(
                    "Session {!r} already has a turn at index {}.".format(
                        turn.session_id, turn.turn_index
                    )
                )
            # Lost a race on the idempotency key: re-read and replay.
            replayed = self._replay(turn)
            if replayed is not None:
                return replayed
            raise
        return turn

    def list_turns(self, session_id: str) -> List[Turn]:
        self.get_session(session_id)
        with self._connection.cursor(row_factory=class_row(Turn)) as cursor:
            cursor.execute(
                "SELECT " + _TURN_COLUMNS
                + " FROM turns WHERE session_id = %s ORDER BY turn_index",
                (session_id,),
            )
            return cursor.fetchall()

    # -- internals -------------------------------------------------------

    def _find_session(self, session_id: str) -> Optional[Session]:
        with self._connection.cursor(row_factory=class_row(Session)) as cursor:
            cursor.execute(
                "SELECT " + _SESSION_COLUMNS + " FROM sessions WHERE id = %s",
                (session_id,),
            )
            return cursor.fetchone()

    def _replay(self, turn: Turn) -> Optional[Turn]:
        """Return the stored turn for this idempotency key, if it matches."""
        with self._connection.cursor(row_factory=class_row(Turn)) as cursor:
            cursor.execute(
                "SELECT " + _TURN_COLUMNS
                + " FROM turns WHERE session_id = %s AND idempotency_key = %s",
                (turn.session_id, turn.idempotency_key),
            )
            existing = cursor.fetchone()
        if existing is None:
            return None
        if all(getattr(existing, f) == getattr(turn, f) for f in _IDENTITY):
            return existing
        raise IdempotencyConflict(
            "Idempotency key {!r} was reused with different content in session "
            "{!r}.".format(turn.idempotency_key, turn.session_id)
        )
