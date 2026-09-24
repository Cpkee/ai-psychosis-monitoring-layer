"""Binds the seed-pipeline repository contracts to PostgreSQL, and checks the
shared-database guard (D-28)."""

from __future__ import annotations

import os
import unittest

from tests.contract.seed_repositories import (
    ExtractionCacheRepositoryContract,
    ProcessedVersionsContract,
    SeedFilterRepositoryContract,
    SeedRepositoryContract,
    SourceDocumentRepositoryContract,
    make_document,
    make_seed,
)
from tests.postgres_support import reset_database

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


class _Postgres:
    store_document = False
    store_seeds = False

    def setUp(self):
        from src.adapters.postgres.connection import apply_schema, connect

        self._connection = connect(TEST_DATABASE_URL)
        apply_schema(self._connection)
        reset_database(self._connection)
        if self.store_document:
            # The cache and seeds reference the snapshot they came from.
            from src.adapters.postgres.seeds import PostgresSourceDocumentRepository

            PostgresSourceDocumentRepository(self._connection).save(make_document())
        if self.store_seeds:
            # Overlap checks reference the seed they screened.
            from src.adapters.postgres.seeds import PostgresSeedRepository

            PostgresSeedRepository(self._connection).save_all(
                (make_seed("example-seed-1"), make_seed("example-seed-2")))
        self._connection.commit()

    def tearDown(self):
        self._connection.rollback()
        self._connection.close()


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresSourceDocumentRepositoryTest(_Postgres, SourceDocumentRepositoryContract,
                                           unittest.TestCase):
    def repository(self):
        from src.adapters.postgres.seeds import PostgresSourceDocumentRepository

        return PostgresSourceDocumentRepository(self._connection)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresProcessedVersionsTest(_Postgres, ProcessedVersionsContract, unittest.TestCase):
    def repository(self):
        from src.adapters.postgres.seeds import PostgresSourceDocumentRepository

        return PostgresSourceDocumentRepository(self._connection)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresExtractionCacheRepositoryTest(_Postgres, ExtractionCacheRepositoryContract,
                                            unittest.TestCase):
    store_document = True

    def repository(self):
        from src.adapters.postgres.seeds import PostgresExtractionCacheRepository

        return PostgresExtractionCacheRepository(self._connection)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresSeedRepositoryTest(_Postgres, SeedRepositoryContract, unittest.TestCase):
    store_document = True

    def repository(self):
        from src.adapters.postgres.seeds import PostgresSeedRepository

        return PostgresSeedRepository(self._connection)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class PostgresSeedFilterRepositoryTest(_Postgres, SeedFilterRepositoryContract,
                                       unittest.TestCase):
    store_document = True
    store_seeds = True

    def repository(self):
        from src.adapters.postgres.seeds import PostgresSeedFilterRepository

        return PostgresSeedFilterRepository(self._connection)


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL is not set")
class SharedDatabaseGuard(unittest.TestCase):
    """D-28: resets and schema changes never run against the shared database."""

    def setUp(self):
        from src.adapters.postgres.connection import connect

        self._previous = os.environ.get("SHARED_DATABASE_URL")
        os.environ["SHARED_DATABASE_URL"] = TEST_DATABASE_URL
        self._connection = connect(TEST_DATABASE_URL)

    def tearDown(self):
        self._connection.close()
        if self._previous is None:
            os.environ.pop("SHARED_DATABASE_URL", None)
        else:
            os.environ["SHARED_DATABASE_URL"] = self._previous

    def test_reset_is_refused(self):
        from src.adapters.postgres.connection import SharedDatabaseRefused

        with self.assertRaises(SharedDatabaseRefused):
            reset_database(self._connection)

    def test_schema_application_is_refused(self):
        from src.adapters.postgres.connection import SharedDatabaseRefused, apply_schema

        with self.assertRaises(SharedDatabaseRefused):
            apply_schema(self._connection)

    def test_a_differently_spelled_url_for_the_same_database_is_still_caught(self):
        from src.adapters.postgres.connection import points_at_shared_database

        separator = "&" if "?" in TEST_DATABASE_URL else "?"
        os.environ["SHARED_DATABASE_URL"] = TEST_DATABASE_URL + separator + "application_name=example"
        self.assertTrue(points_at_shared_database(self._connection))


if __name__ == "__main__":
    unittest.main()
