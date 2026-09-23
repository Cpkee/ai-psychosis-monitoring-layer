"""D-41: only a database named ``*_test`` may be truncated.

No database needed: a stand-in connection carries only the identity the guards
read. If a guard ever let one through, ``reset_database`` would call
``execute`` on the stand-in, which does not exist, and the test would error.
"""

from __future__ import annotations

import os
import types
import unittest

from src.adapters.postgres.connection import NotATestDatabase, refuse_unless_test_database
from tests.postgres_support import reset_database


class StandIn:
    """Carries only what the guards read, and records being released."""

    def __init__(self, dbname):
        self.info = types.SimpleNamespace(dbname=dbname, host="localhost", port=5433)
        self.released = []

    def rollback(self):
        self.released.append("rollback")

    def close(self):
        self.released.append("close")


def connection_to(dbname):
    return StandIn(dbname)


class TestDatabaseGuard(unittest.TestCase):
    def setUp(self):
        self._shared = os.environ.pop("SHARED_DATABASE_URL", None)

    def tearDown(self):
        if self._shared is not None:
            os.environ["SHARED_DATABASE_URL"] = self._shared

    def test_the_working_database_cannot_be_reset(self):
        with self.assertRaises(NotATestDatabase):
            reset_database(connection_to("apml"))

    def test_a_refused_reset_releases_its_connection(self):
        """Otherwise its schema locks block every later test (a hang, not a failure)."""
        connection = connection_to("apml")
        with self.assertRaises(NotATestDatabase):
            reset_database(connection)
        self.assertEqual(connection.released, ["rollback", "close"])

    def test_only_a_name_ending_in_test_passes(self):
        refuse_unless_test_database(connection_to("apml_test"), "reset")
        for name in ("apml", "apml_testing", "test_apml", "", None):
            with self.subTest(name=name), self.assertRaises(NotATestDatabase):
                refuse_unless_test_database(connection_to(name), "reset")


if __name__ == "__main__":
    unittest.main()
