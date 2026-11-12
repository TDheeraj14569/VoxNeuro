-- 006_m6_platform_and_ml_registry.sql
-- Milestone 6: User authentication, RBAC, ML training runs, model registry, domain approvals,
-- prediction records (opt-in retention only), and abstention telemetry.

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'participant' CHECK(role IN ('participant', 'researcher', 'ml_admin', 'admin')),
    is_active INTEGER NOT NULL DEFAULT 1,
    participant_id TEXT,
    study_id TEXT,
    prediction_retention_opt_in INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT,
    FOREIGN KEY (participant_id, study_id) REFERENCES participants (participant_id, study_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS user_sessions (
    session_token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    reset_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS training_datasets (
    dataset_record_id TEXT PRIMARY KEY,
    dataset_name TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    participant_count INTEGER NOT NULL,
    recording_count INTEGER NOT NULL,
    authorization_status TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (dataset_name, dataset_version, dataset_sha256)
);

CREATE TABLE IF NOT EXISTS training_runs (
    run_id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    project_code_fingerprint TEXT NOT NULL,
    dataset_ids_json TEXT NOT NULL,
    config_json TEXT NOT NULL,
    random_seed INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_by_user_id TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    receipt_sha256 TEXT,
    FOREIGN KEY (created_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_id TEXT PRIMARY KEY,
    model_version TEXT NOT NULL,
    model_family TEXT NOT NULL,
    feature_schema_version TEXT NOT NULL,
    feature_schema_fingerprint TEXT NOT NULL,
    training_run_id TEXT,
    artifact_path TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(
        lifecycle_state IN (
            'TRAINING',
            'TRAINED',
            'RESEARCH_EVALUATED',
            'EXTERNAL_VALIDATION_PENDING',
            'RESEARCH_INFERENCE_APPROVED',
            'REJECTED',
            'RETIRED'
        )
    ),
    calibration_status TEXT NOT NULL DEFAULT 'UNCALIBRATED',
    clinical_claim_status TEXT NOT NULL DEFAULT 'UNAPPROVED_RESEARCH_ONLY',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (training_run_id) REFERENCES training_runs (run_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS model_evaluations (
    evaluation_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    evaluation_scope TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    n_participants INTEGER NOT NULL,
    roc_auc REAL,
    pr_auc REAL,
    balanced_accuracy REAL,
    sensitivity REAL,
    specificity REAL,
    brier_score REAL,
    ece REAL,
    metrics_json TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (model_id) REFERENCES model_versions (model_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_domain_approvals (
    approval_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    domain_id TEXT NOT NULL,
    approval_state TEXT NOT NULL CHECK(approval_state IN ('PENDING', 'APPROVED', 'REJECTED', 'REVOKED')),
    evidence_sha256 TEXT NOT NULL DEFAULT '',
    approved_by_user_id TEXT,
    approved_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (model_id) REFERENCES model_versions (model_id) ON DELETE CASCADE,
    FOREIGN KEY (approved_by_user_id) REFERENCES users (user_id) ON DELETE SET NULL,
    UNIQUE (model_id, domain_id)
);

CREATE TABLE IF NOT EXISTS prediction_records (
    prediction_id TEXT PRIMARY KEY,
    session_id TEXT,
    participant_id TEXT,
    user_id TEXT,
    model_id TEXT,
    model_version TEXT NOT NULL,
    model_checksum TEXT NOT NULL,
    acquisition_domain_id TEXT NOT NULL,
    capture_origin TEXT NOT NULL,
    research_score REAL,
    research_classification TEXT,
    calibration_status TEXT NOT NULL,
    uncertainty_json TEXT NOT NULL DEFAULT '{}',
    abstained INTEGER NOT NULL DEFAULT 1,
    abstention_reason TEXT,
    retention_permitted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participants (participant_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES model_versions (model_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS abstention_events (
    abstention_id TEXT PRIMARY KEY,
    session_id TEXT,
    model_id TEXT,
    reason_code TEXT NOT NULL,
    reason_detail TEXT NOT NULL,
    acquisition_domain_id TEXT NOT NULL,
    capture_origin TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_lifecycle_events (
    event_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    actor_user_id TEXT,
    actor_role TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (model_id) REFERENCES model_versions (model_id) ON DELETE CASCADE,
    FOREIGN KEY (actor_user_id) REFERENCES users (user_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_state ON model_versions (lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_prediction_records_participant ON prediction_records (participant_id);
CREATE INDEX IF NOT EXISTS idx_prediction_records_user ON prediction_records (user_id);
CREATE INDEX IF NOT EXISTS idx_abstention_events_created ON abstention_events (created_at);
CREATE INDEX IF NOT EXISTS idx_model_lifecycle_model ON model_lifecycle_events (model_id);
