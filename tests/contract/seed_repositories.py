"""Seed-pipeline repository contracts — run against every implementation.

Every document text here is a hand-written synthetic example.
"""

from __future__ import annotations

import dataclasses

from src.domain.seeds.overlap import (
    BLOCKED,
    CLEAR,
    EXCLUDE,
    FLAGGED,
    HARM_TYPE_MATCH,
    KEEP,
    FlagReview,
    OverlapCheck,
)
from src.domain.seeds.records import (
    DELAYED,
    EXTRACTED,
    FAILED,
    SCREENED,
    SNAPSHOTTED,
    VALIDATION_FAILED,
    CacheKey,
    ExtractionCacheEntry,
    QueryLogEntry,
    Seed,
    SourceDocument,
    content_hash,
)
from src.domain.seeds.repository import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
    DocumentNotFound,
    OverlapCheckAlreadyExists,
    OverlapCheckNotFound,
    ReviewConflict,
    SeedAlreadyExists,
    RelevanceConflict,
    SelectionConflict,
    SplitConflict,
)
from src.domain.seeds.selection import (
    CHOOSE,
    DEVELOPMENT,
    EXCLUDE,
    FLAG_REVIEW,
    GOLD,
    INCLUDE,
    SILVER,
    CoverageCell,
    ExposureEvent,
    RelevanceDecision,
    Selection,
    SelectionEntry,
)

EXAMPLE_TEXT = ("Example report. A 71-year-old widower described talking to a chatbot "
                "every evening and came to believe it had chosen him for a mission.")


def make_query(query_id="example-query-log-1", executed_at="2026-01-01T00:00:00Z"):
    return QueryLogEntry(
        id=query_id, source="pubmed", query_id="example-query", query_text="example terms",
        query_config_version="queries_v0.1", executed_at=executed_at,
        result_ids=("PMID:1", "PMID:2"))


def make_document(document_id="example-document-1", text=EXAMPLE_TEXT,
                  retrieved_at="2026-01-01T00:00:00Z", **overrides):
    fields = dict(
        id=document_id, content_hash=content_hash(text), source_type="clinical_case_report",
        source_url="https://example.org/report", title="Example report", text=text,
        retrieved_at=retrieved_at, fetcher_version="example_fetcher_v0.1",
        external_id="PMID:1", publication_date="2026", query_log_id=None)
    fields.update(overrides)
    return SourceDocument(**fields)


def make_entry(document=None, prompt_version="extraction_prompt_v0.1#example",
               reply_text='{"seeds": []}'):
    document = document or make_document()
    return ExtractionCacheEntry(
        key=CacheKey(document.content_hash, prompt_version, "fake_v0.1"),
        provider="fake", model="deterministic", reply_text=reply_text,
        created_at="2026-01-01T00:00:00Z")


def make_seed(seed_id="example-seed-1", document=None, **overrides):
    document = document or make_document()
    fields = dict(
        id=seed_id, seed_version=1, account_kind="individual", source_document_id=document.id,
        content_hash=document.content_hash, source_url=document.source_url,
        source_type=document.source_type, credibility_tier="T1",
        retrieved_at=document.retrieved_at, publication_date="2026", theme_family="A1",
        raw_theme_terms=("chosen for a mission",), arc_summary="Example arc in our own words.",
        reported_phase_progression=("phase_1", "phase_3"), explicitness_candidate="explicit",
        harm_type_candidate=None, companion_behaviour_reported=("affirmed",),
        extraction_provider="fake", extraction_model="deterministic",
        extraction_model_version="fake_v0.1",
        extraction_prompt_version="extraction_prompt_v0.1#example",
        vocabulary_version="seed_vocabulary_v0.2",
        credibility_tier_version="credibility_tiers_v0.1", created_at="2026-01-01T00:00:00Z")
    fields.update(overrides)
    return Seed(**fields)


class SourceDocumentRepositoryContract:
    def repository(self):
        raise NotImplementedError

    def test_query_log_round_trips_in_order(self):
        repo = self.repository()
        first = repo.log_query(make_query())
        second = repo.log_query(make_query("example-query-log-2", "2026-01-01T00:00:01Z"))
        self.assertEqual(repo.list_queries(), (first, second))

    def test_save_get_and_find_by_hash(self):
        repo = self.repository()
        saved = repo.save(make_document())
        self.assertEqual(repo.get(saved.id), saved)
        self.assertEqual(repo.find_by_hash(saved.content_hash), saved)
        self.assertIsNone(repo.find_by_hash(content_hash("other text")))

    def test_identical_content_is_one_snapshot(self):
        repo = self.repository()
        repo.save(make_document())
        with self.assertRaises(DocumentAlreadyExists):
            repo.save(make_document("example-document-2"))

    def test_get_unknown_raises(self):
        with self.assertRaises(DocumentNotFound):
            self.repository().get("no-such-document")

    def test_update_is_conditional_on_the_status_read(self):
        repo = self.repository()
        document = repo.save(make_document())
        screened = repo.update(dataclasses.replace(document, status=SCREENED), SNAPSHOTTED)
        self.assertEqual(repo.get(document.id).status, SCREENED)
        with self.assertRaises(ConcurrentDocumentUpdate):
            repo.update(dataclasses.replace(screened, status=DELAYED), SNAPSHOTTED)

    def test_a_failure_round_trips_with_its_code_and_detail(self):
        repo = self.repository()
        document = repo.save(make_document())
        failed = dataclasses.replace(document, status=FAILED, failure_code=VALIDATION_FAILED,
                                     status_detail="seed 0: arc_summary is required")
        repo.update(failed, SNAPSHOTTED)
        self.assertEqual(repo.get(document.id), failed)

    def test_list_unfinished_excludes_terminal_documents_oldest_first(self):
        repo = self.repository()
        later = repo.save(make_document("example-document-2", text="Second example.",
                                        retrieved_at="2026-01-02T00:00:00Z"))
        earlier = repo.save(make_document())
        done = repo.save(make_document("example-document-3", text="Third example."))
        repo.update(dataclasses.replace(done, status=EXTRACTED), SNAPSHOTTED)
        self.assertEqual([d.id for d in repo.list_unfinished()], [earlier.id, later.id])


class ProcessedVersionsContract:
    """D-45: the document remembers which extraction is current."""

    def repository(self):
        raise NotImplementedError

    def test_processed_versions_round_trip_through_an_update(self):
        repo = self.repository()
        document = repo.save(make_document())
        done = dataclasses.replace(document, status=EXTRACTED,
                                   processed_prompt_version="extraction_prompt_v0.3#example",
                                   processed_model_version="fake_v0.1")
        repo.update(done, SNAPSHOTTED)
        self.assertEqual(repo.get(document.id), done)

    def test_list_by_status_finds_finished_documents_oldest_first(self):
        repo = self.repository()
        extracted = repo.save(make_document())
        failed = repo.save(make_document("example-document-2", text="Second example.",
                                         retrieved_at="2026-01-02T00:00:00Z"))
        repo.save(make_document("example-document-3", text="Third example."))
        repo.update(dataclasses.replace(extracted, status=EXTRACTED), SNAPSHOTTED)
        repo.update(dataclasses.replace(failed, status=FAILED, failure_code=VALIDATION_FAILED),
                    SNAPSHOTTED)
        self.assertEqual([d.id for d in repo.list_by_status(EXTRACTED, FAILED)],
                         [extracted.id, failed.id])
        self.assertEqual(repo.list_by_status(DELAYED), ())


class ExtractionCacheRepositoryContract:
    """Needs the document stored first where storage enforces the reference."""

    def repository(self):
        raise NotImplementedError

    def test_a_miss_is_none(self):
        self.assertIsNone(self.repository().get(make_entry().key))

    def test_put_then_get(self):
        repo = self.repository()
        entry = repo.put(make_entry())
        self.assertEqual(repo.get(entry.key), entry)

    def test_entries_are_immutable_first_write_wins(self):
        repo = self.repository()
        first = repo.put(make_entry())
        second = repo.put(make_entry(reply_text='{"seeds": [{}]}'))
        self.assertEqual(second, first)
        self.assertEqual(repo.get(first.key).reply_text, '{"seeds": []}')

    def test_a_different_prompt_version_is_a_different_entry(self):
        repo = self.repository()
        repo.put(make_entry())
        self.assertIsNone(repo.get(make_entry(prompt_version="extraction_prompt_v0.2#x").key))


class SeedRepositoryContract:
    def repository(self):
        raise NotImplementedError

    def test_save_all_and_list_in_extraction_order(self):
        repo = self.repository()
        seeds = (make_seed("example-seed-b"),
                 make_seed("example-seed-a", theme_family=None, account_kind="pattern"))
        repo.save_all(seeds)
        self.assertEqual(repo.list_for_document("example-document-1"), seeds)

    def test_no_theme_stays_null(self):
        repo = self.repository()
        repo.save_all((make_seed(theme_family=None, harm_type_candidate=None),))
        stored = repo.list_for_document("example-document-1")[0]
        self.assertIsNone(stored.theme_family)
        self.assertIsNone(stored.harm_type_candidate)

    def test_a_second_extraction_of_the_same_document_is_kept_beside_the_first(self):
        """D-45: positions are unique per extraction, not per document."""
        repo = self.repository()
        repo.save_all((make_seed("example-seed-v1"),))
        repo.save_all((make_seed("example-seed-v2", extraction_model_version="fake_v0.2",
                                 created_at="2026-01-02T00:00:00Z"),))
        self.assertEqual([s.id for s in repo.list_for_document("example-document-1")],
                         ["example-seed-v1", "example-seed-v2"])

    def test_a_batch_with_a_duplicate_stores_nothing(self):
        repo = self.repository()
        repo.save_all((make_seed(),))
        with self.assertRaises(SeedAlreadyExists):
            repo.save_all((make_seed("example-seed-2"), make_seed()))
        self.assertEqual([s.id for s in repo.list_for_document("example-document-1")],
                         ["example-seed-1"])

    def test_a_seed_without_an_arc_summary_cannot_exist(self):
        with self.assertRaises(ValueError):
            make_seed(arc_summary="  ")


EXAMPLE_MANIFEST_SHA256 = "a" * 64


def make_check(check_id="example-check-1", seed_id="example-seed-1", result=FLAGGED,
               reasons=(HARM_TYPE_MATCH,), screen_version="overlap_screen_v0.1#example",
               manifest_sha256=EXAMPLE_MANIFEST_SHA256, checked_at="2026-01-01T00:00:00Z"):
    return OverlapCheck(check_id, seed_id, result, reasons, screen_version, manifest_sha256,
                        checked_at)


def make_review(review_id="example-review-1", check_id="example-check-1", decision=KEEP,
                supersedes=None, recorded_at="2026-01-02T00:00:00Z"):
    return FlagReview(review_id, check_id, decision, "Example reason.", "example-actor",
                      recorded_at, supersedes)


class SeedFilterRepositoryContract:
    """The store needs seeds ``example-seed-1`` and ``example-seed-2``."""

    def repository(self):
        raise NotImplementedError

    def test_a_check_round_trips_with_its_reasons_in_order(self):
        repo = self.repository()
        check = make_check(result=BLOCKED, reasons=("sealed_span:arc_summary",
                                                    "sealed_span:raw_theme_terms"))
        self.assertEqual(repo.record_check(check), check)
        self.assertEqual(repo.list_checks(check.screen_version, check.manifest_sha256), (check,))

    def test_a_clear_check_has_no_reasons(self):
        repo = self.repository()
        repo.record_check(make_check(result=CLEAR, reasons=()))
        self.assertEqual(repo.list_checks("overlap_screen_v0.1#example",
                                          EXAMPLE_MANIFEST_SHA256)[0].reasons, ())

    def test_the_first_check_of_a_seed_under_a_screen_wins(self):
        repo = self.repository()
        first = repo.record_check(make_check())
        again = repo.record_check(make_check("example-check-2", result=CLEAR, reasons=()))
        self.assertEqual(again, first)
        self.assertEqual(len(repo.list_checks(first.screen_version, first.manifest_sha256)), 1)

    def test_another_screen_or_manifest_is_another_check(self):
        repo = self.repository()
        repo.record_check(make_check())
        repo.record_check(make_check("example-check-2", screen_version="overlap_screen_v0.2#x"))
        repo.record_check(make_check("example-check-3", manifest_sha256="b" * 64))
        self.assertEqual([c.id for c in repo.list_checks("overlap_screen_v0.1#example",
                                                          EXAMPLE_MANIFEST_SHA256)],
                         ["example-check-1"])

    def test_checks_are_listed_oldest_first(self):
        repo = self.repository()
        repo.record_check(make_check("example-check-b", checked_at="2026-01-02T00:00:00Z"))
        repo.record_check(make_check("example-check-a", seed_id="example-seed-2",
                                     checked_at="2026-01-01T00:00:00Z"))
        self.assertEqual([c.id for c in repo.list_checks("overlap_screen_v0.1#example",
                                                          EXAMPLE_MANIFEST_SHA256)],
                         ["example-check-a", "example-check-b"])

    def test_an_id_already_used_for_another_seed_is_refused(self):
        repo = self.repository()
        repo.record_check(make_check())
        with self.assertRaises(OverlapCheckAlreadyExists):
            repo.record_check(make_check(seed_id="example-seed-2"))

    def test_a_check_has_no_review_until_one_is_saved(self):
        repo = self.repository()
        repo.record_check(make_check())
        self.assertIsNone(repo.latest_review("example-check-1"))
        review = repo.save_review(make_review())
        self.assertEqual(repo.latest_review("example-check-1"), review)

    def test_corrections_chain_and_the_latest_wins(self):
        repo = self.repository()
        repo.record_check(make_check())
        repo.save_review(make_review())
        repo.save_review(make_review("example-review-2", decision=EXCLUDE,
                                     supersedes="example-review-1"))
        third = repo.save_review(make_review("example-review-3", supersedes="example-review-2"))
        self.assertEqual(repo.latest_review("example-check-1"), third)

    def test_a_second_first_review_is_a_conflict(self):
        repo = self.repository()
        repo.record_check(make_check())
        repo.save_review(make_review())
        with self.assertRaises(ReviewConflict):
            repo.save_review(make_review("example-review-2", decision=EXCLUDE))
        self.assertEqual(repo.latest_review("example-check-1").id, "example-review-1")

    def test_superseding_a_review_twice_is_a_conflict(self):
        repo = self.repository()
        repo.record_check(make_check())
        repo.save_review(make_review())
        repo.save_review(make_review("example-review-2", supersedes="example-review-1"))
        with self.assertRaises(ReviewConflict):
            repo.save_review(make_review("example-review-3", supersedes="example-review-1"))

    def test_a_correction_cannot_supersede_another_checks_review(self):
        repo = self.repository()
        repo.record_check(make_check())
        repo.record_check(make_check("example-check-2", seed_id="example-seed-2"))
        repo.save_review(make_review())
        with self.assertRaises(ReviewConflict):
            repo.save_review(make_review("example-review-2", check_id="example-check-2",
                                         supersedes="example-review-1"))

    def test_a_reused_review_id_is_a_conflict(self):
        repo = self.repository()
        repo.record_check(make_check())
        repo.record_check(make_check("example-check-2", seed_id="example-seed-2"))
        repo.save_review(make_review())
        with self.assertRaises(ReviewConflict):
            repo.save_review(make_review(check_id="example-check-2"))

    def test_a_review_of_an_unknown_check_is_refused(self):
        with self.assertRaises(OverlapCheckNotFound):
            self.repository().save_review(make_review(check_id="example-missing-check"))


EXAMPLE_CELL = CoverageCell(theme_family="A1", explicitness="explicit", harm="harm_described",
                            gold=1, silver=0, development=1, unchosen=2, individual=1, pattern=1,
                            tiers=(("T1", 1), ("T2", 1)))


def make_selection(selection_id="example-selection-1", version=1, supersedes=None,
                   entries=(("example-seed-1", GOLD), ("example-seed-2", DEVELOPMENT)),
                   gaps=("theme family A2: 0 chosen, target at least 3",)):
    return Selection(
        id=selection_id, selection_version=version,
        entries=tuple(SelectionEntry(seed_id, 1, split) for seed_id, split in entries),
        actor_id="example-actor", created_at="2026-01-0{}T00:00:00Z".format(version),
        coverage_targets_version="coverage_targets_v0.1#example", coverage=(EXAMPLE_CELL,),
        gaps=gaps, pattern_count=1, supersedes=supersedes)


class SeedSelectionRepositoryContract:
    """The store needs seeds ``example-seed-1`` and ``example-seed-2``."""

    def repository(self):
        raise NotImplementedError

    def test_nothing_is_chosen_until_a_selection_is_saved(self):
        repo = self.repository()
        self.assertIsNone(repo.latest())
        self.assertEqual(repo.list_splits(), ())

    def test_a_selection_round_trips_with_its_coverage_and_gaps(self):
        repo = self.repository()
        selection = repo.save(make_selection())
        self.assertEqual(repo.latest(), selection)
        self.assertEqual(repo.list_splits(), (("example-seed-1", GOLD),
                                              ("example-seed-2", DEVELOPMENT)))

    def test_a_dropped_seed_keeps_its_split(self):
        repo = self.repository()
        repo.save(make_selection())
        second = repo.save(make_selection("example-selection-2", 2, "example-selection-1",
                                          entries=(("example-seed-1", GOLD),), gaps=()))
        self.assertEqual(repo.latest(), second)
        self.assertIn(("example-seed-2", DEVELOPMENT), repo.list_splits())

    def test_a_seed_never_changes_split_and_nothing_is_stored(self):
        repo = self.repository()
        first = repo.save(make_selection())
        with self.assertRaises(SplitConflict):
            repo.save(make_selection("example-selection-2", 2, "example-selection-1",
                                     entries=(("example-seed-1", GOLD),
                                              ("example-seed-2", SILVER))))
        self.assertEqual(repo.latest(), first)
        self.assertIn(("example-seed-2", DEVELOPMENT), repo.list_splits())
        repo.save(make_selection("example-selection-2", 2, "example-selection-1"))

    def test_a_split_taken_by_a_dropped_seed_still_binds_it(self):
        repo = self.repository()
        repo.save(make_selection())
        repo.save(make_selection("example-selection-2", 2, "example-selection-1",
                                 entries=(("example-seed-1", GOLD),)))
        with self.assertRaises(SplitConflict):
            repo.save(make_selection("example-selection-3", 3, "example-selection-2",
                                     entries=(("example-seed-2", GOLD),)))

    def test_the_history_cannot_fork(self):
        repo = self.repository()
        repo.save(make_selection())
        repo.save(make_selection("example-selection-2", 2, "example-selection-1"))
        for fork in (make_selection("example-selection-3", 3, "example-selection-1"),
                     make_selection("example-selection-4", 2, "example-selection-2"),
                     make_selection("example-selection-5"),
                     make_selection("example-selection-6", 3, "example-missing-selection"),
                     make_selection("example-selection-1", 3, "example-selection-2")):
            with self.subTest(selection=fork.id), self.assertRaises(SelectionConflict):
                repo.save(fork)
        self.assertEqual(repo.latest().id, "example-selection-2")


class SeedExposureRepositoryContract:
    """The store needs seeds ``example-seed-1`` and ``example-seed-2``."""

    def repository(self):
        raise NotImplementedError

    def test_the_first_exposure_wins(self):
        repo = self.repository()
        first = ExposureEvent("example-seed-1", "example-actor", CHOOSE, "2026-01-01T00:00:00Z")
        self.assertEqual(repo.record(first), first)
        again = ExposureEvent("example-seed-1", "example-actor", CHOOSE, "2026-01-05T00:00:00Z")
        self.assertEqual(repo.record(again), first)
        self.assertEqual(repo.list_events(), (first,))

    def test_events_are_listed_oldest_first(self):
        repo = self.repository()
        later = repo.record(ExposureEvent("example-seed-1", "example-actor", CHOOSE,
                                          "2026-01-02T00:00:00Z"))
        earlier = repo.record(ExposureEvent("example-seed-2", "example-other-actor",
                                            FLAG_REVIEW, "2026-01-01T00:00:00Z"))
        also = repo.record(ExposureEvent("example-seed-1", "example-actor", FLAG_REVIEW,
                                         "2026-01-03T00:00:00Z"))
        self.assertEqual(repo.list_events(), (earlier, later, also))


def make_decision(decision_id="example-decision-1", seed_id="example-seed-1", decision=EXCLUDE,
                  supersedes=None):
    return RelevanceDecision(decision_id, seed_id, decision, "Example reason.", "example-actor",
                             "2026-01-01T00:00:00Z", supersedes)


class SeedRelevanceRepositoryContract:
    """The store needs seeds ``example-seed-1`` and ``example-seed-2``."""

    def repository(self):
        raise NotImplementedError

    def test_an_exclusion_is_the_latest_decision_for_its_seed(self):
        repo = self.repository()
        self.assertEqual(repo.list_latest(), ())
        decision = repo.save(make_decision())
        self.assertEqual(repo.list_latest(), (decision,))

    def test_undoing_supersedes_and_the_history_stays(self):
        repo = self.repository()
        repo.save(make_decision())
        undone = repo.save(make_decision("example-decision-2", decision=INCLUDE,
                                         supersedes="example-decision-1"))
        again = repo.save(make_decision("example-decision-3", supersedes="example-decision-2"))
        self.assertEqual(repo.list_latest(), (again,))
        self.assertEqual(undone.supersedes, "example-decision-1")

    def test_latest_decisions_are_listed_by_seed(self):
        repo = self.repository()
        second = repo.save(make_decision("example-decision-b", seed_id="example-seed-2"))
        first = repo.save(make_decision("example-decision-a"))
        self.assertEqual(repo.list_latest(), (first, second))

    def test_the_history_cannot_fork(self):
        repo = self.repository()
        repo.save(make_decision())
        repo.save(make_decision("example-decision-2", seed_id="example-seed-2"))
        for fork in (make_decision("example-decision-3"),                  # a second first decision
                     make_decision("example-decision-4", seed_id="example-seed-2",
                                   decision=INCLUDE, supersedes="example-decision-1"),
                     make_decision("example-decision-1", seed_id="example-seed-2",
                                   decision=INCLUDE, supersedes="example-decision-2")):
            with self.subTest(decision=fork.id), self.assertRaises(RelevanceConflict):
                repo.save(fork)
        repo.save(make_decision("example-decision-5", decision=INCLUDE,
                                supersedes="example-decision-1"))
        with self.assertRaises(RelevanceConflict):
            repo.save(make_decision("example-decision-6", decision=INCLUDE,
                                    supersedes="example-decision-1"))

    def test_an_inclusion_only_ever_undoes_an_exclusion(self):
        with self.assertRaises(ValueError):
            make_decision(decision=INCLUDE)
