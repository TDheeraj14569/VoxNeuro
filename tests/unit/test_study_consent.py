"""Unit tests for consent management and Data Use Agreement (DUA) governance."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxneuro.study.consent import (
    get_active_consent_for_participant,
    get_consent,
    get_dataset_access,
    list_dataset_access,
    record_consent,
    register_dataset_access,
    verify_dataset_authorization_for_task,
    verify_participant_consent_for_task,
)
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.participant import register_participant
from voxneuro.study.registry import create_protocol, create_study
from voxneuro.study.schema import (
    ConsentRecord,
    DatasetAccessRecord,
    Participant,
    ProtocolDefinition,
    Study,
    utc_now_iso,
)


@pytest.fixture
def test_db(tmp_path: Path):
    """Fixture providing initialized SQLite DB with protocol, study, and participant."""
    db_file = tmp_path / "test_consent.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    protocol = ProtocolDefinition(
        protocol_id="PROTO-001",
        protocol_version="1.0.0",
        tasks=["sustained_vowel", "ddk"],
    )
    create_protocol(conn, protocol)

    study = Study(
        study_id="STUDY-001",
        study_name="Voice Study",
        study_description="Test study",
        protocol_id="PROTO-001",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-001",
        dataset_version="1.0",
        created_at=utc_now_iso(),
    )
    create_study(conn, study)

    participant = Participant(
        participant_id="PT-CONSENT01",
        study_id="STUDY-001",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="0.0",
        enrollment_timestamp=utc_now_iso(),
    )
    register_participant(conn, participant)

    yield conn
    conn.close()


def test_record_and_get_consent(test_db):
    """Verify storing and retrieving informed consent."""
    consent = ConsentRecord(
        consent_record_id="CONSENT-001",
        participant_id="PT-CONSENT01",
        study_id="STUDY-001",
        consent_form_version="2.0",
        consent_date=utc_now_iso(),
        scope_of_permission=["audio_analysis", "longitudinal_tracking"],
        permitted_recording_tasks=["sustained_vowel", "ddk"],
        permitted_research_uses=["biomarker_research"],
    )
    record_consent(test_db, consent)

    retrieved = get_consent(test_db, "CONSENT-001")
    assert retrieved.consent_record_id == "CONSENT-001"
    assert retrieved.consent_form_version == "2.0"
    assert "sustained_vowel" in retrieved.permitted_recording_tasks
    assert retrieved.withdrawal_status is False

    active = get_active_consent_for_participant(test_db, "PT-CONSENT01")
    assert active is not None
    assert active.consent_record_id == "CONSENT-001"


def test_verify_participant_consent_for_task(test_db):
    """Verify task scope enforcement against active consent."""
    # Before consent
    ok, msg = verify_participant_consent_for_task(test_db, "PT-CONSENT01", "sustained_vowel")
    assert not ok
    assert "no active consent" in msg

    # Record consent with sustained_vowel only
    consent = ConsentRecord(
        consent_record_id="CONSENT-002",
        participant_id="PT-CONSENT01",
        study_id="STUDY-001",
        consent_form_version="1.0",
        consent_date=utc_now_iso(),
        scope_of_permission=["research"],
        permitted_recording_tasks=["sustained_vowel"],
    )
    record_consent(test_db, consent)

    ok_vowel, _ = verify_participant_consent_for_task(test_db, "PT-CONSENT01", "sustained_vowel")
    assert ok_vowel is True

    ok_ddk, msg_ddk = verify_participant_consent_for_task(test_db, "PT-CONSENT01", "ddk")
    assert ok_ddk is False
    assert "not within consented recording tasks" in msg_ddk


def test_dataset_access_and_dua_verification(test_db):
    """Verify DUA approval state, active status, and task authorization."""
    dua = DatasetAccessRecord(
        dataset_id="DATASET-001",
        dataset_version="1.0",
        dataset_owner="Research Institution",
        license_type="Research Non-Commercial",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel", "ddk"],
    )
    register_dataset_access(test_db, dua)

    retrieved = get_dataset_access(test_db, "DATASET-001")
    assert retrieved.access_approval_state == "APPROVED"
    assert retrieved.dua_state == "ACTIVE"

    all_duas = list_dataset_access(test_db)
    assert len(all_duas) == 1

    # Check authorized tasks
    ok, _ = verify_dataset_authorization_for_task(test_db, "DATASET-001", "sustained_vowel")
    assert ok is True

    ok_unauth, msg = verify_dataset_authorization_for_task(
        test_db, "DATASET-001", "connected_speech"
    )
    assert ok_unauth is False
    assert "not authorized in dataset" in msg

    # Unregistered dataset fails closed
    ok_missing, msg_m = verify_dataset_authorization_for_task(
        test_db, "DATASET-UNKNOWN", "sustained_vowel"
    )
    assert ok_missing is False
    assert "no registered access/DUA" in msg_m
