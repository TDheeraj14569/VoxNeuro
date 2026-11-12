"""Unit tests for M4 participant independence, roster binding, and receipt verification."""

from __future__ import annotations

import hashlib

import pandas as pd
import pytest

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
    verify_evaluation_provenance_receipt,
    verify_participant_independence,
    verify_participant_independence_attestation,
)
from voxneuro.modeling.domain_registry import load_domain_registry
from voxneuro.modeling.trust_registry import (
    DEFAULT_AUTHORITY_KEY_ID,
    AuthorizationTrustRegistry,
    AuthorizationTrustRootError,
    AuthorizedReviewerRecord,
    AuthorizedSourceRecord,
    generate_ed25519_keypair,
    sign_authorization_registry,
)
from voxneuro.provenance import project_code_fingerprint
from voxneuro.study.consent import register_dataset_access
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.schema import DatasetAccessRecord


def _make_signed_registry(
    seed: bytes,
    ref_sha: str,
    cand_sha: str,
    *,
    reviewer_id: str = "auditor.jane@voxneuro.org",
    auth_ref_cand: str = "CANDIDATE-DUA-2026-V1",
    cand_dua_fp: str = "",
) -> trust_registry.SignedAuthorizationRegistry:
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
                authorization_ref="UAMS-IRB-EXEMPT-2023",
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
                source_id="neurovoz_authorized_roster",
                role="candidate",
                artifact_sha256=cand_sha,
                retrieval_reference="dua:neurovoz-corpus-v1-roster",
                authorization_ref=auth_ref_cand,
                authorization_state="APPROVED",
                permitted_tasks=("sustained_vowel",),
                permitted_operations=("frozen_model_evaluation",),
                expiry_utc="2035-12-31T00:00:00Z",
                issuing_authority="VoxNeuro Scientific Governance Authority",
                registry_version="2026.11.1",
                dua_document_fingerprint=cand_dua_fp,
            ),
        ),
        authorized_reviewers=(
            AuthorizedReviewerRecord(
                reviewer_id=reviewer_id,
                role="lead_validation_auditor",
                approval_status="APPROVED",
                permitted_evaluation_tasks=("sustained_vowel",),
                permitted_operations=("frozen_model_evaluation",),
                expiry_utc="2035-12-31T00:00:00Z",
            ),
        ),
    )
    return sign_authorization_registry(reg_payload, seed)


@pytest.fixture
def m4_setup(tmp_path, monkeypatch):
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
    test_key = "test_hmac_secret_key_m4_2026"
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", test_key)

    ref_csv = tmp_path / "ref_uams.csv"
    ref_row = {"participant_id": "R01", "diagnostic_group": "HC"}
    for f in FEATURE_NAMES:
        ref_row[f] = 0.1
    pd.DataFrame([ref_row]).to_csv(ref_csv, index=False)
    ref_sha = hashlib.sha256(ref_csv.read_bytes()).hexdigest()

    cand_csv = tmp_path / "cand_neurovoz.csv"
    cand_row = {"participant_id": "C01", "diagnostic_group": "PD"}
    for f in FEATURE_NAMES:
        cand_row[f] = 0.2
    pd.DataFrame([cand_row]).to_csv(cand_csv, index=False)
    cand_sha = hashlib.sha256(cand_csv.read_bytes()).hexdigest()

    ref_roster = tmp_path / "ref_roster.txt"
    ref_roster.write_text("participant_id\nR01\n", encoding="utf-8")
    ref_roster_sha = hashlib.sha256(ref_roster.read_bytes()).hexdigest()
    cand_roster = tmp_path / "cand_roster.txt"
    cand_roster.write_text("participant_id\nC01\n", encoding="utf-8")
    cand_roster_sha = hashlib.sha256(cand_roster.read_bytes()).hexdigest()

    dua_doc = tmp_path / "authorized_neurovoz_dua.txt"
    dua_doc.write_bytes(b"authorized-neurovoz-dua-v1")
    dua_fp = hashlib.sha256(dua_doc.read_bytes()).hexdigest()

    signed_env = _make_signed_registry(
        seed,
        ref_roster_sha,
        cand_roster_sha,
        cand_dua_fp=dua_fp,
    )

    db_file = tmp_path / "m4_gov.db"
    run_migrations(db_file)
    conn = get_connection(db_file)
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
        source_documentation="CANDIDATE-DUA-2026-V1-SIGNED",
        dua_document_fingerprint=dua_fp,
        authorization_ref="CANDIDATE-DUA-2026-V1",
        source_id="neurovoz_authorized_roster",
        authorization_registry_id="VOXNEURO-M4-REG-2026",
        authorization_registry_version="2026.11.1",
        issuing_authority="VoxNeuro Scientific Governance Authority",
        dua_source_artifact_reference="dua:neurovoz-corpus-v1-roster",
        dua_verification_status="DOCUMENT_AUTHENTICATED",
    )
    register_dataset_access(conn, auth_rec)
    conn.commit()

    att = create_participant_independence_attestation(
        reference_dataset_id="uams_figshare_23849127",
        reference_dataset_version="v1",
        candidate_dataset_id="neurovoz_corpus",
        candidate_dataset_version="v1",
        signed_registry=signed_env,
        reference_roster_path=ref_roster,
        candidate_roster_path=cand_roster,
        reference_roster_source="uams_figshare_verified_roster",
        reference_authorization_ref="UAMS-IRB-EXEMPT-2023",
        candidate_roster_source="neurovoz_authorized_roster",
        candidate_authorization_ref="CANDIDATE-DUA-2026-V1",
        identity_basis_type="authorized_crosswalk",
        reviewer_identity="auditor.jane@voxneuro.org",
        key=test_key,
    )

    feat_fp = feature_config_fingerprint(load_config("feature_config.yaml"))
    prep_fp = configuration_fingerprint(load_config("audio_config.yaml"))
    code_fp = project_code_fingerprint()

    receipt = EvaluationProvenanceReceipt(
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
    rec_hash = receipt.compute_sha256()
    rec_hmac = receipt.compute_hmac(test_key)
    valid_receipt = EvaluationProvenanceReceipt(
        **{**receipt.to_dict(), "receipt_sha256": rec_hash, "receipt_hmac": rec_hmac}
    )

    try:
        yield {
            "seed": seed,
            "test_key": test_key,
            "ref_csv": ref_csv,
            "cand_csv": cand_csv,
            "ref_roster": ref_roster,
            "cand_roster": cand_roster,
            "ref_roster_sha": ref_roster_sha,
            "cand_roster_sha": cand_roster_sha,
            "signed_env": signed_env,
            "conn": conn,
            "auth_rec": auth_rec,
            "dua_doc": dua_doc,
            "att": att,
            "valid_receipt": valid_receipt,
        }
    finally:
        conn.close()


def test_independence_verification_requires_common_identity_basis(m4_setup):
    """Disparate pseudonym systems without a crosswalk return INDEPENDENCE_NOT_VERIFIED."""
    res = verify_participant_independence(
        ["R01", "R02"],
        ["C01", "C02"],
        key=m4_setup["test_key"],
        identity_basis_type="disparate_pseudonyms",  # No common identity basis
    )
    assert res["overlap_status"] == "INDEPENDENCE_NOT_VERIFIED"
    assert res["is_disjoint"] is False
    assert "independently assigned pseudonyms cannot establish" in res["reason"]


def test_independence_attestation_to_roster_binding(m4_setup):
    """Attestation contains exact roster checksums, roster fingerprint, and explicit reviewer."""
    att = m4_setup["att"]
    assert (
        att.reference_roster_sha256
        == hashlib.sha256(m4_setup["ref_roster"].read_bytes()).hexdigest()
    )
    assert len(att.reference_roster_sha256) == 64
    assert (
        att.candidate_roster_sha256
        == hashlib.sha256(m4_setup["cand_roster"].read_bytes()).hexdigest()
    )
    assert len(att.candidate_roster_sha256) == 64
    assert att.roster_fingerprint != ""
    assert att.reviewer_identity == "auditor.jane@voxneuro.org"
    assert att.authentication_method == "HMAC-SHA256"


def test_attestation_rejects_missing_provenance_defaults(m4_setup):
    """Creating attestation without signed trust registry or explicit roster/refs must fail."""
    with pytest.raises(AuthorizationTrustRootError, match="AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED"):
        create_participant_independence_attestation(
            reference_dataset_id="uams_figshare_23849127",
            reference_dataset_version="v1",
            candidate_dataset_id="neurovoz_corpus",
            candidate_dataset_version="v1",
            key=m4_setup["test_key"],
        )

    with pytest.raises(ValueError, match="INDEPENDENCE_NOT_VERIFIED"):
        create_participant_independence_attestation(
            reference_dataset_id="uams_figshare_23849127",
            reference_dataset_version="v1",
            candidate_dataset_id="neurovoz_corpus",
            candidate_dataset_version="v1",
            signed_registry=m4_setup["signed_env"],
            key=m4_setup["test_key"],
        )


def test_attestation_rejects_tampered_source_roster_file(m4_setup):
    """Modifying a source roster file after signing invalidates attestation verification."""
    ok, _ = verify_participant_independence_attestation(
        m4_setup["att"],
        expected_reference=("uams_figshare_23849127", "v1"),
        expected_candidate=("neurovoz_corpus", "v1"),
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
    )
    assert ok

    # Tamper candidate roster file bytes (add participant / alter file)
    m4_setup["cand_roster"].write_text("participant_id\nC01\nC99\n", encoding="utf-8")
    ok_after, reason = verify_participant_independence_attestation(
        m4_setup["att"],
        expected_reference=("uams_figshare_23849127", "v1"),
        expected_candidate=("neurovoz_corpus", "v1"),
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
    )
    assert not ok_after
    assert "INDEPENDENCE_NOT_VERIFIED" in reason


def test_attestation_rejects_unauthorized_reviewer_or_source(m4_setup):
    """Attestation fails closed when signed trust registry excludes reviewer or source ref."""
    other_rev_reg = _make_signed_registry(
        m4_setup["seed"],
        m4_setup["ref_roster_sha"],
        m4_setup["cand_roster_sha"],
        reviewer_id="different.reviewer@voxneuro.org",
    )
    ok_rev, reason_rev = verify_participant_independence_attestation(
        m4_setup["att"],
        expected_reference=("uams_figshare_23849127", "v1"),
        expected_candidate=("neurovoz_corpus", "v1"),
        key=m4_setup["test_key"],
        signed_registry=other_rev_reg,
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
    )
    assert not ok_rev
    assert "INDEPENDENCE_NOT_VERIFIED" in reason_rev

    other_src_reg = _make_signed_registry(
        m4_setup["seed"],
        m4_setup["ref_roster_sha"],
        m4_setup["cand_roster_sha"],
        auth_ref_cand="OTHER-REF",
    )
    ok_src, reason_src = verify_participant_independence_attestation(
        m4_setup["att"],
        expected_reference=("uams_figshare_23849127", "v1"),
        expected_candidate=("neurovoz_corpus", "v1"),
        key=m4_setup["test_key"],
        signed_registry=other_src_reg,
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
    )
    assert not ok_src
    assert "INDEPENDENCE_NOT_VERIFIED" in reason_src


def test_receipt_rejects_forged_approval_against_pending_or_expired_db_dua(m4_setup):
    """Receipt claiming AUTHORIZED_DUA fails when DB DUA is PENDING, expired, or scoped out."""
    # 1. Pending in DB despite signed receipt claiming AUTHORIZED_DUA
    pending_rec = DatasetAccessRecord(
        **{**m4_setup["auth_rec"].to_dict(), "access_approval_state": "PENDING"}
    )
    register_dataset_access(m4_setup["conn"], pending_rec)
    m4_setup["conn"].commit()
    ok_p, reason_p = verify_evaluation_provenance_receipt(
        m4_setup["valid_receipt"],
        m4_setup["cand_csv"],
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
        study_conn=m4_setup["conn"],
    )
    assert not ok_p
    assert "DATASET_AUTHORIZATION_NOT_VERIFIED" in reason_p

    # 2. Expired in DB
    expired_rec = DatasetAccessRecord(
        **{**m4_setup["auth_rec"].to_dict(), "expiration_date": "2020-01-01"}
    )
    register_dataset_access(m4_setup["conn"], expired_rec)
    m4_setup["conn"].commit()
    ok_e, reason_e = verify_evaluation_provenance_receipt(
        m4_setup["valid_receipt"],
        m4_setup["cand_csv"],
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
        study_conn=m4_setup["conn"],
    )
    assert not ok_e
    assert "DATASET_AUTHORIZATION_NOT_VERIFIED" in reason_e

    # 3. Operation not permitted in DB
    disallowed_op_rec = DatasetAccessRecord(
        **{
            **m4_setup["auth_rec"].to_dict(),
            "permitted_data_processing_operations": ["statistical_audit"],
        }
    )
    register_dataset_access(m4_setup["conn"], disallowed_op_rec)
    m4_setup["conn"].commit()
    ok_o, reason_o = verify_evaluation_provenance_receipt(
        m4_setup["valid_receipt"],
        m4_setup["cand_csv"],
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
        study_conn=m4_setup["conn"],
    )
    assert not ok_o
    assert "DATASET_AUTHORIZATION_NOT_VERIFIED" in reason_o


def test_receipt_rejects_unregistered_key_id(m4_setup):
    """Receipt with unknown key_id must be rejected."""
    bad_key_rec = EvaluationProvenanceReceipt(
        **{**m4_setup["valid_receipt"].to_dict(), "key_id": "retired_key_v0", "receipt_hmac": ""}
    )
    signed_bad = EvaluationProvenanceReceipt(
        **{
            **bad_key_rec.to_dict(),
            "receipt_sha256": bad_key_rec.compute_sha256(),
            "receipt_hmac": bad_key_rec.compute_hmac(m4_setup["test_key"]),
        }
    )
    is_ok, reason = verify_evaluation_provenance_receipt(
        signed_bad,
        m4_setup["cand_csv"],
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        study_conn=m4_setup["conn"],
    )
    assert not is_ok
    assert "unknown, retired, or invalid" in reason


def test_receipt_rejects_dataset_id_mismatch(m4_setup):
    """Receipt with dataset_id differing from registered domain metadata is rejected."""
    bad_ds_rec = EvaluationProvenanceReceipt(
        **{
            **m4_setup["valid_receipt"].to_dict(),
            "dataset_id": "unregistered_dataset_xyz",
            "receipt_hmac": "",
        }
    )
    signed_bad = EvaluationProvenanceReceipt(
        **{
            **bad_ds_rec.to_dict(),
            "receipt_sha256": bad_ds_rec.compute_sha256(),
            "receipt_hmac": bad_ds_rec.compute_hmac(m4_setup["test_key"]),
        }
    )
    is_ok, reason = verify_evaluation_provenance_receipt(
        signed_bad,
        m4_setup["cand_csv"],
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        study_conn=m4_setup["conn"],
    )
    assert not is_ok
    assert "Dataset ID mismatch" in reason


def test_receipt_rejects_model_sha_mismatch(m4_setup):
    """Receipt with missing or incorrect frozen model SHA is rejected."""
    bad_model_rec = EvaluationProvenanceReceipt(
        **{
            **m4_setup["valid_receipt"].to_dict(),
            "frozen_model_sha256": "00" * 32,
            "receipt_hmac": "",
        }
    )
    signed_bad = EvaluationProvenanceReceipt(
        **{
            **bad_model_rec.to_dict(),
            "receipt_sha256": bad_model_rec.compute_sha256(),
            "receipt_hmac": bad_model_rec.compute_hmac(m4_setup["test_key"]),
        }
    )
    is_ok, reason = verify_evaluation_provenance_receipt(
        signed_bad,
        m4_setup["cand_csv"],
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
        study_conn=m4_setup["conn"],
        dua_document_path=m4_setup["dua_doc"],
    )
    assert not is_ok
    assert "Frozen model SHA-256 mismatch" in reason


def test_receipt_rejects_feature_config_fingerprint_mismatch(m4_setup):
    """Receipt with mismatched feature config fingerprint is rejected."""
    bad_fp_rec = EvaluationProvenanceReceipt(
        **{
            **m4_setup["valid_receipt"].to_dict(),
            "feature_config_fingerprint": "bad_fp" * 16,
            "receipt_hmac": "",
        }
    )
    signed_bad = EvaluationProvenanceReceipt(
        **{
            **bad_fp_rec.to_dict(),
            "receipt_sha256": bad_fp_rec.compute_sha256(),
            "receipt_hmac": bad_fp_rec.compute_hmac(m4_setup["test_key"]),
        }
    )
    is_ok, reason = verify_evaluation_provenance_receipt(
        signed_bad,
        m4_setup["cand_csv"],
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
        study_conn=m4_setup["conn"],
        dua_document_path=m4_setup["dua_doc"],
    )
    assert not is_ok
    assert "Feature configuration fingerprint mismatch" in reason


def test_receipt_rejects_candidate_table_with_non_numeric_features(m4_setup, tmp_path):
    """Receipt validation parses candidate table and rejects non-numeric or NaN features."""
    bad_csv = tmp_path / "bad_non_num.csv"
    row = {"participant_id": "C01", "diagnostic_group": "PD"}
    for f in FEATURE_NAMES:
        row[f] = 0.5
    row["jitter_local"] = "NOT_A_NUMBER"
    pd.DataFrame([row]).to_csv(bad_csv, index=False)
    bad_sha = hashlib.sha256(bad_csv.read_bytes()).hexdigest()

    rec = EvaluationProvenanceReceipt(
        **{
            **m4_setup["valid_receipt"].to_dict(),
            "candidate_feature_table_sha256": bad_sha,
            "receipt_hmac": "",
        }
    )
    signed = EvaluationProvenanceReceipt(
        **{
            **rec.to_dict(),
            "receipt_sha256": rec.compute_sha256(),
            "receipt_hmac": rec.compute_hmac(m4_setup["test_key"]),
        }
    )
    is_ok, reason = verify_evaluation_provenance_receipt(
        signed,
        bad_csv,
        m4_setup["ref_csv"],
        key=m4_setup["test_key"],
        signed_registry=m4_setup["signed_env"],
        reference_roster_path=m4_setup["ref_roster"],
        candidate_roster_path=m4_setup["cand_roster"],
        study_conn=m4_setup["conn"],
        dua_document_path=m4_setup["dua_doc"],
    )
    assert not is_ok
    assert "not numeric" in reason


def test_evaluate_external_domain_cli_fails_closed_without_governance_flags(tmp_path):
    """scripts/evaluate_external_domain.py exits non-zero if governance args are omitted."""
    import subprocess
    import sys

    cand_csv = tmp_path / "cand.csv"
    cand_csv.write_text("participant_id,diagnostic_group\nC1,PD\n", encoding="utf-8")
    receipt_json = tmp_path / "receipt.json"
    receipt_json.write_text("{}", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_external_domain.py",
            "--features-path",
            str(cand_csv),
            "--receipt-path",
            str(receipt_json),
            "--out-dir",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    combined = proc.stdout + proc.stderr
    assert "NOT_VERIFIED" in combined


def test_italian_ipvs_acquisition_fields_allow_unknown():
    """Italian IPVS metadata correctly sets unknown/null acquisition fields without crash."""
    reg = load_domain_registry()
    ipvs = reg.get_domain("italian_parkinsons_headset")
    assert ipvs.metadata.original_sample_rate is None
    assert ipvs.metadata.bit_depth is None
    assert ipvs.metadata.channel_count is None
    assert ipvs.metadata.device_category == "unknown"
    assert ipvs.metadata.microphone_type == "unknown"
    assert ipvs.research_evaluation_eligible is False
