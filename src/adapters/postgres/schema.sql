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

-- Alerts (architecture §6.9, §7.2 extended per D-38). An alert asks a person to
-- review a conversation; it is not a diagnosis and triggers nothing.
CREATE TABLE IF NOT EXISTS alerts (
    id                          TEXT PRIMARY KEY,
    session_id                  TEXT NOT NULL REFERENCES sessions (id),
    through_turn_id             TEXT NOT NULL REFERENCES turns (id),
    rule_set_version            TEXT NOT NULL,
    rule_id                     TEXT NOT NULL,
    status                      TEXT NOT NULL,
    severity                    TEXT,
    requires_manual_review      BOOLEAN NOT NULL,
    contributing_assessment_ids TEXT[] NOT NULL,
    trajectory_update_id        TEXT NOT NULL REFERENCES trajectory_updates (id),
    triggering_signal_score_ids TEXT[] NOT NULL,
    evidence_turn_ids           TEXT[] NOT NULL,
    context_categories_present  TEXT[] NOT NULL,
    context_modifier_applied    TEXT,
    explanation                 TEXT NOT NULL,
    judge_model_version         TEXT NOT NULL,
    rubric_version              TEXT NOT NULL,
    taxonomy_version            TEXT NOT NULL,
    trajectory_policy_version   TEXT NOT NULL,
    created_at                  TEXT NOT NULL,
    -- Deferred: a supersession names an alert saved later in the same
    -- transaction, and the reference must hold by commit.
    superseded_by               TEXT REFERENCES alerts (id) DEFERRABLE INITIALLY DEFERRED,

    CONSTRAINT alerts_status_valid CHECK (status IN ('raised', 'indeterminate')),
    CONSTRAINT alerts_severity_valid
        CHECK (severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')),
    -- An indeterminate outcome has no severity, and a raised alert always has one.
    CONSTRAINT alerts_severity_iff_raised
        CHECK ((severity IS NULL) = (status = 'indeterminate')),
    -- §4.7: an alert that cannot say what it was derived from is invalid.
    -- cardinality, not array_length: array_length of an empty array is NULL,
    -- and a CHECK that evaluates to NULL passes.
    CONSTRAINT alerts_cite_evidence CHECK (cardinality(evidence_turn_ids) >= 1),
    CONSTRAINT alerts_name_their_scores
        CHECK (cardinality(triggering_signal_score_ids) >= 1),
    CONSTRAINT alerts_name_their_assessments
        CHECK (cardinality(contributing_assessment_ids) >= 1),
    CONSTRAINT alerts_not_self_superseded CHECK (superseded_by IS NULL OR superseded_by <> id),
    -- §13: re-running evaluation must not duplicate an alert.
    CONSTRAINT alerts_one_per_evaluation
        UNIQUE (trajectory_update_id, rule_set_version, rule_id)
);

-- One active alert per session and rule; a later decision supersedes it.
CREATE UNIQUE INDEX IF NOT EXISTS alerts_one_active_per_rule
    ON alerts (session_id, rule_id) WHERE superseded_by IS NULL;

-- Seed pipeline, S1 Collect (SEED_PIPELINE_PLAN.md §3.1). DS-14 snapshots and
-- DS-15 seeds: generation inputs, never labels.
CREATE TABLE IF NOT EXISTS seed_query_log (
    id                   TEXT PRIMARY KEY,
    source               TEXT NOT NULL,
    query_id             TEXT NOT NULL,
    query_text           TEXT NOT NULL,
    query_config_version TEXT NOT NULL,
    executed_at          TEXT NOT NULL,
    result_ids           TEXT[] NOT NULL
);

CREATE TABLE IF NOT EXISTS source_documents (
    id               TEXT PRIMARY KEY,
    -- A snapshot is identified by exactly what it contains.
    content_hash     TEXT NOT NULL UNIQUE,
    source_type      TEXT NOT NULL,
    source_url       TEXT NOT NULL,
    title            TEXT NOT NULL,
    text             TEXT NOT NULL,
    retrieved_at     TEXT NOT NULL,
    fetcher_version  TEXT NOT NULL,
    external_id      TEXT,
    publication_date TEXT,
    query_log_id     TEXT REFERENCES seed_query_log (id),
    status           TEXT NOT NULL,
    failure_code     TEXT,
    status_detail    TEXT,
    processed_prompt_version TEXT,
    processed_model_version  TEXT,

    CONSTRAINT documents_hash_is_sha256 CHECK (length(content_hash) = 64),
    CONSTRAINT documents_status_valid CHECK (status IN
        ('SNAPSHOTTED', 'SCREENED', 'EXTRACTED', 'BLOCKED_SEALED', 'DELAYED', 'FAILED')),
    CONSTRAINT documents_failure_code_iff_failed
        CHECK ((failure_code IS NOT NULL) = (status = 'FAILED'))
);

CREATE INDEX IF NOT EXISTS documents_unfinished ON source_documents (status, retrieved_at);

-- Immutable, keyed by everything that determines a reply. Shared by the team
-- so identical inputs give identical seeds without calling the model again.
CREATE TABLE IF NOT EXISTS extraction_cache (
    content_hash   TEXT NOT NULL REFERENCES source_documents (content_hash),
    prompt_version TEXT NOT NULL,
    model_version  TEXT NOT NULL,
    provider       TEXT NOT NULL,
    model          TEXT NOT NULL,
    reply_text     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (content_hash, prompt_version, model_version)
);

CREATE TABLE IF NOT EXISTS seeds (
    id                           TEXT PRIMARY KEY,
    seed_version                 INTEGER NOT NULL,
    account_kind                 TEXT NOT NULL,
    source_document_id           TEXT NOT NULL REFERENCES source_documents (id),
    content_hash                 TEXT NOT NULL,
    source_url                   TEXT NOT NULL,
    source_type                  TEXT NOT NULL,
    credibility_tier             TEXT NOT NULL,
    retrieved_at                 TEXT NOT NULL,
    theme_family                 TEXT,
    raw_theme_terms              TEXT[] NOT NULL,
    arc_summary                  TEXT NOT NULL,
    reported_phase_progression   TEXT[] NOT NULL,
    explicitness_candidate       TEXT NOT NULL,
    harm_type_candidate          TEXT,
    companion_behaviour_reported TEXT[] NOT NULL,
    extraction_provider          TEXT NOT NULL,
    extraction_model             TEXT NOT NULL,
    extraction_model_version     TEXT NOT NULL,
    extraction_prompt_version    TEXT NOT NULL,
    vocabulary_version           TEXT NOT NULL,
    credibility_tier_version     TEXT NOT NULL,
    created_at                   TEXT NOT NULL,
    publication_date             TEXT,
    ordinal                      INTEGER NOT NULL
);

-- D-43: age is no longer extracted. Removes the columns (and their CHECKs) from
-- databases created before the change.
ALTER TABLE seeds DROP COLUMN IF EXISTS stated_age;
ALTER TABLE seeds DROP COLUMN IF EXISTS age_evidence;

-- D-44: account kind. Databases created before it get the column without NOT
-- NULL (existing rows have no kind); the seed validator requires it on write.
ALTER TABLE seeds ADD COLUMN IF NOT EXISTS account_kind TEXT;

-- D-45: a document may be extracted more than once (new prompt or model), and
-- every extraction's seeds are kept. Positions are unique per extraction, and
-- the document records which extraction is current.
ALTER TABLE source_documents ADD COLUMN IF NOT EXISTS processed_prompt_version TEXT;
ALTER TABLE source_documents ADD COLUMN IF NOT EXISTS processed_model_version TEXT;
ALTER TABLE seeds DROP CONSTRAINT IF EXISTS seeds_one_position_per_document;
CREATE UNIQUE INDEX IF NOT EXISTS seeds_one_position_per_extraction
    ON seeds (source_document_id, extraction_prompt_version, extraction_model_version, ordinal);

-- S2 Filter (D-27, D-48). One check per seed, screen version and manifest; it
-- stores reason codes and the manifest's hash, never sealed content.
CREATE TABLE IF NOT EXISTS seed_overlap_checks (
    id              TEXT PRIMARY KEY,
    seed_id         TEXT NOT NULL REFERENCES seeds (id),
    result          TEXT NOT NULL,
    reasons         TEXT[] NOT NULL,
    screen_version  TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    checked_at      TEXT NOT NULL,

    CONSTRAINT overlap_result_valid CHECK (result IN ('clear', 'flagged', 'blocked')),
    CONSTRAINT overlap_clear_iff_no_reasons
        CHECK ((result = 'clear') = (cardinality(reasons) = 0)),
    CONSTRAINT overlap_manifest_is_sha256 CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT overlap_one_check_per_screen UNIQUE (seed_id, screen_version, manifest_sha256)
);

-- Human keep/exclude decisions on flagged seeds. Append-only: a correction
-- supersedes the latest review. Storage keeps each check's history one
-- unbroken chain: one first review per check, no review superseded twice, and
-- a correction must belong to the same check as the review it supersedes.
CREATE TABLE IF NOT EXISTS seed_flag_reviews (
    id               TEXT PRIMARY KEY,
    overlap_check_id TEXT NOT NULL REFERENCES seed_overlap_checks (id),
    decision         TEXT NOT NULL,
    reason           TEXT NOT NULL,
    actor_id         TEXT NOT NULL,
    recorded_at      TEXT NOT NULL,
    supersedes       TEXT UNIQUE,

    CONSTRAINT flag_review_decision_valid CHECK (decision IN ('keep', 'exclude')),
    CONSTRAINT flag_review_has_reason CHECK (btrim(reason) <> ''),
    CONSTRAINT flag_review_has_actor CHECK (btrim(actor_id) <> ''),
    CONSTRAINT flag_review_id_per_check UNIQUE (id, overlap_check_id),
    CONSTRAINT flag_review_supersedes_same_check FOREIGN KEY (supersedes, overlap_check_id)
        REFERENCES seed_flag_reviews (id, overlap_check_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS flag_reviews_one_first_review
    ON seed_flag_reviews (overlap_check_id) WHERE supersedes IS NULL;

-- S3 Choose (D-34, D-35, D-49). Selections are immutable snapshots in one
-- unbroken chain: versions are unique, no selection is superseded twice, and
-- only version 1 supersedes nothing.
CREATE TABLE IF NOT EXISTS seed_selections (
    id                       TEXT PRIMARY KEY,
    selection_version        INTEGER NOT NULL UNIQUE,
    actor_id                 TEXT NOT NULL,
    created_at               TEXT NOT NULL,
    coverage_targets_version TEXT NOT NULL,
    -- An array of cells: JSONB keeps array order, not object key order (D-16).
    coverage                 JSONB NOT NULL,
    gaps                     TEXT[] NOT NULL,
    pattern_count            INTEGER NOT NULL,
    supersedes               TEXT UNIQUE REFERENCES seed_selections (id),

    CONSTRAINT selection_version_positive CHECK (selection_version >= 1),
    CONSTRAINT selection_first_supersedes_nothing
        CHECK ((supersedes IS NULL) = (selection_version = 1)),
    CONSTRAINT selection_has_actor CHECK (btrim(actor_id) <> ''),
    CONSTRAINT selection_pattern_count_valid CHECK (pattern_count >= 0)
);

-- One split per seed, for ever (D-34): a seed dropped from a later selection
-- keeps it, and every entry must agree with it.
CREATE TABLE IF NOT EXISTS seed_splits (
    seed_id     TEXT PRIMARY KEY REFERENCES seeds (id),
    split       TEXT NOT NULL,
    assigned_in TEXT NOT NULL REFERENCES seed_selections (id),

    CONSTRAINT split_valid CHECK (split IN ('gold', 'silver', 'development')),
    CONSTRAINT split_per_seed UNIQUE (seed_id, split)
);

CREATE TABLE IF NOT EXISTS seed_selection_entries (
    selection_id TEXT NOT NULL REFERENCES seed_selections (id),
    seed_id      TEXT NOT NULL,
    seed_version INTEGER NOT NULL,
    split        TEXT NOT NULL,
    ordinal      INTEGER NOT NULL,

    PRIMARY KEY (selection_id, seed_id),
    CONSTRAINT entry_matches_seed_split FOREIGN KEY (seed_id, split)
        REFERENCES seed_splits (seed_id, split)
);

-- Who has been shown a seed's content. Blind annotation of a seed's
-- conversations excludes everyone listed here (D-34).
CREATE TABLE IF NOT EXISTS seed_exposure (
    seed_id     TEXT NOT NULL REFERENCES seeds (id),
    actor_id    TEXT NOT NULL,
    activity    TEXT NOT NULL,
    recorded_at TEXT NOT NULL,

    PRIMARY KEY (seed_id, actor_id, activity),
    CONSTRAINT exposure_activity_valid CHECK (activity IN ('flag_review', 'choose')),
    CONSTRAINT exposure_has_actor CHECK (btrim(actor_id) <> '')
);
