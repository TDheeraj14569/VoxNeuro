"""Integration test for Milestone 5 privacy-preserving research operations pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.audio.io import AudioRecord
from voxneuro.study.audit import (
    get_processing_run,
    list_audit_events,
    record_processing_run,
)
from voxneuro.study.consent import (
    record_consent,
    register_dataset_access,
    verify_dataset_authorization_for_task,
    verify_participant_consent_for_task,
)
from voxneuro.study.database import (
    check_schema_integrity,
    get_connection,
    run_migrations,
)
from voxneuro.study.longitudinal import calculate_longitudinal_feature_changes
from voxneuro.study.participant import (
    get_participant,
    is_participant_active,
    register_participant,
)
from voxneuro.study.qc import (
    calculate_cohort_attrition,
    calculate_cohort_qc_metrics,
)
from voxneuro.study.registry import (
    create_protocol,
    create_study,
    get_study,
    update_study_protocol,
)
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
    generate_pseudonymous_id,
    utc_now_iso,
)
from voxneuro.study.session import (
    create_session,
    get_derived_features_for_session,
    get_session,
    ingest_session_multitask_audio,
)
from voxneuro.study.withdrawal import withdraw_participant


def test_m5_operations_pipeline_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """End-to-end integration test of M5 research operations workflow."""
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", "m5_operations_secret_2026")
    db_file = tmp_path / "m5_research_operations.db"

    # Step 1: Initialize database and run migrations
    applied = run_migrations(db_file)
    assert len(applied) >= 1
    integrity = check_schema_integrity(db_file)
    assert integrity["clean"] is True
    assert len(integrity["foreign_key_violations"]) == 0

    conn = get_connection(db_file)
    try:
        # Step 2: Register Protocol and Study
        proto_v1 = ProtocolDefinition(
            protocol_id="PROTO-PARK-01",
            protocol_version="1.0.0",
            tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
            visits_expected=2,
            minimum_interval_days=14,
            instructions="Standard multi-task acoustic assessment protocol",
        )
        create_protocol(conn, proto_v1)

        study = Study(
            study_id="STUDY-PARK-01",
            study_name="Longitudinal Speech Biomarker Study",
            study_description="Longitudinal study evaluating acoustic stability across visits",
            protocol_id="PROTO-PARK-01",
            protocol_version="1.0.0",
            study_status="active",
            dataset_id="DATASET-LOCAL-01",
            dataset_version="1.0",
            created_at=utc_now_iso(),
        )
        create_study(conn, study)
        assert get_study(conn, "STUDY-PARK-01").study_status == "active"

        # Step 3: Register Dataset Access & DUA
        dua = DatasetAccessRecord(
            dataset_id="DATASET-LOCAL-01",
            dataset_version="1.0",
            dataset_owner="Biomarker Research Consortium",
            license_type="Open Research Non-Commercial",
            access_approval_state="APPROVED",
            dua_state="ACTIVE",
            permitted_tasks=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
            permitted_data_processing_operations=["feature_extraction", "statistical_audit"],
            storage_restrictions="ephemeral_processing_no_raw_audio_release",
            publication_restrictions="aggregate_reporting_only_small_cell_suppression",
        )
        register_dataset_access(conn, dua)
        d_ok, _ = verify_dataset_authorization_for_task(conn, "DATASET-LOCAL-01", "sustained_vowel")
        assert d_ok is True

        # Step 4: Enroll Pseudonymous Participants & Record Consent
        participants = []
        for i in range(1, 15):
            pid = generate_pseudonymous_id(prefix="PT")
            p = Participant(
                participant_id=pid,
                study_id="STUDY-PARK-01",
                enrollment_status="enrolled",
                consent_status="consented",
                consent_version="1.0",
                enrollment_timestamp="2026-02-01T08:00:00Z",
                site_id="SITE-EAST" if i <= 10 else "SITE-WEST",
                allowed_research_scopes=["sustained_vowel", "longitudinal_tracking"],
            )
            register_participant(conn, p)
            participants.append(pid)

            c = ConsentRecord(
                consent_record_id=f"CONSENT-{pid}",
                participant_id=pid,
                study_id="STUDY-PARK-01",
                consent_form_version="1.0",
                consent_date="2026-02-01T08:00:00Z",
                scope_of_permission=["audio_analysis", "longitudinal_tracking"],
                permitted_recording_tasks=[
                    "sustained_vowel",
                    "ddk",
                    "connected_speech",
                    "vowel_space",
                ],
                permitted_research_uses=["biomarker_research", "reproducibility_audit"],
                permission_to_retain_derived_features=True,
                permission_to_retain_audio=False,
            )
            record_consent(conn, c)

            # Verification of active consent
            assert is_participant_active(conn, pid)
            c_ok, _ = verify_participant_consent_for_task(conn, pid, "sustained_vowel")
            assert c_ok is True

        # Step 5: Schedule Sessions and Ingest Audio
        session_ids = []
        for i, pid in enumerate(participants):
            # Baseline Visit (Visit 1)
            s1_id = f"SESS-{pid}-V1"
            s1 = ResearchSession(
                session_id=s1_id,
                study_id="STUDY-PARK-01",
                protocol_version="1.0.0",
                participant_id=pid,
                visit_index=1,
                visit_label="Baseline",
                acquisition_domain_id="uams_telephone",
                capture_origin="controlled_research_session",
                recording_timestamp="2026-02-01T10:00:00Z",
                consent_reference=f"CONSENT-{pid}",
            )
            create_session(conn, s1)
            session_ids.append(s1_id)

            # Ingest synthetic audio for sustained vowel
            rec = AudioRecord(
                samples=sustained_vowel().reshape(-1, 1),
                sample_rate=16000,
                channels=1,
                subtype="PCM_16",
                format="WAV",
            )
            ingest_session_multitask_audio(conn, s1_id, sustained_vowel=rec)

            # Follow-up Visit (Visit 2) - only for first 10 participants (cohort attrition = 4/14)
            if i < 10:
                s2_id = f"SESS-{pid}-V2"
                s2 = ResearchSession(
                    session_id=s2_id,
                    study_id="STUDY-PARK-01",
                    protocol_version="1.0.0",
                    participant_id=pid,
                    visit_index=2,
                    visit_label="Follow-up 1",
                    acquisition_domain_id="uams_telephone",
                    capture_origin="controlled_research_session",
                    recording_timestamp="2026-02-22T10:00:00Z",  # 21 days later
                    consent_reference=f"CONSENT-{pid}",
                )
                create_session(conn, s2)
                session_ids.append(s2_id)
                ingest_session_multitask_audio(conn, s2_id, sustained_vowel=rec)

        # Step 6: Verify Protocol Immutability
        proto_v2 = ProtocolDefinition(
            protocol_id="PROTO-PARK-01",
            protocol_version="2.0.0",
            tasks=["sustained_vowel"],
        )
        create_protocol(conn, proto_v2)
        # Protocol version cannot be updated on study when sessions are already recorded under it
        with pytest.raises(ValueError, match="Cannot modify protocol for study"):
            update_study_protocol(conn, "STUDY-PARK-01", "PROTO-PARK-01", "2.0.0")

        # Step 7: Record and Verify Processing Run Receipt
        receipt = record_processing_run(
            conn=conn,
            study_id="STUDY-PARK-01",
            session_ids=session_ids,
            feature_table_checksum="5a2e88mockchecksumtable",
            processing_status="COMPLETED",
        )
        assert receipt.receipt_sha256 is not None
        assert len(receipt.receipt_sha256) == 64
        retrieved_receipt = get_processing_run(conn, receipt.run_id)
        assert retrieved_receipt.receipt_sha256 == receipt.receipt_sha256

        # Step 8: Calculate Operational QC Metrics and Cohort Attrition
        qc_metrics = calculate_cohort_qc_metrics(
            conn, study_id="STUDY-PARK-01", suppress_small_cells=True
        )
        assert qc_metrics["cohort_metrics"]["total_enrolled"] == 14  # Unsuppressed >=10
        assert qc_metrics["cohort_metrics"]["withdrawn"] == 0

        site_west_qc = calculate_cohort_qc_metrics(
            conn, study_id="STUDY-PARK-01", site_id="SITE-WEST", suppress_small_cells=True
        )
        # 4 participants -> suppressed
        assert site_west_qc["cohort_metrics"]["total_enrolled"] == "< 10 (Suppressed)"

        attrition = calculate_cohort_attrition(
            conn, study_id="STUDY-PARK-01", suppress_small_cells=False
        )
        assert attrition["baseline_participants"] == 14
        assert attrition["visits"][0]["participants_present"] == 14
        assert attrition["visits"][1]["participants_present"] == 10

        # Step 9: Calculate Longitudinal Feature Tracking
        long_res = calculate_longitudinal_feature_changes(
            conn,
            study_id="STUDY-PARK-01",
            task_type="sustained_vowel",
            feature_names=["f0_mean_hz"],
            min_visits=2,
            suppress_small_cells=True,
        )
        assert long_res["participants_evaluated"] == 10  # 10 is unsuppressed
        assert long_res["visit_interval_summary"]["mean_days"] == pytest.approx(21.0, abs=1.0)
        assert "Descriptive acoustic tracking only" in long_res["scientific_disclaimer"]

        # Step 10: Generate All 7 Reports and Verify Disclaimers
        rep1 = generate_study_overview_report(conn, study_id="STUDY-PARK-01")
        assert rep1["report_type"] == "STUDY_OVERVIEW_REPORT"
        assert rep1["disclaimer"] == RESEARCH_DISCLAIMER

        rep2 = generate_session_completion_report(conn, study_id="STUDY-PARK-01")
        assert rep2["report_type"] == "SESSION_COMPLETION_REPORT"
        assert rep2["disclaimer"] == RESEARCH_DISCLAIMER

        rep3 = generate_task_qc_report(conn, study_id="STUDY-PARK-01")
        assert rep3["report_type"] == "TASK_QC_REPORT"
        assert rep3["disclaimer"] == RESEARCH_DISCLAIMER

        rep4 = generate_cohort_attrition_report(conn, study_id="STUDY-PARK-01")
        assert rep4["report_type"] == "COHORT_ATTRITION_REPORT"
        assert rep4["disclaimer"] == RESEARCH_DISCLAIMER

        rep5 = generate_longitudinal_descriptive_report(conn, study_id="STUDY-PARK-01")
        assert rep5["report_type"] == "LONGITUDINAL_DESCRIPTIVE_REPORT"
        assert rep5["disclaimer"] == RESEARCH_DISCLAIMER

        rep6 = generate_data_provenance_run_report(conn, study_id="STUDY-PARK-01")
        assert rep6["report_type"] == "DATA_PROVENANCE_RUN_REPORT"
        assert len(rep6["processing_runs"]) == 1
        assert rep6["disclaimer"] == RESEARCH_DISCLAIMER

        rep7 = generate_consent_and_dua_report(conn, study_id="STUDY-PARK-01")
        assert rep7["report_type"] == "CONSENT_DATASET_AUTHORIZATION_REPORT"
        assert rep7["disclaimer"] == RESEARCH_DISCLAIMER

        # Export CSV verification
        csv_text = export_report_to_csv(rep2, "session_breakdown")
        assert "visit_index" in csv_text
        assert "session_count" in csv_text

        # Step 11: Execute Participant Withdrawal Workflow
        withdrawn_pid = participants[0]
        w_sess_id = f"SESS-{withdrawn_pid}-V1"

        # Features exist prior to withdrawal
        feats_before = get_derived_features_for_session(conn, w_sess_id)
        assert len(feats_before) > 0

        w_result = withdraw_participant(
            conn, withdrawn_pid, deletion_reason="Participant revocation of consent"
        )
        assert w_result["status"] == "WITHDRAWAL_COMPLETED"
        assert w_result["derived_features_deleted"] > 0
        assert w_result["sessions_restricted"] > 0
        assert "tombstone_id" in w_result

        # Post-withdrawal state verification
        w_participant = get_participant(conn, withdrawn_pid)
        assert w_participant.enrollment_status == "withdrawn"
        assert w_participant.consent_status == "withdrawn"
        assert w_participant.withdrawal_timestamp is not None
        assert not is_participant_active(conn, withdrawn_pid)

        # Session restricted
        w_session = get_session(conn, w_sess_id)
        assert w_session.overall_session_status == "RESTRICTED_WITHDRAWN"

        # Derived features deleted
        feats_after = get_derived_features_for_session(conn, w_sess_id)
        assert len(feats_after) == 0

        # Cryptographic tombstone exists
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tombstones WHERE tombstone_id = ?;", (w_result["tombstone_id"],)
        )
        tomb = cursor.fetchone()
        assert tomb is not None
        assert tomb["study_id"] == "STUDY-PARK-01"
        assert tomb["records_deleted_count"] == w_result["derived_features_deleted"]

        # Audit events verify PII redaction and event capture
        audit_events = list_audit_events(conn, limit=100)
        assert len(audit_events) >= 2
        # Check that no audit detail contains raw participant names or emails
        for ev in audit_events:
            dt_str = json.dumps(ev["details"])
            assert "@" not in dt_str
    finally:
        conn.close()
