"""Unit tests for M4 Ed25519 authorization trust registry and dataset access authenticity."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

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
    evaluate_external_domain_with_provenance,
    verify_evaluation_provenance_receipt,
    verify_participant_independence_attestation,
)
from voxneuro.modeling.trust_registry import (
    DEFAULT_AUTHORITY_KEY_ID,
    AuthorizationTrustRegistry,
    AuthorizationTrustRootError,
    AuthorizedReviewerRecord,
    AuthorizedSourceRecord,
    SignedAuthorizationRegistry,
    ed25519_public_key_from_seed,
    ed25519_sign,
    ed25519_verify,
    generate_ed25519_keypair,
    load_and_verify_authorization_registry,
    sign_authorization_registry,
    verify_signed_authorization_registry,
)
from voxneuro.provenance import project_code_fingerprint
from voxneuro.study.consent import register_dataset_access
from voxneuro.study.database import get_connection, run_migrations
from voxneuro.study.schema import DatasetAccessRecord


def _build_signed_env(
    ref_sha: str,
    cand_sha: str,
    *,
    seed: bytes,
    ref_version: str = "v1",
    cand_version: str = "v1",
    expires_utc: str = "2035-12-31T00:00:00Z",
    reviewer_id: str = "auditor.jane@voxneuro.org",
    reviewer_role: str = "lead_validation_auditor",
    reviewer_status: str = "APPROVED",
    reviewer_expiry: str = "2035-12-31T00:00:00Z",
    cand_dua_fp: str = "",
    cand_auth_ref: str = "CANDIDATE-DUA-2026-V1",
    cand_source_id: str = "neurovoz_authorized_roster",
    cand_auth_state: str = "APPROVED",
    cand_tasks: tuple[str, ...] = ("sustained_vowel",),
    cand_ops: tuple[str, ...] = ("frozen_model_evaluation",),
    cand_expiry: str = "2035-12-31T00:00:00Z",
    cand_issuing_authority: str = "VoxNeuro Scientific Governance Authority",
    cand_registry_version: str = "2026.11.1",
    cand_retrieval_ref: str = "dua:neurovoz-corpus-v1-roster",
) -> SignedAuthorizationRegistry:
    reg = AuthorizationTrustRegistry(
        registry_id="VOXNEURO-M4-REG-2026",
        registry_version="2026.11.1",
        issuing_authority="VoxNeuro Scientific Governance Authority",
        created_utc="2026-01-01T00:00:00Z",
        expires_utc=expires_utc,
        review_date_utc="2027-01-01T00:00:00Z",
        key_id=DEFAULT_AUTHORITY_KEY_ID,
        signature_algorithm="Ed25519",
        authorized_sources=(
            AuthorizedSourceRecord(
                dataset_id="uams_figshare_23849127",
                dataset_version=ref_version,
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
                dataset_version=cand_version,
                source_id=cand_source_id,
                role="candidate",
                artifact_sha256=cand_sha,
                retrieval_reference=cand_retrieval_ref,
                authorization_ref=cand_auth_ref,
                authorization_state=cand_auth_state,
                permitted_tasks=cand_tasks,
                permitted_operations=cand_ops,
                expiry_utc=cand_expiry,
                issuing_authority=cand_issuing_authority,
                registry_version=cand_registry_version,
                dua_document_fingerprint=cand_dua_fp,
            ),
        ),
        authorized_reviewers=(
            AuthorizedReviewerRecord(
                reviewer_id=reviewer_id,
                role=reviewer_role,
                approval_status=reviewer_status,
                permitted_evaluation_tasks=("sustained_vowel",),
                permitted_operations=("frozen_model_evaluation",),
                expiry_utc=reviewer_expiry,
            ),
        ),
    )
    return sign_authorization_registry(reg, seed)


@pytest.fixture
def m4_trust_env(tmp_path, monkeypatch):
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
    hmac_key = "test_m4_trust_hmac_secret_2026"
    monkeypatch.setenv("VOXNEURO_HMAC_KEY", hmac_key)

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

    ref_roster = tmp_path / "ref_roster.csv"
    ref_roster.write_text("participant_id\nR01\n", encoding="utf-8")
    ref_roster_sha = hashlib.sha256(ref_roster.read_bytes()).hexdigest()

    cand_roster = tmp_path / "cand_roster.csv"
    cand_roster.write_text("participant_id\nC01\n", encoding="utf-8")
    cand_roster_sha = hashlib.sha256(cand_roster.read_bytes()).hexdigest()

    dua_doc = tmp_path / "authorized_neurovoz_dua.txt"
    dua_doc.write_bytes(b"authorized-neurovoz-dua-2026-v1")
    dua_fp = hashlib.sha256(dua_doc.read_bytes()).hexdigest()

    signed_env = _build_signed_env(
        ref_roster_sha,
        cand_roster_sha,
        seed=seed,
        cand_dua_fp=dua_fp,
    )

    db_file = tmp_path / "m4_authority.db"
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
        key=hmac_key,
    )

    rec_base = EvaluationProvenanceReceipt(
        candidate_domain_id="neurovoz_studio",
        dataset_id="neurovoz_corpus",
        dataset_version="v1",
        dataset_source="Hospital General Universitario Gregorio Maranon",
        authorization_status="AUTHORIZED_DUA",
        task_identifier="sustained_vowel",
        feature_schema_version=SCHEMA_VERSION,
        feature_schema_fingerprint=schema_fingerprint(),
        feature_config_fingerprint=feature_config_fingerprint(load_config("feature_config.yaml")),
        preprocessing_config_fingerprint=configuration_fingerprint(
            load_config("audio_config.yaml")
        ),
        code_fingerprint=project_code_fingerprint(),
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
        dua_expiration_date="2035-12-31",
        dua_document_fingerprint=dua_fp,
        permitted_operations=["frozen_model_evaluation"],
        frozen_model_sha256=FROZEN_REFERENCE_MODEL_SHA256,
        independence_attestation=att.to_dict(),
        key_id="voxneuro-key-v1",
    )
    receipt = EvaluationProvenanceReceipt(
        **{
            **rec_base.to_dict(),
            "receipt_sha256": rec_base.compute_sha256(),
            "receipt_hmac": rec_base.compute_hmac(hmac_key),
        }
    )

    try:
        yield {
            "seed": seed,
            "pub": pub,
            "hmac_key": hmac_key,
            "ref_csv": ref_csv,
            "cand_csv": cand_csv,
            "ref_roster": ref_roster,
            "cand_roster": cand_roster,
            "ref_roster_sha": ref_roster_sha,
            "cand_roster_sha": cand_roster_sha,
            "signed_env": signed_env,
            "conn": conn,
            "db_file": db_file,
            "auth_rec": auth_rec,
            "dua_doc": dua_doc,
            "att": att,
            "receipt": receipt,
        }
    finally:
        conn.close()


def test_ed25519_rfc8032_vectors():
    """Ed25519 primitives match official RFC 8032 Section 7.1 test vectors."""
    vectors = [
        (
            "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
            "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
            b"",
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
            "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
        ),
        (
            "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
            "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
            b"\x72",
            "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
            "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
        ),
        (
            "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
            "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
            b"\xaf\x82",
            "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
            "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
        ),
    ]
    for sk_hex, pk_hex, msg, sig_hex in vectors:
        sk = bytes.fromhex(sk_hex)
        pk = bytes.fromhex(pk_hex)
        sig = bytes.fromhex(sig_hex)
        assert ed25519_public_key_from_seed(sk) == pk
        assert ed25519_sign(sk, msg) == sig
        assert ed25519_verify(pk, msg, sig) is True
        assert ed25519_verify(pk, msg + b"\x00", sig) is False


def test_registry_signature_and_trust_anchor_failures(m4_trust_env, tmp_path):
    """Unsigned, altered, untrusted-key, self-key, or expired registries are rejected."""
    env = m4_trust_env

    # 1. Missing registry fails closed
    ok_missing, msg_missing, _ = verify_signed_authorization_registry(None)
    assert not ok_missing and "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED" in msg_missing

    # 2. Unsigned registry rejected
    unsigned = SignedAuthorizationRegistry(
        registry=env["signed_env"].registry,
        signature_hex="",
        key_id=DEFAULT_AUTHORITY_KEY_ID,
    )
    ok_u, msg_u, _ = verify_signed_authorization_registry(unsigned)
    assert not ok_u and "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED" in msg_u

    # 3. Altered registry contents invalidate signature
    tampered_reg = AuthorizationTrustRegistry(
        **{**env["signed_env"].registry.to_dict(), "registry_version": "2026.99.9"}
    )
    tampered_env = SignedAuthorizationRegistry(
        registry=tampered_reg,
        signature_hex=env["signed_env"].signature_hex,
        key_id=DEFAULT_AUTHORITY_KEY_ID,
    )
    ok_t, msg_t, _ = verify_signed_authorization_registry(tampered_env)
    assert not ok_t and "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED" in msg_t

    # 4. Registry signed by untrusted key rejected
    rogue_seed, rogue_pub = generate_ed25519_keypair()
    rogue_env = _build_signed_env(env["ref_roster_sha"], env["cand_roster_sha"], seed=rogue_seed)
    ok_r, msg_r, _ = verify_signed_authorization_registry(rogue_env)
    assert not ok_r and "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED" in msg_r

    # 5. Embedded public key self-declaration rejected
    reg_p = tmp_path / "self_signed.json"
    sig_p = tmp_path / "self_signed.sig"
    payload = env["signed_env"].registry.to_dict()
    payload["public_key"] = rogue_pub.hex()
    reg_p.write_text(json.dumps(payload), encoding="utf-8")
    sig_p.write_text(rogue_env.signature_hex, encoding="utf-8")
    with pytest.raises(AuthorizationTrustRootError, match="AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED"):
        load_and_verify_authorization_registry(reg_p, sig_p)

    # 6. Expired registry rejected
    expired_env = _build_signed_env(
        env["ref_roster_sha"],
        env["cand_roster_sha"],
        seed=env["seed"],
        expires_utc="2026-06-01T00:00:00Z",
    )
    ok_e, msg_e, _ = verify_signed_authorization_registry(expired_env)
    assert not ok_e and "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED" in msg_e

    # 7. Callers cannot inject a dynamic trust anchor parameter into verification functions
    import inspect

    sig = inspect.signature(verify_signed_authorization_registry)
    assert "public_key" not in sig.parameters
    assert "trust_anchors" not in sig.parameters


def test_reviewer_authorization_failures(m4_trust_env):
    """Unknown, insufficient-role, revoked, or expired reviewers are rejected."""
    env = m4_trust_env
    common = {
        "reference_dataset_id": "uams_figshare_23849127",
        "reference_dataset_version": "v1",
        "candidate_dataset_id": "neurovoz_corpus",
        "candidate_dataset_version": "v1",
        "reference_roster_path": env["ref_roster"],
        "candidate_roster_path": env["cand_roster"],
        "reference_roster_source": "uams_figshare_verified_roster",
        "reference_authorization_ref": "UAMS-IRB-EXEMPT-2023",
        "candidate_roster_source": "neurovoz_authorized_roster",
        "candidate_authorization_ref": "CANDIDATE-DUA-2026-V1",
        "identity_basis_type": "authorized_crosswalk",
        "key": env["hmac_key"],
    }

    # Unknown reviewer
    with pytest.raises(PermissionError, match="INDEPENDENCE_NOT_VERIFIED"):
        create_participant_independence_attestation(
            **common, signed_registry=env["signed_env"], reviewer_identity="unknown@evil.org"
        )

    # Insufficient role
    low_role_env = _build_signed_env(
        env["ref_roster_sha"],
        env["cand_roster_sha"],
        seed=env["seed"],
        reviewer_role="observer",
    )
    with pytest.raises(PermissionError, match="INDEPENDENCE_NOT_VERIFIED"):
        create_participant_independence_attestation(
            **common, signed_registry=low_role_env, reviewer_identity="auditor.jane@voxneuro.org"
        )

    # Revoked reviewer
    revoked_env = _build_signed_env(
        env["ref_roster_sha"],
        env["cand_roster_sha"],
        seed=env["seed"],
        reviewer_status="REVOKED",
    )
    with pytest.raises(PermissionError, match="INDEPENDENCE_NOT_VERIFIED"):
        create_participant_independence_attestation(
            **common, signed_registry=revoked_env, reviewer_identity="auditor.jane@voxneuro.org"
        )

    # Expired reviewer approval
    expired_rev_env = _build_signed_env(
        env["ref_roster_sha"],
        env["cand_roster_sha"],
        seed=env["seed"],
        reviewer_expiry="2020-01-01T00:00:00Z",
    )
    with pytest.raises(PermissionError, match="INDEPENDENCE_NOT_VERIFIED"):
        create_participant_independence_attestation(
            **common, signed_registry=expired_rev_env, reviewer_identity="auditor.jane@voxneuro.org"
        )


def test_source_authorization_and_hmac_bypass_rejected(m4_trust_env):
    """Source version mismatch, roster tamper, or HMAC alone without valid source are rejected."""
    env = m4_trust_env

    # Version mismatch between registry and requested candidate dataset
    wrong_ver_env = _build_signed_env(
        env["ref_roster_sha"],
        env["cand_roster_sha"],
        seed=env["seed"],
        cand_version="v2",
    )
    with pytest.raises(PermissionError, match="INDEPENDENCE_NOT_VERIFIED"):
        create_participant_independence_attestation(
            reference_dataset_id="uams_figshare_23849127",
            reference_dataset_version="v1",
            candidate_dataset_id="neurovoz_corpus",
            candidate_dataset_version="v1",
            signed_registry=wrong_ver_env,
            reference_roster_path=env["ref_roster"],
            candidate_roster_path=env["cand_roster"],
            reference_roster_source="uams_figshare_verified_roster",
            reference_authorization_ref="UAMS-IRB-EXEMPT-2023",
            candidate_roster_source="neurovoz_authorized_roster",
            candidate_authorization_ref="CANDIDATE-DUA-2026-V1",
            identity_basis_type="authorized_crosswalk",
            reviewer_identity="auditor.jane@voxneuro.org",
            key=env["hmac_key"],
        )

    # Changed roster file invalidates an already HMAC-signed attestation
    env["cand_roster"].write_text("participant_id\nC01\nC02\n", encoding="utf-8")
    ok_t, msg_t = verify_participant_independence_attestation(
        env["att"],
        expected_reference=("uams_figshare_23849127", "v1"),
        expected_candidate=("neurovoz_corpus", "v1"),
        key=env["hmac_key"],
        signed_registry=env["signed_env"],
        reference_roster_path=env["ref_roster"],
        candidate_roster_path=env["cand_roster"],
    )
    assert not ok_t and "INDEPENDENCE_NOT_VERIFIED" in msg_t

    # HMAC alone over an unauthorized source cannot bypass signed trust registry
    env["cand_roster"].write_text("participant_id\nC01\n", encoding="utf-8")
    from voxneuro.modeling.domain_evaluation import IndependenceAttestation

    fake_src_att = IndependenceAttestation(
        **{
            **env["att"].to_dict(),
            "candidate_roster_source": "rogue_unlisted_source",
            "attestation_hmac": "",
        }
    )
    signed_fake_src = IndependenceAttestation(
        **{
            **fake_src_att.to_dict(),
            "attestation_hmac": fake_src_att.compute_hmac(env["hmac_key"]),
        }
    )
    ok_fs, msg_fs = verify_participant_independence_attestation(
        signed_fake_src,
        expected_reference=("uams_figshare_23849127", "v1"),
        expected_candidate=("neurovoz_corpus", "v1"),
        key=env["hmac_key"],
        signed_registry=env["signed_env"],
        reference_roster_path=env["ref_roster"],
        candidate_roster_path=env["cand_roster"],
    )
    assert not ok_fs and "INDEPENDENCE_NOT_VERIFIED" in msg_fs


def test_tampered_trust_anchor_yaml_fails_closed(m4_trust_env, monkeypatch):
    """Altering configs/m4_trust_anchors.yaml out of sync with compiled pin fails closed."""
    _, rogue_pub = generate_ed25519_keypair()
    tampered_yaml = m4_trust_env["db_file"].parent / "tampered_anchors.yaml"
    tampered_yaml.write_text(
        "schema_version: voxneuro.m4_trust_anchors.v1\n"
        "authority_name: Rogue\n"
        "signature_algorithm: Ed25519\n"
        "pinned_public_keys:\n"
        f'  {DEFAULT_AUTHORITY_KEY_ID}: "{rogue_pub.hex()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(trust_registry, "PINNED_TRUST_ANCHORS_PATH", tampered_yaml)
    ok_cfg, msg_cfg, _ = verify_signed_authorization_registry(m4_trust_env["signed_env"])
    assert not ok_cfg and "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED" in msg_cfg


def test_dataset_access_database_authenticity_required(m4_trust_env, tmp_path):
    """Caller-supplied DatasetAccessRecord objects cannot bypass authoritative DB lookup."""
    env = m4_trust_env

    # 1. Valid authoritative DB record + valid signed trust registry + DUA artifact passes
    ok_valid, msg_valid = verify_evaluation_provenance_receipt(
        env["receipt"],
        env["cand_csv"],
        env["ref_csv"],
        key=env["hmac_key"],
        signed_registry=env["signed_env"],
        expected_reviewer_id="auditor.jane@voxneuro.org",
        reference_roster_path=env["ref_roster"],
        candidate_roster_path=env["cand_roster"],
        study_conn=env["conn"],
        dua_document_path=env["dua_doc"],
    )
    assert ok_valid, msg_valid

    # 2. Missing authority DB rejected even when a fabricated DatasetAccessRecord is supplied
    ok_bypass, msg_bypass = verify_evaluation_provenance_receipt(
        env["receipt"],
        env["cand_csv"],
        env["ref_csv"],
        key=env["hmac_key"],
        signed_registry=env["signed_env"],
        expected_reviewer_id="auditor.jane@voxneuro.org",
        reference_roster_path=env["ref_roster"],
        candidate_roster_path=env["cand_roster"],
        study_conn=None,
        dataset_access_record=env["auth_rec"],
    )
    assert not ok_bypass and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg_bypass

    # 3. Missing authority DB also blocks evaluate_external_domain_with_provenance
    with pytest.raises(PermissionError, match="DATASET_AUTHORIZATION_NOT_VERIFIED"):
        evaluate_external_domain_with_provenance(
            env["receipt"],
            env["cand_csv"],
            env["ref_csv"],
            key=env["hmac_key"],
            signed_registry=env["signed_env"],
            expected_reviewer_id="auditor.jane@voxneuro.org",
            reference_roster_path=env["ref_roster"],
            candidate_roster_path=env["cand_roster"],
            study_conn=None,
            dataset_access_record=env["auth_rec"],
        )

    # 4. Manually constructed record absent from an empty authority DB is rejected
    empty_db = tmp_path / "empty_authority.db"
    run_migrations(empty_db)
    empty_conn = get_connection(empty_db)
    try:
        ok_abs, msg_abs = verify_evaluation_provenance_receipt(
            env["receipt"],
            env["cand_csv"],
            env["ref_csv"],
            key=env["hmac_key"],
            signed_registry=env["signed_env"],
            expected_reviewer_id="auditor.jane@voxneuro.org",
            reference_roster_path=env["ref_roster"],
            candidate_roster_path=env["cand_roster"],
            study_conn=empty_conn,
            dataset_access_record=env["auth_rec"],
        )
        assert not ok_abs and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg_abs
    finally:
        empty_conn.close()

    # 5. Forged DUA fingerprint in DB rejected against receipt
    bad_fp = hashlib.sha256(b"other-dua").hexdigest()
    register_dataset_access(
        env["conn"],
        DatasetAccessRecord(**{**env["auth_rec"].to_dict(), "dua_document_fingerprint": bad_fp}),
    )
    env["conn"].commit()
    ok_fp, msg_fp = verify_evaluation_provenance_receipt(
        env["receipt"],
        env["cand_csv"],
        env["ref_csv"],
        key=env["hmac_key"],
        signed_registry=env["signed_env"],
        expected_reviewer_id="auditor.jane@voxneuro.org",
        reference_roster_path=env["ref_roster"],
        candidate_roster_path=env["cand_roster"],
        study_conn=env["conn"],
    )
    assert not ok_fp and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg_fp

    # 5b. DB record with changed dataset version leaves receipt version (v1) unauthorized
    v2_db = tmp_path / "v2_only.db"
    run_migrations(v2_db)
    v2_conn = get_connection(v2_db)
    try:
        register_dataset_access(
            v2_conn,
            DatasetAccessRecord(**{**env["auth_rec"].to_dict(), "dataset_version": "v2"}),
        )
        v2_conn.commit()
        ok_v2, msg_v2 = verify_evaluation_provenance_receipt(
            env["receipt"],
            env["cand_csv"],
            env["ref_csv"],
            key=env["hmac_key"],
            signed_registry=env["signed_env"],
            expected_reviewer_id="auditor.jane@voxneuro.org",
            reference_roster_path=env["ref_roster"],
            candidate_roster_path=env["cand_roster"],
            study_conn=v2_conn,
        )
        assert not ok_v2 and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg_v2
    finally:
        v2_conn.close()

    # 6. Missing signed trust registry blocks evaluation immediately
    with pytest.raises(PermissionError, match="AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED"):
        evaluate_external_domain_with_provenance(
            env["receipt"],
            env["cand_csv"],
            env["ref_csv"],
            key=env["hmac_key"],
            signed_registry=None,
            study_conn=env["conn"],
        )


def test_cli_rejects_unsigned_reviewer_and_source_flags(tmp_path):
    """CLI refuses deprecated --authorized-reviewers and --authorized-sources-json flags."""
    sources_json = tmp_path / "sources.json"
    sources_json.write_text('{"uams": {"authorization_ref": "FAKE"}}', encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_external_domain.py",
            "--authorized-reviewers",
            "rogue@attacker.org",
            "--authorized-sources-json",
            str(sources_json),
            "--out-dir",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED" in (proc.stdout + proc.stderr)


def test_dua_to_signed_registry_cross_binding_enforcement(m4_trust_env, tmp_path):
    """Part 8.4: Authoritative SQLite DUA rows must match signed registry fields & DUA artifact."""
    env = m4_trust_env

    def _run_verify(conn, signed_reg=None, dua_path=None):
        return verify_evaluation_provenance_receipt(
            env["receipt"],
            env["cand_csv"],
            env["ref_csv"],
            key=env["hmac_key"],
            signed_registry=signed_reg if signed_reg is not None else env["signed_env"],
            expected_reviewer_id="auditor.jane@voxneuro.org",
            reference_roster_path=env["ref_roster"],
            candidate_roster_path=env["cand_roster"],
            study_conn=conn,
            dua_document_path=dua_path,
        )

    def _with_db_overrides(name: str, **overrides):
        db_path = tmp_path / f"{name}.db"
        run_migrations(db_path)
        conn = get_connection(db_path)
        rec = DatasetAccessRecord(**{**env["auth_rec"].to_dict(), **overrides})
        register_dataset_access(conn, rec)
        conn.commit()
        return conn

    # 1. Baseline valid end-to-end signed registry + authoritative DB + DUA artifact passes
    ok, msg = _run_verify(env["conn"], dua_path=env["dua_doc"])
    assert ok, msg

    # 2. Missing DUA document path -> fail closed
    ok, msg = _run_verify(env["conn"], dua_path=None)
    assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg

    # 3. Missing DUA file on disk -> fail closed
    ok, msg = _run_verify(env["conn"], dua_path=tmp_path / "does_not_exist_dua.txt")
    assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg

    # 4. Tampered DUA file bytes -> fail closed
    tampered_dua = tmp_path / "tampered_dua.txt"
    tampered_dua.write_bytes(b"tampered-dua-payload")
    ok, msg = _run_verify(env["conn"], dua_path=tampered_dua)
    assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg

    # 5. DB verification status not DOCUMENT_AUTHENTICATED
    for bad_status in ("UNVERIFIED", "REVOKED", "EXPIRED"):
        c = _with_db_overrides(f"status_{bad_status}", dua_verification_status=bad_status)
        try:
            ok, msg = _run_verify(c, dua_path=env["dua_doc"])
            assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
        finally:
            c.close()

    # 6. authorization_ref mismatch between DB & signed registry
    c = _with_db_overrides("bad_auth_ref", authorization_ref="FORGED-DUA-REF")
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 7. source_id mismatch between DB & signed registry
    c = _with_db_overrides("bad_source_id", source_id="rogue_source_id")
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 8. DB DUA expiration_date mismatch vs signed expiry_utc date prefix
    c = _with_db_overrides("bad_expiry", expiration_date="2034-12-31")
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 9. DB permitted_tasks broader than signed permitted_tasks
    c = _with_db_overrides("broad_tasks", permitted_tasks=["sustained_vowel", "reading_passage"])
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 10. DB permitted_data_processing_operations broader than signed permitted_operations
    c = _with_db_overrides(
        "broad_ops",
        permitted_data_processing_operations=["frozen_model_evaluation", "model_training"],
    )
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 11. issuing_authority mismatch between DB & signed registry
    c = _with_db_overrides("bad_authority", issuing_authority="Rogue Local Entity")
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 12. registry_id or registry_version mismatch between DB & signed registry
    for field_name, bad_val in (
        ("authorization_registry_id", "WRONG-REG-ID"),
        ("authorization_registry_version", "1999.01.0"),
    ):
        c = _with_db_overrides(f"bad_{field_name}", **{field_name: bad_val})
        try:
            ok, msg = _run_verify(c, dua_path=env["dua_doc"])
            assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
        finally:
            c.close()

    # 13. dua_source_artifact_reference mismatch vs signed retrieval_reference
    c = _with_db_overrides(
        "bad_artifact_ref",
        dua_source_artifact_reference="dua:neurovoz-rogue-copy",
    )
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 14. Forged DB row matching only dataset_id + dataset_version (default empty binding fields)
    c = _with_db_overrides(
        "forged_minimal",
        authorization_ref="",
        source_id="",
        authorization_registry_id="",
        authorization_registry_version="",
        issuing_authority="",
        dua_source_artifact_reference="",
        dua_verification_status="DOCUMENT_AUTHENTICATED",
    )
    try:
        ok, msg = _run_verify(c, dua_path=env["dua_doc"])
        assert not ok and "DATASET_AUTHORIZATION_NOT_VERIFIED" in msg
    finally:
        c.close()

    # 15. Signed registry with mismatched DUA fingerprint vs authoritative DB / artifact
    bad_fp_reg = _build_signed_env(
        env["ref_roster_sha"],
        env["cand_roster_sha"],
        seed=env["seed"],
        cand_dua_fp="f" * 64,
    )
    ok, msg = _run_verify(env["conn"], signed_reg=bad_fp_reg, dua_path=env["dua_doc"])
    assert not ok and "DUA" in msg

    # 16. Signed registry with revoked source authorization
    revoked_reg = _build_signed_env(
        env["ref_roster_sha"],
        env["cand_roster_sha"],
        seed=env["seed"],
        cand_dua_fp=hashlib.sha256(env["dua_doc"].read_bytes()).hexdigest(),
        cand_auth_state="REVOKED",
    )
    ok, msg = _run_verify(env["conn"], signed_reg=revoked_reg, dua_path=env["dua_doc"])
    assert not ok and "AUTHORIZATION" in msg
