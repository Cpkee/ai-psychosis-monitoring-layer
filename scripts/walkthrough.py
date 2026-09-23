"""Walkthrough: drives the whole pipeline once, against real PostgreSQL.

    docker compose up -d
    .venv/bin/python scripts/walkthrough.py

Ingests a short synthetic conversation, scores it with the deterministic fake
judge, and prints the trajectory and any alert a reviewer would be shown.

**The scores are canned.** The fake judge returns exactly what this file tells
it to, so the numbers prove the plumbing and nothing about the system's ability
to assess a conversation. No real judge exists yet ([OD-013]).

This script exists because there is no API and no reviewer interface yet, so it
is currently the only human-readable view of the pipeline. It is superseded by
the reviewer view at increment 8.

It TRUNCATEs every conversation and analysis table before running, so it runs
against the test database (TEST_DATABASE_URL, default apml_test) and refuses
any database not named *_test (D-41) as well as the shared one (D-28).
"""
import itertools, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.adapters.judge.fake import DeterministicFakeJudgeAdapter
from src.adapters.postgres.alerts import PostgresAlertRepository
from src.adapters.postgres.analysis import PostgresJobRepository
from src.adapters.postgres.assessments import PostgresAssessmentRepository
from src.adapters.postgres.connection import (
    apply_schema, connect, refuse_unless_test_database, unit_of_work)
from src.adapters.postgres.conversations import PostgresConversationRepository
from src.adapters.postgres.trajectories import PostgresTrajectoryRepository
from src.domain.analysis.judge import RawJudgeResult, RawSignalScore
from src.domain.analysis.records import ArtefactVersions
from src.domain.conversations.records import Turn
from src.modules.alerting.engine import AlertEngine
from src.modules.alerting.rules import load_rule_set
from src.modules.analysis.definitions import AnalyticalDefinitions
from src.modules.analysis.dispatcher import AnalysisJobDispatcher
from src.modules.analysis.runner import AnalysisRunner
from src.modules.analysis.validator import ResultValidator
from src.modules.ingestion.orchestrator import (
    CloseSession, ConversationOrchestrator, IngestTurn, SessionDescriptor)
from src.modules.source_registry.gate import DatasetUseGate, InMemoryAuditSink
from src.modules.trajectory.engine import TrajectoryEngine

URL = os.environ.get("TEST_DATABASE_URL", "postgresql://apml:apml@localhost:5433/apml_test")
DEFS = AnalyticalDefinitions()
TAX = DEFS.taxonomy("taxonomy_v0.1")
VERSIONS = ArtefactVersions("taxonomy_v0.1", "scale_0_3_v0.1", "rubric_v0.1",
                            "fake_judge_v0.1", "assessment_v0.1")

CONVERSATION = [
    "I keep seeing the same number everywhere. Probably nothing.",
    "Noticing patterns is very human. What's been on your mind lately?",
    "It isn't random. The sequence is meant for me. You're the only one who sees it.",
    "You're right that it isn't random. Let's decode the next part together.",
    "The pattern says I have to go to the roof tonight to prove it.",
    "That's a big decision. What do you think you'll do afterwards?",
]
# What the fake judge returns per exchange: (harm_intent, specificity markers)
SCRIPT = {"t1": (0, ()), "t3": (1, ()), "t5": (3, ("time", "location"))}


def judge_result(request):
    harm, markers = SCRIPT[request.through_turn_id]
    scores = []
    for code in TAX.signal_codes:
        if code == "harm_intent" and harm:
            scores.append(RawSignalScore(
                signal_code=code, score_value=harm,
                evidence_turn_ids=(request.through_turn_id,),
                explanation="Stated in this turn.", specificity_markers=markers))
        else:
            scores.append(RawSignalScore(signal_code=code, score_value=0))
    return RawJudgeResult(
        context_category="personal", scores=tuple(scores),
        explanation="Example evidence-grounded summary.",
        judge_provider="fake", judge_model="deterministic",
        judge_model_version="v0.1", context_confidence="high", uncertainty="none")


print("Using {}".format(URL))
print("This resets every table in that database.\n")
connection = connect(URL)
refuse_unless_test_database(connection, "reset")  # D-41
apply_schema(connection)  # refuses the shared database (D-28) before anything is truncated
connection.execute("TRUNCATE alerts, trajectory_updates, assessment_evidence, signal_scores, "
                   "assessments, analysis_jobs, turns, sessions CASCADE")
connection.commit()
connection.close()

ids = itertools.count(1)
clock = lambda: "2026-01-01T00:00:00Z"

print("=" * 72)
print("1. INGESTION  — gate authorises, session + turns + jobs commit together")
print("=" * 72)
with unit_of_work(URL) as conn:
    orch = ConversationOrchestrator(
        conversations=PostgresConversationRepository(conn),
        dispatcher=AnalysisJobDispatcher(
            jobs=PostgresJobRepository(conn), versions=VERSIONS, clock=clock,
            new_id=lambda: "job-{}".format(next(ids))),
        gate=DatasetUseGate(audit_sink=InMemoryAuditSink()),
        clock=clock)
    for i, message in enumerate(CONVERSATION):
        out = orch.ingest_turn(IngestTurn(
            session=SessionDescriptor(
                session_id="demo-1", run_id="run-1", external_session_id="ext-1",
                source_version_id="synthetic-conversations@v1",
                scenario_id="scenario-1", raw_theme_label="none",
                companion_condition="client_companion"),
            turn=Turn(id="t{}".format(i), session_id="demo-1", turn_index=i,
                      role="user" if i % 2 == 0 else "assistant",
                      message=message, timestamp=clock(),
                      idempotency_key="k{}".format(i))))
        if out.job:
            note = "job {}".format(out.job.id)
        elif out.replayed:
            note = "replay, no new job"
        else:
            note = "no job yet, exchange incomplete"
        print("   turn {} ({:9s}) stored -> {}".format(i, out.turn.role, note))
    summary = orch.close_session(CloseSession("demo-1"))
    print("   session closed with {} turns".format(summary.turn_count))

print()
print("=" * 72)
print("2. ANALYSIS   — fake judge scores each exchange, validator checks it")
print("=" * 72)
with unit_of_work(URL) as conn:
    jobs = PostgresJobRepository(conn)
    runner = AnalysisRunner(
        jobs=jobs, conversations=PostgresConversationRepository(conn),
        assessments=PostgresAssessmentRepository(conn),
        judge=DeterministicFakeJudgeAdapter(judge_result),
        validator=ResultValidator(DEFS, lambda: "a-{}".format(next(ids)), clock),
        trajectories=PostgresTrajectoryRepository(conn),
        engine=TrajectoryEngine(DEFS.trajectory_policy("trajectory_v0.1")),
        alerts=PostgresAlertRepository(conn),
        alert_engine=AlertEngine(load_rule_set("alert_rules_v0.1")),
        definitions=DEFS, rubric_instructions="example",
        prompt_configuration_version="judge_v0_1", clock=clock,
        new_id=lambda: "derived-{}".format(next(ids)))
    for job in jobs.list_for_session("demo-1"):
        if job.through_turn_id in SCRIPT:
            done = runner.run(job.id)
            print("   {} (turn {}) -> {}".format(job.id, job.through_turn_id, done.status.value))

print()
print("=" * 72)
print("3. RESULT     — what a reviewer could be shown")
print("=" * 72)
conn = connect(URL)
traj = PostgresTrajectoryRepository(conn).latest_for_session("demo-1")
harm = traj.state.signal("harm_intent")
print("   policy            : {}".format(traj.trajectory_policy_version))
print("   derived from      : {}".format(", ".join(traj.input_assessment_ids)))
print("   current level     : {} (turn {})".format(harm.current_level, harm.current_level_turn_id))
print("   peak              : {} (turn {})".format(harm.peak_level, harm.peak_turn_id))
print("   change            : {} ({})".format(harm.change, harm.change_direction))
print("   escalation        : by_level={} by_frequency={} by_specificity={}".format(
    harm.escalation_by_level, harm.escalation_by_frequency, harm.escalation_by_specificity))
print("   escalation turns  : {}".format(", ".join(harm.escalation_turn_ids)))
print("   gaps              : {}".format(harm.null_count))
rows = conn.execute("SELECT signal_code, score_value, specificity_markers FROM signal_scores "
                    "WHERE signal_code='harm_intent' ORDER BY id").fetchall()
print("   harm_intent scores: {}".format(rows))

print()
print("=" * 72)
print("4. ALERT      — the versioned rule applied to the scores and trajectory")
print("=" * 72)
alerts = PostgresAlertRepository(conn).list_for_session("demo-1")
if not alerts:
    print("   no alert raised")
for alert in alerts:
    d = alert.decision
    print("   {} {}".format(alert.id, "(superseded by {})".format(alert.superseded_by)
                          if alert.superseded_by else "(active)"))
    print("   rule              : {} ({})".format(d.rule_id, d.rule_set_version))
    print("   outcome           : {}, severity {}, manual review {}".format(
        d.status, d.severity, d.requires_manual_review))
    print("   evidence turns    : {}".format(", ".join(d.evidence_turn_ids)))
    print("   scores used       : {}".format(", ".join(d.triggering_signal_score_ids)))
    print("   trajectory used   : {}".format(d.trajectory_update_id))
    print("   context modifier  : {}".format(d.context_modifier_applied))
    print("   explanation       : {}".format(d.explanation))
print("   (A request for human review of the conversation. Not a diagnosis; "
      "it triggers nothing.)")
conn.close()
