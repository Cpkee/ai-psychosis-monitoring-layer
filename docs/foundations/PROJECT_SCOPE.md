# Project Scope — MVP Boundaries

**Document status:** Proposed foundation, awaiting stakeholder approval
**Version:** 0.1
**Canonical for:** MVP capability boundaries, requirement classification, data-source boundaries
**Supersedes:** nothing. Extends [`README.md`](../../README.md), which remains the authoritative project overview.

---

## 1. Purpose

The AI Psychosis Monitoring Layer is a research prototype that monitors conversations between a user and an AI companion, tracks how defined **monitoring signals** change across turns, and produces **explainable conversational-risk alerts** for human review.

It answers two questions already stated in [`README.md`](../../README.md):

1. Does the user's conversational risk appear to increase or decrease over time?
2. Does the companion respond safely, or does it reinforce beliefs, dependency or harmful actions?

### 1.1 Non-diagnostic boundary (non-negotiable)

This system **does not make clinical diagnoses and does not make autonomous medical decisions.**

- It produces conversational-risk alerts, monitoring signals and evidence. It does not produce diagnoses, clinical stages, or treatment recommendations.
- Every output describes *observable conversation content*, never the user's clinical condition.
- No output may be used as the sole basis for a clinical, safety, or access decision about a real person.
- The simulation "phases" in [`README.md`](../../README.md) are simulation control states, not clinical stages assigned to a person.

This boundary is repeated in every derived document and must survive every future revision.

### 1.2 Simulated population — older adults (65+)

*Amendment, 2026-09-23. Decided by the project lead (D-23); stakeholder approval pending: [OD-023](OPEN_DECISIONS.md#od-023).*

- Every **simulated** user is an older adult, aged **65 or over**. The population is treated as one group: there are **no age bands** for now.
- Personas are written for this population. MindEval-derived personas (DS-04) are not used for them.
- Seeds are kept only if a person confirms the account applies to an older adult, either because the source states an age of 65+ or because the pattern plausibly applies ([`SEED_PIPELINE_PLAN.md` §3.2](SEED_PIPELINE_PLAN.md#32-filter)).
- Age is a property of the **simulation**, not something the system infers about anyone. No output estimates a user's age, and nothing about age may be read as a clinical characteristic.
- Older adults bring confounds the taxonomy does not yet exclude: cognitive impairment, sensory loss, bereavement, and isolation from circumstance rather than choice. Until [OD-025](OPEN_DECISIONS.md#od-025) is resolved, treat any alert that could reflect one of them with particular caution.

Real user conversations remain out of scope at every stage (§7).

---

## 2. Intended users

| User | Needs from the MVP | Primary artefacts |
|---|---|---|
| Client stakeholders | Evidence that their companion model behaves safely under escalating conversations; a defensible non-diagnostic boundary | This document, `FOUNDATION_READINESS.md`, dashboard alert view |
| Researchers | Reproducible metric definitions, versioned rubrics, experiment history | `ANALYTICAL_TAXONOMY.md`, `RUBRIC_VALIDATION.md` |
| Technical developers | Unambiguous data contracts, lifecycle states, provenance fields | `DATA_SOURCES_AND_CONTRACTS.md`, `IMPLEMENTATION_FOUNDATION.md` |
| Human annotators / reviewers | A repeatable procedure for producing reference labels and adjudicating alerts | `ANNOTATION_GUIDE.md` |
| Clinical / safety advisers (consulted, not embedded) | Visibility of unresolved definitional questions before they are frozen | `OPEN_DECISIONS.md` |

---

## 3. Requirement classification

> **Analytical Requirements define what the system must determine from a conversation. Functional Requirements define what the software must do to capture, produce, update, store, and expose those determinations.**

Non-functional requirements are tracked as a third, separate category.

### 3.1 Analytical Requirements (MVP)

| ID | The system must determine | Canonical definition |
|---|---|---|
| AR-1 | The level of each user signal expressed in an assessed exchange: belief conviction, pattern-seeking, AI dependency, social withdrawal, behavioural/harm intent | [`ANALYTICAL_TAXONOMY.md` §3](ANALYTICAL_TAXONOMY.md#3-user-signals) |
| AR-2 | The context category of the user content: personal experience, fiction, hypothetical, attributed/quoted, cultural or ordinary spiritual, uncertain | [`ANALYTICAL_TAXONOMY.md` §5](ANALYTICAL_TAXONOMY.md#5-context-categories) |
| AR-3 | The companion-response behaviour scores: DCS, HES, SIS, SGQ | [`ANALYTICAL_TAXONOMY.md` §4](ANALYTICAL_TAXONOMY.md#4-ai-behaviour-metrics) |
| AR-4 | Whether evidence is sufficient to score, and where it is not | [`ANALYTICAL_TAXONOMY.md` §7](ANALYTICAL_TAXONOMY.md#7-uncertainty-and-insufficient-evidence) |
| AR-5 | How each signal changes across the assessed window: current level, change over time, persistence, escalation, peak, recovery | [`ANALYTICAL_TAXONOMY.md` §6](ANALYTICAL_TAXONOMY.md#6-temporal-concepts) |
| AR-6 | Which specific turns constitute the evidence for each non-empty score | [`RUBRIC_v0.1.md` §7](RUBRIC_v0.1.md#7-evidence-selection-requirements) |
| AR-7 | Whether the combination of signals, trajectory and context meets a defined alert condition, and at what severity | [`ANALYTICAL_TAXONOMY.md` §8](ANALYTICAL_TAXONOMY.md#8-alert-severity-conceptual) |

### 3.2 Functional Requirements (MVP)

| ID | The software must | Notes |
|---|---|---|
| FR-1 | Ingest a conversation with stable `session_id` and ordered `turn_index` identifiers | Contract: `DATA_SOURCES_AND_CONTRACTS.md` §4.1–4.2 |
| FR-2 | Record the data source, scenario, companion condition, and companion model/version for every session | Required for the audit chain |
| FR-3 | Invoke the LLM Judge per assessed exchange using an identified rubric version and produce a structured result | `RUBRIC_v0.1.md` §9 |
| FR-4 | Persist judge results, evidence turn identifiers, judge model/version and rubric version durably in PostgreSQL | Redis must never be the sole record |
| FR-5 | Maintain and update a trajectory state per session and signal from stored per-turn results | Must be reconstructible from stored results |
| FR-6 | Evaluate versioned alert rules against signal scores and trajectory state, and persist the resulting alert with its inputs | `alert_rule_version` mandatory |
| FR-7 | Expose processing status through the lifecycle `PENDING → PROCESSING → COMPLETED`, with `DELAYED` and `FAILED` branches | `DATA_SOURCES_AND_CONTRACTS.md` §6 |
| FR-8 | Provide reviewer access to any alert's supporting conversation turns, scores, trajectory and rubric version | Minimal reviewer view in the tracer bullet |
| FR-9 | Record human review and adjudication outcomes as first-class, inspectable records | Not overwritten onto judge output |
| FR-10 | Maintain audit history: every derived record carries the versions and inputs that produced it | `DATA_SOURCES_AND_CONTRACTS.md` §7 |
| FR-11 | Keep Psychosis-Bench execution on a separate, sealed evaluation path with no feedback into development | Enforced as a test, see `IMPLEMENTATION_FOUNDATION.md` §6 AT-9 |

### 3.3 Non-Functional Requirements (MVP)

| ID | Requirement | Current state |
|---|---|---|
| NFR-1 | **Reproducibility.** Any stored score can be re-derived given the stored conversation, rubric version, judge model/version and configuration. | **Cannot be met as written.** Current models reject `temperature`/`top_p`/`top_k` with a 400, so exact re-derivation is not achievable by configuration. Must be amended to re-runnability, or to measured variation — see [`JUDGE_DECISIONS.md` §2](JUDGE_DECISIONS.md#2-sampling-and-determinism) and [OD-013](OPEN_DECISIONS.md#od-013). |
| NFR-2 | **Traceability.** No derived record exists without a complete provenance path. | Enforced by contracts |
| NFR-3 | **Durability.** Loss of Redis must not lose any alert, score, annotation or conversation. | Tested by AT-8 |
| NFR-4 | **Explainability.** Every alert carries an evidence-grounded explanation in plain language, with no hidden reasoning required. | Enforced by rubric §8 |
| NFR-5 | **Data isolation.** Sealed evaluation data is physically and procedurally separated from development data. | Partially met — see [OD-008](OPEN_DECISIONS.md#od-008) |
| NFR-6 | **Sensitive-content handling.** Conversations describing self-harm and harm to others are stored, displayed and retained under a defined policy. | Unresolved — see [OD-014](OPEN_DECISIONS.md#od-014) |
| NFR-7 | **Versioning.** Prompts, rubrics, models, scenarios and alert rules are versioned and retained; the existing `*_VERSION_DICT` convention in [`prompts/prompts.py`](../../prompts/prompts.py) is the precedent for prompt versioning. | Convention exists, not yet applied to rubrics |
| NFR-8 | **Human-in-the-loop.** No alert produces an automated action affecting a person. | Confirmed boundary |
| NFR-9 | **Performance.** Latency and throughput targets are not set for the MVP. | Deferred — see [OD-015](OPEN_DECISIONS.md#od-015) |

---

## 4. MVP capabilities

In scope for the MVP:

1. **Conversation capture** with session and turn identifiers, including source, scenario and companion condition metadata.
2. **Per-exchange structured scoring by an LLM Judge** — the MVP analytical scorer — producing user-signal scores and AI-behaviour scores (DCS, HES, SIS, SGQ).
3. **Context assessment** classifying user content into the six context categories, with an explicit uncertainty marker.
4. **Temporal trajectory updates** maintaining current level, change, persistence, escalation, peak and recovery per signal per session.
5. **Explainable conversational-risk alerts** produced by versioned alert rules and carrying their inputs and evidence.
6. **Reviewer access to supporting evidence** — the conversation, the cited turns, the scores, the trajectory, the rubric version.
7. **Processing status and audit history** across the defined lifecycle.
8. **Sealed benchmark evaluation mode** running the 16 Psychosis-Bench cases as a final test only.
9. **Adaptive simulation mode** and the three companion conditions described in [`README.md`](../../README.md) (client companion, grounded reference, sycophantic stress test) as the source of development conversations.

---

## 5. Future capabilities (explicitly not MVP)

| Capability | Status |
|---|---|
| **Fine-tuned Transformer** for structured user-risk inference (e.g. DistilRoBERTa / DeBERTa-v3-small per [`README.md`](../../README.md)) | Future component. Not implemented, not part of the tracer bullet, and not a fallback for the LLM Judge. Requires a sufficient corpus of human-adjudicated labels first. |
| Modifying or intervening in the companion's next response | Possible extension, per [`README.md`](../../README.md). Out of MVP. |
| `pgvector` similarity retrieval over conversations | Optional, deferred |
| Real-user deployment | Out of scope at every stage of this prototype |
| Automated escalation to a human service or emergency contact | Out of scope |
| Themes beyond the three literature-supported families | Out of scope — see [OD-011](OPEN_DECISIONS.md#od-011) |

---

## 6. Explicit exclusions

The MVP does **not**:

- Diagnose psychosis or any mental-health condition, or assign clinical stages.
- Replace clinical assessment or professional care.
- Train or fine-tune a generative LLM.
- Deploy the sycophantic stress-test condition with real users, or run it outside offline experiments.
- Treat synthetic data as evidence of real-world clinical performance.
- Treat LLM Judge output as ground truth.
- Use Psychosis-Bench for training, prompt tuning, rubric tuning, threshold setting or model selection.
- Take autonomous action on any alert.

---

## 7. Data-source boundaries

Full register: [`DATA_SOURCES_AND_CONTRACTS.md` §3](DATA_SOURCES_AND_CONTRACTS.md#3-data-source-register).

| Boundary | Rule |
|---|---|
| **Psychosis-Bench** (present in this repository as [`data/test_cases.json`](../../data/test_cases.json), 16 cases) | **Sealed.** Final evaluation only. Excluded from training, prompt tuning, rubric tuning, threshold selection and model selection. Results are reported, never iterated against. |
| **Synthetic scenarios and simulated-user conversations** | The development and validation corpus. Generated from independent scenario specifications, for a simulated older-adult (65+) population (§1.2). |
| **Collected source documents** (DS-14) | Published accounts from PubMed, arXiv, and human-supplied news, legal filings and incident databases, snapshotted with a content hash. **Never forums or social media.** Generation input only: never labels, never evidence of validity, never final evaluation. |
| **Seeds** (DS-15) | Scenario parameters extracted from DS-14. Their theme, phase and harm type are generation parameters, **not labels**. Same permissions as DS-14. |
| **Grounded reference and sycophantic stress-test conditions** | Experimental controls producing lower-risk and higher-risk reference trajectories. Offline only. |
| **LLM Judge results** | Derived assessments. Never automatic ground truth. |
| **Human-adjudicated labels** | The evaluation reference labels. |
| **MindEval-derived assets in `data/`** (`human_annotations.jsonl`, `human_user_turns.jsonl`, `profiles.jsonl`) and [`prompts/prompts.py`](../../prompts/prompts.py) | Imported reference material for a different rubric (MindEval clinician criteria). **Not** reference labels for this project's taxonomy — see [OD-007](OPEN_DECISIONS.md#od-007). |
| **Real user conversations** | Not used at any stage of this prototype. |

---

## 8. Definition of a successful MVP foundation

The foundation is successful when all of the following hold:

1. Every analytical output named in §3.1 has exactly one canonical definition with inclusion criteria, exclusion criteria and worked examples.
2. Every data object has a named producer, consumer, contract and retention expectation.
3. Every score and alert can be traced from the stored alert back to the source conversation, the supporting turns, the judge model/version, the rubric version and the alert-rule version.
4. LLM Judge output and human-adjudicated labels are structurally distinguishable in storage.
5. Psychosis-Bench is isolated by both process and code path from anything that tunes the system.
6. Uncertainty is representable in every analytical output rather than being collapsed into a definite score.
7. Every unresolved definition appears in [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) with an owner and a required-by milestone.
8. A reader can distinguish approved decisions from proposals awaiting approval in [`FOUNDATION_READINESS.md`](FOUNDATION_READINESS.md).

The foundation being successful does **not** mean the system is implementation-ready for evaluation reporting; that additionally requires the human approvals listed in [`RUBRIC_VALIDATION.md` §5](RUBRIC_VALIDATION.md#5-approval-gate).
