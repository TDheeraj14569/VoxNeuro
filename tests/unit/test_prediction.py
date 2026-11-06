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
from voxneuro.modeling.prediction import predict_research

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


def _model():
    X = pd.DataFrame(np.zeros((2, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    return DummyClassifier(strategy="constant", constant=0).fit(X, [0, 1])


def _bundle(domain_validation_report=None, **overrides):
    arguments = {
        "dataset_provenance": "synthetic test only",
        "dataset_version": "synthetic-v1",
        "dataset_checksum_sha256": "a" * 64,
        "code_version": "b" * 64,
        "training_evaluation_receipt_sha256": "c" * 64,
        "validation_method": "unit test only",
        "software_versions": {"python": "3.12"},
        "preprocessing_config": PREPROCESSING_CONFIG,
        "feature_config": FEATURE_CONFIG,
        "validated_input_domains": [],
    }
    if domain_validation_report is not None:
        arguments["domain_validation_report"] = domain_validation_report
        arguments["validated_input_domains"] = ["controlled speech lab"]
    arguments.update(overrides)
    return make_bundle(_model(), **arguments)


@pytest.fixture
def domain_report(tmp_path):
    path = tmp_path / "domain_validation.json"
    path.write_text(
        json.dumps(
            {
                "report_version": "1.0",
                "validated_utc": "2026-11-06T00:00:00+00:00",
                "validation_protocol": "held-out synthetic test protocol",
                "validation_dataset": "synthetic test cohort",
                "independent_validation": True,
                "validated_input_domains": ["controlled speech lab"],
                "results": {"n_participants": 20, "balanced_accuracy": 0.7},
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def trusted_domain_report(domain_report, monkeypatch):
    digest = hashlib.sha256(domain_report.read_bytes()).hexdigest()
    monkeypatch.setattr(
        domain_safety, "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256", frozenset({digest})
    )
    return domain_report


def _features():
    return {
        **dict.fromkeys(FEATURE_NAMES, 0.0),
        "schema_version": SCHEMA_VERSION,
        "schema_fingerprint": schema_fingerprint(),
        "feature_config_fingerprint": feature_config_fingerprint(FEATURE_CONFIG),
        "preprocessing_config_fingerprint": configuration_fingerprint(PREPROCESSING_CONFIG),
    }


def test_prediction_returns_experimental_status_for_explicit_validated_domain(
    trusted_domain_report,
):
    result = predict_research(
        _bundle(trusted_domain_report), _features(), input_domain="controlled_speech_lab"
    )
    assert result["clinical_probability"] is None
    assert result["status"].startswith("experimental")


def test_prediction_rejects_model_without_explicit_domain_compatibility():
    bundle = _bundle(validated_input_domains=[])
    assert bundle["domain_compatibility_verified"] is False
    with pytest.raises(ModelCompatibilityError, match="not been verified"):
        predict_research(bundle, _features(), input_domain="controlled_speech_lab")


def test_domain_list_alone_cannot_claim_compatibility():
    with pytest.raises(ValueError, match="domain-validation report is required"):
        _bundle(validated_input_domains=["controlled_speech_lab"])


def test_prediction_rejects_microphone_aliases_after_canonicalization(trusted_domain_report):
    bundle = _bundle(trusted_domain_report)
    for value in (
        "browser_microphone ",
        "Browser Microphone",
        "built-in mic",
        "laptop-microphone",
        "smartphone",
        "mobile",
        "phone_recording",
        "web_audio",
        "iPhone voice recording",
        "Android browser audio",
        "live_device",
    ):
        with pytest.raises(ModelCompatibilityError, match="Microphone inference is disabled"):
            predict_research(bundle, _features(), input_domain=value)
    assert not domain_safety.is_microphone_domain("uams_telephone")
    assert not domain_safety.is_microphone_domain("telephone_collected_research")


def test_prediction_rejects_non_string_domain_as_compatibility_error(domain_report):
    with pytest.raises(ModelCompatibilityError, match="non-empty string"):
        predict_research(_bundle(domain_report), _features(), input_domain=None)


def test_prediction_rejects_missing_features_nonfinite_values_and_wrong_order(
    trusted_domain_report,
):
    bundle = _bundle(trusted_domain_report)
    missing = _features()
    missing.pop(FEATURE_NAMES[0])
    with pytest.raises(ModelCompatibilityError, match="every measurement"):
        predict_research(bundle, missing, input_domain="controlled_speech_lab")

    invalid = _features()
    invalid[FEATURE_NAMES[0]] = float("inf")
    with pytest.raises(ModelCompatibilityError, match="non-finite"):
        predict_research(bundle, invalid, input_domain="controlled_speech_lab")

    reordered = dict(reversed(list(_features().items())))
    with pytest.raises(ModelCompatibilityError, match="exact schema order"):
        predict_research(bundle, reordered, input_domain="controlled_speech_lab")


def test_prediction_rejects_all_features_missing_but_allows_named_undefined_measures(
    trusted_domain_report,
):
    bundle = _bundle(trusted_domain_report)
    all_missing = {**_features(), **dict.fromkeys(FEATURE_NAMES, float("nan"))}
    with pytest.raises(ModelCompatibilityError, match="missing or non-finite"):
        predict_research(bundle, all_missing, input_domain="controlled_speech_lab")

    partial = _features()
    partial["jitter_local"] = float("nan")
    result = predict_research(bundle, partial, input_domain="controlled_speech_lab")
    assert result["experimental_class"] == 0


def test_prediction_rejects_missing_or_false_safety_metadata(trusted_domain_report):
    bundle = _bundle(trusted_domain_report)
    bundle.pop("domain_compatibility_verified")
    with pytest.raises(ModelCompatibilityError, match="missing safety metadata"):
        predict_research(bundle, _features(), input_domain="controlled_speech_lab")

    bundle = _bundle(trusted_domain_report)
    bundle["research_only"] = False
    with pytest.raises(ModelCompatibilityError, match="research-only"):
        predict_research(bundle, _features(), input_domain="controlled_speech_lab")


def test_prediction_rejects_incompatible_feature_schema(trusted_domain_report):
    bundle = _bundle(trusted_domain_report)
    bundle["feature_schema_version"] = "voxneuro.voice.v1"
    with pytest.raises(ModelCompatibilityError, match="schema version"):
        predict_research(bundle, _features(), input_domain="controlled_speech_lab")


def test_prediction_rejects_bundle_without_fitted_estimator(trusted_domain_report):
    bundle = _bundle(trusted_domain_report)
    bundle["model"] = None
    with pytest.raises(ModelCompatibilityError, match="usable fitted estimator"):
        predict_research(bundle, _features(), input_domain="controlled_speech_lab")


def test_prediction_rejects_microphone_flag_even_for_non_microphone_domain(trusted_domain_report):
    bundle = _bundle(trusted_domain_report)
    bundle["allow_user_microphone_inference"] = True
    with pytest.raises(ModelCompatibilityError, match="Microphone inference is disabled"):
        predict_research(bundle, _features(), input_domain="controlled_speech_lab")


@pytest.mark.parametrize("value", [True, np.bool_(True)])
def test_prediction_rejects_boolean_feature_values(value, trusted_domain_report):
    features = _features()
    features[FEATURE_NAMES[0]] = value
    with pytest.raises(ModelCompatibilityError, match="not boolean"):
        predict_research(
            _bundle(trusted_domain_report), features, input_domain="controlled_speech_lab"
        )


def test_prediction_rejects_feature_or_preprocessing_fingerprint_mismatch(trusted_domain_report):
    bundle = _bundle(trusted_domain_report)
    features = _features()
    features["feature_config_fingerprint"] = "0" * 64
    with pytest.raises(ModelCompatibilityError, match="settings do not match"):
        predict_research(bundle, features, input_domain="controlled_speech_lab")

    features = _features()
    features["preprocessing_config_fingerprint"] = "0" * 64
    with pytest.raises(ModelCompatibilityError, match="preprocessing settings"):
        predict_research(bundle, features, input_domain="controlled_speech_lab")
