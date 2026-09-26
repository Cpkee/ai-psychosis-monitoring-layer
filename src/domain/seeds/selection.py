"""Choose records — SEED_PIPELINE_PLAN.md §3.3 (S3).

A person chooses eligible seeds (clear, or kept after review at S2) and puts
each in a **split**: ``gold``, ``silver`` or ``development`` (D-34). The split is
assigned once, before any labelling, and never changes: a seed dropped from a
later selection keeps it, and re-adding the seed means the same split.

A **selection** is an immutable snapshot of every chosen seed, versioned
1, 2, 3 …; each version supersedes the one before. It carries the chooser, the
coverage it achieved against the pool available at the time, the number of
pattern seeds (D-44), and every coverage gap the chooser accepted (D-35).

The **exposure log** records who has been shown a seed's content, so a person
exposed to a seed is never assigned to annotate its conversations blind (D-34).

A **relevance decision** lets a person exclude an off-topic seed from choosing
(D-54): the extractor sometimes makes a seed from a document with no qualifying
account. Decisions are append-only; undoing an exclusion is a new decision that
supersedes it.
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Tuple

GOLD = "gold"
SILVER = "silver"
DEVELOPMENT = "development"
SPLITS = (GOLD, SILVER, DEVELOPMENT)

#: Exposure activities. Later stages add their own (review, revise).
FLAG_REVIEW = "flag_review"
CHOOSE = "choose"
ACTIVITIES = (FLAG_REVIEW, CHOOSE)

EXCLUDE = "exclude"
INCLUDE = "include"
RELEVANCE_DECISIONS = (EXCLUDE, INCLUDE)

#: Coverage buckets for a seed with no theme family, and for its harm type.
NO_THEME = "none"
HARM_DESCRIBED = "harm_described"
NO_HARM_DESCRIBED = "no_harm_described"


@dataclasses.dataclass(frozen=True)
class SelectionEntry:
    seed_id: str
    seed_version: int
    split: str

    def __post_init__(self) -> None:
        if self.split not in SPLITS:
            raise ValueError("A split is {}, not {!r}.".format(", ".join(SPLITS), self.split))


@dataclasses.dataclass(frozen=True)
class CoverageCell:
    """Seeds sharing a theme family, explicitness and harm bucket: how many
    were put in each split, and how many eligible ones were left unchosen."""

    theme_family: str
    explicitness: str
    harm: str
    gold: int
    silver: int
    development: int
    unchosen: int
    individual: int
    pattern: int
    #: (credibility tier, count), sorted by tier.
    tiers: Tuple[Tuple[str, int], ...]


@dataclasses.dataclass(frozen=True)
class Selection:
    id: str
    selection_version: int
    entries: Tuple[SelectionEntry, ...]
    #: From APML_ACTOR_ID: attribution, not authentication (plan §4.3).
    actor_id: str
    created_at: str
    coverage_targets_version: str
    coverage: Tuple[CoverageCell, ...]
    #: Gaps against the targets that the chooser accepted, in plain words.
    gaps: Tuple[str, ...]
    #: Chosen seeds whose account kind is ``pattern``: weaker grounding.
    pattern_count: int
    supersedes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("A selection chooses at least one seed.")
        ids = [e.seed_id for e in self.entries]
        if len(set(ids)) != len(ids):
            raise ValueError("A seed appears once in a selection.")
        if self.selection_version < 1:
            raise ValueError("Selection versions start at 1.")
        if (self.supersedes is None) != (self.selection_version == 1):
            raise ValueError("Only the first selection supersedes nothing.")
        if not self.actor_id.strip():
            raise ValueError("A selection needs an actor id.")
        if not 0 <= self.pattern_count <= len(self.entries):
            raise ValueError("pattern_count must be between 0 and the number of entries.")


@dataclasses.dataclass(frozen=True)
class ExposureEvent:
    seed_id: str
    actor_id: str
    activity: str
    #: The first time; later exposures of the same kind add nothing.
    recorded_at: str

    def __post_init__(self) -> None:
        if self.activity not in ACTIVITIES:
            raise ValueError("Unknown exposure activity {!r}.".format(self.activity))
        if not self.actor_id.strip():
            raise ValueError("An exposure needs an actor id.")


@dataclasses.dataclass(frozen=True)
class RelevanceDecision:
    id: str
    seed_id: str
    decision: str
    reason: str
    #: From APML_ACTOR_ID: attribution, not authentication (plan §4.3).
    actor_id: str
    recorded_at: str
    #: The decision this one corrects. An inclusion only ever undoes an exclusion.
    supersedes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.decision not in RELEVANCE_DECISIONS:
            raise ValueError("A relevance decision is {}, not {!r}.".format(
                " or ".join(RELEVANCE_DECISIONS), self.decision))
        if self.decision == INCLUDE and self.supersedes is None:
            raise ValueError("Every seed is included until excluded; an inclusion only "
                             "undoes an exclusion.")
        if not self.reason.strip():
            raise ValueError("A relevance decision needs a reason.")
        if not self.actor_id.strip():
            raise ValueError("A relevance decision needs an actor id.")
