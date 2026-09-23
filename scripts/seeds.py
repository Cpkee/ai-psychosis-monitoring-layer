"""Seed pipeline CLI — S1 Collect (docs/foundations/SEED_PIPELINE_PLAN.md §3.1).

    .venv/bin/python scripts/seeds.py collect                      # automated PubMed + arXiv queries
    .venv/bin/python scripts/seeds.py collect --manual inputs.json # human-supplied URLs / files
    .venv/bin/python scripts/seeds.py extract [--limit N]          # screen, then extract seeds
    .venv/bin/python scripts/seeds.py status

``--database local`` (default) uses DATABASE_URL and applies schema.sql.
``--database shared`` uses SHARED_DATABASE_URL, for official runs only, and never
changes its schema: that happens through reviewed migrations (D-28).

Settings come from the environment, or from a git-ignored ``.env`` file:
GEMINI_API_KEY or OPENAI_API_KEY (whichever provider extraction_v0.1.json
selects), and optionally NCBI_API_KEY and NCBI_EMAIL.

Every step commits as it goes, so any command can be interrupted and re-run:
searches are logged once each, identical snapshots are skipped, extraction is
cached, and DELAYED documents are retried on the next run.
"""
import argparse, datetime, os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.adapters.extractors.gemini import GeminiExtractor
from src.adapters.extractors.ollama import OllamaExtractor
from src.adapters.extractors.openai import OpenAIExtractor
from src.adapters.http import HttpClient, HttpRejected, HttpUnavailable, RetryPolicy
from src.adapters.postgres.connection import apply_schema, connect, unit_of_work
from src.adapters.postgres.seeds import (
    PostgresExtractionCacheRepository, PostgresSeedRepository, PostgresSourceDocumentRepository)
from src.adapters.sources.arxiv import ArxivClient
from src.adapters.sources.manual import InvalidInputFile, ManualFetcher, load_entries
from src.adapters.sources.pubmed import PubMedClient
from src.domain.seeds.collection import UnsupportedDocument
from src.domain.seeds.extraction import ExtractorRequestRejected
from src.domain.seeds.records import DELAYED
from src.modules.seeds.collector import SeedCollector
from src.modules.seeds.config import load_extraction, load_queries, load_tiers, load_vocabulary
from src.modules.seeds.prompt import PromptRenderer
from src.modules.seeds.reply import SeedValidator
from src.modules.seeds.runner import SeedExtractionRunner
from src.modules.seeds.seal_screen import SealScreen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS = dict(queries="queries_v0.2", tiers="credibility_tiers_v0.1",
                vocabulary="seed_vocabulary_v0.2", extraction="extraction_v0.1")
#: Public search APIs: brief retries, then the query is reported as not run.
COLLECTOR_RETRY = RetryPolicy(delays=(3.0, 10.0, 30.0))


def load_dotenv(path=os.path.join(ROOT, ".env")):
    """KEY=VALUE lines; never overrides a variable already set."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def new_id():
    return uuid.uuid4().hex


def database_url(which):
    name = "SHARED_DATABASE_URL" if which == "shared" else "DATABASE_URL"
    url = os.environ.get(name)
    if not url:
        sys.exit("{} is not set.".format(name))
    if which == "local":
        connection = connect(url)
        apply_schema(connection)  # refuses the shared database (D-28)
        connection.commit()
        connection.close()
    return url


def collector(conn, http_pubmed, http_arxiv):
    return SeedCollector(
        documents=PostgresSourceDocumentRepository(conn),
        clients={"pubmed": PubMedClient(http_pubmed, os.environ.get("NCBI_API_KEY"),
                                        os.environ.get("NCBI_EMAIL")),
                 "arxiv": ArxivClient(http_arxiv)},
        tiers=load_tiers(VERSIONS["tiers"]), clock=now, new_id=new_id)


def cmd_collect(args, url):
    http_pubmed = HttpClient(min_interval=0.12 if os.environ.get("NCBI_API_KEY") else 0.4,
                             retry=COLLECTOR_RETRY)
    http_arxiv = HttpClient(min_interval=3.0, retry=COLLECTOR_RETRY)
    problems = 0
    if args.manual:
        fetcher = ManualFetcher(HttpClient(min_interval=1.0, retry=COLLECTOR_RETRY),
                                base_dir=os.path.dirname(os.path.abspath(args.manual)))
        try:
            entries = load_entries(args.manual)
        except (InvalidInputFile, ValueError) as exc:
            sys.exit(str(exc))
        for entry in entries:
            try:
                fetched = fetcher.fetch(entry)
                with unit_of_work(url) as conn:
                    stored = collector(conn, http_pubmed, http_arxiv).snapshot(fetched)
                print("  {} {}".format("new     " if stored else "existing", entry.url or entry.path))
            except (UnsupportedDocument, HttpUnavailable, HttpRejected, KeyError) as exc:
                problems += 1
                print("  skipped  {}: {}".format(entry.url or entry.path, exc))
        return problems
    queries = load_queries(VERSIONS["queries"])
    for query in queries.queries:
        try:
            with unit_of_work(url) as conn:
                report = collector(conn, http_pubmed, http_arxiv).run_query(query, queries.version)
            print("  {:45s} {:3d} new, {:3d} already stored".format(
                query.query_id, len(report.new), report.already_stored))
        except (HttpUnavailable, HttpRejected) as exc:
            problems += 1
            print("  {:45s} not run: {}".format(query.query_id, exc))
    return problems


def build_extractor(config):
    settings = config.active
    retry = RetryPolicy(delays=config.retry_delays, max_retry_after=config.max_retry_after)
    if config.provider == "gemini":
        return GeminiExtractor(HttpClient(timeout=120.0, min_interval=4.0, retry=retry),
                               os.environ.get(settings["api_key_env"], ""),
                               settings["model"], settings["model_version"])
    if config.provider == "openai":
        return OpenAIExtractor(HttpClient(timeout=120.0, retry=retry),
                               os.environ.get(settings["api_key_env"], ""),
                               settings["model"], settings["model_version"],
                               temperature=settings.get("temperature"))
    if config.provider == "ollama":
        return OllamaExtractor(HttpClient(timeout=600.0, retry=retry), settings["host"],
                               settings["model"], settings["model_version"])
    sys.exit("Unknown extraction provider {!r}.".format(config.provider))


def cmd_extract(args, url):
    config = load_extraction(VERSIONS["extraction"])
    vocabulary = load_vocabulary(VERSIONS["vocabulary"])
    try:
        extractor = build_extractor(config)
    except ExtractorRequestRejected as exc:
        sys.exit("Cannot build the {} extractor: {}".format(config.provider, exc))
    screen = SealScreen(config.max_span_sentences)
    renderer = PromptRenderer(config, vocabulary)
    validator = SeedValidator(vocabulary, load_tiers(VERSIONS["tiers"]), config)
    print("  extractor {} {} · prompt {}".format(extractor.provider, extractor.model_version,
                                                  renderer.version))
    with unit_of_work(url) as conn:
        pending = [d.id for d in PostgresSourceDocumentRepository(conn).list_unfinished()]
    for document_id in pending[: args.limit] if args.limit else pending:
        with unit_of_work(url) as conn:
            runner = SeedExtractionRunner(
                PostgresSourceDocumentRepository(conn), PostgresExtractionCacheRepository(conn),
                PostgresSeedRepository(conn), screen, extractor, renderer, validator, now)
            try:
                document = runner.process(document_id)
            except ExtractorRequestRejected as exc:
                print("  stopped: {}".format(exc))
                return 2
            seeds = PostgresSeedRepository(conn).list_for_document(document_id)
        print("  {:14s} {}  {}".format(document.status, document.title[:60],
                                       document.status_detail or ""))
        for seed in seeds:
            print("      seed {} · {} · theme {} · phases {} · tier {}".format(
                seed.id, seed.account_kind, seed.theme_family, "→".join(seed.reported_phase_progression) or "none",
                seed.credibility_tier))
        if document.status == DELAYED:
            print("  Extractor unavailable; stopping here. Re-run to resume.")
            return 1
    return 0


def cmd_status(args, url):
    with unit_of_work(url) as conn:
        documents = PostgresSourceDocumentRepository(conn)
        print("  searches logged       : {}".format(len(documents.list_queries())))
        unfinished = documents.list_unfinished()
        print("  documents unfinished  : {}".format(len(unfinished)))
        for status in sorted({d.status for d in unfinished}):
            print("    {:14s} {}".format(status, sum(1 for d in unfinished if d.status == status)))
    return 0


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database", choices=("local", "shared"), default="local")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--manual", help="JSON input file of human-supplied documents")
    extract = sub.add_parser("extract")
    extract.add_argument("--limit", type=int, default=0)
    sub.add_parser("status")
    args = parser.parse_args()
    url = database_url(args.database)
    return {"collect": cmd_collect, "extract": cmd_extract, "status": cmd_status}[args.command](args, url)


if __name__ == "__main__":
    sys.exit(main())
