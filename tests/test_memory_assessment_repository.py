"""Binds the AssessmentRepository contract to the in-memory adapter."""

from __future__ import annotations

import unittest

from src.adapters.memory.assessments import InMemoryAssessmentRepository
from tests.contract.assessment_repository import AssessmentRepositoryContract


class InMemoryAssessmentRepositoryTest(AssessmentRepositoryContract, unittest.TestCase):
    def repository(self):
        return InMemoryAssessmentRepository()


class ScoreInvariants(unittest.TestCase):
    def test_a_null_score_must_be_marked_not_assessable(self):
        from src.domain.assessments.records import SignalScore

        with self.assertRaises(ValueError):
            SignalScore(
                id="s", assessment_id="a", signal_code="harm_intent",
                score_value=None, scale_version="scale_0_3_v0.1",
                not_assessable=False,
            )

    def test_a_scored_signal_cannot_be_marked_not_assessable(self):
        from src.domain.assessments.records import SignalScore

        with self.assertRaises(ValueError):
            SignalScore(
                id="s", assessment_id="a", signal_code="harm_intent",
                score_value=2, scale_version="scale_0_3_v0.1",
                not_assessable=True,
            )


if __name__ == "__main__":
    unittest.main()
