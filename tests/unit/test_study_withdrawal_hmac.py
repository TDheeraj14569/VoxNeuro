"""Regression tests for HMAC-authenticated participant withdrawal and transactional rollback."""

from __future__ import annotations

import hmac
from pathlib import Path
from unittest.mock import patch

import pytest

from voxneuro.study.consent import record_consent, register_dataset_access
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.participant import get_participant, register_participant
from voxneuro.study.registry import create_protocol, create_study
from voxneuro.study.schema import (
    ConsentRecord,
    DatasetAccessRecord,
    Participant,
    ProtocolDefinition,
    ResearchSession,
    Study,
    TaskRecording,
    utc_now_iso,
)
from voxneuro.study.session import create_session, record_task_recording
from voxneuro.study.withdrawal import compute_withdrawal_tombstone_hash, withdraw_participant


@pytest.fixture
def withdraw_db(tmp_path: Path):
    """Fixture providing initialized database with participant, session, and derived features."""
    db_file = tmp_path / "test_withdraw.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    proto = ProtocolDefinition(
        protocol_id="PROTO-W",
        protocol_version="1.0.0",
        tasks=["sustained_vowel"],
    )
    create_protocol(conn, proto)

    study = Study(
        study_id="STUDY-W",
        study_name="Withdrawal Study",
        study_description="Test study for withdrawal",
        protocol_id="PROTO-W",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-W",
        dataset_version="1.0",
    )
    create_study(conn, study)

    dua = DatasetAccessRecord(
        dataset_id="DATASET-W",
        dataset_version="1.0",
        dataset_owner="Withdrawal Sponsor",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel"],
    )
    register_dataset_access(conn, dua)

    p = Participant(
        participant_id="PT-WITHDRAW-01",
        study_id="STUDY-W",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="none",
    )
    register_participant(conn, p)

    c = ConsentRecord(
        consent_record_id="CONSENT-W-01",
        participant_id="PT-WITHDRAW-01",
        study_id="STUDY-W",
        consent_form_version="1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_recording"],
        permitted_recording_tasks=["sustained_vowel"],
        permission_to_retain_derived_features=True,
    )
    record_consent(conn, c)

    sess = ResearchSession(
        session_id="SESS-W-01",
        study_id="STUDY-W",
        protocol_version="1.0.0",
        participant_id="PT-WITHDRAW-01",
        visit_index=1,
        consent_reference="CONSENT-W-01",
    )
    create_session(conn, sess)

    task = TaskRecording(
        task_id="TASK-W-01",
        session_id="SESS-W-01",
        task_type="sustained_vowel",
        task_status="FEATURES_EXTRACTED",
        derived_feature_count=39,
    )
    record_task_recording(
        conn,
        task,
        features={"f0_mean_hz": 120.0, "jitter_percent": 0.5},
        consent=c,
    )

    yield conn
    conn.close()


def test_withdrawal_fails_closed_without_hmac_key(withdraw_db, monkeypatch):
    """Ensure withdrawal fails closed when external HMAC key is not set."""
    monkeypatch.delenv("VOXNEURO_HMAC_KEY", raising=False)
    monkeypatch.delenv("VOXNEURO_EXTERNAL_EVALUATION_KEY", raising=False)

    with pytest.raises(KeyError, match="external HMAC key material"):
        withdraw_participant(withdraw_db, "PT-WITHDRAW-01")

    # Verify participant is NOT marked withdrawn
    p = get_participant(withdraw_db, "PT-WITHDRAW-01")
    assert p.enrollment_status == "enrolled"


def test_withdrawal_succeeds_and_creates_hmac_tombstone(withdraw_db, monkeypatch):
    """Ensure withdrawal computes valid HMAC tombstone and purges features."""
    test_key = "secure_audit_key_2026"
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", test_key)

    res = withdraw_participant(withdraw_db, "PT-WITHDRAW-01")
    assert res["status"] == "WITHDRAWAL_COMPLETED"
    assert res["derived_features_deleted"] > 0
    assert "tombstone_id" in res

    # Verify participant state in DB
    p = get_participant(withdraw_db, "PT-WITHDRAW-01")
    assert p.enrollment_status == "withdrawn"
    assert p.consent_status == "withdrawn"
    assert p.withdrawal_timestamp is not None

    # Verify tombstone table has key_id and verifiable HMAC
    cursor = withdraw_db.cursor()
    cursor.execute(
        """
        SELECT tombstone_id, participant_pseudonym_hash, key_id
        FROM tombstones WHERE tombstone_id = ?;
        """,
        (res["tombstone_id"],),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["key_id"] == "voxneuro-key-v1"
    stored_hmac = row["participant_pseudonym_hash"]

    # Verify HMAC calculation matches
    expected_hmac, _ = compute_withdrawal_tombstone_hash(
        participant_id="PT-WITHDRAW-01",
        key=test_key,
    )
    assert hmac.compare_digest(stored_hmac, expected_hmac)


def test_withdrawal_transactional_rollback_on_error(withdraw_db, monkeypatch):
    """Ensure entire withdrawal rolls back atomically if any step raises an exception."""
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", "rollback_key_2026")

    # Inject an error into tombstone insertion or session restriction
    with patch(
        "voxneuro.study.withdrawal.compute_withdrawal_tombstone_hash",
        side_effect=RuntimeError("Simulated tombstone failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated tombstone failure"):
            withdraw_participant(withdraw_db, "PT-WITHDRAW-01")

    # Assert participant remains enrolled with active consent
    p = get_participant(withdraw_db, "PT-WITHDRAW-01")
    assert p.enrollment_status == "enrolled"
    assert p.consent_status == "consented"

    # Assert derived features were NOT deleted
    cursor = withdraw_db.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM derived_features WHERE session_id = 'SESS-W-01';")
    assert cursor.fetchone()["count"] > 0

    # Assert zero tombstones written
    cursor.execute("SELECT COUNT(*) as count FROM tombstones;")
    assert cursor.fetchone()["count"] == 0
