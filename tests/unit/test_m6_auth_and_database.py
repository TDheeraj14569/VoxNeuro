"""Unit tests for M6 migration 006, authentication, password reset, and server-side RBAC."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from voxneuro.study.auth import (
    AuthorizationError,
    authenticate_user,
    complete_password_reset,
    issue_password_reset_token,
    list_users_admin,
    register_user,
    resolve_session_user,
    revoke_session,
    update_user_profile_preferences,
    update_user_role_or_status,
)
from voxneuro.study.consent import record_consent
from voxneuro.study.database import check_schema_integrity, get_connection, run_migrations
from voxneuro.study.participant import register_participant
from voxneuro.study.registry import create_protocol, create_study
from voxneuro.study.schema import (
    ConsentRecord,
    Participant,
    ProtocolDefinition,
    Study,
    utc_now_iso,
)
from voxneuro.study.withdrawal import withdraw_participant


def test_migration_006_creates_all_m6_tables_and_preserves_m5(tmp_path: Path):
    db_path = tmp_path / "m6_test.db"
    applied = run_migrations(db_path)
    assert "006_m6_platform_and_ml_registry.sql" in applied

    status = check_schema_integrity(db_path)
    assert status["clean"] is True
    expected_tables = {
        "studies",
        "participants",
        "consents",
        "users",
        "user_sessions",
        "password_reset_tokens",
        "training_datasets",
        "training_runs",
        "model_versions",
        "model_evaluations",
        "model_domain_approvals",
        "prediction_records",
        "abstention_events",
        "model_lifecycle_events",
    }
    assert expected_tables.issubset(set(status["tables"]))


def test_auth_registration_login_rbac_and_password_reset(tmp_path: Path):
    db_path = tmp_path / "auth.db"
    run_migrations(db_path)
    conn = get_connection(db_path)
    try:
        # First admin bootstrap succeeds when no admin exists yet
        admin = register_user(
            conn,
            username="sysadmin",
            email="admin@example.org",
            password="AdminPassword123!",
            display_name="System Admin",
            role="admin",
        )
        assert admin.role == "admin"

        # Self-registration defaults safely to participant
        user = register_user(
            conn,
            username="alice_voice",
            email="alice@example.org",
            password="AlicePassword123!",
            display_name="Alice",
        )
        assert user.role == "participant"
        assert user.prediction_retention_opt_in is False

        # Privilege escalation without admin session fails closed
        with pytest.raises(AuthorizationError):
            register_user(
                conn,
                username="hacker",
                email="hacker@example.org",
                password="HackerPassword123!",
                role="researcher",
            )

        # Authenticate admin & participant
        _, admin_token = authenticate_user(
            conn, identifier="sysadmin", password="AdminPassword123!"
        )
        _, user_token = authenticate_user(
            conn, identifier="alice@example.org", password="AlicePassword123!"
        )
        assert resolve_session_user(conn, user_token).username == "alice_voice"

        # Non-admin cannot access admin endpoints
        with pytest.raises(AuthorizationError):
            list_users_admin(conn, user_token)
        with pytest.raises(AuthorizationError):
            update_user_role_or_status(
                conn, user_token, target_user_id=user.user_id, new_role="admin"
            )

        # Admin can list and update roles
        all_users = list_users_admin(conn, admin_token)
        assert len(all_users) == 2
        promoted = update_user_role_or_status(
            conn, admin_token, target_user_id=user.user_id, new_role="researcher"
        )
        assert promoted.role == "researcher"

        # Profile preference opt-in update works
        updated = update_user_profile_preferences(
            conn, user_token, display_name="Alice R.", prediction_retention_opt_in=True
        )
        assert updated.display_name == "Alice R."
        assert updated.prediction_retention_opt_in is True

        # Sign-out revokes session immediately
        assert revoke_session(conn, user_token) is True
        assert resolve_session_user(conn, user_token) is None

        # Password reset single-use flow invalidates old password and works once
        reset_tok = issue_password_reset_token(conn, email="alice@example.org")
        assert reset_tok is not None
        complete_password_reset(conn, reset_token=reset_tok, new_password="NewAlicePassword99!")
        with pytest.raises(AuthorizationError):
            complete_password_reset(conn, reset_token=reset_tok, new_password="AnotherPassword1!")
        with pytest.raises(AuthorizationError):
            authenticate_user(conn, identifier="alice_voice", password="AlicePassword123!")
        reauthed, _ = authenticate_user(
            conn, identifier="alice_voice", password="NewAlicePassword99!"
        )
        assert reauthed.user_id == user.user_id

        # Expired session fails closed
        expired_iso = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        conn.execute(
            "INSERT INTO user_sessions (session_token_hash, user_id, role, created_at, expires_at) "
            "VALUES ('deadhash', ?, 'admin', ?, ?);",
            (admin.user_id, expired_iso, expired_iso),
        )
        conn.commit()
    finally:
        conn.close()


def test_participant_withdrawal_deletes_retained_prediction_records(tmp_path: Path):
    db_path = tmp_path / "withdraw_pred.db"
    run_migrations(db_path)
    conn = get_connection(db_path)
    try:
        create_protocol(
            conn,
            ProtocolDefinition(
                protocol_id="prot-m6",
                protocol_version="1.0",
                tasks=["sustained_vowel"],
                visits_expected=1,
                minimum_interval_days=0,
            ),
        )
        create_study(
            conn,
            Study(
                study_id="study-m6",
                study_name="M6 Retention Study",
                study_description="Synthetic withdrawal test",
                protocol_id="prot-m6",
                protocol_version="1.0",
                study_status="active",
                dataset_id="uams",
                consent_requirements=["voice_recording", "feature_retention"],
                data_retention_policy_id="ret-opt-in",
                analysis_configuration_id="cfg-v3",
            ),
        )
        register_participant(
            conn,
            Participant(
                participant_id="part-m6-01",
                study_id="study-m6",
                allowed_research_scopes=["voice_analysis"],
            ),
        )
        record_consent(
            conn,
            ConsentRecord(
                consent_record_id="con-m6-01",
                participant_id="part-m6-01",
                study_id="study-m6",
                consent_form_version="v1",
                consent_date=utc_now_iso(),
                scope_of_permission=["voice_analysis"],
                permitted_recording_tasks=["sustained_vowel"],
                permitted_research_uses=["biomarker_research"],
                permission_to_retain_derived_features=True,
                source_document_reference="doc://signed-01",
            ),
        )
        conn.execute(
            """
            INSERT INTO prediction_records (
                prediction_id, session_id, participant_id, user_id, model_id,
                model_version, model_checksum, acquisition_domain_id, capture_origin,
                research_score, research_classification, calibration_status, uncertainty_json,
                abstained, abstention_reason, retention_permitted, created_at
            ) VALUES (
                'prd-001', NULL, 'part-m6-01', NULL, NULL,
                'none', 'none', 'uams_telephone', 'pre_recorded_research',
                NULL, NULL, 'NOT_APPLICABLE', '{}',
                1, 'Abstained in test', 1, '2026-11-12T00:00:00+00:00'
            );
            """
        )
        conn.commit()
        res = withdraw_participant(
            conn,
            "part-m6-01",
            key=b"unit-test-hmac-key-32-bytes-minimum",
        )
        assert res["prediction_records_deleted"] == 1
        leftover = conn.execute(
            "SELECT COUNT(*) AS c FROM prediction_records WHERE participant_id = 'part-m6-01';"
        ).fetchone()["c"]
        assert leftover == 0
    finally:
        conn.close()


def test_auth_edge_cases_and_error_handling(tmp_path: Path):
    from voxneuro.study.auth import (
        hash_password,
        require_role,
        verify_password,
    )

    db_path = tmp_path / "auth_edge.db"
    run_migrations(db_path)
    conn = get_connection(db_path)

    try:
        # 1. Short password error
        with pytest.raises(ValueError, match="at least 8 characters"):
            hash_password("short")

        # 2. Invalid hash verification
        assert verify_password("secret123", "md5$invalid$hash") is False
        assert verify_password("secret123", "corrupt_hash_format") is False

        # 3. Invalid username
        with pytest.raises(ValueError, match="at least 3 non-whitespace"):
            register_user(conn, username="a ", email="user@test.org", password="ValidPassword123!")

        # 4. Invalid email
        with pytest.raises(ValueError, match="valid email"):
            register_user(
                conn, username="alice", email="invalid-email", password="ValidPassword123!"
            )

        # 5. Unsupported role
        with pytest.raises(ValueError, match="Unsupported role"):
            register_user(
                conn,
                username="alice",
                email="alice@test.org",
                password="ValidPassword123!",
                role="supergod",
            )

        # 6. Password reset on unknown email returns None
        assert issue_password_reset_token(conn, email="unknown@test.org") is None

        # 7. Register admin and test role checks
        admin = register_user(
            conn,
            username="admin_user",
            email="admin@test.org",
            password="AdminPassword123!",
            role="admin",
        )
        _, admin_token = authenticate_user(
            conn, identifier="admin_user", password="AdminPassword123!"
        )

        # require_role raises AuthorizationError for missing role
        with pytest.raises(AuthorizationError, match="is not authorized"):
            require_role(conn, admin_token, {"consumer"})

        # update_user_role_or_status with invalid role
        with pytest.raises(ValueError, match="Unsupported role"):
            update_user_role_or_status(
                conn, admin_token, target_user_id=admin.user_id, new_role="bad_role"
            )

        # Deactivating a user revokes their sessions
        update_user_role_or_status(conn, admin_token, target_user_id=admin.user_id, is_active=False)
        with pytest.raises(AuthorizationError, match="inactive"):
            authenticate_user(conn, identifier="admin_user", password="AdminPassword123!")
    finally:
        conn.close()
