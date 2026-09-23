"""Conversation Orchestrator — architecture.md section 6.3.

Accepts normalised conversation events, enforces ordering and idempotency,
persists them, and requests analysis when eligible.

Two responsibilities are deliberately placed here rather than in storage:

* **Ordering and contiguity.** A unique index can express "no duplicate
  ``turn_index``" but not "no gaps", so the gap rule lives in the domain.
* **Source authorisation.** Section 6.1 requires every ingested conversation to
  have a registered source version, so ingestion passes through the Dataset Use
  Gate. Sealed data therefore fails here, not at a convention.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, List, Optional

from src.domain.analysis.records import AnalysisJob
from src.domain.conversations.records import Session, Turn
from src.domain.conversations.repository import ConversationRepository, SessionNotFound
from src.domain.provenance.data_sources import (
    DataUsePurpose,
    DataUseRequest,
    ExecutionMode,
)
from src.modules.analysis.dispatcher import AnalysisJobDispatcher
from src.modules.source_registry.gate import DatasetUseGate


class TurnOutOfOrder(ValueError):
    """A turn arrived with an index that would leave a gap or go backwards."""


@dataclasses.dataclass(frozen=True)
class SessionDescriptor:
    """Session metadata carried by the first turn of a conversation."""

    session_id: str
    run_id: str
    external_session_id: str
    source_version_id: str
    scenario_id: str
    raw_theme_label: str
    companion_condition: str


@dataclasses.dataclass(frozen=True)
class IngestTurn:
    """Command: store one turn and request analysis if it is new."""

    session: SessionDescriptor
    turn: Turn
    requested_by: str = "ingestion"


@dataclasses.dataclass(frozen=True)
class IngestedTurn:
    """Result: what was stored, and whether this call was a replay."""

    turn: Turn
    session: Session
    job: Optional[AnalysisJob]
    replayed: bool


@dataclasses.dataclass(frozen=True)
class CloseSession:
    session_id: str


@dataclasses.dataclass(frozen=True)
class SessionSummary:
    session: Session
    turn_count: int


class ConversationOrchestrator:
    def __init__(
        self,
        conversations: ConversationRepository,
        dispatcher: AnalysisJobDispatcher,
        gate: DatasetUseGate,
        clock: Callable[[], str],
    ):
        self._conversations = conversations
        self._dispatcher = dispatcher
        self._gate = gate
        self._clock = clock

    def ingest_turn(self, command: IngestTurn) -> IngestedTurn:
        """Store a turn and, if it is new, request its analysis.

        The caller owns the transaction. Running this inside a unit of work is
        what satisfies section 6.3's "analysis begins only after the durable
        turn transaction succeeds": the turn and its job commit together or not
        at all.

        Raises :class:`DataUseNotAuthorized` if the source is not registered or
        not permitted for development, :class:`TurnOutOfOrder` if the index
        would leave a gap, and the ``ConversationRepository`` error modes for
        idempotency conflicts.
        """
        self._authorize(command)

        session = self._ensure_session(command)
        existing = self._conversations.list_turns(session.id)
        occupied = {turn.turn_index for turn in existing}

        is_new = command.turn.turn_index not in occupied
        if is_new and command.turn.turn_index != len(existing):
            raise TurnOutOfOrder(
                "Session {!r} has {} turns, so the next index is {}; received "
                "{}.".format(
                    session.id, len(existing), len(existing), command.turn.turn_index
                )
            )

        stored = self._conversations.append_turn(command.turn)
        if not is_new:
            return IngestedTurn(turn=stored, session=session, job=None, replayed=True)

        job = None
        if self._completes_an_exchange(stored, existing):
            job = self._dispatcher.request_analysis(session.id, stored.id)
        return IngestedTurn(turn=stored, session=session, job=job, replayed=False)

    def close_session(self, command: CloseSession) -> SessionSummary:
        session = self._conversations.close_session(command.session_id, self._clock())
        turns = self._conversations.list_turns(session.id)
        return SessionSummary(session=session, turn_count=len(turns))

    # -- internals -------------------------------------------------------

    @staticmethod
    def _completes_an_exchange(stored: Turn, existing: List[Turn]) -> bool:
        """Is this turn the companion response that closes an exchange?

        The rubric's unit of assessment is the exchange: a user turn plus the
        companion response that follows it ([`RUBRIC_v0.1.md` §3]). Requesting
        analysis on a user turn that has no response yet would produce a
        half-assessment nobody asked for, and would double the judge calls a
        conversation costs. See D-18.
        """
        if stored.role != "assistant":
            return False
        preceding = stored.turn_index - 1
        return any(
            turn.turn_index == preceding and turn.role == "user" for turn in existing
        )

    def _authorize(self, command: IngestTurn) -> None:
        self._gate.authorize(
            DataUseRequest(
                source_version_id=command.session.source_version_id,
                purpose=DataUsePurpose.DEVELOPMENT,
                execution_mode=ExecutionMode.DEVELOPMENT,
                requested_by=command.requested_by,
            )
        )

    def _ensure_session(self, command: IngestTurn) -> Session:
        descriptor = command.session
        try:
            return self._conversations.get_session(descriptor.session_id)
        except SessionNotFound:
            return self._conversations.create_session(
                Session(
                    id=descriptor.session_id,
                    run_id=descriptor.run_id,
                    external_session_id=descriptor.external_session_id,
                    source_version_id=descriptor.source_version_id,
                    scenario_id=descriptor.scenario_id,
                    raw_theme_label=descriptor.raw_theme_label,
                    companion_condition=descriptor.companion_condition,
                    created_at=self._clock(),
                )
            )
