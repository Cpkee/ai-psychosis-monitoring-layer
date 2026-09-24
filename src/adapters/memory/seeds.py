"""In-memory seed-pipeline repositories."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from src.domain.seeds.overlap import FlagReview, OverlapCheck
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
    OverlapCheckAlreadyExists,
    OverlapCheckNotFound,
    ReviewConflict,
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
        return self._sorted(d for d in self._by_id.values() if d.status not in TERMINAL)

    def list_by_status(self, *statuses: str) -> Tuple[SourceDocument, ...]:
        return self._sorted(d for d in self._by_id.values() if d.status in statuses)

    def _sorted(self, documents) -> Tuple[SourceDocument, ...]:
        return tuple(sorted(documents, key=lambda d: (d.retrieved_at, self._order.index(d.id))))


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


class InMemorySeedFilterRepository:
    def __init__(self) -> None:
        self._checks: Dict[str, OverlapCheck] = {}
        self._reviews: List[FlagReview] = []

    def record_check(self, check: OverlapCheck) -> OverlapCheck:
        key = self._key(check)
        for stored in self._checks.values():
            if self._key(stored) == key:
                return stored
        if check.id in self._checks:
            raise OverlapCheckAlreadyExists(
                "Overlap check {!r} is already stored for another seed or screen.".format(
                    check.id))
        self._checks[check.id] = check
        return check

    def list_checks(self, screen_version: str,
                    manifest_sha256: str) -> Tuple[OverlapCheck, ...]:
        found = [c for c in self._checks.values()
                 if (c.screen_version, c.manifest_sha256) == (screen_version, manifest_sha256)]
        return tuple(sorted(found, key=lambda c: (c.checked_at, c.id)))

    def save_review(self, review: FlagReview) -> FlagReview:
        if review.overlap_check_id not in self._checks:
            raise OverlapCheckNotFound("No overlap check {!r}.".format(review.overlap_check_id))
        chain = [r for r in self._reviews if r.overlap_check_id == review.overlap_check_id]
        forks = (
            any(r.id == review.id for r in self._reviews)
            or (review.supersedes is None and chain)
            or (review.supersedes is not None
                and (review.supersedes not in {r.id for r in chain}
                     or any(r.supersedes == review.supersedes for r in self._reviews)))
        )
        if forks:
            raise ReviewConflict("Review {!r} does not extend the history of check {!r}.".format(
                review.id, review.overlap_check_id))
        self._reviews.append(review)
        return review

    def latest_review(self, check_id: str) -> Optional[FlagReview]:
        superseded = {r.supersedes for r in self._reviews}
        for review in self._reviews:
            if review.overlap_check_id == check_id and review.id not in superseded:
                return review
        return None

    @staticmethod
    def _key(check: OverlapCheck):
        return (check.seed_id, check.screen_version, check.manifest_sha256)
