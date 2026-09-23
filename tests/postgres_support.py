"""Shared PostgreSQL test helpers.

``reset_database`` discovers the tables rather than naming them. Each module
used to hand-roll its own ``TRUNCATE``, and every one of them broke the moment
``analysis_jobs`` added a foreign key to ``turns``. Discovering the tables means
the next table cannot break them again.
"""

from __future__ import annotations


def reset_database(connection) -> None:
    from src.adapters.postgres.connection import (
        refuse_shared_database,
        refuse_unless_test_database,
    )

    try:
        refuse_shared_database(connection, "reset")
        refuse_unless_test_database(connection, "reset")
    except Exception:
        # Callers apply the schema first, inside the same transaction, and a
        # setUp that raises never reaches tearDown. Without this the refused
        # connection stays open holding table locks, and every later test
        # waits on them instead of failing.
        connection.rollback()
        connection.close()
        raise
    rows = connection.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    ).fetchall()
    if rows:
        connection.execute(
            "TRUNCATE {} CASCADE".format(", ".join(row[0] for row in rows))
        )
