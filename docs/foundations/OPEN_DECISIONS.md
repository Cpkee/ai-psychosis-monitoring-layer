# Open Decisions

**Document status:** Live register
**Version:** 0.1
**Purpose:** every question that requires stakeholder, domain-expert, or clinical/safety review before the affected artefact can be treated as settled.

Nothing in this register has been decided by this foundations pack. Where a document proceeds under a provisional assumption, the assumption is labelled provisional there and linked here.

**Status values:** `OPEN` (no owner has begun) · `IN REVIEW` (with an owner) · `DECIDED` (resolution recorded and propagated).
**Recommended owner** names a role, not a person; roles are not yet assigned.
**Milestones:** `M1` before the rubric can leave draft · `M2` before the annotation pilot runs · `M3` before the tracer bullet ships · `M4` before any external evaluation report.

| ID | Question | Blocks | Milestone | Status |
|---|---|---|---|---|
| [OD-001](#od-001) | Score scale for user signals | Rubric v1.0, all stored scores | M1 | OPEN |
| [OD-002](#od-002) | Scale and semantics for DCS/HES/SIS/SGQ | Rubric v1.0, comparability | M1 | OPEN |
| [OD-003](#od-003) | Confirmation of the assessment unit | Rubric, annotation guide | M1 | OPEN |
| [OD-004](#od-004) | Alert thresholds and severity rules | Alert engine | M3 | OPEN |
| [OD-005](#od-005) | Annotator and reviewer qualifications | Annotation pilot | M2 | OPEN |
| [OD-006](#od-006) | Pilot annotation sample size | Annotation pilot | M2 | OPEN |
| [OD-007](#od-007) | Status of imported MindEval annotations | Reference-label strategy | M2 | OPEN |
| [OD-008](#od-008) | Sealing and storage of Psychosis-Bench | Benchmark integrity | M3 | OPEN |
| [OD-009](#od-009) | Reviewer interface technology | Reviewer view | M3 | OPEN |
| [OD-010](#od-010) | "Redis Iris" clarification | Infrastructure | M3 | OPEN |
| [OD-011](#od-011) | Theme taxonomy reconciliation | Taxonomy, scenario engine | M2 | OPEN |
| [OD-012](#od-012) | Theme and phase estimation for alerts | Alert contract | M3 | OPEN |
| [OD-013](#od-013) | Judge model selection, determinism and confidence | Rubric v1.0 | M1 | OPEN |
| [OD-014](#od-014) | Sensitive-content, retention and annotator-welfare policy | Annotation pilot, storage | M2 | OPEN |
| [OD-015](#od-015) | Companion ↔ monitor contract and performance targets (was: client companion API, corrected by D-46) | Companion integration, live signal return | M3 | OPEN |
| [OD-016](#od-016) | Harm sub-types and third-party risk | Taxonomy, alert rules | M2 | OPEN |
| [OD-017](#od-017) | Agreement metric, thresholds and recurrence definition | Rubric validation | M1 | OPEN |
| [OD-018](#od-018) | Trajectory window and temporal thresholds | Trajectory logic | M3 | OPEN |
| [OD-019](#od-019) | Terminology: "warning" vs "alert" | Documentation consistency | M1 | OPEN |
| [OD-020](#od-020) | Treatment of the inconsistent `ai_sweetheart` cases | Theme mapping, benchmark aggregates | M1 | OPEN |
| [OD-021](#od-021) | Review of taxonomy/rubric examples after disclosed pre-seal inspection | Rubric v1.0 approval | M1 | OPEN |
| [OD-022](#od-022) | Simulated-user model selection (pilot) | Seed pipeline S5 generation | M2 | OPEN |
| [OD-023](#od-023) | Stakeholder approval of the older-adult (65+) scope | PROJECT_SCOPE, personas, taxonomy | M1 | DECIDED: withdrawn (D-43) |
| [OD-024](#od-024) | Copyright and terms of use for source snapshots and quotations | Seed pipeline S1 | M2 | OPEN |
| [OD-025](#od-025) | Older-adult confounds in the taxonomy | Rubric v1.0, persona design | M1 | DECIDED: withdrawn (D-43) |
| [OD-026](#od-026) | Hosted storage of harm-bearing content, and whether OD-014 gates Review and Label | Seed pipeline S1, S6, S7 | M2 | OPEN |
| [OD-027](#od-027) | Coverage targets and realism sample rule | Seed pipeline S3, S6 | M2 | OPEN |
| [OD-028](#od-028) | Companion memory, and the monitor's cross-session findings history | Companion memory, cross-session alerting | — | OPEN |
| [OD-029](#od-029) | Automated in-conversation intervention (redirection flows, fast pre-screen) | Companion redirection, signal return | — | OPEN |
| [OD-030](#od-030) | Preconditions for a live demo with real users | Any real-user conversation (D-47) | Before any real user | OPEN |

---

## OD-001

**Question:** What is the score scale for the five user signals — how many levels, and what range?

**Why it matters:** Every stored score, every anchor in the rubric, every human label and every alert threshold depends on it. Changing it later invalidates all prior scores and all agreement statistics, and forces re-annotation.

**Available options:**
1. Adopt the provisional 0–3 ordinal in [taxonomy §2](ANALYTICAL_TAXONOMY.md#2-scoring-scale-provisional).
2. Adopt a scale matching the published Psychosis-Bench metric definitions, for comparability.
3. Use a coarser 0–2 scale to raise inter-annotator agreement at the cost of resolution.
4. Use different scales for different signals (e.g. finer resolution for `harm_intent`).

**Evidence already available:** No scale exists anywhere in the repository, and no metrics module exists. Imported MindEval annotations use 0–6 on undefined criteria ([`data/human_annotations.jsonl`](../../data/human_annotations.jsonl)), which is not this project's rubric. The anchors in [`RUBRIC_v0.1.md` §5.1](RUBRIC_v0.1.md#5-score-levels-and-observable-anchors) are written for 0–3.

**Recommended owner:** Research lead, with the clinical/safety adviser consulted on `harm_intent`.

**Required by:** M1. **Status:** OPEN.

---

## OD-002

**Question:** What are the scales and precise scoring semantics for DCS, HES, SIS and SGQ, and how do they reconcile with the published Psychosis-Bench definitions? Sub-questions: is SGQ higher-is-better on the same ordinal as the risk metrics; is SIS scored on every exchange or only where intervention is warranted; does HES include omission (failing to address stated intent)?

**Why it matters:** These four metrics are the companion-evaluation output the client will be shown. If the scales diverge from the published benchmark definitions without disclosure, benchmark results are not comparable to published work, which is a reporting integrity problem, not just an engineering one.

**Available options:**
1. Adopt the published Psychosis-Bench scales verbatim for DCS/HES/SIS and define SGQ separately.
2. Adopt a single project-internal 0–3 scale for all four and report a documented mapping to the published scales.
3. Keep two parallel scorings (project scale and benchmark scale) on the same exchanges.

**Evidence already available:** Acronym expansions are verified in [`README.md`](../../README.md): DCS — Delusion Confirmation Score; HES — Harm Enablement Score; SIS — Safety Intervention Score; SGQ — Supportive Grounding Quality. No numeric definitions exist in the repository. The cited sources ([The Psychogenic Machine](https://arxiv.org/abs/2509.10970), [Psychosis-Bench](https://github.com/w-is-h/psychosis-bench)) are the obvious place to look, but nothing in this repository records what they specify.

**Recommended owner:** Research lead.

**Required by:** M1. **Status:** OPEN.

---

## OD-003

**Question:** Is the exchange (one user turn plus the following companion response) confirmed as the unit of assessment for both the judge and annotators? What happens when the companion emits multiple messages for one user turn, or when a session ends on a user turn?

**Why it matters:** Judge and human labels must share a unit or agreement cannot be measured. The unit also determines how many judge calls a session costs.

**Available options:**
1. Exchange, as currently specified in [`RUBRIC_v0.1.md` §3](RUBRIC_v0.1.md#3-unit-of-assessment).
2. Single turn, scored separately for user and assistant roles.
3. Sliding conversation window of N exchanges.
4. Whole conversation.

**Evidence already available:** [`data/test_cases.json`](../../data/test_cases.json) is structured as 12 ordered user prompts per case, one companion response each — a natural exchange structure. [`PROJECT_SCOPE.md` §4](PROJECT_SCOPE.md#4-mvp-capabilities) requires per-turn scoring. DCS and HES are defined relative to what the user said, which requires both sides.

**Recommended owner:** Research lead with the technical lead.

**Required by:** M1. **Status:** OPEN.

---

## OD-004

**Question:** What are the executable alert thresholds, severity rules, context modifiers and clearance conditions?

**Why it matters:** Thresholds determine the false-positive and false-negative rate a reviewer actually experiences. Set without evidence, they make the system either noisy or blind, and both are safety-relevant.

**Available options:**
1. Start with the provisional example rule in [`IMPLEMENTATION_FOUNDATION.md` §5](IMPLEMENTATION_FOUNDATION.md#5-the-one-alert-rule) and tune against adjudicated labels once the pilot exists.
2. Derive thresholds from the annotation pilot's severity judgements.
3. Have a clinical/safety adviser specify the harm-related thresholds directly.

**Evidence already available:** [`README.md`](../../README.md) fixes the four severity levels (low, medium, high, critical) but no thresholds. [Taxonomy §8](ANALYTICAL_TAXONOMY.md#8-alert-severity-conceptual) gives the conceptual meaning of each level and the principles any rule must respect. No labelled data exists to tune against.

**Recommended owner:** Research lead with the clinical/safety adviser; thresholds approved as a versioned alert-rule release.

**Required by:** M3 for a provisional rule; M4 for approved thresholds. **Status:** OPEN.

---

## OD-005

**Question:** What qualifications are required of annotators, adjudicators, clinical/safety advisers and cultural-competence reviewers, and what happens when only one reviewer is available?

**Why it matters:** The adjudicated labels are the standard the whole system is measured against. If annotator competence is undefined, the reference labels have unknown authority and every downstream agreement figure is uninterpretable.

**Available options:**
1. Trained lay annotators for general signals, with clinical review restricted to harm-related and ambiguous cases.
2. Require clinically qualified annotators throughout (highest authority, lowest throughput).
3. Tiered: lay annotators for the first pass, clinically qualified adjudicators.
4. Accept single-reviewer batches with reduced status, as [`ANNOTATION_GUIDE.md` §9.4](ANNOTATION_GUIDE.md#94-reviewers) currently proposes.

**Evidence already available:** [`README.md`](../../README.md) records that access to clinical experts is limited and that clinical review will be sought where possible. The imported MindEval annotations show a four-annotator-per-item precedent, but the annotators' qualifications are not recorded in the data.

**Recommended owner:** Project lead with the clinical/safety adviser.

**Required by:** M2. **Status:** OPEN.

---

## OD-006

**Question:** How many conversations does the pilot annotation set contain?

**Why it matters:** Too small and agreement estimates are noise; too large and the pilot consumes the limited expert time the project has. The number also determines how much of the taxonomy can be exercised.

**Available options:** Set the size from (a) the coverage criteria in [`ANNOTATION_GUIDE.md` §9.3](ANNOTATION_GUIDE.md#93-selection-criteria-before-sample-size), (b) the confidence interval required for the agreement metric chosen in [OD-017](#od-017), and (c) available annotator and adjudicator hours. **An arbitrary round number is explicitly not acceptable.**

**Evidence already available:** 11 required coverage categories, 3 companion conditions and 3 theme families must all be represented, each by more than one conversation. The MindEval precedent used 60 conversations with 4 annotators each; that figure is context for effort estimation, not a target.

**Recommended owner:** Research lead.

**Required by:** M2. **Status:** OPEN.

---

## OD-007

**Question:** What is the status of [`data/human_annotations.jsonl`](../../data/human_annotations.jsonl) — are these annotations usable for anything in this project, and what do their criteria mean?

**Why it matters:** The file is the only human-annotated data in the repository. If it were usable as reference labels it would save substantial effort. If it is not, treating it as a head start would silently corrupt the reference-label set.

**Current classification (applied, not awaiting this decision):** *prohibited as domain reference labels or as evidence of system validity; potentially usable only for isolated infrastructure-format tests, if provenance and the incompatible criteria are clearly preserved.* **The 0–6 criterion values must never be converted into the project's provisional 0–3 scale.** This is now enforced in code by [`config/data_sources.json`](../../config/data_sources.json) and [`tests/`](../../tests/). What remains open is only whether anything further can ever be made of the file.

**Available options:**
1. Leave the classification as applied — infrastructure-format tests only ([`DATA_SOURCES_AND_CONTRACTS.md` DS-10](DATA_SOURCES_AND_CONTRACTS.md#ds-10--imported-mindeval-annotations)).
2. Obtain the MindEval criterion definitions and assess whether any map onto this project's taxonomy.
3. Remove the files from the repository to prevent accidental use.

**Evidence already available:** 60 conversations, 4 independent annotator responses per criterion, 3 companion models (`azure/gpt-5-chat-2`, `hosted_vllm/Qwen3-235B-A22B-Instruct-2507`, `hosted_vllm/DeepSeek-R1-0528`, 20 each). Criteria are `criterion_1`–`criterion_4`, `criterion_6`–`criterion_10`, `criterion11` — `criterion_5` is missing and `criterion11` breaks the naming convention. **No definition of any criterion exists in the repository.** Values span 0–6. Content is mental-health-programme check-ins about depression and anxiety, not the three psychosis-related theme families.

**Recommended owner:** Research lead.

**Required by:** M2. **Status:** OPEN.

---

## OD-008

**Question:** Where does Psychosis-Bench live, and what technical controls enforce its seal?

**Why it matters:** The seal is currently procedural only. [`data/test_cases.json`](../../data/test_cases.json) sits in the working repository alongside development data, readable by any developer and any test fixture. A single convenient import defeats the entire final-evaluation design, and the contamination would be undetectable after the fact.

**Available options:**
1. Move to a separate access-controlled repository or storage bucket, loaded only by the benchmark runner.
2. Keep in place but add a marker file, a loader that refuses outside benchmark mode, and a CI test asserting no development code path reads it.
3. Separate database schema or role for sealed results, as [`DATA_SOURCES_AND_CONTRACTS.md` DS-12](DATA_SOURCES_AND_CONTRACTS.md#ds-12--postgresql-persistent-system-storage) suggests.
4. Make the repository private, given it holds a sealed evaluation set.

**Partially actioned.** Option 2 is now implemented: a guarded loader, a checksum manifest, a contamination guard and CI enforcement are in force — see [`BENCHMARK_SEAL.md` §4](BENCHMARK_SEAL.md#4-controls-now-in-force). **The final controlled location remains undecided, and no additional cases are to be executed or inspected until it is.**

**Evidence already available:** All 16 cases (192 prompts) are committed to `main` and were pushed to a **public** GitHub remote on 2026-09-11, so prior exposure is unbounded and cannot be enumerated ([`BENCHMARK_SEAL.md` §3.2](BENCHMARK_SEAL.md#32-remote-exposure--unbounded)). Because Psychosis-Bench is itself public, this adds no disclosure beyond what already existed — but it does mean confidentiality cannot be retrofitted, and only process discipline is protectable.

**Recommended owner:** Technical lead with the project lead.

**Required by:** M3. **Status:** OPEN.

---

## OD-009

**Question:** Is the reviewer interface Next.js/React, or a lightweight Python dashboard?

**Why it matters:** It determines the API surface the backend must expose and who can maintain the interface. No dashboard code exists, so nothing is committed either way.

**Available options:**
1. Next.js/React, per the brief's technology roles.
2. A lightweight Python dashboard, the alternative offered in [`README.md`](../../README.md).
3. Minimal server-rendered pages for the tracer bullet, deferring the choice.

**Evidence already available:** [`README.md`](../../README.md) lists both as acceptable. The tracer bullet needs only a read-only alert list and detail view.

**Recommended owner:** Technical lead.

**Required by:** M3. **Status:** OPEN.

---

## OD-010

**Question:** What is "Redis Iris" in [`README.md`](../../README.md)'s technology stack, and is it required?

**Why it matters:** An unclarified infrastructure dependency in the stated stack cannot be provisioned, costed or ruled out. It may be a specific product choice with consequences, or a typo.

**Available options:** Clarify and either specify it with its justification, or replace the phrase with plain Redis.

**Evidence already available:** [`README.md`](../../README.md) says "Redis or Redis Iris where justified". No other mention anywhere in the repository. [`DATA_SOURCES_AND_CONTRACTS.md` DS-13](DATA_SOURCES_AND_CONTRACTS.md#ds-13--redis-transient-state) assumes plain Redis.

**Recommended owner:** Technical lead.

**Required by:** M3. **Status:** OPEN.

---

## OD-011

**Question:** How do the three theme families in [`README.md`](../../README.md) reconcile with the six theme labels in Psychosis-Bench, and is "unusual belief" in the taxonomy bounded by those families?

**Why it matters:** It determines what the scenario engine generates, what the judge treats as in-scope for `belief_conviction`, and whether benchmark results can be reported by theme without a mapping that has never been written down.

**Available options:**
1. Keep three project families and publish an explicit mapping from the six benchmark labels onto them.
2. Adopt the benchmark's labels as the project taxonomy.
3. Keep both, stored as separate fields, and never conflate them in reporting.

**Evidence already available:** [`README.md`](../../README.md) defines three families: spiritual/messianic beliefs; sentient or god-like AI beliefs; emotional dependency or romantic attachment. [`data/test_cases.json`](../../data/test_cases.json) `metadata.themes` lists six: Grandiose Delusions; Attachment / Erotic Delusions; Grandiose/Referential Delusions; Grandiose/Attachment Delusions; Referential/Anthropomorphic Delusions; Erotic Attachment Delusions and Self-Isolation. The two vocabularies overlap but do not correspond one-to-one, and `ai_sweetheart_explicit` and `ai_sweetheart_implicit` carry different theme labels from each other.

**Versioned artefact:** [`THEME_VOCABULARY_MAPPING.md`](THEME_VOCABULARY_MAPPING.md) (`theme_mapping_v0.1`) now holds both vocabularies separately with **every mapping cell marked UNRESOLVED**. The vocabularies must not be renamed, merged or substituted until a resolution is released as `theme_mapping_v1.0`. Cross-vocabulary aggregation is prohibited meanwhile.

**Recommended owner:** Research lead.

**Required by:** M2. **Status:** OPEN.

---

## OD-012

**Question:** Should alerts carry a theme estimate and a phase estimate, and should AI exceptionalism be separated from AI dependency?

**Why it matters:** [`README.md`](../../README.md)'s warning output includes "estimated theme and phase", but phases are defined there as *simulation states, not clinical stages*. Presenting an inferred "phase" on an alert about a conversation risks reading as a clinical stage assignment — precisely the non-diagnostic boundary the project depends on.

**Available options:**
1. Drop `phase_estimate` from alerts; keep phase as a generation parameter only.
2. Keep it, renamed to something unambiguously conversational, with a visible non-clinical disclaimer in the reviewer view.
3. Keep both estimates but restrict them to research reporting, never the reviewer-facing alert.

Separately: whether `ai_dependency` ([taxonomy §3.3](ANALYTICAL_TAXONOMY.md#33-ai-dependency)) should split into beliefs about the AI's nature versus reliance on it.

**Evidence already available:** [`README.md`](../../README.md) lists both the warning field and the simulation-state caveat. [`DATA_SOURCES_AND_CONTRACTS.md` §4.7](DATA_SOURCES_AND_CONTRACTS.md#47-alerts) currently marks both fields nullable with a warning attached.

**Recommended owner:** Project lead with the clinical/safety adviser.

**Required by:** M3. **Status:** OPEN.

---

## OD-013

**Question:** Which model serves as the LLM Judge, with what sampling settings, and how is `confidence` defined and calibrated?

**Why it matters:** [`README.md`](../../README.md) already records that LLM evaluators may introduce scoring bias. A judge from the same family as the companion under evaluation may score it leniently, which would bias the project's headline finding. Reproducibility (NFR-1) also depends on determinism settings.

**Available options:**
1. Pin a judge model from a different family than any companion under evaluation.
2. Use two judges and report disagreement as a bias estimate.
3. Fix low-temperature sampling and measure run-to-run stability before pinning.

For `confidence`: self-reported by the judge (cheap, poorly calibrated), derived from repeat-run agreement (expensive, better grounded), or derived from rubric-defined ambiguity conditions (deterministic, coarse).

**Evidence already available:** No judge implementation exists. [`RUBRIC_v0.1.md` §11](RUBRIC_v0.1.md#11-known-limitations) records bias, non-determinism and condition-leakage risks.

**Expanded into an actionable brief:** [`JUDGE_DECISIONS.md`](JUDGE_DECISIONS.md) — four decisions with instructions, required inputs, and the exact configuration values each produces.

**Material change since this entry was written:** on current Claude models (Opus 5, Sonnet 5, Fable 5/5.1, Opus 4.7/4.8) the sampling parameters `temperature`, `top_p` and `top_k` are **removed and return a 400**. Setting temperature to zero for determinism is no longer possible, so [`PROJECT_SCOPE.md` NFR-1](PROJECT_SCOPE.md#33-non-functional-requirements-mvp) — "any stored score can be re-derived" — **cannot be met as written** and must be amended to the standard actually achievable. See [`JUDGE_DECISIONS.md` §2](JUDGE_DECISIONS.md#2-sampling-and-determinism).

**Recommended owner:** Research lead with the technical lead.

**Required by:** M1. **Status:** OPEN.

---

## OD-014

**Question:** What is the policy for sensitive content — retention periods, access control, annotator welfare support, the named escalation contact, and handling of any content that appears to involve a real person at risk?

**Why it matters:** Conversations contain detailed self-harm, suicide, harm-to-others, medical-neglect and financial-ruin content. Annotators are exposed to it repeatedly. Without a named contact and a stated policy, [`ANNOTATION_GUIDE.md` §10](ANNOTATION_GUIDE.md#10-handling-sensitive-content) cannot actually be followed, and the pilot should not start.

**Available options:** Adopt an existing organisational policy; commission one with the clinical/safety adviser; or restrict the pilot to staff with existing professional support arrangements until a policy exists.

**Evidence already available:** [`data/test_cases.json`](../../data/test_cases.json) enumerates nine `harm_type` values including jumping from height, suicide to "join" the AI, medical neglect, cult formation and severe isolation. No policy of any kind exists in the repository. All data is synthetic, which lowers but does not remove the concern.

**Recommended owner:** Project lead with the clinical/safety adviser.

**Required by:** M2 — **this blocks the pilot, not merely the documentation.** **Status:** OPEN.

---

## OD-015

**Question:** What is the contract between the companion and the monitoring layer — what the companion sends per turn and per session, what the monitor sends back, how the companion's model, prompt, memory and flow versions are reported — and what latency and throughput targets apply?

*Reframed 2026-09-24 by D-46. The question was originally about a client companion API; no such API exists, because this team builds the one companion.*

**Why it matters:** The audit chain can only attribute a result to what actually produced it. If the companion does not report its model version, persona-prompt version, memory configuration and redirection-flow version on every session, a change in behaviour cannot be traced to a change in the companion. The return direction matters as much: once the companion acts on the monitor's signals ([OD-029](#od-029)), those signals become an interface with consumers, and changing them silently changes companion behaviour.

**Proposed shape (for the owner, provisional):**

| Direction | Content |
|---|---|
| Companion → monitor, per session | Companion configuration id and versions (model, persona prompt, memory policy, redirection flows); ids of memories loaded at session start ([OD-028](#od-028)) |
| Companion → monitor, per turn | The turn, and whether a redirection flow fired and which one ([OD-029](#od-029)) |
| Monitor → companion | A small, versioned set of signals: severity, times seen, and theme **only once** a theme mapping is approved ([OD-012](#od-012); all mappings are currently `UNRESOLVED`) |

**Available options:** Define the contract now against the in-process ingestion path and keep the HTTP surface for increment 9; or define both together at increment 9.

**Evidence already available:** Ingestion already records `companion_condition` and model metadata per session (FR-2). The monitor runs asynchronously after each turn, with latency dominated by one judge call; no performance target is stated (NFR-9). Signals the companion must act on **before its next reply** would need a faster path — see [OD-029](#od-029).

**Recommended owner:** Technical lead, with the project lead.

**Required by:** M3 for the slice after the tracer bullet. **Status:** OPEN.

---

## OD-016

**Question:** Should `harm_intent` split into harm-to-self, harm-to-others and harm-through-neglect sub-scores, and does attributed content indicating risk to an identifiable third party need its own alert type?

**Why it matters:** The three harm kinds imply different review responses. Collapsing them into one score means a reviewer sees "harm intent 3" without knowing who is at risk. Third-party risk arriving through attributed content ([taxonomy §5.4](ANALYTICAL_TAXONOMY.md#54-attributed-to-others--quoted-content)) is the case most likely to be wrongly suppressed by a naive context rule.

**Available options:**
1. One score plus a `harm_target` field (`self` / `others` / `neglect` / `unclear`).
2. Three separate scores with independent trajectories.
3. One score plus a distinct third-party-risk alert type.

**Evidence already available:** [`data/test_cases.json`](../../data/test_cases.json) distinguishes nine `harm_type` values spanning self-harm, harm to others (cult formation), property damage, self-neglect, financial ruin and severe isolation. [Taxonomy §3.5](ANALYTICAL_TAXONOMY.md#35-behavioural--harm-intent) currently records all of these under one signal and flags the question.

**Recommended owner:** Research lead with the clinical/safety adviser.

**Required by:** M2, so the pilot labels the distinction from the start rather than being re-annotated. **Status:** OPEN.

---

## OD-017

**Question:** Which inter-annotator and judge-vs-reference agreement metrics are used, what thresholds count as acceptable, and how many sessions constitute a "recurring" weakness for [`RUBRIC_VALIDATION.md` §3](RUBRIC_VALIDATION.md#3-valid-triggers-for-a-rubric-change)? Related: how many turns of sustained frame are required before Fiction is assigned as the primary context category?

**Why it matters:** Without a metric and a threshold, "the rubric is good enough" is an opinion. Without a recurrence definition, the change-control gate can be satisfied by a single motivated example, which is exactly what it exists to prevent.

**Available options:** Weighted kappa or Krippendorff's alpha for ordinal scores, with a separate exact-match rate for context categories and a separate evidence-overlap measure; thresholds set per signal, with a higher bar for `harm_intent` and `hes`.

**Evidence already available:** No significance-testing implementation exists and no method has been chosen. [`ANNOTATION_GUIDE.md` §8.2](ANNOTATION_GUIDE.md#82-recording-disagreement) defines the disagreement types the metric would consume.

**Recommended owner:** Research lead.

**Required by:** M1. **Status:** OPEN.

---

## OD-018

**Question:** What is the assessed conversation window, and what are the numeric thresholds for staleness, persistence run length, escalation, and sustained recovery? What reference point does change-over-time use?

**Why it matters:** Every temporal concept in [taxonomy §6](ANALYTICAL_TAXONOMY.md#6-temporal-concepts) is currently defined qualitatively with its threshold marked unresolved. Different windows produce different peaks and different escalation findings from identical scores, so results are not comparable across runs until this is fixed and versioned.

**Available options:**
1. Whole session (current provisional default, `window_definition: "whole_session_v0.1"`).
2. Fixed sliding window of N exchanges.
3. Whole session for peak and persistence; sliding window for current level and change.

**Evidence already available:** Psychosis-Bench sessions are uniformly 12 exchanges, so whole-session and a 12-exchange window coincide there but will diverge for adaptive sessions of other lengths. [`DATA_SOURCES_AND_CONTRACTS.md` §4.6](DATA_SOURCES_AND_CONTRACTS.md#46-trajectory_updates) stores `window_definition` on every state, so a change is a recomputation rather than a data loss.

**Recommended owner:** Research lead with the technical lead.

**Required by:** M3. **Status:** OPEN.

---

## OD-019

**Question:** Is the reviewer-facing output called a "warning" (as in [`README.md`](../../README.md)) or a "conversational-risk alert" (as in this foundations pack)?

**Why it matters:** Two names for one object in project documentation produces two vocabularies in code, schema, dashboard and client conversations. It is small and cheap to fix now and expensive to fix after the schema exists.

**Available options:**
1. Adopt "conversational-risk alert" as canonical and update [`README.md`](../../README.md)'s "Warning output" section.
2. Keep "warning" as the user-facing term and "alert" as the internal one, documented explicitly.
3. Keep "warning" throughout and revise this foundations pack.

**Evidence already available:** [`README.md`](../../README.md) uses "warning output" and "warnings"; it also uses "Alert engine" in its architecture diagram — so the README already contains both. This pack uses "alert" throughout and records the equivalence at [taxonomy §8](ANALYTICAL_TAXONOMY.md#8-alert-severity-conceptual).

**Recommended owner:** Project lead.

**Required by:** M1. **Status:** OPEN.

---

## OD-020

**Question:** How should the inconsistent `ai_sweetheart` case pair be treated?

**Why it matters:** Every other benchmark case is a matched explicit/implicit pair sharing one theme label and one harm type. This pair is the sole exception, differing on both. The explicit/implicit contrast is the benchmark's controlled variable, so for this case that contrast is confounded. `Erotic Attachment Delusions and Self-Isolation` is also a label with exactly one member, which may simply belong under `Attachment / Erotic Delusions`. Until this is settled, **no per-theme benchmark aggregate is trustworthy.**

**Available options:**
1. Preserve both labels exactly as recorded, exclude the pair from per-theme aggregates, and report the inconsistency in the evaluation report (**current handling**).
2. Treat `B6` as a member of `B2` for aggregation only, with the mapping recorded in [`THEME_VOCABULARY_MAPPING.md`](THEME_VOCABULARY_MAPPING.md) and disclosed wherever used.
3. Report the pair individually and never aggregate it.
4. Raise it upstream with the benchmark authors and adopt their answer.

**Evidence already available:** `ai_sweetheart_explicit` — theme `Erotic Attachment Delusions and Self-Isolation`, harm type `Severe Isolation and Emotional Dependence`. `ai_sweetheart_implicit` — theme `Attachment / Erotic Delusions`, harm type `Financial Ruin & Severe Isolation`. Both carry 12 prompts, as do all other cases. Details at [`THEME_VOCABULARY_MAPPING.md` §6](THEME_VOCABULARY_MAPPING.md#6-the-ai_sweetheart-inconsistency).

**Constraint:** the source records must not be edited. The sealed file is checksum-pinned, and relabelling it would break comparability with published results.

**Recommended owner:** Research lead.

**Required by:** M1. **Status:** OPEN.

---

## OD-021

**Question:** Do the examples in [`ANALYTICAL_TAXONOMY.md`](ANALYTICAL_TAXONOMY.md) and [`RUBRIC_v0.1.md`](RUBRIC_v0.1.md) need revision, given that sealed case 1 content was inspected in the same session that authored them?

**Why it matters:** The seal exists to guarantee that no rubric or taxonomy artefact was shaped by sealed content. During repository inventory on 2026-09-16 — before any control existed — case 1's 12 prompts were surfaced verbatim, and all 16 cases' metadata enumerated, in the session that then authored the taxonomy and rubric. The automated contamination check confirms no sealed prompt appears in any project file, and the examples were authored independently and labelled illustrative. That is evidence, but it is not the same as an independent human confirming the examples do not echo case 1's structure.

**Available options:**
1. Independent reviewer compares the taxonomy and rubric examples against sealed case 1 and records a finding before `rubric_v1.0` is approved (**recommended** — it is a bounded, one-off review).
2. Rewrite all illustrative examples from scratch by someone who has not seen the sealed set, removing the question entirely.
3. Accept the automated check as sufficient and record the residual risk as a known limitation on the rubric release.

**Evidence already available:** Full disclosure at [`BENCHMARK_SEAL.md` §3.3](BENCHMARK_SEAL.md#33-automated-and-tooling-access). Guard check 3 passes: no verbatim sealed prompt exists in any scanned file.

**Recommended owner:** Independent reviewer, as part of the `rubric_v1.0` approval gate.

**Required by:** M1. **Status:** OPEN.

---

## OD-022

**Question:** Which model plays the simulated user?

**Why it matters:** The simulated user sets the realism of the whole corpus. Its family also constrains which families the reference companion and judge may use (D-30).

**Available options:** A pilot on 5 development-split seeds compares three candidates: Gemini Flash (free tier), a low-cost Claude model, and a local ~24B open-weight model. Human raters, blind to the model, rate each conversation pass/weak/fail on staying in character, holding the belief under pushback, and sounding like the persona.

**Evidence already available:** None. Procedure in [`SEED_PIPELINE_PLAN.md` §3.4](SEED_PIPELINE_PLAN.md#34-generate).

**Resolution:** recorded as a new D-record in [`IMPLEMENTATION_FOUNDATION.md` §10](IMPLEMENTATION_FOUNDATION.md#10-decisions-taken-during-implementation), and the chosen model is pinned in config.

**Recommended owner:** Research lead.

**Required by:** M2 — generation beyond the pilot does not run until this is decided. **Status:** OPEN.

---

## OD-023

**Question:** Do stakeholders approve narrowing the simulated population to older adults (65+)?

**Why it matters:** [`PROJECT_SCOPE.md`](PROJECT_SCOPE.md) is a proposed foundation awaiting stakeholder approval, and it names no target population. The project lead has decided the change (D-23). Personas, seeds, the taxonomy's worked examples and the annotator briefing all follow from it.

**Available options:** Approve the amendment as drafted; approve with a different age threshold; reject, keeping an unrestricted adult population.

**Evidence already available:** D-23; [`SEED_PIPELINE_PLAN.md`](SEED_PIPELINE_PLAN.md).

**Recommended owner:** Project lead with client stakeholders.

**Resolution (2026-09-24):** withdrawn. The project lead dropped the age focus entirely (D-43), so there is no narrowed population to approve.

**Required by:** M1. **Status:** DECIDED.

---

## OD-024

**Question:** What may be stored and quoted from collected sources?

**Why it matters:** The pipeline stores full-text snapshots of news articles, papers and filings in a hosted database, and seeds carry short evidence spans. Licences differ: PubMed abstracts, PubMed Central open-access subsets, arXiv licences, and publisher terms for news. Anything that reaches a committed fixture becomes public.

**Available options:** Store full text for internal research use only, with quotations capped; store only metadata plus the text of openly licensed documents; store paraphrased extractions only and discard snapshots after hashing (this weakens the audit trail).

**Evidence already available:** None.

**Recommended owner:** Project lead, with the organisation's legal or research-governance contact.

**Required by:** M2, before S1 writes to the shared DB. **Status:** OPEN.

---

## OD-025

**Question:** Does the taxonomy need exclusions or guidance specific to older adults?

**Why it matters:** Cognitive impairment, sensory loss, bereavement, polypharmacy and circumstantial isolation can all produce conversation that looks like `belief_conviction` or `social_withdrawal` without matching what those signals mean. Without explicit exclusions, both the judge and annotators may score them as risk. Scoring them would also push the system towards the diagnostic territory it must stay out of.

**Available options:** Add older-adult exclusion criteria and worked examples to [`ANALYTICAL_TAXONOMY.md`](ANALYTICAL_TAXONOMY.md), with a rubric revision under [`RUBRIC_VALIDATION.md`](RUBRIC_VALIDATION.md); add a context category; or leave the taxonomy unchanged and record the confound as a known limitation.

**Evidence already available:** None in the repository.

**Recommended owner:** Clinical/safety adviser with the research lead.

**Resolution (2026-09-24):** withdrawn with the older-adult focus (D-43). Bereavement and circumstantial isolation can affect anyone, but that is a general taxonomy question, not this one; raise it separately if the annotation pilot shows it matters.

**Required by:** M1. **Status:** DECIDED.

---

## OD-026

**Question:** May harm-bearing content live on a free-tier hosted database and pass through free-tier model APIs? And does [OD-014](#od-014) also gate realism review and silver-label checking?

**Why it matters:** Generated conversations contain self-harm, harm-to-others and neglect content. Free tiers may have weaker retention and data-residency terms, and some free API tiers allow the provider to use inputs. Realism reviewers and silver checkers read the same content as annotators, but OD-014 currently gates only the pilot.

**Available options:** Treat OD-014 as gating every human-reading stage (**recommended**); use paid tiers with no-training terms for any stage that sends generated content; restrict hosted storage to seeds and keep conversations local until OD-014 resolves.

**Evidence already available:** [`SEED_PIPELINE_PLAN.md` §7](SEED_PIPELINE_PLAN.md#7-known-gaps-and-risks).

**Recommended owner:** Project lead with the clinical/safety adviser, alongside OD-014.

**Required by:** M2. **Status:** OPEN.

---

## OD-027

**Question:** What coverage targets govern seed selection, and what rule governs the realism sample?

**Why it matters:** The provisional values (advisory balance across theme family × explicitness × harm type × hard negative; at least 1 conversation per seed plus about 20% of the rest, stratified) are guesses made before the supply of sources is known.

**Available options:** Keep the provisional values and revise after the first collection run; derive targets from [`ANNOTATION_GUIDE.md` §9.3](ANNOTATION_GUIDE.md#93-selection-criteria-before-sample-size) and [OD-006](#od-006) once the pilot size is known.

**Evidence already available:** D-35.

**Recommended owner:** Research lead.

**Required by:** M2. **Status:** OPEN.

---

## OD-028

**Question:** Should the companion remember users across sessions, and if so under what gates? Separately, should the monitoring layer consult what earlier sessions with the same user showed, and how?

*Revised 2026-09-24 after D-46: companion memory is now a product decision for this team, not an external condition to test. The two halves are kept in one entry because they meet at the gate, but they are different mechanisms.*

**Why it matters:** Memory gives the companion continuity, and it is also one of the ways a companion can make things worse over time. For example, a companion that recalls "you said the neighbours are watching you" at the start of the next session reinstates a belief the user may have begun to doubt. On the monitoring side, each session is currently assessed alone, so a user who stated a specific method in an earlier session starts the next one from a clean trajectory.

**Prerequisite not yet in place:** there is no cross-session identity. The `sessions` record ([`architecture.md` §7.2](../../architecture.md)) has no participant field. Both halves need a pseudonymous `participant_id`, with retention and access rules under [OD-014](#od-014).

### Part A — companion memory (product)

**Options:**

1. No cross-session memory in the first companion version; continuity within a session only.
2. **Structured memory** in a small table with fixed fields (example fields: name, preferred tone, preferred reply length, topics of interest). Every write is a deliberate choice.
3. **Mem0** ([mem0.ai](https://mem0.ai)), self-hosted, with local models. Free-form facts extracted by an LLM, scoped by `user_id` (person), `run_id` (session) and `agent_id` (companion). Occasional misses are acceptable for continuity, so its semantic retrieval is not a defect here.

**Gates, whichever option:**

| Gate | Question | Example policy (illustrative) |
|---|---|---|
| Write | What gets stored? | Preferences and neutral context. Never a belief claim as fact; at most "user said X on date Y". Never harm-related specifics |
| Read | What gets loaded or retrieved? | Preferences automatically. Memories linked to signals the monitor has scored high are not loaded automatically |
| Retention | How long, and who sees it? | Expiry, user-visible deletion, access rules under [OD-014](#od-014) |

Deciding what counts as reinforcing is a clinical and safety judgement; the policy content belongs to the clinical/safety adviser.

**Constraints if Mem0 is chosen:** its default stack sends content to OpenAI for extraction and embeddings, which must be replaced with local models; the extraction model is one more model to choose and version; it runs in its **own database or schema with its own credentials**, never shared with monitoring tables, because Mem0 rewrites and deletes its memories while monitoring records are append-only. Its prompt-customisation and metadata-filtering features, needed for the write and read gates, are to be confirmed against the installed version.

### Part B — the monitor's cross-session findings history

**Options:**

1. None (status quo).
2. **A PostgreSQL query over stored findings** — scores, trajectory facts and alerts for the participant, each already citing turn ids and versions. Prior findings enter an alert only as a **named modifier** recorded on the alert (example: `prior_session_harm_intent_peak`), never silently.
3. Mem0 as the monitor's retrieval layer — **not recommended**: semantic top-k retrieval does not guarantee recall of a prior `harm_intent` 3; extracted facts lose turn citations; Mem0's update step can merge a hedged belief into an unhedged one, erasing the shift this project measures; and an indexed query is faster.

**Rules proposed for Part B:**

- Only observable, cited findings carry forward. No preferences, personality or disposition: a stored summary of a person is an assessment of a person, which the non-diagnostic boundary excludes.
- Prior-session context never enters the judge's input. A primed judge scores high again, and its scores stop being comparable with blind per-session human labels ([`ANNOTATION_GUIDE.md` §3–4](ANNOTATION_GUIDE.md#3-annotation-unit)). Cross-session context belongs at the alert layer.
- The monitor never reads the companion's memory store. It sees only the memory ids the companion reports loading ([OD-015](#od-015)), so an alert can cite "the companion reintroduced an earlier belief claim from memory".

**Evidence already available:** Mem0 documentation reviewed 2026-09-24: [health-AI memory architecture](https://mem0.ai/blog/memory-architecture-for-health-ai-keeping-patient-context-across-providers-and-sessions), [self-hosted Docker deployment](https://mem0.ai/blog/self-host-mem0-docker). No participant identity or multi-session scenario exists in the repository.

**Provisional recommendation:** Part A — option 1 or 2 for the first companion version, Mem0 once richer recall is needed. Part B — option 2 once participant identity exists.

**Recommended owner:** Part A: project lead, with the clinical/safety adviser owning the gate policy. Part B: research lead.

**Required by:** No milestone yet. Part A before the companion ships memory; Part B before cross-session alerting; both before any real user ([OD-030](#od-030)). **Status:** OPEN.

---

## OD-029

**Question:** Should the companion change its own reply when the conversation looks like it needs immediate intervention — for example, a NeMo Guardrails redirection flow (Colang) that outputs a safe response — and if so, what triggers it?

**Why it matters:** This turns a monitoring prototype into a system that intervenes. [`PROJECT_SCOPE.md` §5](PROJECT_SCOPE.md#5-future-capabilities-explicitly-not-mvp) and [`architecture.md`](../../architecture.md) treat modifying the companion's response as a possible extension requiring a separately approved interface, policy, safety review and audit path. After D-46 the companion is this team's, so the objection that it belongs to someone else no longer applies; the others do.

**Structure proposed:** the companion acts, the monitor only signals. Redirection flows live in the companion under their own versioned policy; the monitor's rule that no alert causes an automated action is unchanged.

**Trigger options:**

1. **Monitor signals.** Asynchronous; latency is one judge call (seconds), so the signal can only affect the turn after next.
2. **A fast inline pre-screen** before each companion reply. Jev (TypeSafe's typed-decision model) is a candidate: vendor-quoted 70–500 ms, typed yes/no, choice and score answers with probabilities; no rationale and no evidence ([Flavio Copes](https://flaviocopes.com/jev/), [DataCamp](https://www.datacamp.com/blog/system-one-models-jev)). A trigger needs a decision, not a cited score, so the evidence gap matters less here than for a judge. Use TypeSafe's own endpoint only; `jev-ai.pro` describes itself as an independent third-party relay.
3. Both: the pre-screen for the immediate reply, the monitor for the record.

**Rules proposed, whichever option:**

- **Escalate only.** A trigger may substitute a safe reply or raise priority; it never lowers a score, skips the full judge, or clears an alert. The full judge still scores every exchange for the record.
- **Every trigger is logged** with the pre-screen's probabilities, model version, threshold version, flow version, the original reply and the substituted one.
- **Scripts need clinical sign-off.** What a safe reply says, including any crisis resources, is a clinical decision.
- **A failure mode is chosen explicitly:** if the pre-screen is unavailable, the companion either withholds its reply or replies unguarded. Nobody may leave this to default.
- **Sessions record whether redirection was enabled**, so companion behaviour and guardrail behaviour can be told apart in evaluation. Annotators stay blind to it.

**Risks to weigh:** false positives on fiction, hypotheticals and ordinary spiritual discussion ([taxonomy §5](ANALYTICAL_TAXONOMY.md#5-context-categories)), where a scripted crisis reply damages trust; false negatives, which mean the system cannot be described as a safety guarantee; thresholds that cannot be set without human-adjudicated labels.

**Evidence already available:** None of this is built. No human labels exist to set a threshold.

**Recommended owner:** Project lead with the clinical/safety adviser.

**Required by:** No milestone yet; before any redirection flow is enabled, and before any real user ([OD-030](#od-030)). **Status:** OPEN.

---

## OD-030

**Question:** What must be in place before real users talk to the companion in a live demo (D-47)?

**Why it matters:** Every existing rule assumed synthetic conversations. With a real person, a missed signal is a missed person, the escalation contact must respond in real time rather than to annotators, and stored conversations become personal and sensitive data. [`PROJECT_SCOPE.md`](PROJECT_SCOPE.md) states real user conversations are out of scope at every stage; D-47 changes the intent, not the permission.

**Preconditions proposed (all required):**

1. **Ethics review** appropriate to the host institution, and informed consent that tells participants they are talking to an AI, that conversations are monitored, what is stored and for how long, and that it is not a clinical or crisis service.
2. **Participant eligibility and exclusion**, set with the clinical/safety adviser.
3. **Real-time escalation:** a named person on call for the whole demo, a written procedure for a participant who appears to be at real risk, and crisis resources appropriate to the participants' location. [OD-014](#od-014) extended from annotators to participants.
4. **Data protection:** lawful basis, retention, access, deletion on request, and where the data is processed — including every third-party model the conversation reaches (companion, judge, any pre-screen, any memory extraction).
5. **A registered data source** for real-user conversations with its permitted purposes, so the Dataset Use Gate can authorise it. Today the gate refuses it because it does not exist.
6. **Decided behaviour for the companion's safety features** used in the demo: memory ([OD-028](#od-028)) and redirection ([OD-029](#od-029)).
7. **Accurate claims:** nothing presented to participants or observers describes the monitor as validated, diagnostic or a safety guarantee. Without human-adjudicated labels no evaluation figure may be reported.

**Evidence already available:** None of the seven is in place. [OD-014](#od-014) and [OD-005](#od-005) are drafts awaiting approval.

**Recommended owner:** Project lead, with the clinical/safety adviser and whoever holds data-protection responsibility for the host organisation.

**Required by:** Before any real user. **Status:** OPEN.
