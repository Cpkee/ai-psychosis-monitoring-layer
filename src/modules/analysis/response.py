"""Judge response parsing.

Turns a provider's decoded reply into a :class:`RawJudgeResult`, or refuses.

**This module translates; it does not judge.** It converts turn numbers back to
turn identifiers and shapes the payload, and leaves every question of whether
the content is *acceptable* to the Result Validator. A score of 7, an unknown
signal, missing evidence: all of those parse fine here and are rejected there,
with the validator's own message.

The one exception is structure. If the reply is not a mapping, or omits a key
needed to build the result at all, no amount of downstream validation helps —
that raises :class:`JudgeOutputUnreadable`.

Nothing outside the declared fields is carried forward. A provider that returns
a reasoning field has it dropped here, because architecture §6.6 requires that
hidden chain-of-thought is neither requested nor stored.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Tuple

from src.domain.analysis.judge import (
    JudgeOutputUnreadable,
    RawJudgeResult,
    RawSignalScore,
)

#: Used when the model cites a turn number that was never shown to it. The
#: validator rejects it with "evidence cites turns outside the assessed
#: window", which is a better message than anything this module could give.
UNMAPPED = "unmapped-turn-{}"


def parse_response(
    payload: Any, turn_ids_by_number: Mapping[int, str]
) -> RawJudgeResult:
    """Build a :class:`RawJudgeResult` from a decoded judge reply."""
    if not isinstance(payload, Mapping):
        raise JudgeOutputUnreadable(
            "Expected a JSON object, got {}.".format(type(payload).__name__)
        )

    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, Sequence) or isinstance(raw_scores, (str, bytes)):
        raise JudgeOutputUnreadable("'scores' is missing or is not a list.")

    scores = tuple(
        _score(entry, position, turn_ids_by_number)
        for position, entry in enumerate(raw_scores)
    )

    return RawJudgeResult(
        context_category=_text(payload, "context_category"),
        scores=scores,
        explanation=_text(payload, "explanation", default=""),
        judge_provider=_text(payload, "judge_provider", default=""),
        judge_model=_text(payload, "judge_model", default=""),
        judge_model_version=_text(payload, "judge_model_version", default=""),
        context_confidence=_optional_text(payload, "context_confidence"),
        uncertainty=_optional_text(payload, "uncertainty"),
        insufficient_evidence=bool(payload.get("insufficient_evidence", False)),
    )


def with_provider_metadata(
    result: RawJudgeResult, provider: str, model: str, model_version: str
) -> RawJudgeResult:
    """Stamp provider identity, which the model itself must never supply."""
    return RawJudgeResult(
        context_category=result.context_category,
        scores=result.scores,
        explanation=result.explanation,
        judge_provider=provider,
        judge_model=model,
        judge_model_version=model_version,
        context_confidence=result.context_confidence,
        uncertainty=result.uncertainty,
        insufficient_evidence=result.insufficient_evidence,
    )


# -- internals -----------------------------------------------------------


def _score(
    entry: Any, position: int, turn_ids_by_number: Mapping[int, str]
) -> RawSignalScore:
    if not isinstance(entry, Mapping):
        raise JudgeOutputUnreadable(
            "scores[{}] is not an object.".format(position)
        )
    code = entry.get("signal_code")
    if not isinstance(code, str) or not code.strip():
        raise JudgeOutputUnreadable(
            "scores[{}] has no usable signal_code.".format(position)
        )

    value = entry.get("score", entry.get("score_value"))
    if value is not None and not isinstance(value, int) or isinstance(value, bool):
        raise JudgeOutputUnreadable(
            "{}: score must be a whole number or null, got {!r}.".format(code, value)
        )

    explanation = entry.get("explanation")
    if explanation is not None and not isinstance(explanation, str):
        raise JudgeOutputUnreadable("{}: explanation must be text.".format(code))

    return RawSignalScore(
        signal_code=code.strip(),
        score_value=value,
        evidence_turn_ids=_turn_ids(entry.get("evidence_turns"), code, turn_ids_by_number),
        explanation=explanation,
        not_assessable=value is None,
        specificity_markers=_markers(entry.get("specificity_markers"), code),
    )


def _turn_ids(
    raw: Any, code: str, turn_ids_by_number: Mapping[int, str]
) -> Tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise JudgeOutputUnreadable("{}: evidence_turns must be a list.".format(code))
    ids: List[str] = []
    for number in raw:
        if isinstance(number, bool) or not isinstance(number, int):
            raise JudgeOutputUnreadable(
                "{}: evidence_turns must be turn numbers, got {!r}.".format(code, number)
            )
        ids.append(turn_ids_by_number.get(number, UNMAPPED.format(number)))
    return tuple(dict.fromkeys(ids))


def _markers(raw: Any, code: str) -> Tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise JudgeOutputUnreadable(
            "{}: specificity_markers must be a list.".format(code)
        )
    for marker in raw:
        if not isinstance(marker, str):
            raise JudgeOutputUnreadable(
                "{}: specificity_markers must be text.".format(code)
            )
    return tuple(dict.fromkeys(m.strip() for m in raw))


def _text(payload: Mapping, key: str, default: Optional[str] = None) -> str:
    value = payload.get(key, default)
    if value is None:
        raise JudgeOutputUnreadable("'{}' is missing.".format(key))
    if not isinstance(value, str):
        raise JudgeOutputUnreadable("'{}' must be text.".format(key))
    return value


def _optional_text(payload: Mapping, key: str) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise JudgeOutputUnreadable("'{}' must be text or null.".format(key))
    return value
