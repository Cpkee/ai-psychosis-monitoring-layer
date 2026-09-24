"""Seed extraction runner — screens, extracts and validates one document.

The caller owns the transaction and calls :meth:`process` once per document, so
every step is saved as it happens and an interrupted run resumes where it
stopped (D-26). The seal screen always runs first: the extractor is never
called for a document that has not been screened clear (D-27).

:meth:`reextract` re-runs a finished document under the current prompt and
model (D-45). Nothing is deleted or edited: new seeds are added, and the
document records which extraction is current.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Optional, Tuple

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


#: Only these can be re-extracted: a document still in progress is picked up by
#: ``extract``, and a BLOCKED_SEALED document must never reach an extractor.
REEXTRACTABLE = (EXTRACTED, FAILED)


class NotReextractable(ValueError):
    """The document is not finished, or was blocked by the seal screen."""


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

    @property
    def current_extraction(self) -> Tuple[str, str]:
        """The (prompt version, model version) a document would be processed under now."""
        return (self._renderer.version, self._extractor.model_version)

    def is_stale(self, document: SourceDocument) -> bool:
        """Finished under a different prompt or model than the current one. A
        document processed before versions were recorded counts as stale."""
        processed = (document.processed_prompt_version, document.processed_model_version)
        return document.status in REEXTRACTABLE and processed != self.current_extraction

    def reextract(self, document_id: str) -> SourceDocument:
        """Send a finished document back through extraction. The seal screen is
        not re-run (the text is unchanged). Until the new extraction finishes,
        the previous one stays current, so an interrupted run loses nothing."""
        document = self._documents.get(document_id)
        if document.status not in REEXTRACTABLE:
            raise NotReextractable("Document {!r} is {}; only {} documents can be "
                                   "re-extracted.".format(document_id, document.status,
                                                          " or ".join(REEXTRACTABLE)))
        self._documents.update(
            dataclasses.replace(document, status=SCREENED, failure_code=None,
                                status_detail="Re-extraction requested."),
            document.status)
        return self.process(document_id)

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
                return self._fail(document, OUTPUT_UNREADABLE, str(exc), key)
            entry = self._cache.put(ExtractionCacheEntry(
                key=key, provider=self._extractor.provider, model=self._extractor.model,
                reply_text=reply, created_at=self._clock()))

        try:
            built = self._validator.build(parse_reply(entry.reply_text), document, entry,
                                          self._clock())
        except SeedsRejected as exc:
            return self._fail(document, VALIDATION_FAILED, "; ".join(exc.problems), key)
        stored = {seed.id for seed in self._seeds.list_for_document(document.id)}
        if built and all(seed.id in stored for seed in built):
            # Seed ids are derived from the cached reply, so re-running under a
            # prompt and model already used rebuilds seeds that are stored: a
            # no-op, not a conflict. Recording the key makes them current again.
            return self._move(document, EXTRACTED, detail="{} seed(s) extracted; "
                              "already stored.".format(len(built)), key=key)
        self._seeds.save_all(built)
        return self._move(document, EXTRACTED,
                          detail="{} seed(s) extracted.".format(len(built)), key=key)

    def _screen_document(self, document: SourceDocument) -> SourceDocument:
        result = self._screen.screen(document.source_url, document.external_id, document.text)
        if result.blocked:
            return self._move(document, BLOCKED_SEALED, detail=result.reason)
        return self._move(document, SCREENED, detail=None)

    def _move(self, document: SourceDocument, status: str, detail,
              key: Optional[CacheKey] = None) -> SourceDocument:
        return self._documents.update(
            dataclasses.replace(document, status=status, status_detail=detail,
                                **self._processed(key)),
            document.status)

    def _fail(self, document: SourceDocument, code: str, detail: str,
              key: CacheKey) -> SourceDocument:
        return self._documents.update(
            dataclasses.replace(document, status=FAILED, failure_code=code, status_detail=detail,
                                **self._processed(key)),
            document.status)

    @staticmethod
    def _processed(key: Optional[CacheKey]):
        """Record the extraction a document finished under. Without a key (screening,
        a delay) the previous extraction, if any, stays current."""
        if key is None:
            return {}
        return {"processed_prompt_version": key.prompt_version,
                "processed_model_version": key.model_version}
