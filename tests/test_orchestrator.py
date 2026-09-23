"""Conversation Orchestrator — architecture.md section 6.3.

The in-memory tests cover ordering, idempotency and authorisation. The
PostgreSQL test covers the one thing memory cannot express: that the turn and
its analysis job commit in a single transaction.
"""

from __future__ import annotations

import itertools
import os
import unittest

from src.adapters.memory.analysis import InMemoryJobRepository
from src.adapters.memory.conversations import InMemoryConversationRepository
from src.domain.analysis.records import ProcessingStatus
from src.domain.conversations.repository import IdempotencyConflict
from src.domain.provenance.data_sources import DataUseNotAuthorized
from src.modules.analysis.dispatcher import AnalysisJobDispatcher
from src.modules.ingestion.orchestrator import (
    CloseSession,
    ConversationOrchestrator,
    IngestTurn,
    SessionDescriptor,
    TurnOutOfOrder,
)
from src.modules.source_registry.gate import DatasetUseGate, InMemoryAuditSink
from tests.contract.conversation_repository import make_turn
from tests.contract.job_repository import VERSIONS
from tests.postgres_support import reset_database

SYNTHETIC = "synthetic-conversations@v1"
BENCH = "psychosis-bench@1.0"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def descriptor(**overrides) -> SessionDescriptor:
    fields = dict(
        session_id="example-session-1",
        run_id="example-run-1",
        external_session_id="example-external-1",
        source_version_id=SYNTHETIC,
        scenario_id="example-scenario-1",
        raw_theme_label="none",
        companion_condition="client_companion",
    )
    fields.update(overrides)
    return SessionDescriptor(**fields)


def ingest(index: int, **turn_overrides) -> IngestTurn:
    fields = dict(
        id="example-turn-{}".format(index),
        turn_index=index,
        role="user" if index % 2 == 0 else "assistant",
        idempotency_key="example-key-{}".format(index),
    )
    fields.update(turn_overrides)
    return IngestTurn(session=descriptor(), turn=make_turn(**fields))


def build(conversations=None, jobs=None):
    counter = itertools.count(1)
    clock = itertools.count(1)
    return ConversationOrchestrator(
        conversations=conversations or InMemoryConversationRepository(),
        dispatcher=AnalysisJobDispatcher(
            jobs=jobs or InMemoryJobRepository(),
            versions=VERSIONS,
            clock=lambda: "2026-01-01T00:00:{:02d}Z".format(next(clock)),
            new_id=lambda: "example-job-{}".format(next(counter)),
        ),
        gate=DatasetUseGate(audit_sink=InMemoryAuditSink()),
        clock=lambda: "2026-01-01T00:00:00Z",
    )


class Ingestion(unittest.TestCase):
    def setUp(self):
        self.jobs = InMemoryJobRepository()
        self.conversations = InMemoryConversationRepository()
        self.orchestrator = build(self.conversations, self.jobs)

    def test_a_user_turn_alone_is_stored_but_requests_no_analysis(self):
        """The unit of assessment is the exchange, so a user turn with no
        companion response yet is not scoreable work (D-18)."""
        result = self.orchestrator.ingest_turn(ingest(0))
        self.assertFalse(result.replayed)
        self.assertEqual(result.session.id, "example-session-1")
        self.assertEqual(result.turn.turn_index, 0)
        self.assertIsNone(result.job)
        self.assertEqual(self.jobs.list_for_session("example-session-1"), [])

    def test_the_companion_response_completes_the_exchange_and_requests_analysis(self):
        self.orchestrator.ingest_turn(ingest(0))
        result = self.orchestrator.ingest_turn(ingest(1))
        self.assertIsNotNone(result.job)
        self.assertEqual(result.job.status, ProcessingStatus.PENDING)
        self.assertEqual(result.job.through_turn_id, result.turn.id)

    def test_job_pins_the_artefact_versions_in_force(self):
        """Section 6.4: each job records the versions used to request it."""
        self.orchestrator.ingest_turn(ingest(0))
        job = self.orchestrator.ingest_turn(ingest(1)).job
        self.assertEqual(job.rubric_version, VERSIONS.rubric_version)
        self.assertEqual(job.taxonomy_version, VERSIONS.taxonomy_version)
        self.assertEqual(job.scale_version, VERSIONS.scale_version)
        self.assertEqual(job.judge_configuration_version, VERSIONS.judge_configuration_version)
        self.assertEqual(job.schema_version, VERSIONS.schema_version)

    def test_only_completed_exchanges_request_analysis(self):
        """Four turns are two exchanges, so two jobs and not four (D-18)."""
        for index in range(4):
            self.orchestrator.ingest_turn(ingest(index))
        jobs = self.jobs.list_for_session("example-session-1")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(
            [j.through_turn_id for j in jobs],
            ["example-turn-1", "example-turn-3"],
        )

    def test_a_trailing_user_turn_adds_no_job(self):
        for index in range(3):
            self.orchestrator.ingest_turn(ingest(index))
        self.assertEqual(len(self.jobs.list_for_session("example-session-1")), 1)

    def test_retry_creates_neither_a_second_turn_nor_a_second_job(self):
        """Section 6.3 and section 13: a retried ingestion duplicates nothing."""
        self.orchestrator.ingest_turn(ingest(0))
        first = self.orchestrator.ingest_turn(ingest(1))
        second = self.orchestrator.ingest_turn(ingest(1))
        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual(second.turn, first.turn)
        self.assertIsNone(second.job)
        self.assertEqual(len(self.conversations.list_turns("example-session-1")), 2)
        self.assertEqual(len(self.jobs.list_for_session("example-session-1")), 1)

    def test_reused_key_with_different_content_still_raises(self):
        self.orchestrator.ingest_turn(ingest(0))
        with self.assertRaises(IdempotencyConflict):
            self.orchestrator.ingest_turn(ingest(0, message="different text"))

    def test_a_gap_in_turn_index_is_rejected(self):
        """The rule deliberately kept out of storage: no gaps."""
        self.orchestrator.ingest_turn(ingest(0))
        with self.assertRaises(TurnOutOfOrder):
            self.orchestrator.ingest_turn(ingest(2))
        self.assertEqual(self.jobs.list_for_session("example-session-1"), [])

    def test_out_of_order_arrival_is_rejected(self):
        with self.assertRaises(TurnOutOfOrder):
            self.orchestrator.ingest_turn(ingest(3))

    def test_a_rejected_turn_requests_no_analysis(self):
        with self.assertRaises(TurnOutOfOrder):
            self.orchestrator.ingest_turn(ingest(1))
        self.assertEqual(self.jobs.list_for_session("example-session-1"), [])


class SourceAuthorisation(unittest.TestCase):
    """Section 6.1: every ingested conversation has a registered source version."""

    def setUp(self):
        self.orchestrator = build()

    def test_sealed_benchmark_cannot_be_ingested(self):
        command = IngestTurn(
            session=descriptor(source_version_id=BENCH), turn=make_turn()
        )
        with self.assertRaises(DataUseNotAuthorized):
            self.orchestrator.ingest_turn(command)

    def test_unregistered_source_cannot_be_ingested(self):
        command = IngestTurn(
            session=descriptor(source_version_id="not-registered@1"), turn=make_turn()
        )
        with self.assertRaises(DataUseNotAuthorized):
            self.orchestrator.ingest_turn(command)

    def test_mindeval_annotations_cannot_be_ingested_as_conversations(self):
        command = IngestTurn(
            session=descriptor(
                source_version_id="mindeval-human-annotations@imported-2026-09-13"
            ),
            turn=make_turn(),
        )
        with self.assertRaises(DataUseNotAuthorized):
            self.orchestrator.ingest_turn(command)


class Closing(unittest.TestCase):
    def test_close_session_reports_what_was_stored(self):
        orchestrator = build()
        for index in range(3):
            orchestrator.ingest_turn(ingest(index))
        summary = orchestrator.close_session(CloseSession("example-session-1"))
        self.assertEqual(summary.turn_count, 3)
        self.assertIsNotNone(summary.session.closed_at)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class TurnAndJobCommitTogether(unittest.TestCase):
    """Section 6.3: analysis begins only after the durable turn transaction succeeds.

    Memory cannot express this. If the unit of work rolls back, neither the turn
    nor its job may survive, or the system ends up with a stored message nobody
    will ever analyse.
    """

    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect

        connection = connect(TEST_DATABASE_URL)
        apply_schema(connection)
        reset_database(connection)
        connection.commit()
        connection.close()

    def _orchestrator(self, connection):
        from src.adapters.postgres.analysis import PostgresJobRepository
        from src.adapters.postgres.conversations import PostgresConversationRepository

        counter = itertools.count(1)
        return ConversationOrchestrator(
            conversations=PostgresConversationRepository(connection),
            dispatcher=AnalysisJobDispatcher(
                jobs=PostgresJobRepository(connection),
                versions=VERSIONS,
                clock=lambda: "2026-01-01T00:00:00Z",
                new_id=lambda: "example-job-{}".format(next(counter)),
            ),
            gate=DatasetUseGate(audit_sink=InMemoryAuditSink()),
            clock=lambda: "2026-01-01T00:00:00Z",
        )

    def _counts(self):
        from src.adapters.postgres.connection import connect

        connection = connect(TEST_DATABASE_URL)
        try:
            return (
                connection.execute("SELECT count(*) FROM turns").fetchone()[0],
                connection.execute("SELECT count(*) FROM analysis_jobs").fetchone()[0],
            )
        finally:
            connection.close()

    def test_commit_persists_both(self):
        from src.adapters.postgres.connection import unit_of_work

        with unit_of_work(TEST_DATABASE_URL) as connection:
            orchestrator = self._orchestrator(connection)
            orchestrator.ingest_turn(ingest(0))
            orchestrator.ingest_turn(ingest(1))
        self.assertEqual(self._counts(), (2, 1))

    def test_rollback_leaves_neither(self):
        from src.adapters.postgres.connection import unit_of_work

        class Boom(RuntimeError):
            pass

        with self.assertRaises(Boom):
            with unit_of_work(TEST_DATABASE_URL) as connection:
                orchestrator = self._orchestrator(connection)
                orchestrator.ingest_turn(ingest(0))
                orchestrator.ingest_turn(ingest(1))
                raise Boom("a later step in the same unit of work failed")
        self.assertEqual(self._counts(), (0, 0))


if __name__ == "__main__":
    unittest.main()
