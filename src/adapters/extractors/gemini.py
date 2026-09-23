"""Gemini extractor over the REST API (``generateContent``).

Temperature 0, JSON output enforced by ``responseSchema``, and an exact
``model_version`` that is part of the cache key. The adapter stamps its own
identity (D-20). A rejected request carries Google's short error message,
because it stops the run and is never stored; retryable errors carry only our
own description, because those are stored on DELAYED documents.

Model choice: ``gemini-2.5-flash`` still appears in the model list but is
"no longer available to new users" (404), so v0.1 uses ``gemini-3.6-flash``.

Free-tier inputs may be used by the provider (OD-026). Only DS-14 snapshots of
already-published documents are sent, and only after the seal screen.
"""

from __future__ import annotations

from src.adapters.http import HttpClient, HttpRejected, HttpUnavailable
from src.domain.seeds.extraction import (
    ExtractionOutputUnreadable,
    ExtractionRequest,
    ExtractorRequestRejected,
    ExtractorUnavailable,
)

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


class GeminiExtractor:
    provider = "gemini"

    def __init__(self, http: HttpClient, api_key: str, model: str, model_version: str):
        if not api_key:
            raise ExtractorRequestRejected("No Gemini API key configured.")
        self._http = http
        self._api_key = api_key
        self.model = model
        self.model_version = model_version

    def extract(self, request: ExtractionRequest) -> str:
        body = {
            "contents": [{"role": "user", "parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": request.schema,
            },
        }
        try:
            reply = self._http.post_json(ENDPOINT.format(self.model_version), body,
                                         headers={"x-goog-api-key": self._api_key})
        except HttpUnavailable as exc:
            raise ExtractorUnavailable("Gemini unavailable: {}".format(exc))
        except HttpRejected as exc:
            raise ExtractorRequestRejected("Gemini rejected the request: {}".format(exc))

        candidates = reply.get("candidates") or []
        if not candidates:
            reason = (reply.get("promptFeedback") or {}).get("blockReason", "none given")
            raise ExtractionOutputUnreadable("Gemini returned no candidate (block reason: {}).".format(reason))
        finish = candidates[0].get("finishReason")
        if finish not in (None, "STOP"):
            raise ExtractionOutputUnreadable("Gemini stopped early: {}.".format(finish))
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
        if not text.strip():
            raise ExtractionOutputUnreadable("Gemini returned an empty reply.")
        return text
