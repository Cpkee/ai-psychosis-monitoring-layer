# `data/` — contents and permitted use

This directory mixes **sealed evaluation data** with **imported reference assets**. Read this before using anything here.

Authoritative register: [`docs/foundations/DATA_SOURCES_AND_CONTRACTS.md` §3](../docs/foundations/DATA_SOURCES_AND_CONTRACTS.md#3-data-source-register).

| File | Source | Permitted use |
|---|---|---|
| `test_cases.json` | **`DS-01` — Psychosis-Bench, 16 sealed cases** | ⚠️ **SEALED. Final evaluation only.** Prohibited for training, prompt tuning, rubric tuning, threshold selection, model selection, fixtures, examples and validation sets. |
| `human_annotations.jsonl` | `DS-10` — imported MindEval annotations (60 conversations, 4 annotators each) | **Prohibited as domain reference labels or as evidence of system validity.** Usable **only** for isolated infrastructure-format tests, with provenance and the incompatible criteria preserved. Criteria are undefined in this repository; values span 0–6. **Never convert to the project's 0–3 scale.** Read only via `config/data_sources.json`. See [OD-007](../docs/foundations/OPEN_DECISIONS.md#od-007). |
| `human_user_turns.jsonl` | `DS-04` — imported MindEval personas / user turns (432 records) | Generation input for the persona system only. Prohibited as reference labels or evidence of validity. Read only via `config/data_sources.json`. |
| `profiles.jsonl` | `DS-04` — imported MindEval profiles (50 records) | Generation input for the persona system only. Prohibited as reference labels or evidence of validity. Read only via `config/data_sources.json`. |

## Why `test_cases.json` must not be touched by development code

The project's evaluation design depends on Psychosis-Bench being a **sealed final test set**. Any use during development — including reading it for a fixture, an example, or a "quick check" — silently invalidates every benchmark result, and the contamination cannot be detected afterwards.

## Controls in force

The seal is enforced in code, not by convention:

- `src/modules/source_registry/gate.py` is the only permitted reader. It requires a complete pre-registration record naming an **approved** rubric version, so **every load currently fails by design**.
- `python3 -m unittest discover -s tests -t .` fails if any other module references the sealed path, if a sealed prompt appears verbatim anywhere in code or fixtures, or if MindEval material is misused. It runs in CI on every push.
- Checksums and per-case permitted-use markers: `data/sealed/psychosis_bench_manifest.json`.

Full provenance, access record and control list: [`docs/foundations/BENCHMARK_SEAL.md`](../docs/foundations/BENCHMARK_SEAL.md).

The **final controlled location** for the sealed file is still undecided ([OD-008](../docs/foundations/OPEN_DECISIONS.md#od-008)). Do not execute or inspect additional cases while that decision is open.
