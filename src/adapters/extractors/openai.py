"""OpenAI extractor over the REST API (Chat Completions, Structured Outputs).

The reply schema is enforced by OpenAI itself (``json_schema``, ``strict``), so
a reply that parses is already the right shape. The adapter stamps its own
identity (D-20), and ``model_version`` should be a dated snapshot, since it is
part of the cache key.

Temperature is sent only when configured. Some OpenAI model families accept no
temperature other than their default and reject the request otherwise; for
those the config sets ``null``. Seeds stay identical across the team because
replies are cached (D-26), not because of the temperature.
"""

from __future__ import annotations

from typing import Optional

from src.adapters.extractors.json_schema import to_json_schema
from src.adapters.http import HttpClient, HttpRejected, HttpUnavailable
from src.domain.seeds.extraction import (
    ExtractionOutputUnreadable,
    ExtractionRequest,
    ExtractorRequestRejected,
    ExtractorUnavailable,
)

ENDPOINT = "https://api.openai.com/v1/chat/completions"


class OpenAIExtractor:
    provider = "openai"

    def __init__(self, http: HttpClient, api_key: str, model: str, model_version: str,
                 temperature: Optional[float] = 0):
        if not api_key:
            raise ExtractorRequestRejected("No OpenAI API key configured.")
        self._http = http
        self._api_key = api_key
        self._temperature = temperature
        self.model = model
        self.model_version = model_version

    def extract(self, request: ExtractionRequest) -> str:
        body = {
            "model": self.model_version,
            "messages": [{"role": "user", "content": request.prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "seed_extraction", "strict": True,
                                "schema": to_json_schema(request.schema, strict=True)},
            },
        }
        if self._temperature is not None:
            body["temperature"] = self._temperature
        try:
            reply = self._http.post_json(
                ENDPOINT, body, headers={"Authorization": "Bearer " + self._api_key})
        except HttpUnavailable as exc:
            raise ExtractorUnavailable("OpenAI unavailable: {}".format(exc))
        except HttpRejected as exc:
            raise ExtractorRequestRejected("OpenAI rejected the request: {}".format(exc))

        choices = reply.get("choices") or []
        if not choices:
            raise ExtractionOutputUnreadable("OpenAI returned no choices.")
        choice = choices[0]
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise ExtractionOutputUnreadable("OpenAI refused to answer.")
        finish = choice.get("finish_reason")
        if finish not in (None, "stop"):
            raise ExtractionOutputUnreadable("OpenAI stopped early: {}.".format(finish))
        text = message.get("content") or ""
        if not text.strip():
            raise ExtractionOutputUnreadable("OpenAI returned an empty reply.")
        return text
