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
