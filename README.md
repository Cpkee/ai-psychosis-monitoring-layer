Use the following as the top-level README. It makes the project’s purpose, boundaries and deliverables visible before the technical details.

# AI Psychosis Monitoring Layer

A research prototype for evaluating whether an AI companion safely responds to conversational patterns involving unusual beliefs, AI dependency and potential harm under the umbrella of AI Psychosis.

## Project at a glance

This project builds a simulation and monitoring layer around an existing companion LLM.

It is designed to answer two questions:

1. Does the user’s conversational risk appear to increase or decrease over time?
2. Does the companion respond safely, or does it reinforce beliefs, dependency or harmful actions?

The system generates controlled synthetic conversations, sends them to the client’s companion API, evaluates both sides of the interaction and displays the results through a browser dashboard.

## Important boundary

This system does **not**:

- Diagnose psychosis or any mental-health condition.
- replace clinical assessment or professional care.
- train a new generative LLM.
- use the sycophantic test companion with real users.
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

    FR --> CR{Companion condition}
    SU --> CR

    CR --> CLIENT[Client companion API]
    CR --> SAFE[Grounded reference policy]
    CR --> SYC[Sycophantic stress-test condition]

    CLIENT --> LOG[Conversation record]
    SAFE --> LOG
    SYC --> LOG

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

The system runs the original 16 Psychosis-Bench cases against the client model.

These cases are preserved as a sealed final test set and are never used for training or prompt tuning.

This mode measures how safely the client model responds to a predetermined escalating conversation.

### 2. Adaptive simulation mode

A simulated user responds dynamically to the companion’s previous message.

A hidden-state updater tracks variables such as belief conviction, AI dependency, social withdrawal and harm intent. This allows different companion responses to produce different simulated trajectories.

## Companion conditions

The same synthetic scenario can be tested against three conditions:

- **Client companion:** the primary model being evaluated.
- **Grounded reference:** an empathetic, non-affirming comparison condition.
- **Sycophantic stress test:** an intentionally agreeable condition used only in offline experiments.

The grounded and sycophantic conditions provide lower-risk and higher-risk reference trajectories. They are experimental controls, not production companions.

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
- Client companion API adapter.
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
- The system is not approved for clinical or autonomous safety decision-making.