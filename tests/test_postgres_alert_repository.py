"""Binds the AlertRepository contract to the PostgreSQL adapter, and checks
that storage refuses an invalid alert even if the record check is bypassed."""

from __future__ import annotations

import os
import unittest

from tests.contract.alert_repository import (
    TRAJECTORY_IDS,
    AlertRepositoryContract,
    make_alert,
)
from tests.contract.conversation_repository import make_session, make_turn
from tests.contract.trajectory_repository import make_update
from tests.postgres_support import reset_database

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresAlertRepositoryTest(AlertRepositoryContract, unittest.TestCase):
    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect
        from src.adapters.postgres.conversations import PostgresConversationRepository
        from src.adapters.postgres.trajectories import PostgresTrajectoryRepository

        self._connection = connect(TEST_DATABASE_URL)
        apply_schema(self._connection)
        reset_database(self._connection)

        # An alert references its session, turn and trajectory update: it can
        # never cite a derivation that was not stored.
        conversations = PostgresConversationRepository(self._connection)
        conversations.create_session(make_session())
        for index in (0, 1):
            conversations.append_turn(
                make_turn(
                    id="example-turn-{}".format(index),
                    turn_index=index,
                    role="user" if index == 0 else "assistant",
                    idempotency_key="example-key-{}".format(index),
                )
            )
        trajectories = PostgresTrajectoryRepository(self._connection)
        for update_id in TRAJECTORY_IDS:
            trajectories.save(make_update(update_id=update_id))
        self._connection.commit()

    def tearDown(self):
        self._connection.rollback()
        self._connection.close()

    def repository(self):
        from src.adapters.postgres.alerts import PostgresAlertRepository

        return PostgresAlertRepository(self._connection)

    def _copy_with(self, severity="severity", evidence="evidence_turn_ids"):
        """Store a valid alert, then write a copy directly in SQL with one
        column replaced, bypassing the record's own validation."""
        from src.adapters.postgres.alerts import PostgresAlertRepository

        PostgresAlertRepository(self._connection).save(make_alert())
        self._connection.execute(
            "INSERT INTO alerts (id, session_id, through_turn_id, rule_set_version, rule_id, "
            "status, severity, requires_manual_review, contributing_assessment_ids, "
            "trajectory_update_id, triggering_signal_score_ids, evidence_turn_ids, "
            "context_categories_present, context_modifier_applied, explanation, "
            "judge_model_version, rubric_version, taxonomy_version, "
            "trajectory_policy_version, created_at) "
            "SELECT 'example-alert-raw', session_id, through_turn_id, rule_set_version, "
            "'another-example-rule', status, " + severity + ", requires_manual_review, "
            "contributing_assessment_ids, %s, triggering_signal_score_ids, " + evidence + ", "
            "context_categories_present, context_modifier_applied, explanation, "
            "judge_model_version, rubric_version, taxonomy_version, "
            "trajectory_policy_version, created_at FROM alerts WHERE id = 'example-alert-1'",
            (TRAJECTORY_IDS[1],),
        )

    def test_storage_refuses_an_alert_without_evidence(self):
        import psycopg

        with self.assertRaises(psycopg.errors.CheckViolation):
            self._copy_with(evidence="'{}'::TEXT[]")

    def test_storage_refuses_a_raised_alert_without_a_severity(self):
        import psycopg

        with self.assertRaises(psycopg.errors.CheckViolation):
            self._copy_with(severity="NULL")


if __name__ == "__main__":
    unittest.main()
