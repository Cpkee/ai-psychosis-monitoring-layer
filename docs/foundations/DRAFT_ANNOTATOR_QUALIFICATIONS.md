# DRAFT FOR APPROVAL — Annotator Qualifications and Required Training

> ## Status: DRAFT FOR APPROVAL — not in force
>
> This is a proposal written so an approver can **edit rather than author**. It resolves [OD-005](OPEN_DECISIONS.md#od-005). Until it is approved, **no annotation can become a reference label**, because the authority of the adjudicated label set depends on knowing who produced it and what they were trained to do.
>
> **Approver:** `[ROLE TO BE ASSIGNED]` · **Clinical/safety adviser consulted:** `[ROLE TO BE ASSIGNED]` · **Approval date:** *not approved*

---

## 1. Why this needs deciding before the pilot

Human-adjudicated labels are the standard the LLM Judge is measured against ([`RUBRIC_VALIDATION.md` §2](RUBRIC_VALIDATION.md#2-what-the-rubric-is-measured-against)). If annotator competence is undefined, the reference labels have unknown authority, and every agreement figure computed from them is uninterpretable. Deciding afterwards is not possible: it would mean re-annotating.

The project constraint is real and recorded — [`README.md`](../../README.md) states that access to clinical experts is limited and clinical review will be sought where possible. This proposal is built around that constraint rather than assuming it away.

## 2. Proposed roles

### 2.1 Annotator (first-pass, independent)

| Requirement | Proposal |
|---|---|
| Clinical qualification | **Not required.** The task is scoring observable conversational content against defined anchors, not clinical assessment. |
| Required | Completion of the training in §3; a pass on the calibration set (§4); fluent English; ability to follow written inclusion/exclusion criteria precisely |
| Disqualifying | Authored the rubric, the judge prompt, or the scenarios being annotated; any role in judge development |
| Desirable | Prior structured annotation experience; familiarity with conversational data |
| Quantity | At least 2 independent annotators per conversation ([`ANNOTATION_GUIDE.md` §9.4](ANNOTATION_GUIDE.md#94-reviewers)) |

### 2.2 Adjudicator

| Requirement | Proposal |
|---|---|
| Required | Experienced annotator with `[TO BE CONFIRMED — proposed: at least one completed batch]`; did not produce either label under adjudication; completed adjudication training (§3.4) |
| Clinical qualification | **Required for `safety_disagreement` items** (any disagreement on `harm_intent` or `hes`), where available — see §5 for the fallback |
| Disqualifying | Authored either label; authored the rubric |

### 2.3 Clinical / safety adviser

| Requirement | Proposal |
|---|---|
| Required | A relevant professional qualification in mental health, clinical psychology, psychiatry or equivalent — `[SPECIFIC REQUIREMENT TO BE CONFIRMED]` |
| Role | **Consulted, not embedded.** Reviews the taxonomy's harm-related definitions; reviews a sample of adjudicated labels; adjudicates or reviews `safety_disagreement` items; advises on §3.4 escalation |
| Not responsible for | Routine annotation volume; making the system clinically valid — no amount of advice does that |

### 2.4 Cultural-competence reviewer

| Requirement | Proposal |
|---|---|
| Required | Familiarity with the tradition or community in question, sufficient to judge whether content is ordinary within it |
| Role | Confirms assignments of the cultural/ordinary-spiritual context category ([taxonomy §5.5](ANALYTICAL_TAXONOMY.md#55-cultural-or-ordinary-spiritual-discussion)) |
| Rationale | This category is the taxonomy's highest false-positive risk. Misclassifying ordinary faith or practice as risk is the most likely way this system would be unjust to a real person. |
| Engagement | Per tradition represented in the corpus, as needed. `[ENGAGEMENT ROUTE TO BE SPECIFIED]` |

## 3. Required training

Proposed as approximately `[half a day — TO BE CONFIRMED]` before any batch, with all materials already written.

| # | Module | Content | Assessment |
|---|---|---|---|
| T-1 | Purpose and boundary | What the system is and is not; the non-diagnostic boundary; that annotators describe conversations, never assess people | Acknowledgement |
| T-2 | Taxonomy | Walkthrough of [`ANALYTICAL_TAXONOMY.md`](ANALYTICAL_TAXONOMY.md): each signal's inclusion criteria, exclusion criteria, and the benign and ambiguous counterexamples | Short exercise |
| T-3 | Anchors | The score anchors in [`RUBRIC_v0.1.md` §5](RUBRIC_v0.1.md#5-score-levels-and-observable-anchors); applying inclusion before exclusion; naming the exclusion that applied | Short exercise |
| T-4 | Context categories | The six categories; that attributed and fictional content is **recorded, not suppressed**; that cultural/spiritual content is the main false-positive risk | Short exercise |
| T-5 | Evidence citation | Citing the fewest turns that justify the score; citing frame-establishing turns; citing by identifier, never pasted text | Exercise |
| T-6 | Uncertainty | `null` versus 0; `between_levels`; `context_ambiguous`; that ambiguity on `harm_intent` is never resolved downward | Exercise |
| T-7 | Independence | Why the first pass is blind; what must not be seen; declaring recognition of a conversation | Acknowledgement |
| T-8 | Sensitive content | [`DRAFT_SENSITIVE_CONTENT_POLICY.md`](DRAFT_SENSITIVE_CONTENT_POLICY.md) in full, including the §3.4 escalation route and the right to stop | Acknowledgement |
| T-9 | Adjudication *(adjudicators only)* | Disagreement types; writing a rationale; when to record `unresolvable` rather than force a resolution | Exercise |

Training version is recorded on every annotation (`annotation_guide_version`), so labels made under different training are separable.

## 4. Calibration before labels count

1. Each annotator labels at least 5 pilot conversations spanning the categories in [`ANNOTATION_GUIDE.md` §9.1](ANNOTATION_GUIDE.md#91-required-composition).
2. Discrepancies against the guide are discussed with the guide owner.
3. Calibration labels are retained, marked `calibration: true`, and **excluded from agreement statistics**.
4. Proposed pass condition: `[TO BE CONFIRMED]` — for example, no `major_disagreement` against the reference calibration key on `harm_intent` or `hes`, and no systematic directional bias across signals.
5. An annotator who does not pass repeats the training and calibration. Failing calibration is a signal about the guide as often as about the annotator; recurring failures on the same item are raised as a guide defect.

## 5. The realistic constraint: limited clinical access

The project has recorded that clinical expertise is limited. Proposed handling, in preference order:

1. **Preferred.** Trained lay annotators for the first pass; a clinically qualified adjudicator for `safety_disagreement` items; clinical adviser reviews a sample of adjudicated labels.
2. **Acceptable.** Trained lay annotators and lay adjudicators throughout; **all** `safety_disagreement` items queued for clinical review before the reference label set is released; the release carries an explicit known limitation.
3. **Not acceptable.** Releasing a reference label set containing unreviewed `safety_disagreement` items with no disclosure.

If only one reviewer is available for a batch, that batch produces **no reference labels** — it is marked `single_reviewer: true`, excluded from agreement statistics and validation sets, and reported as a resourcing gap ([`ANNOTATION_GUIDE.md` §9.4](ANNOTATION_GUIDE.md#94-reviewers)).

## 6. Record-keeping

| Field | Stored |
|---|---|
| `annotator_id` | Pseudonymous, stable. Never a name in the data record. |
| Qualification tier | `lay_trained` / `clinically_qualified` / `cultural_competence` |
| Training version completed | Recorded |
| Calibration result | Recorded, with date |
| Roles held per conversation | Recorded, to enforce adjudicator independence automatically |

## 7. Approval checklist

- [ ] Annotator requirement confirmed (lay-trained accepted, or not)
- [ ] Adjudicator experience threshold set
- [ ] Clinical adviser's specific qualification requirement stated
- [ ] Which of the §5 options applies, confirmed with the clinical/safety adviser
- [ ] Cultural-competence reviewer engagement route specified
- [ ] Training duration and calibration pass condition set
- [ ] Approver signed and dated
- [ ] [OD-005](OPEN_DECISIONS.md#od-005) moved to `DECIDED` and this document's status changed to *in force*
