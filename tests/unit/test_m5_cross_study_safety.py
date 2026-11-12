"""Regression tests for cross-study session prevention and dataset isolation invariants."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxneuro.study.consent import record_consent, register_dataset_access
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.participant import register_participant
from voxneuro.study.registry import create_protocol, create_study
from voxneuro.study.schema import (
    ConsentRecord,
    DatasetAccessRecord,
    Participant,
    ProtocolDefinition,
    ResearchSession,
    Study,
    utc_now_iso,
)
from voxneuro.study.session import create_session, preflight_session_ingestion


@pytest.fixture
def multi_study_db(tmp_path: Path):
    """Fixture with two distinct studies, protocols, and DUAs."""
    db_file = tmp_path / "test_cross_study.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    proto1 = ProtocolDefinition(
        protocol_id="PROTO-A",
        protocol_version="1.0.0",
        tasks=["sustained_vowel", "ddk"],
    )
    create_protocol(conn, proto1)

    proto2 = ProtocolDefinition(
        protocol_id="PROTO-B",
        protocol_version="1.0.0",
        tasks=["connected_speech", "vowel_space"],
    )
    create_protocol(conn, proto2)

    study_a = Study(
        study_id="STUDY-A",
        study_name="Study Alpha",
        study_description="First study",
        protocol_id="PROTO-A",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-A",
        dataset_version="1.0",
    )
    create_study(conn, study_a)

    study_b = Study(
        study_id="STUDY-B",
        study_name="Study Beta",
        study_description="Second study",
        protocol_id="PROTO-B",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-B",
        dataset_version="1.0",
    )
    create_study(conn, study_b)

    dua_a = DatasetAccessRecord(
        dataset_id="DATASET-A",
        dataset_version="1.0",
        dataset_owner="Alpha Consortium",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel", "ddk"],
        permitted_data_processing_operations=["feature_extraction"],
        expiration_date="2035-12-31",
    )
    register_dataset_access(conn, dua_a)

    dua_b = DatasetAccessRecord(
        dataset_id="DATASET-B",
        dataset_version="1.0",
        dataset_owner="Beta Consortium",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["connected_speech", "vowel_space"],
        permitted_data_processing_operations=["feature_extraction"],
        expiration_date="2035-12-31",
    )
    register_dataset_access(conn, dua_b)

    p_a = Participant(
        participant_id="PT-ALPHA-01",
        study_id="STUDY-A",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="none",
    )
    register_participant(conn, p_a)

    c_a = ConsentRecord(
        consent_record_id="CONSENT-ALPHA-01",
        participant_id="PT-ALPHA-01",
        study_id="STUDY-A",
        consent_form_version="1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_recording", "feature_retention"],
        permitted_recording_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        permission_to_retain_derived_features=True,
    )
    record_consent(conn, c_a)

    yield conn
    conn.close()


def test_cross_study_session_assignment_rejected(multi_study_db):
    """Ensure participant enrolled in Study A cannot have session created in Study B."""
    cross_session = ResearchSession(
        session_id="SESS-CROSS-01",
        study_id="STUDY-B",  # mismatched study
        protocol_version="1.0.0",
        participant_id="PT-ALPHA-01",  # belongs to STUDY-A
        visit_index=1,
    )
    with pytest.raises(ValueError, match="Cross-study session assignment rejected"):
        create_session(multi_study_db, cross_session)


def test_consent_from_study_a_cannot_authorize_study_b(multi_study_db):
    """Ensure consent recorded for Study A does not authorize session in Study B."""
    # Enroll a participant in Study B without consent
    p_b = Participant(
        participant_id="PT-BETA-01",
        study_id="STUDY-B",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="none",
    )
    register_participant(multi_study_db, p_b)

    # Attempt to schedule session in Study B referencing Study A's consent record
    sess_b = ResearchSession(
        session_id="SESS-BETA-01",
        study_id="STUDY-B",
        protocol_version="1.0.0",
        participant_id="PT-BETA-01",
        visit_index=1,
        consent_reference="CONSENT-ALPHA-01",  # references Study A
    )
    with pytest.raises(
        PermissionError, match="not currently enrolled with active consent in study 'STUDY-B'"
    ):
        create_session(multi_study_db, sess_b)


def test_dataset_version_mismatch_blocks_study(multi_study_db):
    """Ensure study requiring dataset version 2.0 cannot ingest under version 1.0 DUA."""
    study_v2 = Study(
        study_id="STUDY-V2",
        study_name="Study Version 2",
        study_description="Test version mismatch",
        protocol_id="PROTO-A",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-A",
        dataset_version="2.0",  # Requires 2.0 but DUA is 1.0
    )
    create_study(multi_study_db, study_v2)

    p_v2 = Participant(
        participant_id="PT-V2-01",
        study_id="STUDY-V2",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="none",
    )
    register_participant(multi_study_db, p_v2)

    c_v2 = ConsentRecord(
        consent_record_id="CONSENT-V2-01",
        participant_id="PT-V2-01",
        study_id="STUDY-V2",
        consent_form_version="1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_recording"],
        permitted_recording_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        permission_to_retain_derived_features=True,
    )
    record_consent(multi_study_db, c_v2)

    sess_v2 = ResearchSession(
        session_id="SESS-V2-01",
        study_id="STUDY-V2",
        protocol_version="1.0.0",
        participant_id="PT-V2-01",
        visit_index=1,
        consent_reference="CONSENT-V2-01",
    )
    create_session(multi_study_db, sess_v2)

    is_auth, reason, meta = preflight_session_ingestion(multi_study_db, "SESS-V2-01")
    assert is_auth is False
    assert "version" in reason.lower()
