"""Unit tests verifying M5 session consent pinning, research scope, and DUA enforcement."""

from __future__ import annotations

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
    TaskRecording,
    utc_now_iso,
)
from voxneuro.study.session import (
    create_session,
    preflight_session_ingestion,
    record_task_recording,
)


@pytest.fixture
def study_env(tmp_path):
    """Provide a configured study test environment with migrations applied."""
    db_file = tmp_path / "study_consent_repair.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    try:
        # Register protocol
        create_protocol(
            conn,
            ProtocolDefinition(
                protocol_id="proto_multitask_v1",
                protocol_version="v1",
                tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
            ),
        )

        # Register study
        create_study(
            conn,
            Study(
                study_id="study_longitudinal_101",
                study_name="Longitudinal Voice Study 101",
                study_description="Rigorous longitudinal cohort",
                protocol_id="proto_multitask_v1",
                protocol_version="v1",
                dataset_id="uams_figshare_23849127",
                dataset_version="v1",
                created_at=utc_now_iso(),
                updated_at=utc_now_iso(),
                consent_requirements=["biomarker_research"],
                data_retention_policy_id="ret_policy_opt_in",
                analysis_configuration_id="cfg_voice_v3",
            ),
        )

        # Register valid DUA
        register_dataset_access(
            conn,
            DatasetAccessRecord(
                dataset_id="uams_figshare_23849127",
                dataset_version="v1",
                dataset_owner="UAMS",
                license_type="academic_research_only",
                access_approval_state="APPROVED",
                dua_state="ACTIVE",
                permitted_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
                permitted_data_processing_operations=["feature_extraction", "statistical_audit"],
                expiration_date="2035-12-31",
            ),
        )

        yield conn
    finally:
        conn.close()


def test_new_participant_defaults_to_pending_consent(study_env):
    """New participant registration must default to pending consent and consent_version='none'."""
    p = Participant(
        participant_id="P_PENDING_01",
        study_id="study_longitudinal_101",
    )
    register_participant(study_env, p)
    from voxneuro.study.participant import get_participant

    part = get_participant(study_env, "P_PENDING_01")
    assert part.consent_status == "pending"
    assert part.consent_version == "none"
    assert part.enrollment_status == "enrolled"


def test_missing_or_empty_consent_reference_blocks_session_creation(study_env):
    """create_session must fail closed when consent_reference is missing, None, or empty."""
    register_participant(
        study_env,
        Participant(
            participant_id="P_NO_CONSENT_REF",
            study_id="study_longitudinal_101",
        ),
    )
    c = ConsentRecord(
        consent_record_id="c_temp_active",
        participant_id="P_NO_CONSENT_REF",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permitted_research_uses=["biomarker_research"],
    )
    record_consent(study_env, c)

    sess = ResearchSession(
        session_id="s_no_consent_ref",
        study_id="study_longitudinal_101",
        protocol_version="v1",
        participant_id="P_NO_CONSENT_REF",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="telephone",
        recording_timestamp=utc_now_iso(),
        consent_reference="",  # empty
    )
    with pytest.raises(PermissionError, match="Missing required consent_reference"):
        create_session(study_env, sess)


def test_invalid_or_nonexistent_consent_reference_blocks_session_creation(study_env):
    """create_session must fail closed without implicitly falling back to active consent."""
    register_participant(
        study_env,
        Participant(
            participant_id="P_INVALID_REF",
            study_id="study_longitudinal_101",
        ),
    )
    # Grant active consent
    c = ConsentRecord(
        consent_record_id="c_valid_on_file",
        participant_id="P_INVALID_REF",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=False,
    )
    record_consent(study_env, c)

    # Session with invalid consent reference must NOT fall back to c_valid_on_file
    sess = ResearchSession(
        session_id="s_invalid_ref",
        study_id="study_longitudinal_101",
        protocol_version="v1",
        participant_id="P_INVALID_REF",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="telephone",
        recording_timestamp=utc_now_iso(),
        consent_reference="nonexistent_consent_record_id",
    )
    with pytest.raises(PermissionError, match="does not exist in study"):
        create_session(study_env, sess)


def test_newer_more_permissive_consent_cannot_authorize_pinned_old_session(study_env):
    """Older session pinned to restricted consent cannot acquire permissions from newer consent."""
    register_participant(
        study_env,
        Participant(
            participant_id="P_RESTRICTED_OLD",
            study_id="study_longitudinal_101",
        ),
    )

    # Consent 1: ONLY sustained vowel permitted, non-retention
    c1 = ConsentRecord(
        consent_record_id="c_v1_restricted",
        participant_id="P_RESTRICTED_OLD",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date="2026-01-01",
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],  # NO ddk, NO connected_speech
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=False,
    )
    record_consent(study_env, c1)

    sess = ResearchSession(
        session_id="s_old_pinned",
        study_id="study_longitudinal_101",
        protocol_version="v1",
        participant_id="P_RESTRICTED_OLD",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="telephone",
        recording_timestamp="2026-01-02T10:00:00Z",
        consent_reference="c_v1_restricted",
    )
    create_session(study_env, sess)

    # Later: Participant signs Consent 2 adding DDK and connected_speech
    c2 = ConsentRecord(
        consent_record_id="c_v2_permissive",
        participant_id="P_RESTRICTED_OLD",
        study_id="study_longitudinal_101",
        consent_form_version="v2.0",
        consent_date="2026-06-01",
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=True,
    )
    record_consent(study_env, c2)

    # Preflighting OLD session for DDK must FAIL: old session pinned to c_v1_restricted
    is_ok, reason, _ = preflight_session_ingestion(
        study_env,
        session_id="s_old_pinned",
        tasks_to_process=["ddk"],
    )
    assert not is_ok
    assert "Task consent failure for 'ddk'" in reason
    assert "c_v1_restricted" in reason


def test_withdrawn_pinned_consent_blocks_processing_even_if_participant_re_enrolled(study_env):
    """If the pinned consent of a session is withdrawn, that session remains blocked."""
    register_participant(
        study_env,
        Participant(
            participant_id="P_WITHDRAWN_PIN",
            study_id="study_longitudinal_101",
        ),
    )
    c1 = ConsentRecord(
        consent_record_id="c_withdrawn_pin",
        participant_id="P_WITHDRAWN_PIN",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date="2026-01-01",
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=False,
    )
    record_consent(study_env, c1)

    sess = ResearchSession(
        session_id="s_withdrawn_pin",
        study_id="study_longitudinal_101",
        protocol_version="v1",
        participant_id="P_WITHDRAWN_PIN",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="telephone",
        recording_timestamp="2026-01-02T10:00:00Z",
        consent_reference="c_withdrawn_pin",
    )
    create_session(study_env, sess)

    # Withdraw c1
    study_env.execute(
        "UPDATE consents SET withdrawal_status = 1 WHERE consent_record_id = 'c_withdrawn_pin';"
    )
    study_env.commit()

    is_ok, reason, _ = preflight_session_ingestion(
        study_env, "s_withdrawn_pin", tasks_to_process=["sustained_vowel"]
    )
    assert not is_ok
    assert "withdrawn or revoked" in reason


def test_derived_feature_retention_defaults_to_false_and_prevents_storage(study_env):
    """When permission_to_retain_derived_features is False, derived_features table remains empty."""
    register_participant(
        study_env,
        Participant(
            participant_id="P_NON_RETENTION",
            study_id="study_longitudinal_101",
        ),
    )
    # Use default constructor: permission_to_retain_derived_features must default to False!
    c = ConsentRecord(
        consent_record_id="c_non_retention",
        participant_id="P_NON_RETENTION",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permitted_research_uses=["biomarker_research"],
    )
    assert c.permission_to_retain_derived_features is False
    record_consent(study_env, c)

    sess = ResearchSession(
        session_id="s_non_retention",
        study_id="study_longitudinal_101",
        protocol_version="v1",
        participant_id="P_NON_RETENTION",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="telephone",
        recording_timestamp=utc_now_iso(),
        consent_reference="c_non_retention",
    )
    create_session(study_env, sess)

    task = TaskRecording(
        task_id="t_vowel_01",
        session_id="s_non_retention",
        task_type="sustained_vowel",
        task_status="FEATURES_EXTRACTED",
        audio_duration_seconds=3.0,
        quality_passed=True,
    )
    record_task_recording(study_env, task, features={"jitter_local": 0.01, "shimmer_local": 0.03})

    # Check task recording status
    cursor = study_env.execute(
        "SELECT task_status, derived_feature_count "
        "FROM task_recordings WHERE task_id = 't_vowel_01';"
    )
    row = cursor.fetchone()
    assert row["task_status"] == "ACCEPTED_TRANSIENT_PROCESSED"
    assert row["derived_feature_count"] == 0

    # Check derived features table: MUST BE EMPTY
    cursor = study_env.execute(
        "SELECT count(*) as cnt FROM derived_features WHERE session_id = 's_non_retention';"
    )
    assert cursor.fetchone()["cnt"] == 0


def test_incorrect_passed_consent_object_rejected(study_env):
    """Passing a different consent object to record_task_recording raises PermissionError."""
    register_participant(
        study_env,
        Participant(
            participant_id="P_SPOOF",
            study_id="study_longitudinal_101",
        ),
    )
    c_legit = ConsentRecord(
        consent_record_id="c_legit_pin",
        participant_id="P_SPOOF",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=False,
    )
    record_consent(study_env, c_legit)

    sess = ResearchSession(
        session_id="s_spoof_test",
        study_id="study_longitudinal_101",
        protocol_version="v1",
        participant_id="P_SPOOF",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="telephone",
        recording_timestamp=utc_now_iso(),
        consent_reference="c_legit_pin",
    )
    create_session(study_env, sess)

    fake_consent = ConsentRecord(
        consent_record_id="c_fake_unauthorized",
        participant_id="P_SPOOF",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date=utc_now_iso()[:10],
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel", "ddk"],
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=True,
    )

    task = TaskRecording(
        task_id="t_vowel_spoof",
        session_id="s_spoof_test",
        task_type="sustained_vowel",
        task_status="FEATURES_EXTRACTED",
        audio_duration_seconds=3.0,
        quality_passed=True,
    )
    with pytest.raises(
        PermissionError, match="does not match the authorized session-pinned consent"
    ):
        record_task_recording(
            study_env, task, features={"jitter_local": 0.01}, consent=fake_consent
        )

    # Also test same consent_record_id with tampered permission_to_retain_derived_features=True
    field_tampered = ConsentRecord(
        consent_record_id="c_legit_pin",
        participant_id="P_SPOOF",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date=c_legit.consent_date,
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=True,
    )
    with pytest.raises(
        PermissionError, match="does not match the authorized session-pinned consent"
    ):
        record_task_recording(
            study_env, task, features={"jitter_local": 0.01}, consent=field_tampered
        )


def test_operation_authorization_map_enforces_scope_and_research_uses(study_env):
    """Preflight enforces exact OPERATION_AUTHORIZATION_MAP scope & research-use matching."""
    register_participant(
        study_env,
        Participant(
            participant_id="P_SCOPE_01",
            study_id="study_longitudinal_101",
        ),
    )
    c_extract_only = ConsentRecord(
        consent_record_id="c_extract_only",
        participant_id="P_SCOPE_01",
        study_id="study_longitudinal_101",
        consent_form_version="v1.0",
        consent_date="2026-01-01",
        scope_of_permission=["voice_analysis"],
        permitted_recording_tasks=["sustained_vowel"],
        permitted_research_uses=["biomarker_research"],
        permission_to_retain_derived_features=False,
    )
    record_consent(study_env, c_extract_only)
    sess = ResearchSession(
        session_id="s_scope_01",
        study_id="study_longitudinal_101",
        protocol_version="v1",
        participant_id="P_SCOPE_01",
        visit_index=1,
        visit_label="Baseline",
        acquisition_domain_id="uams_telephone",
        capture_origin="telephone",
        recording_timestamp="2026-01-02T10:00:00Z",
        consent_reference="c_extract_only",
    )
    create_session(study_env, sess)

    # Feature extraction allowed
    ok_fe, msg_fe, _ = preflight_session_ingestion(
        study_env, "s_scope_01", ["sustained_vowel"], requested_operation="feature_extraction"
    )
    assert ok_fe, msg_fe

    # Mismatched operations blocked despite valid feature extraction consent
    for blocked_op in [
        "longitudinal_analysis",
        "aggregate_reporting",
        "statistical_audit",
        "qc_validation",
        "unknown_operation",
    ]:
        ok_b, msg_b, _ = preflight_session_ingestion(
            study_env, "s_scope_01", ["sustained_vowel"], requested_operation=blocked_op
        )
        assert not ok_b, f"Expected {blocked_op} to be blocked, got: {msg_b}"

    # Direct record_task_recording call cannot bypass preflight on RESTRICTED_WITHDRAWN session
    study_env.execute(
        "UPDATE sessions SET overall_session_status = 'RESTRICTED_WITHDRAWN' "
        "WHERE session_id = 's_scope_01';"
    )
    study_env.commit()
    task = TaskRecording(
        task_id="t_blocked_direct",
        session_id="s_scope_01",
        task_type="sustained_vowel",
        task_status="FEATURES_EXTRACTED",
        audio_duration_seconds=2.5,
        quality_passed=True,
    )
    with pytest.raises(PermissionError, match="central authorization preflight"):
        record_task_recording(study_env, task, features={"f0_mean_hz": 120.0})
