"""In-memory ConversationRepository.

Used to build Phase C before PostgreSQL exists, and as the fast implementation
in tests. It is held to the same contract suite as the PostgreSQL adapter.
"""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Tuple

from src.domain.conversations.records import Session, Turn
from src.domain.conversations.repository import (
    DuplicateTurnIndex,
    IdempotencyConflict,
    SessionAlreadyExists,
    SessionClosed,
    SessionNotFound,
)

#: The fields that make two turns "the same turn" for idempotency purposes.
_IDENTITY = ("session_id", "turn_index", "role", "message")


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._turns: Dict[str, Dict[int, Turn]] = {}
        self._by_key: Dict[Tuple[str, str], Turn] = {}

    def create_session(self, session: Session) -> Session:
        if session.id in self._sessions:
            raise SessionAlreadyExists("Session {!r} already exists.".format(session.id))
        self._sessions[session.id] = session
        self._turns[session.id] = {}
        return session

    def get_session(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFound("No session {!r}.".format(session_id))

    def close_session(self, session_id: str, closed_at: str) -> Session:
        session = self.get_session(session_id)
        if session.closed_at is None:
            session = dataclasses.replace(session, closed_at=closed_at)
            self._sessions[session_id] = session
        return session

    def append_turn(self, turn: Turn) -> Turn:
        session = self.get_session(turn.session_id)

        existing = self._by_key.get((turn.session_id, turn.idempotency_key))
        if existing is not None:
            if self._same_turn(existing, turn):
                return existing
            raise IdempotencyConflict(
                "Idempotency key {!r} was reused with different content in "
                "session {!r}.".format(turn.idempotency_key, turn.session_id)
            )

        if session.closed_at is not None:
            raise SessionClosed("Session {!r} is closed.".format(turn.session_id))

        if turn.turn_index in self._turns[turn.session_id]:
            raise DuplicateTurnIndex(
                "Session {!r} already has a turn at index {}.".format(
                    turn.session_id, turn.turn_index
                )
            )

        self._turns[turn.session_id][turn.turn_index] = turn
        self._by_key[(turn.session_id, turn.idempotency_key)] = turn
        return turn

    def list_turns(self, session_id: str) -> List[Turn]:
        self.get_session(session_id)
        turns = self._turns[session_id]
        return [turns[index] for index in sorted(turns)]

    @staticmethod
    def _same_turn(a: Turn, b: Turn) -> bool:
        return all(getattr(a, f) == getattr(b, f) for f in _IDENTITY)
