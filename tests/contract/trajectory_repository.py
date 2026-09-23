"""TrajectoryRepository contract — run against every implementation."""

from __future__ import annotations

from src.domain.trajectories.records import (
    SignalTrajectory,
    TrajectoryState,
    TrajectoryUpdate,
)
from src.domain.trajectories.repository import (
    TrajectoryUpdateAlreadyExists,
    TrajectoryUpdateNotFound,
)


def make_update(update_id="example-trajectory-1", through_turn_id="example-turn-1",
                created_at="2026-01-01T00:00:00Z"):
    return TrajectoryUpdate(
        id=update_id,
        session_id="example-session-1",
        through_turn_id=through_turn_id,
        trajectory_policy_version="trajectory_v0.1",
        state=TrajectoryState(
            session_id="example-session-1",
            through_turn_id=through_turn_id,
            window_definition="whole_session_v0.1",
            signals=(
                SignalTrajectory(
                    signal_code="harm_intent",
                    current_level=1,
                    current_level_turn_id="example-turn-1",
                    change=-2,
                    change_direction="decreasing",
                    escalation_by_specificity=True,
                    escalation_turn_ids=("example-turn-0", "example-turn-1"),
                    peak_level=3,
                    peak_turn_id="example-turn-0",
                    recovery_decrease=2,
                    recovery_sustained_count=2,
                    recovery_antecedent_turn_id="example-turn-0",
                    recovery_antecedent_kind="grounding",
                    null_count=1,
                ),
                SignalTrajectory(signal_code="dcs", current_level=0, peak_level=0),
            ),
        ),
        input_assessment_ids=("example-assessment-1", "example-assessment-2"),
        created_at=created_at,
    )


class TrajectoryRepositoryContract:
    """Subclass alongside ``unittest.TestCase`` and implement :meth:`repository`."""

    def repository(self):
        raise NotImplementedError

    def test_save_and_get_round_trips_every_derived_fact(self):
        repo = self.repository()
        saved = repo.save(make_update())
        self.assertEqual(repo.get(saved.id), saved)

    def test_peak_survives_storage_alongside_the_current_level(self):
        """A stored recovery must never look like the peak never happened."""
        repo = self.repository()
        repo.save(make_update())
        harm = repo.get("example-trajectory-1").state.signal("harm_intent")
        self.assertEqual(harm.peak_level, 3)
        self.assertEqual(harm.current_level, 1)
        self.assertEqual(harm.recovery_antecedent_kind, "grounding")

    def test_all_three_escalation_mechanisms_round_trip(self):
        repo = self.repository()
        repo.save(make_update())
        harm = repo.get("example-trajectory-1").state.signal("harm_intent")
        self.assertFalse(harm.escalation_by_level)
        self.assertFalse(harm.escalation_by_frequency)
        self.assertTrue(harm.escalation_by_specificity)

    def test_gaps_round_trip_as_gaps(self):
        repo = self.repository()
        repo.save(make_update())
        self.assertEqual(
            repo.get("example-trajectory-1").state.signal("harm_intent").null_count, 1
        )

    def test_input_assessment_ids_are_retained(self):
        """Without them the derivation cannot be recomputed (§19 criterion 7)."""
        repo = self.repository()
        repo.save(make_update())
        self.assertEqual(
            repo.get("example-trajectory-1").input_assessment_ids,
            ("example-assessment-1", "example-assessment-2"),
        )

    def test_get_unknown_raises(self):
        with self.assertRaises(TrajectoryUpdateNotFound):
            self.repository().get("no-such-update")

    def test_duplicate_id_raises(self):
        repo = self.repository()
        repo.save(make_update())
        with self.assertRaises(TrajectoryUpdateAlreadyExists):
            repo.save(make_update())

    def test_latest_for_session_returns_the_most_recent(self):
        repo = self.repository()
        repo.save(make_update(created_at="2026-01-01T00:00:00Z"))
        repo.save(make_update(update_id="example-trajectory-2",
                              created_at="2026-01-01T00:00:01Z"))
        self.assertEqual(repo.latest_for_session("example-session-1").id,
                         "example-trajectory-2")

    def test_latest_for_unknown_session_is_none(self):
        self.assertIsNone(self.repository().latest_for_session("no-such-session"))

    def test_an_update_must_name_its_inputs(self):
        with self.assertRaises(ValueError):
            TrajectoryUpdate(
                id="example-trajectory-9",
                session_id="example-session-1",
                through_turn_id="example-turn-1",
                trajectory_policy_version="trajectory_v0.1",
                state=TrajectoryState(
                    session_id="example-session-1",
                    through_turn_id="example-turn-1",
                    window_definition="whole_session_v0.1",
                    signals=(),
                ),
                input_assessment_ids=(),
                created_at="2026-01-01T00:00:00Z",
            )
