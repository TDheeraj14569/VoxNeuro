import hashlib
import json

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION
from voxneuro.modeling import domains as domain_safety
from voxneuro.modeling.model_bundle import load_bundle, make_bundle, save_bundle


def _fitted_model():
    X = pd.DataFrame(np.zeros((2, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    return DummyClassifier(strategy="constant", constant=0).fit(X, [0, 1])


def _bundle(**overrides):
    arguments = {
        "dataset_provenance": "synthetic test only",
        "dataset_version": "synthetic-v1",
        "dataset_checksum_sha256": "a" * 64,
        "code_version": "b" * 64,
        "training_evaluation_receipt_sha256": "c" * 64,
        "validation_method": "unit test only",
        "software_versions": {"python": "3.12"},
        "preprocessing_config": {"target_sample_rate": 16000},
        "feature_config": {"schema_version": SCHEMA_VERSION},
    }
    arguments.update(overrides)
    return make_bundle(_fitted_model(), **arguments)


def test_model_bundle_saves_reloads_with_full_safety_and_provenance(tmp_path):
    bundle = _bundle()
    target = tmp_path / "bundle.joblib"
    save_bundle(bundle, target)
    loaded = load_bundle(target)
    assert loaded["research_only"] is True
    assert loaded["domain_compatibility_verified"] is False
    assert loaded["feature_config"]["schema_version"] == SCHEMA_VERSION
    assert loaded["bundle_version"] == 4
    assert len(loaded["feature_schema_fingerprint"]) == 64
    assert len(loaded["feature_config_fingerprint"]) == 64
    assert len(loaded["preprocessing_config_fingerprint"]) == 64
    assert len(loaded["dataset_checksum_sha256"]) == 64
    assert len(loaded["training_evaluation_receipt_sha256"]) == 64
    X = pd.DataFrame(np.zeros((2, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    assert np.array_equal(loaded["model"].predict(X), bundle["model"].predict(X))


def test_model_bundle_refuses_microphone_inference_configuration():
    with pytest.raises(ValueError, match="Microphone inference cannot be enabled"):
        _bundle(allow_user_microphone_inference=True)


def test_model_bundle_does_not_infer_validation_from_domain_names():
    with pytest.raises(ValueError, match="domain-validation report is required"):
        _bundle(validated_input_domains=["uams_telephone"])


def test_model_bundle_requires_and_checks_validation_report(tmp_path, monkeypatch):
    report = tmp_path / "validation.json"
    report.write_text(
        json.dumps(
            {
                "report_version": "1.0",
                "validated_utc": "2026-11-06T00:00:00+00:00",
                "validation_protocol": "held-out test protocol",
                "validation_dataset": "independent test cohort",
                "independent_validation": True,
                "validated_input_domains": ["uams telephone"],
                "results": {"n_participants": 12, "balanced_accuracy": 0.8},
            }
        ),
        encoding="utf-8",
    )
    unapproved = _bundle(domain_validation_report=report)
    assert unapproved["domain_compatibility_verified"] is False
    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    monkeypatch.setattr(
        domain_safety,
        "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256",
        frozenset({digest}),
    )
    bundle = _bundle(domain_validation_report=report)
    assert bundle["domain_compatibility_verified"] is True
    assert bundle["validated_input_domains"] == ["uams_telephone"]
    target = tmp_path / "evidence_bundle.joblib"
    save_bundle(bundle, target)
    assert load_bundle(target)["domain_compatibility_verified"] is True


def test_model_bundle_rejects_microphone_domain_even_with_evidence(tmp_path):
    report = tmp_path / "validation.json"
    report.write_text(
        json.dumps(
            {
                "report_version": "1.0",
                "validated_utc": "2026-11-06T00:00:00+00:00",
                "validation_protocol": "held-out test protocol",
                "validation_dataset": "independent test cohort",
                "independent_validation": True,
                "validated_input_domains": ["browser microphone"],
                "results": {"n_participants": 12, "balanced_accuracy": 0.8},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Microphone domains cannot be enabled"):
        _bundle(domain_validation_report=report)


def test_model_bundle_requires_timezone_aware_utc_evidence(tmp_path):
    report = tmp_path / "validation.json"
    report.write_text(
        json.dumps(
            {
                "report_version": "1.0",
                "validated_utc": "2026-11-06T00:00:00",
                "validation_protocol": "held-out test protocol",
                "validation_dataset": "independent test cohort",
                "independent_validation": True,
                "validated_input_domains": ["uams telephone"],
                "results": {"n_participants": 12, "balanced_accuracy": 0.8},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expressed in UTC"):
        _bundle(domain_validation_report=report)


def test_model_bundle_detects_modified_domain_evidence_even_with_fresh_bundle_checksum(tmp_path):
    report = tmp_path / "validation.json"
    report.write_text(
        json.dumps(
            {
                "report_version": "1.0",
                "validated_utc": "2026-11-06T00:00:00+00:00",
                "validation_protocol": "held-out test protocol",
                "validation_dataset": "independent test cohort",
                "independent_validation": True,
                "validated_input_domains": ["uams telephone"],
                "results": {"n_participants": 12, "balanced_accuracy": 0.8},
            }
        ),
        encoding="utf-8",
    )
    bundle = _bundle(domain_validation_report=report)
    bundle["domain_validation_evidence_json"] += " "
    target = tmp_path / "tampered_evidence.joblib"
    save_bundle(bundle, target)
    with pytest.raises(ValueError, match="domain-validation evidence is invalid"):
        load_bundle(target)


def test_model_bundle_checksum_detects_changed_artifact_before_loading(tmp_path):
    target = tmp_path / "bundle.joblib"
    save_bundle(_bundle(), target)
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        load_bundle(target)


def test_missing_trusted_model_artifact_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="artifact or its SHA-256 sidecar is missing"):
        load_bundle(tmp_path / "missing.joblib")


def test_model_bundle_requires_dataset_evaluation_and_code_fingerprints():
    with pytest.raises(ValueError, match="SHA-256"):
        _bundle(dataset_checksum_sha256="")
