"""Source collectors, snapshotting, and the extractor adapters — no network.

PubMed and arXiv responses are small hand-written examples in each service's
real format. Provider adapters run against a recording fake HTTP client.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from src.adapters.extractors.gemini import GeminiExtractor
from src.adapters.extractors.ollama import OllamaExtractor
from src.adapters.extractors.openai import OpenAIExtractor
from src.adapters.http import HttpRejected, HttpUnavailable
from src.adapters.memory.seeds import InMemorySourceDocumentRepository
from src.adapters.sources.arxiv import ArxivClient, parse_feed
from src.adapters.sources.manual import ManualEntry, ManualFetcher, html_to_text
from src.adapters.sources.pubmed import PubMedClient, parse_efetch, source_type_for
from src.domain.seeds.collection import FetchedDocument, SearchResult, UnsupportedDocument
from src.domain.seeds.extraction import (
    ExtractionOutputUnreadable,
    ExtractionRequest,
    ExtractorRequestRejected,
    ExtractorUnavailable,
)
from src.modules.seeds.collector import SeedCollector
from src.modules.seeds.config import QuerySpec, UnknownSourceType, load_tiers

EFETCH = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>11111111</PMID>
      <Article>
        <Journal><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
        <ArticleTitle>Example case of chatbot-reinforced beliefs in an older adult</ArticleTitle>
        <Abstract>
          <AbstractText Label="CASE">An example <i>78-year-old</i> woman chatted with an AI companion daily.</AbstractText>
          <AbstractText Label="OUTCOME">Example outcome text.</AbstractText>
        </Abstract>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
          <PublicationType>Case Reports</PublicationType>
        </PublicationTypeList>
      </Article>
    </MedlineCitation>
    <PubmedData><ArticleIdList><ArticleId IdType="doi">10.0000/example.1</ArticleId></ArticleIdList></PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>22222222</PMID>
      <Article><ArticleTitle>Example title with no abstract</ArticleTitle></Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2601.01234v2</id>
    <published>2026-01-05T00:00:00Z</published>
    <title>Example: Companion
      Chatbots and Attachment</title>
    <summary>  An example abstract about   older users. </summary>
    <arxiv:doi>10.0000/example.2</arxiv:doi>
  </entry>
</feed>"""


class FakeHttp:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append(("GET", url, params, headers))
        if self.error:
            raise self.error
        return self.responses.pop(0)

    def post_json(self, url, body, headers=None):
        self.calls.append(("POST", url, body, headers))
        if self.error:
            raise self.error
        return self.responses.pop(0)


class PubMed(unittest.TestCase):
    def test_efetch_records_become_title_plus_abstract_snapshots(self):
        (document,) = parse_efetch(EFETCH)
        self.assertEqual(document.source_type, "clinical_case_report")
        self.assertEqual(document.source_url, "https://pubmed.ncbi.nlm.nih.gov/11111111/")
        self.assertEqual(document.external_id, "PMID:11111111 DOI:10.0000/example.1")
        self.assertEqual(document.publication_date, "2025")
        self.assertIn("CASE: An example 78-year-old woman", document.text)
        self.assertTrue(document.text.startswith("Example case of chatbot-reinforced"))

    def test_source_type_comes_from_publication_types(self):
        self.assertEqual(source_type_for(["Journal Article"]), "peer_reviewed_article")
        self.assertEqual(source_type_for(["Journal Article", "Case Reports"]),
                         "clinical_case_report")
        self.assertEqual(source_type_for(["Editorial"]), "secondary_report")

    def test_search_logs_every_id_even_those_without_an_abstract(self):
        http = FakeHttp([json.dumps({"esearchresult": {"idlist": ["11111111", "22222222"]}})
                         .encode(), EFETCH])
        result = PubMedClient(http, api_key="example-key").search("example terms", 5)
        self.assertEqual(result.result_ids, ("PMID:11111111", "PMID:22222222"))
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(http.calls[0][2]["term"], "example terms")
        self.assertEqual(http.calls[0][2]["api_key"], "example-key")

    def test_no_results_makes_no_fetch(self):
        http = FakeHttp([json.dumps({"esearchresult": {"idlist": []}}).encode()])
        self.assertEqual(PubMedClient(http).search("example", 5), SearchResult((), ()))
        self.assertEqual(len(http.calls), 1)


class Arxiv(unittest.TestCase):
    def test_entries_become_preprint_snapshots(self):
        (document,) = parse_feed(ATOM)
        self.assertEqual(document.source_type, "preprint")
        self.assertEqual(document.source_url, "https://arxiv.org/abs/2601.01234v2")
        self.assertEqual(document.external_id, "arXiv:2601.01234v2 DOI:10.0000/example.2")
        self.assertEqual(document.title, "Example: Companion Chatbots and Attachment")
        self.assertIn("An example abstract about older users.", document.text)
        self.assertEqual(document.publication_date, "2026-01-05")

    def test_search_reports_arxiv_ids(self):
        result = ArxivClient(FakeHttp([ATOM])).search("abs:example", 5)
        self.assertEqual(result.result_ids, ("arXiv:2601.01234v2",))


class Manual(unittest.TestCase):
    def test_html_is_reduced_to_text_without_scripts_or_navigation(self):
        title, text = html_to_text(
            "<html><head><title>Example story</title><script>var x=1;</script></head>"
            "<body><nav>Menu</nav><p>First paragraph.</p><p>Second   paragraph.</p></body></html>")
        self.assertEqual(title, "Example story")
        self.assertEqual(text, "First paragraph.\nSecond paragraph.")

    def test_a_url_is_fetched_and_titled(self):
        http = FakeHttp([b"<html><title>Example</title><p>Example story text.</p></html>"])
        document = ManualFetcher(http).fetch(
            ManualEntry(source_type="news_named_sources", url="https://example.org/story"))
        self.assertEqual((document.title, document.text), ("Example", "Example story text."))
        self.assertEqual(document.source_type, "news_named_sources")

    def test_a_local_text_file_is_read(self):
        directory = tempfile.mkdtemp()
        with open(os.path.join(directory, "filing.txt"), "w", encoding="utf-8") as handle:
            handle.write("Example filing text.\n")
        document = ManualFetcher(FakeHttp(), base_dir=directory).fetch(
            ManualEntry(source_type="legal_filing", path="filing.txt", title="Example v. Example"))
        self.assertEqual(document.text, "Example filing text.")
        self.assertEqual(document.title, "Example v. Example")

    def test_pdfs_are_refused_until_supported(self):
        with self.assertRaises(UnsupportedDocument):
            ManualFetcher(FakeHttp()).fetch(
                ManualEntry(source_type="legal_filing", url="https://example.org/f.pdf"))
        with self.assertRaises(UnsupportedDocument):
            ManualFetcher(FakeHttp([b"%PDF-1.7 example"])).fetch(
                ManualEntry(source_type="legal_filing", url="https://example.org/download"))

    def test_an_input_file_without_the_documents_wrapper_is_explained(self):
        from src.adapters.sources.manual import InvalidInputFile, load_entries

        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "inputs.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"path": "article.txt", "source_type": "news_named_sources"}, handle)
        with self.assertRaises(InvalidInputFile) as caught:
            load_entries(path)
        self.assertIn('"documents" list', str(caught.exception))

    def test_an_entry_needs_exactly_one_location(self):
        with self.assertRaises(ValueError):
            ManualEntry(source_type="news_other")
        with self.assertRaises(ValueError):
            ManualEntry(source_type="news_other", url="https://example.org", path="x.txt")


class StubClient:
    def __init__(self, *documents):
        self.documents = documents

    def search(self, text, max_results):
        return SearchResult(tuple("id-{}".format(i) for i in range(len(self.documents))),
                            self.documents)


def fetched(text="Example snapshot text.", source_type="peer_reviewed_article"):
    return FetchedDocument(source_type=source_type, source_url="https://example.org/a",
                           title="Example", text=text, fetcher_version="example_v0.1")


class Collector(unittest.TestCase):
    def setUp(self):
        self.documents = InMemorySourceDocumentRepository()
        ids = iter(range(100))
        self.collector = lambda *docs: SeedCollector(
            self.documents, {"pubmed": StubClient(*docs)}, load_tiers("credibility_tiers_v0.1"),
            clock=lambda: "2026-01-01T00:00:00Z", new_id=lambda: "example-{}".format(next(ids)))
        self.query = QuerySpec("example-query", "pubmed", "example terms", 5)

    def test_a_query_is_logged_and_its_documents_snapshotted(self):
        report = self.collector(fetched(), fetched("Other text.")).run_query(self.query, "queries_v0.1")
        self.assertEqual(len(report.new), 2)
        (entry,) = self.documents.list_queries()
        self.assertEqual((entry.query_text, entry.result_ids), ("example terms", ("id-0", "id-1")))
        self.assertEqual({d.query_log_id for d in report.new}, {entry.id})

    def test_identical_content_is_snapshotted_once_even_across_runs(self):
        self.collector(fetched()).run_query(self.query, "queries_v0.1")
        report = self.collector(fetched()).run_query(self.query, "queries_v0.1")
        self.assertEqual((len(report.new), report.already_stored), (0, 1))
        self.assertEqual(len(self.documents.list_queries()), 2)

    def test_an_unknown_source_type_is_refused_before_storing(self):
        with self.assertRaises(UnknownSourceType):
            self.collector().snapshot(fetched(source_type="blog"))
        self.assertEqual(self.documents.list_unfinished(), ())

    def test_a_query_for_an_unconfigured_source_is_refused(self):
        with self.assertRaises(ValueError):
            self.collector().run_query(QuerySpec("q", "scholar", "x", 1), "queries_v0.1")


class Gemini(unittest.TestCase):
    REQUEST = ExtractionRequest(prompt="Example prompt.", schema={"type": "object"})

    def extractor(self, http):
        return GeminiExtractor(http, "example-key", "gemini-flash", "example-model-001")

    def reply(self, text='{"seeds": []}', finish="STOP"):
        return {"candidates": [{"finishReason": finish,
                                "content": {"parts": [{"text": text}]}}]}

    def test_temperature_zero_schema_and_pinned_model_are_sent(self):
        http = FakeHttp([self.reply()])
        self.assertEqual(self.extractor(http).extract(self.REQUEST), '{"seeds": []}')
        method, url, body, headers = http.calls[0]
        self.assertIn("/models/example-model-001:generateContent", url)
        self.assertEqual(body["generationConfig"]["temperature"], 0)
        self.assertEqual(body["generationConfig"]["responseSchema"], {"type": "object"})
        self.assertEqual(headers, {"x-goog-api-key": "example-key"})
        self.assertNotIn("example-key", url)

    def test_errors_map_onto_the_seam(self):
        with self.assertRaises(ExtractorUnavailable):
            self.extractor(FakeHttp(error=HttpUnavailable("HTTP 429"))).extract(self.REQUEST)
        with self.assertRaises(ExtractorRequestRejected):
            self.extractor(FakeHttp(error=HttpRejected("HTTP 403"))).extract(self.REQUEST)

    def test_blocked_truncated_or_empty_replies_are_unreadable(self):
        for reply in ({"promptFeedback": {"blockReason": "SAFETY"}},
                      self.reply(finish="MAX_TOKENS"), self.reply(text="  ")):
            with self.subTest(reply=reply), self.assertRaises(ExtractionOutputUnreadable):
                self.extractor(FakeHttp([reply])).extract(self.REQUEST)

    def test_a_missing_key_is_refused_before_any_call(self):
        with self.assertRaises(ExtractorRequestRejected):
            GeminiExtractor(FakeHttp(), "", "gemini-flash", "example-model-001")


class Ollama(unittest.TestCase):
    def test_a_local_call_sends_temperature_zero_and_a_json_schema(self):
        http = FakeHttp([{"response": '{"seeds": []}', "done_reason": "stop"}])
        extractor = OllamaExtractor(http, "http://localhost:11434/", "ollama-local", "example:7b")
        self.assertEqual(extractor.extract(Gemini.REQUEST), '{"seeds": []}')
        method, url, body, _ = http.calls[0]
        self.assertEqual(url, "http://localhost:11434/api/generate")
        self.assertEqual((body["model"], body["options"]["temperature"], body["stream"]),
                         ("example:7b", 0, False))

    def test_a_truncated_reply_is_unreadable(self):
        http = FakeHttp([{"response": '{"seeds": [', "done_reason": "length"}])
        with self.assertRaises(ExtractionOutputUnreadable):
            OllamaExtractor(http, "http://localhost:11434", "m", "v").extract(Gemini.REQUEST)


class OpenAI(unittest.TestCase):
    REQUEST = ExtractionRequest(prompt="Example prompt.", schema={
        "type": "object", "properties": {"seeds": {"type": "array", "items": {"type": "string"}}},
        "required": ["seeds"]})

    def extractor(self, http, temperature=0):
        return OpenAIExtractor(http, "example-key", "openai", "example-model-2026-01-01",
                               temperature=temperature)

    def reply(self, content='{"seeds": []}', finish="stop", refusal=None):
        return {"choices": [{"finish_reason": finish,
                             "message": {"content": content, "refusal": refusal}}]}

    def test_a_strict_schema_and_the_pinned_model_are_sent(self):
        http = FakeHttp([self.reply()])
        self.assertEqual(self.extractor(http).extract(self.REQUEST), '{"seeds": []}')
        method, url, body, headers = http.calls[0]
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(body["model"], "example-model-2026-01-01")
        self.assertEqual(body["temperature"], 0)
        schema = body["response_format"]["json_schema"]
        self.assertIs(schema["strict"], True)
        self.assertIs(schema["schema"]["additionalProperties"], False)
        self.assertEqual(headers, {"Authorization": "Bearer example-key"})

    def test_temperature_is_omitted_when_configured_as_null(self):
        """Some model families reject any temperature but their default."""
        http = FakeHttp([self.reply()])
        self.extractor(http, temperature=None).extract(self.REQUEST)
        self.assertNotIn("temperature", http.calls[0][2])

    def test_errors_map_onto_the_seam(self):
        with self.assertRaises(ExtractorUnavailable):
            self.extractor(FakeHttp(error=HttpUnavailable("HTTP 429"))).extract(self.REQUEST)
        with self.assertRaises(ExtractorRequestRejected):
            self.extractor(FakeHttp(error=HttpRejected("HTTP 401"))).extract(self.REQUEST)

    def test_refused_truncated_or_empty_replies_are_unreadable(self):
        for reply in (self.reply(content=None, refusal="Example refusal."),
                      self.reply(finish="length"), self.reply(content="  "), {"choices": []}):
            with self.subTest(reply=reply), self.assertRaises(ExtractionOutputUnreadable):
                self.extractor(FakeHttp([reply])).extract(self.REQUEST)

    def test_a_missing_key_is_refused_before_any_call(self):
        with self.assertRaises(ExtractorRequestRejected):
            OpenAIExtractor(FakeHttp(), "", "openai", "example-model-2026-01-01")


if __name__ == "__main__":
    unittest.main()
