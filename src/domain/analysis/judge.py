"""Judge seam — architecture.md section 6.6.

One interface, several implementations:

* ``DeterministicFakeJudgeAdapter`` — tests only, available now.
* ``LLMJudgeAdapter`` — the MVP scorer, once a provider is chosen ([OD-013]).
* ``TransformerJudgeAdapter`` — future, after an approved training process.

The seam is justified because these vary while returning the same domain
result. **Hidden chain-of-thought is neither requested nor stored**, so
``RawJudgeResult`` has no field to carry it.
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Protocol, Tuple

from src.domain.conversations.records import Turn


@dataclasses.dataclass(frozen=True)
class JudgeRequest:
    """Everything a judge is given, and nothing it is not.

    Deliberately absent: the companion condition, the scenario's intended
    phase, and the simulator's hidden state. Passing any of them would let the
    judge score the experiment rather than the conversation.
    """

    session_id: str
    through_turn_id: str
    window: Tuple[Turn, ...]
    taxonomy_version: str
    scale_version: str
    rubric_version: str
    rubric_instructions: str
    prompt_configuration_version: str
    schema_version: str
    judge_configuration_version: str

    @property
    def window_turn_ids(self) -> frozenset:
        return frozenset(turn.id for turn in self.window)


@dataclasses.dataclass(frozen=True)
class RawSignalScore:
    """One score as the judge reported it, before validation."""

    signal_code: str
    score_value: Optional[int]
    evidence_turn_ids: Tuple[str, ...] = ()
    explanation: Optional[str] = None
    uncertain: bool = False
    not_assessable: bool = False
    #: Only ``harm_intent`` carries these. They let the trajectory engine see
    #: escalation when the numeric level has not moved.
    specificity_markers: Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class RawJudgeResult:
    """A judge's output, before validation. Nothing here is trusted yet."""

    context_category: str
    scores: Tuple[RawSignalScore, ...]
    explanation: str
    judge_provider: str
    judge_model: str
    judge_model_version: str
    context_confidence: Optional[str] = None
    uncertainty: Optional[str] = None
    insufficient_evidence: bool = False


class JudgeAdapter(Protocol):
    def assess(self, request: JudgeRequest) -> RawJudgeResult:
        """Score the exchange described by ``request``."""


class JudgeUnavailable(RuntimeError):
    """The judge could not be reached or timed out. Retryable."""


class JudgeOutputUnreadable(ValueError):
    """The reply could not be turned into a :class:`RawJudgeResult` at all.

    Distinct from both other failure modes, and the distinction matters for
    diagnosis:

    * :class:`JudgeUnavailable` — the judge could not be reached. Retryable.
    * :class:`JudgeOutputUnreadable` — it answered, and the answer is not a
      result: truncated, refused, or not the expected shape. Not retryable
      without a change.
    * ``AssessmentRejected`` — it answered with a well-formed result that
      breaks the contract. The validator's business, not the adapter's.
    """
