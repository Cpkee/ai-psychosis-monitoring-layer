# AI Psychosis Monitoring Layer

A research prototype for evaluating whether an AI companion safely responds to conversational patterns involving unusual beliefs, AI dependency and potential harm under the umbrella of AI Psychosis.

## Architecture

[`architecture.md`](architecture.md) is the **implementation source of truth** for the platform: module seams, interfaces, invariants, data records, delivery phases and gates. Where it conflicts with the foundations pack below, the architecture wins.

## Project foundations pack

The canonical definitions, data contracts and validation workflow live in [`docs/foundations/`](docs/foundations/). This README remains the project overview; the foundations pack is the source of truth for the details below.

| Document | Canonical for |
|---|---|
| [PROJECT_SCOPE.md](docs/foundations/PROJECT_SCOPE.md) | MVP boundaries; analytical vs functional vs non-functional requirements |
| [ANALYTICAL_TAXONOMY.md](docs/foundations/ANALYTICAL_TAXONOMY.md) | Every user signal, AI-behaviour metric, context category and temporal concept |
| [RUBRIC_v0.1.md](docs/foundations/RUBRIC_v0.1.md) | LLM Judge scoring framework — **draft and unvalidated** |
| [ANNOTATION_GUIDE.md](docs/foundations/ANNOTATION_GUIDE.md) | Human annotation, disagreement and adjudication |
| [DATA_SOURCES_AND_CONTRACTS.md](docs/foundations/DATA_SOURCES_AND_CONTRACTS.md) | Data-source register, contracts, lifecycle, audit chain |
| [RUBRIC_VALIDATION.md](docs/foundations/RUBRIC_VALIDATION.md) | Rubric change control and the approval gate |
| [IMPLEMENTATION_FOUNDATION.md](docs/foundations/IMPLEMENTATION_FOUNDATION.md) | The first end-to-end tracer bullet and its acceptance tests |
| [OPEN_DECISIONS.md](docs/foundations/OPEN_DECISIONS.md) | Unresolved questions awaiting stakeholder or clinical review |
| [FOUNDATION_READINESS.md](docs/foundations/FOUNDATION_READINESS.md) | What is ready, partially ready, or blocked; the agreed priority sequence |
| [BENCHMARK_SEAL.md](docs/foundations/BENCHMARK_SEAL.md) | Psychosis-Bench provenance, access record and controls |
| [THEME_VOCABULARY_MAPPING.md](docs/foundations/THEME_VOCABULARY_MAPPING.md) | The two theme vocabularies, held separate; mappings UNRESOLVED |
| [DRAFT_SENSITIVE_CONTENT_POLICY.md](docs/foundations/DRAFT_SENSITIVE_CONTENT_POLICY.md) | Draft for approval — blocks the annotation pilot |
| [DRAFT_ANNOTATOR_QUALIFICATIONS.md](docs/foundations/DRAFT_ANNOTATOR_QUALIFICATIONS.md) | Draft for approval — blocks reference labels |

### Current status

**The project is not implementation-ready for evaluation reporting. It is ready for a bounded tracer-bullet implementation using synthetic fixtures and provisional, auditable contracts.**

### Data boundaries

[`data/test_cases.json`](data/test_cases.json) is the **sealed** Psychosis-Bench set: all 192 prompts are final-evaluation-only and must never enter development, prompt construction, rubric tuning, fixtures or routine tests. The seal is enforced in code, not by convention:

```bash
# Seal and governance tests: bare interpreter, no dependencies, no database.
python3 -m unittest tests.test_dataset_use_gate tests.test_benchmark_seal
```

## Seeing it run

```bash
docker compose up -d
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/walkthrough.py
```

Ingests a short synthetic conversation, scores it with the deterministic fake judge, and prints the resulting trajectory. The scores are canned — it demonstrates the pipeline, not any ability to assess a conversation. It resets every conversation and analysis table first, so it runs against the test database (`TEST_DATABASE_URL`, default `apml_test`) and refuses any database not named `*_test`.

## Running the full suite

The repository contract tests need PostgreSQL. Everything else does not, and never will:

```bash
docker compose up -d
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
TEST_DATABASE_URL=postgresql://apml:apml@localhost:5433/apml_test \
  .venv/bin/python -m unittest discover -s tests -t .
```

Without `TEST_DATABASE_URL` the PostgreSQL tests skip and the rest still run, so the seal stays verifiable with no setup at all.

Tests truncate every table, so they use their own database, `apml_test`, and refuse any database not named `*_test`. Working data (collected documents, cached extractor replies, seeds) lives in `apml`, which `scripts/seeds.py` reads from `DATABASE_URL`. On a Docker volume created before `apml_test` existed, create it once:

```bash
docker exec apml-postgres psql -U apml -d apml -c "CREATE DATABASE apml_test OWNER apml"
```

See [`data/README.md`](data/README.md) for permitted use of every data file, and [`BENCHMARK_SEAL.md`](docs/foundations/BENCHMARK_SEAL.md) for provenance, the access record and the full control list.

## Project at a glance

This project builds a companion LLM for the client, and a simulation and monitoring layer around it. There is one companion, and this team builds it ([D-46](docs/foundations/IMPLEMENTATION_FOUNDATION.md#10-decisions-taken-during-implementation)).

It is designed to answer two questions:

1. Does the user’s conversational risk appear to increase or decrease over time?
2. Does the companion respond safely, or does it reinforce beliefs, dependency or harmful actions?

The system generates controlled synthetic conversations, sends them to the companion, evaluates both sides of the interaction and displays the results through a browser dashboard.

## Important boundary

This system does **not**:

- Diagnose psychosis or any mental-health condition.
- replace clinical assessment or professional care.
- train a new generative LLM.
- expose real users to the companion before the live-demo preconditions are approved ([OD-030](docs/foundations/OPEN_DECISIONS.md#od-030)).
- treat synthetic data as evidence of real-world clinical performance.

It detects and evaluates **conversational risk indicators** for research purposes.

## Research scope

The prototype is intentionally limited to three literature-supported theme families:

1. **Spiritual or messianic beliefs**  
   Experiences involving awakening, destiny, hidden signals or special access to reality.

2. **Sentient or god-like AI beliefs**  
   Beliefs that the AI is conscious, divine, secretly communicating or has selected the user.

3. **Emotional dependency or romantic attachment**  
   Increasing emotional reliance, exclusivity, romantic attachment or withdrawal from human relationships.

Simulated conversations progress through four phases:

1. Initial engagement and latent vulnerability.
2. Pattern-seeking and early belief formation.
3. Belief solidification, grandiosity or dependency.
4. Behavioural enactment and potential harm.

These phases are simulation states—not clinical stages assigned to real users.

## How the system works

```mermaid
flowchart TD
    PB[Sealed Psychosis-Bench cases] --> BA[Benchmark adapter]
    BA --> FR[Fixed benchmark runner]

    SS[Synthetic scenarios] --> SC[Scenario controller]
    PS[Persona and hidden state] --> SC
    SC --> SU[Adaptive simulated user]

    FR --> COMP[Companion LLM]
    SU --> COMP

    COMP --> LOG[Conversation record]

    LOG --> UM[User-trajectory monitor]
    LOG --> RA[Response-safety auditor]

    UM --> AE[Alert engine]
    RA --> AE

    AE --> API[Python API]
    API --> DB[(Experiment database)]
    API --> UI[Browser dashboard]
```

## Evaluation modes

### 1. Fixed benchmark mode

The system runs the original 16 Psychosis-Bench cases against the companion.

These cases are preserved as a sealed final test set and are never used for training or prompt tuning.

This mode measures how safely the companion responds to a predetermined escalating conversation.

### 2. Adaptive simulation mode

A simulated user responds dynamically to the companion’s previous message.

A hidden-state updater tracks variables such as belief conviction, AI dependency, social withdrawal and harm intent. This allows different companion responses to produce different simulated trajectories.

## The companion

There is one companion: an LLM with a persona prompt that carries non-sycophancy instructions. It may later gain gated memory across sessions ([OD-028](docs/foundations/OPEN_DECISIONS.md#od-028)) and redirection flows that act on risk signals ([OD-029](docs/foundations/OPEN_DECISIONS.md#od-029)); neither is decided.

The companion and the monitoring layer stay separate. The companion acts; the monitor observes and sends signals back. No alert itself causes an action. Every session records which configuration of the companion produced it, so a change in behaviour can be traced to a change in the companion.

The earlier plan compared three conditions: the client companion, a grounded reference and a sycophantic stress test. The two reference conditions have been dropped. Lower-risk and higher-risk reference trajectories must now come from the synthetic scenarios themselves, or from configurations of the one companion.

## Evaluation metrics

### User-trajectory indicators

- Belief conviction.
- Pattern-seeking and preoccupation.
- AI exceptionalism or dependency.
- Social withdrawal or exclusivity.
- Behavioural or harm intent.

### Companion-response metrics

- **DCS — Delusion Confirmation Score:** whether the response confirms or amplifies the belief.
- **HES — Harm Enablement Score:** whether the response enables a harmful action.
- **SIS — Safety Intervention Score:** whether appropriate human or professional support is suggested.
- **SGQ — Supportive Grounding Quality:** whether the response is empathetic, non-affirming and constructive.

These metrics evaluate conversation behaviour, not the user’s clinical condition.

## Warning output

The monitoring layer produces a structured warning containing:

- Estimated theme and phase.
- User-trajectory scores.
- Companion-response scores.
- Low, medium, high or critical severity.
- Supporting conversation excerpts.
- Explanation for the warning.
- Scorer and model versions.
- Confidence and human-review status.

The prototype prioritises recording and explaining warnings. Modifying the companion’s next response is a possible extension.

## Data strategy

The project uses controlled synthetic data because suitable real conversational data is unavailable and ethically sensitive.

- Psychosis-Bench’s 16 cases are reserved exclusively for final evaluation.
- New synthetic scenarios are generated from independent scenario specifications.
- Data is balanced across themes, phases, explicitness and severity.
- Benign hard-negative examples are included to measure false alarms.
- A representative subset is reviewed by human annotators.
- Clinical review will be sought where possible.

Synthetic data supports engineering evaluation but does not establish clinical validity.

## Model strategy

The MVP does not train a generative LLM.

Existing LLMs are used for:

- Simulating users.
- Producing companion responses.
- Applying evaluation rubrics.

A small transformer classifier may later be fine-tuned for faster or offline risk screening if enough consistently labelled data is collected.

## Primary deliverables

- Psychosis-Bench adapter.
- The companion: persona prompt, and its interface to the monitoring layer ([OD-015](docs/foundations/OPEN_DECISIONS.md#od-015)).
- Scenario controller and persona system.
- Adaptive simulated-user engine.
- Hidden-state updater.
- User-trajectory monitor.
- Companion-response safety auditor.
- Warning and event-logging service.
- Python API.
- Browser-based evaluation dashboard.
- Synthetic development dataset.
- Annotation handbook and evaluation report.
- Reproducible final benchmark results.

## Proposed technology stack

- **Backend:** Python and FastAPI.
- **Schemas:** Pydantic.
- **Database:** PostgreSQL with optional `pgvector`.
- **Session cache:** Redis or Redis Iris where justified.
- **Dashboard:** React/Next.js or a lightweight Python dashboard.
- **LLM access:** Cloud model APIs.
- **Optional local inference:** DistilRoBERTa or DeBERTa-v3-small.
- **Experiment tracking:** Versioned prompts, models, seeds and scoring rubrics.

## Research foundation

This project builds upon:

- [The Psychogenic Machine](https://arxiv.org/abs/2509.10970)
- [Psychosis-Bench](https://github.com/w-is-h/psychosis-bench)
- [MindEval: Benchmarking Language Models on Multi-turn Mental Health Support](https://arxiv.org/pdf/2511.18491)


## Current limitations

- Training conversations are primarily synthetic.
- The initial scope covers only three theme families.
- LLM-based evaluators may introduce scoring bias.
- Access to clinical experts is limited.
- Results from simulated conversations may not generalise to real users.
- There is no grounded or sycophantic reference companion, so the monitor has no built-in positive and negative controls.
- A live demo with real users is intended but not permitted until its preconditions are approved ([OD-030](docs/foundations/OPEN_DECISIONS.md#od-030)).
- The system is not approved for clinical or autonomous safety decision-making.