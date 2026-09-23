"""Result Validator and Normalizer — architecture.md section 6.7.

Converts provider-specific judge output into a trusted domain assessment, or
rejects it. Section 6.7 is explicit that *"validation failures are stored as
processing failures, not coerced into valid scores"*, so this module raises
rather than repairing.

Every problem found is reported, not just the first, so a failing judge can be
diagnosed from one run.
"""

from __future__ import annotations

from typing import Callable, List

from src.domain.analysis.judge import JudgeRequest, RawJudgeResult, RawSignalScore
from src.domain.assessments.records import (
    Assessment,
    EvidenceReference,
    SignalScore,
    ValidatedAssessment,
)
from src.modules.analysis.definitions import AnalyticalDefinitions


class AssessmentRejected(ValueError):
    """The judge output did not satisfy the contract.

    Carries every problem found. The messages describe *our* validation rules
    and never reproduce provider output, so recording them cannot leak the
    hidden reasoning section 6.6 forbids.
    """

    def __init__(self, problems: List[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


class ResultValidator:
    def __init__(
        self,
        definitions: AnalyticalDefinitions,
        new_id: Callable[[], str],
        clock: Callable[[], str],
    ):
        self._definitions = definitions
        self._new_id = new_id
        self._clock = clock

    def validate_and_normalize(
        self, raw: RawJudgeResult, request: JudgeRequest, analysis_job_id: str
    ) -> ValidatedAssessment:
        taxonomy = self._definitions.taxonomy(request.taxonomy_version)
        scale = self._definitions.scale(request.scale_version)
        problems: List[str] = []

        if raw.context_category not in taxonomy.context_categories:
            problems.append(
                "context_category {!r} is not in taxonomy {}".format(
                    raw.context_category, taxonomy.version
                )
            )
        if raw.context_confidence is not None and (
            raw.context_confidence not in taxonomy.confidence_levels
        ):
            problems.append(
                "context_confidence {!r} is not a defined level".format(
                    raw.context_confidence
                )
            )
        if raw.uncertainty is not None and raw.uncertainty not in taxonomy.uncertainty_markers:
            problems.append(
                "uncertainty marker {!r} is not defined".format(raw.uncertainty)
            )
        if not raw.explanation or not raw.explanation.strip():
            problems.append("an evidence-grounded explanation is required")
        for field in ("judge_provider", "judge_model", "judge_model_version"):
            if not str(getattr(raw, field) or "").strip():
                problems.append("{} must be recorded".format(field))

        reported = [score.signal_code for score in raw.scores]
        missing = [code for code in taxonomy.signal_codes if code not in reported]
        if missing:
            problems.append("missing signals: " + ", ".join(missing))
        unknown = [code for code in reported if code not in taxonomy.signal_codes]
        if unknown:
            problems.append("unknown signals: " + ", ".join(sorted(set(unknown))))
        if len(reported) != len(set(reported)):
            problems.append("a signal was scored more than once")

        assessment_id = self._new_id()
        scores: List[SignalScore] = []
        evidence: List[EvidenceReference] = []

        for raw_score in raw.scores:
            if raw_score.signal_code not in taxonomy.signal_codes:
                continue
            problems.extend(self._check_score(raw_score, scale, taxonomy, request))
            scores.append(
                SignalScore(
                    id=self._new_id(),
                    assessment_id=assessment_id,
                    signal_code=raw_score.signal_code,
                    score_value=raw_score.score_value,
                    scale_version=scale.version,
                    uncertain=raw_score.uncertain,
                    not_assessable=raw_score.score_value is None,
                    specificity_markers=tuple(
                        dict.fromkeys(raw_score.specificity_markers)
                    ),
                )
            )
            for turn_id in dict.fromkeys(raw_score.evidence_turn_ids):
                evidence.append(
                    EvidenceReference(
                        assessment_id=assessment_id,
                        turn_id=turn_id,
                        signal_code=raw_score.signal_code,
                    )
                )

        if problems:
            raise AssessmentRejected(problems)

        return ValidatedAssessment(
            assessment=Assessment(
                id=assessment_id,
                analysis_job_id=analysis_job_id,
                context_category=raw.context_category,
                context_confidence=raw.context_confidence,
                uncertainty=raw.uncertainty,
                insufficient_evidence=raw.insufficient_evidence,
                explanation=raw.explanation.strip(),
                judge_provider=raw.judge_provider,
                judge_model=raw.judge_model,
                judge_model_version=raw.judge_model_version,
                rubric_version=request.rubric_version,
                taxonomy_version=taxonomy.version,
                scale_version=scale.version,
                prompt_configuration_version=request.prompt_configuration_version,
                schema_version=request.schema_version,
                created_at=self._clock(),
            ),
            scores=tuple(scores),
            evidence=tuple(evidence),
        )

    @staticmethod
    def _check_score(
        raw_score: RawSignalScore, scale, taxonomy, request: JudgeRequest
    ) -> List[str]:
        problems: List[str] = []
        code = raw_score.signal_code
        value = raw_score.score_value

        if value is None:
            if not scale.null_allowed:
                problems.append("{}: scale {} does not permit a null score".format(code, scale.version))
            if raw_score.evidence_turn_ids:
                problems.append("{}: an unscoreable signal must cite no evidence".format(code))
        else:
            if value not in scale.values:
                problems.append(
                    "{}: score {!r} is not in scale {}".format(code, value, scale.version)
                )
            if raw_score.not_assessable:
                problems.append("{}: a scored signal cannot be marked not assessable".format(code))
            if value != 0 and not raw_score.evidence_turn_ids:
                problems.append(
                    "{}: a score above zero must cite at least one turn".format(code)
                )
            if value != 0 and not (raw_score.explanation or "").strip():
                problems.append("{}: a score above zero must carry an explanation".format(code))

        if raw_score.specificity_markers:
            if code not in taxonomy.specificity_signals:
                problems.append(
                    "{}: only {} may carry specificity markers".format(
                        code, ", ".join(sorted(taxonomy.specificity_signals)) or "no signal"
                    )
                )
            unknown_markers = [
                m for m in raw_score.specificity_markers
                if m not in taxonomy.specificity_markers
            ]
            if unknown_markers:
                problems.append(
                    "{}: unknown specificity markers: {}".format(
                        code, ", ".join(sorted(set(unknown_markers)))
                    )
                )
            if value is None:
                problems.append(
                    "{}: an unscoreable signal cannot carry specificity markers".format(code)
                )

        outside = [t for t in raw_score.evidence_turn_ids if t not in request.window_turn_ids]
        if outside:
            problems.append(
                "{}: evidence cites turns outside the assessed window: {}".format(
                    code, ", ".join(sorted(outside))
                )
            )
        return problems
