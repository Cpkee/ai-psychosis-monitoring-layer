"""PostgreSQL seed-pipeline repositories.

Uniqueness lives in the schema: one snapshot per content hash, one cache entry
per key. The cache insert is ``ON CONFLICT DO NOTHING`` followed by a read, so
two team members extracting the same document concurrently both end up with
the first reply stored.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Optional, Tuple

import psycopg

from src.domain.seeds.records import (
    TERMINAL,
    CacheKey,
    ExtractionCacheEntry,
    QueryLogEntry,
    Seed,
    SourceDocument,
)
from src.domain.seeds.repository import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
    DocumentNotFound,
    SeedAlreadyExists,
)

_QUERY_COLUMNS = ("id", "source", "query_id", "query_text", "query_config_version",
                  "executed_at", "result_ids")
_DOCUMENT_COLUMNS = tuple(f.name for f in dataclasses.fields(SourceDocument))
_SEED_COLUMNS = tuple(f.name for f in dataclasses.fields(Seed))
_SEED_ARRAYS = {"raw_theme_terms", "reported_phase_progression", "companion_behaviour_reported"}


def _insert(table: str, columns) -> str:
    return "INSERT INTO {} ({}) VALUES ({})".format(
        table, ", ".join(columns), ", ".join(["%s"] * len(columns)))


class PostgresSourceDocumentRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def log_query(self, entry: QueryLogEntry) -> QueryLogEntry:
        values = [getattr(entry, c) for c in _QUERY_COLUMNS]
        values[-1] = list(entry.result_ids)
        self._connection.execute(_insert("seed_query_log", _QUERY_COLUMNS), values)
        return entry

    def list_queries(self) -> Tuple[QueryLogEntry, ...]:
        rows = self._connection.execute(
            "SELECT {} FROM seed_query_log ORDER BY executed_at, id".format(
                ", ".join(_QUERY_COLUMNS))).fetchall()
        return tuple(QueryLogEntry(*row[:-1], result_ids=tuple(row[-1])) for row in rows)

    def save(self, document: SourceDocument) -> SourceDocument:
        try:
            self._connection.execute(_insert("source_documents", _DOCUMENT_COLUMNS),
                                     [getattr(document, c) for c in _DOCUMENT_COLUMNS])
        except psycopg.errors.UniqueViolation:
            raise DocumentAlreadyExists("Document {!r} or its content is already stored.".format(
                document.id))
        return document

    def get(self, document_id: str) -> SourceDocument:
        found = self._one("id = %s", document_id)
        if found is None:
            raise DocumentNotFound("No source document {!r}.".format(document_id))
        return found

    def find_by_hash(self, content_hash: str) -> Optional[SourceDocument]:
        return self._one("content_hash = %s", content_hash)

    def update(self, document: SourceDocument, expected_status: str) -> SourceDocument:
        row = self._connection.execute(
            "UPDATE source_documents SET status = %s, failure_code = %s, status_detail = %s, "
            "processed_prompt_version = %s, processed_model_version = %s "
            "WHERE id = %s AND status = %s RETURNING id",
            (document.status, document.failure_code, document.status_detail,
             document.processed_prompt_version, document.processed_model_version,
             document.id, expected_status)).fetchone()
        if row is None:
            stored = self.get(document.id)
            raise ConcurrentDocumentUpdate("Document {!r} is {}, not {}.".format(
                document.id, stored.status, expected_status))
        return document

    def list_unfinished(self) -> Tuple[SourceDocument, ...]:
        return self._many("NOT (status = ANY(%s))", sorted(TERMINAL))

    def list_by_status(self, *statuses: str) -> Tuple[SourceDocument, ...]:
        return self._many("status = ANY(%s)", list(statuses))

    def _many(self, where: str, value: Any) -> Tuple[SourceDocument, ...]:
        rows = self._connection.execute(
            "SELECT {} FROM source_documents WHERE {} ORDER BY retrieved_at, id".format(
                ", ".join(_DOCUMENT_COLUMNS), where), (value,)).fetchall()
        return tuple(SourceDocument(*row) for row in rows)

    def _one(self, where: str, value: Any) -> Optional[SourceDocument]:
        row = self._connection.execute(
            "SELECT {} FROM source_documents WHERE {}".format(", ".join(_DOCUMENT_COLUMNS), where),
            (value,)).fetchone()
        return SourceDocument(*row) if row is not None else None


class PostgresExtractionCacheRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def get(self, key: CacheKey) -> Optional[ExtractionCacheEntry]:
        row = self._connection.execute(
            "SELECT provider, model, reply_text, created_at FROM extraction_cache "
            "WHERE content_hash = %s AND prompt_version = %s AND model_version = %s",
            (key.content_hash, key.prompt_version, key.model_version)).fetchone()
        if row is None:
            return None
        return ExtractionCacheEntry(key=key, provider=row[0], model=row[1],
                                    reply_text=row[2], created_at=row[3])

    def put(self, entry: ExtractionCacheEntry) -> ExtractionCacheEntry:
        key = entry.key
        self._connection.execute(
            "INSERT INTO extraction_cache (content_hash, prompt_version, model_version, "
            "provider, model, reply_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (key.content_hash, key.prompt_version, key.model_version, entry.provider,
             entry.model, entry.reply_text, entry.created_at))
        return self.get(key)


class PostgresSeedRepository:
    def __init__(self, connection: psycopg.Connection):
        self._connection = connection

    def save_all(self, seeds: Tuple[Seed, ...]) -> Tuple[Seed, ...]:
        # One statement per seed inside the caller's transaction; a savepoint
        # makes the batch all-or-nothing even if the caller carries on.
        try:
            with self._connection.transaction():
                for ordinal, seed in enumerate(seeds):
                    values = [list(getattr(seed, c)) if c in _SEED_ARRAYS else getattr(seed, c)
                              for c in _SEED_COLUMNS]
                    self._connection.execute(
                        _insert("seeds", _SEED_COLUMNS + ("ordinal",)), values + [ordinal])
        except psycopg.errors.UniqueViolation:
            raise SeedAlreadyExists("A seed in this batch is already stored.")
        return seeds

    def list_for_document(self, document_id: str) -> Tuple[Seed, ...]:
        rows = self._connection.execute(
            "SELECT {} FROM seeds WHERE source_document_id = %s "
            "ORDER BY created_at, extraction_prompt_version, extraction_model_version, "
            "ordinal".format(
                ", ".join(_SEED_COLUMNS)), (document_id,)).fetchall()
        seeds = []
        for row in rows:
            fields = dict(zip(_SEED_COLUMNS, row))
            for name in _SEED_ARRAYS:
                fields[name] = tuple(fields[name])
            seeds.append(Seed(**fields))
        return tuple(seeds)
