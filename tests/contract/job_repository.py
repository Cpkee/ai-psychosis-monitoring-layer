"""JobRepository contract — run against every implementation (section 17)."""

from __future__ import annotations

from src.domain.analysis.records import (
    AnalysisJob,
    AnalysisRequest,
    ArtefactVersions,
    ProcessingStatus,
)
from src.domain.analysis.repository import (
    DuplicateAnalysisRequest,
    JobAlreadyExists,
    JobNotFound,
)

VERSIONS = ArtefactVersions(
    taxonomy_version="taxonomy_v0.1",
    scale_version="scale_0_3_v0.1",
    rubric_version="rubric_v0.1",
    judge_configuration_version="fake_judge_v0.1",
    schema_version="assessment_v0.1",
)


def make_job(**overrides) -> AnalysisJob:
    fields = dict(
        id="example-job-1",
        session_id="example-session-1",
        through_turn_id="example-turn-1",
        status=ProcessingStatus.PENDING,
        attempt_count=0,
        taxonomy_version=VERSIONS.taxonomy_version,
        scale_version=VERSIONS.scale_version,
        rubric_version=VERSIONS.rubric_version,
        judge_configuration_version=VERSIONS.judge_configuration_version,
        schema_version=VERSIONS.schema_version,
        requested_at="2026-01-01T00:00:00Z",
    )
    fields.update(overrides)
    return AnalysisJob(**fields)


class JobRepositoryContract:
    """Subclass alongside ``unittest.TestCase`` and implement :meth:`repository`."""

    def repository(self):
        raise NotImplementedError

    def test_create_and_get(self):
        repo = self.repository()
        created = repo.create(make_job())
        self.assertEqual(repo.get(created.id), created)

    def test_get_unknown_job_raises(self):
        with self.assertRaises(JobNotFound):
            self.repository().get("no-such-job")

    def test_duplicate_id_raises(self):
        repo = self.repository()
        repo.create(make_job())
        with self.assertRaises((JobAlreadyExists, DuplicateAnalysisRequest)):
            repo.create(make_job())

    def test_equivalent_request_is_rejected(self):
        """Section 13: jobs are unique per window and artefact-version set."""
        repo = self.repository()
        repo.create(make_job())
        with self.assertRaises(DuplicateAnalysisRequest):
            repo.create(make_job(id="example-job-2"))

    def test_a_different_rubric_version_is_a_different_job(self):
        """Re-analysing the same window under a new rubric is legitimate work."""
        repo = self.repository()
        repo.create(make_job())
        second = repo.create(make_job(id="example-job-2", rubric_version="rubric_v0.2"))
        self.assertEqual(len(repo.list_for_session("example-session-1")), 2)
        self.assertEqual(second.rubric_version, "rubric_v0.2")

    def test_find_equivalent_returns_the_existing_job(self):
        repo = self.repository()
        created = repo.create(make_job())
        found = repo.find_equivalent(
            AnalysisRequest(
                session_id="example-session-1",
                through_turn_id="example-turn-1",
                versions=VERSIONS,
            )
        )
        self.assertEqual(found, created)

    def test_find_equivalent_returns_none_when_absent(self):
        repo = self.repository()
        self.assertIsNone(
            repo.find_equivalent(
                AnalysisRequest(
                    session_id="example-session-1",
                    through_turn_id="example-turn-1",
                    versions=VERSIONS,
                )
            )
        )

    def test_list_for_session_is_scoped_and_ordered(self):
        repo = self.repository()
        repo.create(make_job(requested_at="2026-01-01T00:00:00Z"))
        repo.create(
            make_job(
                id="example-job-2",
                through_turn_id="example-turn-2",
                requested_at="2026-01-01T00:00:01Z",
            )
        )
        jobs = repo.list_for_session("example-session-1")
        self.assertEqual([j.id for j in jobs], ["example-job-1", "example-job-2"])
        self.assertEqual(repo.list_for_session("other-session"), [])

    def test_failed_job_must_carry_a_failure_code(self):
        with self.assertRaises(ValueError):
            make_job(status=ProcessingStatus.FAILED)

    def test_completed_job_must_carry_a_completion_time(self):
        with self.assertRaises(ValueError):
            make_job(status=ProcessingStatus.COMPLETED)
