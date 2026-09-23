# Rubric Validation and Change Control

**Document status:** Proposed foundation, awaiting stakeholder approval
**Version:** 0.1
**Canonical for:** how a rubric version becomes authoritative, and what evidence must exist before it does.

**Purpose of this document:** to provide a checkable gate that prevents an unvalidated rubric from being presented as authoritative, and preserves the evidence behind every approved change.

Current state: [`RUBRIC_v0.1.md`](RUBRIC_v0.1.md) is **draft and unvalidated**. No approved rubric version exists.

---

## 1. Lifecycle

```text
Observed recurring scoring problem
        ↓
Human review and error analysis
        ↓
Proposed rubric revision
        ↓
Old-versus-new comparison on a fixed validation set
        ↓
Human review of intended improvements and regressions
        ↓
Approval and versioned release
```

Each stage produces an artefact that is retained:

| Stage | Artefact retained |
|---|---|
| Observed recurring problem | Defect record: the recurring pattern, the sessions and exchanges exhibiting it, how many |
| Human review and error analysis | Error-analysis note: what the rubric currently instructs, why it produces the observed result, which taxonomy concept is implicated |
| Proposed revision | Diff against the current rubric, plus the specific defect IDs it addresses |
| Old-vs-new comparison | Comparison report on a **fixed, pre-registered** validation set: per-concept agreement with reference labels, before and after |
| Human review of improvements and regressions | Reviewer note listing intended improvements achieved, improvements not achieved, and **every regression**, with an accept/reject decision for each |
| Approval and release | Version record ([contracts §4.9](DATA_SOURCES_AND_CONTRACTS.md#49-artifact_versions)) with `status: approved`, a named independent reviewer, and an approval date |

The validation set is fixed **before** the revision is written. A validation set chosen after seeing the revision's results is not evidence.

---

## 2. What the rubric is measured against

| Compared to | Status |
|---|---|
| **Human-adjudicated reference labels** ([`ANNOTATION_GUIDE.md` §8.3](ANNOTATION_GUIDE.md#83-adjudication-procedure)) | **The standard.** Agreement is measured against these. |
| Individual (unadjudicated) annotations | Evidence about annotator agreement, not a standard for the judge |
| Prior judge versions | Regression detection only; never a standard |
| Scenario generation parameters (intended phase, intended harm type) | **Never a standard** ([contracts §8.3](DATA_SOURCES_AND_CONTRACTS.md#8-cross-cutting-constraints)) |
| Simulator hidden state | **Never a standard** |
| Psychosis-Bench results | **Never used to tune or select a rubric version** (§6) |

Agreement metric and acceptance thresholds are unresolved — [OD-017](OPEN_DECISIONS.md#od-017). Until they are set, comparison reports present raw agreement and disagreement-type breakdowns without a pass/fail claim.

---

## 3. Valid triggers for a rubric change

A change is admissible only if it is justified by one of the following, **documented with evidence**:

1. Repeated disagreement with human-adjudicated labels on the same concept or boundary.
2. Ambiguous score-level boundaries — annotators or the judge cannot reliably separate two adjacent levels.
3. Recurring false positives.
4. Recurring false negatives.
5. Weak handling of fiction, hypothetical, quoted, attributed, or cultural/spiritual contexts.
6. Weak temporal reasoning, including incorrect `specificity_markers` or frame-establishment fields that make trajectory computation wrong.
7. Missing or incorrect supporting evidence — scores that cite the wrong turns, or cite none.
8. Newly validated edge cases that the rubric does not cover.
9. Approved changes to metric definitions in [`ANALYTICAL_TAXONOMY.md`](ANALYTICAL_TAXONOMY.md).
10. Required changes to the structured output contract ([`RUBRIC_v0.1.md` §9](RUBRIC_v0.1.md#9-required-structured-output)).
11. Resolution of an entry in [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) that the rubric currently marks as provisional.

**Not valid triggers:**

- Ordinary variation in a single conversation.
- A single surprising score, however striking.
- A stakeholder's preference for a different result on a particular case.
- A desire to improve a headline number.
- Anything observed on Psychosis-Bench (§6).

A "recurring" weakness means the same failure mode observed across **multiple distinct sessions**, recorded as defect instances before any revision is drafted. How many sessions constitute recurrence is unresolved — [OD-017](OPEN_DECISIONS.md#od-017); until set, the defect record states the count and the reviewer judges sufficiency explicitly.

---

## 4. Validation effort proportional to change

Every rubric version intended for official evaluation or deployment requires **independent human validation**. The depth scales with the change:

| Change class | Examples | Required validation |
|---|---|---|
| **Minor clarification** | Wording that does not alter any score boundary; added example; clarified exclusion already implied by the taxonomy | Targeted review of the affected cases, plus a regression check on the fixed validation set confirming no score changes outside the affected concept |
| **Changed score or context rules** | Moved an anchor between levels; changed a context-assignment rule; changed evidence requirements; changed `null` handling | Broader revalidation on the full fixed validation set, with per-concept before/after agreement and an explicit regression list |
| **New signal or major redesign** | Added or removed a concept; changed the scale; changed the unit of assessment; restructured the output contract | Full validation and adjudication proportional to project risk: new or extended reference labels covering the new concept, full-set comparison, and clinical/safety adviser review where harm-related concepts are touched |

Additional rules:

1. A change touching `harm_intent`, `hes` or `sis` is **never** classified as a minor clarification.
2. Reclassifying a change downward to reduce validation effort requires the independent reviewer's agreement, recorded.
3. Regressions may be accepted, but each must be individually named and justified in the reviewer note. Silent regressions invalidate the approval.
4. The validation set version is recorded on the release. Comparisons across different validation-set versions are not evidence of improvement.

---

## 5. Approval gate

A rubric version may be marked `approved` only when **all** of the following are true. Any `no` blocks the release.

- [ ] The change is justified by a documented trigger from §3, with defect instances across multiple sessions.
- [ ] An error-analysis note exists.
- [ ] A fixed validation set was pre-registered before the revision was written.
- [ ] An old-versus-new comparison report exists against **human-adjudicated reference labels**.
- [ ] Every regression is listed with an accept/reject decision.
- [ ] Validation depth matches the change class (§4).
- [ ] An **independent human reviewer** — not the author of the change — has reviewed and approved. This cannot be waived.
- [ ] Where harm-related concepts changed, a clinical/safety adviser reviewed the change, or their unavailability is explicitly recorded as a known limitation on the release.
- [ ] Known limitations are written into the released rubric.
- [ ] A version record ([contracts §4.9](DATA_SOURCES_AND_CONTRACTS.md#49-artifact_versions)) exists with `status: approved`, `independent_reviewer`, `validation_dataset_version`, `test_results_ref`, `approval_date` and `content_hash`.
- [ ] **No Psychosis-Bench data was used** at any point in the change (§6).

Enforcement, so the gate is checkable rather than aspirational:

1. A judge run configured with a rubric whose version record is not `approved` stamps its results `rubric_status: draft`, and those results are **excluded from any evaluation report** by query, not by convention.
2. Reports and dashboards display the rubric status alongside every figure. A figure produced under a draft rubric is labelled as such wherever it appears.
3. The `content_hash` is verified at run time. A rubric whose content does not match its version record fails the run.

---

## 6. Psychosis-Bench isolation

Psychosis-Bench ([`DS-01`](DATA_SOURCES_AND_CONTRACTS.md#ds-01--psychosis-bench-sealed)) must not be used to tune or select rubric versions.

Prohibited, without exception:

- Running the benchmark to compare candidate rubric versions.
- Inspecting per-case benchmark results to diagnose a rubric weakness.
- Constructing validation sets, examples or anchors from benchmark content.
- Selecting a judge model, prompt configuration or threshold using benchmark outcomes.
- Repeated benchmark runs to track progress during development.

Permitted:

- A single, pre-registered final evaluation run of an **already approved** rubric version, reported as-is.

Controls:

1. All sealed sessions carry `sealed = true`; every development, tuning and validation query filters it out ([contracts §8.1](DATA_SOURCES_AND_CONTRACTS.md#8-cross-cutting-constraints)).
2. Benchmark runs execute on a separate code path with its own configuration ([`IMPLEMENTATION_FOUNDATION.md` §7](IMPLEMENTATION_FOUNDATION.md#7-what-is-deliberately-out-of-the-tracer-bullet)).
3. Each benchmark run is pre-registered: rubric version, judge model/version, date, and the reason for running, recorded **before** the run.
4. If the benchmark is nonetheless run more than once against evolving rubric versions, every run is disclosed in the evaluation report, and the results are reported as **contaminated for model-selection purposes**. Disclosure is the minimum remedy; it does not restore the seal.

---

## 7. Version semantics

| Version | Meaning |
|---|---|
| `v0.x` | Draft, experimental or unvalidated. May be used for development and validation runs. **Must not** be presented as authoritative, used for external reporting, or used for a benchmark run. |
| `v1.0` | First approved and human-validated release. Requires a complete §5 gate. |
| `v1.x` | Controlled revision of an approved rubric. Requires a §5 gate proportional to the change class. Full history retained. |
| `v2.0+` | Major redesign. Results are **not comparable** to prior major versions without an explicit re-scoring of the comparison set. |

Rules:

1. Version numbers never decrease and are never reused.
2. A superseded version's record is retained with `status: superseded`; its stored results remain valid as history under that version.
3. Re-scoring under a new version **adds** results; it never overwrites results produced under an earlier version ([contracts §4.4](DATA_SOURCES_AND_CONTRACTS.md#44-assessments)).
4. Every stored score names the rubric version that produced it, so mixed-version data is always separable.
5. The taxonomy is versioned independently. A taxonomy change that alters a concept's meaning forces a rubric version bump, because the rubric's anchors then refer to different definitions.

---

## 8. Release record template

Recorded for every released rubric version, in the version record ([contracts §4.9](DATA_SOURCES_AND_CONTRACTS.md#49-artifact_versions)):

```text
Version:                     (e.g. rubric_v1.0)
Status:                      draft | approved | superseded | withdrawn
Change summary:              what changed
Rationale:                   which defects from §3 it addresses, with defect IDs
Author:                      who wrote the change
Independent reviewer:        who approved it (must differ from the author)
Clinical/safety review:      reviewer, or explicit record of unavailability
Validation dataset version:  the pre-registered fixed set
Test results:                pointer to the comparison report
Error analysis:              pointer to the error-analysis note
Regressions:                 each one, with accept/reject and justification
Known limitations:           carried into the released rubric
Approval date:               date, or "not approved"
Content hash:                hash of the released rubric text
```

### 8.1 Current register

| Version | Status | Independent reviewer | Validation set | Approval date |
|---|---|---|---|---|
| `rubric_v0.1` | `draft` | **None** | **None** | **Not approved** |

No approved rubric version exists. Any evaluation figure produced today is a draft-rubric figure and must be labelled as such.
