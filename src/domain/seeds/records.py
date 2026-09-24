"""Seed pipeline records — SEED_PIPELINE_PLAN.md §3.1 (Collect).

A **source document** is a snapshot of a published account (DS-14). A **seed**
is the set of scenario parameters extracted from it (DS-15). Neither is a label
and neither says anything about any person's condition: a seed's theme, phase
progression and harm type are generation parameters (contracts §8.3).

A document moves through a small state machine, saved after every step, so a
run can stop at any point (interruption, rate limit) and resume:

    SNAPSHOTTED -> SCREENED -> EXTRACTED
         |            |
         |            +-> DELAYED (extractor unreachable; retried later)
         |            +-> FAILED  (OUTPUT_UNREADABLE | VALIDATION_FAILED)
         +-> BLOCKED_SEALED (Psychosis-Bench screen; never sent to any model)

As with analysis jobs (D-13), DELAYED and FAILED stay strictly apart.

**Current seeds (D-45).** A document records the prompt and model version it
was last processed under. Its *current* seeds are those from that extraction;
seeds from earlier extractions stay stored, unchanged, as history. Re-extracting
under a new prompt or model therefore supersedes old seeds without editing or
deleting any, and switching back makes the earlier ones current again.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Optional, Tuple

SNAPSHOTTED = "SNAPSHOTTED"
SCREENED = "SCREENED"
EXTRACTED = "EXTRACTED"
BLOCKED_SEALED = "BLOCKED_SEALED"
DELAYED = "DELAYED"
FAILED = "FAILED"

STATUSES = (SNAPSHOTTED, SCREENED, EXTRACTED, BLOCKED_SEALED, DELAYED, FAILED)
#: Nothing further happens to a document in one of these states.
TERMINAL = frozenset({EXTRACTED, BLOCKED_SEALED, FAILED})

OUTPUT_UNREADABLE = "OUTPUT_UNREADABLE"
VALIDATION_FAILED = "VALIDATION_FAILED"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class QueryLogEntry:
    """One search, exactly as run. Append-only: a later reader can see what an
    earlier run saw, even after the source's index has changed."""

    id: str
    source: str
    query_id: str
    query_text: str
    query_config_version: str
    executed_at: str
    result_ids: Tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class SourceDocument:
    id: str
    content_hash: str
    source_type: str
    source_url: str
    title: str
    text: str
    retrieved_at: str
    fetcher_version: str
    external_id: Optional[str] = None
    publication_date: Optional[str] = None
    query_log_id: Optional[str] = None
    status: str = SNAPSHOTTED
    failure_code: Optional[str] = None
    #: Our own messages only, never provider output (as D-11).
    status_detail: Optional[str] = None
    #: The extraction whose seeds are current: set when the document is
    #: EXTRACTED or FAILED, kept while a re-extraction is under way.
    processed_prompt_version: Optional[str] = None
    processed_model_version: Optional[str] = None

    def __post_init__(self) -> None:
        if content_hash(self.text) != self.content_hash:
            raise ValueError(
                "content_hash does not match the text: a snapshot is identified "
                "by exactly what it contains."
            )
        if self.status not in STATUSES:
            raise ValueError("Unknown document status {!r}.".format(self.status))
        if (self.status == FAILED) != (self.failure_code is not None):
            raise ValueError("A failure code is required if and only if the document FAILED.")


@dataclasses.dataclass(frozen=True)
class CacheKey:
    """Everything that determines an extractor's reply to a document."""

    content_hash: str
    prompt_version: str
    model_version: str


@dataclasses.dataclass(frozen=True)
class ExtractionCacheEntry:
    """An extractor reply, stored once and reused by every team member.

    The cache, not temperature 0, is what makes seeds identical across the
    team: a hosted model at temperature 0 is not guaranteed deterministic.
    """

    key: CacheKey
    provider: str
    model: str
    reply_text: str
    created_at: str


@dataclasses.dataclass(frozen=True)
class Seed:
    id: str
    seed_version: int
    source_document_id: str
    content_hash: str
    source_url: str
    source_type: str
    credibility_tier: str
    retrieved_at: str
    #: "individual" (one person's documented interaction) or "pattern" (a course
    #: the document describes across users). Pattern seeds are weaker evidence
    #: and are chosen deliberately at S3 (D-44).
    account_kind: str
    #: Vocabulary A code, or None when the account fits no project family.
    theme_family: Optional[str]
    #: The source's own words for the theme, verbatim.
    raw_theme_terms: Tuple[str, ...]
    arc_summary: str
    reported_phase_progression: Tuple[str, ...]
    explicitness_candidate: str
    harm_type_candidate: Optional[str]
    companion_behaviour_reported: Tuple[str, ...]
    extraction_provider: str
    extraction_model: str
    extraction_model_version: str
    extraction_prompt_version: str
    vocabulary_version: str
    credibility_tier_version: str
    created_at: str
    publication_date: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.arc_summary.strip():
            raise ValueError("A seed needs an arc summary.")


def current_seeds(document: SourceDocument, seeds: Tuple[Seed, ...]) -> Tuple[Seed, ...]:
    """The seeds from the document's current extraction (D-45)."""
    current = (document.processed_prompt_version, document.processed_model_version)
    return tuple(
        seed for seed in seeds
        if (seed.extraction_prompt_version, seed.extraction_model_version) == current
    )
