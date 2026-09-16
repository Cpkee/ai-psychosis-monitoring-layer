"""ConversationRepository — the persistence seam for sessions and turns.

Architecture section 3.9: callers depend on domain objects and **declared error
modes**, not storage details. The error types below are part of the contract;
an implementation must raise these and not leak driver exceptions.

Two implementations are required, which is what justifies the interface:

* ``InMemoryConversationRepository`` — available now, used to build Phase C.
* a PostgreSQL implementation — required by section 19 criterion 10.

One contract test suite runs against both (section 17), so the in-memory
implementation cannot drift from real SQL behaviour.

**Scope.** This repository owns storage-level invariants only: existence and
uniqueness. Turn *ordering and contiguity* is a domain rule belonging to the
Conversation Orchestrator (section 6.3), not to storage — a unique index cannot
express "no gaps".
"""

from __future__ import annotations

from typing import List, Protocol

from src.domain.conversations.records import Session, Turn


class SessionNotFound(LookupError):
    """No session exists with the given id."""


class SessionAlreadyExists(ValueError):
    """A session with the given id is already stored."""


class DuplicateTurnIndex(ValueError):
    """A different turn already occupies this ``(session_id, turn_index)``.

    Architecture section 13: reject or quarantine duplicate turn indices.
    """


class IdempotencyConflict(ValueError):
    """An idempotency key was reused with different content.

    Returning the stored turn here would silently discard the new payload, so
    the repository refuses instead.
    """


class SessionClosed(ValueError):
    """The session is closed and will not accept further turns."""


class ConversationRepository(Protocol):
    def create_session(self, session: Session) -> Session:
        """Store a new session. Raises :class:`SessionAlreadyExists`."""

    def get_session(self, session_id: str) -> Session:
        """Fetch a session. Raises :class:`SessionNotFound`."""

    def close_session(self, session_id: str, closed_at: str) -> Session:
        """Mark a session closed. Idempotent: closing twice keeps the first time."""

    def append_turn(self, turn: Turn) -> Turn:
        """Store a turn, idempotently on ``idempotency_key``.

        Re-ingesting the same key with identical content returns the stored
        turn without creating a duplicate (section 6.3). Raises
        :class:`SessionNotFound`, :class:`SessionClosed`,
        :class:`DuplicateTurnIndex` or :class:`IdempotencyConflict`.
        """

    def list_turns(self, session_id: str) -> List[Turn]:
        """Return the session's turns ordered by ``turn_index``."""
