"""Seed collector — searches, logs, and snapshots (SEED_PIPELINE_PLAN.md §3.1).

Every search is logged exactly as run, with the ids it returned. Every
document is stored as a raw-text snapshot identified by its content hash;
extraction later reads the snapshot, never the live page, so a changed page
becomes a new snapshot rather than silently changing a seed.

The collector calls no model. Its caller commits once per query or entry.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Mapping, Optional, Tuple

from src.domain.seeds.collection import FetchedDocument, SourceClient
from src.domain.seeds.records import QueryLogEntry, SourceDocument, content_hash
from src.domain.seeds.repository import SourceDocumentRepository
from src.modules.seeds.config import CredibilityTiers, QuerySpec


@dataclasses.dataclass(frozen=True)
class CollectionReport:
    new: Tuple[SourceDocument, ...]
    #: Snapshots already stored with identical content.
    already_stored: int


class SeedCollector:
    def __init__(self, documents: SourceDocumentRepository,
                 clients: Mapping[str, SourceClient], tiers: CredibilityTiers,
                 clock: Callable[[], str], new_id: Callable[[], str]):
        self._documents = documents
        self._clients = clients
        self._tiers = tiers
        self._clock = clock
        self._new_id = new_id

    def run_query(self, query: QuerySpec, query_config_version: str) -> CollectionReport:
        try:
            client = self._clients[query.source]
        except KeyError:
            raise ValueError("No client for source {!r} (query {}).".format(
                query.source, query.query_id))
        result = client.search(query.text, query.max_results)
        entry = self._documents.log_query(QueryLogEntry(
            id=self._new_id(), source=query.source, query_id=query.query_id,
            query_text=query.text, query_config_version=query_config_version,
            executed_at=self._clock(), result_ids=result.result_ids))
        stored = [self.snapshot(document, entry.id) for document in result.documents]
        new = tuple(d for d in stored if d is not None)
        return CollectionReport(new=new, already_stored=len(stored) - len(new))

    def snapshot(self, fetched: FetchedDocument,
                 query_log_id: Optional[str] = None) -> Optional[SourceDocument]:
        """Store a snapshot, or return None if identical content is stored."""
        # Refuse an unknown source type before storing anything: a snapshot
        # without a tier could never become a seed.
        self._tiers.tier_for(fetched.source_type)
        digest = content_hash(fetched.text)
        if self._documents.find_by_hash(digest) is not None:
            return None
        return self._documents.save(SourceDocument(
            id=self._new_id(), content_hash=digest, source_type=fetched.source_type,
            source_url=fetched.source_url, title=fetched.title, text=fetched.text,
            retrieved_at=self._clock(), fetcher_version=fetched.fetcher_version,
            external_id=fetched.external_id, publication_date=fetched.publication_date,
            query_log_id=query_log_id))
