# Data Sources and Contracts

**Document status:** Proposed foundation, awaiting stakeholder approval
**Version:** 0.1
**Canonical for:** the data-source register, data contracts, processing lifecycle, audit chain, and storage responsibilities.

> **Precedence.** [`architecture.md`](../../architecture.md) is the implementation source of truth. Where this document and the architecture differ, **the architecture wins.** The record names and fields in §4 have been reconciled to [`architecture.md` §7.2](../../architecture.md). This document adds per-field required/optional/nullable marking, permitted-use detail and worked examples; it does not redefine the records.

The repository contains no schema definitions today; the only code is the Data Source Registry and Dataset Use Gate in [`src/`](../../src/). [`README.md`](../../README.md) names Pydantic as the intended schema layer. The contracts below are therefore given as **implementation-neutral field tables plus illustrative JSON**, ready to be expressed as Pydantic models without further decisions.

**Every identifier and value in this document is an example.**

---

## 1. Conventions

| Marker | Meaning |
|---|---|
| **R** | Required. Must be present and non-null. |
| **O** | Optional. May be absent entirely. |
| **N** | Nullable. Must be present; `null` is a meaningful value (typically "not determinable"). |

Rules that apply to every contract:

1. Identifiers are opaque strings. No meaning is encoded in their format.
2. Timestamps are UTC, ISO 8601.
3. Every **derived** record (judge result, trajectory state, alert) carries the versions of everything that produced it. A derived record without complete version metadata is invalid and is not stored.
4. `null` never means zero. See [taxonomy §7](ANALYTICAL_TAXONOMY.md#7-uncertainty-and-insufficient-evidence).
5. Records are append-only where they represent a judgement. Corrections create new records with a `supersedes` pointer; nothing is overwritten.

---

## 2. Storage responsibilities

| Store | Responsibility | Must never |
|---|---|---|
| **PostgreSQL** | Durable source of truth: conversations, turns, scenarios and conditions, judge results, signal scores, trajectory states, alerts, human annotations and adjudications, all version records, experiment history, processing job history. | — |
| **Redis** | Transient only: live session state, recent-context cache, processing-status cache, rate limiting, queue coordination. | Be the sole durable record of any alert, score, annotation, trajectory state or conversation turn. |

Derived rule (tested by [AT-8](IMPLEMENTATION_FOUNDATION.md#6-acceptance-tests)): flushing Redis entirely must lose nothing except in-flight work, which is re-derivable from PostgreSQL.

[`README.md`](../../README.md) lists `pgvector` as optional and "Redis or Redis Iris where justified"; the latter term is unclarified in the repository — [OD-010](OPEN_DECISIONS.md#od-010).

---

## 3. Data-source register

### DS-01 — Psychosis-Bench (sealed)

| Field | Value |
|---|---|
| **Source ID / name** | `DS-01` — Psychosis-Bench fixed benchmark cases |
| **Type** | Fixed external benchmark; 16 cases × 12 ordered user prompts |
| **Producer** | External ([Psychosis-Bench](https://github.com/w-is-h/psychosis-bench), [The Psychogenic Machine](https://arxiv.org/abs/2509.10970)) |
| **Consumer** | Benchmark adapter → fixed benchmark runner → client companion API |
| **Purpose** | Final, one-shot evaluation of companion safety on a predetermined escalating conversation |
| **Permitted training use** | **Prohibited** |
| **Permitted validation use** | **Prohibited** — includes prompt tuning, rubric tuning, threshold selection, model selection and judge selection |
| **Permitted final-evaluation use** | **Permitted**, as the sealed final test set only |
| **Authority / ground-truth status** | Authoritative as a *stimulus set*. Carries no per-turn score labels; it is not a label source. |
| **Storage location** | [`data/test_cases.json`](../../data/test_cases.json), now under code-level seal — see [`BENCHMARK_SEAL.md`](BENCHMARK_SEAL.md). The **final controlled location remains undecided**: [OD-008](OPEN_DECISIONS.md#od-008). |
| **Retention expectation** | Retained indefinitely, unmodified, version-pinned |
| **Access constraints** | Readable only via [`src/modules/source_registry/gate.py`](../../src/modules/source_registry/gate.py), which requires a complete pre-registration record naming an **approved** rubric version. No approved rubric exists, so every load currently fails by design. Repository is **public**; prior exposure is unbounded — see [`BENCHMARK_SEAL.md` §3.2](BENCHMARK_SEAL.md#32-remote-exposure--unbounded). |
| **Version / provenance fields** | File carries `version: "1.0"` and `metadata.total_cases: 16`; case fields `id`, `name`, `theme`, `condition` (`Explicit` / `Implicit`), `harm_type`, `prompts` |
| **Lifecycle** | Frozen. Any change constitutes a new benchmark version and invalidates comparison with prior results. |

### DS-02 — Synthetic Scenario Engine

| Field | Value |
|---|---|
| **Source ID / name** | `DS-02` — synthetic scenario specifications |
| **Type** | Generated scenario definitions (theme family, phase progression, explicitness, severity) |
| **Producer** | Scenario controller — planned; no module exists |
| **Consumer** | Simulated-user engine; experiment configuration |
| **Purpose** | The development and validation corpus, generated independently of Psychosis-Bench |
| **Permitted training use** | Permitted (future fine-tuned Transformer) |
| **Permitted validation use** | Permitted — this is the intended validation source |
| **Permitted final-evaluation use** | Permitted for synthetic-mode evaluation; does not substitute for DS-01 |
| **Authority / ground-truth status** | Not authoritative. A scenario's *intended* phase or theme is a generation parameter, **not** a label; it must never be used as ground truth for scoring. |
| **Storage location** | PostgreSQL `scenario` table |
| **Retention expectation** | Retained with the experiments that used them |
| **Access constraints** | Project team |
| **Version / provenance fields** | `scenario_id`, `scenario_version`, `generator_model`, `generator_prompt_version`, `seed` |
| **Lifecycle** | Versioned; superseded versions retained for reproducibility |

### DS-03 — Simulated-user outputs

| Field | Value |
|---|---|
| **Source ID / name** | `DS-03` — adaptive simulated-user turns |
| **Type** | Generated conversation turns with `role = "user"` |
| **Producer** | Adaptive simulated-user engine + hidden-state updater — planned; no module exists |
| **Consumer** | Companion conditions (DS-05/06/07); conversation record |
| **Purpose** | Produce conversations that respond dynamically to companion behaviour, so different companion responses yield different trajectories |
| **Permitted training use** | Permitted |
| **Permitted validation use** | Permitted |
| **Permitted final-evaluation use** | Permitted in adaptive-simulation mode |
| **Authority / ground-truth status** | Not authoritative. The simulator's **hidden state is not a label** — it is the generator's internal variable and must never be compared against judge scores as though it were truth. See [OD-012](OPEN_DECISIONS.md#od-012). |
| **Storage location** | PostgreSQL `turn` table; hidden state in a separate `simulation_state` table, never joined into scoring inputs |
| **Retention expectation** | Retained with the session |
| **Access constraints** | Project team. Hidden state must be excluded from judge and annotator inputs. |
| **Version / provenance fields** | `simuser_model`, `simuser_model_version`, `persona_id`, `prompt_config_version`, `seed` |
| **Lifecycle** | Per-session, immutable once produced |

### DS-04 — Persona and profile assets (imported)

| Field | Value |
|---|---|
| **Source ID / name** | `DS-04` — imported MindEval personas and profiles |
| **Type** | JSONL profile records |
| **Producer** | External (MindEval-derived), committed to [`data/profiles.jsonl`](../../data/profiles.jsonl) (50 records) and [`data/human_user_turns.jsonl`](../../data/human_user_turns.jsonl) (432 records) |
| **Consumer** | Persona system for the simulated user |
| **Purpose** | Realistic, varied member attributes and narratives to seed synthetic personas |
| **Permitted training use** | Permitted as generation input only |
| **Permitted validation use** | Permitted as generation input only. **Prohibited as domain reference labels or as evidence of system validity.** |
| **Permitted final-evaluation use** | Not applicable — these are inputs, not evaluation items |
| **Authority / ground-truth status** | Not authoritative for this project's taxonomy, and not evidence of system validity. These describe depression/anxiety mental-health-programme members, **not** the three psychosis-related theme families in [`README.md`](../../README.md). |
| **Access control** | Readable only via [`config/data_sources.json`](../../config/data_sources.json) |
| **Storage location** | Repository `data/`; to be loaded into PostgreSQL `persona` |
| **Retention expectation** | Retained |
| **Access constraints** | Contains synthetic personal-style attributes; treat as sensitive by convention |
| **Version / provenance fields** | None present in the files beyond `archetype_name` / `argilla_id`; a `source_dataset` and `import_version` field must be added on load |
| **Lifecycle** | Imported, read-only |

### DS-05 — Client Companion API responses

| Field | Value |
|---|---|
| **Source ID / name** | `DS-05` — client companion under evaluation |
| **Type** | External API responses, `role = "assistant"` |
| **Producer** | Client's companion service |
| **Consumer** | Conversation record → LLM Judge → response-safety auditor |
| **Purpose** | The primary object of evaluation |
| **Permitted training use** | Prohibited for generative training (no generative LLM is trained — [`PROJECT_SCOPE.md` §6](PROJECT_SCOPE.md#6-explicit-exclusions)); permitted as future classifier training input once adjudicated labels exist |
| **Permitted validation use** | Permitted |
| **Permitted final-evaluation use** | Permitted — this is the evaluation target |
| **Authority / ground-truth status** | Not a label source. It is the subject of assessment. |
| **Storage location** | PostgreSQL `turn`; raw response envelope retained |
| **Retention expectation** | Retained for the life of the experiment record |
| **Access constraints** | Governed by the client agreement — [OD-015](OPEN_DECISIONS.md#od-015) |
| **Version / provenance fields** | `companion_model`, `companion_model_version`, `api_endpoint_version`, `request_id`, `sampling_parameters`, `received_at` |
| **Lifecycle** | Immutable once recorded |

### DS-06 — Grounded Reference condition

| Field | Value |
|---|---|
| **Source ID / name** | `DS-06` — grounded reference companion |
| **Type** | Experimental control condition (empathetic, non-affirming) |
| **Producer** | Project-operated model with a fixed grounded policy prompt |
| **Consumer** | Same path as DS-05 |
| **Purpose** | Lower-risk reference trajectory for comparison |
| **Permitted training use** | Permitted as classifier training input (future) |
| **Permitted validation use** | Permitted — expected to produce low DCS/HES and high SIS/SGQ, which makes it a useful judge sanity check |
| **Permitted final-evaluation use** | Permitted as a comparison arm; never reported as the client model |
| **Authority / ground-truth status** | Not a label source. Its expected behaviour is a hypothesis to be measured, not an assumed truth. |
| **Storage location** | PostgreSQL `turn`, tagged `companion_condition = "grounded_reference"` |
| **Retention expectation** | Retained with the experiment |
| **Access constraints** | Project team |
| **Version / provenance fields** | `companion_model`, `companion_model_version`, `policy_prompt_version`, `sampling_parameters` |
| **Lifecycle** | Versioned policy prompt; offline use only |

### DS-07 — Sycophantic Stress Test condition

| Field | Value |
|---|---|
| **Source ID / name** | `DS-07` — sycophantic stress-test companion |
| **Type** | Experimental control condition (intentionally agreeable) |
| **Producer** | Project-operated model with a fixed sycophantic policy prompt |
| **Consumer** | Same path as DS-05 |
| **Purpose** | Higher-risk reference trajectory; exercises the detection path at the top of its range |
| **Permitted training use** | Permitted as classifier training input (future) |
| **Permitted validation use** | Permitted |
| **Permitted final-evaluation use** | Permitted as a comparison arm only |
| **Authority / ground-truth status** | Not a label source |
| **Storage location** | PostgreSQL `turn`, tagged `companion_condition = "sycophantic_stress"` |
| **Retention expectation** | Retained with the experiment |
| **Access constraints** | **Offline experiments only. Never exposed to real users** ([`README.md`](../../README.md), [`PROJECT_SCOPE.md` §6](PROJECT_SCOPE.md#6-explicit-exclusions)). Enforced by configuration, not convention. |
| **Version / provenance fields** | As DS-06 |
| **Lifecycle** | Versioned policy prompt; offline only |

### DS-08 — LLM Judge results

| Field | Value |
|---|---|
| **Source ID / name** | `DS-08` — LLM Judge structured scores |
| **Type** | Derived assessment records |
| **Producer** | LLM Judge under a named rubric version |
| **Consumer** | Trajectory component, alert engine, reviewer view, validation reports |
| **Purpose** | The MVP analytical scoring layer |
| **Permitted training use** | **Prohibited as labels.** Judge output must not be used as training labels for the future Transformer; that would train a model to imitate an unvalidated scorer. |
| **Permitted validation use** | Permitted as the *subject* of validation (compared against reference labels), never as the standard |
| **Permitted final-evaluation use** | Permitted only under an approved rubric version ([`RUBRIC_VALIDATION.md` §5](RUBRIC_VALIDATION.md#5-approval-gate)) |
| **Authority / ground-truth status** | **Derived assessment. Never ground truth.** |
| **Storage location** | PostgreSQL `judge_result` + `signal_score` |
| **Retention expectation** | Retained permanently; superseded by re-scoring, never overwritten |
| **Access constraints** | Project team; withheld from annotators during the blind pass ([`ANNOTATION_GUIDE.md` §4](ANNOTATION_GUIDE.md#4-blind-independent-first-pass)) |
| **Version / provenance fields** | `judge_model`, `judge_model_version`, `rubric_version`, `taxonomy_version`, `prompt_config_version`, `scored_at` |
| **Lifecycle** | Append-only. Re-scoring under a new rubric version creates new records alongside the old. |

### DS-09 — Human annotations and adjudications

| Field | Value |
|---|---|
| **Source ID / name** | `DS-09` — human labels and adjudicated reference labels |
| **Type** | Independent annotations + adjudicated reference labels |
| **Producer** | Annotators and adjudicators per [`ANNOTATION_GUIDE.md`](ANNOTATION_GUIDE.md) |
| **Consumer** | Rubric validation, agreement reporting, future classifier training |
| **Purpose** | The evaluation reference labels |
| **Permitted training use** | Permitted — adjudicated labels only, never single-annotator labels |
| **Permitted validation use** | **Required.** This is the standard against which the judge is measured. |
| **Permitted final-evaluation use** | Permitted |
| **Authority / ground-truth status** | **Adjudicated labels are the reference labels.** Individual annotations are evidence, not truth. |
| **Storage location** | PostgreSQL `human_annotation` + `adjudication` |
| **Retention expectation** | Permanent, including superseded and disagreeing labels |
| **Access constraints** | Annotator identity stored pseudonymously |
| **Version / provenance fields** | `annotator_id`, `annotation_guide_version`, `taxonomy_version`, `annotation_version`, `reference_label_set_version` |
| **Lifecycle** | Immutable per record; corrections append |

### DS-10 — Imported MindEval annotations

| Field | Value |
|---|---|
| **Source ID / name** | `DS-10` — [`data/human_annotations.jsonl`](../../data/human_annotations.jsonl) |
| **Type** | 60 annotated AI-clinician conversations, 4 independent annotator responses per criterion |
| **Producer** | External (MindEval-derived); models present: `azure/gpt-5-chat-2`, `hosted_vllm/Qwen3-235B-A22B-Instruct-2507`, `hosted_vllm/DeepSeek-R1-0528`, 20 conversations each |
| **Consumer** | Reference material for annotation-process design |
| **Purpose** | Precedent for multi-annotator structure and justification fields |
| **Permitted training use** | **Prohibited.** Not domain reference labels. |
| **Permitted validation use** | **Prohibited as domain reference labels or as evidence of system validity.** Permitted **only** for isolated infrastructure-format tests (schema round-tripping, loader behaviour, JSONL handling), and only where provenance and the incompatible criteria are preserved with the records. |
| **Permitted final-evaluation use** | Prohibited |
| **Scale conversion** | **Prohibited.** The 0–6 criterion values must never be converted into the project's provisional 0–3 scale. The scales are not commensurable and the criteria are undefined here; a conversion would fabricate reference labels out of measurements of a different domain. Enforced by [`tests/`](../../tests/). |
| **Access control** | Readable only via [`config/data_sources.json`](../../config/data_sources.json), which refuses prohibited purposes, strips `criterion_*` fields unless explicitly acknowledged, and attaches a provenance envelope to every record. |
| **Authority / ground-truth status** | **Not authoritative for this project, and not evidence of system validity.** The criteria (`criterion_1`…`criterion_4`, `criterion_6`…`criterion_10`, `criterion11`) are undefined anywhere in the repository; `criterion_5` is absent and `criterion11` breaks the naming convention. Observed values span 0–6, a different scale from [taxonomy §2](ANALYTICAL_TAXONOMY.md#2-scoring-scale-provisional). See [OD-007](OPEN_DECISIONS.md#od-007). |
| **Storage location** | Repository `data/` |
| **Retention expectation** | Retained as imported reference |
| **Access constraints** | Project team |
| **Version / provenance fields** | None in file; `source_dataset` and `import_version` must be added on any load |
| **Lifecycle** | Read-only import |

### DS-11 — Version and configuration metadata

| Field | Value |
|---|---|
| **Source ID / name** | `DS-11` — model, prompt, rubric, scenario and alert-rule version records |
| **Type** | Registry records |
| **Producer** | Project team and CI |
| **Consumer** | Every derived record; the audit chain; reproducibility checks |
| **Purpose** | Make every derived result attributable and reproducible |
| **Permitted training use** | Not applicable |
| **Permitted validation use** | Required |
| **Permitted final-evaluation use** | Required |
| **Authority / ground-truth status** | Authoritative for "what produced this record" |
| **Storage location** | PostgreSQL version tables; prompt text follows the existing `*_VERSION_DICT` convention in [`prompts/prompts.py`](../../prompts/prompts.py) |
| **Retention expectation** | Permanent. Version records are never deleted, even when superseded. |
| **Access constraints** | Project team |
| **Version / provenance fields** | Self-describing; see §4.9 |
| **Lifecycle** | Append-only |

### DS-12 — PostgreSQL (persistent system storage)

| Field | Value |
|---|---|
| **Source ID / name** | `DS-12` — durable store |
| **Type** | Relational database |
| **Producer / Consumer** | All components |
| **Purpose** | Source of truth for conversations, scores, alerts, annotations, provenance, experiment history |
| **Permitted uses** | All, subject to per-source rules above — the store does not relax a source's constraints |
| **Authority** | Authoritative |
| **Storage location** | Project database |
| **Retention expectation** | Per-record; see [OD-014](OPEN_DECISIONS.md#od-014) |
| **Access constraints** | Restricted; sealed DS-01 results should be schema- or role-separated ([OD-008](OPEN_DECISIONS.md#od-008)) |
| **Version / provenance fields** | Schema migration version recorded and stamped on experiment records |
| **Lifecycle** | Migrated forward; no destructive migrations over judgement records |

### DS-13 — Redis (transient state)

| Field | Value |
|---|---|
| **Source ID / name** | `DS-13` — transient store |
| **Type** | In-memory key-value store |
| **Producer / Consumer** | Ingestion API, orchestration workers, status endpoints |
| **Purpose** | Live session state, recent-context cache, processing status, queue coordination |
| **Permitted uses** | Caching and coordination only |
| **Authority** | **Never authoritative.** Every key must be re-derivable from PostgreSQL. |
| **Storage location** | Project Redis instance |
| **Retention expectation** | TTL-bounded; no key outlives its PostgreSQL counterpart in significance |
| **Access constraints** | Internal network only |
| **Version / provenance fields** | Keys namespaced with the schema/app version so a deploy cannot read stale-shaped values |
| **Lifecycle** | Ephemeral; flushable at any time without data loss (AT-8) |

### DS-14 — Seed source documents

| Field | Value |
|---|---|
| **Source ID / name** | `DS-14` — collected source documents (`seed-source-documents@v0.1`) |
| **Type** | Raw text snapshots of published accounts, each with a SHA-256 content hash, source URL and retrieval time |
| **Producer** | Seed collector ([`SEED_PIPELINE_PLAN.md` §3.1](SEED_PIPELINE_PLAN.md#31-collect)): PubMed E-utilities and arXiv API (every query logged), plus a human-supplied URL/PDF file for news, legal filings and incident databases. **Never forums or social media** (D-24). |
| **Consumer** | Seed extractor |
| **Purpose** | Ground synthetic scenarios in documented cases rather than only in what a generator imagines |
| **Permitted training use** | Not permitted (fails closed) |
| **Permitted validation use** | Permitted as generation input for the development and validation corpus. **Prohibited as reference labels or as evidence of validity.** |
| **Permitted final-evaluation use** | **Prohibited** |
| **Authority / ground-truth status** | Not authoritative. A reported account is not a label, and says nothing about any person's condition. |
| **Storage location** | Shared PostgreSQL (D-28); original PDFs optionally in a shared Drive folder, referenced by hash |
| **Retention expectation** | Retained with the experiments whose seeds came from it |
| **Access constraints** | Project team. What may be stored and quoted is open: [OD-024](OPEN_DECISIONS.md#od-024). Hosted storage of harm-bearing content: [OD-026](OPEN_DECISIONS.md#od-026). |
| **Version / provenance fields** | `content_hash`, `source_url`, `source_type`, `retrieved_at`, fetcher version, query-log entry |
| **Lifecycle** | Immutable per hash. A changed page is a new snapshot, never an edit. The Psychosis-Bench screen runs **before** any extraction and blocks matches (D-27). |

### DS-15 — Seeds

| Field | Value |
|---|---|
| **Source ID / name** | `DS-15` — seeds (`seeds@v0.1`) |
| **Type** | Structured scenario parameters extracted from a DS-14 snapshot: theme family (vocabulary A only), paraphrased arc, reported phase progression, harm type, explicitness, credibility tier |
| **Producer** | Versioned extractor (provider seam, cached by document hash + prompt version + model version; D-26). Credibility tier assigned **by rule from source type**, never by the model (D-25). |
| **Consumer** | Seed filter and selection; Synthetic Scenario Engine (DS-02) |
| **Purpose** | The input from which scenarios are built. No age focus (D-43) |
| **Permitted training use** | Not permitted (fails closed) |
| **Permitted validation use** | Permitted as generation input. **Prohibited as reference labels or as evidence of validity.** |
| **Permitted final-evaluation use** | **Prohibited** |
| **Authority / ground-truth status** | Not authoritative. A seed's theme, phase progression and harm type are **generation parameters, not labels** (§8.3). |
| **Storage location** | Shared PostgreSQL (D-28) |
| **Retention expectation** | Retained with the experiments that used them; every version kept |
| **Access constraints** | Project team. Split assignment (gold/silver/development) and the exposure log govern who may later annotate its conversations (D-34). |
| **Version / provenance fields** | `seed_id`, `seed_version`, `source_document_id`, `content_hash`, extraction provider, model version, prompt version, schema version |
| **Lifecycle** | Versioned. A revision after realism review creates a new version (D-32). |

---

## 4. Data contracts

Record names follow [`architecture.md` §7.2](../../architecture.md). A record named here is the same record named there; where a field name differs, the architecture's name is canonical and this document's older name is given as an alias in the notes column.

| This document | architecture.md §7.2 | Note |
|---|---|---|
| §4.1 | `sessions` | plus `data_source_versions` for source identity |
| §4.2 | `turns` | |
| §4.3 | `runs` | scenario/condition metadata |
| §4.4 | `assessments` | formerly "judge result" |
| §4.5 | `signal_scores`, `assessment_evidence` | evidence is now its own record |
| §4.6 | `trajectory_updates` | formerly "trajectory state" |
| §4.7 | `alerts` | |
| §4.8 | `annotations`, `adjudications` | |
| §4.9 | `artifact_versions` | formerly "version records" |
| §4.10 | `analysis_jobs` | formerly "processing job" |


### 4.1 `sessions`

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `session_id` | R | string | Primary identifier |
| `data_source_id` | R | enum | `DS-01` … `DS-07`; identifies provenance and therefore permitted use |
| `mode` | R | enum | `fixed_benchmark` \| `adaptive_simulation` |
| `scenario_id` | N | string | `null` for fixed-benchmark sessions |
| `benchmark_case_id` | N | string | e.g. `conduit_explicit`; `null` outside `DS-01` |
| `companion_condition` | R | enum | `client_companion` \| `grounded_reference` \| `sycophantic_stress` |
| `companion_model` | R | string | |
| `companion_model_version` | R | string | |
| `persona_id` | N | string | |
| `simuser_model` / `simuser_model_version` | N | string | `null` for fixed-benchmark |
| `seed` | N | integer | |
| `experiment_id` | R | string | Groups sessions in one experiment run |
| `sealed` | R | boolean | `true` for `DS-01`. Sealed sessions are excluded from every tuning and validation query. |
| `started_at` / `ended_at` | R / N | timestamp | |
| `processing_status` | R | enum | §6 |
| `schema_version` | R | string | |

### 4.2 `turns`

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `turn_id` | R | string | |
| `session_id` | R | string | |
| `turn_index` | R | integer | 0-based, strictly increasing, no gaps. **The evidence-citation key.** |
| `role` | R | enum | `user` \| `assistant` |
| `content` | R | string | Verbatim |
| `source_prompt_index` | N | integer | For `DS-01`, the index into the case's `prompts` array |
| `model` / `model_version` | N | string | Present for `assistant` turns and generated `user` turns |
| `prompt_config_version` | N | string | |
| `request_id` | N | string | Client API correlation |
| `created_at` | R | timestamp | |

Turns are immutable. A re-run produces a new session, never an edited turn.

### 4.3 `runs`, scenario and companion condition

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `scenario_id` | R | string | |
| `scenario_version` | R | string | |
| `theme_family` | R | enum | Three families per [`README.md`](../../README.md); see [OD-011](OPEN_DECISIONS.md#od-011) |
| `intended_phase_progression` | R | array of enum | Simulation control states, **not labels** ([`README.md`](../../README.md)) |
| `explicitness` | R | enum | `explicit` \| `implicit`, matching the `DS-01` `condition` field |
| `intended_harm_type` | N | string | Generation parameter, not a label |
| `benign_hard_negative` | R | boolean | Marks deliberate false-alarm probes |
| `generator_model` / `generator_prompt_version` / `seed` | R | string / string / integer | |
| `companion_condition` | R | enum | As §4.1 |
| `policy_prompt_version` | N | string | Required for `grounded_reference` and `sycophantic_stress` |
| `offline_only` | R | boolean | **Must be `true` for `sycophantic_stress`** |

### 4.4 `assessments`

Full field list in [`RUBRIC_v0.1.md` §9](RUBRIC_v0.1.md#9-required-structured-output). Storage adds:

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `judge_result_id` | R | string | |
| `session_id` | R | string | |
| `exchange_user_turn_index` | R | integer | |
| `exchange_assistant_turn_index` | N | integer | |
| `context_category` | R | enum | Six values ([taxonomy §5](ANALYTICAL_TAXONOMY.md#5-context-categories)) |
| `context_secondary_category` | N | enum | |
| `context_confidence` | R | enum | `high` \| `medium` \| `low` |
| `context_frame_established_at` | N | integer | |
| `overall_explanation` | R | string | |
| `requires_human_review` | R | boolean | |
| `judge_model` / `judge_model_version` | R | string | |
| `rubric_version` / `taxonomy_version` / `prompt_config_version` | R | string | |
| `processing_status` | R | enum | §6 |
| `failure_reason` | N | string | Required when status is `FAILED` |
| `superseded_by` | N | string | Set when re-scored under a newer rubric version |
| `scored_at` | R | timestamp | |

### 4.5 `signal_scores` and `assessment_evidence`

One row per signal or metric per judge result (nine rows for a complete result).

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `signal_score_id` | R | string | |
| `judge_result_id` | R | string | |
| `session_id` | R | string | Denormalised for query and audit |
| `concept_id` | R | enum | Taxonomy ID: `belief_conviction`, `pattern_seeking`, `ai_dependency`, `social_withdrawal`, `harm_intent`, `dcs`, `hes`, `sis`, `sgq` |
| `concept_kind` | R | enum | `user_signal` \| `ai_behaviour` |
| `score` | N | integer | 0–3 or `null` ([taxonomy §2](ANALYTICAL_TAXONOMY.md#2-scoring-scale-provisional)) |
| `confidence` | R | enum | `high` \| `medium` \| `low` |
| `insufficient_evidence` | R | boolean | True iff `score` is `null` |
| `evidence_turn_indices` | R | array of integer | **Non-empty when `score` > 0** |
| `explanation` | N | string | Required when `score` > 0 |
| `higher_is_better` | O | boolean | `true` for `sgq` only |
| `warranted` | O | boolean \| null | `sis` only |
| `specificity_markers` | O | array of enum | `harm_intent` only: `method`, `time`, `location`, `means`, `steps_taken` |
| `scale_version` | R | string | e.g. `scale_0_3_v0.1`; makes a future scale change detectable |

The same contract stores **human** scores, distinguished by the parent record type (§4.8). Judge scores and human scores are never written to the same rows.

### 4.6 `trajectory_updates`

One row per session per concept per update, append-only.

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `trajectory_state_id` | R | string | |
| `session_id` | R | string | |
| `concept_id` | R | enum | As §4.5 |
| `as_of_turn_index` | R | integer | The exchange this state was computed through |
| `window_definition` | R | string | e.g. `whole_session_v0.1` ([OD-018](OPEN_DECISIONS.md#od-018)) |
| `current_level` | N | integer | [Taxonomy §6.1](ANALYTICAL_TAXONOMY.md#61-current-level) |
| `current_level_from_turn_index` | N | integer | Makes staleness visible |
| `stale` | R | boolean | |
| `change` | N | integer | [§6.2](ANALYTICAL_TAXONOMY.md#62-change-over-time) |
| `change_direction` | N | enum | `increasing` \| `decreasing` \| `stable` \| `volatile` |
| `persistence_level` / `persistence_run_length` | N | integer | [§6.3](ANALYTICAL_TAXONOMY.md#63-persistence) |
| `persistence_first_turn_index` / `persistence_last_turn_index` | N | integer | |
| `escalation_by_level` / `escalation_by_frequency` / `escalation_by_specificity` | R | boolean | [§6.4](ANALYTICAL_TAXONOMY.md#64-escalation) |
| `escalation_turn_indices` | N | array of integer | Ordered exchanges forming the escalation |
| `peak_level` | N | integer | [§6.5](ANALYTICAL_TAXONOMY.md#65-peak) |
| `peak_turn_index` | N | integer | |
| `recovery_decrease` / `recovery_sustained_exchanges` | N | integer | [§6.6](ANALYTICAL_TAXONOMY.md#66-recovery--response-to-intervention) |
| `recovery_candidate_antecedent_turn_index` | N | integer | Association only, never causation |
| `recovery_antecedent_kind` | N | enum | `grounding` \| `intervention` \| `none_observed` \| `topic_change` |
| `null_exchange_count` | R | integer | Gaps, so trajectory density is visible |
| `source_judge_result_ids` | R | array of string | **Every input, so the state is reconstructible (AT-5)** |
| `trajectory_logic_version` | R | string | |
| `computed_at` | R | timestamp | |

### 4.7 `alerts`

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `alert_id` | R | string | |
| `session_id` | R | string | |
| `as_of_turn_index` | R | integer | |
| `severity` | R | enum | `low` \| `medium` \| `high` \| `critical` ([taxonomy §8](ANALYTICAL_TAXONOMY.md#8-alert-severity-conceptual)) |
| `alert_rule_id` / `alert_rule_version` | R | string | **The rule that fired** |
| `triggering_signal_score_ids` | R | array of string | Exact score records used |
| `triggering_trajectory_state_ids` | R | array of string | Exact trajectory states used |
| `evidence_turn_indices` | R | array of integer | Union of the evidence of the triggering scores; must be non-empty |
| `context_categories_present` | R | array of enum | Carried through so context influence is visible |
| `context_modifier_applied` | N | string | Named, versioned modifier if the rule adjusted for context; `null` if none. **Never implicit.** |
| `explanation` | R | string | Evidence-grounded, plain language, non-diagnostic |
| `confidence` | R | enum | |
| `theme_estimate` | N | string | From [`README.md`](../../README.md) warning output; unresolved for real conversations ([OD-012](OPEN_DECISIONS.md#od-012)) |
| `phase_estimate` | N | string | Same; **must never be presented as a clinical stage** |
| `judge_model_version` / `rubric_version` / `taxonomy_version` / `trajectory_logic_version` | R | string | Full provenance on the alert itself |
| `human_review_status` | R | enum | `not_reviewed` \| `in_review` \| `confirmed` \| `rejected` \| `amended` |
| `superseded_by` | N | string | |
| `created_at` | R | timestamp | |

An alert is invalid, and must not be stored, if `evidence_turn_indices` is empty or any triggering ID is missing.

### 4.8 `annotations` and `adjudications`

**Annotation**

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `annotation_id` | R | string | |
| `session_id` / `exchange_user_turn_index` | R | string / integer | Same unit as the judge ([`ANNOTATION_GUIDE.md` §3](ANNOTATION_GUIDE.md#3-annotation-unit)) |
| `annotator_id` | R | string | Pseudonymous |
| `blind` | R | boolean | Must be `true` for first-pass labels |
| `calibration` | R | boolean | Excluded from agreement statistics when `true` |
| `single_reviewer` | R | boolean | `true` batches produce no reference labels |
| `context_category` / `context_secondary_category` | R / N | enum | |
| `scores` | R | array | Score objects per §4.5 |
| `uncertainty_flag` | R | enum | `none` \| `between_levels` \| `insufficient_evidence` \| `context_ambiguous` |
| `notes` | N | string | Required when `uncertainty_flag` ≠ `none` |
| `annotation_guide_version` / `taxonomy_version` / `annotation_version` | R | string | |
| `supersedes` | N | string | |
| `submitted_at` | R | timestamp | |

**Adjudication**

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `adjudication_id` | R | string | |
| `session_id` / `exchange_user_turn_index` | R | string / integer | |
| `input_annotation_ids` | R | array of string | The frozen independent labels |
| `adjudicator_id` | R | string | Must not appear in `input_annotation_ids`' annotators |
| `disagreement_types` | R | array of enum | `agreement` \| `partial_evidence_disagreement` \| `adjacent_disagreement` \| `major_disagreement` \| `safety_disagreement` |
| `adjudicated_scores` | R | array | Score objects per §4.5 |
| `adjudicated_context_category` | R | enum | |
| `rationale` | R | string | **Mandatory for every adjudicated item** |
| `unresolvable` | R | boolean | Excluded from reference labels when `true` |
| `reference_label_set_version` | R | string | |
| `adjudicated_at` | R | timestamp | |

### 4.9 `artifact_versions`

One contract shape, one row per released version of anything.

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `version_record_id` | R | string | |
| `artefact_kind` | R | enum | `model` \| `prompt_config` \| `rubric` \| `taxonomy` \| `scenario` \| `alert_rule` \| `trajectory_logic` \| `annotation_guide` \| `reference_label_set` \| `schema` |
| `artefact_id` | R | string | |
| `version` | R | string | e.g. `rubric_v0.1` |
| `status` | R | enum | `draft` \| `approved` \| `superseded` \| `withdrawn` |
| `change_summary` / `rationale` | R | string | |
| `author` | R | string | |
| `independent_reviewer` | N | string | **Required (non-null) for `status = approved` on `rubric` and `alert_rule`** |
| `validation_dataset_version` | N | string | Required for `approved` rubric versions |
| `test_results_ref` | N | string | Pointer to the validation report |
| `known_limitations` | N | string | |
| `approval_date` | N | timestamp | Required for `approved` |
| `supersedes` | N | string | |
| `content_hash` | R | string | Detects silent edits to prompts or rules |

Alert rules additionally record their executable definition and the concepts and thresholds they read, so an alert can be explained without reading code.

### 4.10 `analysis_jobs`

| Field | R/O/N | Type | Notes |
|---|---|---|---|
| `job_id` | R | string | |
| `job_kind` | R | enum | `ingest` \| `judge_exchange` \| `trajectory_update` \| `alert_evaluation` \| `benchmark_run` |
| `session_id` | N | string | |
| `target_turn_index` | N | integer | |
| `status` | R | enum | §6 |
| `attempt` | R | integer | |
| `delay_reason` | N | string | Required when status is `DELAYED` |
| `failure_reason` | N | string | Required when status is `FAILED` |
| `enqueued_at` / `started_at` / `completed_at` | R / N / N | timestamp | |
| `worker_id` | N | string | |
| `app_version` | R | string | |

Status is cached in Redis for fast reads and **written to PostgreSQL as the durable record**. On disagreement, PostgreSQL wins.

### 4.11 Illustrative alert (example values only)

```json
{
  "alert_id": "example-alert-0007",
  "session_id": "example-session-0042",
  "as_of_turn_index": 12,
  "severity": "critical",
  "alert_rule_id": "example-rule-harm-intent-unaddressed",
  "alert_rule_version": "alert_rules_v0.1",
  "triggering_signal_score_ids": ["example-ss-0031", "example-ss-0034", "example-ss-0035"],
  "triggering_trajectory_state_ids": ["example-ts-0012"],
  "evidence_turn_indices": [9, 11, 12],
  "context_categories_present": ["personal"],
  "context_modifier_applied": null,
  "explanation": "In turn 11 the user states a specific intention with a location and timeframe, escalating from the unspecified statements in turns 7 and 9. The companion response in turn 12 does not address the stated intention and offers no route to support.",
  "confidence": "high",
  "theme_estimate": "sentient_or_godlike_ai",
  "phase_estimate": null,
  "judge_model_version": "example-2026-01-15",
  "rubric_version": "rubric_v0.1",
  "taxonomy_version": "taxonomy_v0.1",
  "trajectory_logic_version": "trajectory_v0.1",
  "human_review_status": "not_reviewed",
  "created_at": "2026-09-16T12:00:05Z"
}
```

---

## 5. Where each contract lives

| Contract | PostgreSQL | Redis |
|---|---|---|
| Conversation, Turn | Durable table | Recent-context cache (TTL) |
| Scenario / condition | Durable table | — |
| Judge result, Signal score | Durable tables | — |
| Trajectory state | Durable, append-only | Latest-state cache (TTL) |
| Alert | Durable, append-only | — |
| Annotation, Adjudication | Durable tables | — |
| Version records | Durable, permanent | — |
| Processing job/status | Durable history | Live status + queue coordination |

---

## 6. Processing lifecycle

```text
PENDING → PROCESSING → COMPLETED
                ├──→ DELAYED → COMPLETED
                └──→ FAILED
```

| State | Meaning | Entry condition | Exit |
|---|---|---|---|
| `PENDING` | Accepted and queued; nothing computed | Job created | → `PROCESSING` |
| `PROCESSING` | A worker holds the job | Worker claim recorded with `worker_id`, `attempt` | → `COMPLETED`, `DELAYED` or `FAILED` |
| `DELAYED` | Deferred and retryable (upstream rate limit, transient API error, backpressure) | `delay_reason` required | → `PROCESSING` on retry, → `COMPLETED`, or → `FAILED` on retry exhaustion |
| `COMPLETED` | Durable result written to PostgreSQL | Result persisted **before** the transition | Terminal |
| `FAILED` | Not completed and not retryable | `failure_reason` required | Terminal |

Rules:

1. `COMPLETED` is set only after the durable write succeeds. A status that says complete with no stored result is a defect.
2. `DELAYED` is distinct from `FAILED`: delay is expected operational behaviour, failure is not. They are never merged in reporting.
3. A `FAILED` judge result still creates a `judge_result` row with `processing_status: FAILED`, `failure_reason`, and all `null` scores — so gaps are visible rather than silent.
4. Session-level status is derived from its jobs and is not independently authoritative.
5. Redis holds live status for fast reads; PostgreSQL holds the history.

---

## 7. Minimum audit chain

Every alert must resolve this chain end to end, entirely from PostgreSQL:

```text
Data source                (conversation.data_source_id, sealed)
→ Session                  (session_id, experiment_id, companion_condition, companion_model_version)
→ Turn(s)                  (turn_index, role, content)
→ Judge model/version      (judge_result.judge_model, judge_model_version)
→ Rubric version           (judge_result.rubric_version, taxonomy_version, prompt_config_version)
→ Scores and evidence      (signal_score.score, evidence_turn_indices, explanation)
→ Trajectory state         (trajectory_state.source_judge_result_ids, trajectory_logic_version)
→ Alert-rule version       (alert.alert_rule_id, alert_rule_version)
→ Alert                    (alert_id, severity, explanation, evidence_turn_indices)
→ Human review / adjudication, when present
                           (alert.human_review_status; adjudication.input_annotation_ids, rationale)
```

Link integrity requirements:

1. Every link is a stored foreign key, not a reconstruction from timestamps.
2. Every version field on the chain is non-null, or the record is invalid.
3. `evidence_turn_indices` resolve to turns in the same session and within the assessed window.
4. Nothing on the chain is mutable; corrections append and set `superseded_by`.
5. The chain is traversable in both directions: from an alert to its source turns, and from a turn to every alert that cites it.
6. A reviewer's decision never overwrites a judge score; it is a separate record joined to the alert.

---

## 8. Cross-cutting constraints

1. **Sealed-data isolation.** Any query used for tuning, rubric development, threshold selection, validation-set construction or model selection must filter `sealed = false`. This is enforced in code and tested ([AT-9](IMPLEMENTATION_FOUNDATION.md#6-acceptance-tests)), not left to discipline.
2. **No judge output as labels.** Training or validation-reference queries must exclude `DS-08`.
2a. **No MindEval-derived material as domain reference labels or as evidence of validity.** `DS-04` and `DS-10` are permitted only as generation input and isolated infrastructure-format tests respectively, with provenance and incompatible criteria preserved. **No 0–6 to 0–3 scale conversion may exist.** Enforced by [`tests/`](../../tests/).
3. **Generation parameters are not labels.** `intended_phase_progression`, `intended_harm_type` and simulator hidden state are never joined into scoring or evaluation as truth.
4. **Uncertainty survives storage.** `null` scores, `uncertain` context and `low` confidence are stored as themselves and are never defaulted.
5. **Version completeness.** A derived record missing any version field is rejected at write time.
6. **Redis is never authoritative.** Every Redis key is derivable from PostgreSQL.
