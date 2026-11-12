"""Unit tests for Milestone 5 schemas and data structures."""

import pytest

from voxneuro.study.schema import (
    DatasetAccessRecord,
    Participant,
    ProcessingRunReceipt,
    Study,
    generate_pseudonymous_id,
)


def test_generate_pseudonymous_id():
    pid1 = generate_pseudonymous_id("PT")
    pid2 = generate_pseudonymous_id("PT")
    assert pid1.startswith("PT-")
    assert pid2.startswith("PT-")
    assert pid1 != pid2
    assert len(pid1) == 15


def test_study_schema_validation():
    # Valid study
    s = Study(
        study_id="study_pd_01",
        study_name="Parkinson Voice Longitudinal Study",
        study_description="Longitudinal observational study",
        protocol_id="proto_voice_v1",
        protocol_version="1.0.0",
        study_status="active",
    )
    assert s.study_status == "active"
    assert s.to_dict()["study_id"] == "study_pd_01"

    # Invalid study status
    with pytest.raises(ValueError, match="Invalid study_status"):
        Study(
            study_id="study_pd_02",
            study_name="Test",
            study_description="Test",
            protocol_id="proto_voice_v1",
            protocol_version="1.0.0",
            study_status="unapproved_random_state",
        )


def test_participant_schema_validation():
    p = Participant(
        participant_id="PT-ABC123XYZ890",
        study_id="study_pd_01",
        enrollment_status="enrolled",
        consent_status="consented",
    )
    assert p.participant_id == "PT-ABC123XYZ890"

    with pytest.raises(ValueError, match="Invalid enrollment_status"):
        Participant(
            participant_id="PT-123",
            study_id="study_pd_01",
            enrollment_status="invalid_status",
        )


def test_dataset_access_record_authorization():
    # Approved and active
    dua_ok = DatasetAccessRecord(
        dataset_id="neurovoz_corpus",
        dataset_version="v1",
        dataset_owner="Hospital General Universitario Gregorio Marañón",
        license_type="Research DUA",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
    )
    assert dua_ok.is_authorized() is True

    # Pending approval
    dua_pending = DatasetAccessRecord(
        dataset_id="pc_gita_corpus",
        dataset_version="v1",
        dataset_owner="UdeA",
        license_type="Academic",
        access_approval_state="PENDING",
        dua_state="ACTIVE",
    )
    assert dua_pending.is_authorized() is False


def test_processing_run_receipt_cryptographic_checksum():
    receipt = ProcessingRunReceipt(
        run_id="run-123",
        study_id="study_01",
        session_ids=["sess-1", "sess-2"],
        processing_timestamp="2026-11-12T12:00:00Z",
        application_version="voxneuro-0.5.0-research",
        project_code_fingerprint="code_fp_123",
        python_version="3.12.16",
        dependency_lockfile_fingerprint="lock_fp_123",
        task_schema_fingerprints={"v3": "fp_v3"},
        audio_config_fingerprint="audio_fp",
        feature_config_fingerprint="feat_fp",
        domain_metadata_fingerprint="domain_fp",
        input_file_checksum=None,
        feature_table_checksum="table_sha_123",
        processing_status="COMPLETED",
        exclusion_summary={"clipping": 0},
        error_summary={},
        output_artifact_checksums={"features.csv": "abc"},
    )
    digest1 = receipt.compute_sha256()
    assert len(digest1) == 64
    digest2 = receipt.compute_sha256()
    assert digest1 == digest2
