# Judge Configuration — Decisions Required Before 6b

**Document status:** Decision brief, awaiting approval
**Version:** 0.1
**Expands:** [OD-013](OPEN_DECISIONS.md#od-013)
**Blocks:** increment 6b, the `LLMJudgeAdapter` ([`IMPLEMENTATION_FOUNDATION.md` §8.2](IMPLEMENTATION_FOUNDATION.md#82-increment-6-in-detail--planned-the-real-llm-judge))

Four decisions. Each section states what to decide, how to decide it, what you need in order to decide, and **exactly what the system consumes once you have** — so wiring is mechanical rather than interpretive.

Every output below lands in one new artefact, `config/judge_configurations.json`, which is what `judge_configuration_version` will finally resolve to. That field is already stamped on every stored assessment and currently resolves to nothing.

> **A finding that changes one of these decisions.** On current Claude models — Opus 5, Sonnet 5, Fable 5/5.1, Opus 4.7/4.8 — the sampling parameters `temperature`, `top_p` and `top_k` have been **removed and return a 400 error**. They remain available only on Opus 4.6, Sonnet 4.6, Haiku 4.5 and older. "Set temperature to 0 for determinism" is no longer an available move on a current model, and §2 below is written around that.

---

## 1. Model

**Decide:** which provider and model the judge runs on.

**Instructions.** Start from the constraint that does the most work: [`RUBRIC_v0.1.md` §11.3](RUBRIC_v0.1.md#11-known-limitations) records that a judge sharing a family with the companion under evaluation may score it leniently, so settle §4 first and let it narrow the field. Then weigh three things against each other — the model must reliably produce the structured output the [§9 contract](RUBRIC_v0.1.md#9-required-structured-output) demands, it must hold a full conversation window plus the prompt, and it must be affordable at the volume the project will actually run. Prefer provider-native structured output over asking for free-text JSON; it removes a whole class of parse failure before it starts. Do not pick on price alone: a cheaper model that fails validation half the time costs more in re-runs and produces a rubric finding that is really a model finding, which is the worst outcome for this project because it contaminates the evidence [`RUBRIC_VALIDATION.md` §3](RUBRIC_VALIDATION.md#3-valid-triggers-for-a-rubric-change) depends on.

**Input you need**

| | |
|---|---|
| Which model family the **client companion** belongs to | Blocked on [OD-015](OPEN_DECISIONS.md#od-015); ask the client |
| Current model options, context windows and prices | Claude first-party rates below; other providers priced separately |
| Expected volume | Exchanges per conversation × conversations per run |
| Budget ceiling per evaluation run | Yours to set |

Claude first-party options, for sizing:

| Model | Model ID | Context | Input $/1M | Output $/1M |
|---|---|---|---|---|
| Claude Opus 5 | `claude-opus-5` | 1M | $5.00 | $25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | $2.00 | $10.00 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

Model IDs are **complete as written** — never append a date suffix. There is no separate snapshot string to pin, so "pin the snapshot" reduces to "record the model ID and never change it silently".

**Rough cost, to calibrate the argument.** One judge call is roughly 2,000 input tokens (prompt plus a short window) and ~800 output tokens across nine signals with explanations. On Opus 5 that is about **$0.03 per exchange**; a 12-exchange conversation ≈ $0.36, and all 16 sealed benchmark cases ≈ $6. On Sonnet 5, roughly 40% of that. At this scale cost is not the binding constraint — output reliability is. Note also that the prompt prefix is identical across every exchange in a session, so prompt caching cuts the input side substantially once the adapter reuses it.

**Output the system consumes**

```json
"provider": "anthropic",
"model": "claude-opus-5",
"model_family": "claude"
```

`model_family` exists solely to make §4 checkable in code.

---

## 2. Sampling and determinism

**Decide:** the generation settings, and — the harder half — what reproducibility now means given that temperature is no longer settable.

**Instructions.** On a current model your levers are `output_config.effort` (`low` through `max`, default `high`), whether thinking is on, and `max_tokens`. Choose effort by measuring rather than by intuition: run the same held-out exchanges at `medium`, `high` and `xhigh`, compare validator pass rates and agreement with each other, and take the lowest level whose quality holds. Higher effort is not free and does not reliably help on classification-shaped work. Leave thinking on — turning it off on Opus 5 has two documented failure modes, and lowering effort achieves the cost saving more safely. Set `max_tokens` generously enough that a nine-signal reply is never truncated mid-JSON, because truncation surfaces as `OUTPUT_UNREADABLE` and looks like a model failure when it is a configuration one.

Then confront the reproducibility question honestly. [`PROJECT_SCOPE.md` NFR-1](PROJECT_SCOPE.md#33-non-functional-requirements-mvp) says any stored score can be re-derived from the stored conversation, rubric version and judge version. **With no temperature control, exact re-derivation is not guaranteed**, and no configuration choice will make it so. You must pick what NFR-1 means instead — and record it, because the audit chain's credibility rests on the claim being true rather than aspirational.

**Input you need**

| | |
|---|---|
| A handful of held-out synthetic exchanges | To sweep effort against |
| Tolerance for run-to-run variation | A research judgement, not a technical one |
| Whether NFR-1 is re-derivation or re-runnability | The decision below |

**The NFR-1 options, briefly.** Either **(a)** redefine it as *re-runnability* — the stored inputs and versions are sufficient to run the judge again, and variation between runs is itself reportable data; or **(b)** keep exact re-derivation by storing the judge's full reply, which raises a §6.6 tension because provider output can carry reasoning the project has committed not to store; or **(c)** measure variation directly, scoring each exchange N times and storing the spread, which is the most honest and multiplies cost by N. (a) is the cheapest defensible answer and (c) is the most informative; both require amending NFR-1 rather than quietly failing it.

**Output the system consumes**

```json
"effort": "high",
"thinking": "adaptive",
"max_tokens": 16000,
"runs_per_exchange": 1,
"reproducibility_standard": "re_runnable"
```

Plus an amendment to NFR-1 in [`PROJECT_SCOPE.md`](PROJECT_SCOPE.md) stating which standard applies and why.

---

## 3. Confidence

**Decide:** what `confidence` means, how it is produced, and whether anything is allowed to act on it.

**Instructions.** The prompt already asks the model for `context_confidence` of `high`, `medium` or `low`, and the validator already accepts those three values — so a self-reported answer is being collected today whether or not anyone has decided what it means. Decide what it is before anything downstream starts trusting it. A self-report is nearly free and poorly calibrated: models report high confidence when wrong, and the number carries no guarantee. Confidence derived from repeat-run agreement is far better grounded and costs N times as much. Confidence derived deterministically from rubric conditions — hedged language present, frame ambiguous, evidence thin — is cheap and reproducible but coarse, and it is really a restatement of the `uncertainty` marker the taxonomy already defines. Whichever you choose, decide separately whether confidence may **gate** anything, because [taxonomy §7](ANALYTICAL_TAXONOMY.md#7-uncertainty-and-insufficient-evidence) is explicit that low confidence never suppresses a score, and a low-confidence result on `harm_intent` must still route to human review. A confidence value that quietly lowers an alert would breach that rule.

**Input you need**

| | |
|---|---|
| Whether confidence will be reported to reviewers, used in alert rules, or neither | Determines how much rigour it needs |
| Budget for repeat runs, if calibration matters | Ties to §2 `runs_per_exchange` |
| A calibration check | Does self-reported `high` actually agree with adjudicated labels more often than `low`? Unanswerable until the annotation pilot runs |

**Output the system consumes**

```json
"confidence_source": "self_reported",
"confidence_calibrated": false,
"confidence_may_gate_alerts": false
```

Plus one paragraph in [`ANALYTICAL_TAXONOMY.md` §7](ANALYTICAL_TAXONOMY.md#7-uncertainty-and-insufficient-evidence) defining the term, so every reader means the same thing by it. Until `confidence_calibrated` is true, any reviewer-facing display of confidence carries the same provisional label the draft rubric does.

---

## 4. Judge and companion family independence

**Decide:** the rule governing which judge may evaluate which companion, and how it is enforced.

**Instructions.** This is the decision most likely to undermine the project's headline finding, and the one most easily skipped. If the judge and the companion under evaluation come from the same model family, a lenient score is not distinguishable from a safe response — the finding "this companion behaved well" becomes unfalsifiable, and a reviewer is right to discount it. Write the rule as one of three: require different families outright, which is cleanest but may be impossible if the client's companion is the only model that handles the rubric well; permit same-family evaluation on condition that a second judge from a different family scores the same exchanges as a bias check, disclosing any systematic gap; or require two judges from different families always, reporting disagreement as a first-class result. Then make it **enforceable rather than remembered**: the judge configuration declares its family, the session already records the companion model, and a check refuses or flags the pairing the way the Dataset Use Gate refuses a prohibited purpose. A rule that lives only in a document will be violated by the first person in a hurry.

**Input you need**

| | |
|---|---|
| The client companion's model family | Blocked on [OD-015](OPEN_DECISIONS.md#od-015) |
| Whether budget exists for two judges | Doubles per-exchange cost |
| What the evaluation report must be able to claim | A claim of independence must be true |

**Output the system consumes**

```json
"family_independence_rule": "different_family_required",
"secondary_judge_configuration": null
```

Plus two mechanical additions: `companion_model_family` recorded on the session at ingestion, and a check that refuses — or flags and records — a run whose judge family matches the companion family. It belongs with the governance tests, where prohibited things already fail closed.

---

## 5. What none of these decisions change

- **No rubric is validated**, so every figure the judge produces is draft-rubric output, labelled as such, and not reportable ([`RUBRIC_VALIDATION.md` §5](RUBRIC_VALIDATION.md#5-approval-gate)).
- **Psychosis-Bench stays sealed.** Choosing a judge by comparing benchmark outcomes is model selection on sealed data and is prohibited ([`BENCHMARK_SEAL.md` §2](BENCHMARK_SEAL.md#2-permitted-and-prohibited-use)). Sweep effort and compare models on synthetic material only.
- **Judge output is never ground truth**, whichever model wins.
- **6a is unaffected.** The prompt, parser and error paths are built and tested offline; only the adapter waits on this brief.

## 6. Approval checklist

- [ ] §1 provider, model, family recorded
- [ ] §2 effort chosen **by measurement**, and NFR-1 amended to the standard actually met
- [ ] §3 confidence defined, and whether it may gate anything settled
- [ ] §4 rule written **and** made enforceable in code
- [ ] `config/judge_configurations.json` created with the values above
- [ ] [OD-013](OPEN_DECISIONS.md#od-013) moved to `DECIDED`
