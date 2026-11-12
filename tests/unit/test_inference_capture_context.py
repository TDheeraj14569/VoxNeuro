"""Comprehensive fail-closed inference safety tests covering capture origins and domain gates."""

import hashlib
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from voxneuro.exceptions import ModelCompatibilityError
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling import domains as domain_safety
from voxneuro.modeling.model_bundle import make_bundle
from voxneuro.modeling.prediction import InputCaptureContext, predict_research

FEATURE_CONFIG = {
    "schema_version": SCHEMA_VERSION,
    "pitch_floor_hz": 75,
    "pitch_ceiling_hz": 500,
    "pitch_step_seconds": 0.01,
    "mfcc_count": 13,
    "mel_bands": 40,
    "fft_window_samples": 1024,
    "hop_samples": 160,
    "mel_min_hz": 50,
    "common_max_hz": 3800,
    "spectral_rolloff_fraction": 0.85,
}
PREPROCESSING_CONFIG = {
    "target_sample_rate": 16000,
    "min_duration_seconds": 1.0,
    "mono_policy": "average_with_phase_check",
}


def _dummy_model():
    X = pd.DataFrame(np.zeros((2, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    return DummyClassifier(strategy="constant", constant=0).fit(X, [0, 1])


def _valid_bundle(domain_report=None, **overrides):
    args = {
        "dataset_provenance": "synthetic test",
        "dataset_version": "synthetic-v1",
        "dataset_checksum_sha256": "a" * 64,
        "code_version": "b" * 64,
        "training_evaluation_receipt_sha256": "c" * 64,
        "validation_method": "unit test",
        "software_versions": {"python": "3.12"},
        "preprocessing_config": PREPROCESSING_CONFIG,
        "feature_config": FEATURE_CONFIG,
        "validated_input_domains": ["controlled_speech_lab"] if domain_report else [],
    }
    if domain_report is not None:
        args["domain_validation_report"] = domain_report
    args.update(overrides)
    return make_bundle(_dummy_model(), **args)


def _valid_features():
    return {
        **dict.fromkeys(FEATURE_NAMES, 0.0),
        "schema_version": SCHEMA_VERSION,
        "schema_fingerprint": schema_fingerprint(),
        "feature_config_fingerprint": feature_config_fingerprint(FEATURE_CONFIG),
        "preprocessing_config_fingerprint": configuration_fingerprint(PREPROCESSING_CONFIG),
    }


@pytest.fixture
def trusted_report_setup(tmp_path, monkeypatch):
    path = tmp_path / "valid_domain_report.json"
    path.write_text(
        json.dumps(
            {
                "report_version": "1.0",
                "validated_utc": "2026-11-06T00:00:00+00:00",
                "validation_protocol": "test_protocol",
                "validation_dataset": "test_cohort",
                "independent_validation": True,
                "validated_input_domains": ["controlled_speech_lab"],
                "results": {"n_participants": 20, "balanced_accuracy": 0.75},
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        domain_safety, "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256", frozenset({digest})
    )
    return path, digest


# 1. Missing domain
def test_safety_rejects_missing_domain(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(
        ModelCompatibilityError, match="explicit input recording domain is required"
    ):
        predict_research(bundle, _valid_features(), input_domain="")


# 2. Unknown domain
def test_safety_rejects_unknown_domain(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="not validated for this model"):
        predict_research(bundle, _valid_features(), input_domain="unregistered_mystery_domain")


# 3. Unapproved candidate domain
def test_safety_rejects_unapproved_domain(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="not validated for this model"):
        predict_research(bundle, _valid_features(), input_domain="neurovoz_studio")


# 4. Candidate assessment dossier cannot act as approved report
def test_safety_rejects_candidate_dossier_as_report(tmp_path):
    dossier_path = tmp_path / "candidate_dossier.json"
    dossier_path.write_text(
        json.dumps({"schema_version": "voxneuro.domain_assessment.v1"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Candidate domain assessment dossiers"):
        domain_safety.load_domain_validation_report(dossier_path)


# 5. Modified approved report (hash mismatch)
def test_safety_rejects_modified_payload(trusted_report_setup):
    report_path, digest = trusted_report_setup
    bundle = _valid_bundle(report_path)
    # Alter the stored report JSON string
    bundle["domain_validation_evidence_json"] += " "
    with pytest.raises(ModelCompatibilityError, match="SHA-256 does not match"):
        predict_research(bundle, _valid_features(), input_domain="controlled_speech_lab")


# 6. Wrong hash
def test_safety_rejects_wrong_hash(trusted_report_setup):
    report_path, digest = trusted_report_setup
    bundle = _valid_bundle(report_path)
    bundle["domain_validation_evidence_sha256"] = "f" * 64
    with pytest.raises(ModelCompatibilityError, match="SHA-256 does not match"):
        predict_research(bundle, _valid_features(), input_domain="controlled_speech_lab")


# 7. Empty allowlist (default prototype state)
def test_safety_rejects_when_allowlist_is_empty(trusted_report_setup, monkeypatch):
    report_path, _ = trusted_report_setup
    monkeypatch.setattr(domain_safety, "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256", frozenset())
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="not been verified"):
        predict_research(bundle, _valid_features(), input_domain="controlled_speech_lab")


# 8. Live microphone
def test_safety_rejects_live_microphone(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="Microphone inference is disabled"):
        predict_research(bundle, _valid_features(), input_domain="live_mic")


# 9. Smartphone alias
def test_safety_rejects_smartphone_alias(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="Microphone inference is disabled"):
        predict_research(bundle, _valid_features(), input_domain="iphone_recording")


# 10. Browser microphone
def test_safety_rejects_browser_microphone(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="Microphone inference is disabled"):
        predict_research(bundle, _valid_features(), input_domain="browser_audio_stream")


# 11. Laptop microphone
def test_safety_rejects_laptop_microphone(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="Microphone inference is disabled"):
        predict_research(bundle, _valid_features(), input_domain="laptop_microphone")


# 12. Neutral domain alias combined with microphone capture origin
def test_safety_rejects_neutral_domain_with_microphone_capture_origin(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="microphone or user-upload source"):
        predict_research(
            bundle,
            _valid_features(),
            input_domain="controlled_speech_lab",
            capture_origin="live_browser_mic",
        )


# 13. Unknown acquisition origin
def test_safety_rejects_unknown_capture_origin(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    with pytest.raises(ModelCompatibilityError, match="Acquisition origin is missing or unknown"):
        predict_research(
            bundle,
            _valid_features(),
            input_domain="controlled_speech_lab",
            capture_origin="unknown",
        )


# 14. Incompatible feature schema
def test_safety_rejects_incompatible_feature_schema(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    feats = _valid_features()
    feats["schema_version"] = "voxneuro.voice.v2"
    with pytest.raises(
        ModelCompatibilityError, match="feature schema version is missing or incompatible"
    ):
        predict_research(bundle, feats, input_domain="controlled_speech_lab")


# 15. Incompatible preprocessing configuration
def test_safety_rejects_incompatible_preprocessing(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    feats = _valid_features()
    feats["preprocessing_config_fingerprint"] = "0" * 64
    with pytest.raises(
        ModelCompatibilityError, match="Incoming preprocessing settings do not match"
    ):
        predict_research(bundle, feats, input_domain="controlled_speech_lab")


# 16. Missing model metadata
def test_safety_rejects_missing_model_metadata(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    del bundle["research_only"]
    with pytest.raises(ModelCompatibilityError, match="missing safety metadata"):
        predict_research(bundle, _valid_features(), input_domain="controlled_speech_lab")


# 17. Valid capture context succeeds
def test_safety_accepts_verified_research_capture_context(trusted_report_setup):
    report_path, _ = trusted_report_setup
    bundle = _valid_bundle(report_path)
    ctx = InputCaptureContext(capture_origin="pre_recorded_research", task_type="sustained_vowel")
    result = predict_research(
        bundle, _valid_features(), input_domain="controlled_speech_lab", capture_context=ctx
    )
    assert result["experimental_class"] == 0
    assert result["clinical_probability"] is None
