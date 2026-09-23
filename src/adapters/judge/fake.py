"""Deterministic fake judge — architecture.md section 6.6, tests only.

Returns exactly what the test tells it to, so the whole pipeline can be built
and exercised without choosing a model provider ([OD-013]) and without any
network call. It contains no scoring logic of its own, deliberately: a fake
that decided scores would be a second, untested implementation of the rubric.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Union

from src.domain.analysis.judge import JudgeRequest, RawJudgeResult

Responder = Callable[[JudgeRequest], RawJudgeResult]


class DeterministicFakeJudgeAdapter:
    def __init__(
        self,
        result: Optional[Union[RawJudgeResult, Responder]] = None,
        by_turn_id: Optional[Dict[str, Union[RawJudgeResult, Responder]]] = None,
    ):
        self._result = result
        self._by_turn_id = by_turn_id or {}
        self.requests = []

    def assess(self, request: JudgeRequest) -> RawJudgeResult:
        self.requests.append(request)
        configured = self._by_turn_id.get(request.through_turn_id, self._result)
        if configured is None:
            raise AssertionError(
                "No fake judge result configured for turn {!r}.".format(
                    request.through_turn_id
                )
            )
        if callable(configured):
            return configured(request)
        return configured
