"""Unit tests for research session management and multi-task audio ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.audio.io import AudioRecord
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
    TaskRecording,
    utc_now_iso,
)
from voxneuro.study.session import (
    create_session,
    get_derived_features_for_session,
    get_session,
    get_task_recordings_for_session,
    ingest_session_multitask_audio,
    list_sessions,
    record_task_recording,
    update_session_status,
)


@pytest.fixture
def session_db(tmp_path: Path):
    """Fixture with initialized study, dataset access, participant, and consent."""
    db_file = tmp_path / "test_session.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    protocol = ProtocolDefinition(
        protocol_id="PROTO-001",
        protocol_version="1.0.0",
        tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
    )
    create_protocol(conn, protocol)

    study = Study(
        study_id="STUDY-001",
        study_name="Longitudinal Speech Study",
        study_description="Test study",
        protocol_id="PROTO-001",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-001",
        dataset_version="1.0",
        created_at=utc_now_iso(),
    )
    create_study(conn, study)

    dua = DatasetAccessRecord(
        dataset_id="DATASET-001",
        dataset_version="1.0",
        dataset_owner="Research Center",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
    )
    register_dataset_access(conn, dua)

    p = Participant(
        participant_id="PT-SESSION01",
        study_id="STUDY-001",
        enrollment_status="enrolled",
        consent_status="consented",
        consent_version="1.0",
        enrollment_timestamp=utc_now_iso(),
    )
    register_participant(conn, p)

    c = ConsentRecord(
        consent_record_id="CONSENT-001",
        participant_id="PT-SESSION01",
        study_id="STUDY-001",
        consent_form_version="1.0",
        consent_date=utc_now_iso(),
        scope_of_permission=["audio_analysis"],
        permitted_recording_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        permission_to_retain_derived_features=True,
    )
    record_consent(conn, c)

    yield conn
    conn.close()


def test_create_session_unconsented_rejected(session_db):
    """Ensure session creation fails if participant is not enrolled and consented."""
    # Unenrolled participant
    s_unreg = ResearchSession(
        session_id="SESS-ERR-01",
        study_id="STUDY-001",
        protocol_version="1.0.0",
        participant_id="PT-NONEXISTENT",
    )
    with pytest.raises(PermissionError, match="not currently enrolled with active consent"):
        create_session(session_db, s_unreg)


def test_create_and_get_session(session_db):
    """Verify session creation and lookup."""
    sess = ResearchSession(
        session_id="SESS-001",
        study_id="STUDY-001",
        protocol_version="1.0.0",
        participant_id="PT-SESSION01",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="controlled_research_session",
        consent_reference="CONSENT-001",
    )
    create_session(session_db, sess)

    retrieved = get_session(session_db, "SESS-001")
    assert retrieved.session_id == "SESS-001"
    assert retrieved.visit_index == 1
    assert retrieved.visit_label == "Baseline"
    assert retrieved.overall_session_status == "SCHEDULED"

    # Status update
    update_session_status(session_db, "SESS-001", "IN_PROGRESS")
    updated = get_session(session_db, "SESS-001")
    assert updated.overall_session_status == "IN_PROGRESS"


def test_list_sessions_filters(session_db):
    """Verify session listing with study and participant filtering."""
    for i in range(1, 3):
        s = ResearchSession(
            session_id=f"SESS-00{i}",
            study_id="STUDY-001",
            protocol_version="1.0.0",
            participant_id="PT-SESSION01",
            visit_index=i,
            visit_label=f"Visit {i}",
            consent_reference="CONSENT-001",
        )
        create_session(session_db, s)

    all_s = list_sessions(session_db)
    assert len(all_s) == 2

    by_pid = list_sessions(session_db, participant_id="PT-SESSION01")
    assert len(by_pid) == 2

    by_other = list_sessions(session_db, participant_id="PT-OTHER")
    assert len(by_other) == 0


def test_record_task_and_features(session_db):
    """Verify storing task execution record and derived features."""
    sess = ResearchSession(
        session_id="SESS-TASK-01",
        study_id="STUDY-001",
        protocol_version="1.0.0",
        participant_id="PT-SESSION01",
        visit_index=1,
        consent_reference="CONSENT-001",
    )
    create_session(session_db, sess)

    task = TaskRecording(
        task_id="TASK-001",
        session_id="SESS-TASK-01",
        task_type="sustained_vowel",
        task_status="FEATURES_EXTRACTED",
        audio_duration_seconds=3.2,
        quality_passed=True,
        feature_schema_version="voxneuro.voice.v3",
        derived_feature_count=39,
    )
    sample_features = {"f0_mean_hz": 125.4, "jitter_local_percent": 0.42}
    record_task_recording(session_db, task, features=sample_features)

    tasks = get_task_recordings_for_session(session_db, "SESS-TASK-01")
    assert len(tasks) == 1
    assert tasks[0].task_type == "sustained_vowel"
    assert tasks[0].quality_passed is True

    feats = get_derived_features_for_session(session_db, "SESS-TASK-01")
    assert "sustained_vowel" in feats
    assert feats["sustained_vowel"]["features"]["f0_mean_hz"] == 125.4


def test_ingest_multitask_audio(session_db):
    """Verify running M3 multi-task ingestion updates SQLite session and task states."""
    sess = ResearchSession(
        session_id="SESS-INGEST-01",
        study_id="STUDY-001",
        protocol_version="1.0.0",
        participant_id="PT-SESSION01",
        visit_index=1,
        consent_reference="CONSENT-001",
    )
    create_session(session_db, sess)

    # Ingest synthetic sustained vowel
    samples = sustained_vowel()
    audio_rec = AudioRecord(
        samples=samples.reshape(-1, 1),
        sample_rate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )
    res = ingest_session_multitask_audio(
        conn=session_db,
        session_id="SESS-INGEST-01",
        sustained_vowel=audio_rec,
    )
    assert res is not None

    tasks = get_task_recordings_for_session(session_db, "SESS-INGEST-01")
    assert len(tasks) > 0

    vowel_task = next(t for t in tasks if t.task_type.startswith("sustained_vowel"))
    assert vowel_task.task_status == "FEATURES_EXTRACTED"
    assert vowel_task.derived_feature_count == 39

    feats = get_derived_features_for_session(session_db, "SESS-INGEST-01")
    assert any(k.startswith("sustained_vowel") for k in feats)
    key = next(k for k in feats if k.startswith("sustained_vowel"))
    assert len(feats[key]["features"]) == 39
