"""Seed-pipeline repository contracts — run against every implementation.

Every document text here is a hand-written synthetic example.
"""

from __future__ import annotations

import dataclasses

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
    SeedAlreadyExists,
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
        id=seed_id, seed_version=1, source_document_id=document.id,
        content_hash=document.content_hash, source_url=document.source_url,
        source_type=document.source_type, credibility_tier="T1",
        retrieved_at=document.retrieved_at, publication_date="2026", theme_family="A1",
        raw_theme_terms=("chosen for a mission",), stated_age=71,
        age_evidence="A 71-year-old widower", arc_summary="Example arc in our own words.",
        reported_phase_progression=("phase_1", "phase_3"), explicitness_candidate="explicit",
        harm_type_candidate=None, companion_behaviour_reported=("affirmed",),
        extraction_provider="fake", extraction_model="deterministic",
        extraction_model_version="fake_v0.1",
        extraction_prompt_version="extraction_prompt_v0.1#example",
        vocabulary_version="seed_vocabulary_v0.1",
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
        seeds = (make_seed("example-seed-b"), make_seed("example-seed-a", stated_age=None,
                                                        age_evidence=None, theme_family=None))
        repo.save_all(seeds)
        self.assertEqual(repo.list_for_document("example-document-1"), seeds)

    def test_an_unstated_age_stays_null(self):
        repo = self.repository()
        repo.save_all((make_seed(stated_age=None, age_evidence=None),))
        self.assertIsNone(repo.list_for_document("example-document-1")[0].stated_age)

    def test_a_batch_with_a_duplicate_stores_nothing(self):
        repo = self.repository()
        repo.save_all((make_seed(),))
        with self.assertRaises(SeedAlreadyExists):
            repo.save_all((make_seed("example-seed-2"), make_seed()))
        self.assertEqual([s.id for s in repo.list_for_document("example-document-1")],
                         ["example-seed-1"])

    def test_a_stated_age_without_evidence_cannot_exist(self):
        with self.assertRaises(ValueError):
            make_seed(age_evidence=None)
