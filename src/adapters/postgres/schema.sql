-- Conversation storage. architecture.md section 7.2.
--
-- Scope: sessions and turns only. Assessments, jobs, trajectories, alerts and
-- artifact_versions arrive with their own repositories.
--
-- Constraints here are the storage-level invariants named in sections 6.3 and
-- 13. Ordering and contiguity of turn_index are domain rules owned by the
-- Conversation Orchestrator; a unique index cannot express "no gaps".

CREATE TABLE IF NOT EXISTS sessions (
    id                    TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL,
    external_session_id   TEXT NOT NULL,
    source_version_id     TEXT NOT NULL,
    scenario_id           TEXT NOT NULL,
    raw_theme_label       TEXT NOT NULL,
    canonical_theme_label TEXT,
    theme_mapping_version TEXT,
    companion_condition   TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    closed_at             TEXT,

    -- Section 8.3: a canonical theme may only be introduced through a
    -- reviewed mapping version, and never replaces the raw label.
    CONSTRAINT canonical_theme_requires_mapping_version
        CHECK (canonical_theme_label IS NULL OR theme_mapping_version IS NOT NULL),
    CONSTRAINT raw_theme_label_not_blank
        CHECK (length(raw_theme_label) > 0)
);

CREATE TABLE IF NOT EXISTS turns (
    id                       TEXT PRIMARY KEY,
    session_id               TEXT NOT NULL REFERENCES sessions (id),
    turn_index               INTEGER NOT NULL,
    role                     TEXT NOT NULL,
    message                  TEXT NOT NULL,
    timestamp                TEXT NOT NULL,
    idempotency_key          TEXT NOT NULL,
    model_name               TEXT,
    model_version            TEXT,
    source_payload_reference TEXT,

    CONSTRAINT turns_role_valid CHECK (role IN ('user', 'assistant')),
    CONSTRAINT turns_index_non_negative CHECK (turn_index >= 0),

    -- Section 13: reject duplicate turn indices.
    CONSTRAINT turns_unique_index UNIQUE (session_id, turn_index),
    -- Section 6.3: a retried ingestion must not create a duplicate turn.
    CONSTRAINT turns_unique_idempotency_key UNIQUE (session_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS turns_by_session ON turns (session_id, turn_index);

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id                          TEXT PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions (id),
    through_turn_id             TEXT NOT NULL REFERENCES turns (id),
    status                      TEXT NOT NULL,
    attempt_count               INTEGER NOT NULL DEFAULT 0,
    taxonomy_version            TEXT NOT NULL,
    scale_version               TEXT NOT NULL,
    rubric_version              TEXT NOT NULL,
    judge_configuration_version TEXT NOT NULL,
    schema_version              TEXT NOT NULL,
    requested_at                TEXT NOT NULL,
    started_at                  TEXT,
    completed_at                TEXT,
    failure_code                TEXT,

    CONSTRAINT jobs_status_valid
        CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'DELAYED', 'FAILED')),
    CONSTRAINT jobs_attempt_count_non_negative CHECK (attempt_count >= 0),
    CONSTRAINT jobs_failed_records_a_code
        CHECK (status <> 'FAILED' OR failure_code IS NOT NULL),
    CONSTRAINT jobs_completed_records_a_time
        CHECK (status <> 'COMPLETED' OR completed_at IS NOT NULL),

    -- Section 13: analysis jobs are unique for the same session window and
    -- artefact-version set, so a retried ingestion cannot queue the same work
    -- twice.
    CONSTRAINT jobs_unique_request UNIQUE (
        session_id, through_turn_id, taxonomy_version, scale_version,
        rubric_version, judge_configuration_version, schema_version
    )
);

CREATE INDEX IF NOT EXISTS jobs_by_session ON analysis_jobs (session_id, requested_at);

CREATE TABLE IF NOT EXISTS assessments (
    id                           TEXT PRIMARY KEY,
    analysis_job_id              TEXT NOT NULL UNIQUE REFERENCES analysis_jobs (id),
    context_category             TEXT NOT NULL,
    context_confidence           TEXT,
    uncertainty                  TEXT,
    insufficient_evidence        BOOLEAN NOT NULL,
    explanation                  TEXT NOT NULL,
    judge_provider               TEXT NOT NULL,
    judge_model                  TEXT NOT NULL,
    judge_model_version          TEXT NOT NULL,
    rubric_version               TEXT NOT NULL,
    taxonomy_version             TEXT NOT NULL,
    scale_version                TEXT NOT NULL,
    prompt_configuration_version TEXT NOT NULL,
    schema_version               TEXT NOT NULL,
    created_at                   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_scores (
    id             TEXT PRIMARY KEY,
    assessment_id  TEXT NOT NULL REFERENCES assessments (id) ON DELETE CASCADE,
    signal_code    TEXT NOT NULL,
    score_value    INTEGER,
    scale_version  TEXT NOT NULL,
    uncertain      BOOLEAN NOT NULL DEFAULT FALSE,
    not_assessable BOOLEAN NOT NULL DEFAULT FALSE,

    -- "Could not tell" and "absent" are different findings. A null score is
    -- always marked not_assessable, and a marked score is always null.
    CONSTRAINT scores_null_iff_not_assessable
        CHECK ((score_value IS NULL) = not_assessable),
    CONSTRAINT scores_unique_per_assessment UNIQUE (assessment_id, signal_code)
);

CREATE TABLE IF NOT EXISTS assessment_evidence (
    assessment_id     TEXT NOT NULL REFERENCES assessments (id) ON DELETE CASCADE,
    turn_id           TEXT NOT NULL REFERENCES turns (id),
    signal_code       TEXT,
    evidence_excerpt  TEXT,

    PRIMARY KEY (assessment_id, turn_id, signal_code)
);

CREATE INDEX IF NOT EXISTS scores_by_assessment ON signal_scores (assessment_id);
CREATE INDEX IF NOT EXISTS evidence_by_assessment ON assessment_evidence (assessment_id);

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS failure_detail TEXT;

ALTER TABLE signal_scores
    ADD COLUMN IF NOT EXISTS specificity_markers TEXT[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS trajectory_updates (
    id                        TEXT PRIMARY KEY,
    session_id                TEXT NOT NULL REFERENCES sessions (id),
    through_turn_id           TEXT NOT NULL REFERENCES turns (id),
    trajectory_policy_version TEXT NOT NULL,
    window_definition         TEXT NOT NULL,
    state_json                JSONB NOT NULL,
    derived_facts_json        JSONB NOT NULL,
    input_assessment_ids      TEXT[] NOT NULL,
    created_at                TEXT NOT NULL,

    -- A derivation that does not name its inputs cannot be recomputed,
    -- which §19 criterion 7 requires.
    CONSTRAINT trajectory_names_its_inputs
        CHECK (array_length(input_assessment_ids, 1) >= 1)
);

CREATE INDEX IF NOT EXISTS trajectory_by_session
    ON trajectory_updates (session_id, created_at);
