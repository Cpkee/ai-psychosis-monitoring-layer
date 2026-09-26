"""Repositories for the seed pipeline.

Seven aggregates: source documents (with the query log that found them), the
extraction cache, seeds, the Filter's overlap checks with their reviews,
selections with their split assignments, the exposure log, and relevance
decisions. Storage owns uniqueness (D-6): one document per content hash, one
cache entry per key, one seed per id, one check per seed and screen, one
unbroken chain of reviews per check, one unbroken chain of selections, one
split per seed for ever, one exposure per seed, person and activity, and one
unbroken chain of relevance decisions per seed.
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple

from src.domain.seeds.overlap import FlagReview, OverlapCheck
from src.domain.seeds.records import (
    CacheKey,
    ExtractionCacheEntry,
    QueryLogEntry,
    Seed,
    SourceDocument,
)
from src.domain.seeds.selection import ExposureEvent, RelevanceDecision, Selection


class DocumentNotFound(LookupError):
    """No source document exists with the given id."""


class DocumentAlreadyExists(ValueError):
    """The id is taken, or a snapshot with the same content hash is stored."""


class ConcurrentDocumentUpdate(RuntimeError):
    """The stored status no longer matches the one the caller read."""


class SeedAlreadyExists(ValueError):
    """A seed with the given id is already stored."""


class OverlapCheckAlreadyExists(ValueError):
    """The id is taken by a check for a different seed or screen."""


class OverlapCheckNotFound(LookupError):
    """No overlap check exists with the given id."""


class ReviewConflict(ValueError):
    """The review would fork the check's history: the check already has a
    review this one does not supersede, the superseded review was already
    superseded, or it belongs to another check."""


class SelectionConflict(ValueError):
    """The selection would fork the history: its version or the selection it
    supersedes is already taken, or it is a second first selection."""


class SplitConflict(ValueError):
    """A seed already holds a different split. Splits never change (D-34)."""


class RelevanceConflict(ValueError):
    """The decision would fork the seed's history: the seed already has a first
    decision, the superseded decision was already superseded, or it belongs to
    another seed."""


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


class SeedFilterRepository(Protocol):
    def record_check(self, check: OverlapCheck) -> OverlapCheck:
        """Insert if absent, keyed by (seed, screen version, manifest hash); the
        first write wins and is returned. Raises :class:`OverlapCheckAlreadyExists`
        if the id belongs to a different key."""

    def list_checks(self, screen_version: str,
                    manifest_sha256: str) -> Tuple[OverlapCheck, ...]:
        """Every check made under this screen and manifest, oldest first."""

    def save_review(self, review: FlagReview) -> FlagReview:
        """Append a review. Raises :class:`OverlapCheckNotFound` or
        :class:`ReviewConflict`."""

    def latest_review(self, check_id: str) -> Optional[FlagReview]:
        """The review no other review supersedes, if the check has any."""


class SeedSelectionRepository(Protocol):
    def save(self, selection: Selection) -> Selection:
        """Store the selection and its entries, and assign a split to every
        chosen seed that has none, all or nothing. Raises
        :class:`SelectionConflict` or :class:`SplitConflict`."""

    def latest(self) -> Optional[Selection]:
        """The selection no other supersedes, if any has been made."""

    def list_splits(self) -> Tuple[Tuple[str, str], ...]:
        """(seed id, split) for every seed ever chosen, by seed id. Includes
        seeds dropped from later selections: their split still binds them."""


class SeedExposureRepository(Protocol):
    def record(self, event: ExposureEvent) -> ExposureEvent:
        """Insert if absent, keyed by (seed, actor, activity); the first
        exposure wins and is returned."""

    def list_events(self) -> Tuple[ExposureEvent, ...]:
        """Every exposure, oldest first."""


class SeedRelevanceRepository(Protocol):
    def save(self, decision: RelevanceDecision) -> RelevanceDecision:
        """Append a decision. Raises :class:`RelevanceConflict`."""

    def list_latest(self) -> Tuple[RelevanceDecision, ...]:
        """For every seed with a decision, the one no other supersedes, by seed id."""
