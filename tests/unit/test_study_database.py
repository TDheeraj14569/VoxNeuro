"""Unit tests for SQLite database connection, migrations, foreign keys, and transactions."""

import sqlite3
from pathlib import Path

import pytest

from voxneuro.study.database import (
    check_schema_integrity,
    get_connection,
    run_migrations,
    transaction,
)


def test_database_fresh_creation_and_migration(tmp_path: Path):
    db_file = tmp_path / "research.db"
    applied = run_migrations(db_file)
    assert len(applied) >= 1
    assert "001_initial_study_schema.sql" in applied

    status = check_schema_integrity(db_file)
    assert status["clean"] is True
    assert "studies" in status["tables"]
    assert "participants" in status["tables"]
    assert "sessions" in status["tables"]
    assert "task_recordings" in status["tables"]
    assert "derived_features" in status["tables"]
    assert "tombstones" in status["tables"]


def test_database_migrations_idempotency(tmp_path: Path):
    db_file = tmp_path / "research.db"
    applied1 = run_migrations(db_file)
    assert len(applied1) >= 1

    # Second migration run should apply 0 additional migrations
    applied2 = run_migrations(db_file)
    assert applied2 == []


def test_database_foreign_key_enforcement(tmp_path: Path):
    db_file = tmp_path / "research.db"
    run_migrations(db_file)

    conn = get_connection(db_file)
    try:
        # Attempt to insert a participant for a non-existent study
        with pytest.raises(sqlite3.IntegrityError):
            with transaction(conn):
                conn.execute(
                    """
                    INSERT INTO participants (
                        participant_id, study_id, enrollment_status, consent_status,
                        consent_version, enrollment_timestamp, site_id,
                        allowed_research_scopes_json, participant_metadata_status
                    ) VALUES ('PT-01', 'non_existent_study', 'enrolled', 'consented',
                             'v1.0', '2026-11-12T12:00:00Z', 'site_01', '[]', 'VERIFIED');
                    """
                )
    finally:
        conn.close()


def test_database_transaction_rollback_on_error(tmp_path: Path):
    db_file = tmp_path / "research.db"
    run_migrations(db_file)

    conn = get_connection(db_file)
    try:
        # Register a protocol first
        conn.execute(
            """
            INSERT INTO protocols (
                protocol_id, protocol_version, tasks_json, visits_expected,
                minimum_interval_days, instructions, created_at
            ) VALUES ('proto_01', '1.0', '[]', 1, 0, '', '2026-11-12T12:00:00Z');
            """
        )
        conn.commit()

        # Execute transaction that fails mid-way
        with pytest.raises(ValueError, match="Intentional transaction test error"):
            with transaction(conn):
                conn.execute(
                    """
                    INSERT INTO studies (
                        study_id, study_name, study_description, protocol_id,
                        protocol_version, study_status, research_site_id, dataset_id,
                        dataset_version, created_at, updated_at, study_owner_role,
                        consent_requirements_json, data_retention_policy_id,
                        analysis_configuration_id
                    ) VALUES ('study_rollback_test', 'Test', 'Desc', 'proto_01',
                             '1.0', 'draft', 'site', 'dataset', 'v1',
                             '2026-11-12T12:00:00Z', '2026-11-12T12:00:00Z', 'PI',
                             '[]', 'policy', 'config');
                    """
                )
                raise ValueError("Intentional transaction test error")

        # Verify that study was not committed
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM studies WHERE study_id = 'study_rollback_test';"
        )
        assert cursor.fetchone()["count"] == 0
    finally:
        conn.close()
