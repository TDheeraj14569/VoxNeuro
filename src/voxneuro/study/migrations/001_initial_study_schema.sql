-- 001_initial_study_schema.sql
-- Milestone 5 initial relational database schema for research study operations

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS protocols (
    protocol_id TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    tasks_json TEXT NOT NULL,
    visits_expected INTEGER NOT NULL DEFAULT 1,
    minimum_interval_days INTEGER NOT NULL DEFAULT 0,
    instructions TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (protocol_id, protocol_version)
);

CREATE TABLE IF NOT EXISTS studies (
    study_id TEXT PRIMARY KEY,
    study_name TEXT NOT NULL,
    study_description TEXT NOT NULL,
    protocol_id TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    study_status TEXT NOT NULL DEFAULT 'draft',
    research_site_id TEXT NOT NULL DEFAULT 'primary_site',
    dataset_id TEXT NOT NULL,
    dataset_version TEXT NOT NULL DEFAULT 'v1',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    study_owner_role TEXT NOT NULL DEFAULT 'Principal Investigator',
    consent_requirements_json TEXT NOT NULL,
    data_retention_policy_id TEXT NOT NULL,
    analysis_configuration_id TEXT NOT NULL,
    FOREIGN KEY (protocol_id, protocol_version) REFERENCES protocols (protocol_id, protocol_version)
);

CREATE TABLE IF NOT EXISTS participants (
    participant_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    enrollment_status TEXT NOT NULL DEFAULT 'enrolled',
    consent_status TEXT NOT NULL DEFAULT 'pending',
    consent_version TEXT NOT NULL DEFAULT 'none',
    enrollment_timestamp TEXT NOT NULL,
    withdrawal_timestamp TEXT,
    site_id TEXT NOT NULL DEFAULT 'primary_site',
    allowed_research_scopes_json TEXT NOT NULL,
    participant_metadata_status TEXT NOT NULL DEFAULT 'PSEUDONYMOUS_VERIFIED',
    FOREIGN KEY (study_id) REFERENCES studies (study_id) ON DELETE CASCADE,
    UNIQUE (participant_id, study_id)
);

CREATE TABLE IF NOT EXISTS consents (
    consent_record_id TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL,
    study_id TEXT NOT NULL,
    consent_form_version TEXT NOT NULL,
    consent_date TEXT NOT NULL,
    scope_of_permission_json TEXT NOT NULL,
    permitted_recording_tasks_json TEXT NOT NULL,
    permitted_research_uses_json TEXT NOT NULL,
    permission_to_retain_derived_features INTEGER NOT NULL DEFAULT 0,
    permission_to_retain_audio INTEGER NOT NULL DEFAULT 0,
    withdrawal_status INTEGER NOT NULL DEFAULT 0,
    revocation_date TEXT,
    source_document_reference TEXT NOT NULL,
    FOREIGN KEY (participant_id, study_id) REFERENCES participants (participant_id, study_id) ON DELETE CASCADE,
    FOREIGN KEY (study_id) REFERENCES studies (study_id) ON DELETE CASCADE,
    UNIQUE (consent_record_id, participant_id, study_id)
);

CREATE TABLE IF NOT EXISTS dataset_access (
    dataset_id TEXT PRIMARY KEY,
    dataset_version TEXT NOT NULL,
    dataset_owner TEXT NOT NULL,
    license_type TEXT NOT NULL,
    access_approval_state TEXT NOT NULL DEFAULT 'PENDING',
    dua_state TEXT NOT NULL DEFAULT 'PENDING',
    permitted_tasks_json TEXT NOT NULL,
    permitted_data_processing_operations_json TEXT NOT NULL,
    storage_restrictions TEXT NOT NULL,
    publication_restrictions TEXT NOT NULL,
    expiration_date TEXT,
    source_documentation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    visit_index INTEGER NOT NULL DEFAULT 1,
    visit_label TEXT NOT NULL DEFAULT 'Baseline',
    acquisition_domain_id TEXT NOT NULL,
    capture_origin TEXT NOT NULL,
    recording_timestamp TEXT NOT NULL,
    consent_reference TEXT NOT NULL,
    device_metadata_json TEXT NOT NULL DEFAULT '{}',
    task_completion_states_json TEXT NOT NULL DEFAULT '{}',
    qc_results_json TEXT NOT NULL DEFAULT '{}',
    processing_receipt_sha256 TEXT,
    missing_task_reasons_json TEXT NOT NULL DEFAULT '{}',
    overall_session_status TEXT NOT NULL DEFAULT 'SCHEDULED',
    FOREIGN KEY (study_id) REFERENCES studies (study_id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id, study_id) REFERENCES participants (participant_id, study_id) ON DELETE CASCADE,
    FOREIGN KEY (consent_reference, participant_id, study_id) REFERENCES consents (consent_record_id, participant_id, study_id) ON DELETE CASCADE,
    UNIQUE (participant_id, visit_index)
);

CREATE TABLE IF NOT EXISTS task_recordings (
    task_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    task_status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    audio_duration_seconds REAL NOT NULL DEFAULT 0.0,
    quality_passed INTEGER NOT NULL DEFAULT 0,
    rejection_reason TEXT,
    feature_schema_version TEXT,
    feature_schema_fingerprint TEXT,
    derived_feature_count INTEGER NOT NULL DEFAULT 0,
    qc_metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE,
    UNIQUE (session_id, task_type)
);

CREATE TABLE IF NOT EXISTS derived_features (
    feature_record_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    participant_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    features_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES task_recordings (task_id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE,
    FOREIGN KEY (participant_id) REFERENCES participants (participant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS processing_runs (
    run_id TEXT PRIMARY KEY,
    study_id TEXT NOT NULL,
    session_ids_json TEXT NOT NULL,
    processing_timestamp TEXT NOT NULL,
    application_version TEXT NOT NULL,
    project_code_fingerprint TEXT NOT NULL,
    python_version TEXT NOT NULL,
    dependency_lockfile_fingerprint TEXT NOT NULL,
    task_schema_fingerprints_json TEXT NOT NULL,
    audio_config_fingerprint TEXT NOT NULL,
    feature_config_fingerprint TEXT NOT NULL,
    domain_metadata_fingerprint TEXT NOT NULL,
    input_file_checksum TEXT,
    feature_table_checksum TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    exclusion_summary_json TEXT NOT NULL,
    error_summary_json TEXT NOT NULL,
    output_artifact_checksums_json TEXT NOT NULL,
    receipt_sha256 TEXT NOT NULL,
    FOREIGN KEY (study_id) REFERENCES studies (study_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_utc TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor_role TEXT NOT NULL DEFAULT 'researcher',
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tombstones (
    tombstone_id TEXT PRIMARY KEY,
    timestamp_utc TEXT NOT NULL,
    participant_pseudonym_hash TEXT NOT NULL,
    study_id TEXT NOT NULL,
    deletion_reason TEXT NOT NULL,
    records_deleted_count INTEGER NOT NULL,
    policy_reference TEXT NOT NULL,
    key_id TEXT NOT NULL DEFAULT 'voxneuro-key-v1'
);
