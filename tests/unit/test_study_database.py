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


def test_migrations_directory_and_file_edge_cases(tmp_path: Path):
    from voxneuro.study.database import get_applied_migrations

    # 1. Non-existent migrations directory
    non_existent = tmp_path / "no_such_dir"
    with pytest.raises(FileNotFoundError, match="Migrations directory not found"):
        run_migrations(tmp_path / "test.db", migrations_dir=non_existent)

    # 2. Empty migrations directory
    empty_dir = tmp_path / "empty_mig"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError, match="No SQL migration files found"):
        run_migrations(tmp_path / "test.db", migrations_dir=empty_dir)

    # 3. Migration file with invalid prefix is skipped
    (empty_dir / "invalid_prefix.sql").write_text("SELECT 1;", encoding="utf-8")
    (empty_dir / "001_valid.sql").write_text(
        "CREATE TABLE t1 (id INT PRIMARY KEY); INSERT INTO t1 VALUES (1)", encoding="utf-8"
    )
    db_file = tmp_path / "prefix_test.db"
    applied = run_migrations(db_file, migrations_dir=empty_dir)
    assert len(applied) == 1
    assert "001_valid.sql" in applied

    # 4. get_applied_migrations on unmigrated db returns empty set
    raw_conn = sqlite3.connect(tmp_path / "raw.db")
    raw_conn.row_factory = sqlite3.Row
    try:
        assert get_applied_migrations(raw_conn) == set()
    finally:
        raw_conn.close()


def test_database_migration_checksum_immutability(tmp_path: Path):
    """Verify that tampering with an already-applied SQL migration file raises a RuntimeError."""
    mig_dir = tmp_path / "immutable_migs"
    mig_dir.mkdir()
    mig_file = mig_dir / "001_initial.sql"
    mig_file.write_text("CREATE TABLE test_imm (id INT PRIMARY KEY);", encoding="utf-8")

    db_file = tmp_path / "imm_test.db"
    applied = run_migrations(db_file, migrations_dir=mig_dir)
    assert len(applied) == 1

    # Tampering with the already-applied migration file must fail closed
    mig_file.write_text(
        "CREATE TABLE test_imm (id INT PRIMARY KEY, tampered INT);",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        run_migrations(db_file, migrations_dir=mig_dir)
