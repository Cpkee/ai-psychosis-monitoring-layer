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

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def database_url() -> Optional[str]:
    """The configured database, or ``None`` when no database is available."""
    return os.environ.get("DATABASE_URL") or None


def connect(url: Optional[str] = None) -> psycopg.Connection:
    resolved = url or database_url()
    if not resolved:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg.connect(resolved)


def apply_schema(connection: psycopg.Connection) -> None:
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
