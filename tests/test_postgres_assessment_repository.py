"""Binds the AssessmentRepository contract to the PostgreSQL adapter.

Also covers the one thing memory cannot: that a save spanning three tables
either lands completely or not at all.
"""

from __future__ import annotations

import os
import unittest

from tests.contract.assessment_repository import (
    AssessmentRepositoryContract,
    make_assessment,
)
from tests.contract.conversation_repository import make_session, make_turn
from tests.contract.job_repository import make_job
from tests.postgres_support import reset_database

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def _seed(connection):
    """assessments -> analysis_jobs -> turns -> sessions. The foreign keys are
    the point: an assessment cannot cite a turn that was never stored."""
    from src.adapters.postgres.analysis import PostgresJobRepository
    from src.adapters.postgres.conversations import PostgresConversationRepository

    conversations = PostgresConversationRepository(connection)
    conversations.create_session(make_session())
    conversations.append_turn(make_turn(id="example-turn-1", turn_index=0))
    PostgresJobRepository(connection).create(make_job())


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresAssessmentRepositoryTest(AssessmentRepositoryContract, unittest.TestCase):
    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect

        self._connection = connect(TEST_DATABASE_URL)
        apply_schema(self._connection)
        reset_database(self._connection)
        _seed(self._connection)
        self._connection.commit()

    def tearDown(self):
        self._connection.close()

    def repository(self):
        from src.adapters.postgres.assessments import PostgresAssessmentRepository

        return PostgresAssessmentRepository(self._connection)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class SaveIsAtomicAcrossThreeTables(unittest.TestCase):
    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect

        self._connection = connect(TEST_DATABASE_URL)
        apply_schema(self._connection)
        reset_database(self._connection)
        _seed(self._connection)
        self._connection.commit()

    def tearDown(self):
        self._connection.close()

    def _counts(self):
        return tuple(
            self._connection.execute("SELECT count(*) FROM " + table).fetchone()[0]
            for table in ("assessments", "signal_scores", "assessment_evidence")
        )

    def test_evidence_citing_a_missing_turn_stores_nothing_at_all(self):
        """The assessment and its scores must not survive a failed evidence write."""
        from src.adapters.postgres.assessments import PostgresAssessmentRepository
        from src.domain.assessments.records import EvidenceReference, ValidatedAssessment

        good = make_assessment()
        broken = ValidatedAssessment(
            assessment=good.assessment,
            scores=good.scores,
            evidence=(
                EvidenceReference(
                    assessment_id=good.assessment.id,
                    turn_id="a-turn-that-was-never-stored",
                    signal_code="harm_intent",
                ),
            ),
        )
        with self.assertRaises(Exception):
            PostgresAssessmentRepository(self._connection).save(broken)
        self.assertEqual(self._counts(), (0, 0, 0))

    def test_a_good_save_lands_completely(self):
        from src.adapters.postgres.assessments import PostgresAssessmentRepository

        PostgresAssessmentRepository(self._connection).save(make_assessment())
        self.assertEqual(self._counts(), (1, 9, 1))


if __name__ == "__main__":
    unittest.main()
