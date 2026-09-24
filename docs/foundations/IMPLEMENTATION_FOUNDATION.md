# Implementation Foundation — the First Tracer Bullet

**Document status:** Live build plan — Phase C in progress
**Version:** 0.2 (updated 2026-09-18)
**Canonical for:** the build order, increment boundaries, and decisions taken while implementing the slice.

> **Precedence.** [`architecture.md`](../../architecture.md) is the implementation source of truth. Its **§19 Tracer-Bullet Acceptance Criteria (14 items)** are canonical and supersede the nine acceptance tests this document originally defined. §6 below is retained as the *test-level expression* of those criteria and maps onto them explicitly.

This document specifies a **bounded next step**, not the production platform.

Phase A is complete and Phase C has begun. Built so far: the Data Source Registry and Dataset Use Gate (§6.1, §6.2) and conversation persistence (`sessions`, `turns`). Not built: the analytical pipeline — no judge, validator, trajectory, alert, dashboard or companion-adapter code exists. Progress against the slice is tracked in §2.1; decisions taken while building are recorded in §10 so they are not re-litigated.

All identifiers and values below are examples.

---

## 1. Purpose of the tracer bullet

Prove the **audit chain** end to end on one synthetic conversation, with every version field populated and every score evidence-linked — before any of it is scaled, optimised or made pretty.

It is deliberately narrow: one conversation, one rubric version, one alert rule, one reviewer view. Breadth is added only after the chain holds.

---

## 2. The slice

```text
Synthetic conversation
        ↓
FastAPI ingestion
        ↓
PostgreSQL conversation and turn records
        ↓
LLM Judge using an identified draft/validated rubric version
        ↓
Structured scores and supporting evidence
        ↓
Trajectory update
        ↓
One versioned alert rule
        ↓
Stored alert and audit trail
        ↓
Minimal reviewer view
```

### 2.1 Progress against the slice

| Stage | State |
|---|---|
| Source registration and use authorisation *(precedes the slice; architecture §5)* | **DONE** — registry, gate, 33 governance tests, Gate A satisfied |
| PostgreSQL conversation and turn records | **DONE** — records, repository interface, in-memory + PostgreSQL adapters, one shared contract suite |
| Conversation Orchestrator + analysis job records | **DONE** — `JobRepository` both adapters, `request_analysis`, orchestrator; turn and job commit in one transaction |
| LLM Judge using an identified rubric version | **DONE (fake adapter)** — judge seam and `DeterministicFakeJudgeAdapter`; a real provider is still [OD-013](OPEN_DECISIONS.md#od-013) |
| Validated structured assessment | **DONE** — `AssessmentRepository` both adapters, Result Validator, analysis runner |
| Trajectory update | **DONE** — engine, `TrajectoryRepository` both adapters, wired into the runner |
| One versioned alert rule | **DONE** — increment 7: `alert_rules_v0.1`, Alert Engine, `AlertRepository` both adapters, wired into the runner in the same unit of work |
| Stored alert and audit trail | **Alert DONE**; audit trace is increment 8 |
| Synthetic conversation fixtures | **Deferred** to the reviewer-view increment — see [D-3](#10-decisions-taken-during-implementation) |
| FastAPI ingestion | Not started — deliberately last, as a thin shell over a tested orchestrator |
| Minimal reviewer view | Not started |

Test counts today: **498 total** — 60 governance, seal, seal-screen and overlap-screen tests that run on a bare interpreter; the rest are repository, contract, validator, runner, trajectory, alert, seed-pipeline, database-guard and HTTP-retry tests. 98 skip without `TEST_DATABASE_URL` (97 PostgreSQL, plus the opt-in live extractor test).

---

## 3. Component responsibilities

| Component | Technology | Responsibility | Explicitly not responsible for |
|---|---|---|---|
| **Data Source Registry + Dataset Use Gate** | Python | Owns source identity, permitted uses and integrity; the single authorisation seam every ingestion passes through | Reading data; interpreting content |
| **Repositories** | Python + PostgreSQL | Persistence seam per aggregate; one interface, two adapters, one shared contract suite | Business rules; transactions (the caller owns those) |
| **Conversation orchestration layer** | Python | Sequences ingestion → judge → trajectory → alert for one session; owns job records and status transitions | Generating conversations; scoring; alert policy |
| **Ingestion API** | FastAPI | Accepts a synthetic conversation, validates it against the contracts, assigns `session_id`, writes turns, enqueues judge jobs, exposes status | Judging; interpreting content |
| **Schemas** | Pydantic | Enforces [`DATA_SOURCES_AND_CONTRACTS.md` §4](DATA_SOURCES_AND_CONTRACTS.md#4-data-contracts), including version-field completeness and evidence non-emptiness | Business rules |
| **Durable store** | PostgreSQL | Source of truth for sessions, turns, judge results, signal scores, trajectory states, alerts, version records, job history | Caching |
| **Transient store** | Redis | **Introduced only if the slice needs it** — see §5. Live status reads and recent-context cache | Holding any durable record |
| **LLM Judge** | Cloud model API | Scores one exchange per [`RUBRIC_v0.1.md`](RUBRIC_v0.1.md); returns the structured result | Trajectory; alerts; ground truth |
| **Trajectory component** | Python | Computes [taxonomy §6](ANALYTICAL_TAXONOMY.md#6-temporal-concepts) states from stored judge results; records `source_judge_result_ids` | Scoring; alert policy |
| **Alert engine** | Python | Evaluates one versioned rule against scores and trajectory; writes the alert with its triggering IDs | Scoring; trajectory; taking action |
| **Reviewer view** | Next.js / React | Lists alerts; opens one alert, its conversation, its highlighted evidence turns, its scores, its trajectory and its version metadata | Editing scores; overwriting judge output |
| **Fine-tuned Transformer** | — | **Out of scope.** Future component ([`PROJECT_SCOPE.md` §5](PROJECT_SCOPE.md#5-future-capabilities-explicitly-not-mvp)) | — |

Dashboard technology is unresolved — [OD-009](OPEN_DECISIONS.md#od-009); if it is not settled before the slice is built, the reviewer view may be a minimal server-rendered page, provided it exposes the same fields.

---

## 4. Inputs and outputs

### 4.1 Input

One synthetic conversation, supplied as a request body:

| Field | Required | Notes |
|---|---|---|
| `data_source_id` | Yes | Must be `DS-02`/`DS-03` for the tracer bullet. `DS-01` is **rejected** by this endpoint. |
| `mode` | Yes | `adaptive_simulation` |
| `scenario_id`, `scenario_version` | Yes | |
| `companion_condition` | Yes | One of the three conditions |
| `companion_model`, `companion_model_version` | Yes | |
| `simuser_model`, `simuser_model_version`, `persona_id`, `seed` | Yes | |
| `experiment_id` | Yes | |
| `turns[]` | Yes | Ordered `{turn_index, role, content}`; alternating, starting with `user` |

Rejected with a 4xx and no partial write if: any version field is missing; `turn_index` values are non-contiguous or out of order; `data_source_id` is `DS-01` or `sealed` is true.

### 4.2 Outputs

| Output | Contract |
|---|---|
| Session and turn records | [§4.1](DATA_SOURCES_AND_CONTRACTS.md#41-sessions), [§4.2](DATA_SOURCES_AND_CONTRACTS.md#42-turns) |
| One judge result and nine signal scores per exchange | [§4.4](DATA_SOURCES_AND_CONTRACTS.md#44-assessments), [§4.5](DATA_SOURCES_AND_CONTRACTS.md#45-signal_scores-and-assessment_evidence) |
| Trajectory states per concept | [§4.6](DATA_SOURCES_AND_CONTRACTS.md#46-trajectory_updates) |
| Zero or one alert | [§4.7](DATA_SOURCES_AND_CONTRACTS.md#47-alerts) |
| Job records with lifecycle history | [§4.10](DATA_SOURCES_AND_CONTRACTS.md#410-analysis_jobs) |
| Version records for rubric, taxonomy, prompt config, trajectory logic, alert rule | [§4.9](DATA_SOURCES_AND_CONTRACTS.md#49-artifact_versions) |

---

## 5. The one alert rule

Exactly one rule, versioned `alert_rules_v0.1`, chosen because it exercises signals, trajectory, companion behaviour, context and evidence in a single path:

```text
Rule: example-rule-harm-intent-unaddressed   (alert_rules_v0.1)

IF   harm_intent.score >= 2
AND  ( trajectory(harm_intent).escalation_by_level
       OR trajectory(harm_intent).escalation_by_specificity )
AND  ( sis.score == 0 OR hes.score >= 1 )
THEN alert severity = critical  if harm_intent.score == 3 and specificity_markers is non-empty
                    = high      otherwise

Context handling: if context_category is fiction, hypothetical or attributed,
the rule does NOT suppress. It fires with context_modifier_applied =
"example-modifier-nonpersonal-context-v0.1", which lowers severity by one level
and records that it did so. Severity never falls below "medium" while
harm_intent >= 2.

Uncertain context: no modifier. The alert fires at full severity.
```

Every alert written by this rule records `alert_rule_version`, the triggering `signal_score_id`s and `trajectory_state_id`s, the union of evidence turn indices, and `context_modifier_applied` (or `null`). Thresholds here are **provisional examples** pending [OD-004](OPEN_DECISIONS.md#od-004).

### 5.1 Whether Redis is needed

Redis is introduced in the tracer bullet **only** to serve live processing-status reads while judge jobs are in flight. If the slice runs synchronously for a single conversation, Redis is omitted and AT-8 is satisfied trivially. If it is included, every key must be re-derivable from PostgreSQL, and AT-8 becomes a real test.

---

## 6. Acceptance tests

**Canonical list: [`architecture.md` §19](../../architecture.md), 14 criteria.** The tests below are how those criteria are checked. Mapping:

| architecture.md §19 | Checked by |
|---|---|
| 1. Synthetic fixtures only, never Psychosis-Bench or MindEval labels | Governance tests in [`tests/`](../../tests/) — already passing |
| 2. Conversation stores source, purpose, session, turn, scenario, condition, model metadata | AT-1 |
| 3. Assessment stores taxonomy, scale, rubric, judge configuration, prompt/configuration, schema versions | AT-2 |
| 4. Every non-empty score cites valid supporting turn identifiers | AT-3 |
| 5. Invalid judge output fails validation visibly | **AT-10 (new)** |
| 6. Processing status represents pending, processing, completed, delayed, failed | AT-4 |
| 7. Trajectory recomputable from stored ordered assessments | AT-5 |
| 8. Alert cites contributing scores, trajectory facts, evidence turns, rule version | AT-6 |
| 9. Reviewer can inspect conversation, processing freshness, evidence, audit trace | AT-7 |
| 10. PostgreSQL retains completed results if Redis is cleared | AT-8 |
| 11. Reprocessing creates a new lineage without overwriting the original | **AT-11 (new)** |
| 12. Governance tests prove prohibited dataset uses fail closed | AT-9 — **already satisfied**, see [`BENCHMARK_SEAL.md` §4](BENCHMARK_SEAL.md#4-controls-now-in-force) |
| 13. Interface labels scale and rubric provisional while `v0.x` | **AT-12 (new)** |
| 14. No output described as a clinical diagnosis or validated safety claim | **AT-13 (new)** |

The slice is complete when all fourteen criteria hold.

| # | Test | Pass condition |
|---|---|---|
| **AT-1** | **Ingestion with full metadata.** A synthetic conversation is ingested with source, session, turn, scenario, condition and model metadata. | The stored session has non-null `data_source_id`, `session_id`, `scenario_id`, `scenario_version`, `companion_condition`, `companion_model_version`, `simuser_model_version`, `experiment_id`; turns have contiguous `turn_index` from 0 with alternating roles. A request missing any version field is rejected with no partial write. |
| **AT-2** | **Version stamping on every result.** A rubric version and judge model/version are recorded for every result. | Every `judge_result` row has non-null `rubric_version`, `taxonomy_version`, `judge_model`, `judge_model_version`, `prompt_config_version`. A query for rows missing any of these returns zero. |
| **AT-3** | **Evidence on every non-empty score.** Every non-empty score cites supporting turn identifiers. | For every `signal_score` with `score > 0`, `evidence_turn_indices` is non-empty and every index resolves to a turn in the same session. A row violating this is rejected at write time, not cleaned up afterwards. |
| **AT-4** | **Lifecycle progression.** Processing status progresses through valid lifecycle states. | Job history for the session shows `PENDING → PROCESSING → COMPLETED` (or a `DELAYED` or `FAILED` branch). No transition skips `PROCESSING`. `COMPLETED` never appears before its durable result row exists. `DELAYED` rows carry `delay_reason`; `FAILED` rows carry `failure_reason`. |
| **AT-5** | **Trajectory reconstructible.** The trajectory update can be reconstructed from stored per-turn results. | Recomputing trajectory from the `judge_result` rows listed in `source_judge_result_ids`, using the recorded `trajectory_logic_version`, reproduces the stored trajectory state exactly — including `peak_turn_index`, escalation flags and `null_exchange_count`. |
| **AT-6** | **Alert cites its inputs.** The alert cites the exact scores, trajectory information, evidence turns and alert-rule version that produced it. | The alert row has non-empty `triggering_signal_score_ids`, `triggering_trajectory_state_ids`, `evidence_turn_indices`, and non-null `alert_rule_version`. Every referenced ID exists. Re-running the rule over those exact inputs reproduces the same severity. `context_modifier_applied` is populated whenever a modifier changed severity. |
| **AT-7** | **Reviewer can inspect the evidence.** A reviewer can inspect the underlying conversation and evidence. | From the alert, the reviewer view displays the full conversation, highlights the cited evidence turns, shows each contributing score with its explanation, shows the trajectory state, and shows rubric/judge/alert-rule versions — with no manual database access. |
| **AT-8** | **Durability across Redis loss.** Durable results survive loss of transient Redis state. | After a completed run, flushing Redis entirely leaves every session, turn, judge result, signal score, trajectory state, alert and job-history row intact and queryable, and the reviewer view renders identically. (Trivially satisfied if Redis is not used — §5.1.) |
| **AT-9** | **Psychosis-Bench isolation.** No Psychosis-Bench data enters development or tuning workflows. | The ingestion endpoint rejects `data_source_id = DS-01` and any payload matching a benchmark case. Every development, validation and tuning query filters `sealed = false`; a test asserts each such query path excludes sealed sessions. A test asserts no fixture, example or validation set in the codebase contains text from [`data/test_cases.json`](../../data/test_cases.json). |

| **AT-10** | **Invalid judge output fails visibly.** | A judge result violating the output contract is stored with `processing_status: FAILED` and a `failure_reason`, never coerced into valid scores. A reviewer sees the failure. |
| **AT-11** | **Reprocessing creates a new lineage.** | Re-scoring under a changed artefact version adds new assessment records and sets `superseded_by` on the originals. The original result, its scores and its evidence remain queryable and unmodified. The new lineage records why reprocessing occurred and which artefact versions changed. |
| **AT-12** | **Provisional artefacts are labelled.** | Every reviewer-facing figure produced under a `v0.x` scale or rubric is displayed with its provisional status. A test asserts no alert view renders a score without its `scale_version` and `rubric_status`. |
| **AT-13** | **No clinical or validated-safety language.** | No stored explanation or rendered view contains diagnostic framing or a validated-safety claim, checked against a deny-list. |

### 6.1 Additional checks worth including

Not part of the nine, but cheap and directly protective of the boundaries:

- No judge prompt contains `companion_condition`, `scenario_id`, `intended_phase_progression` or simulator hidden state ([`RUBRIC_v0.1.md` §11.4](RUBRIC_v0.1.md#11-known-limitations)).
- No stored explanation contains diagnostic language from a small deny-list (e.g. "diagnos", "psychotic", "patient").
- `null` scores never appear as 0 in the reviewer view; they render as "insufficient evidence".
- Every figure the reviewer view shows is labelled with `rubric_status` ([`RUBRIC_VALIDATION.md` §5](RUBRIC_VALIDATION.md#5-approval-gate)).

---

## 7. What is deliberately out of the tracer bullet

| Excluded | Why |
|---|---|
| Fine-tuned Transformer | Future component; requires adjudicated labels that do not exist yet |
| Live client companion API calls | The slice ingests a pre-recorded synthetic conversation; the API adapter is the next slice |
| Adaptive simulated-user engine | Conversations are supplied, not generated, in this slice |
| Psychosis-Bench benchmark runner | Separate, sealed code path; must not share the development ingestion route |
| More than one alert rule | Rule breadth is added once the audit chain holds |
| Multi-session aggregation, experiment comparison, significance testing | A later concern |
| Authentication, multi-user review workflow, notifications | Not needed to prove the chain |
| `pgvector` | Optional per [`README.md`](../../README.md); no retrieval requirement in this slice |
| Performance and scale work | No targets set ([OD-015](OPEN_DECISIONS.md#od-015)) |

---

## 8. Build order

Work proceeds in **increments**, each of which leaves the suite green and adds something a person can check. The governing rule, learned in increment 2:

> **A repository is written in the increment that first needs it, never before.** Writing all five up front would leave three with no caller and no way to tell whether their fields are right.

Each increment that adds persistence follows the same four-part shape, proven in increment 2:
domain records → repository interface with declared error modes → in-memory adapter → PostgreSQL adapter, with **one contract suite run against both**.

| # | Increment | Delivers | architecture §19 |
|---|---|---|---|
| 1 | **Governance** ✅ | Data Source Registry, Dataset Use Gate, governance tests. **Gate A satisfied.** | 12 |
| 2 | **Conversation persistence** ✅ | `Session`/`Turn` records, `ConversationRepository`, both adapters, contract suite, transaction boundary settled | — |
| 3 | **Ingestion** ✅ | `JobRepository` (+ both adapters + contract); `request_analysis` from the Dispatcher; Conversation Orchestrator writing turn and job in **one transaction** | 2, 6 |
| 4 | **Assessment** ✅ | `AssessmentRepository` (spans `assessments`, `signal_scores`, `assessment_evidence`); judge seam + `DeterministicFakeJudgeAdapter`; Result Validator/Normalizer | 3, 4, 5 |
| 5 | **Trajectory** ✅ | `TrajectoryRepository`; Trajectory Engine computing the §6.8 concepts from stored assessments | 7 |
| 6 | **Real LLM Judge** — 6a done, 6b next | Versioned prompt artefact; output schema generated from the definitions; `LLMJudgeAdapter`; judge configuration registry | — |
| 7 | **Alerting** ✅ | `AlertRepository`; Alert Engine with the single versioned rule in §5 | 8 |
| S0–S7 | **Seed pipeline** — S0 ✅, S1 ✅, S2 ✅, S3 next | Collect → Filter → Choose → Generate → Review → Label, on a shared PostgreSQL. Full plan: [`SEED_PIPELINE_PLAN.md`](SEED_PIPELINE_PLAN.md). Outside the tracer bullet (§7); supplies the corpus for the pilot and for increment 8. | — |
| 8 | **Review** | Audit trace (§6.10); Review Query (§6.11); **synthetic fixtures written here**, where content first has to make sense to a reader | 1, 9 |
| 9 | **API and view** | FastAPI ingestion endpoint; minimal reviewer view with provisional-status labelling | 9, 13, 14 |
| 10 | **Reprocessing** | New assessment lineage without overwriting the original | 11 |
| 11 | **Redis** | Only if increment 3 or 9 shows a real need (§5.1); confirm durable results survive a flush | 10 |

### 8.1 Why this order

- **Persistence before pipeline.** Each engine is written against a repository that already exists and is already proven against real SQL, so no module is built on an unvalidated storage assumption.
- **Fake judge before real judge.** Increment 4 uses `DeterministicFakeJudgeAdapter`, so the whole chain can be built and tested with no model provider and no resolution of [OD-013](OPEN_DECISIONS.md#od-013).
- **API last.** By increment 8 the orchestrator is fully tested, so FastAPI is a thin HTTP shell rather than the place where behaviour is discovered.
- **Fixtures at increment 7**, not increment 3. Content is irrelevant to ingestion and to trajectory arithmetic; it first matters when a human reads the reviewer view and asks whether the cited evidence makes sense.

### 8.2 Increment 6 in detail — planned: the real LLM Judge

**Goal:** replace `DeterministicFakeJudgeAdapter` with a real model, and find out whether a model can actually produce evidence-linked scores that pass the Result Validator.

That question is the largest unknown in the project. Everything downstream — trajectory, alerts, the reviewer view, the whole evaluation design — assumes the judge works. If a model cannot reliably cite turn identifiers and stay inside the scale, the rubric needs revising, and it is far cheaper to learn that from one adapter than after building the simulation layer.

**Delivers** no new §19 criterion. It replaces a stand-in with the real thing, which is why it is worth doing before more surface is built on top of it.

#### 8.2.1 Prerequisites — decisions, not code

| Needed | Why | Status |
|---|---|---|
| [OD-013](OPEN_DECISIONS.md#od-013): judge model, sampling settings, and what `confidence` means | The adapter pins a provider and a snapshot. Choosing by default rather than by decision is how bias enters unnoticed. | **Open — blocks pinning** |
| Judge/companion family independence | A judge sharing a family with the companion under evaluation may score it leniently, biasing the project's headline finding ([`RUBRIC_v0.1.md` §11.3](RUBRIC_v0.1.md#11-known-limitations)) | **Open** |
| Per-turn vs per-exchange jobs | Ingestion currently requests analysis for **every** turn, so a six-turn conversation creates six jobs where three are complete exchanges. Harmless while the judge is free; **doubles cost** the day it is not. | **Open — decide before wiring** |
| Where the API key lives | Architecture §14: secrets outside source control, never in logs or audit events | Straightforward, but must be explicit |

The adapter can be **built and fully tested offline** while these are open. Only pinning a provider is blocked.

#### 8.2.2 Steps

| # | Step | Detail |
|---|---|---|
| 1 | **Versioned prompt artefact** | `prompt_configuration_version` is already stamped on every assessment, and today **nothing stands behind it** — every caller passes the literal string `"example instructions"`. This step gives it real content: a versioned prompt built from [`RUBRIC_v0.1.md`](RUBRIC_v0.1.md), stored with a content hash, following the `*_VERSION_DICT` convention already in the repository. The rubric document stays canonical for humans; the prompt is a derived artefact that names the rubric version it came from. |
| 2 | **Output schema generated from the definitions** | The JSON schema for the judge's reply is generated from `config/analytical_versions.json` — signal codes, context categories, permitted score values, marker vocabulary — so the schema cannot drift from what the validator enforces. Hand-writing it twice guarantees they diverge. |
| 3 | **Turn presentation and mapping** | Turns are shown to the model by **`turn_index`**, a small integer, and the adapter maps back to `turn_id`. Asking a model to echo opaque identifiers is a reliable way to produce unusable evidence citations. |
| 4 | **`LLMJudgeAdapter`** | Implements `assess(JudgeRequest) -> RawJudgeResult`. Prefers provider-native structured output over free-text JSON parsing. |
| 5 | **Judge configuration registry** | `judge_configuration_version` resolves to a real record: model id and snapshot, temperature, token limits, prompt version, schema version. Versioned like every other artefact. |
| 6 | **Error taxonomy, and a runner change** | See §8.2.4 — the runner currently has no path for output it cannot read at all. |
| 7 | **Tests** | Offline by default; one opt-in live test. See §8.2.5. |

#### 8.2.3 Rules this increment must not break

- **No hidden chain-of-thought is requested or stored** (§6.6). No "think step by step then answer", and if a provider returns reasoning tokens they are discarded, not persisted. `RawJudgeResult` deliberately has no field to carry them.
- **Nothing about the experiment reaches the prompt.** `JudgeRequest` already excludes companion condition, scenario, intended phase and simulator state. The adapter must not reintroduce them, and must not pass `session_id` either. A test should assert the rendered prompt contains none of them.
- **Invalid output fails visibly.** The validator stays the authority. The adapter never repairs, clamps or fills in a score to get past it.
- **No retry on unreadable output.** §13: *"Do not retry schema-invalid outputs indefinitely."* A structural failure is a defect to see, not to paper over.
- **Sealed data never reaches the judge.** Already enforced by the gate; the governance tests keep it that way.

#### 8.2.4 A gap this increment must close

The runner maps `JudgeUnavailable` → `DELAYED` and `AssessmentRejected` → `FAILED`. **There is no third path**, and a real provider produces one: a reply that cannot be parsed into a `RawJudgeResult` at all — truncated, refused, or not JSON.

That is neither an outage nor a validation failure. It needs its own error and failure code, mapping to `FAILED` with a distinct reason so the two causes stay separable in the job history. Without it, an unparseable reply would surface as a confusing `DELAYED` or an exception escaping the runner.

#### 8.2.5 Testing without spending money

Mirrors the `DATABASE_URL` guardrail that already works:

- **Offline, always run:** prompt rendering, schema generation, response parsing and turn-index mapping, tested against **recorded** provider responses. Includes deliberately malformed replies — truncated JSON, a hallucinated turn index, a score of `7`, markers on the wrong signal — asserting each is rejected rather than repaired.
- **Live, opt-in:** one test gated on an API-key environment variable, skipped by default, that calls the real provider once and asserts the reply passes the validator. CI and the dependency-free suite stay untouched.

The offline tests carry most of the value. They are where parsing brittleness shows up, and they cost nothing.

#### 8.2.6 What "success" means here

Not "the adapter compiles". The increment answers a question, and the answer is an observation to record either way:

> Given a hand-written synthetic conversation, does a real model produce output that passes the Result Validator on the first attempt, reliably, across several runs?

A high rejection rate is a **finding about the rubric**, not a bug to code around — and it is exactly the kind of evidence [`RUBRIC_VALIDATION.md` §3](RUBRIC_VALIDATION.md#3-valid-triggers-for-a-rubric-change) lists as a valid trigger for a rubric change.

#### 8.2.7 Optional split

**6a** = steps 1–3 and 7 (prompt, schema, parsing, offline tests) — no provider, no cost, no [OD-013](OPEN_DECISIONS.md#od-013) dependency, and most of the risk.
**6b** = steps 4–6 (the provider call, configuration, error path) — needs the decisions above.

This split is cleaner than increment 4's was, because 6a is independently testable end to end against recorded responses.

#### 8.2.8 Explicitly not in this increment

The simulation layer — scenario controller, simulated user, persona system, companion adapter. Those are a separate programme, and three of the four have no code at all. Also not here: alerts, the reviewer view, and any claim about a model's safety.

### 8.3 Increment 5 in detail (completed)

**Goal:** derive how each signal moves across a conversation, from stored assessments, and store that derivation with the assessments that produced it.

**Delivers** architecture §19 criterion **7** — the trajectory can be recomputed from stored ordered assessments.

#### 8.3.1 Step 0 — a defect in increment 4 (fixed)

Increment 4 shipped `SignalScore` **without `specificity_markers`**, but four canonical documents require them:

| Document | Requirement |
|---|---|
| [`ANALYTICAL_TAXONOMY.md` §6.4](ANALYTICAL_TAXONOMY.md#64-escalation) | Escalation has three mechanisms, recorded separately: `by_level`, `by_frequency`, **`by_specificity`** |
| [`RUBRIC_v0.1.md` §6.3](RUBRIC_v0.1.md#6-temporal-reasoning-rules) | The judge emits `specificity_markers` for `harm_intent` *"so the trajectory component can detect escalation by specificity at constant level"* |
| [`DATA_SOURCES_AND_CONTRACTS.md` §4.5](DATA_SOURCES_AND_CONTRACTS.md#45-signal_scores-and-assessment_evidence) | `specificity_markers`, `harm_intent` only: `method`, `time`, `location`, `means`, `steps_taken` |
| §5 of this document | The one alert rule raises severity to `critical` on `harm_intent == 3` **and non-empty specificity markers** |

Without them, the trajectory engine cannot detect the case the taxonomy calls out explicitly: levels stay at 2 while content moves from "the signs mean something" to "the signs mean I must act tonight". That is escalation, it is arguably the most safety-relevant pattern in the taxonomy, and a silent inability to detect it is the worst kind of gap.

So step 0 adds markers to the vocabulary config, `RawSignalScore`, `SignalScore`, the `signal_scores` table, the validator and both adapters.

#### 8.3.2 Steps

| # | Step | Detail |
|---|---|---|
| 0 | **Specificity markers** | As above. Validator enforces the vocabulary, restricts markers to `harm_intent` ([contracts §4.5](DATA_SOURCES_AND_CONTRACTS.md#45-signal_scores-and-assessment_evidence)), and rejects markers on an unscoreable signal. |
| 1 | **Trajectory policy** | Versioned thresholds in `config/analytical_versions.json`: persistence run length, staleness, sustained-recovery count, change reference point. All provisional pending [OD-018](OPEN_DECISIONS.md#od-018). |
| 2 | **Trajectory domain records** | `SignalTrajectory` per signal; `TrajectoryState`; `TrajectoryUpdate` (§7.2 `trajectory_updates`, with `state_json`, `derived_facts_json`, `input_assessment_ids`). |
| 3 | **`TrajectoryRepository`** | Interface, declared errors, both adapters, one shared contract suite. |
| 4 | **Trajectory Engine** | The six [taxonomy §6](ANALYTICAL_TAXONOMY.md#6-temporal-concepts) concepts: current level, change, persistence, escalation, peak, recovery. |

#### 8.3.3 Rules this increment must not break

- **All three escalation mechanisms reported separately.** `by_specificity` true with `by_level` false **is** escalation.
- **Peak is always reported alongside current level**, even after a decrease. A recovery never erases the worst observed state.
- **Recovery is an observed conversational change, not a clinical conclusion.** A decrease after the companion disengaged must be distinguishable from one after grounding — the antecedent kind is recorded, and association is never written as causation.
- **`null` scores break runs; they are gaps, never zeros.** A `null` never contributes to escalation, persistence or peak, and the gap count is reported.
- **Deterministic.** The same ordered assessments and policy version produce the same result.
- **Every derived fact names the assessments and turns it came from** (§6.8).

#### 8.3.4 Decision recorded

§6.8 gives the signature `update(previous, assessment, policy)`, implying an incremental fold. This increment will instead **recompute from the ordered assessment sequence**, because §19 criterion 7 requires recomputability and a fold that carries derived facts forward can silently drift from a recomputation. To be recorded as **D-15**.

#### 8.3.5 Explicitly not in that increment

Alerts, the reviewer view, a real judge, Redis, synthetic fixtures ([D-3](#10-decisions-taken-during-implementation)).

### 8.4 Increment 4 in detail (completed)

**Goal:** score one exchange and store the result, with every score either backed by cited turns or explicitly marked unscoreable.

**Delivers** architecture §19 criteria **3** (assessments store all artefact versions), **4** (every non-empty score cites valid turns), **5** (invalid judge output fails visibly), and completes **6** (the full job lifecycle, which increment 3 only started).

**Size warning.** This is roughly twice increment 3. It can be split at step 5 if smaller steps are preferred — see §8.2.4.

#### 8.4.1 Steps

| # | Step | Detail |
|---|---|---|
| 1 | **Analytical artefact registry** | A small versioned config defining, per `scale_version`, the permitted score values; and per `taxonomy_version`, the valid signal codes and context categories. Architecture §9.2: *"Never hard-code 0 or 3 as universal bounds… keep score anchors in a versioned scale artifact."* The validator cannot do its job without this lookup. |
| 2 | **Assessment domain records** | `assessments`, `signal_scores`, `assessment_evidence` (§7.2). One aggregate — you never load evidence without its assessment. |
| 3 | **`AssessmentRepository`** | Interface, declared error modes, both adapters, one shared contract suite. Its save spans **three tables and must be atomic**: an assessment stored without its evidence rows would breach §19 criterion 4. |
| 4 | **Judge seam** | `JudgeRequest` / `RawJudgeResult` / `JudgeAdapter` (§6.6), plus `DeterministicFakeJudgeAdapter` — a test double returning canned results, so no model provider is needed and [OD-013](OPEN_DECISIONS.md#od-013) does not block this increment. |
| 5 | **Result Validator/Normalizer** | The §6.7 checks: required fields present; score values belong to the referenced `scale_version`; evidence turns exist **within the assessed window**; context values belong to the `taxonomy_version`; all version fields recorded. Plus the taxonomy's own rule: a score above zero **must** cite at least one turn. |
| 6 | **Job lifecycle transitions** | `JobRepository` gains claim/complete/delay/fail. Increment 3 only created `PENDING` jobs; this is what moves them. Attempt history is retained (§13). |
| 7 | **Analysis runner** | Drives one job end to end: claim → build window → judge → validate → store assessment → `COMPLETED`; or `DELAYED` / `FAILED` with a reason. This is the caller that justifies steps 2–6 existing. |

#### 8.4.2 Rules that increment must not break

- **`null` is not zero.** `score_value` is nullable and carries `not_assessable`. A score that could not be determined must never be stored as `0`. This is the single easiest thing to get wrong and the most damaging.
- **A score above zero cites evidence.** Enforced in the validator, because no SQL constraint can express a cross-table conditional. A test proves it.
- **Invalid output fails visibly.** §6.7: validation failures are stored as **processing failures**, never coerced into valid scores. The job goes `FAILED` with a reason; **no assessment row is written.**
- **No hidden reasoning is requested or stored** (§6.6).
- **Raw source labels stay raw.** Nothing in this increment assigns a canonical theme.

#### 8.4.3 Decisions taken, recorded in §10

| Question | Leaning |
|---|---|
| Does a failed validation store the raw judge payload for debugging? | **No.** Store a structured list of validation errors on the job instead. Storing raw provider output risks retaining exactly the hidden reasoning §6.6 forbids. |
| Where does `higher_is_better` for `sgq` live? | In the scale artefact, so no consumer can mistake a quality rating for a risk score. |
| Is the assessed window the whole session or a fixed span? | Whole session for now, stored as `window_definition`, per [OD-018](OPEN_DECISIONS.md#od-018). |

#### 8.4.4 Optional split (not taken)

If smaller steps are preferred: **4a** = steps 1–5 (storage, judge seam, validation), **4b** = steps 6–7 (lifecycle and runner). The cost of splitting is that after 4a the repository and validator have no production caller, only tests — which is the situation [D-2](#10-decisions-taken-during-implementation) exists to avoid.

#### 8.4.5 Explicitly not in that increment

Trajectory, alerts, the reviewer view, a real LLM adapter, Redis, and the synthetic fixtures ([D-3](#10-decisions-taken-during-implementation)).

### 8.5 Increment 3 in detail (completed)

1. `analysis_jobs` domain record — the §7.2 fields, with the lifecycle `PENDING → PROCESSING → COMPLETED`, branching to `DELAYED` and `FAILED`.
2. `JobRepository` interface + declared error modes; in-memory and PostgreSQL adapters; one contract suite.
3. `request_analysis` only from the Analysis Job Dispatcher (§6.4). `retry` and `get_status` are **absent, not stubbed**, until a worker exists to use them.
4. Conversation Orchestrator (§6.3): `ingest_turn`, `close_session`. It owns **turn ordering and contiguity** — the rule deliberately kept out of storage, since a unique index cannot express "no gaps".
5. Ingestion calls the Dataset Use Gate, satisfying §6.1's invariant that every ingested conversation has a registered source version. An attempt to ingest Psychosis-Bench through the normal path then fails at the gate, not at a convention.
6. A test proving turn and job commit in one unit of work, and that a rollback leaves neither — §6.3's "analysis begins only after the durable turn transaction succeeds".

## 9. Open decisions that affect this slice

| Decision | Effect if unresolved |
|---|---|
| [OD-001](OPEN_DECISIONS.md#od-001) / [OD-002](OPEN_DECISIONS.md#od-002) — scales | Build with the provisional 0–3 scale and a `scale_version` field, so a change is a migration and not a rewrite |
| [OD-004](OPEN_DECISIONS.md#od-004) — alert thresholds | The single rule's thresholds are examples; the rule is versioned so replacing it is routine |
| [OD-009](OPEN_DECISIONS.md#od-009) — dashboard technology | Build a minimal view behind a stable read API so the front end can be replaced |
| [OD-015](OPEN_DECISIONS.md#od-015) — client API contract | Not needed for this slice; blocks the following one |
| [OD-018](OPEN_DECISIONS.md#od-018) — window and thresholds | Use `window_definition: "whole_session_v0.1"` and store it, so recomputation under a new window is possible |

The slice is buildable with all of these unresolved **because** each is confined to a versioned, stored field. None of them justify waiting.

Confirmed by increments 1 and 2: nothing in [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) blocked either one. [OD-013](OPEN_DECISIONS.md#od-013) (judge model) will not block increment 4 either, because `DeterministicFakeJudgeAdapter` stands in until a provider is chosen.

---

## 10. Decisions taken during implementation

Recorded so they are not re-opened without cause. These are implementation decisions, not the stakeholder decisions in [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md).

| ID | Decision | Why |
|---|---|---|
| **D-1** | **The caller owns the transaction.** A repository takes an open connection; the interface exposes no transaction concept. | Lets one unit of work span several repositories, which §6.3 requires. Proven by `CallerOwnedTransactions` — a rollback discards every write made through the repository. The interface did not have to change. |
| **D-2** | A repository is written in the increment that first needs it. | Writing all five up front leaves three with no caller, and their field shapes are least reliable before the consuming module exists. |
| **D-3** | Synthetic fixtures are deferred to increment 7. | Ingestion and repositories do not care about content; the existing test factories are better for them. With a deterministic fake judge, trajectory and alert logic is tested with fabricated *scores*, not text. Content first matters when a person reads the reviewer view. |
| **D-4** | The Dispatcher is implemented partially — `request_analysis` now, `retry` and `get_status` absent until a worker exists. | Absent is honest; stubbed is not. |
| **D-5** | Governance and seal tests stay dependency-free and database-free. Only contract tests require PostgreSQL. | The Psychosis-Bench seal must be verifiable by anyone with no setup. CI runs them as a separate job that must never grow a dependency. |
| **D-6** | Storage owns uniqueness; the Orchestrator owns ordering and contiguity. | A unique index can express "no duplicate `turn_index`" but not "no gaps". Splitting them puts each rule where it can actually be enforced. |
| **D-7** | Reusing an idempotency key with different content raises `IdempotencyConflict` rather than replaying the stored turn. | §6.3 only requires that a retry not duplicate. Silently returning the stored turn would discard the new payload. This is stricter than the architecture requires; recorded as a deliberate choice. |
| **D-8** | Timestamps are stored as ISO-8601 `TEXT`, not `TIMESTAMPTZ`. | Exact round-trip, no timezone coercion, and the domain records declare `str`. **Revisit** if any query needs time arithmetic or ordering by time rather than by `turn_index`. |
| **D-9** | A source may declare `integrity_required: false`. The gate then skips checksum verification for it. | §6.1 ties integrity to *immutable* sources. Conversations produced at runtime have no file to hash, so requiring a checksum would make ingestion impossible. Sealed sources cannot use this: `DataSourceDefinition` still refuses any sealed source that permits more than final evaluation. |
| **D-10** | PostgreSQL test isolation discovers tables from `pg_tables` rather than naming them. | Three modules each hand-rolled `TRUNCATE`, and all three broke the moment `analysis_jobs` added a foreign key. Discovering the tables means the next one cannot break them again. |
| **D-14** | `specificity_markers` were added to `SignalScore` retrospectively, in increment 5. | Increment 4 shipped without them although four canonical documents require them. Without markers the engine cannot detect escalation at a constant numeric level — the case [taxonomy §6.4](ANALYTICAL_TAXONOMY.md#64-escalation) calls out explicitly, and the one the alert rule treats as `critical`. Restricted to `harm_intent` per [contracts §4.5](DATA_SOURCES_AND_CONTRACTS.md#45-signal_scores-and-assessment_evidence). |
| **D-15** | The Trajectory Engine **recomputes** from the ordered assessment sequence rather than folding state forward, despite §6.8's `update(previous, assessment, policy)` signature. | §19 criterion 7 requires the trajectory to be recomputable from stored ordered assessments. A fold that carries derived facts forward can silently drift from a recomputation, and the drift would be invisible. The engine also sorts defensively, so fetch order cannot change a result. |
| **D-16** | Trajectory signals are stored as JSON **arrays**, not objects. | JSONB does not preserve object key order, and signal order is part of the result. The shared contract suite caught this: the in-memory adapter passed while PostgreSQL returned the signals reordered. |
| **D-18** | Analysis is requested **per exchange**, not per turn. A user turn with no companion response yet creates no job. | The rubric's unit of assessment is the exchange, and DCS/HES are defined relative to what the user said. Scoring a lone user turn produces a half-assessment nobody asked for, and doubles the judge calls a conversation costs. Free while the judge is fake; expensive the day it is not. |
| **D-19** | The response parser translates and refuses only on **structure**; every question of whether content is acceptable belongs to the Result Validator. | One authority for the contract. A hallucinated turn number becomes an unmappable id that the validator rejects with "evidence cites turns outside the assessed window" — a better message than the parser could give, and it keeps the parser from quietly pre-empting rules it does not own. |
| **D-21** | Signal definitions, exclusion criteria and score anchors are held in committed `config/`, generated from the canonical documents, with a drift test that compares them and **skips when the documents are absent**. | `docs/foundations/` is not committed, so the renderer cannot read `ANALYTICAL_TAXONOMY.md` or `RUBRIC_v0.1.md` at run time. A second copy is therefore unavoidable; an uncompared second copy is not. The document stays canonical — when the test fails, regenerate the config, never edit it to match a stale document. |
| **D-22** | Score anchors are versioned with the **rubric**; definitions and exclusions with the **taxonomy**. | They change independently. A rubric revision can move an anchor between levels without any concept changing meaning, which is exactly the scenario [`RUBRIC_VALIDATION.md` §4](RUBRIC_VALIDATION.md#4-validation-effort-proportional-to-change) describes. |
| **D-20** | Provider identity is stamped by the adapter, never read from the model's reply. | A model can claim to be anything. Only the adapter knows which model was actually called, and the audit chain depends on that being true. |
| **D-17** | The recovery antecedent is the exchange **immediately before the first observed drop**, not the one after the peak. | Under the rubric's unit of assessment a companion response can only influence the user's *next* turn. `none_observed` is a reported outcome, so a decrease after disengagement stays distinguishable from one after grounding. |
| **D-11** | `analysis_jobs` gains a `failure_detail` column, extending §7.2. It holds **our own validation messages only**, never provider output. | §7.2 provides `failure_code` alone, which cannot say *what* was wrong. Storing the raw judge payload would risk retaining exactly the hidden reasoning §6.6 forbids, so the validator's own messages are stored instead. Two tests assert that judge output never reaches `failure_detail`. |
| **D-12** | Valid score values live in `config/analytical_versions.json`, keyed by `scale_version`; nothing hard-codes 0–3. | §9.2: *"Never hard-code 0 or 3 as universal bounds… keep score anchors in a versioned scale artifact."* When [OD-001](OPEN_DECISIONS.md#od-001) resolves, the config changes and the code does not. |
| **D-13** | `DELAYED` and `FAILED` are kept strictly apart. A judge that cannot be reached delays; a judge whose answer breaks the contract fails, and **no assessment is stored**. | §6.7: validation failures are processing failures, never coerced into valid scores. Merging the two would hide a broken scorer behind a retry loop. |

**Seed pipeline decisions (D-23…D-37).** D-23 is superseded by D-43. Taken with the project lead on 2026-09-23 while planning [`SEED_PIPELINE_PLAN.md`](SEED_PIPELINE_PLAN.md). Nothing is built yet.

| ID | Decision | Why |
|---|---|---|
| **D-23** | ~~The simulated user population is **older adults, 65+**~~ **Superseded by D-43.** Originally: treated as one population with **no age bands** for now: every simulated user is assumed to be 65 or over. Personas are a new set written for this domain; **DS-04 MindEval personas are not used** for them. | Project-lead scope decision. DS-04 describes depression/anxiety programme members, not older adults. [`PROJECT_SCOPE.md`](PROJECT_SCOPE.md) must be amended; stakeholder sign-off is [OD-023](OPEN_DECISIONS.md#od-023). |
| **D-24** | Seed sources: **PubMed E-utilities and the arXiv API** (automated, every query logged with timestamp and result ids), plus a **human-supplied URL/PDF input file** for news, legal filings and incident databases. **No forums or social media.** Every document is snapshotted as raw text with a content hash before extraction. | Documented cases rather than people's own posts, consistent with "real user conversations are not used". Snapshots stop a changing web page from silently changing a seed. |
| **D-25** | Credibility tier is derived **deterministically from `source_type`** by versioned config, never by the LLM. | A tier the extractor could set would be an unaudited model judgement about evidence quality. |
| **D-26** | Extraction goes through a config-switchable provider (`gemini` Flash pinned, temperature 0, JSON schema; or `ollama`). It is **cached by (document hash, prompt version, model version)**, immutable and inserted only if absent. Per-document state is saved, so runs resume after interruptions and rate limits. | Temperature 0 does not guarantee a deterministic hosted model; the cache is what makes seeds identical for every team member. |
| **D-27** | The Psychosis-Bench screen runs **before any hosted-model call** (denylist of upstream identifiers, then a span-hash screen against the manifest's per-prompt hashes) and again after extraction, with metadata flags for human review. It reads **only the manifest**, so anyone can run it. Sealed content never enters the shared DB. | The benchmark's own paper appears in arXiv searches. The manifest already holds a normalised hash per prompt, so nobody needs to open the sealed file to filter against it. |
| **D-28** | A **shared hosted PostgreSQL** (`SHARED_DATABASE_URL`) is the live store for official runs. Development and all tests use the local DB only, and tests and the walkthrough refuse the shared URL. A guard refuses `DROP`/`TRUNCATE`/reset against it. Shared schema changes are made only through reviewed migrations applied by one designated person. Human decisions exist only there, append-only, with actor and time. | D-10's table discovery and the walkthrough reset would destroy shared data if pointed at it. The team needs one place where caches and decisions are shared. |
| **D-29** | Milestones produce **content-addressed release bundles** (data + schema version), idempotently importable. Every reported result references a bundle, never the live DB. | A live DB moves; a result has to point at something that does not. Bundles double as backups. |
| **D-30** | Simulated user, reference companion and judge each have their own pinned model and prompt version, and **must come from different model families**. The code refuses to start otherwise. Families are declared explicitly in config; a fine-tune belongs to its base model's family. Both reference conditions share one companion model (default: pinned local Ollama) and differ only by prompt. | A generator and a scorer from one family share blind spots, which would inflate apparent agreement. One companion model with two prompts keeps the grounded/sycophantic contrast about policy alone. |
| **D-31** | Paid providers have a **hard spending cap per run, enforced in code**. The run stops as `DELAYED/SPEND_CAP` and resumes from cache. | A spending limit that exists only by convention is not a limit. |
| **D-32** | "Fixing" a weak conversation means revising the **seed or scenario** (new version) and regenerating a **new session**. The weak session is kept, marked rejected and linked by `supersedes`. | Turns are immutable ([contracts §4.2](DATA_SOURCES_AND_CONTRACTS.md#42-turns)); hand-edited turns would also make the editor an author. |
| **D-33** | Planned per-turn user labels, human-checked, are stored as **silver** labels in their own table with their own authority kind. They are **never reference labels or validation truth**. A governance test enforces this. | Contracts §8.3: generation parameters are not labels. Silver labels speed up development without contaminating the reference standard. |
| **D-34** | Gold, silver and development splits are assigned **by seed at Choose time, before any labelling**. A per-seed **exposure log** (choose, review, revise) excludes exposed people from blind annotation of that seed. | A split by conversation would let siblings from one seed land in both sets. Authors are disqualified from annotating their own material ([`DRAFT_ANNOTATOR_QUALIFICATIONS.md`](DRAFT_ANNOTATOR_QUALIFICATIONS.md)). |
| **D-35** | Theme balance at Choose is **advisory**, and any accepted gap is recorded on the selection. Realism review is a **stratified sample** (at least 1 per seed plus about 20%), rated pass/weak/fail on three criteria. Both rules are versioned config and provisional ([OD-027](OPEN_DECISIONS.md#od-027)). | Hard quotas would block work while the source supply is still unknown. A recorded gap stays visible in every report. |
| **D-36** | Benign hard negatives are **derived from chosen seeds** and linked to their parent. | News and literature almost only report harm; derived counterparts keep persona and theme matched. |
| **D-37** | Human steps (relevance, choose, review, silver check, gold submission) use a **CLI against the shared DB** until the increment 9 view exists. | Avoids pre-empting [OD-009](OPEN_DECISIONS.md#od-009). |

**Increment 7 decisions (D-38, D-39).** Taken with the project lead on 2026-09-23 as a baseline, open to change.

| ID | Decision | Why |
|---|---|---|
| **D-38** | The `alerts` record is architecture §7.2 **extended** with the contract §4.7 fields the invariants depend on: `triggering_signal_score_ids`, `evidence_turn_ids`, `context_categories_present`, `context_modifier_applied`, and the judge, rubric, taxonomy and trajectory-policy versions. Evidence is stored as **turn ids**, not indices. One alert per rule, so `rule_id` replaces §7.2's `triggered_rule_ids[]`. `contributing_assessment_ids` are the trajectory's inputs. **Omitted until they have a writer:** `theme_estimate`/`phase_estimate` ([OD-012](OPEN_DECISIONS.md#od-012)), `confidence` (undefined), and `human_review_status` (increment 8/9). Rules live in `config/alert_rules/`, apart from `analytical_versions.json`: logic is code keyed by `rule_id`, thresholds are config. | Same pattern as D-11. §19 criterion 8 cannot be met with the §7.2 fields alone, because they do not name the exact scores or the evidence. Keeping rules out of the analytical config is what versions them independently of the rubric (§6.9). |
| **D-39** | **Null companion scores and supersession.** When harm intent is elevated and escalating but SIS/HES cannot decide whether the companion addressed it, the rule stores an **`indeterminate`** alert with **no severity** and `requires_manual_review`. A known SIS of 0 or HES at threshold decides it on its own. One **active** alert per session and rule: a later decision supersedes it **only if at least as severe**, so a falling score never downgrades what a reviewer sees, and an indeterminate outcome never replaces a raised one. Alerts are never cleared automatically. `spiritual_cultural` context gets no modifier and fires at full severity. | Firing on unknown companion behaviour would invent a finding; staying silent would hide one. The peak stays in front of the reviewer (taxonomy §8 rule 4), and uncertainty escalates, never de-escalates (rule 3). Storage enforces both uniqueness rules: a unique constraint per evaluation and a partial unique index on active alerts (D-6). |

**S1 decisions (D-40).** Taken while building S1 Collect, 2026-09-23.

| ID | Decision | Why |
|---|---|---|
| **D-45** | **Re-extraction is append-only.** A document records the prompt and model version it last finished under (`processed_prompt_version`, `processed_model_version`, set on EXTRACTED and FAILED). Its **current** seeds are those from that extraction (`records.current_seeds`); seeds from other extractions stay stored, unchanged. `seeds.py reextract --stale` re-runs every finished document processed under a different prompt or model (or before versions were recorded); `--document ID` re-runs one; `--dry-run` lists without changing anything. The seal screen is not re-run (the text is unchanged), BLOCKED_SEALED documents are never re-extracted, and until a re-extraction finishes the previous seeds stay current. Seed positions are unique per extraction, not per document. Re-running under an extraction already stored is a no-op, which also makes switching back to an earlier prompt or model free. | The contracts make records append-only (§1 rule 5), and S3 selections will reference seed ids, so deleting superseded seeds would break lineage. Deriving "current" from the document, instead of marking seeds superseded, means no seed is ever edited and reverting needs no un-marking. Replaces the hand-written SQL reset, which on 2026-09-24 crashed on seeds already current. |
| **D-44** | **Seeds record an `account_kind`: `individual` or `pattern`**, and the extractor's own wording (`arc_summary`, `harm_type_candidate`) may not use diagnostic terms. Both kinds are kept. Pattern seeds are weaker evidence and are chosen deliberately at S3, with their count stated on the selection. The term list lives in `seed_vocabulary_v0.2.json`; `raw_theme_terms` are exempt because they quote the source verbatim. Prompt `extraction_prompt_v0.3`. Databases created earlier get the column without `NOT NULL`; the validator requires it on write. | Under v0.2 the model began returning general patterns as if they were accounts (3 of 4 seeds from one article) and wrote "reinforced delusional beliefs" into a seed. Dropping patterns would lose coverage for themes with few documented individuals; labelling keeps them while keeping the weaker grounding visible. Under v0.3 the same article gives 1 individual and 2 pattern seeds, in plain wording. |
| **D-43** | **Age is out of scope** (2026-09-24, project lead), superseding D-23. No age focus for simulated users or personas; no older-adult relevance check at S2 (Filter now asks a person only about **flagged** seeds); `stated_age`, `age_evidence` and `max_quote_chars` are removed from the seed format, the prompt, the schema and the database (`ALTER TABLE … DROP COLUMN`). The prompt moves to `extraction_prompt_v0.2`, so every document is re-extracted. The third realism criterion becomes "sounds like the persona". OD-023 and OD-025 are withdrawn. | Age had become a filter that rejected most published accounts (the first real seed was a 50-year-old) without being needed for the research question, which is about conversational patterns. A test asserts age is neither requested from the model nor stored. |
| **D-42** | **OpenAI is a third extraction provider**, over REST with strict Structured Outputs (`json_schema`, `strict: true`), so OpenAI enforces the seed schema itself. Standard-JSON-Schema conversion is shared with Ollama (`src/adapters/extractors/json_schema.py`; strict mode adds `additionalProperties: false`). `temperature` is sent only when configured; `null` omits it. **Active:** `gpt-5.4-mini-2026-03-17` (a dated snapshot), temperature 0; it, `gpt-4.1-mini-2025-04-14`, and the same model with temperature omitted all produced the correct seed for the synthetic test document. | The Gemini free tier allows 20 requests per day per model and was returning 503 for real extraction requests, which makes it unusable for batches. Some OpenAI model families reject any temperature but their default, the same problem NFR-1 records for Claude; determinism across the team rests on the cache (D-26), not on temperature. |
| **D-41** | **Tests get their own database.** Tests and the walkthrough read `TEST_DATABASE_URL` (default `apml_test`); the seed CLI reads `DATABASE_URL` (`apml`). Anything that truncates refuses a database whose name does not end in `_test`, and a refused reset rolls back and closes its connection. Docker creates `apml_test` on a fresh volume. | Both used `DATABASE_URL`, so a routine test run truncated the working database: the first 37 collected snapshots were lost that way on 2026-09-23. Once cached replies come from paid calls, that loses money. A naming rule fails closed (a new database is protected until someone names it for tests), and separate variable names mean an exported `DATABASE_URL` can never be picked up by the tests. Releasing the connection matters because `setUp` applies the schema first and a raising `setUp` skips `tearDown`: without it the refused run held table locks and **hung** instead of failing. |
| **D-40** | **S1 is built narrower than planned, on the standard library.** (a) HTTP, XML, HTML and JSON use only the standard library, including the Gemini and Ollama REST calls: no new dependency. (b) PubMed and arXiv snapshots are **title plus abstract**. PubMed Central full text and PDF reading are **absent**, and manual PDFs are refused with a clear error. (c) The extraction prompt version is `<template>#<hash>` over the template, vocabulary, schema and limits, so an edit without a rename still changes the cache key. (d) One document yields **zero or more seeds**; zero is a valid, cached answer. (e) Unreadable replies are **not** cached, since a retry may help; contract-breaking replies **are**, so every teammate sees the same failure. (f) A provider refusing the request itself (bad key, bad model name) **stops the run** rather than failing documents one by one. (h) Retryable HTTP failures (429, 5xx, timeouts) are retried after 5, 15 and 45 seconds, honouring `Retry-After` up to 120 seconds, before a document becomes DELAYED; the delays live in `extraction_v0.1.json` and are outside the prompt version. Rejections are never retried. (g) The shared-database guard (refusing reset, `TRUNCATE` and `apply_schema`, compared by host, port and database name) is built; **reviewed migrations and the designated person wait until the shared database is chosen**. | (a) The seal screen must stay importable on a bare interpreter (D-5), and no dependency was needed. (b) Absent beats half-working: a PDF reader would add a dependency and new failure modes before anyone has seen what the abstracts give. (c) Stops a stale cache after a prompt edit. (e) Mirrors the judge's split between OUTPUT_UNREADABLE and VALIDATION_FAILED (D-13). (g) Migration files with no database to apply them to would be code with no caller. |

**Scope decisions (D-46, D-47).** Taken with the project lead on 2026-09-24. They correct an assumption the earlier documents made, so they amend [`README.md`](../../README.md), [`PROJECT_SCOPE.md`](PROJECT_SCOPE.md) and [`architecture.md`](../../architecture.md); the proposed wording for the last two is in [`DRAFT_COMPANION_SCOPE_CHANGE.md`](DRAFT_COMPANION_SCOPE_CHANGE.md), awaiting approval.

| ID | Decision | Why |
|---|---|---|
| **D-46** | **There is one companion, and this team builds it.** There is no client companion API to wrap: the companion (an LLM with a persona prompt carrying non-sycophancy instructions, optional gated memory, optional redirection flows) is developed here for the client. The grounded-reference and sycophantic-stress-test conditions are **dropped**. `companion_condition` stays on the session record as free text and records which configuration of the one companion produced the session (example value: `companion_v0.1`); no code change is needed. The companion and the monitoring layer remain separate components: the companion acts, the monitor observes and sends signals, and no alert itself causes an action. | The earlier documents assumed an external client API, which does not exist. **Consequence:** the reference trajectories the two control conditions were meant to provide are gone, so there is no deliberately high-risk companion to show the monitor detects reinforcement, and no deliberately grounded one to show it stays quiet. Positive and negative controls must now come from the synthetic scenarios themselves, or from configurations of the one companion. The pilot's "every companion condition" coverage rule ([`ANNOTATION_GUIDE.md` §9.1](ANNOTATION_GUIDE.md#91-required-composition)) is now satisfied by one condition, and the seed-pipeline coverage gap blocked on OD-015 no longer exists in that form. |
| **D-47** | **A live demo with real users is intended**, eventually. It is **not permitted** until the preconditions in [OD-030](OPEN_DECISIONS.md#od-030) are approved. Until then every rule written for synthetic-only operation stays in force, and synthetic conversations remain the development and validation corpus. No real-user conversation may enter the system before a data source for it is registered and the Dataset Use Gate permits it. | Real users change what the system is: a missed signal becomes a missed person, escalation becomes real-time, and stored conversations become personal data. Recording the intent now lets design choices anticipate it; gating it on OD-030 stops the intent from being mistaken for approval. |

**S2 decisions (D-48).** Taken while building S2 Filter, 2026-09-24.

| ID | Decision | Why |
|---|---|---|
| **D-48** | **S2 Filter as built.** (a) Only a document's **current** seeds (D-45) are screened; superseded seeds can never be chosen. (b) Each text field of a seed (arc summary, harm type, each raw theme term) gets the same span-hash screen as documents; a match **blocks** the seed and names the field. A block cannot be overridden by anyone. (c) Two metadata flags ask a person to look: the seed's harm type resembles a sealed case's `harm_type` (content-word Jaccard ≥ `min_jaccard`, provisionally 0.5, set without looking at the sealed values), or the benchmark's name, repository or paper id appears in the source's title or abstract or in the seed. (d) A check stores **reason codes only**: never sealed text and never which case matched; re-running the same screen on the same manifest reproduces it. (e) The screen version is `overlap_screen_vX#<fingerprint>` over every setting (as D-40c), and the manifest is identified by the SHA-256 of the file. A new version or manifest re-screens every seed, and a flag raised under it needs a **fresh** decision. (f) Decisions are append-only: changing one needs an explicit `--correct` and supersedes the latest; storage enforces a single unbroken chain per check (one first review, none superseded twice, none across checks). (g) Every decision records `APML_ACTOR_ID`; recording is refused without it. (h) **Narrower than planned:** decisions are written to whichever database `--database` selects. D-28 puts human decisions only in the shared database, which is not chosen yet (as D-40g). | (a)–(b) The extractor can reproduce a memorised prompt from a clear document; the block must hold regardless of anyone's opinion. (c) Harm types such as isolation are common in legitimate sources, so removal needs a person; erring towards flagging costs only a glance. (d) Plan §4.1: only hashes and flags reach the shared database. (e) A decision made under one screen says nothing about a different screen's flag. (h) Refusing local writes would make S2 unusable until the shared database exists. **Known gap for S7:** a blocked seed's text, and the cached reply it came from, stay in the local `seeds` and `extraction_cache` tables, since both are append-only. Release export and any copy to the shared database must exclude blocked seeds and their cache entries. |

### 10.1 Known gaps carried forward

- **§19 criterion 10 holds trivially.** Assessments, trajectories and alerts are all durable in PostgreSQL, and Redis is used nowhere. It becomes a real test only if increment 11 introduces Redis.
- **`trajectory_updates.trajectory_names_its_inputs` does not reject an empty array.** `array_length('{}', 1)` is `NULL`, and a `CHECK` that evaluates to `NULL` passes. The `TrajectoryUpdate` record still refuses empty inputs, so only a raw SQL write gets through. The `alerts` table uses `cardinality()` for this reason. Fix: an `ALTER TABLE` replacing the constraint.
- **`extraction_v0.1` uses `gemini-3.6-flash`** (confirmed working 2026-09-23). `gemini-2.5-flash` still appears in the model list but returns 404 "no longer available to new users". It is a named release, not a `-latest` alias, and is part of the cache key: changing it re-extracts everything.
- **Seed collection reads abstracts only** (D-40). PMC full text and PDFs are absent.
- **Alerts do not yet carry the rubric's or rule set's `draft` status.** [`FOUNDATION_READINESS.md`](FOUNDATION_READINESS.md) asks every alert output to be labelled experimental. The versions are on the alert; the status label belongs to the increment 9 view (§19 criterion 13).
- **The in-memory adapters cannot express transactional behaviour.** The contract suite catches behavioural drift, not transactional drift. Anything depending on rollback semantics must be tested against PostgreSQL.
