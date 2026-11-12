"""Tests verifying SQLite database-level composite foreign-key constraints and bypass rejections."""

from __future__ import annotations

import sqlite3

import pytest

from voxneuro.study.database import get_connection, run_migrations


@pytest.fixture
def clean_db(tmp_path):
    """Initialize a fresh database with all migrations applied."""
    db_file = tmp_path / "test_constraints.db"
    run_migrations(db_file)
    conn = get_connection(db_file)
    try:
        # Populate base protocol and two distinct studies
        conn.execute(
            """
            INSERT INTO protocols (protocol_id, protocol_version, tasks_json, created_at)
            VALUES ('proto_v1', 'v1', '["sustained_vowel"]', '2026-11-12T00:00:00Z');
            """
        )
        conn.execute(
            """
            INSERT INTO studies (
                study_id, study_name, study_description, protocol_id, protocol_version,
                dataset_id, dataset_version, created_at, updated_at,
                consent_requirements_json, data_retention_policy_id, analysis_configuration_id
            ) VALUES
            ('study_alpha', 'Study Alpha', 'First study', 'proto_v1', 'v1', 'ds_alpha', 'v1',
             '2026-11-12T00:00:00Z', '2026-11-12T00:00:00Z', '[]', 'ret_v1', 'cfg_v1'),
            ('study_beta', 'Study Beta', 'Second study', 'proto_v1', 'v1', 'ds_beta', 'v1',
             '2026-11-12T00:00:00Z', '2026-11-12T00:00:00Z', '[]', 'ret_v1', 'cfg_v1');
            """
        )
        # Register participant P_ALPHA in study_alpha and P_BETA in study_beta
        conn.execute(
            """
            INSERT INTO participants (
                participant_id, study_id, enrollment_status, consent_status,
                consent_version, enrollment_timestamp, allowed_research_scopes_json
            ) VALUES
            ('P_ALPHA', 'study_alpha', 'enrolled', 'consented', 'v1',
             '2026-11-12T00:00:00Z', '["voice_analysis"]'),
            ('P_BETA', 'study_beta', 'enrolled', 'consented', 'v1',
             '2026-11-12T00:00:00Z', '["voice_analysis"]');
            """
        )
        # Record valid consent for P_ALPHA in study_alpha
        conn.execute(
            """
            INSERT INTO consents (
                consent_record_id, participant_id, study_id, consent_form_version,
                consent_date, scope_of_permission_json, permitted_recording_tasks_json,
                permitted_research_uses_json, permission_to_retain_derived_features,
                permission_to_retain_audio, withdrawal_status, source_document_reference
            ) VALUES
            ('c_alpha_valid', 'P_ALPHA', 'study_alpha', 'v1', '2026-11-12T00:00:00Z',
             '["voice_analysis"]', '["sustained_vowel"]', '["biomarker_research"]',
             0, 0, 0, 'DOC-01'),
            ('c_beta_valid', 'P_BETA', 'study_beta', 'v1', '2026-11-12T00:00:00Z',
             '["voice_analysis"]', '["sustained_vowel"]', '["biomarker_research"]',
             0, 0, 0, 'DOC-02');
            """
        )
        conn.commit()
        yield conn
    finally:
        conn.close()


def test_db_rejects_cross_study_consent_insert(clean_db):
    """Direct SQL insert combining valid participant of Study A with Study B must fail."""
    # P_ALPHA exists in study_alpha, attempting to insert consent with study_beta
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        clean_db.execute(
            """
            INSERT INTO consents (
                consent_record_id, participant_id, study_id, consent_form_version,
                consent_date, scope_of_permission_json, permitted_recording_tasks_json,
                permitted_research_uses_json, source_document_reference
            ) VALUES ('c_invalid', 'P_ALPHA', 'study_beta', 'v1',
                      '2026-11-12T00:00:00Z', '[]', '[]', '[]', 'DOC');
            """
        )


def test_db_rejects_cross_study_session_insert(clean_db):
    """Direct SQL insert combining participant of Study A with Study B in session must fail."""
    # P_ALPHA is enrolled in study_alpha, attempting to create session in study_beta
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        clean_db.execute(
            """
            INSERT INTO sessions (
                session_id, study_id, protocol_version, participant_id,
                visit_index, visit_label, acquisition_domain_id, capture_origin,
                recording_timestamp, consent_reference
            ) VALUES (
                's_invalid_1', 'study_beta', 'v1', 'P_ALPHA',
                1, 'Baseline', 'uams_telephone', 'telephone',
                '2026-11-12T00:00:00Z', 'c_alpha_valid'
            );
            """
        )


def test_db_rejects_session_referencing_different_participant_consent(clean_db):
    """Direct SQL session for P_ALPHA referencing P_BETA's consent must fail composite FK."""
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        clean_db.execute(
            """
            INSERT INTO sessions (
                session_id, study_id, protocol_version, participant_id,
                visit_index, visit_label, acquisition_domain_id, capture_origin,
                recording_timestamp, consent_reference
            ) VALUES (
                's_invalid_2', 'study_alpha', 'v1', 'P_ALPHA',
                1, 'Baseline', 'uams_telephone', 'telephone',
                '2026-11-12T00:00:00Z', 'c_beta_valid'
            );
            """
        )


def test_db_rejects_session_referencing_nonexistent_consent(clean_db):
    """Direct SQL session referencing a phantom consent reference must fail composite FK."""
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        clean_db.execute(
            """
            INSERT INTO sessions (
                session_id, study_id, protocol_version, participant_id,
                visit_index, visit_label, acquisition_domain_id, capture_origin,
                recording_timestamp, consent_reference
            ) VALUES (
                's_invalid_3', 'study_alpha', 'v1', 'P_ALPHA',
                1, 'Baseline', 'uams_telephone', 'telephone',
                '2026-11-12T00:00:00Z', 'nonexistent_consent'
            );
            """
        )


def test_db_accepts_valid_composite_session(clean_db):
    """Direct SQL session with valid composite participant, study, and consent succeeds."""
    clean_db.execute(
        """
        INSERT INTO sessions (
            session_id, study_id, protocol_version, participant_id,
            visit_index, visit_label, acquisition_domain_id, capture_origin,
            recording_timestamp, consent_reference
        ) VALUES (
            's_valid_alpha', 'study_alpha', 'v1', 'P_ALPHA',
            1, 'Baseline', 'uams_telephone', 'telephone',
            '2026-11-12T00:00:00Z', 'c_alpha_valid'
        );
        """
    )
    clean_db.commit()
    cursor = clean_db.execute("SELECT session_id FROM sessions WHERE session_id = 's_valid_alpha';")
    assert cursor.fetchone()["session_id"] == "s_valid_alpha"


def test_migration_atomic_rollback_on_syntax_error(tmp_path):
    """Ensure that a migration containing a syntax error does not commit partial statements."""
    from voxneuro.study.database import get_applied_migrations, run_migrations

    db_file = tmp_path / "rollback_test.db"
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()

    # Step 1: Valid initial migration
    (mig_dir / "001_first.sql").write_text(
        "CREATE TABLE test_tab (id INTEGER PRIMARY KEY, name TEXT);",
        encoding="utf-8",
    )
    applied = run_migrations(db_file, migrations_dir=mig_dir)
    assert "001_first.sql" in applied

    # Step 2: Second migration that creates table2 then encounters syntax error
    (mig_dir / "002_broken.sql").write_text(
        """
        CREATE TABLE test_tab_2 (id INTEGER PRIMARY KEY);
        THIS IS INVALID SQL SYNTAX ERROR;
        """,
        encoding="utf-8",
    )
    with pytest.raises(sqlite3.OperationalError):
        run_migrations(db_file, migrations_dir=mig_dir)

    # Verify atomic rollback: test_tab_2 must NOT exist, and version 2 must NOT be recorded
    conn = get_connection(db_file)
    try:
        assert 2 not in get_applied_migrations(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='test_tab_2';"
        )
        assert cursor.fetchone() is None, "test_tab_2 should have been rolled back!"
    finally:
        conn.close()
