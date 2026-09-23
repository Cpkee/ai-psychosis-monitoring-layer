"""Analysis runner — the full job lifecycle, end to end.

Completes architecture section 19 criterion 6: processing status correctly
represents pending, processing, completed, delayed and failed.
"""

from __future__ import annotations

import itertools
import unittest

from src.adapters.judge.fake import DeterministicFakeJudgeAdapter
from src.adapters.memory.analysis import InMemoryJobRepository
from src.adapters.memory.assessments import InMemoryAssessmentRepository
from src.adapters.memory.conversations import InMemoryConversationRepository
from src.domain.analysis.judge import JudgeUnavailable, RawSignalScore
from src.domain.analysis.records import ProcessingStatus
from src.modules.analysis.definitions import AnalyticalDefinitions
from src.modules.analysis.runner import (
    VALIDATION_FAILED,
    WINDOW_NOT_FOUND,
    AnalysisRunner,
)
from src.adapters.memory.alerts import InMemoryAlertRepository
from src.adapters.memory.trajectories import InMemoryTrajectoryRepository
from src.modules.alerting.engine import AlertEngine
from src.modules.alerting.rules import load_rule_set
from src.modules.analysis.validator import ResultValidator
from src.modules.trajectory.engine import TrajectoryEngine
from tests.contract.conversation_repository import make_session, make_turn
from tests.contract.job_repository import make_job
from tests.test_validator import result


class RunnerFixture:
    """In-memory repositories and a runner built over them."""

    def setUp(self):
        self.jobs = InMemoryJobRepository()
        self.assessments = InMemoryAssessmentRepository()
        self.conversations = InMemoryConversationRepository()
        self.conversations.create_session(make_session())
        for index in (0, 1):
            self.conversations.append_turn(
                make_turn(
                    id="example-turn-{}".format(index),
                    turn_index=index,
                    role="user" if index == 0 else "assistant",
                    idempotency_key="example-key-{}".format(index),
                )
            )
        self.trajectories = InMemoryTrajectoryRepository()
        self.alerts = InMemoryAlertRepository()
        self.jobs.create(make_job(through_turn_id="example-turn-1"))

    def runner(self, judge):
        counter = itertools.count(1)
        return AnalysisRunner(
            jobs=self.jobs,
            conversations=self.conversations,
            assessments=self.assessments,
            judge=judge,
            validator=ResultValidator(
                definitions=AnalyticalDefinitions(),
                new_id=lambda: "example-id-{}".format(next(counter)),
                clock=lambda: "2026-01-01T00:00:00Z",
            ),
            trajectories=self.trajectories,
            engine=TrajectoryEngine(
                AnalyticalDefinitions().trajectory_policy("trajectory_v0.1")
            ),
            alerts=self.alerts,
            alert_engine=AlertEngine(load_rule_set("alert_rules_v0.1")),
            definitions=AnalyticalDefinitions(),
            rubric_instructions="example instructions",
            prompt_configuration_version="judge_v0_1",
            clock=lambda: "2026-01-01T00:00:05Z",
            new_id=lambda: "example-trajectory-{}".format(next(counter)),
        )


class RunnerTest(RunnerFixture, unittest.TestCase):
    def test_a_good_result_completes_the_job_and_stores_an_assessment(self):
        judge = DeterministicFakeJudgeAdapter(result(scores={"harm_intent": 2}))
        job = self.runner(judge).run("example-job-1")

        self.assertEqual(job.status, ProcessingStatus.COMPLETED)
        self.assertEqual(job.attempt_count, 1)
        self.assertIsNotNone(job.started_at)
        self.assertIsNotNone(job.completed_at)

        stored = self.assessments.find_for_job("example-job-1")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.score("harm_intent").score_value, 2)

    def test_the_judge_sees_the_window_but_not_the_experiment(self):
        """The judge must score the conversation, not the experiment."""
        judge = DeterministicFakeJudgeAdapter(result())
        self.runner(judge).run("example-job-1")

        request = judge.requests[0]
        self.assertEqual([t.id for t in request.window], ["example-turn-0", "example-turn-1"])
        fields = set(vars(request))
        for leak in ("companion_condition", "scenario_id", "raw_theme_label"):
            self.assertNotIn(leak, fields)

    def test_the_job_pins_the_versions_the_assessment_records(self):
        judge = DeterministicFakeJudgeAdapter(result())
        self.runner(judge).run("example-job-1")
        job = self.jobs.get("example-job-1")
        record = self.assessments.find_for_job("example-job-1").assessment
        self.assertEqual(record.rubric_version, job.rubric_version)
        self.assertEqual(record.taxonomy_version, job.taxonomy_version)
        self.assertEqual(record.scale_version, job.scale_version)

    def test_an_unreachable_judge_delays_rather_than_fails(self):
        """Delay is expected operational behaviour; failure is not."""

        def unavailable(_request):
            raise JudgeUnavailable("provider rate limited")

        job = self.runner(DeterministicFakeJudgeAdapter(unavailable)).run("example-job-1")
        self.assertEqual(job.status, ProcessingStatus.DELAYED)
        self.assertEqual(job.attempt_count, 1)
        self.assertIn("rate limited", job.failure_detail)
        self.assertIsNone(self.assessments.find_for_job("example-job-1"))

    def test_a_delayed_job_can_be_retried_and_the_attempt_is_retained(self):
        def unavailable(_request):
            raise JudgeUnavailable("provider rate limited")

        self.runner(DeterministicFakeJudgeAdapter(unavailable)).run("example-job-1")
        job = self.runner(DeterministicFakeJudgeAdapter(result())).run("example-job-1")

        self.assertEqual(job.status, ProcessingStatus.COMPLETED)
        self.assertEqual(job.attempt_count, 2)

    def test_invalid_output_fails_visibly_and_stores_no_assessment(self):
        """Section 19 criterion 5, and section 6.7: never coerce into valid scores."""
        bad = result(scores={"harm_intent": RawSignalScore(
            signal_code="harm_intent", score_value=3, explanation="no evidence cited")})
        job = self.runner(DeterministicFakeJudgeAdapter(bad)).run("example-job-1")

        self.assertEqual(job.status, ProcessingStatus.FAILED)
        self.assertEqual(job.failure_code, VALIDATION_FAILED)
        self.assertIn("must cite at least one turn", job.failure_detail)
        self.assertIsNone(self.assessments.find_for_job("example-job-1"))

    def test_a_failure_detail_never_contains_judge_output(self):
        secret = "THIS IS THE MODELS PRIVATE REASONING"
        bad = result(explanation=secret, context_category="not-a-category")
        job = self.runner(DeterministicFakeJudgeAdapter(bad)).run("example-job-1")
        self.assertEqual(job.status, ProcessingStatus.FAILED)
        self.assertNotIn(secret, job.failure_detail)

    def test_a_job_pointing_at_a_missing_turn_fails(self):
        self.jobs.create(make_job(id="example-job-2", through_turn_id="example-turn-9"))
        job = self.runner(DeterministicFakeJudgeAdapter(result())).run("example-job-2")
        self.assertEqual(job.status, ProcessingStatus.FAILED)
        self.assertEqual(job.failure_code, WINDOW_NOT_FOUND)

    def test_a_completed_job_cannot_be_run_again(self):
        from src.domain.analysis.records import InvalidTransition

        runner = self.runner(DeterministicFakeJudgeAdapter(result()))
        runner.run("example-job-1")
        with self.assertRaises(InvalidTransition):
            runner.run("example-job-1")

    def test_the_window_stops_at_the_turn_the_job_was_requested_for(self):
        self.conversations.append_turn(
            make_turn(id="example-turn-2", turn_index=2, idempotency_key="example-key-2")
        )
        judge = DeterministicFakeJudgeAdapter(result())
        self.runner(judge).run("example-job-1")
        self.assertEqual(
            [t.id for t in judge.requests[0].window],
            ["example-turn-0", "example-turn-1"],
        )

    def test_a_completed_job_also_stores_a_trajectory(self):
        """The trajectory engine's only production caller."""
        judge = DeterministicFakeJudgeAdapter(result(scores={"harm_intent": 2}))
        self.runner(judge).run("example-job-1")

        update = self.trajectories.latest_for_session("example-session-1")
        self.assertIsNotNone(update)
        self.assertEqual(update.trajectory_policy_version, "trajectory_v0.1")
        self.assertEqual(update.state.signal("harm_intent").current_level, 2)

    def test_the_trajectory_names_the_assessments_it_was_derived_from(self):
        """§19 criterion 7: it must be recomputable from stored assessments."""
        judge = DeterministicFakeJudgeAdapter(result(scores={"harm_intent": 2}))
        self.runner(judge).run("example-job-1")

        update = self.trajectories.latest_for_session("example-session-1")
        stored = self.assessments.find_for_job("example-job-1")
        self.assertEqual(update.input_assessment_ids, (stored.assessment.id,))

    def test_a_failed_job_stores_no_trajectory(self):
        """Nothing was assessed, so there is nothing to derive from."""
        judge = DeterministicFakeJudgeAdapter(result(context_category="not_a_category"))
        job = self.runner(judge).run("example-job-1")

        self.assertEqual(job.status, ProcessingStatus.FAILED)
        self.assertIsNone(self.trajectories.latest_for_session("example-session-1"))

    def test_unreadable_output_fails_with_its_own_code(self):
        """A reply that is not a result at all is neither an outage nor a
        validation failure, and must stay distinguishable from both."""
        from src.domain.analysis.judge import JudgeOutputUnreadable
        from src.modules.analysis.runner import OUTPUT_UNREADABLE

        class Unreadable:
            def assess(self, request):
                raise JudgeOutputUnreadable("Expected a JSON object, got str.")

        job = self.runner(Unreadable()).run("example-job-1")
        self.assertEqual(job.status, ProcessingStatus.FAILED)
        self.assertEqual(job.failure_code, OUTPUT_UNREADABLE)
        self.assertIsNone(self.assessments.find_for_job("example-job-1"))
        self.assertIsNone(self.trajectories.latest_for_session("example-session-1"))

    def test_unreadable_output_is_not_retried_as_delayed(self):
        """§13: do not retry schema-invalid output indefinitely."""
        from src.domain.analysis.judge import JudgeOutputUnreadable
        from src.modules.analysis.runner import VALIDATION_FAILED

        class Unreadable:
            def assess(self, request):
                raise JudgeOutputUnreadable("truncated")

        job = self.runner(Unreadable()).run("example-job-1")
        self.assertNotEqual(job.status, ProcessingStatus.DELAYED)
        self.assertNotEqual(job.failure_code, VALIDATION_FAILED)


    def test_a_single_exchange_raises_no_alert(self):
        """One scored exchange cannot show escalation."""
        judge = DeterministicFakeJudgeAdapter(result(scores={"harm_intent": 3}))
        self.runner(judge).run("example-job-1")
        self.assertEqual(self.alerts.list_for_session("example-session-1"), ())


class RunnerAlertTest(RunnerFixture, unittest.TestCase):
    """The Alert Engine's only production caller: alerts are evaluated after
    every stored trajectory, in the same unit of work, and cite what they used."""

    def setUp(self):
        super().setUp()
        for index in (2, 3, 4, 5):
            self.conversations.append_turn(
                make_turn(
                    id="example-turn-{}".format(index),
                    turn_index=index,
                    role="user" if index % 2 == 0 else "assistant",
                    idempotency_key="example-key-{}".format(index),
                )
            )
        for number, turn in ((2, 3), (3, 5)):
            self.jobs.create(make_job(id="example-job-{}".format(number),
                                      through_turn_id="example-turn-{}".format(turn)))

    def run_exchanges(self, *harm_levels):
        """Score exchanges 1, 3, 5 in order with the given harm_intent
        (level, markers) pairs. SIS stays 0: the companion never addresses it."""
        by_turn = {}
        for position, (level, markers) in enumerate(harm_levels):
            by_turn["example-turn-{}".format(2 * position + 1)] = result(scores={
                "harm_intent": RawSignalScore(
                    signal_code="harm_intent", score_value=level,
                    evidence_turn_ids=("example-turn-0",), explanation="Example reason.",
                    specificity_markers=markers)})
        runner = self.runner(DeterministicFakeJudgeAdapter(by_turn_id=by_turn))
        for position in range(len(harm_levels)):
            runner.run("example-job-{}".format(position + 1))
        return self.alerts.list_for_session("example-session-1")

    def test_escalating_unaddressed_harm_intent_stores_one_traceable_alert(self):
        alerts = self.run_exchanges((1, ()), (2, ()))

        self.assertEqual(len(alerts), 1)
        decision = alerts[0].decision
        self.assertEqual(decision.severity, "high")

        trajectory = self.trajectories.latest_for_session("example-session-1")
        latest = self.assessments.find_for_job("example-job-2")
        self.assertEqual(decision.trajectory_update_id, trajectory.id)
        self.assertEqual(decision.contributing_assessment_ids, trajectory.input_assessment_ids)
        self.assertEqual(decision.triggering_signal_score_ids, tuple(
            latest.score(code).id for code in ("harm_intent", "sis", "hes")))
        self.assertEqual(decision.through_turn_id, "example-turn-3")

    def test_a_later_equally_severe_firing_supersedes_the_active_alert(self):
        alerts = self.run_exchanges((1, ()), (2, ()), (2, ()))

        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0].superseded_by, alerts[1].id)
        active = self.alerts.active_for_session("example-session-1", "harm-intent-unaddressed")
        self.assertEqual(active.decision.through_turn_id, "example-turn-5")

    def test_a_falling_score_does_not_downgrade_the_active_alert(self):
        """D-39: the critical alert stays in front of the reviewer."""
        alerts = self.run_exchanges((1, ()), (3, ("time", "location")), (2, ()))

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].decision.severity, "critical")
        self.assertIsNone(alerts[0].superseded_by)

if __name__ == "__main__":
    unittest.main()
