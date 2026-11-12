"""Unit tests for M6 PredictionService fail-closed abstention, OOD checks, and opt-in retention."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION
from voxneuro.modeling import domains as domains_mod
from voxneuro.modeling import model_bundle as bundle_mod
from voxneuro.modeling import model_registry as reg_mod
from voxneuro.modeling import prediction_service as pred_mod
from voxneuro.modeling.m6_training_ops import train_and_register_research_model
from voxneuro.modeling.model_bundle import load_bundle, save_bundle
from voxneuro.modeling.prediction import InputCaptureContext
from voxneuro.study.auth import authenticate_user, register_user
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
from voxneuro.study.session import create_session
from voxneuro.study.withdrawal import withdraw_participant


def _synthetic_cohort(n_participants: int = 30, seed: int = 77):
    rng = np.random.default_rng(seed)
    rows = []
    y = []
    groups = []
    for idx in range(n_participants):
        label = idx % 2
        pid = f"pred-p-{idx:03d}"
        row = {
            name: float(rng.normal(loc=0.3 if label else -0.3, scale=0.5)) for name in FEATURE_NAMES
        }
        row["participant_id"] = pid
        row["sample_id"] = f"s-{idx:03d}"
        rows.append(row)
        y.append(label)
        groups.append(pid)
    return (
        pd.DataFrame(rows)[["participant_id", "sample_id", *FEATURE_NAMES]],
        np.asarray(y),
        np.asarray(groups),
    )


def _wav_bytes(samples: np.ndarray, sr: int = 16000) -> bytes:
    buf = BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_prediction_service_abstains_on_bad_audio_mic_origin_and_missing_model():
    silent_wav = _wav_bytes(np.zeros(32000, dtype=np.float32))
    bad = pred_mod.evaluate_audio_bytes_research(
        silent_wav,
        capture_context=InputCaptureContext(
            capture_origin="live_browser_mic", verified_origin=False
        ),
        input_domain="laptop_microphone",
    )
    assert bad["quality"].valid is False
    res_bad = bad["prediction"]
    assert res_bad.abstained is True
    assert res_bad.research_score is None
    assert "QUALITY_GATE_FAILED" in res_bad.abstention_reasons
    assert "DISALLOWED_CAPTURE_ORIGIN" in res_bad.abstention_reasons
    assert pred_mod.M6_MEDICAL_DISCLAIMER in res_bad.research_only_disclaimer

    good_wav = _wav_bytes(sustained_vowel())
    good_abstain = pred_mod.evaluate_audio_bytes_research(
        good_wav,
        capture_context=InputCaptureContext(
            capture_origin="live_browser_mic", verified_origin=False
        ),
        input_domain="laptop_microphone",
    )
    assert good_abstain["quality"].valid is True
    assert good_abstain["prediction"].abstained is True
    assert "NO_APPROVED_MODEL_REGISTERED" in good_abstain["prediction"].abstention_reasons


def test_prediction_service_ood_and_consent_and_approved_path_unit_isolated(
    tmp_path: Path, monkeypatch
):
    db_path = tmp_path / "pred_service.db"
    run_migrations(db_path)
    conn = get_connection(db_path)
    try:
        admin = register_user(
            conn,
            username="mladmin2",
            email="mladmin2@example.org",
            password="MlAdminPassword123!",
            role="ml_admin",
        )
        _, token = authenticate_user(conn, identifier="mladmin2", password="MlAdminPassword123!")

        X, y, groups = _synthetic_cohort()
        reg_model, meta = train_and_register_research_model(
            conn,
            X,
            y,
            groups,
            output_dir=tmp_path / "models",
            model_family="logistic_regression",
            actor=admin,
        )

        # Create synthetic trusted report hash ONLY inside isolated tmp test scope
        trusted_report = {
            "report_version": "1",
            "validated_utc": "2026-11-12T00:00:00Z",
            "validation_protocol": "isolated_unit_test_fixture",
            "validation_dataset": "synthetic_uams_like_fixture",
            "independent_validation": True,
            "validated_input_domains": ["uams_telephone"],
            "results": {"n_participants": 30, "roc_auc": 0.82, "balanced_accuracy": 0.78},
        }
        rep_json = json.dumps(trusted_report)
        rep_sha = hashlib.sha256(rep_json.encode("utf-8")).hexdigest()
        monkeypatch.setattr(
            domains_mod, "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256", frozenset({rep_sha})
        )
        monkeypatch.setattr(
            reg_mod, "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256", frozenset({rep_sha})
        )
        monkeypatch.setattr(
            pred_mod, "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256", frozenset({rep_sha})
        )
        monkeypatch.setattr(
            domains_mod, "is_trusted_domain_validation_report", lambda h: h == rep_sha
        )
        monkeypatch.setattr(pred_mod, "is_trusted_domain_validation_report", lambda h: h == rep_sha)
        monkeypatch.setattr(
            bundle_mod, "is_trusted_domain_validation_report", lambda h: h == rep_sha
        )

        # Re-save bundle with domain_compatibility_verified=True for isolated unit verification
        bundle = load_bundle(Path(meta["bundle_path"]))
        bundle["domain_compatibility_verified"] = True
        bundle["domain_validation_evidence_json"] = rep_json
        bundle["domain_validation_evidence_sha256"] = rep_sha
        bundle["validated_input_domains"] = ["uams_telephone"]
        save_bundle(bundle, Path(meta["bundle_path"]))
        new_sha = reg_mod.compute_file_sha256(Path(meta["bundle_path"]))
        conn.execute(
            "UPDATE model_versions SET artifact_sha256 = ? WHERE model_id = ?;",
            (new_sha, reg_model.model_id),
        )
        conn.commit()

        reg_mod.set_model_domain_approval(
            conn,
            token,
            model_id=reg_model.model_id,
            domain_id="uams_telephone",
            approval_state="APPROVED",
            evidence_sha256=rep_sha,
        )
        reg_mod.transition_model_state(
            conn,
            model_id=reg_model.model_id,
            to_state="RESEARCH_INFERENCE_APPROVED",
            reason="Isolated unit test approval",
            session_token=token,
        )

        # Study + Consent + Session
        create_protocol(
            conn,
            ProtocolDefinition(
                protocol_id="p-p",
                protocol_version="1.0",
                tasks=["sustained_vowel"],
            ),
        )
        create_study(
            conn,
            Study(
                study_id="st-p",
                study_name="Pred Test",
                study_description="Unit test",
                protocol_id="p-p",
                protocol_version="1.0",
                study_status="active",
                dataset_id="uams",
                consent_requirements=["voice_analysis"],
                data_retention_policy_id="opt-in",
                analysis_configuration_id="v3",
            ),
        )
        register_dataset_access(
            conn,
            DatasetAccessRecord(
                dataset_id="uams",
                dataset_version="v1",
                dataset_owner="UAMS",
                license_type="CC BY 4.0",
                permitted_tasks=["sustained_vowel"],
                permitted_data_processing_operations=["feature_extraction"],
                storage_restrictions="None",
                publication_restrictions="Cite",
                source_documentation="DOI",
                access_approval_state="APPROVED",
                dua_state="NOT_REQUIRED",
            ),
        )
        register_participant(
            conn,
            Participant(
                participant_id="sub-1",
                study_id="st-p",
                allowed_research_scopes=["voice_analysis"],
            ),
        )
        c_rec = ConsentRecord(
            consent_record_id="con-p-01",
            participant_id="sub-1",
            study_id="st-p",
            consent_form_version="v1",
            consent_date=utc_now_iso(),
            scope_of_permission=["voice_analysis"],
            permitted_recording_tasks=["sustained_vowel"],
            permitted_research_uses=["biomarker_research"],
            permission_to_retain_derived_features=False,
            source_document_reference="doc://c1",
        )
        record_consent(conn, c_rec)
        sess = ResearchSession(
            session_id="sess-p-01",
            study_id="st-p",
            protocol_version="1.0",
            participant_id="sub-1",
            visit_index=1,
            visit_label="Baseline",
            acquisition_domain_id="uams_telephone",
            capture_origin="pre_recorded_research",
            consent_reference=c_rec.consent_record_id,
        )
        create_session(conn, sess)

        # Valid in-distribution feature vector
        valid_feats = {name: 0.0 for name in FEATURE_NAMES}
        valid_feats["schema_version"] = SCHEMA_VERSION
        res_ok = pred_mod.run_prediction_service(
            features=valid_feats,
            quality_valid=True,
            capture_context=InputCaptureContext(capture_origin="pre_recorded_research"),
            input_domain="uams_telephone",
            conn=conn,
            model_id=reg_model.model_id,
            session_id=sess.session_id,
            allow_prediction_retention=True,
        )
        assert res_ok.abstained is False
        assert res_ok.status == "RESEARCH_SCORE_RETURNED"
        assert res_ok.research_score is not None
        # permission_to_retain_derived_features=False overrides retention request!
        assert res_ok.retention_persisted is False

        # Out-of-distribution feature vector abstains cleanly
        ood_feats = {
            **valid_feats,
            "f0_mean_hz": 9999.0,
            "jitter_local": 500.0,
            "shimmer_local": 500.0,
            "hnr_db": -999.0,
        }
        res_ood = pred_mod.run_prediction_service(
            features=ood_feats,
            quality_valid=True,
            capture_context=InputCaptureContext(capture_origin="pre_recorded_research"),
            input_domain="uams_telephone",
            conn=conn,
            model_id=reg_model.model_id,
            session_id=sess.session_id,
        )
        assert res_ood.abstained is True
        assert "OUT_OF_DISTRIBUTION_FEATURES" in res_ood.abstention_reasons

        # Withdrawal blocks subsequent inference immediately
        withdraw_participant(conn, "sub-1", key=b"test-key-32-bytes-minimum-material")
        res_withdrawn = pred_mod.run_prediction_service(
            features=valid_feats,
            quality_valid=True,
            capture_context=InputCaptureContext(capture_origin="pre_recorded_research"),
            input_domain="uams_telephone",
            conn=conn,
            model_id=reg_model.model_id,
            session_id=sess.session_id,
        )
        assert res_withdrawn.abstained is True
        assert "CONSENT_OR_DUA_BLOCKED" in res_withdrawn.abstention_reasons
    finally:
        conn.close()
