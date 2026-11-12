"""Unit tests for frozen reference model evaluation, bootstrap, and suppression."""

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from voxneuro.config import load_config
from voxneuro.features.schema import FEATURE_NAMES
from voxneuro.modeling.domain_evaluation import (
    DEFAULT_MODEL_PATH,
    build_quality_attrition_summary,
    evaluate_frozen_model_on_cohort,
    load_frozen_reference_model,
)
from voxneuro.modeling.model_bundle import make_bundle


def _get_test_bundle():
    if DEFAULT_MODEL_PATH.is_file():
        return load_frozen_reference_model()
    X = pd.DataFrame(np.zeros((2, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    model = DummyClassifier(strategy="constant", constant=0).fit(X, [0, 1])
    feat_cfg = load_config("feature_config.yaml")
    prep_cfg = load_config("audio_config.yaml")
    return make_bundle(
        model=model,
        dataset_provenance="clean-room test",
        dataset_version="test-v1",
        dataset_checksum_sha256="a" * 64,
        code_version="b" * 64,
        training_evaluation_receipt_sha256="c" * 64,
        validation_method="clean-room test only",
        software_versions={"python": "3.12"},
        feature_config=feat_cfg,
        preprocessing_config=prep_cfg,
    )


def test_load_frozen_reference_model():
    if not DEFAULT_MODEL_PATH.is_file():
        with pytest.raises(FileNotFoundError, match="Frozen reference model not found"):
            load_frozen_reference_model()
        return

    bundle = load_frozen_reference_model()
    assert bundle["feature_schema_version"] == "voxneuro.voice.v3"
    assert bundle["domain_compatibility_verified"] is False
    assert bundle["allow_user_microphone_inference"] is False
    assert hasattr(bundle["model"], "predict")


def test_evaluate_frozen_model_bootstrap():
    bundle = _get_test_bundle()
    rng = np.random.default_rng(2026)

    # Cohort of 30 participants (15 PD, 15 HC)
    n = 30
    data = {name: rng.normal(0, 1, n) for name in FEATURE_NAMES}
    data["participant_id"] = [f"P_{i:03d}" for i in range(n)]
    data["diagnostic_group"] = ["PD"] * 15 + ["HC"] * 15
    df = pd.DataFrame(data)

    metrics = evaluate_frozen_model_on_cohort(bundle, df, n_bootstrap=100)
    assert "balanced_accuracy" in metrics
    assert "sensitivity" in metrics
    assert "specificity" in metrics

    bacc = metrics["balanced_accuracy"]
    assert bacc.status == "ESTIMATED"
    assert bacc.point_estimate is not None
    assert bacc.ci_lower is not None
    assert bacc.ci_upper is not None
    assert 0.0 <= bacc.ci_lower <= bacc.ci_upper <= 1.0


def test_small_cell_suppression_on_small_cohort():
    """Small cohort (e.g. N < 20 or group < 10) must flag UNRELIABLE_SMALL_SAMPLE."""
    bundle = _get_test_bundle()
    rng = np.random.default_rng(2026)

    # Only 8 participants
    n = 8
    data = {name: rng.normal(0, 1, n) for name in FEATURE_NAMES}
    data["participant_id"] = [f"P_{i:03d}" for i in range(n)]
    data["diagnostic_group"] = ["PD"] * 4 + ["HC"] * 4
    df = pd.DataFrame(data)

    metrics = evaluate_frozen_model_on_cohort(bundle, df)
    bacc = metrics["balanced_accuracy"]
    assert bacc.status == "UNRELIABLE_SMALL_SAMPLE"
    assert bacc.ci_lower is None
    assert bacc.ci_upper is None


def test_build_quality_attrition_summary():
    qa = build_quality_attrition_summary(
        total_enrolled=50,
        recordings_attempted=48,
        passed_count=40,
        reasons={"clipping": 5, "low_rms": 3},
        failures_by_group={"PD": 5, "HC": 3},
    )
    assert qa.total_enrolled == 50
    assert qa.recordings_attempted == 48
    assert qa.recordings_passed_quality == 40
    assert abs(qa.attrition_rate - (8 / 48)) < 1e-5
    assert qa.reasons["clipping"] == 5


def test_participant_independence_verification(monkeypatch):
    from voxneuro.modeling.domain_evaluation import verify_participant_independence

    ref = ["P01", "P02", "P03"]
    cand = ["EXT01", "EXT02", "EXT03"]

    # Fails closed when external HMAC key is not provided
    monkeypatch.delenv("VOXNEURO_HMAC_KEY", raising=False)
    res_no_key = verify_participant_independence(ref, cand)
    assert res_no_key["overlap_status"] == "INDEPENDENCE_NOT_VERIFIED"
    assert res_no_key["is_disjoint"] is False

    # Disjoint cohorts with external test key
    test_key = "test_external_hmac_secret_2026"
    res = verify_participant_independence(ref, cand, key=test_key)
    assert res["overlap_status"] == "VERIFIED_DISJOINT"
    assert res["is_disjoint"] is True
    assert res["overlapping_participants_count"] == 0

    # Overlapping cohorts
    cand_overlap = ["EXT01", "p_02", "EXT03"]
    res_overlap = verify_participant_independence(ref, cand_overlap, key=test_key)
    assert res_overlap["overlap_status"] == "OVERLAP_DETECTED"
    assert res_overlap["is_disjoint"] is False
    assert res_overlap["overlapping_participants_count"] == 1

    # Empty cohort
    res_empty = verify_participant_independence([], cand, key=test_key)
    assert res_empty["overlap_status"] == "INDEPENDENCE_NOT_VERIFIED"
    assert res_empty["is_disjoint"] is False


def test_evaluation_provenance_receipt_verification(tmp_path, monkeypatch):
    import hashlib

    from voxneuro.config import load_config
    from voxneuro.features.schema import (
        FEATURE_NAMES,
        SCHEMA_VERSION,
        configuration_fingerprint,
        feature_config_fingerprint,
        schema_fingerprint,
    )
    from voxneuro.modeling import trust_registry
    from voxneuro.modeling.domain_evaluation import (
        FROZEN_REFERENCE_MODEL_SHA256,
        EvaluationProvenanceReceipt,
        create_participant_independence_attestation,
        evaluate_external_domain_with_provenance,
        verify_evaluation_provenance_receipt,
    )
    from voxneuro.modeling.trust_registry import (
        DEFAULT_AUTHORITY_KEY_ID,
        AuthorizationTrustRegistry,
        AuthorizedReviewerRecord,
        AuthorizedSourceRecord,
        generate_ed25519_keypair,
        sign_authorization_registry,
    )
    from voxneuro.provenance import project_code_fingerprint
    from voxneuro.study.consent import register_dataset_access
    from voxneuro.study.database import get_connection, run_migrations
    from voxneuro.study.schema import DatasetAccessRecord

    seed, pub = generate_ed25519_keypair()
    anchor_yaml = tmp_path / "m4_trust_anchors.yaml"
    anchor_yaml.write_text(
        "schema_version: voxneuro.m4_trust_anchors.v1\n"
        "authority_name: VoxNeuro Scientific Governance Authority\n"
        "signature_algorithm: Ed25519\n"
        "pinned_public_keys:\n"
        f'  {DEFAULT_AUTHORITY_KEY_ID}: "{pub.hex()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(trust_registry, "PINNED_TRUST_ANCHORS_PATH", anchor_yaml)
    monkeypatch.setattr(
        trust_registry,
        "_PINNED_ED25519_PUBLIC_KEYS",
        {DEFAULT_AUTHORITY_KEY_ID: pub.hex()},
    )
    test_key = "test_external_hmac_secret_2026"
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", test_key)

    cand_csv = tmp_path / "cand.csv"
    cand_row = {"participant_id": "C1", "diagnostic_group": "PD"}
    for f in FEATURE_NAMES:
        cand_row[f] = 0.5
    pd.DataFrame([cand_row]).to_csv(cand_csv, index=False)
    cand_sha = hashlib.sha256(cand_csv.read_bytes()).hexdigest()

    ref_csv = tmp_path / "ref.csv"
    ref_csv.write_text("participant_id,diagnostic_group\nR1,HC\n", encoding="utf-8")
    ref_sha = hashlib.sha256(ref_csv.read_bytes()).hexdigest()

    reg_payload = AuthorizationTrustRegistry(
        registry_id="VOXNEURO-M4-REG-2026",
        registry_version="2026.11.1",
        issuing_authority="VoxNeuro Scientific Governance Authority",
        created_utc="2026-01-01T00:00:00Z",
        expires_utc="2035-12-31T00:00:00Z",
        review_date_utc="2027-01-01T00:00:00Z",
        key_id=DEFAULT_AUTHORITY_KEY_ID,
        signature_algorithm="Ed25519",
        authorized_sources=(
            AuthorizedSourceRecord(
                dataset_id="uams_figshare_23849127",
                dataset_version="v1",
                source_id="uams_figshare_verified_roster",
                role="reference",
                artifact_sha256=ref_sha,
                retrieval_reference="doi:10.6084/m9.figshare.23849127.v1",
                authorization_ref="IRB-UAMS-2023-01",
                authorization_state="APPROVED",
                permitted_tasks=("sustained_vowel",),
                permitted_operations=("frozen_model_evaluation",),
                expiry_utc="2035-12-31T00:00:00Z",
                issuing_authority="VoxNeuro Scientific Governance Authority",
                registry_version="2026.11.1",
            ),
            AuthorizedSourceRecord(
                dataset_id="neurovoz_corpus",
                dataset_version="v1",
                source_id="neurovoz_dua_roster",
                role="candidate",
                artifact_sha256=cand_sha,
                retrieval_reference="dua:neurovoz-corpus-v1-roster",
                authorization_ref="DUA-NV-2026-01",
                authorization_state="APPROVED",
                permitted_tasks=("sustained_vowel",),
                permitted_operations=("frozen_model_evaluation",),
                expiry_utc="2035-12-31T00:00:00Z",
                issuing_authority="VoxNeuro Scientific Governance Authority",
                registry_version="2026.11.1",
                dua_document_fingerprint=hashlib.sha256(b"signed-neurovoz-dua-2026").hexdigest(),
            ),
        ),
        authorized_reviewers=(
            AuthorizedReviewerRecord(
                reviewer_id="reviewer.alice@voxneuro.org",
                role="lead_validation_auditor",
                approval_status="APPROVED",
                permitted_evaluation_tasks=("sustained_vowel",),
                permitted_operations=("frozen_model_evaluation",),
                expiry_utc="2035-12-31T00:00:00Z",
            ),
        ),
    )
    signed_env = sign_authorization_registry(reg_payload, seed)

    dua_doc = tmp_path / "signed_neurovoz_dua.txt"
    dua_doc.write_bytes(b"signed-neurovoz-dua-2026")
    dua_fp = hashlib.sha256(dua_doc.read_bytes()).hexdigest()
    auth_rec = DatasetAccessRecord(
        dataset_id="neurovoz_corpus",
        dataset_version="v1",
        dataset_owner="Hospital General Universitario Gregorio Maranon",
        license_type="DUA_RESTRICTED",
        access_approval_state="APPROVED",
        dua_state="ACTIVE",
        permitted_tasks=["sustained_vowel"],
        permitted_data_processing_operations=["frozen_model_evaluation"],
        storage_restrictions="encrypted_research_vault",
        publication_restrictions="aggregate_only",
        expiration_date="2035-12-31",
        source_documentation="DUA-NV-2026-01-SIGNED",
        dua_document_fingerprint=dua_fp,
        authorization_ref="DUA-NV-2026-01",
        source_id="neurovoz_dua_roster",
        authorization_registry_id="VOXNEURO-M4-REG-2026",
        authorization_registry_version="2026.11.1",
        issuing_authority="VoxNeuro Scientific Governance Authority",
        dua_source_artifact_reference="dua:neurovoz-corpus-v1-roster",
        dua_verification_status="DOCUMENT_AUTHENTICATED",
    )
    db_file = tmp_path / "authority.db"
    run_migrations(db_file)
    conn = get_connection(db_file)
    try:
        register_dataset_access(conn, auth_rec)
        conn.commit()

        att = create_participant_independence_attestation(
            reference_dataset_id="uams_figshare_23849127",
            reference_dataset_version="v1",
            candidate_dataset_id="neurovoz_corpus",
            candidate_dataset_version="v1",
            signed_registry=signed_env,
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            reference_roster_source="uams_figshare_verified_roster",
            reference_authorization_ref="IRB-UAMS-2023-01",
            candidate_roster_source="neurovoz_dua_roster",
            candidate_authorization_ref="DUA-NV-2026-01",
            identity_basis_type="authorized_crosswalk",
            reviewer_identity="reviewer.alice@voxneuro.org",
            key=test_key,
        )

        feat_fp = feature_config_fingerprint(load_config("feature_config.yaml"))
        prep_fp = configuration_fingerprint(load_config("audio_config.yaml"))
        code_fp = project_code_fingerprint()

        rec = EvaluationProvenanceReceipt(
            candidate_domain_id="neurovoz_studio",
            dataset_id="neurovoz_corpus",
            dataset_version="v1",
            dataset_source="Hospital General Universitario Gregorio Marañón",
            authorization_status="AUTHORIZED_DUA",
            task_identifier="sustained_vowel",
            feature_schema_version=SCHEMA_VERSION,
            feature_schema_fingerprint=schema_fingerprint(),
            feature_config_fingerprint=feat_fp,
            preprocessing_config_fingerprint=prep_fp,
            code_fingerprint=code_fp,
            reference_feature_table_sha256=ref_sha,
            candidate_feature_table_sha256=cand_sha,
            num_recordings=1,
            num_unique_participants=1,
            diagnostic_label_provenance="clinical_neurologist",
            participant_overlap_status="VERIFIED_DISJOINT",
            duplicate_participant_count=0,
            duplicate_recording_count=0,
            feature_validation_status="PASSED",
            quality_exclusion_count=0,
            evaluation_protocol_id="VOXNEURO-M4-EXT-VAL-2026-V1",
            timestamp_utc="2026-11-12T12:00:00Z",
            independence_attestation=att.to_dict(),
            dua_expiration_date="2035-12-31",
            dua_document_fingerprint=dua_fp,
            permitted_operations=["frozen_model_evaluation"],
            frozen_model_sha256=FROZEN_REFERENCE_MODEL_SHA256,
            key_id="voxneuro-key-v1",
        )
        rec_hash = rec.compute_sha256()
        rec_hmac = rec.compute_hmac(test_key)
        valid_rec = EvaluationProvenanceReceipt(
            **{**rec.to_dict(), "receipt_sha256": rec_hash, "receipt_hmac": rec_hmac}
        )

        is_valid, reason = verify_evaluation_provenance_receipt(
            valid_rec,
            cand_csv,
            reference_csv_path=ref_csv,
            key=test_key,
            signed_registry=signed_env,
            expected_reviewer_id="reviewer.alice@voxneuro.org",
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            study_conn=conn,
            dua_document_path=dua_doc,
        )
        assert is_valid, f"Verification failed: {reason}"

        # Fails if authoritative study database is omitted (caller-supplied record cannot bypass)
        is_valid, reason = verify_evaluation_provenance_receipt(
            valid_rec,
            cand_csv,
            reference_csv_path=ref_csv,
            key=test_key,
            signed_registry=signed_env,
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            dataset_access_record=auth_rec,
            dua_document_path=dua_doc,
        )
        assert not is_valid
        assert "DATASET_AUTHORIZATION_NOT_VERIFIED" in reason

        # Fails if private model binary is missing during evaluation
        missing_model_path = tmp_path / "missing_model.joblib"
        with pytest.raises(FileNotFoundError, match="MODEL_ARTIFACT_NOT_VERIFIED"):
            evaluate_external_domain_with_provenance(
                valid_rec,
                cand_csv,
                ref_csv,
                bundle_path=missing_model_path,
                key=test_key,
                signed_registry=signed_env,
                reference_roster_path=ref_csv,
                candidate_roster_path=cand_csv,
                study_conn=conn,
                dua_document_path=dua_doc,
            )

        # Fails if receipt HMAC is tampered
        tampered_rec = EvaluationProvenanceReceipt(
            **{**valid_rec.to_dict(), "receipt_hmac": "wrong_hmac"}
        )
        is_valid, reason = verify_evaluation_provenance_receipt(
            tampered_rec,
            cand_csv,
            reference_csv_path=ref_csv,
            key=test_key,
            signed_registry=signed_env,
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            study_conn=conn,
        )
        assert not is_valid
        assert "authentication failed" in reason

        # Fails if reference table is missing
        is_valid, reason = verify_evaluation_provenance_receipt(
            valid_rec,
            cand_csv,
            reference_csv_path=None,
            key=test_key,
            signed_registry=signed_env,
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            study_conn=conn,
            dua_document_path=dua_doc,
        )
        assert not is_valid
        assert "Reference feature table file is required" in reason

        # Fails if independence attestation is missing
        no_att_rec = EvaluationProvenanceReceipt(
            **{**valid_rec.to_dict(), "independence_attestation": None, "receipt_hmac": ""}
        )
        signed_no_att = EvaluationProvenanceReceipt(
            **{
                **no_att_rec.to_dict(),
                "receipt_sha256": no_att_rec.compute_sha256(),
                "receipt_hmac": no_att_rec.compute_hmac(test_key),
            }
        )
        is_valid, reason = verify_evaluation_provenance_receipt(
            signed_no_att,
            cand_csv,
            reference_csv_path=ref_csv,
            key=test_key,
            signed_registry=signed_env,
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            study_conn=conn,
            dua_document_path=dua_doc,
        )
        assert not is_valid
        assert "INDEPENDENCE_NOT_VERIFIED" in reason

        # Fails if DUA status is pending
        pending_rec = EvaluationProvenanceReceipt(
            **{**valid_rec.to_dict(), "authorization_status": "PENDING_DUA", "receipt_hmac": ""}
        )
        signed_pending = EvaluationProvenanceReceipt(
            **{
                **pending_rec.to_dict(),
                "receipt_sha256": pending_rec.compute_sha256(),
                "receipt_hmac": pending_rec.compute_hmac(test_key),
            }
        )
        is_valid, reason = verify_evaluation_provenance_receipt(
            signed_pending,
            cand_csv,
            reference_csv_path=ref_csv,
            key=test_key,
            signed_registry=signed_env,
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            study_conn=conn,
            dua_document_path=dua_doc,
        )
        assert not is_valid
        assert "not authorized" in reason

        # Fails if DUA is expired
        expired_rec = EvaluationProvenanceReceipt(
            **{
                **valid_rec.to_dict(),
                "dua_expiration_date": "2020-01-01",
                "receipt_hmac": "",
            }
        )
        signed_expired = EvaluationProvenanceReceipt(
            **{
                **expired_rec.to_dict(),
                "receipt_sha256": expired_rec.compute_sha256(),
                "receipt_hmac": expired_rec.compute_hmac(test_key),
            }
        )
        is_valid, reason = verify_evaluation_provenance_receipt(
            signed_expired,
            cand_csv,
            reference_csv_path=ref_csv,
            key=test_key,
            signed_registry=signed_env,
            reference_roster_path=ref_csv,
            candidate_roster_path=cand_csv,
            study_conn=conn,
            dua_document_path=dua_doc,
        )
        assert not is_valid
        assert "expired" in reason
    finally:
        conn.close()
