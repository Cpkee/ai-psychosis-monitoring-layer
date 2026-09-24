"""S2 Filter — screens extracted seeds and records human decisions on flags.

The caller owns the transaction and calls :meth:`SeedFilter.screen_document`
once per document, so an interrupted run resumes where it stopped. Screening
is idempotent: a seed already checked under the current screen and manifest is
not checked again. A new screen version or manifest re-screens every seed, and
a flag raised under it needs a fresh human decision.

Only a document's *current* seeds (D-45) are screened; superseded seeds are
history and can never be chosen.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Optional, Tuple

from src.domain.seeds.overlap import (
    ELIGIBLE_FOR_CHOOSE,
    FLAGGED,
    FlagReview,
    OverlapCheck,
    filter_status,
)
from src.domain.seeds.records import EXTRACTED, Seed, SourceDocument, current_seeds
from src.domain.seeds.repository import (
    SeedFilterRepository,
    SeedRepository,
    SourceDocumentRepository,
)
from src.modules.seeds.overlap_screen import OverlapScreen


class UnknownSeed(LookupError):
    """Not a current seed of an extracted document."""


class NotAwaitingReview(ValueError):
    """The seed is unscreened, clear or blocked: only a flag can be reviewed."""


class AlreadyReviewed(ValueError):
    """The flag has a decision; changing it must be asked for as a correction."""


class NothingToCorrect(ValueError):
    """A correction was asked for, but the flag has no decision yet."""


@dataclasses.dataclass(frozen=True)
class ScreenedSeed:
    seed: Seed
    document: SourceDocument
    check: Optional[OverlapCheck]
    review: Optional[FlagReview]

    @property
    def status(self) -> str:
        return filter_status(self.check, self.review)

    @property
    def eligible(self) -> bool:
        return self.status in ELIGIBLE_FOR_CHOOSE


class SeedFilter:
    def __init__(
        self,
        documents: SourceDocumentRepository,
        seeds: SeedRepository,
        checks: SeedFilterRepository,
        screen: OverlapScreen,
        clock: Callable[[], str],
        new_id: Callable[[], str],
    ):
        self._documents = documents
        self._seeds = seeds
        self._checks = checks
        self._screen = screen
        self._clock = clock
        self._new_id = new_id

    def screen_document(self, document_id: str) -> Tuple[OverlapCheck, ...]:
        """Check each current seed of an extracted document; returns the checks,
        new or already stored. A document not EXTRACTED has nothing to screen."""
        document = self._documents.get(document_id)
        if document.status != EXTRACTED:
            return ()
        checks = []
        for seed in self._current(document):
            found = self._screen.screen(seed, document)
            checks.append(self._checks.record_check(OverlapCheck(
                id=self._new_id(), seed_id=seed.id, result=found.result, reasons=found.reasons,
                screen_version=self._screen.version,
                manifest_sha256=self._screen.manifest_sha256, checked_at=self._clock())))
        return tuple(checks)

    def seeds(self) -> Tuple[ScreenedSeed, ...]:
        """Every current seed of every extracted document, with its check under
        the current screen and the latest review of that check."""
        checks = {c.seed_id: c for c in self._checks.list_checks(
            self._screen.version, self._screen.manifest_sha256)}
        found = []
        for document in self._documents.list_by_status(EXTRACTED):
            for seed in self._current(document):
                check = checks.get(seed.id)
                review = (self._checks.latest_review(check.id)
                          if check is not None and check.result == FLAGGED else None)
                found.append(ScreenedSeed(seed, document, check, review))
        return tuple(found)

    def review(self, seed_id: str, decision: str, reason: str, actor_id: str,
               correct: bool = False) -> FlagReview:
        """Record keep or exclude on a flagged seed. Changing an earlier
        decision needs ``correct=True`` and supersedes it; the original stays."""
        screened = next((s for s in self.seeds() if s.seed.id == seed_id), None)
        if screened is None:
            raise UnknownSeed("{!r} is not a current seed of an extracted document.".format(
                seed_id))
        if screened.check is None or screened.check.result != FLAGGED:
            raise NotAwaitingReview("Seed {!r} is {}; only flagged seeds are reviewed.".format(
                seed_id, screened.status))
        latest = screened.review
        if latest is not None and not correct:
            raise AlreadyReviewed("Seed {!r} was already marked {} by {}; ask for a "
                                  "correction to change it.".format(
                                      seed_id, latest.decision, latest.actor_id))
        if latest is None and correct:
            raise NothingToCorrect("Seed {!r} has no decision to correct.".format(seed_id))
        return self._checks.save_review(FlagReview(
            id=self._new_id(), overlap_check_id=screened.check.id, decision=decision,
            reason=reason, actor_id=actor_id, recorded_at=self._clock(),
            supersedes=latest.id if latest is not None else None))

    def _current(self, document: SourceDocument) -> Tuple[Seed, ...]:
        return current_seeds(document, self._seeds.list_for_document(document.id))
