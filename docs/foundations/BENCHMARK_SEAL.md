# Psychosis-Bench Seal — Provenance, Access Record and Controls

**Document status:** Active control record
**Version:** 1.0
**Sealed artefact:** [`data/test_cases.json`](../../data/test_cases.json)
**Seal status:** `SEALED — FINAL EVALUATION ONLY`
**Manifest:** [`data/sealed/psychosis_bench_manifest.json`](../../data/sealed/psychosis_bench_manifest.json)

---

## 1. What is sealed

| Property | Value |
|---|---|
| File | `data/test_cases.json` |
| SHA-256 | `18b59263182899d0dad40be4e1351cd4b25bda18c4d99f8787c0bf9fb8184c62` |
| Git blob | `e6e17c3023df37073c083f3dd02ac15732a055fe` |
| Size | 30,543 bytes |
| Cases | 16 |
| **Prompts** | **192** (16 cases × 12 ordered prompts) — **all 192 are final-evaluation-only** |
| Declared file version | `1.0` |
| Upstream | [Psychosis-Bench](https://github.com/w-is-h/psychosis-bench) · [The Psychogenic Machine](https://arxiv.org/abs/2509.10970) |
| Register entry | [`DATA_SOURCES_AND_CONTRACTS.md` DS-01](DATA_SOURCES_AND_CONTRACTS.md#ds-01--psychosis-bench-sealed) |

Per-case checksums, per-prompt normalised hashes and a `permitted_use: FINAL_EVALUATION_ONLY` marker on every case are recorded in the manifest. **The manifest contains no prompt text** — only hashes — so it is safe to read, diff and quote.

### 1.1 What the seal is for

Psychosis-Bench is a **public** benchmark. The seal is therefore **not** about secrecy and encryption would be theatre.

The seal protects one specific claim: that this project's development, prompt construction, rubric tuning, threshold selection, judge selection and model selection **never touched these 192 prompts**. That claim cannot be re-established once broken, and contamination is undetectable after the fact — which is why the control is preventative rather than corrective.

---

## 2. Permitted and prohibited use

**Permitted:** a single pre-registered final evaluation run of an **already approved** rubric version.

**Prohibited, without exception:**

- Training, and any future classifier training
- Prompt construction and prompt tuning
- Rubric development, rubric tuning, and comparison of candidate rubric versions
- Threshold selection, alert-rule tuning
- Model selection, judge selection, judge configuration
- Test fixtures, routine tests, examples, validation sets
- Exploratory inspection, "just checking" a case, progress-tracking runs

---

## 3. Access record

Best-effort reconstruction, current as of 2026-09-16. Access outside this repository cannot be enumerated from here.

### 3.1 Repository history

| Event | Detail |
|---|---|
| Introduced | Commit `f8663a05d2f12c5321cd2e60f7f702a3212ab560`, "Uploaded Test Cases JSON file" |
| Date | 2026-09-11T13:11:10+08:00 |
| Author | Kee Chee Pheng `<keecheepheng@example.com>` |
| Modified since | **No.** The blob hash is unchanged from introduction to working copy (`e6e17c30…`). |
| Repository contributors (all time) | 1 — Kee Chee Pheng |

### 3.2 Remote exposure — unbounded

The file was pushed to `origin/main` at `https://github.com/Cpkee/ai-psychosis-monitoring-layer.git`, and **the repository is public**.

Consequences to record honestly:

1. All 192 prompts have been **publicly readable since 2026-09-11**. Prior exposure cannot be bounded or enumerated.
2. This does not itself invalidate the benchmark: the upstream benchmark is public, so public readability adds no disclosure that did not already exist.
3. It does mean **no confidentiality control can be retrofitted meaningfully**. What remains protectable is process discipline — which is what the controls in §4 enforce.
4. Any future claim that the benchmark was held confidentially by this project would be false and must not be made.

### 3.3 Automated and tooling access

| Accessor | When | What was accessed | Disclosure |
|---|---|---|---|
| Claude Code session `38328b5d` (foundations pack authoring) | 2026-09-16, **before the seal existed** | Parsed the full file; surfaced case 1's 12 prompts verbatim into the session transcript; enumerated all 16 cases' `id`, `name`, `theme`, `condition`, `harm_type` and prompt counts | **Disclosed.** This was exploratory inspection of the kind now prohibited. It occurred during repository inventory, before any control existed. |
| Same session, seal construction | 2026-09-16, after the decision to seal | Checksums, per-prompt hashes, case metadata; one prompt written to a temporary file to negative-test the guard, then deleted, never displayed | Metadata and hashing only; no additional prompt text surfaced |
| the governance tests in `tests/` | Every run, ongoing | Bytes hashed for checksum comparison; no content returned or printed | Permitted, non-inspecting |

**Assessment of the disclosed inspection.** Case 1 prompt content entered a session that also produced [`ANALYTICAL_TAXONOMY.md`](ANALYTICAL_TAXONOMY.md) and [`RUBRIC_v0.1.md`](RUBRIC_v0.1.md). The taxonomy's examples were authored independently and are labelled illustrative, and no sealed prompt appears in any project file — the guard's contamination check verifies this mechanically. Nevertheless, the exposure is recorded rather than dismissed, because the affected artefacts are exactly the ones the seal exists to keep uncontaminated. **Recommended action:** a human should review the taxonomy and rubric examples for resemblance to case 1 before `rubric_v1.0` is approved. Tracked as [OD-021](OPEN_DECISIONS.md#od-021).

### 3.4 What cannot be determined from here

- Who has cloned, forked or read the public repository.
- Whether the file was read outside git — filesystem access times are unreliable and were not preserved.
- Whether any copy exists outside this repository.

---

## 4. Controls now in force

Implemented as the seams defined in [`architecture.md`](../../architecture.md) §6.1 and §6.2, not as bespoke per-dataset code.

| # | Control | Implementation | architecture.md |
|---|---|---|---|
| C-1 | Manifest with checksum, counts and per-case permitted use | [`data/sealed/psychosis_bench_manifest.json`](../../data/sealed/psychosis_bench_manifest.json) — field names per §8.1 | §8.1(1) |
| C-2 | Source registered with explicit permitted and prohibited uses | [`config/data_sources.json`](../../config/data_sources.json) → [`src/modules/source_registry/registry.py`](../../src/modules/source_registry/registry.py) | §6.1 |
| C-3 | Single authorisation seam; no reader takes a path | [`src/modules/source_registry/gate.py`](../../src/modules/source_registry/gate.py) — readers accept `AuthorizedDataUse` only | §6.2 |
| C-4 | Fail closed on unregistered source, unspecified purpose, failed integrity | `DatasetUseGate.decide` | §6.2 |
| C-5 | `FINAL_EVALUATION` execution mode required | `_sealed_source_reasons` | §6.2 |
| C-6 | Refused unless tied to frozen artefact versions | `FinalEvaluationSpecification`, all 13 fields required | §6.2, §6.14 |
| C-7 | Audit event emitted for every authorisation **and** rejection | `InMemoryAuditSink` / `JsonlAuditSink`; identifiers and decisions only, no conversation content | §6.2, §15 |
| C-8 | A sealed source cannot be defined as permitting anything else | `DataSourceDefinition.__post_init__` raises | §8.1 |
| C-9 | No sealed prompt verbatim in code, fixtures, prompts or validation sets | `tests/test_benchmark_seal.py::NoBenchmarkContamination` — hash comparison, never stores prompt text | §8.1(8) |
| C-10 | Raw labels preserved; `ai_sweetheart` inconsistency kept visible | `tests/test_benchmark_seal.py::RawLabelPreservation` | §8.3, §2 |
| C-11 | Governance tests prove prohibited purposes fail | [`tests/test_dataset_use_gate.py`](../../tests/test_dataset_use_gate.py) | §8.1(5), §17 |
| C-12 | CI runs the suite on every push and pull request | [`.github/workflows/tests.yml`](../../.github/workflows/tests.yml) — no assertion logic in YAML | §17 |

### 4.1 There is no loading path at all — by design

**No code in this repository can read the sealed file.** The Dataset Use Gate refuses every purpose, and no Controlled Evaluation Runner (§6.14) exists to supply an authorised final-evaluation path. `FinalEvaluationSpecification` is defined as a **type and seam only**, so Phase F has somewhere to attach.

This is the correct state for Phase A. Gate A requires only that prohibited uses demonstrably fail. Building the runner now would create a loading path while the final controlled location is still undecided ([OD-008](OPEN_DECISIONS.md#od-008)).

### 4.2 Verification performed

| Check | Result |
|---|---|
| Full suite, 33 tests | PASS |
| Sealed source refused for development, training, prompt tuning, rubric tuning, rubric validation, model selection, infrastructure-format test, internal validation | PASS — 8 tests |
| Final evaluation refused in development execution mode | PASS |
| Final evaluation refused without a specification | PASS |
| Final evaluation refused with any frozen input missing | PASS — 4 subtests |
| `authorize()` raises rather than returning a path | PASS |
| Unregistered source, unspecified purpose, integrity mismatch all refused | PASS |
| Audit event emitted for every decision, with no conversation content | PASS |
| Manifest checksum matches the untransformed file; counts 192 / 16 / 12 | PASS |
| Manifest contains no prompt text | PASS |
| `ai_sweetheart` inconsistency still visible | PASS |
| **Contamination test detects a planted sealed prompt** (written programmatically, never displayed, then deleted) | **PASS — suite failed and named the file** |
| Suite returns to green after cleanup | PASS |

An untested control is not a control; the contamination test was deliberately made to fail before being trusted.

---

## 5. Running the tests

```bash
python3 -m unittest discover -s tests -t .        # all tests
python3 -m unittest tests.test_dataset_use_gate   # governance tests only
```

Standard library only, no installation, no virtual environment. Runs on the repository's system Python today and in CI.

Exit code `0` means the boundaries hold. A failure means a boundary has been crossed — **the fix is to remove the violating code, never to amend a test or a registry entry.**

---

## 6. If the seal is broken

1. **Stop.** Do not continue the work that touched it.
2. Record what was accessed, by whom, when and for what purpose, in §3.3 of this document.
3. Assess whether the access could have influenced any rubric, prompt, threshold, judge choice or fixture.
4. If it could have, disclose it in the evaluation report and mark affected results **contaminated for model-selection purposes**. Disclosure is the minimum remedy; it does not restore the seal.
5. Raise it as a defect under [`RUBRIC_VALIDATION.md` §3](RUBRIC_VALIDATION.md#3-valid-triggers-for-a-rubric-change) if a rubric artefact was affected.

---

## 7. Outstanding

| Item | Tracked as |
|---|---|
| Final controlled location for the sealed file — no additional cases are to be executed or inspected while this is decided | [OD-008](OPEN_DECISIONS.md#od-008) |
| Human review of taxonomy and rubric examples against case 1, given the disclosed pre-seal inspection | [OD-021](OPEN_DECISIONS.md#od-021) |
| Whether public repository visibility is intended for a project holding a sealed evaluation set | [OD-008](OPEN_DECISIONS.md#od-008) |
