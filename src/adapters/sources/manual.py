"""Human-supplied documents: news, legal filings, incident databases (D-24).

A person lists each document in a JSON input file (git-ignored), declaring its
``source_type``, which sets its credibility tier. Supported: web pages, and local
``.html``, ``.txt`` and ``.md`` files. PDFs are refused until a PDF reader is
added (D-40): absent beats a half-working text extraction.

Input file shape (all values are examples)::

    {"documents": [
      {"url": "https://example.org/news/story", "source_type": "news_named_sources"},
      {"path": "inputs/filing.txt", "source_type": "legal_filing",
       "title": "Example v. Example", "publication_date": "2026-01-01"}
    ]}
"""

from __future__ import annotations

import dataclasses
import json
import os
from html.parser import HTMLParser
from typing import List, Optional, Tuple

from src.adapters.http import HttpClient
from src.domain.seeds.collection import FetchedDocument, UnsupportedDocument

FETCHER_VERSION = "manual_input_v0.1"


@dataclasses.dataclass(frozen=True)
class ManualEntry:
    source_type: str
    url: Optional[str] = None
    path: Optional[str] = None
    title: Optional[str] = None
    publication_date: Optional[str] = None

    def __post_init__(self) -> None:
        if bool(self.url) == bool(self.path):
            raise ValueError("Each input entry needs exactly one of 'url' or 'path'.")


def load_entries(input_path: str) -> Tuple[ManualEntry, ...]:
    with open(input_path, "r", encoding="utf-8") as handle:
        document = json.load(handle)
    return tuple(ManualEntry(**entry) for entry in document["documents"])


class ManualFetcher:
    def __init__(self, http: HttpClient, base_dir: str = "."):
        self._http = http
        self._base_dir = base_dir

    def fetch(self, entry: ManualEntry) -> FetchedDocument:
        location = entry.url or entry.path
        if location.lower().endswith(".pdf"):
            raise UnsupportedDocument("PDF input is not supported yet (D-40): {}".format(location))
        if entry.url:
            raw = self._http.get(entry.url)
            source_url = entry.url
        else:
            path = os.path.join(self._base_dir, entry.path)
            with open(path, "rb") as handle:
                raw = handle.read()
            source_url = "file:" + os.path.abspath(path)
        if raw.startswith(b"%PDF"):
            raise UnsupportedDocument("PDF input is not supported yet (D-40): {}".format(location))
        decoded = raw.decode("utf-8", errors="replace")
        is_html = decoded.lstrip()[:1] == "<" or location.lower().endswith((".html", ".htm"))
        title, text = html_to_text(decoded) if is_html else (None, decoded.strip())
        if not text:
            raise UnsupportedDocument("No readable text in {}.".format(location))
        return FetchedDocument(
            source_type=entry.source_type,
            source_url=source_url,
            title=entry.title or title or location,
            text=text,
            fetcher_version=FETCHER_VERSION,
            publication_date=entry.publication_date,
        )


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "nav", "footer", "header", "form"}
    _BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "article",
              "section", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.title: Optional[str] = None
        self._skipping = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skipping += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skipping:
            self._skipping -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data.strip()
        elif not self._skipping:
            self.parts.append(data)


def html_to_text(html: str) -> Tuple[Optional[str], str]:
    parser = _TextExtractor()
    parser.feed(html)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return parser.title, "\n".join(line for line in lines if line)
