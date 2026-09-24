"""Filter records — SEED_PIPELINE_PLAN.md §3.2 (S2).

After extraction, every current seed is screened again against the sealed
benchmark's manifest (D-27). An **overlap check** records the result:

- ``blocked`` — a field of the seed matches a sealed prompt hash: the extractor
  reproduced a sealed prompt. Never eligible, and no person can override it.
- ``flagged`` — metadata resembles the benchmark (a harm type like a sealed
  case's, or a mention of the benchmark). Removal needs a human decision,
  because harm types such as isolation are common in legitimate sources.
- ``clear`` — neither.

A person reviews each flagged seed and records ``keep`` or ``exclude`` in a
**flag review**. Reviews are append-only: a correction is a new review that
``supersedes`` the latest one, and the original stays stored.

A check stores only reason codes, a screen version and the manifest's hash —
never sealed content, and never which sealed case matched. Re-running the same
screen against the same manifest reproduces the match.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Optional, Tuple

CLEAR = "clear"
FLAGGED = "flagged"
BLOCKED = "blocked"
RESULTS = (CLEAR, FLAGGED, BLOCKED)

#: Reason codes. A sealed-span reason names the seed field that matched,
#: for example ``sealed_span:arc_summary``.
SEALED_SPAN = "sealed_span"
HARM_TYPE_MATCH = "harm_type_matches_sealed_case"
CITES_BENCHMARK = "mentions_sealed_benchmark"

KEEP = "keep"
EXCLUDE = "exclude"
DECISIONS = (KEEP, EXCLUDE)

#: Where a seed stands after S2. Only CLEAR and KEPT seeds may be chosen at S3.
UNSCREENED = "unscreened"
AWAITING_REVIEW = "awaiting_review"
KEPT = "kept"
EXCLUDED = "excluded"
ELIGIBLE_FOR_CHOOSE = frozenset({CLEAR, KEPT})

_SHA256 = re.compile(r"[0-9a-f]{64}")


def is_sealed_span(reason: str) -> bool:
    return reason.split(":", 1)[0] == SEALED_SPAN


@dataclasses.dataclass(frozen=True)
class OverlapCheck:
    id: str
    seed_id: str
    result: str
    reasons: Tuple[str, ...]
    #: Config version and a fingerprint of its settings: an edit without a
    #: rename still changes it (as D-40c for prompts).
    screen_version: str
    #: SHA-256 of the manifest file the screen read.
    manifest_sha256: str
    checked_at: str

    def __post_init__(self) -> None:
        if self.result not in RESULTS:
            raise ValueError("Unknown overlap result {!r}.".format(self.result))
        if (self.result == CLEAR) != (not self.reasons):
            raise ValueError("A check is clear if and only if it has no reasons.")
        if (self.result == BLOCKED) != any(is_sealed_span(r) for r in self.reasons):
            raise ValueError("A check is blocked if and only if a sealed span matched.")
        if not _SHA256.fullmatch(self.manifest_sha256):
            raise ValueError("manifest_sha256 must be a lower-case SHA-256 hex digest.")


@dataclasses.dataclass(frozen=True)
class FlagReview:
    id: str
    overlap_check_id: str
    decision: str
    reason: str
    #: From APML_ACTOR_ID: attribution, not authentication (plan §4.3).
    actor_id: str
    recorded_at: str
    #: The review this one corrects. None for the first review of a check.
    supersedes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.decision not in DECISIONS:
            raise ValueError("A decision is {}, not {!r}.".format(
                " or ".join(DECISIONS), self.decision))
        if not self.reason.strip():
            raise ValueError("A review needs a reason.")
        if not self.actor_id.strip():
            raise ValueError("A review needs an actor id.")


def filter_status(check: Optional[OverlapCheck], review: Optional[FlagReview]) -> str:
    """Where a seed stands, from its check under the current screen and the
    latest review of that check."""
    if check is None:
        return UNSCREENED
    if check.result != FLAGGED:
        return check.result
    if review is None:
        return AWAITING_REVIEW
    return KEPT if review.decision == KEEP else EXCLUDED
