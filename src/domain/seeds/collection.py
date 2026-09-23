"""The source-client seam: what a search returns before it is snapshotted."""

from __future__ import annotations

import dataclasses
from typing import Optional, Protocol, Tuple


@dataclasses.dataclass(frozen=True)
class FetchedDocument:
    source_type: str
    source_url: str
    title: str
    text: str
    fetcher_version: str
    external_id: Optional[str] = None
    publication_date: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SearchResult:
    #: Every id the search returned, including any with no usable text, so the
    #: query log shows what the source actually said.
    result_ids: Tuple[str, ...]
    documents: Tuple[FetchedDocument, ...]


class UnsupportedDocument(ValueError):
    """A document type this collector cannot read yet (for example PDF)."""


class SourceClient(Protocol):
    def search(self, text: str, max_results: int) -> SearchResult:
        """Run one query and fetch its results."""
