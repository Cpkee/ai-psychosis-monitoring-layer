"""S3 Choose — a person picks eligible seeds and puts each in a split.

Only seeds S2 made eligible (clear, or kept after review) can be chosen, and
only a document's current seeds (D-45). A new selection starts from the
current one, adds and drops seeds, and is refused while:

- a seed would change split (D-34: a split is assigned once, for ever);
- the current selection holds a seed that is no longer eligible, until the
  chooser drops it explicitly;
- the result misses a coverage target, until the chooser accepts the gaps.
  Accepted gaps are written into the selection (D-35).

A person can also exclude an off-topic seed, which removes it from the
candidates until the exclusion is undone (D-54).

Showing a seed's content to a person, letting them choose it, or letting them
exclude it records an exposure (D-34). The caller owns the transaction.
"""

from __future__ import annotations

import collections
import dataclasses
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from src.domain.seeds.records import Seed
from src.domain.seeds.repository import (
    SeedExposureRepository,
    SeedRelevanceRepository,
    SeedSelectionRepository,
)
from src.domain.seeds.selection import (
    CHOOSE,
    DEVELOPMENT,
    EXCLUDE,
    GOLD,
    HARM_DESCRIBED,
    INCLUDE,
    NO_HARM_DESCRIBED,
    NO_THEME,
    SILVER,
    CoverageCell,
    ExposureEvent,
    RelevanceDecision,
    Selection,
    SelectionEntry,
)
from src.modules.seeds.config import CoverageTargets
from src.modules.seeds.filter import ScreenedSeed, SeedFilter


class ChoiceRefused(ValueError):
    """The requested selection cannot be made; the message says why."""


class SplitAlreadyAssigned(ChoiceRefused):
    """The seed already holds another split, which never changes (D-34)."""


class GapsNotAccepted(ChoiceRefused):
    def __init__(self, gaps: Tuple[str, ...]):
        super().__init__("The selection misses {} coverage target(s); accept the gaps "
                         "to record them on the selection.".format(len(gaps)))
        self.gaps = gaps


@dataclasses.dataclass(frozen=True)
class Candidate:
    """An eligible seed, as a chooser sees it."""

    screened: ScreenedSeed
    #: The split this seed was given in any earlier selection, if any.
    split: Optional[str]
    in_current_selection: bool
    #: Everyone already exposed to this seed, by actor id.
    seen_by: Tuple[str, ...]

    @property
    def seed(self) -> Seed:
        return self.screened.seed


@dataclasses.dataclass(frozen=True)
class Assessment:
    """What a set of chosen seeds achieves against the targets."""

    entries: Tuple[SelectionEntry, ...]
    coverage: Tuple[CoverageCell, ...]
    gaps: Tuple[str, ...]
    pattern_count: int
    #: The selection this one would supersede.
    previous: Optional[Selection]


def harm_bucket(seed: Seed) -> str:
    return HARM_DESCRIBED if seed.harm_type_candidate else NO_HARM_DESCRIBED


def coverage(chosen: Sequence[Tuple[Seed, str]],
             unchosen: Sequence[Seed]) -> Tuple[CoverageCell, ...]:
    """The matrix: theme family × explicitness × harm, with seeds per split,
    eligible seeds left unchosen, and account kinds and tiers of chosen ones."""
    def key(seed: Seed):
        return (seed.theme_family or NO_THEME, seed.explicitness_candidate, harm_bucket(seed))

    cells: Dict[tuple, Dict[str, object]] = collections.defaultdict(
        lambda: {GOLD: 0, SILVER: 0, DEVELOPMENT: 0, "unchosen": 0, "individual": 0,
                 "pattern": 0, "tiers": collections.Counter()})
    for seed, split in chosen:
        cell = cells[key(seed)]
        cell[split] += 1
        cell["pattern" if seed.account_kind == "pattern" else "individual"] += 1
        cell["tiers"][seed.credibility_tier] += 1
    for seed in unchosen:
        cells[key(seed)]["unchosen"] += 1
    return tuple(
        CoverageCell(theme_family=k[0], explicitness=k[1], harm=k[2], gold=c[GOLD],
                     silver=c[SILVER], development=c[DEVELOPMENT], unchosen=c["unchosen"],
                     individual=c["individual"], pattern=c["pattern"],
                     tiers=tuple(sorted(c["tiers"].items())))
        for k, c in sorted(cells.items()))


def find_gaps(chosen: Sequence[Tuple[Seed, str]], targets: CoverageTargets) -> Tuple[str, ...]:
    """Every target the chosen seeds miss, in plain words, in a fixed order."""
    gaps: List[str] = []

    def minimums(label: str, wanted: Mapping[str, int], value: Callable[[Seed], str]) -> None:
        for bucket, minimum in sorted(wanted.items()):
            found = sum(1 for seed, _ in chosen if value(seed) == bucket)
            if found < minimum:
                gaps.append("{} {}: {} chosen, target at least {}".format(
                    label, bucket, found, minimum))

    minimums("theme family", targets.min_per_theme_family, lambda s: s.theme_family)
    minimums("explicitness", targets.min_per_explicitness, lambda s: s.explicitness_candidate)
    minimums("harm", targets.min_per_harm, harm_bucket)
    patterns = sum(1 for seed, _ in chosen if seed.account_kind == "pattern")
    if chosen and patterns / len(chosen) > targets.max_pattern_share:
        gaps.append("pattern seeds: {} of {}, target at most {:.0%}".format(
            patterns, len(chosen), targets.max_pattern_share))
    for split in targets.every_theme_family_in_splits:
        for family in sorted(targets.min_per_theme_family):
            if not any(s.theme_family == family and sp == split for s, sp in chosen):
                gaps.append("{} split has no {} seed".format(split, family))
    return tuple(gaps)


class SeedChooser:
    def __init__(
        self,
        seed_filter: SeedFilter,
        selections: SeedSelectionRepository,
        exposure: SeedExposureRepository,
        relevance: SeedRelevanceRepository,
        targets: CoverageTargets,
        clock: Callable[[], str],
        new_id: Callable[[], str],
    ):
        self._filter = seed_filter
        self._selections = selections
        self._exposure = exposure
        self._relevance = relevance
        self._targets = targets
        self._clock = clock
        self._new_id = new_id

    def current(self) -> Optional[Selection]:
        return self._selections.latest()

    def candidates(self) -> Tuple[Candidate, ...]:
        """Every eligible seed, whether chosen yet or not."""
        splits = dict(self._selections.list_splits())
        current = self.current()
        chosen = {e.seed_id for e in current.entries} if current else set()
        seen: Dict[str, set] = collections.defaultdict(set)
        for event in self._exposure.list_events():
            seen[event.seed_id].add(event.actor_id)
        return tuple(
            Candidate(s, splits.get(s.seed.id), s.seed.id in chosen, tuple(sorted(seen[s.seed.id])))
            for s in self._eligible())

    def stale(self) -> Tuple[Tuple[str, str], ...]:
        """(seed id, why) for each seed in the current selection that can no
        longer be chosen. A new selection must drop them."""
        current = self.current()
        if current is None:
            return ()
        statuses = {s.seed.id: s.status for s in self._filter.seeds()}
        statuses.update({i: "excluded as off-topic" for i in self.excluded()})
        eligible = {s.seed.id for s in self._eligible()}
        return tuple(
            (e.seed_id, statuses.get(e.seed_id, "superseded by a re-extraction"))
            for e in current.entries if e.seed_id not in eligible)

    def excluded(self) -> Dict[str, RelevanceDecision]:
        """Seed id → the exclusion in force, for every seed excluded as off-topic."""
        return {d.seed_id: d for d in self._relevance.list_latest() if d.decision == EXCLUDE}

    def exclude(self, seed_id: str, reason: str, actor_id: str) -> RelevanceDecision:
        """Remove an off-topic seed from choosing. A seed already in the
        selection must then be dropped explicitly (see :meth:`stale`)."""
        self._require_current(seed_id)
        latest = {d.seed_id: d for d in self._relevance.list_latest()}.get(seed_id)
        if latest is not None and latest.decision == EXCLUDE:
            raise ChoiceRefused("Seed {!r} is already excluded.".format(seed_id))
        return self._decide(seed_id, EXCLUDE, reason, actor_id, latest)

    def undo_exclusion(self, seed_id: str, reason: str, actor_id: str) -> RelevanceDecision:
        self._require_current(seed_id)
        latest = self.excluded().get(seed_id)
        if latest is None:
            raise ChoiceRefused("Seed {!r} is not excluded.".format(seed_id))
        return self._decide(seed_id, INCLUDE, reason, actor_id, latest)

    def show(self, actor_id: str) -> Tuple[Candidate, ...]:
        """The candidates, recording that ``actor_id`` has now seen each one."""
        candidates = self.candidates()
        self._expose(actor_id, (c.seed.id for c in candidates))
        return candidates

    def assess_current(self) -> Optional[Assessment]:
        """What the current selection achieves, over its still-eligible seeds."""
        current = self.current()
        if current is None:
            return None
        return self._assess(tuple(e for e in current.entries
                                  if e.seed_id in self._eligible_ids()), current)

    def propose(self, assign: Mapping[str, str], drop: Iterable[str]) -> Assessment:
        """The selection that adding ``assign`` (seed id → split) and dropping
        ``drop`` would make. Nothing is stored."""
        drop = set(drop)
        current = self.current()
        entries = {e.seed_id: e for e in current.entries} if current else {}
        candidates = {c.seed.id: c for c in self.candidates()}
        for seed_id in sorted(drop):
            if seed_id not in entries:
                raise ChoiceRefused("Seed {!r} is not in the current selection.".format(seed_id))
            if seed_id in assign:
                raise ChoiceRefused("Seed {!r} cannot be both added and dropped.".format(seed_id))
        stale = [(i, why) for i, why in self.stale() if i not in drop]
        if stale:
            raise ChoiceRefused("The current selection holds seeds that can no longer be "
                                "chosen; drop them: {}.".format(
                                    "; ".join("{} ({})".format(i, why) for i, why in stale)))
        kept = [entries[i] for i in entries if i not in drop]
        added = []
        for seed_id, split in sorted(assign.items()):
            candidate = candidates.get(seed_id)
            if candidate is None:
                raise ChoiceRefused("Seed {!r} is not eligible: only current seeds that are "
                                    "clear, or kept after review, can be chosen.".format(seed_id))
            if candidate.split is not None and candidate.split != split:
                raise SplitAlreadyAssigned("Seed {!r} is already {}; a split never "
                                           "changes.".format(seed_id, candidate.split))
            if seed_id not in entries:
                added.append(SelectionEntry(seed_id, candidate.seed.seed_version, split))
        new = tuple(kept + added)
        if current is not None and set(new) == set(current.entries):
            raise ChoiceRefused("Nothing to change: the selection would be identical.")
        if not new:
            raise ChoiceRefused("A selection chooses at least one seed.")
        return self._assess(new, current)

    def commit(self, assessment: Assessment, actor_id: str, accept_gaps: bool) -> Selection:
        if assessment.gaps and not accept_gaps:
            raise GapsNotAccepted(assessment.gaps)
        previous = assessment.previous
        selection = self._selections.save(Selection(
            id=self._new_id(),
            selection_version=previous.selection_version + 1 if previous else 1,
            entries=assessment.entries, actor_id=actor_id, created_at=self._clock(),
            coverage_targets_version=self._targets.version, coverage=assessment.coverage,
            gaps=assessment.gaps, pattern_count=assessment.pattern_count,
            supersedes=previous.id if previous else None))
        self._expose(actor_id, (e.seed_id for e in selection.entries))
        return selection

    def _assess(self, entries: Tuple[SelectionEntry, ...],
                previous: Optional[Selection]) -> Assessment:
        seeds = {c.seed.id: c.seed for c in self.candidates()}
        chosen = [(seeds[e.seed_id], e.split) for e in entries]
        ids = {e.seed_id for e in entries}
        unchosen = [seed for seed_id, seed in seeds.items() if seed_id not in ids]
        return Assessment(
            entries=entries, coverage=coverage(chosen, unchosen),
            gaps=find_gaps(chosen, self._targets),
            pattern_count=sum(1 for seed, _ in chosen if seed.account_kind == "pattern"),
            previous=previous)

    def _eligible(self) -> Tuple[ScreenedSeed, ...]:
        """Current seeds S2 made eligible, less those excluded as off-topic."""
        excluded = self.excluded()
        return tuple(s for s in self._filter.seeds() if s.eligible and s.seed.id not in excluded)

    def _eligible_ids(self) -> set:
        return {s.seed.id for s in self._eligible()}

    def _require_current(self, seed_id: str) -> None:
        if seed_id not in {s.seed.id for s in self._filter.seeds()}:
            raise ChoiceRefused("{!r} is not a current seed of an extracted document.".format(
                seed_id))

    def _decide(self, seed_id: str, decision: str, reason: str, actor_id: str,
                latest: Optional[RelevanceDecision]) -> RelevanceDecision:
        saved = self._relevance.save(RelevanceDecision(
            id=self._new_id(), seed_id=seed_id, decision=decision, reason=reason,
            actor_id=actor_id, recorded_at=self._clock(),
            supersedes=latest.id if latest is not None else None))
        self._expose(actor_id, (seed_id,))
        return saved

    def _expose(self, actor_id: str, seed_ids: Iterable[str]) -> None:
        for seed_id in seed_ids:
            self._exposure.record(ExposureEvent(seed_id, actor_id, CHOOSE, self._clock()))
