"""PostgreSQL connection helpers.

The repository takes an open connection rather than a URL or a pool. The
**caller owns the transaction**, which is what lets one unit of work span
several repositories — required by architecture section 6.3 ("analysis begins
only after the durable turn transaction succeeds").
"""

from __future__ import annotations

import contextlib
import os
from typing import Iterator, Optional

import psycopg
import psycopg.conninfo

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def database_url() -> Optional[str]:
    """The configured database, or ``None`` when no database is available."""
    return os.environ.get("DATABASE_URL") or None


class SharedDatabaseRefused(RuntimeError):
    """A destructive or schema-changing operation was aimed at the shared database."""


def points_at_shared_database(connection: psycopg.Connection) -> bool:
    """True if ``connection`` is to the database named by ``SHARED_DATABASE_URL``.

    Compared by host, port and database name rather than by URL text, so a
    differently spelled URL for the same database is still caught (D-28).
    """
    shared = os.environ.get("SHARED_DATABASE_URL")
    if not shared:
        return False
    target = psycopg.conninfo.conninfo_to_dict(shared)
    info = connection.info
    return (
        (target.get("host") or "localhost") == (info.host or "localhost")
        and str(target.get("port") or 5432) == str(info.port or 5432)
        and target.get("dbname") == info.dbname
    )


def refuse_shared_database(connection: psycopg.Connection, action: str) -> None:
    """D-28: no reset, TRUNCATE, DROP or ad-hoc schema change ever runs against
    the shared database. Its schema changes only through reviewed migrations."""
    if points_at_shared_database(connection):
        raise SharedDatabaseRefused(
            "Refusing to {} the shared database. Point DATABASE_URL at a local "
            "database.".format(action))


class NotATestDatabase(RuntimeError):
    """A table-truncating operation was aimed at a database not named ``*_test``."""


def refuse_unless_test_database(connection: psycopg.Connection, action: str) -> None:
    """D-41: only a database whose name ends in ``_test`` may be reset.

    The working database holds collected snapshots, cached extractor replies
    and seeds, which cost real model calls to reproduce. A naming rule, rather
    than a list of protected databases, fails closed: a new database is
    protected until someone deliberately names it for tests.
    """
    name = connection.info.dbname or ""
    if not name.endswith("_test"):
        raise NotATestDatabase(
            "Refusing to {} database {!r}: only databases named *_test may be "
            "truncated. Point TEST_DATABASE_URL at apml_test.".format(action, name))


def connect(url: Optional[str] = None) -> psycopg.Connection:
    resolved = url or database_url()
    if not resolved:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg.connect(resolved)


def apply_schema(connection: psycopg.Connection) -> None:
    refuse_shared_database(connection, "apply schema.sql to")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as handle:
        connection.execute(handle.read())


@contextlib.contextmanager
def unit_of_work(url: Optional[str] = None) -> Iterator[psycopg.Connection]:
    """One transaction, committed on success and rolled back on any exception.

    Repositories constructed against the yielded connection share the
    transaction, so a turn and its analysis job commit together or not at all.
    """
    connection = connect(url)
    try:
        with connection.transaction():
            yield connection
    finally:
        connection.close()
