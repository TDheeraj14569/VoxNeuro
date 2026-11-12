-- 003_composite_foreign_keys_and_retention_defaults.sql
-- Milestone 5: Enforce database-level composite foreign-key constraints and default non-retention

-- 1. Ensure composite unique constraints exist on participants
CREATE UNIQUE INDEX IF NOT EXISTS uq_participants_composite ON participants (participant_id, study_id);

-- 2. Migrate existing consents: conservatively update historical default retention to non-retention
UPDATE consents
SET permission_to_retain_derived_features = 0
WHERE source_document_reference NOT LIKE '%EXPLICIT_AFFIRMATIVE_RETENTION_VERIFIED%';

-- 3. Rebuild consents table to enforce composite FK and default 0
CREATE TABLE IF NOT EXISTS consents_v3 (
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

INSERT OR IGNORE INTO consents_v3 (
    consent_record_id, participant_id, study_id, consent_form_version, consent_date,
    scope_of_permission_json, permitted_recording_tasks_json, permitted_research_uses_json,
    permission_to_retain_derived_features, permission_to_retain_audio, withdrawal_status,
    revocation_date, source_document_reference
)
SELECT
    consent_record_id, participant_id, study_id, consent_form_version, consent_date,
    scope_of_permission_json, permitted_recording_tasks_json, permitted_research_uses_json,
    permission_to_retain_derived_features, permission_to_retain_audio, withdrawal_status,
    revocation_date, source_document_reference
FROM consents;

DROP TABLE IF EXISTS consents;
ALTER TABLE consents_v3 RENAME TO consents;

-- 4. Rebuild sessions table to enforce composite FKs to participants and consents
CREATE TABLE IF NOT EXISTS sessions_v3 (
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

INSERT OR IGNORE INTO sessions_v3 (
    session_id, study_id, protocol_version, participant_id,
    visit_index, visit_label, acquisition_domain_id, capture_origin,
    recording_timestamp, consent_reference, device_metadata_json,
    task_completion_states_json, qc_results_json, processing_receipt_sha256,
    missing_task_reasons_json, overall_session_status
)
SELECT
    session_id, study_id, protocol_version, participant_id,
    visit_index, visit_label, acquisition_domain_id, capture_origin,
    recording_timestamp, consent_reference, device_metadata_json,
    task_completion_states_json, qc_results_json, processing_receipt_sha256,
    missing_task_reasons_json, overall_session_status
FROM sessions;

DROP TABLE IF EXISTS sessions;
ALTER TABLE sessions_v3 RENAME TO sessions;

-- 5. Create supporting indexes
CREATE INDEX IF NOT EXISTS idx_consents_participant_study_v3 ON consents (participant_id, study_id, withdrawal_status);
CREATE INDEX IF NOT EXISTS idx_sessions_participant_study_v3 ON sessions (participant_id, study_id);
