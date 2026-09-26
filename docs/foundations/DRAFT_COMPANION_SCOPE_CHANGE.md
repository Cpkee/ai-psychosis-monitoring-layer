# Draft: one in-house companion, and a real-user live demo

**Document status:** DRAFT FOR APPROVAL. Nothing below has been applied.
**Implements:** [D-46](IMPLEMENTATION_FOUNDATION.md#10-decisions-taken-during-implementation) (one companion, built by this team) and [D-47](IMPLEMENTATION_FOUNDATION.md#10-decisions-taken-during-implementation) (a live demo with real users is intended, gated on [OD-030](OPEN_DECISIONS.md#od-030)).
**Already applied:** [`README.md`](../../README.md), and [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) OD-015, OD-028, OD-029, OD-030.

[`architecture.md`](../../architecture.md) is the implementation source of truth, so its wording changes only on approval. [`PROJECT_SCOPE.md`](PROJECT_SCOPE.md) is included because it states that real users are out of scope at every stage.

---

## 1. `architecture.md`

| § / line | Current | Proposed |
|---|---|---|
| §4 diagram (l. 90–92, 101–103) | `Client Companion API`, `Grounded Reference`, `Sycophantic Stress Test` nodes, each feeding the platform | One node, `Companion (built in-house)`, feeding the platform. A dashed return arrow from the platform labelled `risk signals (OD-015)` |
| §4 actors table (l. 114–116) | Three rows | One row: **Companion** — produces companion responses; reports its configuration and versions, memories loaded, and redirection flows fired — *Target-system evaluation* |
| §5 diagram (l. 128–130, 162–164) | `CLIENT`, `GROUND`, `STRESS` sources, each registered | One `COMPANION` source, registered |
| §6.9 invariant (l. 468) | "does not block or alter the Client Companion response unless a separately approved runtime intervention interface is introduced" | "The monitoring layer creates alerts and may send versioned signals to the companion ([OD-015](OPEN_DECISIONS.md#od-015)). It never blocks or alters a companion response itself. Any change to a reply is made by the companion under its own approved, versioned policy ([OD-029](OPEN_DECISIONS.md#od-029))." |
| §7.2 `sessions` (after l. 626) | No participant field | Add, **when OD-028 Part B is decided**: `participant_id nullable` (pseudonymous). Add now: nothing. `companion_condition` keeps its column and now records the companion configuration (example value: `companion_v0.1`) |
| §7.2 new record, **when OD-015 is decided** | — | `companion_session_reports`: session id, companion model version, persona-prompt version, memory-policy version, redirection-flow version, loaded memory ids. `redirection_events`: session id, turn id, flow id and version, trigger source, pre-screen probabilities if any, original and substituted reply |
| §12.4 (l. 1106) | "Blocking, rewriting, or replacing a Client Companion response is not part of the monitoring MVP…" | Keep the principle, retarget it: "The evaluator is never an inline response gate. If the companion changes its own reply, that is a companion feature with its own approved interface, policy, safety review and audit path ([OD-029](OPEN_DECISIONS.md#od-029)); every change is logged and every session records whether redirection was enabled." |
| §16 layout (l. 1231) | `adapters/client_companion/` | `adapters/companion/` — the monitor's side of the OD-015 contract |
| §17 contract tests (l. 1259) | "Client Companion adapter" | "Companion ↔ monitor contract (OD-015)" |
| §10.1 preconditions | Annotation pilot only | Add a sibling list, **§10.3 Live-demo preconditions**, pointing to [OD-030](OPEN_DECISIONS.md#od-030); the live demo cannot start until all seven are approved |

Unchanged on purpose: l. 293, 486, 1367 ("condition" metadata stays, with its new meaning), and every alert invariant.

---

## 2. `PROJECT_SCOPE.md`

| § / line | Current | Proposed |
|---|---|---|
| §1.2 (l. 38) | "Real user conversations remain out of scope at every stage (§7)." | "Real user conversations are out of scope until the live-demo preconditions ([OD-030](OPEN_DECISIONS.md#od-030)) are approved (D-47). Synthetic conversations remain the development and validation corpus." |
| §2 stakeholders (l. 46) | "Client stakeholders … their companion model" | "Client stakeholders … the companion built for them" |
| §4 item 9 (l. 116) | "the three companion conditions … (client companion, grounded reference, sycophantic stress test)" | "the companion (D-46), in whichever configurations are under test" |
| §5 (l. 125) | Intervening in the companion's next response: "Possible extension. Out of MVP." | "A companion feature, not a monitoring one. Undecided ([OD-029](OPEN_DECISIONS.md#od-029))." |
| §5 (l. 127) | Real-user deployment: "Out of scope at every stage of this prototype" | "Live demo intended (D-47); not permitted until [OD-030](OPEN_DECISIONS.md#od-030) is approved" |
| §6 (l. 140) | "Deploy the sycophantic stress-test condition with real users…" | Replace with: "Expose any real user to the companion before OD-030 is approved." |
| §7 (l. 158) | Grounded reference and sycophantic stress-test row | Remove. Add a note under the table: "Reference conditions were dropped by D-46; controls come from scenario design." |
| §7 (l. 162) | "Real user conversations — Not used at any stage of this prototype." | "Not used until OD-030 is approved and a data source for them is registered with the Dataset Use Gate." |
| New §1.3 | — | "**The companion.** One companion, built by this team for the client (D-46). The companion acts; the monitoring layer observes and signals. No alert itself causes an action." |

---

## 3. Also stale, left for their owners

- [`SEED_PIPELINE_PLAN.md` §7](SEED_PIPELINE_PLAN.md#7-known-gaps-and-risks): the gap "the gold set cannot satisfy 'every companion condition' until the client companion exists" no longer exists in that form. To be updated with the S5 text below.
- [`SEED_PIPELINE_PLAN.md` §3.4](SEED_PIPELINE_PLAN.md#34-generate) and the S5 row of §6: S5 generates against the grounded and sycophantic reference companions and says "the client companion is not generated". Under D-46 it generates against the one companion, which needs a first version (pinned model, persona prompt with non-sycophancy instructions) before S5 can run, and the family-separation rule (D-30) then covers that companion. Positive and negative controls move into scenario design. To be updated before S5.
- `CLAUDE.md`: D-46 and D-47 were added to its hard rules on 2026-09-25, with a note that the `architecture.md` and `PROJECT_SCOPE.md` passages above are stale until this draft is approved.

---

## 4. What approval means

Approving this draft applies §1 and §2 as written. The records in §1 marked "when OD-0xx is decided" are **not** created on approval: under "write no code without a caller", they arrive with the increment that first needs them.
