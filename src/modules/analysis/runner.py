"""Analysis runner — drives one job through the lifecycle.

This is the caller that justifies the judge seam, the validator and the
assessment repository existing. It is deliberately the only place that decides
whether a job ends `COMPLETED`, `DELAYED` or `FAILED`.

The distinction matters and is kept sharp:

* ``DELAYED`` — the judge could not be reached. Expected operational
  behaviour, retryable.
* ``FAILED`` — the judge answered and the answer was unusable, either because
  it could not be read as a result at all (``OUTPUT_UNREADABLE``) or because it
  was well formed but broke the contract (``VALIDATION_FAILED``). Not retryable
  without a change. **No assessment is stored** (section 6.7); the failure is
  visible rather than papered over with coerced scores.
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from src.domain.analysis import records as lifecycle
from src.domain.analysis.judge import (
    JudgeAdapter,
    JudgeOutputUnreadable,
    JudgeRequest,
    JudgeUnavailable,
)
from src.domain.analysis.records import AnalysisJob, ProcessingStatus
from src.domain.analysis.repository import JobRepository
from src.domain.assessments.repository import AssessmentRepository
from src.domain.conversations.records import Turn
from src.domain.conversations.repository import ConversationRepository
from src.domain.trajectories.records import AssessedExchange, TrajectoryUpdate
from src.domain.trajectories.repository import TrajectoryRepository
from src.modules.analysis.definitions import AnalyticalDefinitions
from src.modules.analysis.validator import AssessmentRejected, ResultValidator
from src.modules.trajectory.engine import TrajectoryEngine

WINDOW_NOT_FOUND = "WINDOW_NOT_FOUND"
VALIDATION_FAILED = "VALIDATION_FAILED"
#: The judge answered and the answer was not a result at all: truncated,
#: refused, or the wrong shape. Kept separate from VALIDATION_FAILED so the
#: two causes stay distinguishable in job history.
OUTPUT_UNREADABLE = "OUTPUT_UNREADABLE"


class AnalysisRunner:
    def __init__(
        self,
        jobs: JobRepository,
        conversations: ConversationRepository,
        assessments: AssessmentRepository,
        judge: JudgeAdapter,
        validator: ResultValidator,
        trajectories: TrajectoryRepository,
        engine: TrajectoryEngine,
        definitions: AnalyticalDefinitions,
        rubric_instructions: str,
        prompt_configuration_version: str,
        clock: Callable[[], str],
        new_id: Callable[[], str],
    ):
        self._jobs = jobs
        self._conversations = conversations
        self._assessments = assessments
        self._judge = judge
        self._validator = validator
        self._trajectories = trajectories
        self._engine = engine
        self._definitions = definitions
        self._new_id = new_id
        self._rubric_instructions = rubric_instructions
        self._prompt_configuration_version = prompt_configuration_version
        self._clock = clock

    def run(self, job_id: str) -> AnalysisJob:
        """Claim a job, score it, and record the outcome."""
        pending = self._jobs.get(job_id)
        claimed = self._jobs.update(
            lifecycle.claim(pending, self._clock()), pending.status
        )

        window = self._window(claimed)
        if window is None:
            return self._jobs.update(
                lifecycle.fail(
                    claimed,
                    WINDOW_NOT_FOUND,
                    "Turn {!r} is not in session {!r}.".format(
                        claimed.through_turn_id, claimed.session_id
                    ),
                ),
                ProcessingStatus.PROCESSING,
            )

        request = self._request(claimed, window)

        try:
            raw = self._judge.assess(request)
        except JudgeUnavailable as exc:
            return self._jobs.update(
                lifecycle.delay(claimed, str(exc)), ProcessingStatus.PROCESSING
            )
        except JudgeOutputUnreadable as exc:
            # Not an outage, so not retryable; and not a validation failure,
            # because there is no well-formed result to validate.
            return self._jobs.update(
                lifecycle.fail(claimed, OUTPUT_UNREADABLE, str(exc)),
                ProcessingStatus.PROCESSING,
            )

        try:
            validated = self._validator.validate_and_normalize(raw, request, claimed.id)
        except AssessmentRejected as exc:
            return self._jobs.update(
                lifecycle.fail(claimed, VALIDATION_FAILED, "; ".join(exc.problems)),
                ProcessingStatus.PROCESSING,
            )

        self._assessments.save(validated)
        completed = self._jobs.update(
            lifecycle.complete(claimed, self._clock()), ProcessingStatus.PROCESSING
        )
        self._update_trajectory(completed)
        return completed

    def _update_trajectory(self, job: AnalysisJob) -> Optional[TrajectoryUpdate]:
        """Recompute the session trajectory from every stored assessment.

        Recomputation rather than an incremental fold, so the stored result is
        always reproducible from the assessments it names (§19 criterion 7).
        """
        positions = {
            turn.id: turn.turn_index
            for turn in self._conversations.list_turns(job.session_id)
        }
        exchanges = []
        for session_job in self._jobs.list_for_session(job.session_id):
            assessment = self._assessments.find_for_job(session_job.id)
            if assessment is None or session_job.through_turn_id not in positions:
                continue
            exchanges.append(
                AssessedExchange(
                    turn_id=session_job.through_turn_id,
                    turn_index=positions[session_job.through_turn_id],
                    assessment=assessment,
                )
            )
        if not exchanges:
            return None

        state = self._engine.compute(
            job.session_id,
            exchanges,
            self._definitions.taxonomy(job.taxonomy_version).signal_codes,
        )
        return self._trajectories.save(
            TrajectoryUpdate(
                id=self._new_id(),
                session_id=job.session_id,
                through_turn_id=state.through_turn_id,
                trajectory_policy_version=self._engine.policy.version,
                state=state,
                input_assessment_ids=tuple(
                    e.assessment.assessment.id for e in sorted(
                        exchanges, key=lambda x: x.turn_index
                    )
                ),
                created_at=self._clock(),
            )
        )

    # -- internals -------------------------------------------------------

    def _window(self, job: AnalysisJob) -> Optional[Tuple[Turn, ...]]:
        """Turns up to and including the one this job was requested for."""
        turns = self._conversations.list_turns(job.session_id)
        for position, turn in enumerate(turns):
            if turn.id == job.through_turn_id:
                return tuple(turns[: position + 1])
        return None

    def _request(self, job: AnalysisJob, window: Tuple[Turn, ...]) -> JudgeRequest:
        return JudgeRequest(
            session_id=job.session_id,
            through_turn_id=job.through_turn_id,
            window=window,
            taxonomy_version=job.taxonomy_version,
            scale_version=job.scale_version,
            rubric_version=job.rubric_version,
            rubric_instructions=self._rubric_instructions,
            prompt_configuration_version=self._prompt_configuration_version,
            schema_version=job.schema_version,
            judge_configuration_version=job.judge_configuration_version,
        )
