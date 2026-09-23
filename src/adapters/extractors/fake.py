"""Deterministic fake extractor — tests only.

Returns exactly what the test tells it to and records every request, so tests
can prove when the extractor was, and was not, called. It contains no
extraction logic: a fake that decided seeds would be a second, untested
extractor.
"""

from __future__ import annotations

from typing import Callable, List, Union

from src.domain.seeds.extraction import ExtractionRequest

Responder = Callable[[ExtractionRequest], str]


class FakeExtractor:
    provider = "fake"
    model = "deterministic"

    def __init__(self, reply: Union[str, Responder], model_version: str = "fake_v0.1"):
        self._reply = reply
        self.model_version = model_version
        self.requests: List[ExtractionRequest] = []

    def extract(self, request: ExtractionRequest) -> str:
        self.requests.append(request)
        return self._reply(request) if callable(self._reply) else self._reply
