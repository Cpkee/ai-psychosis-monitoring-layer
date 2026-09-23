"""The extractor seam — SEED_PIPELINE_PLAN.md §3.1, D-26.

Same shape as the judge seam. An adapter knows which provider and model it
calls and stamps that identity itself (D-20); it never takes it from the reply.
It returns the reply **text**, so the runner can cache exactly what came back.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Mapping, Protocol


@dataclasses.dataclass(frozen=True)
class ExtractionRequest:
    prompt: str
    #: JSON schema the provider is asked to enforce on its reply.
    schema: Mapping[str, Any]


class ExtractorUnavailable(RuntimeError):
    """Outage, timeout or rate limit. Retryable: the document is DELAYED."""


class ExtractorRequestRejected(RuntimeError):
    """The provider refused the request itself (bad key, bad model name,
    malformed request). Not retryable and not the document's fault, so it
    stops the run rather than failing documents one by one."""


class ExtractionOutputUnreadable(ValueError):
    """The reply is not a result at all: empty, blocked, truncated or not JSON.
    Distinct from a readable reply that breaks the seed contract."""


class Extractor(Protocol):
    provider: str
    model: str
    #: Pinned version. Part of the cache key, so it must be known before calling.
    model_version: str

    def extract(self, request: ExtractionRequest) -> str:
        """Return the raw reply text. Raises :class:`ExtractorUnavailable`,
        :class:`ExtractorRequestRejected` or :class:`ExtractionOutputUnreadable`."""
