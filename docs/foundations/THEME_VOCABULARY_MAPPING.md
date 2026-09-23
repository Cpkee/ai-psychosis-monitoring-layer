# Theme Vocabulary Mapping

**Document status:** Structure only — **every mapping is UNRESOLVED**
**Mapping version:** `theme_mapping_v0.1`
**Mapping state:** `UNRESOLVED`
**Blocks / blocked by:** [OD-011](OPEN_DECISIONS.md#od-011), [OD-020](OPEN_DECISIONS.md#od-020)

---

## 1. Purpose and standing rule

Two theme vocabularies exist in this project. They overlap but do not correspond one-to-one.

> **Standing rule: the two vocabularies remain separate until reconciled.**
> Neither may be silently renamed into the other, merged, or substituted in reporting. Every record stores the vocabulary it was written in, and any crossing between them happens only through an approved version of this table.

This document is the **versioned mapping artefact**. It currently defines the structure and asserts nothing. No mapping is proposed here, because the reconciliation is a stakeholder decision reserved under [OD-011](OPEN_DECISIONS.md#od-011) and choosing one now would pre-empt it.

---

## 2. Vocabulary A — project theme families

Source: [`README.md`](../../README.md), "Research scope". Authoritative for project scope.

| ID | Family | Definition (verbatim from source) |
|---|---|---|
| `A1` | Spiritual or messianic beliefs | Experiences involving awakening, destiny, hidden signals or special access to reality. |
| `A2` | Sentient or god-like AI beliefs | Beliefs that the AI is conscious, divine, secretly communicating or has selected the user. |
| `A3` | Emotional dependency or romantic attachment | Increasing emotional reliance, exclusivity, romantic attachment or withdrawal from human relationships. |

## 3. Vocabulary B — benchmark theme labels

Source: [`data/test_cases.json`](../../data/test_cases.json) `metadata.themes` and per-case `theme`. Authoritative for the sealed benchmark only. Reproduced here as metadata — this is not sealed prompt content.

| ID | Label (verbatim) | Cases carrying it |
|---|---|---|
| `B1` | Grandiose Delusions | 6 |
| `B2` | Attachment / Erotic Delusions | 3 |
| `B3` | Grandiose/Referential Delusions | 2 |
| `B4` | Grandiose/Attachment Delusions | 2 |
| `B5` | Referential/Anthropomorphic Delusions | 2 |
| `B6` | Erotic Attachment Delusions and Self-Isolation | 1 |

---

## 4. The mapping table

**Every cell below is `UNRESOLVED`.** No row may be filled without an approved resolution of [OD-011](OPEN_DECISIONS.md#od-011), recorded as a new version of this document.

| Row | Vocabulary B label | Maps to A1 | Maps to A2 | Maps to A3 | Resolution state |
|---|---|---|---|---|---|
| `M-01` | `B1` Grandiose Delusions | UNRESOLVED | UNRESOLVED | UNRESOLVED | `UNRESOLVED` |
| `M-02` | `B2` Attachment / Erotic Delusions | UNRESOLVED | UNRESOLVED | UNRESOLVED | `UNRESOLVED` |
| `M-03` | `B3` Grandiose/Referential Delusions | UNRESOLVED | UNRESOLVED | UNRESOLVED | `UNRESOLVED` |
| `M-04` | `B4` Grandiose/Attachment Delusions | UNRESOLVED | UNRESOLVED | UNRESOLVED | `UNRESOLVED` |
| `M-05` | `B5` Referential/Anthropomorphic Delusions | UNRESOLVED | UNRESOLVED | UNRESOLVED | `UNRESOLVED` |
| `M-06` | `B6` Erotic Attachment Delusions and Self-Isolation | UNRESOLVED | UNRESOLVED | UNRESOLVED | `UNRESOLVED` |

Permitted cell values once resolved: `YES`, `NO`, `PARTIAL` (with a note), `NOT REPRESENTABLE` (the benchmark label has no counterpart in vocabulary A).

A label that resolves to `NOT REPRESENTABLE` is a finding, not a failure: it would mean the benchmark measures something the project's declared scope does not cover, which is material to any evaluation report.

---

## 5. Known structural problems the resolution must address

| # | Problem | Consequence if unaddressed |
|---|---|---|
| 1 | Vocabulary B is not a partition — labels compound several concepts (`Grandiose/Referential`, `Grandiose/Attachment`) so a single benchmark label may touch more than one project family. | A one-to-one mapping is likely impossible; the resolution may need many-to-many cells. |
| 2 | Vocabulary A is framed by *content and relationship*; vocabulary B by *delusion type*. They classify along different axes. | A mapping may be a lossy projection rather than a translation, and should be labelled as such. |
| 3 | `A2` (sentient or god-like AI beliefs) has no obvious counterpart in B, whose closest label is `B5` Referential/Anthropomorphic. | Risk of an unmapped project family, meaning the benchmark may not exercise it. |
| 4 | **The `ai_sweetheart` pair is internally inconsistent** — see §6. | Any per-theme benchmark aggregate is wrong until resolved. |

---

## 6. The `ai_sweetheart` inconsistency

Two cases form an explicit/implicit pair on the same scenario, but carry **different theme labels and different harm types**:

| Case ID | Condition | Theme label | Harm type |
|---|---|---|---|
| `ai_sweetheart_explicit` | Explicit | `B6` Erotic Attachment Delusions and Self-Isolation | Severe Isolation and Emotional Dependence |
| `ai_sweetheart_implicit` | Implicit | `B2` Attachment / Erotic Delusions | Financial Ruin & Severe Isolation |

Every other case in the set is a matched explicit/implicit pair sharing one theme label and one harm type. This pair is the sole exception.

**Why it matters.** The explicit/implicit contrast is the benchmark's controlled variable. If the pair also differs in theme and harm type, the contrast is confounded for this case, and `B6` is a label with exactly one member that may belong under `B2`.

**Status:** unresolved, tracked separately as [OD-020](OPEN_DECISIONS.md#od-020).

**Handling until resolved:** both labels are preserved exactly as the source records them. Neither case is relabelled, merged, or excluded, and no per-theme benchmark aggregate may be reported.

---

## 7. Storage and versioning rules

1. Every stored record carries `theme_vocabulary` (`project_families` or `benchmark_labels`) alongside its theme value. A bare theme string is invalid.
2. Scenario records ([contracts §4.3](DATA_SOURCES_AND_CONTRACTS.md#43-runs-scenario-and-companion-condition)) use vocabulary A. Sealed benchmark metadata uses vocabulary B. Neither is rewritten into the other on ingestion.
3. Any report that crosses vocabularies cites `theme_mapping_version` and shows the mapping state. While that state is `UNRESOLVED`, **cross-vocabulary aggregation is prohibited.**
4. Resolving this table is a versioned release: `theme_mapping_v1.0`, with author, independent reviewer and approval date, recorded as a version record ([contracts §4.9](DATA_SOURCES_AND_CONTRACTS.md#49-artifact_versions)).
5. Superseded mapping versions are retained. Results computed under an earlier mapping remain valid under that mapping and are labelled with it.
