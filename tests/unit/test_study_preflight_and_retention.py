"""Regression tests for preflight audio authorization and derived-feature retention preferences."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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
    utc_now_iso,
)
from voxneuro.study.session import (
    create_session,
    get_derived_features_for_session,
    get_task_recordings_for_session,
    ingest_session_multitask_audio,
    preflight_session_ingestion,
)


@pytest.fixture
def preflight_db(tmp_path: Path):
    """Fixture providing initialized study database."""
    db_file = tmp_path / "test_preflight.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    proto = ProtocolDefinition(
        protocol_id="PROTO-TEST",
        protocol_version="1.0.0",
        tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
    )
    create_protocol(conn, proto)

    study = Study(
        study_id="STUDY-PREFLIGHT",
        study_name="Preflight Test Study",
        study_description="Test study for preflight validation",
        protocol_id="PROTO-TEST",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-PRE",
        dataset_version="1.0",
    )
    create_study(conn, study)

    dua = DatasetAccessRecord(
        dataset_id="DATASET-PRE",
        dataset_version="1.0",
        dataset_owner="Test Sponsor",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        permitted_data_processing_operations=[
            "research_audio_ingestion",
            "feature_extraction",
            "longitudinal_analysis",
        ],
        expiration_date="2035-12-31",
    )
    register_dataset_access(conn, dua)

    p1 = Participant(
        participant_id="PT-PRE-01",
        study_id="STUDY-PREFLIGHT",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="none",
    )
    register_participant(conn, p1)

    c1 = ConsentRecord(
        consent_record_id="CONSENT-PRE-01",
        participant_id="PT-PRE-01",
        study_id="STUDY-PREFLIGHT",
        consent_form_version="1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_recording", "feature_retention"],
        permitted_recording_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        permission_to_retain_derived_features=True,
    )
    record_consent(conn, c1)

    sess = ResearchSession(
        session_id="SESS-PRE-01",
        study_id="STUDY-PREFLIGHT",
        protocol_version="1.0.0",
        participant_id="PT-PRE-01",
        visit_index=1,
        acquisition_domain_id="uams_telephone",
        consent_reference="CONSENT-PRE-01",
    )
    create_session(conn, sess)

    yield conn
    conn.close()


@pytest.fixture
def sample_audio() -> AudioRecord:
    """Generate a clean synthetic sustained vowel AudioRecord."""
    samples = sustained_vowel(sample_rate=16000, duration=2.5)
    return AudioRecord(
        samples=samples.reshape(-1, 1),
        sample_rate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )


def test_preflight_blocks_when_participant_withdrawn(preflight_db, sample_audio, monkeypatch):
    """Ensure preflight authorization fails immediately if participant has withdrawn."""
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", "test_key_preflight_2026")
    from voxneuro.study.withdrawal import withdraw_participant

    withdraw_participant(preflight_db, "PT-PRE-01")

    is_auth, reason, meta = preflight_session_ingestion(preflight_db, "SESS-PRE-01")
    assert is_auth is False
    assert "withdrawn" in reason.lower()

    # Ensure audio processing is rejected before execution
    with patch("voxneuro.study.session.analyze_multitask_session") as mock_pipeline:
        with pytest.raises(PermissionError, match="preflight failed"):
            ingest_session_multitask_audio(
                preflight_db,
                session_id="SESS-PRE-01",
                sustained_vowel=sample_audio,
            )
        assert mock_pipeline.call_count == 0


def test_preflight_blocks_when_study_paused_or_archived(preflight_db, sample_audio):
    """Ensure preflight authorization blocks processing if study is not active."""
    cursor = preflight_db.cursor()
    cursor.execute(
        "UPDATE studies SET study_status = 'archived' WHERE study_id = 'STUDY-PREFLIGHT';"
    )
    preflight_db.commit()

    is_auth, reason, meta = preflight_session_ingestion(preflight_db, "SESS-PRE-01")
    assert is_auth is False
    assert "archived" in reason.lower()

    with patch("voxneuro.study.session.analyze_multitask_session") as mock_pipeline:
        with pytest.raises(PermissionError, match="preflight failed"):
            ingest_session_multitask_audio(
                preflight_db,
                session_id="SESS-PRE-01",
                sustained_vowel=sample_audio,
            )
        assert mock_pipeline.call_count == 0


def test_preflight_blocks_when_dua_expired(preflight_db, sample_audio):
    """Ensure expired DUA blocks preflight and prevents pipeline execution."""
    cursor = preflight_db.cursor()
    cursor.execute(
        "UPDATE dataset_access SET expiration_date = '2020-01-01' WHERE dataset_id = 'DATASET-PRE';"
    )
    preflight_db.commit()

    is_auth, reason, meta = preflight_session_ingestion(preflight_db, "SESS-PRE-01")
    assert is_auth is False
    assert "expired" in reason.lower()

    with patch("voxneuro.study.session.analyze_multitask_session") as mock_pipeline:
        with pytest.raises(PermissionError, match="preflight failed"):
            ingest_session_multitask_audio(
                preflight_db,
                session_id="SESS-PRE-01",
                sustained_vowel=sample_audio,
            )
        assert mock_pipeline.call_count == 0


def test_preflight_blocks_when_task_not_consented(preflight_db, sample_audio):
    """Ensure preflight blocks specific tasks that participant did not consent to."""
    # Register participant who only consented to DDK, not sustained_vowel
    p2 = Participant(
        participant_id="PT-PRE-02",
        study_id="STUDY-PREFLIGHT",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="none",
    )
    register_participant(preflight_db, p2)

    c2 = ConsentRecord(
        consent_record_id="CONSENT-PRE-02",
        participant_id="PT-PRE-02",
        study_id="STUDY-PREFLIGHT",
        consent_form_version="1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_recording"],
        permitted_recording_tasks=["ddk"],  # sustained_vowel omitted
        permission_to_retain_derived_features=True,
    )
    record_consent(preflight_db, c2)

    sess2 = ResearchSession(
        session_id="SESS-PRE-02",
        study_id="STUDY-PREFLIGHT",
        protocol_version="1.0.0",
        participant_id="PT-PRE-02",
        visit_index=1,
        acquisition_domain_id="uams_telephone",
        consent_reference="CONSENT-PRE-02",
    )
    create_session(preflight_db, sess2)

    is_auth, reason, meta = preflight_session_ingestion(
        preflight_db,
        "SESS-PRE-02",
        tasks_to_process=["sustained_vowel"],
    )
    assert is_auth is False
    assert "sustained_vowel" in reason

    with patch("voxneuro.study.session.analyze_multitask_session") as mock_pipeline:
        with pytest.raises(PermissionError, match="preflight failed"):
            ingest_session_multitask_audio(
                preflight_db,
                session_id="SESS-PRE-02",
                sustained_vowel=sample_audio,
            )
        assert mock_pipeline.call_count == 0


def test_ephemeral_processing_when_retention_consent_false(preflight_db, sample_audio):
    """Ensure features are not persisted when permission_to_retain_derived_features is False."""
    p_noretain = Participant(
        participant_id="PT-PRE-NORETAIN",
        study_id="STUDY-PREFLIGHT",
        enrollment_status="enrolled",
        consent_status="pending",
        consent_version="none",
    )
    register_participant(preflight_db, p_noretain)

    c_noretain = ConsentRecord(
        consent_record_id="CONSENT-PRE-NORETAIN",
        participant_id="PT-PRE-NORETAIN",
        study_id="STUDY-PREFLIGHT",
        consent_form_version="1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_recording"],
        permitted_recording_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        permission_to_retain_derived_features=False,  # DO NOT RETAIN
    )
    record_consent(preflight_db, c_noretain)

    sess_noretain = ResearchSession(
        session_id="SESS-PRE-NORETAIN",
        study_id="STUDY-PREFLIGHT",
        protocol_version="1.0.0",
        participant_id="PT-PRE-NORETAIN",
        visit_index=1,
        acquisition_domain_id="uams_telephone",
        consent_reference="CONSENT-PRE-NORETAIN",
    )
    create_session(preflight_db, sess_noretain)

    # Ingest audio for sustained_vowel
    res = ingest_session_multitask_audio(
        preflight_db,
        session_id="SESS-PRE-NORETAIN",
        sustained_vowel=sample_audio,
    )

    assert res.overall_processing_status in {"complete", "partial", "failed"}

    # Verify task recordings table has ACCEPTED_TRANSIENT_PROCESSED and 0 count
    tasks = get_task_recordings_for_session(preflight_db, "SESS-PRE-NORETAIN")
    vowel_task = next(t for t in tasks if t.task_type.startswith("sustained_vowel"))
    assert vowel_task.task_status == "ACCEPTED_TRANSIENT_PROCESSED"
    assert vowel_task.derived_feature_count == 0

    # Verify derived_features table is empty for this session
    features = get_derived_features_for_session(preflight_db, "SESS-PRE-NORETAIN")
    assert len(features) == 0
