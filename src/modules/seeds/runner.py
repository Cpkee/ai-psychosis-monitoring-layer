"""Seed extraction runner — screens, extracts and validates one document.

The caller owns the transaction and calls :meth:`process` once per document, so
every step is saved as it happens and an interrupted run resumes where it
stopped (D-26). The seal screen always runs first: the extractor is never
called for a document that has not been screened clear (D-27).
"""

from __future__ import annotations

import dataclasses
from typing import Callable

from src.domain.seeds.extraction import (
    ExtractionOutputUnreadable,
    ExtractionRequest,
    Extractor,
    ExtractorUnavailable,
)
from src.domain.seeds.records import (
    BLOCKED_SEALED,
    DELAYED,
    EXTRACTED,
    FAILED,
    OUTPUT_UNREADABLE,
    SCREENED,
    SNAPSHOTTED,
    VALIDATION_FAILED,
    CacheKey,
    ExtractionCacheEntry,
    SourceDocument,
)
from src.domain.seeds.repository import (
    ExtractionCacheRepository,
    SeedRepository,
    SourceDocumentRepository,
)
from src.modules.seeds.prompt import PromptRenderer
from src.modules.seeds.reply import SeedsRejected, SeedValidator, parse_reply
from src.modules.seeds.seal_screen import SealScreen


class SeedExtractionRunner:
    def __init__(
        self,
        documents: SourceDocumentRepository,
        cache: ExtractionCacheRepository,
        seeds: SeedRepository,
        screen: SealScreen,
        extractor: Extractor,
        renderer: PromptRenderer,
        validator: SeedValidator,
        clock: Callable[[], str],
    ):
        self._documents = documents
        self._cache = cache
        self._seeds = seeds
        self._screen = screen
        self._extractor = extractor
        self._renderer = renderer
        self._validator = validator
        self._clock = clock

    def process(self, document_id: str) -> SourceDocument:
        """Advance one document as far as it can go. Raises
        ``ExtractorRequestRejected`` if the provider refuses the request itself:
        that is a configuration problem, not the document's."""
        document = self._documents.get(document_id)
        if document.status == SNAPSHOTTED:
            document = self._screen_document(document)
        if document.status not in (SCREENED, DELAYED):
            return document

        rendered = self._renderer.render(document.text)
        key = CacheKey(document.content_hash, rendered.version, self._extractor.model_version)
        entry = self._cache.get(key)
        if entry is None:
            try:
                reply = self._extractor.extract(
                    ExtractionRequest(prompt=rendered.text, schema=rendered.schema))
                parse_reply(reply)
            except ExtractorUnavailable as exc:
                return self._move(document, DELAYED, detail=str(exc))
            except ExtractionOutputUnreadable as exc:
                # Not cached: a truncated or blocked reply may not recur.
                return self._fail(document, OUTPUT_UNREADABLE, str(exc))
            entry = self._cache.put(ExtractionCacheEntry(
                key=key, provider=self._extractor.provider, model=self._extractor.model,
                reply_text=reply, created_at=self._clock()))

        try:
            built = self._validator.build(parse_reply(entry.reply_text), document, entry,
                                          self._clock())
        except SeedsRejected as exc:
            return self._fail(document, VALIDATION_FAILED, "; ".join(exc.problems))
        stored = {seed.id for seed in self._seeds.list_for_document(document.id)}
        if built and all(seed.id in stored for seed in built):
            # Seed ids are derived from the cached reply, so a document reset
            # and re-run under the same prompt and model rebuilds exactly the
            # seeds it already has. That is a no-op, not a conflict.
            return self._move(document, EXTRACTED, detail="{} seed(s) extracted; "
                              "already stored.".format(len(built)))
        self._seeds.save_all(built)
        return self._move(document, EXTRACTED,
                          detail="{} seed(s) extracted.".format(len(built)))

    def _screen_document(self, document: SourceDocument) -> SourceDocument:
        result = self._screen.screen(document.source_url, document.external_id, document.text)
        if result.blocked:
            return self._move(document, BLOCKED_SEALED, detail=result.reason)
        return self._move(document, SCREENED, detail=None)

    def _move(self, document: SourceDocument, status: str, detail) -> SourceDocument:
        return self._documents.update(
            dataclasses.replace(document, status=status, status_detail=detail),
            document.status)

    def _fail(self, document: SourceDocument, code: str, detail: str) -> SourceDocument:
        return self._documents.update(
            dataclasses.replace(document, status=FAILED, failure_code=code, status_detail=detail),
            document.status)
