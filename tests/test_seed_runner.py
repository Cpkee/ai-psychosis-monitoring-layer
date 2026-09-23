"""Seed extraction runner — the screen runs first, the cache is honoured, and
DELAYED, OUTPUT_UNREADABLE and VALIDATION_FAILED stay distinct.

Every document and reply is a hand-written synthetic example. The extractor is
a recording fake, so each test can prove whether a model was called.
"""

from __future__ import annotations

import json
import unittest

from src.adapters.extractors.fake import FakeExtractor
from src.adapters.memory.seeds import (
    InMemoryExtractionCacheRepository,
    InMemorySeedRepository,
    InMemorySourceDocumentRepository,
)
from src.domain.seeds.extraction import (
    ExtractionOutputUnreadable,
    ExtractorRequestRejected,
    ExtractorUnavailable,
)
from src.domain.seeds.records import (
    BLOCKED_SEALED,
    DELAYED,
    CacheKey,
    EXTRACTED,
    FAILED,
    OUTPUT_UNREADABLE,
    SCREENED,
    VALIDATION_FAILED,
)
from src.modules.seeds.config import load_extraction, load_tiers, load_vocabulary
from src.modules.seeds.prompt import PromptRenderer
from src.modules.seeds.reply import SeedValidator
from src.modules.seeds.runner import SeedExtractionRunner
from src.modules.seeds.seal_screen import SealScreen
from tests.contract.seed_repositories import make_document
from tests.test_seal_screen import EXAMPLE_PROMPT, manifest_with
from tests.test_seed_extraction import raw_seed, reply

CONFIG = load_extraction("extraction_v0.1")
VOCABULARY = load_vocabulary("seed_vocabulary_v0.2")


def raising(error):
    def respond(_request):
        raise error
    return respond


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.documents = InMemorySourceDocumentRepository()
        self.cache = InMemoryExtractionCacheRepository()
        self.seeds = InMemorySeedRepository()
        self.document = self.documents.save(make_document())

    def runner(self, extractor, documents=None):
        return SeedExtractionRunner(
            documents=documents or self.documents, cache=self.cache, seeds=self.seeds,
            screen=SealScreen(CONFIG.max_span_sentences, manifest_with(EXAMPLE_PROMPT)),
            extractor=extractor, renderer=PromptRenderer(CONFIG, VOCABULARY),
            validator=SeedValidator(VOCABULARY, load_tiers("credibility_tiers_v0.1"), CONFIG),
            clock=lambda: "2026-01-01T00:00:00Z")

    def test_a_clear_document_is_screened_extracted_and_its_seeds_stored(self):
        extractor = FakeExtractor(reply(raw_seed(), raw_seed(theme_family="A3")))
        done = self.runner(extractor).process(self.document.id)

        self.assertEqual(done.status, EXTRACTED)
        self.assertEqual(len(extractor.requests), 1)
        seeds = self.seeds.list_for_document(self.document.id)
        self.assertEqual([s.theme_family for s in seeds], ["A2", "A3"])
        self.assertEqual({s.credibility_tier for s in seeds}, {"T1"})

    def test_the_request_carries_the_document_and_the_schema(self):
        extractor = FakeExtractor(reply())
        self.runner(extractor).process(self.document.id)
        request = extractor.requests[0]
        self.assertIn(self.document.text, request.prompt)
        self.assertIn("seeds", request.schema["properties"])

    def test_a_document_matching_a_sealed_prompt_never_reaches_the_extractor(self):
        """D-27: the most important property of this runner."""
        document = self.documents.save(make_document(
            "example-document-2", text="Example article. The user wrote: " + EXAMPLE_PROMPT))
        extractor = FakeExtractor(reply(raw_seed()))
        done = self.runner(extractor).process(document.id)

        self.assertEqual(done.status, BLOCKED_SEALED)
        self.assertEqual(extractor.requests, [])
        self.assertEqual(self.seeds.list_for_document(document.id), ())

    def test_the_upstream_paper_is_blocked_by_identifier(self):
        runner = SeedExtractionRunner(
            self.documents, self.cache, self.seeds, SealScreen(CONFIG.max_span_sentences),
            FakeExtractor(reply()), PromptRenderer(CONFIG, VOCABULARY),
            SeedValidator(VOCABULARY, load_tiers("credibility_tiers_v0.1"), CONFIG),
            lambda: "2026-01-01T00:00:00Z")
        document = self.documents.save(make_document(
            "example-document-2", text="Example abstract.", source_type="preprint",
            source_url="https://arxiv.org/abs/2509.10970v2", external_id="arXiv:2509.10970v2"))
        self.assertEqual(runner.process(document.id).status, BLOCKED_SEALED)

    def test_a_cached_reply_is_reused_without_calling_the_model(self):
        self.runner(FakeExtractor(reply(raw_seed()))).process(self.document.id)

        # A teammate's fresh database, sharing the cache.
        elsewhere = InMemorySourceDocumentRepository()
        elsewhere.save(make_document())
        self.seeds = InMemorySeedRepository()
        second = FakeExtractor(reply(raw_seed(theme_family="A1")))
        self.runner(second, documents=elsewhere).process(self.document.id)

        self.assertEqual(second.requests, [])
        self.assertEqual(self.seeds.list_for_document(self.document.id)[0].theme_family, "A2")

    def test_a_new_model_version_is_a_cache_miss(self):
        self.runner(FakeExtractor(reply(raw_seed()))).process(self.document.id)
        elsewhere = InMemorySourceDocumentRepository()
        elsewhere.save(make_document())
        self.seeds = InMemorySeedRepository()
        newer = FakeExtractor(reply(raw_seed()), model_version="fake_v0.2")
        self.runner(newer, documents=elsewhere).process(self.document.id)
        self.assertEqual(len(newer.requests), 1)

    def test_an_unreachable_extractor_delays_and_a_rerun_resumes(self):
        delayed = self.runner(FakeExtractor(raising(ExtractorUnavailable("HTTP 429"))))\
            .process(self.document.id)
        self.assertEqual(delayed.status, DELAYED)
        self.assertIn("429", delayed.status_detail)
        self.assertIsNone(delayed.failure_code)

        done = self.runner(FakeExtractor(reply(raw_seed()))).process(self.document.id)
        self.assertEqual(done.status, EXTRACTED)

    def test_an_unreadable_reply_fails_and_is_not_cached(self):
        done = self.runner(FakeExtractor("not json at all")).process(self.document.id)
        self.assertEqual((done.status, done.failure_code), (FAILED, OUTPUT_UNREADABLE))
        key = CacheKey(self.document.content_hash,
                       PromptRenderer(CONFIG, VOCABULARY).version, "fake_v0.1")
        self.assertIsNone(self.cache.get(key))

    def test_an_adapter_reported_unreadable_reply_fails_the_same_way(self):
        done = self.runner(FakeExtractor(raising(ExtractionOutputUnreadable("blocked"))))\
            .process(self.document.id)
        self.assertEqual((done.status, done.failure_code), (FAILED, OUTPUT_UNREADABLE))

    def test_a_contract_breaking_reply_fails_validation_with_our_message_only(self):
        secret = "PRIVATE MODEL TEXT"
        bad = reply(raw_seed(theme_family="Grandiose Delusions", arc_summary=secret))
        done = self.runner(FakeExtractor(bad)).process(self.document.id)

        self.assertEqual((done.status, done.failure_code), (FAILED, VALIDATION_FAILED))
        self.assertIn("vocabulary A", done.status_detail)
        self.assertNotIn(secret, done.status_detail)
        self.assertEqual(self.seeds.list_for_document(self.document.id), ())

    def test_a_rejected_request_stops_the_run_and_leaves_the_document_screened(self):
        with self.assertRaises(ExtractorRequestRejected):
            self.runner(FakeExtractor(raising(ExtractorRequestRejected("HTTP 403"))))\
                .process(self.document.id)
        self.assertEqual(self.documents.get(self.document.id).status, SCREENED)

    def test_finished_documents_are_left_alone(self):
        self.runner(FakeExtractor(reply(raw_seed()))).process(self.document.id)
        again = FakeExtractor(reply(raw_seed()))
        self.assertEqual(self.runner(again).process(self.document.id).status, EXTRACTED)
        self.assertEqual(again.requests, [])

    def test_re_running_a_reset_document_is_a_no_op_not_a_crash(self):
        """Same prompt and model: the cached reply rebuilds the same seed ids."""
        import dataclasses

        self.runner(FakeExtractor(reply(raw_seed(), raw_seed()))).process(self.document.id)
        self.documents.update(dataclasses.replace(self.documents.get(self.document.id),
                                                  status=SCREENED), EXTRACTED)
        again = FakeExtractor(reply(raw_seed()))
        done = self.runner(again).process(self.document.id)

        self.assertEqual(done.status, EXTRACTED)
        self.assertIn("already stored", done.status_detail)
        self.assertEqual(again.requests, [])
        self.assertEqual(len(self.seeds.list_for_document(self.document.id)), 2)

    def test_a_document_with_no_account_is_extracted_with_no_seeds(self):
        done = self.runner(FakeExtractor(json.dumps({"seeds": []}))).process(self.document.id)
        self.assertEqual(done.status, EXTRACTED)
        self.assertIn("0 seed", done.status_detail)


if __name__ == "__main__":
    unittest.main()
