"""Binds the ConversationRepository contract to the PostgreSQL adapter.

Skipped when TEST_DATABASE_URL is unset, so the governance and seal tests stay
runnable on a bare interpreter with no database.

    docker compose up -d
    export TEST_DATABASE_URL=postgresql://apml:apml@localhost:5433/apml
"""

from __future__ import annotations

import os
import unittest

from tests.contract.conversation_repository import ConversationRepositoryContract
from tests.postgres_support import reset_database

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresConversationRepositoryTest(ConversationRepositoryContract, unittest.TestCase):
    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect

        self._connection = connect(TEST_DATABASE_URL)
        apply_schema(self._connection)
        reset_database(self._connection)
        self._connection.commit()

    def tearDown(self):
        self._connection.close()

    def repository(self):
        from src.adapters.postgres.conversations import PostgresConversationRepository

        return PostgresConversationRepository(self._connection)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class CallerOwnedTransactions(unittest.TestCase):
    """The answer to the cross-repository transaction question.

    The repository takes a connection, so the caller owns the transaction. That
    is what lets one unit of work span several repositories, which section 6.3
    requires: "analysis begins only after the durable turn transaction
    succeeds". Nothing in the repository interface had to change to allow it.
    """

    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect

        connection = connect(TEST_DATABASE_URL)
        apply_schema(connection)
        reset_database(connection)
        connection.commit()
        connection.close()

    def test_rollback_discards_everything_written_in_the_unit_of_work(self):
        from src.adapters.postgres.connection import connect, unit_of_work
        from src.adapters.postgres.conversations import PostgresConversationRepository
        from tests.contract.conversation_repository import make_session, make_turn

        class Boom(RuntimeError):
            pass

        with self.assertRaises(Boom):
            with unit_of_work(TEST_DATABASE_URL) as connection:
                repository = PostgresConversationRepository(connection)
                repository.create_session(make_session())
                repository.append_turn(make_turn())
                raise Boom("a later step in the same unit of work failed")

        verify = connect(TEST_DATABASE_URL)
        try:
            count = verify.execute("SELECT count(*) FROM sessions").fetchone()[0]
            turns = verify.execute("SELECT count(*) FROM turns").fetchone()[0]
        finally:
            verify.close()
        self.assertEqual((count, turns), (0, 0))

    def test_commit_persists_across_connections(self):
        from src.adapters.postgres.connection import connect, unit_of_work
        from src.adapters.postgres.conversations import PostgresConversationRepository
        from tests.contract.conversation_repository import make_session, make_turn

        with unit_of_work(TEST_DATABASE_URL) as connection:
            repository = PostgresConversationRepository(connection)
            repository.create_session(make_session())
            repository.append_turn(make_turn())

        verify = connect(TEST_DATABASE_URL)
        try:
            stored = PostgresConversationRepository(verify).list_turns("example-session-1")
        finally:
            verify.close()
        self.assertEqual([t.turn_index for t in stored], [0])


if __name__ == "__main__":
    unittest.main()
