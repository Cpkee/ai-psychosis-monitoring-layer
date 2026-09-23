"""Assessment records — architecture.md section 7.2.

Three tables, one aggregate: you never load evidence without its assessment,
so they are saved and fetched together.

The rule that matters most lives here: a score that could not be determined is
``None`` with ``not_assessable``. It is never ``0``. "No evidence" and
"evidence of absence" are different findings, and collapsing them would make
the system report "nothing concerning" when the truth was "we could not tell".
"""

from __future__ import annotations

import dataclasses
from typing import List, Optional, Tuple


@dataclasses.dataclass(frozen=True)
class SignalScore:
    id: str
    assessment_id: str
    signal_code: str
    score_value: Optional[int]
    scale_version: str
    uncertain: bool = False
    not_assessable: bool = False
    #: ``harm_intent`` only. Movement here at a constant numeric level is
    #: escalation (taxonomy §6.4) and is the pattern the alert rule treats as
    #: most serious.
    specificity_markers: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (self.score_value is None) != self.not_assessable:
            raise ValueError(
                "score_value is None if and only if not_assessable is true; "
                "{!r} has score_value={!r} and not_assessable={!r}.".format(
                    self.signal_code, self.score_value, self.not_assessable
                )
            )


@dataclasses.dataclass(frozen=True)
class EvidenceReference:
    """A turn cited in support of a score.

    Section 7.2: *"Store turn references as the authority. Any excerpt is a
    convenience copy and must be traceable to the turn."*
    """

    assessment_id: str
    turn_id: str
    signal_code: Optional[str] = None
    evidence_excerpt: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Assessment:
    id: str
    analysis_job_id: str
    context_category: str
    uncertainty: Optional[str]
    insufficient_evidence: bool
    explanation: str
    judge_provider: str
    judge_model: str
    judge_model_version: str
    rubric_version: str
    taxonomy_version: str
    scale_version: str
    prompt_configuration_version: str
    schema_version: str
    created_at: str
    context_confidence: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class ValidatedAssessment:
    """An assessment that has passed the Result Validator, with its parts."""

    assessment: Assessment
    scores: Tuple[SignalScore, ...]
    evidence: Tuple[EvidenceReference, ...]

    def score(self, signal_code: str) -> SignalScore:
        for score in self.scores:
            if score.signal_code == signal_code:
                return score
        raise KeyError(signal_code)

    def evidence_for(self, signal_code: str) -> List[EvidenceReference]:
        return [e for e in self.evidence if e.signal_code == signal_code]
