"""arXiv via its Atom API. Snapshots are title plus abstract; PDFs are not
fetched yet (D-40). Every arXiv record is a ``preprint`` (D-25).

The benchmark's own paper will appear in searches on this topic. The seal
screen blocks it by arXiv id before any model sees it (D-27).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List

from src.adapters.http import HttpClient
from src.domain.seeds.collection import FetchedDocument, SearchResult

API = "https://export.arxiv.org/api/query"
FETCHER_VERSION = "arxiv_atom_v0.1"
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivClient:
    def __init__(self, http: HttpClient):
        self._http = http

    def search(self, text: str, max_results: int) -> SearchResult:
        feed = self._http.get(API, {"search_query": text, "start": 0,
                                    "max_results": max_results})
        documents = parse_feed(feed)
        return SearchResult(result_ids=tuple(d.external_id.split()[0] for d in documents),
                            documents=tuple(documents))


def parse_feed(xml_bytes: bytes) -> List[FetchedDocument]:
    documents = []
    for entry in ET.fromstring(xml_bytes).findall("atom:entry", _NS):
        url = _text(entry, "atom:id").replace("http://", "https://")
        arxiv_id = url.rsplit("/abs/", 1)[-1]
        title = _collapse(_text(entry, "atom:title"))
        abstract = _collapse(_text(entry, "atom:summary"))
        if not arxiv_id or not abstract:
            continue
        doi = _text(entry, "arxiv:doi")
        documents.append(FetchedDocument(
            source_type="preprint",
            source_url=url,
            title=title,
            text="{}\n\n{}".format(title, abstract),
            fetcher_version=FETCHER_VERSION,
            external_id=" ".join(filter(None, ("arXiv:" + arxiv_id, "DOI:" + doi if doi else None))),
            publication_date=_text(entry, "atom:published")[:10] or None,
        ))
    return documents


def _text(entry, path: str) -> str:
    found = entry.find(path, _NS)
    return (found.text or "").strip() if found is not None else ""


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
