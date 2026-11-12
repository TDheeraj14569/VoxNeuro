"""Unit tests for the 7 Milestone 5 research reports and CSV exports."""

from __future__ import annotations

from pathlib import Path

import pytest

from voxneuro.study.audit import record_processing_run
from voxneuro.study.consent import record_consent, register_dataset_access
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.participant import register_participant
from voxneuro.study.registry import create_protocol, create_study
from voxneuro.study.reporting import (
    RESEARCH_DISCLAIMER,
    export_report_to_csv,
    generate_cohort_attrition_report,
    generate_consent_and_dua_report,
    generate_data_provenance_run_report,
    generate_longitudinal_descriptive_report,
    generate_session_completion_report,
    generate_study_overview_report,
    generate_task_qc_report,
)
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
def reporting_db(tmp_path: Path):
    """Fixture providing initialized study with data for reporting."""
    db_file = tmp_path / "test_reporting.db"
    run_migrations(db_file)
    conn = get_connection(db_file)

    protocol = ProtocolDefinition(
        protocol_id="PROTO-REP-01",
        protocol_version="1.0.0",
        tasks=["sustained_vowel"],
        visits_expected=2,
    )
    create_protocol(conn, protocol)

    study = Study(
        study_id="STUDY-REP-01",
        study_name="Reporting Test Study",
        study_description="Study for reporting tests",
        protocol_id="PROTO-REP-01",
        protocol_version="1.0.0",
        study_status="active",
        dataset_id="DATASET-REP-01",
        dataset_version="1.0",
        created_at=utc_now_iso(),
    )
    create_study(conn, study)

    dua = DatasetAccessRecord(
        dataset_id="DATASET-REP-01",
        dataset_version="1.0",
        dataset_owner="Research Center",
        license_type="Research",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel"],
    )
    register_dataset_access(conn, dua)

    for i in range(1, 11):
        pid = f"PT-REP{i:02d}"
        p = Participant(
            participant_id=pid,
            study_id="STUDY-REP-01",
            enrollment_status="enrolled",
            consent_status="consented",
            consent_version="1.0",
            enrollment_timestamp="2026-01-01T00:00:00Z",
        )
        register_participant(conn, p)

        c = ConsentRecord(
            consent_record_id=f"CONSENT-{pid}",
            participant_id=pid,
            study_id="STUDY-REP-01",
            consent_form_version="1.0",
            consent_date="2026-01-01T00:00:00Z",
            scope_of_permission=["audio_analysis"],
            permitted_recording_tasks=["sustained_vowel"],
            permission_to_retain_derived_features=True,
        )
        record_consent(conn, c)

        s1 = ResearchSession(
            session_id=f"SESS-{pid}-V1",
            study_id="STUDY-REP-01",
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
        record_task_recording(conn, t1, features={"f0_mean_hz": 120.0 + i})

        if i <= 6:
            s2 = ResearchSession(
                session_id=f"SESS-{pid}-V2",
                study_id="STUDY-REP-01",
                protocol_version="1.0.0",
                participant_id=pid,
                visit_index=2,
                visit_label="Follow-up",
                recording_timestamp="2026-01-20T10:00:00Z",
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
            record_task_recording(conn, t2, features={"f0_mean_hz": 121.0 + i})

    # Record a processing run
    record_processing_run(
        conn=conn,
        study_id="STUDY-REP-01",
        session_ids=[f"SESS-PT-REP{i:02d}-V1" for i in range(1, 11)],
        feature_table_checksum="testchk123",
        processing_status="COMPLETED",
    )

    yield conn
    conn.close()


def test_all_seven_reports_generated(reporting_db):
    """Verify all 7 research reports are generated with disclaimer and expected fields."""
    # Report 1: Study Overview
    rep1 = generate_study_overview_report(reporting_db, study_id="STUDY-REP-01")
    assert rep1["report_type"] == "STUDY_OVERVIEW_REPORT"
    assert len(rep1["studies"]) == 1
    assert rep1["disclaimer"] == RESEARCH_DISCLAIMER

    # Report 2: Session Completion
    rep2 = generate_session_completion_report(reporting_db, study_id="STUDY-REP-01")
    assert rep2["report_type"] == "SESSION_COMPLETION_REPORT"
    assert len(rep2["session_breakdown"]) == 2  # V1 and V2
    assert rep2["disclaimer"] == RESEARCH_DISCLAIMER

    # Report 3: Task QC
    rep3 = generate_task_qc_report(reporting_db, study_id="STUDY-REP-01")
    assert rep3["report_type"] == "TASK_QC_REPORT"
    assert len(rep3["tasks"]) > 0
    assert rep3["disclaimer"] == RESEARCH_DISCLAIMER

    # Report 4: Cohort Attrition
    rep4 = generate_cohort_attrition_report(reporting_db, study_id="STUDY-REP-01")
    assert rep4["report_type"] == "COHORT_ATTRITION_REPORT"
    assert rep4["baseline_participants"] == 10  # 10 is unsuppressed
    assert rep4["disclaimer"] == RESEARCH_DISCLAIMER

    # Report 5: Longitudinal Descriptive
    rep5 = generate_longitudinal_descriptive_report(
        reporting_db, study_id="STUDY-REP-01", task_type="sustained_vowel"
    )
    assert rep5["report_type"] == "LONGITUDINAL_DESCRIPTIVE_REPORT"
    assert rep5["participants_evaluated"] == "< 10 (Suppressed)"  # 6 is suppressed
    assert rep5["disclaimer"] == RESEARCH_DISCLAIMER

    # Report 6: Data Provenance
    rep6 = generate_data_provenance_run_report(reporting_db, study_id="STUDY-REP-01")
    assert rep6["report_type"] == "DATA_PROVENANCE_RUN_REPORT"
    assert len(rep6["processing_runs"]) == 1
    assert rep6["disclaimer"] == RESEARCH_DISCLAIMER

    # Report 7: Consent and DUA
    rep7 = generate_consent_and_dua_report(reporting_db, study_id="STUDY-REP-01")
    assert rep7["report_type"] == "CONSENT_DATASET_AUTHORIZATION_REPORT"
    assert rep7["consent_status_counts"]["consented"] == 10
    assert len(rep7["dataset_dua_records"]) == 1
    assert rep7["disclaimer"] == RESEARCH_DISCLAIMER


def test_csv_export(reporting_db):
    """Verify CSV export utility on tabular report data."""
    rep2 = generate_session_completion_report(reporting_db, study_id="STUDY-REP-01")
    csv_str = export_report_to_csv(rep2, "session_breakdown")
    assert "visit_index" in csv_str
    assert "session_count" in csv_str
    lines = csv_str.strip().split("\n")
    assert len(lines) == 3  # Header + 2 data rows
