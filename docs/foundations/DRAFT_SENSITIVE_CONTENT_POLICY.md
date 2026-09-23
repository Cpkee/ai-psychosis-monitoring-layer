# DRAFT FOR APPROVAL — Sensitive Content Handling and Escalation Ownership

> ## Status: DRAFT FOR APPROVAL — not in force
>
> This is a proposal written so an approver can **edit rather than author**. It resolves [OD-014](OPEN_DECISIONS.md#od-014). Until it is approved and every `[ROLE TO BE ASSIGNED]` placeholder is filled, **the annotation pilot must not start** — [`ANNOTATION_GUIDE.md` §10](ANNOTATION_GUIDE.md#10-handling-sensitive-content) cannot be followed without it.
>
> **Approver:** `[ROLE TO BE ASSIGNED]` · **Clinical/safety adviser consulted:** `[ROLE TO BE ASSIGNED]` · **Approval date:** *not approved*

---

## 1. Scope

Applies to everyone who reads, annotates, adjudicates, reviews or stores conversation content in this project: annotators, adjudicators, developers, reviewers and advisers.

## 2. What people will be exposed to

All conversations in this project are **synthetic**. They nonetheless contain sustained, detailed and deliberately escalating depictions of:

| Category | Present in the corpus as |
|---|---|
| Suicide and self-harm | Jumping from height; suicide framed as "joining" an AI |
| Harm through neglect | Stopping medical treatment; self-neglect |
| Harm to others | Cult formation and recruitment |
| Financial and property harm | Financial ruin; property damage |
| Social harm | Severe isolation; severing family contact |

Source: `harm_type` values recorded in [`data/sealed/psychosis_bench_manifest.json`](../../data/sealed/psychosis_bench_manifest.json), and the equivalent categories the Synthetic Scenario Engine is specified to generate.

Synthetic origin lowers the concern. It does not remove it: the material is designed to be persuasive, is read repeatedly, and is read closely enough to score.

## 3. Proposed rules

### 3.1 Informed acceptance

1. Before accepting any batch, a person is told in writing: the content categories present, the expected session volume, and that they may decline or stop at any time without giving a reason and without consequence.
2. Declining or stopping is recorded as a resourcing fact, never in any individual performance record.
3. A person is never assigned a batch they have previously stopped, unless they ask for it.

### 3.2 Volume and pacing

| Control | Proposed value | Note |
|---|---|---|
| Maximum annotation time per day | `[4 hours — TO BE CONFIRMED]` | Set with the annotator, not imposed |
| Break after | `[45 minutes continuous — TO BE CONFIRMED]` | |
| Maximum consecutive days on high-severity batches | `[3 — TO BE CONFIRMED]` | |
| High-severity batches interleaved with benign ones | Yes | Also improves calibration, since a majority-concerning workload biases scoring |

Values are proposed, not evidence-based. The approver should set them with the clinical/safety adviser.

### 3.3 Support and debriefing

1. A **named contact** is supplied with every batch: `[NAME AND CONTACT TO BE ASSIGNED]`.
2. A debrief is offered at the end of every batch, and is available on request at any time. Uptake is not recorded against the individual.
3. Access to `[ORGANISATIONAL SUPPORT ROUTE TO BE SPECIFIED — e.g. employee assistance, occupational health, or an equivalent named provision]`.
4. Nobody is asked to justify using any of the above.

### 3.4 Escalation — content that may involve a real person at risk

This is the rule that most needs an owner before the pilot starts.

1. If a person has **any** reason to believe a conversation involves a real person at real risk, they **stop immediately**, do not continue annotating it, and contact the escalation owner.
2. **Escalation owner:** `[ROLE TO BE ASSIGNED]`. **Out-of-hours route:** `[TO BE ASSIGNED]`.
3. Annotators are **never** asked to assess whether the risk is real. That judgement belongs to the escalation owner, supported by the clinical/safety adviser.
4. The escalation owner acknowledges within `[TO BE CONFIRMED — proposed: 1 working hour]` and records the outcome.
5. Escalations are logged with date, session identifier, who raised it and the outcome. The log is reviewed at the end of the pilot.
6. A false alarm is a correct use of this procedure and is treated as such.

> **Note for the approver.** All data is synthetic, so this path should never fire. It exists because "should never" is not "cannot" — data provenance can be mislabelled, and a person who suspects real risk must have somewhere to go that is not their own judgement.

### 3.5 Storage, access and retention

| Control | Proposal |
|---|---|
| Access to conversation content | Restricted to assigned annotators, adjudicators and named project staff |
| Content leaving the annotation tool | Prohibited. Evidence is cited by `turn_index`, never by pasted text ([`ANNOTATION_GUIDE.md` §6](ANNOTATION_GUIDE.md#6-evidence-turn-selection)) |
| Content in explanations and alerts | Identifiers and brief evidence-grounded description only, never transcript excerpts beyond what a reviewer needs |
| Retention of synthetic conversations | `[TO BE CONFIRMED — proposed: retained for the life of the experiment record, since reproducibility requires it]` |
| Retention of annotator identity | Pseudonymous `annotator_id` only; no names in data records |
| Deletion route | `[TO BE SPECIFIED]` |
| Real personal data | None is collected. If any is ever found in the corpus, it is an escalation under §3.4. |

### 3.6 Publication and display

1. No sealed prompt text is reproduced in any document, dashboard, report or artefact. Enforced by [`tests/`](../../tests/).
2. Illustrative examples in project documentation are authored for the purpose and labelled illustrative.
3. Reviewer interfaces display harmful content only where it is the evidence for the alert being reviewed, never as ambient browsing.

## 4. What this policy deliberately does not do

- It does not make anyone responsible for assessing real-world risk except the named escalation owner.
- It does not treat synthetic content as harmless.
- It does not make support conditional on demonstrating distress.

## 5. Approval checklist

- [ ] Escalation owner named, with an out-of-hours route
- [ ] Named debrief contact assigned
- [ ] Organisational support route specified
- [ ] Volume, break and consecutive-day values confirmed with the clinical/safety adviser
- [ ] Retention and deletion routes specified
- [ ] Clinical/safety adviser has reviewed §3.4
- [ ] Approver signed and dated
- [ ] [OD-014](OPEN_DECISIONS.md#od-014) moved to `DECIDED` and this document's status changed to *in force*
