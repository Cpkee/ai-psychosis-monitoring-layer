# Foundation Readiness Report

**Date:** 2026-09-16
**Version:** 0.1
**Scope:** the state of the Project Foundations Pack, distinguishing completed foundations from proposals awaiting human approval.

> ## Status statement
>
> **The project is not implementation-ready for evaluation reporting. It is ready for a bounded tracer-bullet implementation using synthetic fixtures and provisional, auditable contracts.**
>
> No rubric has been validated, no human reference labels exist, and two decisions ([OD-014](OPEN_DECISIONS.md#od-014), [OD-005](OPEN_DECISIONS.md#od-005)) block the annotation pilot, which is on the critical path for everything downstream.
>
> **Precedence.** [`architecture.md`](../../architecture.md) is the implementation source of truth. Where it conflicts with this pack, the architecture wins. Reconciled so far: contract record names follow its §7.2, and tracer-bullet acceptance follows its §19.

---

## 1. Readiness by area

| Area | State | Why |
|---|---|---|
| MVP scope and boundaries | `READY` | [`PROJECT_SCOPE.md`](PROJECT_SCOPE.md) separates MVP, future and excluded; analytical, functional and non-functional requirements are distinct; the non-diagnostic boundary is explicit throughout. |
| Analytical taxonomy | `PARTIALLY READY` | All 21 concepts have definitions, inclusion/exclusion criteria and three-way examples. Acronym expansions are verified from [`README.md`](../../README.md). **Scales are provisional** ([OD-001](OPEN_DECISIONS.md#od-001), [OD-002](OPEN_DECISIONS.md#od-002)) and temporal thresholds are unset ([OD-018](OPEN_DECISIONS.md#od-018)). |
| Rubric | `PARTIALLY READY` | [`RUBRIC_v0.1.md`](RUBRIC_v0.1.md) is complete enough to configure a judge, and is labelled **draft and unvalidated**. It has no independent reviewer, no validation set and no approval. |
| Annotation procedure | `BLOCKED BY DECISION` | [`ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md) is complete and executable in structure, but the pilot cannot start: sensitive-content policy and the named escalation contact do not exist ([OD-014](OPEN_DECISIONS.md#od-014)), and annotator qualifications are undefined ([OD-005](OPEN_DECISIONS.md#od-005)). |
| Data sources and contracts | `READY` | Thirteen sources registered with permitted-use and authority status; eleven contracts specified with required/optional/nullable fields; lifecycle and audit chain defined. |
| Rubric validation and change control | `READY` | [`RUBRIC_VALIDATION.md`](RUBRIC_VALIDATION.md) provides a checkable gate with enforcement mechanics. Its thresholds depend on [OD-017](OPEN_DECISIONS.md#od-017), but the gate itself functions without them. |
| Auditability and provenance | `READY` | End-to-end chain defined with foreign-key integrity rules; every derived contract carries version metadata; AT-2, AT-3, AT-5 and AT-6 make it testable. |
| Phase C persistence, ingestion and analysis | `PARTIALLY READY` | Increments 1–5, 6a and 7 complete: registry, gate, conversation, job, assessment, trajectory and alert persistence; dispatcher, orchestrator, judge seam and prompt, validator, runner, Trajectory Engine and Alert Engine. **527 tests**, including seed-pipeline S0–S3. One repository remains (reprocessing lineage). §19 criteria 8 and 10 now hold; 10 trivially, since Redis is used nowhere. |
| Tracer-bullet build plan | `READY` | [`IMPLEMENTATION_FOUNDATION.md`](IMPLEMENTATION_FOUNDATION.md) v0.2 — ten increments, increments 1 and 2 complete, increment 3 specified in detail, and eight implementation decisions recorded in its §10 so they are not re-litigated. |
| Tracer-bullet implementation | `READY` | [`IMPLEMENTATION_FOUNDATION.md`](IMPLEMENTATION_FOUNDATION.md) has explicit inputs, outputs, component responsibilities, build order and nine mechanically checkable acceptance tests. Buildable with all current open decisions unresolved, because each is confined to a versioned stored field. |
| Psychosis-Bench isolation | `PARTIALLY READY` | **Gate A satisfied.** Data Source Registry (§6.1) and Dataset Use Gate (§6.2) in force; 33 tests pass, including a deliberate negative test. **No loading path exists at all** — no runner, by design. Remaining: **final controlled location** ([OD-008](OPEN_DECISIONS.md#od-008)), **public repository visibility**, and the **disclosed pre-seal inspection** ([OD-021](OPEN_DECISIONS.md#od-021)). |
| Human reference labels | `BLOCKED BY DECISION` | None exist. The only human-annotated file is MindEval-derived and is now classified **prohibited as domain reference labels or as evidence of system validity**, usable only for isolated infrastructure-format tests with provenance preserved, with **no 0–6 to 0–3 conversion permitted** — enforced in code ([OD-007](OPEN_DECISIONS.md#od-007)). Blocked behind the annotation pilot. |
| Alert rules | `PARTIALLY READY` | One provisional rule, `alert_rules_v0.1`, is **implemented** and cites its scores, trajectory, evidence turns and rule version (D-38, D-39). Real thresholds require [OD-004](OPEN_DECISIONS.md#od-004) and labelled data. |
| Client companion integration | `BLOCKED BY DECISION` | No API contract and no adapter module ([OD-015](OPEN_DECISIONS.md#od-015)). |
| Theme vocabulary reconciliation | `BLOCKED BY DECISION` | [`THEME_VOCABULARY_MAPPING.md`](THEME_VOCABULARY_MAPPING.md) (`theme_mapping_v0.1`) holds both vocabularies separately with **every mapping cell UNRESOLVED**. Cross-vocabulary aggregation is prohibited. The `ai_sweetheart` inconsistency is split out as [OD-020](OPEN_DECISIONS.md#od-020). |
| Sensitive-content policy | `PARTIALLY READY` | [`DRAFT_SENSITIVE_CONTENT_POLICY.md`](DRAFT_SENSITIVE_CONTENT_POLICY.md) drafted for approval. Not in force; placeholders unassigned ([OD-014](OPEN_DECISIONS.md#od-014)). |
| Annotator qualifications | `PARTIALLY READY` | [`DRAFT_ANNOTATOR_QUALIFICATIONS.md`](DRAFT_ANNOTATOR_QUALIFICATIONS.md) drafted for approval. Not in force ([OD-005](OPEN_DECISIONS.md#od-005)). |

---

## 2. Deliverables created or updated

| File | Status | Notes |
|---|---|---|
| [`docs/foundations/PROJECT_SCOPE.md`](PROJECT_SCOPE.md) | Created | |
| [`docs/foundations/ANALYTICAL_TAXONOMY.md`](ANALYTICAL_TAXONOMY.md) | Created | Canonical for all analytical concepts |
| [`docs/foundations/RUBRIC_v0.1.md`](RUBRIC_v0.1.md) | Created | Draft and unvalidated |
| [`docs/foundations/ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md) | Created | |
| [`docs/foundations/DATA_SOURCES_AND_CONTRACTS.md`](DATA_SOURCES_AND_CONTRACTS.md) | Created | |
| [`docs/foundations/RUBRIC_VALIDATION.md`](RUBRIC_VALIDATION.md) | Created | |
| [`docs/foundations/IMPLEMENTATION_FOUNDATION.md`](IMPLEMENTATION_FOUNDATION.md) | Created | |
| [`docs/foundations/OPEN_DECISIONS.md`](OPEN_DECISIONS.md) | Created | 19 entries |
| [`docs/foundations/FOUNDATION_READINESS.md`](FOUNDATION_READINESS.md) | Created | This document |
| [`docs/foundations/BENCHMARK_SEAL.md`](BENCHMARK_SEAL.md) | Created | Provenance, access record, controls, verification |
| [`docs/foundations/THEME_VOCABULARY_MAPPING.md`](THEME_VOCABULARY_MAPPING.md) | Created | `theme_mapping_v0.1`, all cells UNRESOLVED |
| [`docs/foundations/DRAFT_SENSITIVE_CONTENT_POLICY.md`](DRAFT_SENSITIVE_CONTENT_POLICY.md) | Created | DRAFT FOR APPROVAL |
| [`docs/foundations/DRAFT_ANNOTATOR_QUALIFICATIONS.md`](DRAFT_ANNOTATOR_QUALIFICATIONS.md) | Created | DRAFT FOR APPROVAL |
| [`src/domain/provenance/data_sources.py`](../../src/domain/provenance/data_sources.py) | Created | Provenance domain types (architecture §6.1, §6.2, §6.14, §7.2) |
| [`src/modules/source_registry/registry.py`](../../src/modules/source_registry/registry.py) | Created | Data Source Registry (§6.1) |
| [`src/modules/source_registry/gate.py`](../../src/modules/source_registry/gate.py) | Created | Dataset Use Gate (§6.2) — the single authorisation seam |
| [`src/adapters/datasets/reader.py`](../../src/adapters/datasets/reader.py) | Created | Generic readers taking `AuthorizedDataUse`, never a path |
| [`config/data_sources.json`](../../config/data_sources.json) | Created | Executable source permissions |
| [`tests/test_dataset_use_gate.py`](../../tests/test_dataset_use_gate.py) | Created | Governance tests (§17) — 25 tests |
| [`tests/test_benchmark_seal.py`](../../tests/test_benchmark_seal.py) | Created | Seal, contamination, raw-label preservation — 8 tests |
| [`.github/workflows/tests.yml`](../../.github/workflows/tests.yml) | Created | Two CI jobs: governance (no dependencies) and contract (real PostgreSQL) |
| [`src/domain/conversations/`](../../src/domain/conversations/) | Created | `Session`/`Turn` records (§7.2) + `ConversationRepository` interface and declared error modes |
| [`src/adapters/memory/conversations.py`](../../src/adapters/memory/conversations.py) | Created | In-memory repository |
| [`src/adapters/postgres/`](../../src/adapters/postgres/) | Created | Schema for `sessions`/`turns`, connection + unit of work, PostgreSQL repository |
| [`tests/contract/conversation_repository.py`](../../tests/contract/conversation_repository.py) | Created | One contract suite, run against both adapters (§17) |
| [`docker-compose.yml`](../../docker-compose.yml), [`requirements.txt`](../../requirements.txt) | Created | Local PostgreSQL; `psycopg` pinned |
| [`data/sealed/psychosis_bench_manifest.json`](../../data/sealed/psychosis_bench_manifest.json) | Created | §8.1 field names; checksums only, no prompt text |
| [`README.md`](../../README.md) | Updated | Added a foundations-pack index; removed a stray editorial instruction sentence that preceded the title. No project content changed. |
| [`data/README.md`](../../data/README.md) | Created | Marks `test_cases.json` as sealed and states permitted use per file |

### 2.1 Filename and location substitutions

- The nine required deliverables are placed under [`docs/foundations/`](.) rather than the repository root. The repository had no prior documentation convention (no `docs/` directory existed), and the brief specifies `docs/foundations/` in that case. Filenames are unchanged.
- No existing file was superseded or replaced. [`README.md`](../../README.md) remains the project overview and the authoritative source for the metric acronym expansions, theme families, companion conditions, severity levels and technology stack; the foundations pack cites it rather than restating it.
- `data/README.md` is an addition not named in the brief. It exists because the sealed benchmark sits unmarked in a working directory, which is a live integrity risk.

---

## 3. Existing sources reused (not duplicated)

| Source | What was taken as authoritative |
|---|---|
| [`README.md`](../../README.md) | Project purpose; non-diagnostic boundary; three theme families; four simulation phases (as simulation states); three companion conditions; five user-trajectory indicators; **DCS/HES/SIS/SGQ names and definitions**; four severity levels; warning-output field list; data strategy; model strategy; technology stack; current limitations |
| [`data/test_cases.json`](../../data/test_cases.json) | Psychosis-Bench structure: `version 1.0`, 16 cases × 12 prompts, fields `id`/`name`/`theme`/`condition`/`harm_type`/`prompts`, six theme labels, nine harm types, Explicit/Implicit conditions |
| [`prompts/prompts.py`](../../prompts/prompts.py) | The `*_VERSION_DICT` prompt-versioning convention (`v0_1`, `v0_2`, `v0_2_3`), adopted as the precedent for `prompt_config_version` |
| [`data/human_annotations.jsonl`](../../data/human_annotations.jsonl) | Multi-annotator structure (4 independent responses per item across 60 conversations) and free-text justification fields, adopted as annotation-process precedent only |
| Empty stub files and directories committed in `5cb2c40` | Read as intent-without-implementation; recorded as unimplemented rather than assumed. **Deleted during cleanup** — they held no content and sat outside the `src/` layout adopted from architecture.md §16. |

---

## 4. Confirmed project decisions (from existing repository evidence)

These were already decided and are preserved, not re-litigated:

1. The system does not diagnose, does not replace clinical assessment, and is not approved for clinical or autonomous safety decision-making.
2. The MVP does not train a generative LLM; a small transformer classifier is a possible later addition.
3. Psychosis-Bench's 16 cases are reserved exclusively for final evaluation.
4. Development uses controlled synthetic data, balanced across themes, phases, explicitness and severity, including benign hard negatives.
5. Three theme families bound the research scope.
6. Three companion conditions: client companion, grounded reference, sycophantic stress test — the last offline only, never with real users.
7. Five user-trajectory indicators and four companion-response metrics, with the acronym expansions verified in [`README.md`](../../README.md).
8. Four severity levels: low, medium, high, critical.
9. Alerts carry supporting excerpts, explanation, scorer and model versions, confidence and human-review status.
10. Technology direction: Python, FastAPI, Pydantic, PostgreSQL (optional `pgvector`), Redis, a browser dashboard, cloud LLM APIs, versioned experiment tracking.
11. Simulation phases are simulation states, never clinical stages.

Decisions **added** by this pack, and therefore proposals awaiting approval: the exchange as the unit of assessment; the provisional 0–3 scale; `null` as a first-class insufficient-evidence value; context as a non-suppressing feature; judge/trajectory separation; append-only derived records; and the rubric approval gate.

---

## 5. Contradictions and gaps found during inventory

| # | Finding | Handling |
|---|---|---|
| 1 | **"Warning" vs "alert".** [`README.md`](../../README.md) uses "warning output" in prose and "Alert engine" in its architecture diagram. | "Alert" adopted as canonical, equivalence recorded at [taxonomy §8](ANALYTICAL_TAXONOMY.md#8-alert-severity-conceptual); confirmation raised as [OD-019](OPEN_DECISIONS.md#od-019). README not rewritten. |
| 2 | **Theme vocabularies do not correspond.** Three README families vs six theme labels in `test_cases.json`; two `ai_sweetheart` cases carry different theme labels from each other. | Both preserved as separate fields; reconciliation raised as [OD-011](OPEN_DECISIONS.md#od-011). |
| 3 | **No score scale anywhere.** No numeric definition for any of the nine concepts; `evaluation/metrics.py` empty. | Provisional 0–3 scale, labelled provisional at every use, with a stored `scale_version`; raised as [OD-001](OPEN_DECISIONS.md#od-001)/[OD-002](OPEN_DECISIONS.md#od-002). Not presented as a project decision. |
| 4 | **Sealed data sits in the working tree.** `data/test_cases.json` is committed to `main` with no marker or control. | [`data/README.md`](../../data/README.md) added; AT-9 specified; technical control raised as [OD-008](OPEN_DECISIONS.md#od-008). |
| 5 | **Imported MindEval assets could be mistaken for project data.** `human_annotations.jsonl`, `human_user_turns.jsonl`, `profiles.jsonl` and `prompts/prompts.py` describe a depression/anxiety clinician-proxy evaluation, not this project's domain. Criteria are undefined; `criterion_5` is missing; `criterion11` breaks the naming convention; values span 0–6. | Registered as DS-04 and DS-10 with explicitly prohibited uses; raised as [OD-007](OPEN_DECISIONS.md#od-007). |
| 6 | **"Phase" appears in the alert output** while phases are defined as simulation states, not clinical stages. | `phase_estimate` kept nullable with an explicit warning in the contract; raised as [OD-012](OPEN_DECISIONS.md#od-012). |
| 7 | **"Redis Iris"** appears once in the stack with no explanation. | Plain Redis assumed; raised as [OD-010](OPEN_DECISIONS.md#od-010). |
| 8 | **Dashboard technology stated two ways** (React/Next.js *or* a lightweight Python dashboard). | Deferred behind a stable read API; raised as [OD-009](OPEN_DECISIONS.md#od-009). |
| 9 | **Simulator hidden state could be mistaken for ground truth** — it tracks the same variable names as the user signals. | Explicitly prohibited as a label (DS-03, [contracts §8.3](DATA_SOURCES_AND_CONTRACTS.md#8-cross-cutting-constraints)). |
| 10 | **Stray editorial line at the top of `README.md`** ("Use the following as the top-level README…"). | Removed. It was an authoring artefact, not project content. |
| 11 | **Nine of eleven Python files are empty**, and `dashboard/` and `llm/` are empty directories. | Recorded as unimplemented throughout; no capability is described as existing. |
| 12 | **`architecture.md` §2 cites "README.md lines 139–142"** for the DCS/HES/SIS/SGQ definitions. They are now at **lines 155–158** — my README edits moved them. Content unchanged. | Recorded, not silently fixed. Line-number citations are fragile; recommend citing the heading ("Companion-response metrics") instead. `architecture.md` is not edited by this pack. |
| 13 | **`architecture.md` is untracked** and not yet committed. | Recorded. Treated as the implementation source of truth per its own header, but it carries no commit history. |

### 5.1 Transaction boundary — resolved

The open question when Phase C began was whether cross-repository atomicity (§6.3, "analysis begins only after the durable turn transaction succeeds") would force a change to the repository interface. **It did not.**

A repository takes an **open connection**, so the caller owns the transaction and several repositories can share one unit of work. The interface exposes no transaction concept. Proven by `CallerOwnedTransactions` in [`tests/test_postgres_conversation_repository.py`](../../tests/test_postgres_conversation_repository.py): a rollback discards every write made through the repository in that unit of work.

The remaining four repositories can therefore be written against this shape without re-litigating it.

No project definition was silently replaced. Every conflict above is either preserved as-is or recorded in [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md).

---

## 6. Status summary

| Item | Status |
|---|---|
| **Rubric status** | `rubric_v0.1` — **draft, unvalidated, not approved.** No independent reviewer, no validation dataset, no test results. Any figure produced under it must be labelled a draft-rubric figure. |
| **Annotation-pilot status** | **Not started.** Guide complete; pilot composition specified across 11 required categories; sample size deliberately unset ([OD-006](OPEN_DECISIONS.md#od-006)); blocked by [OD-014](OPEN_DECISIONS.md#od-014) and [OD-005](OPEN_DECISIONS.md#od-005). |
| **Data-contract status** | **Complete and implementable.** Eleven contracts with field-level required/optional/nullable marking, illustrative JSON, lifecycle and audit chain. Ready to become Pydantic models. |
| **Validation readiness** | **Gate defined, cannot yet run.** Validation requires human-adjudicated reference labels, which require the pilot. |
| **Tracer-bullet readiness** | **Ready to build.** Nine acceptance tests, explicit build order, no hidden data-contract assumptions. The only external dependency is a judge model choice ([OD-013](OPEN_DECISIONS.md#od-013)), which can be provisional. |
| **Open decisions** | **21 open, 0 decided.** Six at M1, five at M2, the remainder at M3/M4. |
| **Blocking open decisions** | [OD-014](OPEN_DECISIONS.md#od-014) (sensitive-content policy — blocks the pilot), [OD-005](OPEN_DECISIONS.md#od-005) (annotator qualifications — blocks the pilot), [OD-008](OPEN_DECISIONS.md#od-008) (benchmark seal — blocks trustworthy final evaluation), [OD-015](OPEN_DECISIONS.md#od-015) (client API — blocks the slice after the tracer bullet). |

---

## 7. Agreed sequence

Approved priority order. Items 1-3 gate item 5; item 4 runs in parallel throughout.

### Priority 1 — Protect Psychosis-Bench · **DONE this pass**

| Step | State |
|---|---|
| Record checksum and provenance | Done — [`BENCHMARK_SEAL.md` §1](BENCHMARK_SEAL.md#1-what-is-sealed), manifest with per-case and per-prompt hashes |
| Mark all 192 prompts final-evaluation-only | Done — `permitted_use: FINAL_EVALUATION_ONLY` on every case |
| Exclude from development, prompt construction, rubric tuning, fixtures, routine tests | Done — guard checks 2 and 3, CI-enforced |
| Record prior access | Done — [`§3`](BENCHMARK_SEAL.md#3-access-record), including **public remote exposure** and a **disclosed pre-seal inspection** ([OD-021](OPEN_DECISIONS.md#od-021)) |
| Technical control against accidental loading | Done — Data Source Registry + Dataset Use Gate (architecture §6.1, §6.2). **No loading path exists**: the gate refuses every purpose and no runner is implemented |
| Do not execute or inspect further cases pending the final location | In force — [OD-008](OPEN_DECISIONS.md#od-008) |

### Priority 2 — Resolve OD-014 and OD-005 · **BLOCKING the pilot**

Drafts prepared for approval, so the approver edits rather than authors:

- [`DRAFT_SENSITIVE_CONTENT_POLICY.md`](DRAFT_SENSITIVE_CONTENT_POLICY.md) — [OD-014](OPEN_DECISIONS.md#od-014). Needs the escalation owner named before anyone is exposed to the pilot.
- [`DRAFT_ANNOTATOR_QUALIFICATIONS.md`](DRAFT_ANNOTATOR_QUALIFICATIONS.md) — [OD-005](OPEN_DECISIONS.md#od-005). Needs qualifications and training confirmed before labels can become reference labels.

### Priority 3 — Minimum M1 analytical decisions

| Decision | Entry |
|---|---|
| Signal scales and anchors | [OD-001](OPEN_DECISIONS.md#od-001), [OD-002](OPEN_DECISIONS.md#od-002) |
| LLM Judge choice and configuration | [OD-013](OPEN_DECISIONS.md#od-013) |
| Agreement metric and acceptance threshold | [OD-017](OPEN_DECISIONS.md#od-017) |
| Authoritative theme vocabulary, or an explicit mapping | [OD-011](OPEN_DECISIONS.md#od-011) → [`THEME_VOCABULARY_MAPPING.md`](THEME_VOCABULARY_MAPPING.md) |
| Treatment of the inconsistent `ai_sweetheart` cases | [OD-020](OPEN_DECISIONS.md#od-020) |

### Priority 4 — Tracer bullet only, in parallel

Constraints that apply for its whole duration:

1. **Newly created synthetic fixtures only.** Never Psychosis-Bench, never MindEval-derived data. Enforced by [`tests/`](../../tests/).
2. **Store provisional versions explicitly** — scale, taxonomy, rubric, judge, prompt and alert-rule versions on every derived record ([contracts §4.9](DATA_SOURCES_AND_CONTRACTS.md#49-artifact_versions)).
3. **Label every alert output experimental**, carrying `rubric_status: draft`.
4. **No model-quality or safety claims** from anything it produces.

Specification and acceptance tests: [`IMPLEMENTATION_FOUNDATION.md`](IMPLEMENTATION_FOUNDATION.md).

### Priority 5 — Annotation pilot

Independent annotation → evidence-turn selection → agreement measurement → adjudication → error analysis → rubric revision → human approval. Procedure: [`ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md). Gated by priorities 2 and 3.

### Priority 6 — Validate before final evaluation

1. Promote the rubric from `v0.x` only after human validation ([`RUBRIC_VALIDATION.md` §5](RUBRIC_VALIDATION.md#5-approval-gate)).
2. Freeze the approved rubric, prompts, judge configuration, alert rules and code version.
3. Run Psychosis-Bench **once**, through the controlled evaluation path, pre-registered.

The seal enforces step 3's dependency on steps 1 and 2 mechanically: the loader refuses any rubric whose status is not `approved`.

---

## 8. Verification against the completion criteria

| Criterion | Met | Note |
|---|---|---|
| MVP and future scope clearly separated | Yes | [`PROJECT_SCOPE.md` §4–§6](PROJECT_SCOPE.md#4-mvp-capabilities) |
| Non-diagnostic boundary explicit | Yes | Scope §1.1, taxonomy §1, annotation guide §1, and in every alert explanation rule |
| All user signals have canonical definitions and examples | Yes | Taxonomy §3, each with positive, benign and ambiguous examples |
| DCS/HES/SIS/SGQ use verified definitions or are marked unresolved | Yes | Expansions verified from `README.md`; **scales marked unresolved** |
| Six context categories including attributed/quoted and spiritual/cultural | Yes | Taxonomy §5; attributed content is explicitly not a suppression rule |
| Escalation, peak and recovery defined as trajectory concepts | Yes | Taxonomy §6.4–§6.6, with the non-clinical caveat on recovery |
| Rubric labelled draft and unvalidated | Yes | First block of [`RUBRIC_v0.1.md`](RUBRIC_v0.1.md) |
| Human annotation and adjudication defined | Yes | Annotation guide §4, §8 |
| LLM Judge output not treated as ground truth | Yes | DS-08 authority status; validation §2 |
| Psychosis-Bench isolated from development and tuning | Yes, with a caveat | Code-level controls in force and verified, CI-enforced. Caveats: final controlled location undecided ([OD-008](OPEN_DECISIONS.md#od-008)) and one disclosed pre-seal inspection under review ([OD-021](OPEN_DECISIONS.md#od-021)) |
| Data-source permissions and authority explicit | Yes | Contracts §3, thirteen sources |
| Processing states include pending/processing/completed/delayed/failed | Yes | Contracts §6 |
| PostgreSQL and Redis responsibilities distinct | Yes | Contracts §2, §5; AT-8 |
| Every score and alert has an end-to-end provenance path | Yes | Contracts §7; AT-2, AT-3, AT-5, AT-6 |
| Rubric changes require documented validation and independent approval | Yes | Validation §4, §5 |
| Tracer bullet has testable acceptance criteria | Yes | Nine tests, each mechanically checkable |
| Every unresolved decision appears in `OPEN_DECISIONS.md` | Yes | 21 entries; every provisional statement in the pack links to one |
| Readiness report distinguishes completed, partial and blocked | Yes | §1 |

**The project is not implementation-ready for evaluation reporting. It is ready for a bounded tracer-bullet implementation using synthetic fixtures and provisional, auditable contracts.** Required definitions (scales, thresholds, agreement criteria) and all human approvals remain unresolved.
