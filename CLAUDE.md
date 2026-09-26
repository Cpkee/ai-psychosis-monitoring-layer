# AI Psychosis Monitoring Layer — working notes

A research prototype that monitors conversations with an AI companion, tracks how defined signals change across turns, and produces explainable **conversational-risk alerts** for human review.

**It does not diagnose.** No output may be described as a diagnosis, a clinical stage, or a validated safety claim. Write "the user asserts the belief without hedging", never "the user shows delusional conviction".

---

## Authority order

1. **[`architecture.md`](architecture.md)** — implementation source of truth. Module seams, interfaces, invariants, data records (§7.2), delivery phases (§18), acceptance criteria (§19). Where anything conflicts with it, it wins.
2. **[`README.md`](README.md)** — project overview. Authoritative for the DCS/HES/SIS/SGQ definitions (section "Companion-response metrics"), the three theme families, the companion (section "The companion") and severity levels.
3. **`docs/foundations/`** — analytical taxonomy, rubric, data contracts, build plan, open decisions. **Tracked in git**, despite the original intention to ignore it, and the repository is **public**: everything written here is published on push.

The build plan and every implementation decision live in `docs/foundations/IMPLEMENTATION_FOUNDATION.md` — §8 build order, §10 decisions **D-1…D-54**. Read §10 before changing anything structural; those decisions were argued once already.

**Known conflict, pending approval:** `architecture.md` and `PROJECT_SCOPE.md` still describe a client companion API, three companion conditions and real users as out of scope. D-46 and D-47 supersede those passages; the replacement wording is in `docs/foundations/DRAFT_COMPANION_SCOPE_CHANGE.md`, awaiting approval. Everywhere else, `architecture.md` still wins.

---

## Hard rules

### Sealed data

`data/test_cases.json` is **Psychosis-Bench**: 16 cases, 12 prompts each, **192 prompts, all final-evaluation-only**.

- Never read it, copy from it, or use it in fixtures, prompts, tuning or tests.
- There is **no loading path**. The Dataset Use Gate refuses every purpose, and no evaluation runner exists.
- `tests/test_benchmark_seal.py` fails if any sealed prompt appears verbatim anywhere in the repo.
- Provenance and access record: `docs/foundations/BENCHMARK_SEAL.md`. The repository is **public**, so prior exposure is unbounded; the seal protects process discipline, not secrecy.

### MindEval-derived data

`data/*.jsonl` and `prompts/prompts.py` are MindEval-derived — depression/anxiety check-ins, **not this project's domain**.

- Prohibited as domain reference labels or as evidence of system validity.
- Permitted only for isolated infrastructure-format tests.
- **Never convert its 0–6 criterion values to the project's 0–3 scale.** The criteria are undefined here and measure something else.

### Two theme vocabularies

Three README theme families and six benchmark labels **do not correspond**. Keep raw labels verbatim; never rename or merge. A canonical label requires a `theme_mapping_version`, and the record refuses one without it. All mappings are currently `UNRESOLVED`.

The two `ai_sweetheart` cases have inconsistent labels. **That inconsistency must stay visible** — a test enforces it.

### Scores

- The 0–3 scale is **provisional, not approved**. Never hard-code bounds; valid values live in `config/analytical_versions.json` keyed by `scale_version`.
- **`null` is never `0`.** "Could not tell" and "absent" are different findings. Enforced by the record, a SQL `CHECK`, and a round-trip test.
- A score above zero **must** cite supporting turn ids within the assessed window.
- Judge output is a **derived assessment**, never ground truth. Human-adjudicated labels are the reference, and none exist yet. Never tune anything against gold-split labels; they are for testing only.

### The companion and real users

- **One companion, built by this team for the client (D-46).** There is no client companion API, and the grounded and sycophantic reference conditions are dropped. The companion acts; the monitor observes and sends signals; **no alert causes an action**.
- **No real users yet (D-47).** A live demo with real users is intended, but not permitted until the preconditions in [OD-030](docs/foundations/OPEN_DECISIONS.md) are approved. No real-user conversation may enter the system before a data source for it is registered and the Dataset Use Gate permits it.
- Companion memory (Mem0 or a structured table) and redirection flows (NeMo, a Jev pre-screen) are undecided companion features ([OD-028](docs/foundations/OPEN_DECISIONS.md), [OD-029](docs/foundations/OPEN_DECISIONS.md)). The monitor's own cross-session history, if built, is a PostgreSQL query over cited findings, never Mem0.
- **How they will plug in** is specified, without code, in `docs/foundations/COMPANION_INTEGRATION_BLUEPRINT.md`: the companion–monitor contract (C2), Mem0 memory (C3) and the Jev pre-screen (C4), with interfaces, records, rules, tests to write first, and what unblocks each. Hand it to whoever implements them; **no skeletal code** before each increment is unblocked.

---

## Commands

```bash
# Governance and seal tests — bare interpreter, no dependencies, no database.
# This must never grow a dependency.
python3 -m unittest tests.test_dataset_use_gate tests.test_benchmark_seal tests.test_seal_screen \
  tests.test_overlap_screen

# Full suite.
docker compose up -d
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
TEST_DATABASE_URL=postgresql://apml:apml@localhost:5433/apml_test \
  .venv/bin/python -m unittest discover -s tests -t .
```

Without `TEST_DATABASE_URL` the PostgreSQL tests skip and everything else runs. **543 tests**; 111 skip without a database (110 PostgreSQL, plus the opt-in live extractor test: `APML_LIVE_TESTS=1`).

**Seed pipeline runbook** (`scripts/seeds.py`, against `apml`):

```bash
.venv/bin/python scripts/seeds.py collect [--manual seed_inputs/inputs.json]  # S1: sources
.venv/bin/python scripts/seeds.py extract --limit 15   # S1: paid model calls, cached
.venv/bin/python scripts/seeds.py screen                # S2: overlap screen
.venv/bin/python scripts/seeds.py review-flags          # S2: decide flagged seeds
.venv/bin/python scripts/seeds.py choose                # S3: coverage and candidates
.venv/bin/python scripts/seeds.py exclude --seed ID --reason "..."   # S3: off-topic seed
.venv/bin/python scripts/seeds.py status
```

(Interactive zsh does not treat `#` as a comment unless `setopt interactivecomments` is on: paste the commands without the comments.)

**Where results live.** Everything the pipeline produces is in the local PostgreSQL database `apml`, inside the Docker volume `ai-psychosis-monitoring-layer_apml-pgdata`: searches (`seed_query_log`), snapshots with their text (`source_documents`), raw model replies (`extraction_cache`), `seeds`, overlap checks and flag reviews, relevance decisions, selections and splits, and the exposure log. None of it is in git, and there is no shared database or release bundle yet, so **the volume is the only copy**. Back it up with `docker exec apml-postgres pg_dump -U apml -d apml -Fc > apml-$(date +%F).dump` (outside the repository; it contains article text).

`review-flags` and `choose` need `APML_ACTOR_ID` in `.env`. **A split is permanent** and viewing is recorded as exposure, so try `choose` on a copy first: `docker exec apml-postgres psql -U apml -d postgres -c "CREATE DATABASE apml_trial_test TEMPLATE apml"`, then point `DATABASE_URL` at it and drop it afterwards.

**Two local databases (D-41).** `apml_test` (`TEST_DATABASE_URL`) is for tests and the walkthrough, which truncate tables; anything that truncates refuses a database not named `*_test`. `apml` (`DATABASE_URL`) holds working data for `scripts/seeds.py`: snapshots, cached extractor replies and seeds, which cost real model calls to reproduce. **Never point tests at `apml`.**

---

## Layout and patterns

```
src/domain/      records, repository interfaces, declared error modes
src/modules/     source_registry, ingestion, analysis, trajectory, alerting, seeds
src/adapters/    memory, postgres, judge, datasets, sources, extractors, http.py
config/          data_sources.json, analytical_versions.json,
                 judge_prompts/, rubrics/, alert_rules/, seed_collection/
scripts/         walkthrough.py, seeds.py (seed pipeline CLI)
tests/contract/  one suite per repository, run against every adapter
```

**Persistence pattern** — every repository follows it:
domain records → interface with declared error modes → in-memory adapter → PostgreSQL adapter → **one contract suite run against both**.

- **The caller owns the transaction.** Repositories take an open connection; the interface has no transaction concept. This is what lets one unit of work span repositories (`unit_of_work` in `src/adapters/postgres/connection.py`).
- **Driver exceptions never escape.** Adapters translate `psycopg` errors into the declared error types.
- **Storage owns uniqueness; modules own domain rules.** A unique index expresses "no duplicate `turn_index`"; the Orchestrator expresses "no gaps".

---

## Conventions

- **British English** throughout: behaviour, analyse, prioritise.
- Say "conversation orchestration layer", not "prompt hookup". "Alert", not "warning".
- **Write no code without a caller.** A repository is written in the increment that first needs it. Unused helpers, stub methods and speculative abstractions get deleted — several already have been.
- Absent beats stubbed. The Dispatcher has `request_analysis` only; `retry` and `get_status` arrive with a worker.
- Label every illustrative identifier or value as an example.
- Timestamps are ISO-8601 `TEXT`, not `TIMESTAMPTZ` (D-8) — revisit if anything needs time arithmetic.

---

## Done

| # | Increment | Delivered |
|---|---|---|
| 1 | Governance | Data Source Registry, Dataset Use Gate, 33 governance tests. **Gate A satisfied** |
| 2 | Conversation persistence | `Session`/`Turn`, `ConversationRepository`, both adapters, transaction boundary settled |
| 3 | Ingestion | `JobRepository`, `request_analysis`, Conversation Orchestrator; turn + job commit in one transaction |
| 4 | Assessment | `AssessmentRepository` (3 tables, atomic), judge seam, `DeterministicFakeJudgeAdapter`, Result Validator, analysis runner |
| 5 | Trajectory | Trajectory Engine (6 temporal concepts), `TrajectoryRepository`, wired into the runner |
| 6a | Judge prompt + parsing | Versioned prompt artefact with real anchors and exclusions, renderer, response parser, `OUTPUT_UNREADABLE` path |
| S0 + S1 | Seed pipeline: scope and Collect | PROJECT_SCOPE §1.2 (no age focus since D-43); DS-14/DS-15 registered; PubMed/arXiv/manual collection with query log and content-hashed snapshots; **seal screen before any model call**; Gemini/Ollama extraction seam, cached; `scripts/seeds.py`; D-40 |
| 7 | Alerting | `alert_rules_v0.1`, Alert Engine, `AlertRepository` both adapters, wired into the runner in one unit of work; D-38, D-39 |
| S2 | Seed pipeline: Filter | Post-extraction overlap screen on current seeds (sealed span → blocked; harm-type or benchmark mention → flagged); `SeedFilterRepository` both adapters; append-only keep/exclude reviews with `APML_ACTOR_ID`; `seeds screen`, `seeds review-flags`; D-48 |
| S3 | Seed pipeline: Choose | Immutable, versioned selections; one split per seed for ever (gold/silver/development); advisory `coverage_targets_v0.1` with accepted gaps stored; exposure log from `choose` and `review-flags`; `seeds choose`; D-49 |

**What works end to end today:** a synthetic conversation is authorised at the gate, ingested with full metadata, scored per exchange by the fake judge, validated, stored with complete provenance, its trajectory derived across turns, and a versioned rule raises an alert citing its scores, trajectory, evidence turns and rule version — or it fails visibly with the cause distinguishable. `scripts/walkthrough.py` runs the whole path.

**Seed pipeline today (S1–S3):** published accounts are collected, screened against the sealed benchmark, extracted into seeds, screened again, and chosen into permanent splits, with exposure recorded. Each stage is tested; the chain has **not yet been run end to end on fresh material**, and the working database holds only 3 seeds.

**§19 acceptance criteria met:** 1, 2, 3, 4, 5, 6, 7, 8, 10 (trivially: Redis is used nowhere), 12.

---

## Next steps

1. **End-to-end run of S1–S3 on fresh material**, which also grows the corpus (3 seeds cannot meet any coverage target). Needs `APML_ACTOR_ID` in `.env` and a go-ahead for paid extraction; cap the first run at about 15 documents. Run `collect`, `extract` and `screen` on `apml`; trial `review-flags` and `choose` on a `*_test` copy, because splits are permanent. Run `scripts/walkthrough.py` too.
2. **Bring the plan in line with D-46 before S4.** Approve `DRAFT_COMPANION_SCOPE_CHANGE.md`; update `SEED_PIPELINE_PLAN.md` §3.4 and the S4/S5 rows (a scenario names a companion *configuration*, and S5 generates against the one companion); add a **companion v0.1** increment (pinned model, persona prompt with non-sycophancy instructions), which S5 needs.
3. **S4 Scenario and persona.**
4. **In parallel, not engineering:** approve OD-014 (now including the terms for sending packets to an external clinician) and OD-005 (arrangement proposed). They still block the annotation pilot, the only route to reference labels.

## To do

| # | Increment | State | Blocked by |
|---|---|---|---|
| 6b | `LLMJudgeAdapter`, judge config registry, generated JSON schema, opt-in live test | **Blocked** | [OD-013](docs/foundations/OPEN_DECISIONS.md) — see `docs/foundations/JUDGE_DECISIONS.md` |
| S4 | **⬅ next increment: Scenario and persona.** Plan: `docs/foundations/SEED_PIPELINE_PLAN.md`, decisions D-23…D-54 | Unblocked once the plan reflects D-46 (next step 2) | — |
| C1 | **Companion v0.1**: pinned model, persona prompt with non-sycophancy instructions. Not yet in any plan | Needed before S5 | Model choice; family separation from simulated user and judge (D-30) |
| C2–C4 | Companion–monitor contract (C2), Mem0 memory (C3), Jev pre-screen and redirection (C4). Blueprint: `docs/foundations/COMPANION_INTEGRATION_BLUEPRINT.md` | After C1 | OD-015 (C2); OD-028 (C3); OD-029 and clinical sign-off (C4) |
| S5–S8 | Generate → Review → Label → Adjudicate (S8, D-50) | After S4 and C1 | S5: [OD-022](docs/foundations/OPEN_DECISIONS.md) simulated-user pilot. S7–S8 running: OD-014, OD-005. Shared writes: OD-024, OD-026 |
| 8 | Audit trace, Review Query, **synthetic fixtures** | After 7 | — |
| 9 | FastAPI ingestion, minimal reviewer view | After 8 | [OD-009](docs/foundations/OPEN_DECISIONS.md) dashboard choice |
| 10 | Reprocessing lineage | After 9 | — |
| 11 | Redis — only if a real need appears | Last | — |

**§19 criteria still open:** 9 + 13 + 14 (increments 8–9), 11 (increment 10).

### Alerting rules (increment 7, done — these keep holding)

- Alert rules are versioned **independently of the rubric**. Changing a threshold must never mean redefining a signal.
- Every alert cites the exact scores, trajectory facts, evidence turns and rule version, and is reproducible from them.
- Context never silently suppresses an alert — a modifier is named and recorded on the alert itself.
- Uncertain context with elevated harm intent **escalates** to review; it does not de-escalate.
- No alert causes an automated action. It is not a diagnosis.
- When SIS/HES cannot decide whether the companion addressed the harm, the alert is `indeterminate`: no severity, manual review (D-39).
- One active alert per session and rule. A later decision supersedes it **only if at least as severe**; alerts are never cleared automatically (D-39).
- Provisional thresholds ([OD-004](docs/foundations/OPEN_DECISIONS.md)) do not block: the rule is versioned, so replacing it later is routine.

---

## Decisions awaiting approval — the real critical path

| Decision | Blocks | Status |
|---|---|---|
| Judge model, sampling, confidence, judge/companion family independence | Increment 6b | Brief ready: `docs/foundations/JUDGE_DECISIONS.md` |
| [OD-014](docs/foundations/OPEN_DECISIONS.md) sensitive-content policy + **named escalation owner**, and terms for sending packets to an external clinician | The annotation pilot; any packet leaving the team | Draft ready for approval |
| [OD-005](docs/foundations/OPEN_DECISIONS.md) annotator qualifications | The annotation pilot | Arrangement proposed 2026-09-25: an external clinician sets the calibration key and adjudicates; groupmates annotate blind; the LLM is tested, never a label source. Awaiting approval |

| `DRAFT_COMPANION_SCOPE_CHANGE.md` — `architecture.md` and `PROJECT_SCOPE.md` wording for D-46/D-47 | Clearing the known conflict; S4/S5 plan update | Draft ready for approval |
| [OD-030](docs/foundations/OPEN_DECISIONS.md) preconditions for a live demo with real users | Any real user | Seven preconditions listed; none in place |

OD-014 and OD-005 matter most. The pilot produces the human-adjudicated labels; without labels no rubric can be validated; without a validated rubric **no evaluation figure may be reported**. It is the longest pole and it is blocked on two approvals, not on engineering.

**One finding that needs a decision, not just a note:** current Claude models reject `temperature`/`top_p`/`top_k` with a 400, so [`PROJECT_SCOPE.md`](docs/foundations/PROJECT_SCOPE.md) **NFR-1 ("any stored score can be re-derived") cannot be met as written** and must be amended. See `JUDGE_DECISIONS.md` §2.

---

## Constraints carried forward

### Judge notes (6a, done)

- Turns are shown to the model **by number**; the parser maps back to `turn_id`. Models do not reliably echo opaque ids.
- The prompt carries **per-signal definitions, score anchors and exclusion criteria** — not a generic 0–3 ladder. A generic ladder cannot express that `harm_intent` 3 needs a specific method, time or location, which is what the alert rule treats as most serious.
- Those come from committed `config/` (`analytical_versions.json` for definitions/exclusions, `config/rubrics/` for anchors), generated from the canonical documents. `tests/test_rubric_drift.py` compares them and **skips when `docs/foundations/` is absent** (it is tracked today, but the test does not assume so). When it fails, the document wins: regenerate the config (D-21, D-22).
- Never write a signal definition in Python. Definitions belong to the taxonomy, anchors to the rubric.
- The parser refuses only on **structure** (D-19). Score 7, unknown signal, hallucinated turn number: all parse, then the validator rejects them with its own message.
- Provider identity is stamped by the adapter, never taken from the reply (D-20).
- Three failure modes stay distinct: `DELAYED` (outage), `FAILED/OUTPUT_UNREADABLE` (not a result), `FAILED/VALIDATION_FAILED` (breaks the contract).

### Trajectory notes (increment 5, done)

- Escalation reports three mechanisms separately: `by_level`, `by_frequency`, `by_specificity`. Specificity growth at a constant level **is** escalation.
- `specificity_markers` live on `SignalScore`, `harm_intent` only (D-14).
- The engine **recomputes** from ordered assessments rather than folding (D-15), and sorts defensively so fetch order cannot change a result.
- Trajectory signals are stored as JSON **arrays**; JSONB does not preserve object key order (D-16).
- The recovery antecedent is the exchange **before the first drop**, not after the peak (D-17).

### Known gaps

- In-memory adapters cannot express transactional behaviour. Anything depending on rollback must be tested against PostgreSQL.
- No real judge. `DeterministicFakeJudgeAdapter` only — every score it returns is canned, so nothing produced so far says anything about a model's behaviour.
- Seeds carry `account_kind` (`individual` / `pattern`, D-44); the extractor's own wording may not use diagnostic terms (list in `seed_vocabulary_v0.2.json`). Prompt `extraction_prompt_v0.6` admits only in-scope accounts (D-51) and lists the refused words, injected from the vocabulary, including in reported speech (D-52, D-53); searches are `queries_v0.5` (the A1 searches were withdrawn: A1 comes from journalism and case reports added by hand, D-54). Off-topic seeds are removed from choosing with `seeds.py exclude` (D-54). **The corpus is deliberately mixed** (most documents on v0.5): do not run `reextract --stale` unless you mean to regenerate every seed, which reshuffles them (D-53). After changing the prompt or model, run `scripts/seeds.py reextract --stale` (`--dry-run` first). Re-extraction is append-only: old seeds stay stored, the document records which extraction is current (D-45). Never delete seeds by hand.
- Extraction providers: `gemini` (`gemini-3.6-flash`; the free tier allows **20 requests/day/model** and was congested, so it is unusable for batches), `openai` (**active**, D-42: `gpt-5.4-mini-2026-03-17`, temperature 0, verified 2026-09-23), `ollama`. `gemini-2.5-flash` is listed but refuses new users with a 404. The model version is part of the cache key.
- Seed collection reads abstracts only; PMC full text and PDFs are absent (D-40). Shared-DB migrations wait until the shared database is chosen.
- S2 Filter (D-48): run `scripts/seeds.py screen` after any extraction; flagged seeds need `review-flags --seed ID --keep|--exclude --reason ...` with `APML_ACTOR_ID` set in `.env`. Changing `overlap_screen_v0.1.json` re-screens everything and flags need fresh decisions. Decisions go to whichever database `--database` selects until the shared one exists. **A blocked seed's text stays in local `seeds` and `extraction_cache`: S7 export must exclude blocked seeds and their cache entries.**
- S3 Choose (D-49): `scripts/seeds.py choose` shows coverage and candidates (and records that you saw them); `choose --gold IDS --silver IDS --development IDS [--drop IDS] [--dry-run] [--accept-gaps]` makes a new selection. A split never changes. Coverage targets are provisional guesses (OD-027): expect to accept gaps until the corpus grows.
- `APML_ACTOR_ID` is attribution, not authentication (plan §4.3): recorded, never verified, until increment 9 adds real sign-in.
- Labelling (S7–S8) works on spreadsheet packet files with one validated import (D-50); spreadsheet support will need a library, the first outside the governance suite's reach, confirmed when S7 is built.
- Alerts carry every version but not the `draft` status label; that belongs to the increment 9 view (§19 criterion 13).
- `trajectory_updates` `CHECK` uses `array_length`, which lets an empty array through in raw SQL (IMPLEMENTATION_FOUNDATION §10.1). `alerts` uses `cardinality`.
- No human reference labels exist, so **no rubric is validated** and no evaluation figure may be reported.
- The annotation pilot is **blocked** on OD-014 (sensitive-content policy, escalation owner) and OD-005 (annotator qualifications).

---

## Before reporting work complete

- Run the suite in **both** modes — with and without `TEST_DATABASE_URL`.
- Check for dead code: anything with no caller should not exist.
- Check internal doc links resolve.
- Update `docs/foundations/IMPLEMENTATION_FOUNDATION.md` §2.1, §8 and §10, and `FOUNDATION_READINESS.md`, after each increment.
- Never describe the project as implementation-ready for evaluation reporting. The accurate statement is: *not implementation-ready for evaluation reporting; ready for a bounded tracer-bullet implementation using synthetic fixtures and provisional, auditable contracts.*
