"""Repositories for the seed pipeline.

Three aggregates: source documents (with the query log that found them), the
extraction cache, and seeds. Storage owns uniqueness (D-6): one document per
content hash, one cache entry per key, one seed per id.
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple

from src.domain.seeds.records import (
    CacheKey,
    ExtractionCacheEntry,
    QueryLogEntry,
    Seed,
    SourceDocument,
)


class DocumentNotFound(LookupError):
    """No source document exists with the given id."""


class DocumentAlreadyExists(ValueError):
    """The id is taken, or a snapshot with the same content hash is stored."""


class ConcurrentDocumentUpdate(RuntimeError):
    """The stored status no longer matches the one the caller read."""


class SeedAlreadyExists(ValueError):
    """A seed with the given id is already stored."""


class SourceDocumentRepository(Protocol):
    def log_query(self, entry: QueryLogEntry) -> QueryLogEntry:
        """Append a search to the query log."""

    def list_queries(self) -> Tuple[QueryLogEntry, ...]:
        """Every logged search, oldest first."""

    def save(self, document: SourceDocument) -> SourceDocument:
        """Store a new snapshot. Raises :class:`DocumentAlreadyExists`."""

    def get(self, document_id: str) -> SourceDocument:
        """Raises :class:`DocumentNotFound`."""

    def find_by_hash(self, content_hash: str) -> Optional[SourceDocument]:
        """The snapshot with exactly this content, if already stored."""

    def update(self, document: SourceDocument, expected_status: str) -> SourceDocument:
        """Persist a status change, only if the stored status still matches.
        Raises :class:`ConcurrentDocumentUpdate`."""

    def list_unfinished(self) -> Tuple[SourceDocument, ...]:
        """Documents not yet in a terminal state, oldest retrieval first."""

    def list_by_status(self, *statuses: str) -> Tuple[SourceDocument, ...]:
        """Documents in any of the given states, oldest retrieval first."""


class ExtractionCacheRepository(Protocol):
    def get(self, key: CacheKey) -> Optional[ExtractionCacheEntry]:
        """The cached reply for this key, if any."""

    def put(self, entry: ExtractionCacheEntry) -> ExtractionCacheEntry:
        """Insert if absent. Entries are immutable: if the key is already
        present, the stored entry is returned unchanged."""


class SeedRepository(Protocol):
    def save_all(self, seeds: Tuple[Seed, ...]) -> Tuple[Seed, ...]:
        """Store every seed from one extraction, or none of them.
        Raises :class:`SeedAlreadyExists`."""

    def list_for_document(self, document_id: str) -> Tuple[Seed, ...]:
        """Every seed the document has ever had, current and superseded, in
        extraction order. ``records.current_seeds`` picks the current ones."""
