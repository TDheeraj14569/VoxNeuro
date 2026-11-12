"""Unit tests for pseudonymous participant management and PII prevention."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.participant import (
    get_participant,
    is_participant_active,
    list_participants,
    register_participant,
    update_participant_consent_status,
    validate_pseudonym_safety,
)
from voxneuro.study.registry import create_protocol, create_study
from voxneuro.study.schema import (
    Participant,
    ProtocolDefinition,
    Study,
    generate_pseudonymous_id,
    utc_now_iso,
)


@pytest.fixture
def test_db(tmp_path: Path):
    """Fixture providing initialized SQLite DB with protocol and study."""
    db_file = tmp_path / "test_participants.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    protocol = ProtocolDefinition(
        protocol_id="PROTO-001",
        protocol_version="1.0.0",
        tasks=["sustained_vowel", "ddk"],
        visits_expected=2,
    )
    create_protocol(conn, protocol)

    study = Study(
        study_id="STUDY-001",
        study_name="Longitudinal Voice Study",
        study_description="Longitudinal research study",
        protocol_id="PROTO-001",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="TEST-DS-01",
        dataset_version="1.0",
        created_at=utc_now_iso(),
    )
    create_study(conn, study)

    yield conn
    conn.close()


def test_pseudonym_safety_validation():
    """Verify that clear PII triggers ValueError and safe pseudonyms pass."""
    safe_ids = ["PT-1234567890AB", "SUBJ-9999", "participant-12345", generate_pseudonymous_id()]
    for safe in safe_ids:
        validate_pseudonym_safety(safe)  # Should not raise

    pii_candidates = [
        "john.doe@example.com",
        "555-123-4567",
        "mrn=987654321",
        "ssn: 123-45-6789",
        "patient=JohnSmith",
    ]
    for pii in pii_candidates:
        with pytest.raises(ValueError, match="contains potential PII"):
            validate_pseudonym_safety(pii)


def test_register_and_get_participant(test_db):
    """Verify participant enrollment and retrieval."""
    pid = generate_pseudonymous_id()
    participant = Participant(
        participant_id=pid,
        study_id="STUDY-001",
        enrollment_status="enrolled",
        consent_status="consented",
        consent_version="1.0",
        enrollment_timestamp=utc_now_iso(),
        site_id="SITE-A",
        allowed_research_scopes=["sustained_vowel", "ddk"],
        participant_metadata_status="VERIFIED_DEIDENTIFIED",
    )
    register_participant(test_db, participant)

    retrieved = get_participant(test_db, pid)
    assert retrieved.participant_id == pid
    assert retrieved.study_id == "STUDY-001"
    assert retrieved.site_id == "SITE-A"
    assert retrieved.allowed_research_scopes == ["sustained_vowel", "ddk"]
    assert retrieved.participant_metadata_status == "VERIFIED_DEIDENTIFIED"


def test_register_participant_unknown_study(test_db):
    """Verify registration fails if referenced study is missing."""
    participant = Participant(
        participant_id="PT-NONEXISTENT",
        study_id="STUDY-DOES-NOT-EXIST",
        enrollment_status="enrolled",
        consent_status="consented",
        consent_version="1.0",
        enrollment_timestamp=utc_now_iso(),
    )
    with pytest.raises(KeyError, match="Referenced study does not exist"):
        register_participant(test_db, participant)


def test_list_participants_filtering(test_db):
    """Verify participant listing with study filter."""
    for i in range(3):
        pid = f"PT-PARTICIPANT{i}"
        p = Participant(
            participant_id=pid,
            study_id="STUDY-001",
            enrollment_status="enrolled",
            consent_status="consented",
            consent_version="1.0",
            enrollment_timestamp=utc_now_iso(),
        )
        register_participant(test_db, p)

    all_parts = list_participants(test_db)
    assert len(all_parts) == 3

    study_parts = list_participants(test_db, study_id="STUDY-001")
    assert len(study_parts) == 3

    other_parts = list_participants(test_db, study_id="STUDY-OTHER")
    assert len(other_parts) == 0


def test_update_participant_consent_status(test_db):
    """Verify updating consent status and error on invalid status."""
    pid = "PT-STATUS-TEST"
    p = Participant(
        participant_id=pid,
        study_id="STUDY-001",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="1.0",
        enrollment_timestamp=utc_now_iso(),
    )
    register_participant(test_db, p)
    assert not is_participant_active(test_db, pid)

    update_participant_consent_status(test_db, pid, "consented", "1.1")
    updated = get_participant(test_db, pid)
    assert updated.consent_status == "consented"
    assert updated.consent_version == "1.1"
    assert is_participant_active(test_db, pid)

    with pytest.raises(ValueError, match="Invalid consent_status"):
        update_participant_consent_status(test_db, pid, "invalid_status", "1.1")
