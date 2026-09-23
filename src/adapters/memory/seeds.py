"""In-memory seed-pipeline repositories."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

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


class InMemorySourceDocumentRepository:
    def __init__(self) -> None:
        self._queries: List[QueryLogEntry] = []
        self._by_id: Dict[str, SourceDocument] = {}
        self._order: List[str] = []

    def log_query(self, entry: QueryLogEntry) -> QueryLogEntry:
        self._queries.append(entry)
        return entry

    def list_queries(self) -> Tuple[QueryLogEntry, ...]:
        return tuple(self._queries)

    def save(self, document: SourceDocument) -> SourceDocument:
        if document.id in self._by_id or self.find_by_hash(document.content_hash):
            raise DocumentAlreadyExists("Document {!r} or its content is already stored.".format(
                document.id))
        self._by_id[document.id] = document
        self._order.append(document.id)
        return document

    def get(self, document_id: str) -> SourceDocument:
        try:
            return self._by_id[document_id]
        except KeyError:
            raise DocumentNotFound("No source document {!r}.".format(document_id))

    def find_by_hash(self, content_hash: str) -> Optional[SourceDocument]:
        for document in self._by_id.values():
            if document.content_hash == content_hash:
                return document
        return None

    def update(self, document: SourceDocument, expected_status: str) -> SourceDocument:
        stored = self.get(document.id)
        if stored.status != expected_status:
            raise ConcurrentDocumentUpdate("Document {!r} is {}, not {}.".format(
                document.id, stored.status, expected_status))
        self._by_id[document.id] = document
        return document

    def list_unfinished(self) -> Tuple[SourceDocument, ...]:
        return tuple(sorted(
            (self._by_id[i] for i in self._order if self._by_id[i].status not in TERMINAL),
            key=lambda d: (d.retrieved_at, self._order.index(d.id))))


class InMemoryExtractionCacheRepository:
    def __init__(self) -> None:
        self._entries: Dict[CacheKey, ExtractionCacheEntry] = {}

    def get(self, key: CacheKey) -> Optional[ExtractionCacheEntry]:
        return self._entries.get(key)

    def put(self, entry: ExtractionCacheEntry) -> ExtractionCacheEntry:
        return self._entries.setdefault(entry.key, entry)


class InMemorySeedRepository:
    def __init__(self) -> None:
        self._seeds: Dict[str, Seed] = {}

    def save_all(self, seeds: Tuple[Seed, ...]) -> Tuple[Seed, ...]:
        ids = [seed.id for seed in seeds]
        if len(set(ids)) != len(ids) or any(i in self._seeds for i in ids):
            raise SeedAlreadyExists("A seed in this batch is already stored.")
        for seed in seeds:
            self._seeds[seed.id] = seed
        return seeds

    def list_for_document(self, document_id: str) -> Tuple[Seed, ...]:
        return tuple(s for s in self._seeds.values() if s.source_document_id == document_id)
