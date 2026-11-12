"""Unit tests for operational QC metrics, small-cell suppression, and longitudinal tracking."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxneuro.study.consent import record_consent, register_dataset_access
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.longitudinal import calculate_longitudinal_feature_changes
from voxneuro.study.participant import register_participant
from voxneuro.study.qc import (
    apply_small_cell_suppression,
    calculate_cohort_attrition,
    calculate_cohort_qc_metrics,
)
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


@pytest.fixture
def populated_db(tmp_path: Path):
    """Fixture providing initialized study with participants and longitudinal sessions."""
    db_file = tmp_path / "test_qc_longitudinal.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    protocol = ProtocolDefinition(
        protocol_id="PROTO-QC-01",
        protocol_version="1.0.0",
        tasks=["sustained_vowel"],
        visits_expected=2,
    )
    create_protocol(conn, protocol)

    study = Study(
        study_id="STUDY-QC-01",
        study_name="QC and Longitudinal Study",
        study_description="Test study for QC metrics",
        protocol_id="PROTO-QC-01",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-QC-01",
        dataset_version="1.0",
        created_at=utc_now_iso(),
    )
    create_study(conn, study)

    dua = DatasetAccessRecord(
        dataset_id="DATASET-QC-01",
        dataset_version="1.0",
        dataset_owner="Research Center",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel"],
    )
    register_dataset_access(conn, dua)

    # Enroll 12 participants to test both suppressed (<10) and unsuppressed (>=10) cells
    for i in range(1, 13):
        pid = f"PT-COHORT{i:02d}"
        p = Participant(
            participant_id=pid,
            study_id="STUDY-QC-01",
            enrollment_status="enrolled",
            consent_status="consented",
            consent_version="1.0",
            enrollment_timestamp="2026-01-01T00:00:00Z",
            site_id="SITE-A" if i <= 8 else "SITE-B",
        )
        register_participant(conn, p)

        c = ConsentRecord(
            consent_record_id=f"CONSENT-{pid}",
            participant_id=pid,
            study_id="STUDY-QC-01",
            consent_form_version="1.0",
            consent_date="2026-01-01T00:00:00Z",
            scope_of_permission=["audio_analysis"],
            permitted_recording_tasks=["sustained_vowel"],
            permission_to_retain_derived_features=True,
        )
        record_consent(conn, c)

        # Baseline visit (Visit 1)
        s1 = ResearchSession(
            session_id=f"SESS-{pid}-V1",
            study_id="STUDY-QC-01",
            protocol_version="1.0.0",
            participant_id=pid,
            visit_index=1,
            visit_label="Baseline",
            recording_timestamp="2026-01-01T10:00:00Z",
            overall_session_status="COMPLETED",
            consent_reference=f"CONSENT-{pid}",
        )
        create_session(conn, s1)
        t1 = TaskRecording(
            task_id=f"TASK-{pid}-V1",
            session_id=s1.session_id,
            task_type="sustained_vowel",
            task_status="FEATURES_EXTRACTED",
            audio_duration_seconds=3.0,
            quality_passed=True,
            feature_schema_version="voxneuro.voice.v3",
            derived_feature_count=39,
        )
        record_task_recording(
            conn,
            t1,
            features={"f0_mean_hz": 120.0 + i, "jitter_local_percent": 0.5 + 0.01 * i},
        )

        # Follow-up visit (Visit 2) - only for first 8 participants (modeling attrition)
        if i <= 8:
            s2 = ResearchSession(
                session_id=f"SESS-{pid}-V2",
                study_id="STUDY-QC-01",
                protocol_version="1.0.0",
                participant_id=pid,
                visit_index=2,
                visit_label="Follow-up",
                recording_timestamp="2026-01-31T10:00:00Z",  # 30 days later
                overall_session_status="COMPLETED",
                consent_reference=f"CONSENT-{pid}",
            )
            create_session(conn, s2)
            t2 = TaskRecording(
                task_id=f"TASK-{pid}-V2",
                session_id=s2.session_id,
                task_type="sustained_vowel",
                task_status="FEATURES_EXTRACTED",
                audio_duration_seconds=3.0,
                quality_passed=True,
                feature_schema_version="voxneuro.voice.v3",
                derived_feature_count=39,
            )
            record_task_recording(
                conn,
                t2,
                features={"f0_mean_hz": 122.0 + i, "jitter_local_percent": 0.52 + 0.01 * i},
            )

    yield conn
    conn.close()


def test_small_cell_suppression_logic():
    """Verify small cell suppression rules (0 unsuppressed, 1-9 suppressed, >=10 unsuppressed)."""
    assert apply_small_cell_suppression(0) == 0
    assert apply_small_cell_suppression(1) == "< 10 (Suppressed)"
    assert apply_small_cell_suppression(5) == "< 10 (Suppressed)"
    assert apply_small_cell_suppression(9) == "< 10 (Suppressed)"
    assert apply_small_cell_suppression(10) == 10
    assert apply_small_cell_suppression(15) == 15


def test_cohort_qc_metrics(populated_db):
    """Verify calculation of cohort QC metrics with and without suppression."""
    # With suppression
    qc_supp = calculate_cohort_qc_metrics(
        populated_db, study_id="STUDY-QC-01", suppress_small_cells=True
    )
    assert qc_supp["cohort_metrics"]["total_enrolled"] == 12
    # Withdrawn count is 0, so should be 0 (not suppressed)
    assert qc_supp["cohort_metrics"]["withdrawn"] == 0

    # Filtered by Site B (4 participants -> should be suppressed)
    qc_site_b = calculate_cohort_qc_metrics(
        populated_db, study_id="STUDY-QC-01", site_id="SITE-B", suppress_small_cells=True
    )
    assert qc_site_b["cohort_metrics"]["total_enrolled"] == "< 10 (Suppressed)"

    # Without suppression
    qc_site_b_raw = calculate_cohort_qc_metrics(
        populated_db, study_id="STUDY-QC-01", site_id="SITE-B", suppress_small_cells=False
    )
    assert qc_site_b_raw["cohort_metrics"]["total_enrolled"] == 4


def test_cohort_attrition(populated_db):
    """Verify cohort attrition rates and small cell protection."""
    attrition = calculate_cohort_attrition(
        populated_db, study_id="STUDY-QC-01", suppress_small_cells=False
    )
    assert attrition["baseline_participants"] == 12
    visits = attrition["visits"]
    assert len(visits) == 2
    assert visits[0]["participants_present"] == 12
    assert visits[1]["participants_present"] == 8
    assert visits[1]["retention_rate"] == pytest.approx(0.6667, abs=1e-3)
    assert visits[1]["attrition_rate"] == pytest.approx(0.3333, abs=1e-3)


def test_longitudinal_feature_changes(populated_db):
    """Verify descriptive feature deltas and interval statistics."""
    long_res = calculate_longitudinal_feature_changes(
        populated_db,
        study_id="STUDY-QC-01",
        task_type="sustained_vowel",
        feature_names=["f0_mean_hz", "jitter_local_percent"],
        min_visits=2,
    )
    assert long_res["participants_evaluated"] == "< 10 (Suppressed)"  # 8 is suppressed
    assert "visit_interval_summary" in long_res
    assert long_res["visit_interval_summary"]["mean_days"] == pytest.approx(30.0, abs=1.0)

    summaries = long_res["feature_change_summaries"]
    assert "f0_mean_hz" in summaries
    # Every participant increased f0 by 2.0 Hz
    f0_stats = summaries["f0_mean_hz"]
    assert f0_stats["mean_change"] == pytest.approx(2.0, abs=1e-3)
    assert f0_stats["median_change"] == pytest.approx(2.0, abs=1e-3)

    # Check scientific disclaimer is present
    assert "scientific_disclaimer" in long_res
    assert "Descriptive acoustic tracking only" in long_res["scientific_disclaimer"]
