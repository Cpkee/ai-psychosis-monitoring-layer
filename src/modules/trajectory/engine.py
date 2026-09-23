"""Trajectory Engine — architecture.md section 6.8.

Derives the six [taxonomy §6] concepts from stored assessments: current level,
change over time, persistence, escalation, peak, and recovery.

**Recomputation, not a fold.** Section 6.8 sketches
``update(previous, assessment, policy)``, which implies carrying derived facts
forward. This engine instead recomputes from the ordered sequence, because
§19 criterion 7 requires the trajectory to be recomputable from stored ordered
assessments, and a fold can silently drift from a recomputation. Recorded as
D-15.

Two rules run through everything here:

* **A ``null`` score is a gap, never a zero.** It never contributes to
  escalation, persistence or peak, and it breaks a run rather than continuing it.
* **Peak is never erased by a later decrease.** The worst observed state is
  always reported alongside the current one.
"""

from __future__ import annotations

import dataclasses
from typing import List, Optional, Sequence, Tuple

from src.domain.trajectories.records import (
    DECREASING,
    GROUNDING,
    INCREASING,
    INTERVENTION,
    NONE_OBSERVED,
    STABLE,
    VOLATILE,
    AssessedExchange,
    SignalTrajectory,
    TrajectoryState,
)
from src.modules.analysis.definitions import TrajectoryPolicy


@dataclasses.dataclass(frozen=True)
class _Observation:
    """One scored appearance of a signal."""

    turn_id: str
    position: int
    value: int
    markers: Tuple[str, ...]


class TrajectoryEngine:
    def __init__(self, policy: TrajectoryPolicy):
        self._policy = policy

    @property
    def policy(self) -> TrajectoryPolicy:
        return self._policy

    def compute(
        self, session_id: str, exchanges: Sequence[AssessedExchange], signal_codes: Sequence[str]
    ) -> TrajectoryState:
        """Compute the trajectory for every signal across ``exchanges``.

        ``exchanges`` must be ordered by ``turn_index``; the engine sorts
        defensively so a caller cannot make the result depend on fetch order.
        """
        if not exchanges:
            raise ValueError("A trajectory needs at least one assessment.")
        ordered = sorted(exchanges, key=lambda e: e.turn_index)
        return TrajectoryState(
            session_id=session_id,
            through_turn_id=ordered[-1].turn_id,
            window_definition=self._policy.window_definition,
            signals=tuple(
                self._for_signal(code, ordered) for code in signal_codes
            ),
        )

    # -- per signal ------------------------------------------------------

    def _for_signal(
        self, code: str, ordered: Sequence[AssessedExchange]
    ) -> SignalTrajectory:
        observations: List[_Observation] = []
        null_count = 0

        for position, exchange in enumerate(ordered):
            try:
                score = exchange.assessment.score(code)
            except KeyError:
                null_count += 1
                continue
            if score.score_value is None:
                null_count += 1
                continue
            observations.append(
                _Observation(
                    turn_id=exchange.turn_id,
                    position=position,
                    value=score.score_value,
                    markers=tuple(score.specificity_markers),
                )
            )

        if not observations:
            return SignalTrajectory(signal_code=code, null_count=null_count)

        latest = observations[-1]
        peak = max(observations, key=lambda o: (o.value, -o.position))
        change, direction = self._change(observations)
        run_level, run_length, run_first, run_last = self._persistence(observations)
        by_level, by_frequency, by_specificity = self._escalation(observations)
        decrease, sustained, antecedent_id, antecedent_kind = self._recovery(
            observations, peak, ordered
        )

        return SignalTrajectory(
            signal_code=code,
            current_level=latest.value,
            current_level_turn_id=latest.turn_id,
            stale=(len(ordered) - 1 - latest.position) >= self._policy.staleness_gap,
            change=change,
            change_direction=direction,
            persistence_level=run_level,
            persistence_run_length=run_length,
            persistence_first_turn_id=run_first,
            persistence_last_turn_id=run_last,
            escalation_by_level=by_level,
            escalation_by_frequency=by_frequency,
            escalation_by_specificity=by_specificity,
            escalation_turn_ids=(
                tuple(o.turn_id for o in observations)
                if (by_level or by_frequency or by_specificity)
                else ()
            ),
            peak_level=peak.value,
            peak_turn_id=peak.turn_id,
            recovery_decrease=decrease,
            recovery_sustained_count=sustained,
            recovery_antecedent_turn_id=antecedent_id,
            recovery_antecedent_kind=antecedent_kind,
            null_count=null_count,
        )

    # -- concepts --------------------------------------------------------

    @staticmethod
    def _change(observations: List[_Observation]):
        """Taxonomy §6.2. Fewer than two scores means ``None``, never zero."""
        if len(observations) < 2:
            return None, None
        values = [o.value for o in observations]
        change = values[-1] - values[0]
        if change > 0:
            return change, INCREASING
        if change < 0:
            return change, DECREASING
        # Net zero, but 3 -> 0 -> 3 is not stability.
        if max(values) - min(values) >= 2:
            return change, VOLATILE
        return change, STABLE

    def _persistence(self, observations: List[_Observation]):
        """Taxonomy §6.3. A run is consecutive *scored* exchanges at or above
        the threshold; a gap or a lower score ends it."""
        best: Tuple[int, List[_Observation]] = (0, [])
        current: List[_Observation] = []
        previous_position: Optional[int] = None

        for observation in observations:
            contiguous = previous_position is None or observation.position == previous_position + 1
            if observation.value >= self._policy.persistence_min_level and contiguous:
                current.append(observation)
            elif observation.value >= self._policy.persistence_min_level:
                current = [observation]
            else:
                current = []
            previous_position = observation.position
            if len(current) > best[0]:
                best = (len(current), list(current))

        length, run = best
        if length < self._policy.persistence_min_run_length:
            return None, 0, None, None
        return min(o.value for o in run), length, run[0].turn_id, run[-1].turn_id

    @staticmethod
    def _escalation(observations: List[_Observation]):
        """Taxonomy §6.4. Three mechanisms, each reported separately."""
        values = [o.value for o in observations]
        by_level = len(values) >= 2 and values[-1] > values[0]

        # Symmetric halves. An uneven split makes an oscillation like
        # 1, 0, 1, 0, 1 look like rising frequency, which taxonomy §6.4 gives
        # as a benign counterexample.
        by_frequency = False
        half = len(values) // 2
        if half >= 2:
            earlier = sum(1 for v in values[:half] if v > 0)
            later = sum(1 for v in values[-half:] if v > 0)
            by_frequency = later > earlier

        # Movement toward more concerning content at the same numeric level:
        # the case taxonomy §6.4 says "IS escalation and must be reported".
        by_specificity = len(observations[-1].markers) > len(observations[0].markers)

        return by_level, by_frequency, by_specificity

    def _recovery(
        self,
        observations: List[_Observation],
        peak: _Observation,
        ordered: Sequence[AssessedExchange],
    ):
        """Taxonomy §6.6. An observed decrease, never a clinical conclusion."""
        after = [o for o in observations if o.position > peak.position]
        if not after or observations[-1].value >= peak.value:
            return None, 0, None, None

        sustained = 0
        first_drop: Optional[_Observation] = None
        for observation in after:
            if observation.value < peak.value:
                sustained += 1
                if first_drop is None:
                    first_drop = observation
            else:
                sustained = 0
                first_drop = None
        if sustained < self._policy.recovery_min_sustained or first_drop is None:
            return None, 0, None, None

        antecedent_id, antecedent_kind = self._antecedent(first_drop, ordered)
        return peak.value - observations[-1].value, sustained, antecedent_id, antecedent_kind

    @staticmethod
    def _antecedent(first_drop: _Observation, ordered: Sequence[AssessedExchange]):
        """What preceded the decrease. Association is recorded, never causation.

        The candidate is the exchange **immediately before the drop was first
        observed**: under the rubric's unit of assessment a companion response
        can only influence the user's next turn. A decrease after the companion
        simply disengaged must be distinguishable from one after grounding, so
        ``none_observed`` is a reported outcome rather than a missing value.
        """
        position = first_drop.position - 1
        if position < 0:
            return None, None
        following = ordered[position]
        turn_id = following.turn_id

        def level(code: str) -> int:
            try:
                value = following.assessment.score(code).score_value
            except KeyError:
                return 0
            return value or 0

        if level("sis") >= 2:
            return turn_id, INTERVENTION
        if level("sgq") >= 2:
            return turn_id, GROUNDING
        return turn_id, NONE_OBSERVED
