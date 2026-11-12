"""Unit tests for audit logging, processing receipts, participant withdrawal, and tombstones."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxneuro.study.audit import (
    get_processing_run,
    list_audit_events,
    log_audit_event,
    record_processing_run,
    sanitize_audit_details,
)
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
from voxneuro.study.session import (
    create_session,
    get_derived_features_for_session,
    get_session,
    record_task_recording,
)
from voxneuro.study.withdrawal import withdraw_participant


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Fixture providing initialized study with participant, consent, and session."""
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", "test_hmac_secret_2026")
    db_file = tmp_path / "test_withdrawal_audit.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    protocol = ProtocolDefinition(
        protocol_id="PROTO-W-01",
        protocol_version="1.0.0",
        tasks=["sustained_vowel"],
    )
    create_protocol(conn, protocol)

    study = Study(
        study_id="STUDY-W-01",
        study_name="Withdrawal Study",
        study_description="Test study for withdrawal",
        protocol_id="PROTO-W-01",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-W-01",
        dataset_version="1.0",
        created_at=utc_now_iso(),
    )
    create_study(conn, study)

    dua = DatasetAccessRecord(
        dataset_id="DATASET-W-01",
        dataset_version="1.0",
        dataset_owner="Research Center",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel"],
    )
    register_dataset_access(conn, dua)

    p = Participant(
        participant_id="PT-WITHDRAW01",
        study_id="STUDY-W-01",
        enrollment_status="enrolled",
        consent_status="consented",
        consent_version="1.0",
        enrollment_timestamp=utc_now_iso(),
    )
    register_participant(conn, p)

    c = ConsentRecord(
        consent_record_id="CONSENT-W-01",
        participant_id="PT-WITHDRAW01",
        study_id="STUDY-W-01",
        consent_form_version="1.0",
        consent_date=utc_now_iso(),
        scope_of_permission=["audio_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permission_to_retain_derived_features=True,
    )
    record_consent(conn, c)

    s = ResearchSession(
        session_id="SESS-W-01",
        study_id="STUDY-W-01",
        protocol_version="1.0.0",
        participant_id="PT-WITHDRAW01",
        visit_index=1,
        consent_reference="CONSENT-W-01",
    )
    create_session(conn, s)

    t = TaskRecording(
        task_id="TASK-W-01",
        session_id="SESS-W-01",
        task_type="sustained_vowel",
        task_status="FEATURES_EXTRACTED",
        audio_duration_seconds=3.0,
        quality_passed=True,
        feature_schema_version="voxneuro.voice.v3",
        derived_feature_count=39,
    )
    record_task_recording(conn, t, features={"f0_mean_hz": 130.0})

    yield conn
    conn.close()


def test_sanitize_audit_details_pii():
    """Verify that PII keys are redacted in audit details."""
    raw = {
        "user_id": "PT-1234",
        "participant_name": "Alice Smith",
        "email_address": "alice@example.com",
        "nested": {"phone_number": "555-123-4567", "safe_metric": 42},
    }
    cleaned = sanitize_audit_details(raw)
    assert cleaned["user_id"] == "PT-1234"
    assert cleaned["participant_name"] == "[REDACTED_PII]"
    assert cleaned["email_address"] == "[REDACTED_PII]"
    assert cleaned["nested"]["phone_number"] == "[REDACTED_PII]"
    assert cleaned["nested"]["safe_metric"] == 42


def test_audit_event_logging(test_db):
    """Verify writing and reading audit events with privacy protection."""
    log_audit_event(
        test_db,
        operation_type="TEST_ACTION",
        entity_type="test_entity",
        entity_id="ENT-001",
        actor_role="lead_auditor",
        details={"name": "Bob", "count": 10},
    )

    events = list_audit_events(test_db, entity_type="test_entity")
    assert len(events) == 1
    ev = events[0]
    assert ev["operation_type"] == "TEST_ACTION"
    assert ev["actor_role"] == "lead_auditor"
    assert ev["details"]["name"] == "[REDACTED_PII]"
    assert ev["details"]["count"] == 10


def test_processing_run_receipt(test_db):
    """Verify creating and retrieving ProcessingRunReceipt with cryptographic hashes."""
    receipt = record_processing_run(
        conn=test_db,
        study_id="STUDY-W-01",
        session_ids=["SESS-W-01"],
        feature_table_checksum="abc123mockchecksum",
        processing_status="COMPLETED",
    )
    assert receipt.receipt_sha256 is not None
    assert len(receipt.receipt_sha256) == 64

    retrieved = get_processing_run(test_db, receipt.run_id)
    assert retrieved.run_id == receipt.run_id
    assert retrieved.receipt_sha256 == receipt.receipt_sha256
    assert retrieved.feature_table_checksum == "abc123mockchecksum"


def test_withdraw_participant_workflow(test_db):
    """Verify participant withdrawal: feature deletion, session restriction, and tombstone."""
    # Before withdrawal: derived features exist
    feats = get_derived_features_for_session(test_db, "SESS-W-01")
    assert len(feats) == 1

    res = withdraw_participant(test_db, "PT-WITHDRAW01", deletion_reason="Subject request")
    assert res["status"] == "WITHDRAWAL_COMPLETED"
    assert res["derived_features_deleted"] == 1
    assert res["sessions_restricted"] == 1
    assert "tombstone_id" in res

    # Check participant state
    p = get_participant(test_db, "PT-WITHDRAW01")
    assert p.enrollment_status == "withdrawn"
    assert p.consent_status == "withdrawn"
    assert p.withdrawal_timestamp is not None

    # Check session restricted
    s = get_session(test_db, "SESS-W-01")
    assert s.overall_session_status == "RESTRICTED_WITHDRAWN"

    # Check derived features deleted
    feats_after = get_derived_features_for_session(test_db, "SESS-W-01")
    assert len(feats_after) == 0

    # Check tombstone recorded
    cursor = test_db.cursor()
    cursor.execute(
        "SELECT * FROM tombstones WHERE tombstone_id = ?;",
        (res["tombstone_id"],),
    )
    row = cursor.fetchone()
    assert row is not None

    # Verify idempotency
    second_res = withdraw_participant(test_db, "PT-WITHDRAW01")
    assert second_res["status"] == "ALREADY_WITHDRAWN"


def test_withdraw_participant_deactivates_linked_user_and_revokes_sessions(test_db):
    """Verify withdrawing a participant deactivates their linked account and revokes sessions."""
    from voxneuro.study.auth import authenticate_user, register_user, resolve_session_user

    p = Participant(
        participant_id="PT-USER-LINK01",
        study_id="STUDY-W-01",
        enrollment_status="active",
        consent_status="consented",
    )
    register_participant(test_db, p)
    user = register_user(
        test_db,
        username="linked_user",
        email="linked@example.org",
        password="ValidPassword123!",
        participant_id="PT-USER-LINK01",
        study_id="STUDY-W-01",
    )
    _, token = authenticate_user(test_db, identifier="linked_user", password="ValidPassword123!")
    assert resolve_session_user(test_db, token) is not None

    res = withdraw_participant(
        test_db, "PT-USER-LINK01", deletion_reason="Participant left study", actor_role="admin"
    )
    assert res["status"] == "WITHDRAWAL_COMPLETED"

    # User session is now revoked and account is inactive
    assert resolve_session_user(test_db, token) is None
    cur = test_db.execute("SELECT is_active FROM users WHERE user_id = ?;", (user.user_id,))
    assert bool(cur.fetchone()["is_active"]) is False
