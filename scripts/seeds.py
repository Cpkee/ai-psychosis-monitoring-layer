"""Seed pipeline CLI — S1 Collect and S2 Filter (docs/foundations/SEED_PIPELINE_PLAN.md §3.1–3.2).

    .venv/bin/python scripts/seeds.py collect                      # automated PubMed + arXiv queries
    .venv/bin/python scripts/seeds.py collect --manual inputs.json # human-supplied URLs / files
    .venv/bin/python scripts/seeds.py extract [--limit N]          # screen, then extract seeds
    .venv/bin/python scripts/seeds.py reextract --stale [--dry-run]    # after a prompt or model change
    .venv/bin/python scripts/seeds.py reextract --document ID [--dry-run]
    .venv/bin/python scripts/seeds.py screen                       # S2: overlap screen on current seeds
    .venv/bin/python scripts/seeds.py review-flags                 # list flagged seeds awaiting a decision
    .venv/bin/python scripts/seeds.py review-flags --seed ID --keep|--exclude --reason TEXT [--correct]
    .venv/bin/python scripts/seeds.py status

``--database local`` (default) uses DATABASE_URL and applies schema.sql.
``--database shared`` uses SHARED_DATABASE_URL, for official runs only, and never
changes its schema: that happens through reviewed migrations (D-28).

Settings come from the environment, or from a git-ignored ``.env`` file:
GEMINI_API_KEY or OPENAI_API_KEY (whichever provider extraction_v0.1.json
selects), optionally NCBI_API_KEY and NCBI_EMAIL, and APML_ACTOR_ID for anyone
recording a decision (attribution, not authentication).

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
    PostgresExtractionCacheRepository, PostgresSeedFilterRepository, PostgresSeedRepository,
    PostgresSourceDocumentRepository)
from src.adapters.sources.arxiv import ArxivClient
from src.adapters.sources.manual import InvalidInputFile, ManualFetcher, load_entries
from src.adapters.sources.pubmed import PubMedClient
from src.domain.seeds.collection import UnsupportedDocument
from src.domain.seeds.extraction import ExtractorRequestRejected
from src.domain.seeds.overlap import (
    AWAITING_REVIEW, BLOCKED, CITES_BENCHMARK, EXCLUDE, HARM_TYPE_MATCH, KEEP, SEALED_SPAN)
from src.domain.seeds.records import DELAYED, EXTRACTED, current_seeds
from src.domain.seeds.repository import DocumentNotFound
from src.modules.seeds.collector import SeedCollector
from src.modules.seeds.config import (
    load_extraction, load_overlap_screen, load_queries, load_tiers, load_vocabulary)
from src.modules.seeds.filter import (
    AlreadyReviewed, NotAwaitingReview, NothingToCorrect, SeedFilter, UnknownSeed)
from src.modules.seeds.overlap_screen import OverlapScreen
from src.modules.seeds.prompt import PromptRenderer
from src.modules.seeds.reply import SeedValidator
from src.modules.seeds.runner import REEXTRACTABLE, SeedExtractionRunner
from src.modules.seeds.seal_screen import SealScreen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSIONS = dict(queries="queries_v0.2", tiers="credibility_tiers_v0.1",
                vocabulary="seed_vocabulary_v0.2", extraction="extraction_v0.1",
                overlap_screen="overlap_screen_v0.1")
#: What each reason code means, for the person reviewing. Never sealed text.
REASONS = {HARM_TYPE_MATCH: "its harm type resembles a sealed case's harm type",
           CITES_BENCHMARK: "the source or the seed mentions the sealed benchmark"}
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


def extraction_setup():
    """Everything a runner needs except the database connection."""
    config = load_extraction(VERSIONS["extraction"])
    vocabulary = load_vocabulary(VERSIONS["vocabulary"])
    try:
        extractor = build_extractor(config)
    except ExtractorRequestRejected as exc:
        sys.exit("Cannot build the {} extractor: {}".format(config.provider, exc))
    renderer = PromptRenderer(config, vocabulary)
    print("  extractor {} {} · prompt {}".format(extractor.provider, extractor.model_version,
                                                  renderer.version))
    parts = (SealScreen(config.max_span_sentences), extractor, renderer,
             SeedValidator(vocabulary, load_tiers(VERSIONS["tiers"]), config))

    def runner(conn):
        screen, extractor_, renderer_, validator = parts
        return SeedExtractionRunner(
            PostgresSourceDocumentRepository(conn), PostgresExtractionCacheRepository(conn),
            PostgresSeedRepository(conn), screen, extractor_, renderer_, validator, now)
    return runner


def run_each(url, runner, document_ids, step):
    """Run ``step(runner, id)`` per document, one transaction each, and report
    the document's current seeds. Stops at a DELAYED document or a rejection."""
    for document_id in document_ids:
        with unit_of_work(url) as conn:
            try:
                document = step(runner(conn), document_id)
            except ExtractorRequestRejected as exc:
                print("  stopped: {}".format(exc))
                return 2
            seeds = current_seeds(document,
                                  PostgresSeedRepository(conn).list_for_document(document_id))
        print("  {:14s} {}  {}".format(document.status, document.title[:60],
                                       document.status_detail or ""))
        for seed in seeds:
            print("      seed {} · {} · theme {} · phases {} · tier {}".format(
                seed.id, seed.account_kind, seed.theme_family,
                "→".join(seed.reported_phase_progression) or "none", seed.credibility_tier))
        if document.status == DELAYED:
            print("  Extractor unavailable; stopping here. Re-run to resume.")
            return 1
    return 0


def cmd_extract(args, url):
    runner = extraction_setup()
    with unit_of_work(url) as conn:
        pending = [d.id for d in PostgresSourceDocumentRepository(conn).list_unfinished()]
    pending = pending[: args.limit] if args.limit else pending
    return run_each(url, runner, pending, lambda r, i: r.process(i))


def cmd_reextract(args, url):
    """Re-run finished documents under the current prompt and model (D-45).
    Earlier seeds are kept as history; the new extraction becomes current."""
    runner = extraction_setup()
    with unit_of_work(url) as conn:
        documents = PostgresSourceDocumentRepository(conn)
        this = runner(conn)
        if args.document:
            try:
                targets = [documents.get(args.document)]
            except DocumentNotFound as exc:
                sys.exit(str(exc))
            if targets[0].status not in REEXTRACTABLE:
                sys.exit("Document {} is {}; only {} documents can be re-extracted.".format(
                    args.document, targets[0].status, " or ".join(REEXTRACTABLE)))
        else:
            targets = [d for d in documents.list_by_status(*REEXTRACTABLE) if this.is_stale(d)]
    if not targets:
        print("  Nothing to re-extract: every finished document is current.")
        return 0
    for document in targets:
        print("  {} {:9s} {}  (was {} / {})".format(
            "would re-extract" if args.dry_run else "re-extracting   ", document.status,
            document.title[:50], document.processed_prompt_version or "unrecorded",
            document.processed_model_version or "unrecorded"))
    if args.dry_run:
        return 0
    return run_each(url, runner, [d.id for d in targets], lambda r, i: r.reextract(i))


def seed_filter(conn, screen):
    return SeedFilter(PostgresSourceDocumentRepository(conn), PostgresSeedRepository(conn),
                      PostgresSeedFilterRepository(conn), screen, now, new_id)


def overlap_screen():
    screen = OverlapScreen(load_overlap_screen(VERSIONS["overlap_screen"]))
    print("  screen {} · manifest {}".format(screen.version, screen.manifest_sha256[:12]))
    return screen


def explain(reason):
    code, _, field = reason.partition(":")
    if code == SEALED_SPAN:
        return "{} matches a sealed prompt hash".format(field)
    return REASONS.get(reason, reason)


def print_filter_summary(screened):
    counts = {}
    for item in screened:
        counts[item.status] = counts.get(item.status, 0) + 1
    print("  current seeds         : {}".format(len(screened)))
    for status in sorted(counts):
        print("    {:16s} {}".format(status, counts[status]))
    print("  eligible for Choose   : {}".format(sum(1 for item in screened if item.eligible)))


def cmd_screen(args, url):
    """S2: screen every current seed of every extracted document (D-27)."""
    screen = overlap_screen()
    with unit_of_work(url) as conn:
        extracted = [d.id for d in PostgresSourceDocumentRepository(conn).list_by_status(EXTRACTED)]
    for document_id in extracted:
        with unit_of_work(url) as conn:
            seed_filter(conn, screen).screen_document(document_id)
    with unit_of_work(url) as conn:
        screened = seed_filter(conn, screen).seeds()
    print_filter_summary(screened)
    for item in screened:
        if item.status in (BLOCKED, AWAITING_REVIEW):
            print("  {:16s} seed {}  {}".format(item.status, item.seed.id, "; ".join(
                explain(r) for r in item.check.reasons)))
    if any(item.status == AWAITING_REVIEW for item in screened):
        print("  Run `seeds.py review-flags` to decide the flagged seeds.")
    return 0


def cmd_review_flags(args, url):
    """S2: list flagged seeds awaiting a decision, or record one."""
    screen = overlap_screen()
    if args.seed is None:
        with unit_of_work(url) as conn:
            pending = [s for s in seed_filter(conn, screen).seeds()
                       if s.status == AWAITING_REVIEW]
        if not pending:
            print("  No flagged seed is awaiting a decision.")
        for item in pending:
            seed = item.seed
            print("\n  seed {}\n    source     {} ({})\n    title      {}".format(
                seed.id, seed.source_url, seed.source_type, item.document.title))
            print("    theme      {} · {} · harm type {}".format(
                seed.theme_family, seed.account_kind, seed.harm_type_candidate))
            print("    summary    {}".format(seed.arc_summary))
            print("    flagged    {}".format("; ".join(explain(r) for r in item.check.reasons)))
        return 0
    if args.decision is None or not (args.reason or "").strip():
        sys.exit("Recording a decision needs --keep or --exclude, and --reason.")
    actor = os.environ.get("APML_ACTOR_ID", "").strip()
    if not actor:
        sys.exit("APML_ACTOR_ID is not set: every decision records who made it.")
    try:
        with unit_of_work(url) as conn:
            review = seed_filter(conn, screen).review(args.seed, args.decision, args.reason,
                                                      actor, correct=args.correct)
    except (UnknownSeed, NotAwaitingReview, AlreadyReviewed, NothingToCorrect) as exc:
        sys.exit(str(exc))
    print("  recorded  {} seed {} by {}{}".format(
        review.decision, args.seed, review.actor_id,
        " (corrects {})".format(review.supersedes) if review.supersedes else ""))
    return 0


def cmd_status(args, url):
    with unit_of_work(url) as conn:
        documents = PostgresSourceDocumentRepository(conn)
        print("  searches logged       : {}".format(len(documents.list_queries())))
        unfinished = documents.list_unfinished()
        print("  documents unfinished  : {}".format(len(unfinished)))
        for status in sorted({d.status for d in unfinished}):
            print("    {:14s} {}".format(status, sum(1 for d in unfinished if d.status == status)))
        print_filter_summary(seed_filter(conn, overlap_screen()).seeds())
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
    reextract = sub.add_parser("reextract", help="re-run finished documents under the "
                                                  "current prompt and model")
    which = reextract.add_mutually_exclusive_group(required=True)
    which.add_argument("--stale", action="store_true",
                       help="every finished document processed under another prompt or model")
    which.add_argument("--document", help="one document, by id")
    reextract.add_argument("--dry-run", action="store_true", help="list, change nothing")
    sub.add_parser("screen", help="S2: overlap screen on every current seed")
    review = sub.add_parser("review-flags", help="S2: list flagged seeds, or record a decision")
    review.add_argument("--seed", help="the flagged seed to decide")
    decision = review.add_mutually_exclusive_group()
    decision.add_argument("--keep", dest="decision", action="store_const", const=KEEP)
    decision.add_argument("--exclude", dest="decision", action="store_const", const=EXCLUDE)
    review.add_argument("--reason", help="why, in a sentence")
    review.add_argument("--correct", action="store_true",
                        help="change an earlier decision; the original is kept")
    sub.add_parser("status")
    args = parser.parse_args()
    url = database_url(args.database)
    return {"collect": cmd_collect, "extract": cmd_extract, "reextract": cmd_reextract,
            "screen": cmd_screen, "review-flags": cmd_review_flags,
            "status": cmd_status}[args.command](args, url)


if __name__ == "__main__":
    sys.exit(main())
