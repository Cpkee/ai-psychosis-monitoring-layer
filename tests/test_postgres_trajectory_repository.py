"""Binds the TrajectoryRepository contract to the PostgreSQL adapter."""

from __future__ import annotations

import os
import unittest

from tests.contract.conversation_repository import make_session, make_turn
from tests.contract.trajectory_repository import TrajectoryRepositoryContract
from tests.postgres_support import reset_database

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresTrajectoryRepositoryTest(TrajectoryRepositoryContract, unittest.TestCase):
    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect
        from src.adapters.postgres.conversations import PostgresConversationRepository

        self._connection = connect(TEST_DATABASE_URL)
        apply_schema(self._connection)
        reset_database(self._connection)

        # trajectory_updates references sessions and turns: a derivation cannot
        # point at a conversation that was never stored.
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
        self._connection.commit()

    def tearDown(self):
        self._connection.close()

    def repository(self):
        from src.adapters.postgres.trajectories import PostgresTrajectoryRepository

        return PostgresTrajectoryRepository(self._connection)


if __name__ == "__main__":
    unittest.main()
