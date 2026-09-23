"""Trajectory Engine — architecture.md §6.8, taxonomy §6.

Cases are taken from the taxonomy's own worked examples, so a change to the
engine that contradicts the taxonomy fails here.
"""

from __future__ import annotations

import unittest

from src.domain.assessments.records import (
    Assessment,
    SignalScore,
    ValidatedAssessment,
)
from src.domain.trajectories.records import AssessedExchange
from src.modules.analysis.definitions import AnalyticalDefinitions
from src.modules.trajectory.engine import TrajectoryEngine

SIGNALS = ("harm_intent", "sis", "sgq")
POLICY = AnalyticalDefinitions().trajectory_policy("trajectory_v0.1")


def assessment(index, values, markers=()):
    record = Assessment(
        id="example-assessment-{}".format(index),
        analysis_job_id="example-job-{}".format(index),
        context_category="personal",
        uncertainty="none",
        insufficient_evidence=False,
        explanation="Example explanation.",
        judge_provider="example-provider",
        judge_model="example-model",
        judge_model_version="example-2026-01",
        rubric_version="rubric_v0.1",
        taxonomy_version="taxonomy_v0.1",
        scale_version="scale_0_3_v0.1",
        prompt_configuration_version="judge_v0_1",
        schema_version="assessment_v0.1",
        created_at="2026-01-01T00:00:00Z",
    )
    scores = tuple(
        SignalScore(
            id="example-score-{}-{}".format(index, code),
            assessment_id=record.id,
            signal_code=code,
            score_value=values.get(code, 0),
            scale_version="scale_0_3_v0.1",
            not_assessable=values.get(code, 0) is None,
            specificity_markers=tuple(markers) if code == "harm_intent" else (),
        )
        for code in SIGNALS
    )
    return ValidatedAssessment(assessment=record, scores=scores, evidence=())


def series(harm_values, markers_by_index=None, companion=None):
    """Build exchanges whose harm_intent follows ``harm_values``."""
    markers_by_index = markers_by_index or {}
    companion = companion or {}
    exchanges = []
    for index, value in enumerate(harm_values):
        values = {"harm_intent": value}
        values.update(companion.get(index, {}))
        exchanges.append(
            AssessedExchange(
                turn_id="example-turn-{}".format(index),
                turn_index=index,
                assessment=assessment(index, values, markers_by_index.get(index, ())),
            )
        )
    return exchanges


def harm(harm_values, **kwargs):
    engine = TrajectoryEngine(POLICY)
    state = engine.compute("example-session-1", series(harm_values, **kwargs), SIGNALS)
    return state.signal("harm_intent")


class CurrentLevelAndPeak(unittest.TestCase):
    def test_current_level_is_the_latest_scored_value(self):
        self.assertEqual(harm([0, 1, 3]).current_level, 3)

    def test_a_null_is_skipped_not_treated_as_zero(self):
        """Taxonomy §6.1: 1, 2, null, 3 -> current level 3."""
        trajectory = harm([1, 2, None, 3])
        self.assertEqual(trajectory.current_level, 3)
        self.assertEqual(trajectory.null_count, 1)

    def test_current_level_comes_from_the_last_scored_exchange(self):
        trajectory = harm([2, None, None])
        self.assertEqual(trajectory.current_level, 2)
        self.assertEqual(trajectory.current_level_turn_id, "example-turn-0")

    def test_a_long_run_of_nulls_marks_the_level_stale(self):
        self.assertTrue(harm([2, None, None, None]).stale)

    def test_peak_survives_a_later_decrease(self):
        """Taxonomy §6.5: peak 3 at exchange 11, current level 1."""
        trajectory = harm([0, 1, 3, 1])
        self.assertEqual(trajectory.peak_level, 3)
        self.assertEqual(trajectory.peak_turn_id, "example-turn-2")
        self.assertEqual(trajectory.current_level, 1)

    def test_all_zero_gives_peak_zero_not_none(self):
        self.assertEqual(harm([0, 0, 0]).peak_level, 0)

    def test_a_signal_never_scored_reports_nothing_rather_than_zero(self):
        trajectory = harm([None, None])
        self.assertIsNone(trajectory.current_level)
        self.assertIsNone(trajectory.peak_level)
        self.assertEqual(trajectory.null_count, 2)


class Change(unittest.TestCase):
    def test_a_single_score_gives_no_change(self):
        """Fewer than two scores means None, not zero."""
        self.assertIsNone(harm([2]).change)

    def test_increase(self):
        trajectory = harm([0, 1, 3])
        self.assertEqual((trajectory.change, trajectory.change_direction), (3, "increasing"))

    def test_decrease(self):
        trajectory = harm([3, 1])
        self.assertEqual((trajectory.change, trajectory.change_direction), (-2, "decreasing"))

    def test_flat_is_stable(self):
        self.assertEqual(harm([2, 2, 2]).change_direction, "stable")

    def test_oscillation_is_volatile_not_stable(self):
        """Taxonomy §6.2: 3 -> 0 -> 3 is change 0 but must not read as stable."""
        trajectory = harm([3, 0, 3])
        self.assertEqual(trajectory.change, 0)
        self.assertEqual(trajectory.change_direction, "volatile")


class Persistence(unittest.TestCase):
    def test_a_sustained_run_is_reported(self):
        trajectory = harm([2, 2, 2, 2])
        self.assertEqual(trajectory.persistence_run_length, 4)
        self.assertEqual(trajectory.persistence_level, 2)
        self.assertEqual(trajectory.persistence_first_turn_id, "example-turn-0")

    def test_a_single_elevated_exchange_is_not_persistence(self):
        """Taxonomy §6.3 benign counterexample."""
        self.assertEqual(harm([2, 0, 0, 0]).persistence_run_length, 0)

    def test_a_null_breaks_the_run_rather_than_bridging_it(self):
        """Taxonomy §6.3: a gap starts a new run, it does not bridge two."""
        unbroken = harm([2, 2, 2, 2, 2, 2, 2])
        broken = harm([2, 2, 2, None, 2, 2, 2])
        self.assertEqual(unbroken.persistence_run_length, 7)
        self.assertEqual(broken.persistence_run_length, 3)

    def test_a_lower_score_breaks_the_run(self):
        self.assertEqual(harm([2, 2, 2, 1, 2, 2, 2]).persistence_run_length, 3)

    def test_a_broken_run_below_the_threshold_is_not_reported(self):
        """Policy requires three; two either side of a gap is not persistence."""
        self.assertEqual(harm([2, 2, None, 2, 2]).persistence_run_length, 0)


class Escalation(unittest.TestCase):
    def test_rising_levels_escalate_by_level(self):
        trajectory = harm([0, 1, 1, 2, 3])
        self.assertTrue(trajectory.escalation_by_level)
        self.assertTrue(trajectory.escalating)

    def test_oscillation_at_a_low_level_is_not_escalation(self):
        """Taxonomy §6.4 benign counterexample: 1, 0, 1, 0, 1."""
        trajectory = harm([1, 0, 1, 0, 1])
        self.assertFalse(trajectory.escalation_by_level)
        self.assertFalse(trajectory.escalating)

    def test_specificity_growth_at_a_constant_level_is_escalation(self):
        """Taxonomy §6.4 ambiguous case, stated explicitly: levels stay at 2
        while content gains a method and a time. by_level false, by_specificity
        true, and this **is** escalation."""
        trajectory = harm(
            [2, 2, 2],
            markers_by_index={0: (), 1: ("method",), 2: ("method", "time")},
        )
        self.assertFalse(trajectory.escalation_by_level)
        self.assertTrue(trajectory.escalation_by_specificity)
        self.assertTrue(trajectory.escalating)

    def test_mechanisms_are_reported_separately(self):
        trajectory = harm([0, 1, 1, 2, 3])
        self.assertIsInstance(trajectory.escalation_by_level, bool)
        self.assertIsInstance(trajectory.escalation_by_frequency, bool)
        self.assertIsInstance(trajectory.escalation_by_specificity, bool)

    def test_escalation_names_the_turns_it_came_from(self):
        trajectory = harm([0, 1, 3])
        self.assertEqual(
            trajectory.escalation_turn_ids,
            ("example-turn-0", "example-turn-1", "example-turn-2"),
        )

    def test_no_escalation_cites_no_turns(self):
        self.assertEqual(harm([1, 1, 1]).escalation_turn_ids, ())


class Recovery(unittest.TestCase):
    def test_a_sustained_decrease_after_grounding_is_recorded(self):
        """Taxonomy §6.6 positive example: 3, 3, 1, 1, 1 after a grounding turn."""
        trajectory = harm(
            [3, 3, 1, 1, 1],
            companion={1: {"sis": 3, "sgq": 3}},
        )
        self.assertEqual(trajectory.recovery_decrease, 2)
        self.assertGreaterEqual(trajectory.recovery_sustained_count, 2)

    def test_peak_is_still_reported_after_recovery(self):
        trajectory = harm([3, 3, 1, 1, 1], companion={1: {"sis": 3}})
        self.assertEqual(trajectory.peak_level, 3)
        self.assertEqual(trajectory.current_level, 1)

    def test_a_decrease_after_disengagement_is_distinguishable_from_grounding(self):
        """Taxonomy §6.6 ambiguous case: the signal fell but nothing grounded it."""
        grounded = harm([3, 3, 1, 1, 1], companion={1: {"sgq": 3}})
        disengaged = harm([3, 3, 1, 1, 1], companion={1: {"sis": 0, "sgq": 0}})
        self.assertEqual(grounded.recovery_antecedent_kind, "grounding")
        self.assertEqual(disengaged.recovery_antecedent_kind, "none_observed")

    def test_a_single_dip_is_not_recovery(self):
        self.assertIsNone(harm([3, 1, 3]).recovery_decrease)

    def test_no_recovery_when_the_signal_is_still_at_peak(self):
        self.assertIsNone(harm([1, 2, 3]).recovery_decrease)


class Determinism(unittest.TestCase):
    """§6.8: the update is deterministic for the same ordered assessments."""

    def test_same_input_gives_the_same_result(self):
        first = harm([0, 1, 2, 3])
        second = harm([0, 1, 2, 3])
        self.assertEqual(first, second)

    def test_fetch_order_cannot_change_the_result(self):
        engine = TrajectoryEngine(POLICY)
        exchanges = series([0, 1, 3])
        forward = engine.compute("example-session-1", exchanges, SIGNALS)
        reversed_ = engine.compute("example-session-1", list(reversed(exchanges)), SIGNALS)
        self.assertEqual(forward, reversed_)

    def test_an_empty_window_is_refused(self):
        with self.assertRaises(ValueError):
            TrajectoryEngine(POLICY).compute("example-session-1", [], SIGNALS)


if __name__ == "__main__":
    unittest.main()
