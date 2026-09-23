"""Local Ollama extractor (``/api/generate``), the no-cost fallback to Gemini.

Nothing leaves the machine. Ollama takes standard JSON Schema, so the
OpenAPI-style ``nullable`` flags in the shared schema are converted here.
"""

from __future__ import annotations

from typing import Any, Mapping

from src.adapters.http import HttpClient, HttpRejected, HttpUnavailable
from src.domain.seeds.extraction import (
    ExtractionOutputUnreadable,
    ExtractionRequest,
    ExtractorRequestRejected,
    ExtractorUnavailable,
)


def to_json_schema(schema: Mapping[str, Any]) -> Any:
    """``{"type": "string", "nullable": true}`` -> ``{"type": ["string", "null"]}``."""
    converted = {}
    for key, value in schema.items():
        if key == "nullable":
            continue
        if isinstance(value, Mapping):
            # Covers "items" and "properties" (whose values are schemas) alike.
            converted[key] = to_json_schema(value)
        else:
            converted[key] = value
    if schema.get("nullable"):
        converted["type"] = [schema["type"], "null"]
        if "enum" in converted:
            converted["enum"] = list(converted["enum"]) + [None]
    return converted


class OllamaExtractor:
    provider = "ollama"

    def __init__(self, http: HttpClient, host: str, model: str, model_version: str):
        self._http = http
        self._host = host.rstrip("/")
        self.model = model
        self.model_version = model_version

    def extract(self, request: ExtractionRequest) -> str:
        body = {
            "model": self.model_version,
            "prompt": request.prompt,
            "format": to_json_schema(request.schema),
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            reply = self._http.post_json(self._host + "/api/generate", body)
        except HttpUnavailable as exc:
            raise ExtractorUnavailable("Ollama unavailable: {}".format(exc))
        except HttpRejected as exc:
            raise ExtractorRequestRejected("Ollama rejected the request: {}".format(exc))
        if reply.get("done_reason") == "length":
            raise ExtractionOutputUnreadable("Ollama stopped at its length limit.")
        text = reply.get("response") or ""
        if not text.strip():
            raise ExtractionOutputUnreadable("Ollama returned an empty reply.")
        return text
