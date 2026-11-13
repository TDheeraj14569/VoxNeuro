"""Regression coverage for the explicitly non-validated individual research path."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from voxneuro.config import load_config
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling import inference_provenance
from voxneuro.modeling.exploratory import (
    ExploratoryPredictionInput,
    OODStatus,
    assess_training_distribution,
    run_exploratory_prediction,
)
from voxneuro.modeling.m6_experiment import build_training_distribution_manifest
from voxneuro.modeling.model_bundle import make_bundle, save_bundle
from voxneuro.modeling.prediction_service import PredictionResult


def _distribution(values: dict[str, float] | None = None) -> dict:
    values = values or {}
    return {
        "schema_version": "voxneuro.training_distribution.v1",
        "feature_schema_version": SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "statistics": {
            name: {
                "n": 20,
                "mean": 0.0,
                "std": 1.0,
                "q01": -2.0,
                "q99": 2.0,
            }
            for name in FEATURE_NAMES
        },
        "values": values,
    }


def _features(value: float = 0.0) -> dict[str, float | str]:
    features: dict[str, float | str] = {name: value for name in FEATURE_NAMES}
    features.update(
        {
            "schema_version": SCHEMA_VERSION,
            "schema_fingerprint": schema_fingerprint(),
            "feature_config_fingerprint": feature_config_fingerprint(
                load_config("feature_config.yaml")
            ),
            "preprocessing_config_fingerprint": configuration_fingerprint(
                load_config("audio_config.yaml")
            ),
        }
    )
    return features


def _context(features: dict, *, domain: str = "laptop_microphone") -> ExploratoryPredictionInput:
    return ExploratoryPredictionInput(
        features=features,
        feature_names=tuple(name for name in features if name in FEATURE_NAMES),
        feature_schema_fingerprint=schema_fingerprint(),
        task_type="sustained_vowel",
        capture_origin="user_upload",
        acquisition_domain_id=domain,
        acquisition_domain_source="user_declared",
        preprocessing_fingerprint=str(features["preprocessing_config_fingerprint"]),
        quality_valid=True,
        source_audio_sha256="a" * 64,
        repetition_count=1,
    )


def test_training_distribution_assessment_separates_shift_and_ood():
    manifest = _distribution()
    assert assess_training_distribution(_features(), manifest).status is OODStatus.IN_DISTRIBUTION

    shifted = _features()
    shifted[FEATURE_NAMES[0]] = 3.0
    assert assess_training_distribution(shifted, manifest).status is OODStatus.MILD_SHIFT

    ood = _features()
    for name in FEATURE_NAMES[:3]:
        ood[name] = 7.0
    assert assess_training_distribution(ood, manifest).status is OODStatus.OUT_OF_DISTRIBUTION


def test_training_distribution_rejects_missing_reference_and_required_features():
    assert (
        assess_training_distribution(_features(), None).status
        is OODStatus.OOD_ASSESSMENT_UNAVAILABLE
    )
    features = _features()
    for name in FEATURE_NAMES[:3]:
        features[name] = None
    result = assess_training_distribution(features, _distribution())
    assert result.status is OODStatus.INSUFFICIENT_REFERENCE_DATA


def test_exploratory_prediction_returns_audited_raw_candidate(tmp_path, monkeypatch):
    import voxneuro.modeling.exploratory as exploratory

    monkeypatch.setattr(exploratory, "verify_local_exploratory_provenance", lambda *a, **k: [])
    rng = np.random.default_rng(912)
    training = pd.DataFrame(rng.normal(size=(24, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    target = np.array([0] * 12 + [1] * 12)
    training.iloc[:, 0] += target * 0.8
    estimator = LogisticRegression(random_state=4).fit(training, target)
    audio = load_config("audio_config.yaml")
    feature = load_config("feature_config.yaml")
    digest = hashlib.sha256(b"test provenance only").hexdigest()
    distribution = build_training_distribution_manifest(
        training,
        np.array([f"p-{i}" for i in range(len(training))]),
        dataset_id="synthetic-test-only",
        dataset_version="test",
        dataset_sha256=digest,
        feature_schema_fingerprint=schema_fingerprint(),
        feature_config_fingerprint=feature_config_fingerprint(feature),
        preprocessing_config_fingerprint=configuration_fingerprint(audio),
    )
    bundle = make_bundle(
        estimator,
        dataset_provenance="synthetic test fixture only",
        dataset_version="test",
        dataset_checksum_sha256=digest,
        code_version=hashlib.sha256(b"code").hexdigest(),
        training_evaluation_receipt_sha256=hashlib.sha256(b"evaluation").hexdigest(),
        validation_method="test fixture",
        software_versions={"scikit-learn": "test"},
        preprocessing_config=audio,
        feature_config=feature,
        training_details={
            "model_id": "synthetic-test-only",
            "evaluation_metrics": {"balanced_accuracy": 0.5},
        },
        training_distribution_manifest=distribution,
        score_contract={
            "method": "decision_function",
            "kind": "uncalibrated_logit",
            "threshold": 0.0,
            "positive_class_label": "PD",
            "negative_class_label": "HC",
            "calibrated": False,
        },
    )
    model_path = tmp_path / "artifacts" / "models" / "uams_logistic_research.joblib"
    save_bundle(bundle, model_path)
    manifest_path = tmp_path / "data" / "processed" / "feature_manifest.csv"
    manifest_path.parent.mkdir(parents=True)
    pd.DataFrame({"waveform_sha256": ["b" * 64]}).to_csv(manifest_path, index=False)

    test_features = _features()
    context = _context(test_features)
    result = run_exploratory_prediction(context, project_root=tmp_path)

    assert result.abstained is False
    assert result.status == "EXPLORATORY_NOT_DOMAIN_VALIDATED"
    assert result.score_kind == "uncalibrated_logit"
    assert result.research_classification in {"PD-pattern candidate", "HC-pattern candidate"}
    assert result.decision_threshold == 0.0
    assert result.domain_validation_status == "NOT_VALIDATED"
    assert result.acquisition_domain_source == "user_declared"
    assert result.model_evaluation_metrics == {"balanced_accuracy": 0.5}

    missing_hash = ExploratoryPredictionInput(**{**context.__dict__, "source_audio_sha256": None})
    missing_result = run_exploratory_prediction(missing_hash, project_root=tmp_path)
    assert missing_result.abstained is True
    assert missing_result.abstention_reasons == ["SOURCE_AUDIO_FINGERPRINT_MISSING"]

    pd.DataFrame({"waveform_sha256": [context.source_audio_sha256]}).to_csv(
        manifest_path, index=False
    )
    overlap_result = run_exploratory_prediction(context, project_root=tmp_path)
    assert overlap_result.abstained is True
    assert overlap_result.abstention_reasons == ["KNOWN_TRAINING_RECORDING"]


def test_exploratory_prediction_fails_closed_for_unknown_domain(tmp_path):
    result = run_exploratory_prediction(
        _context(_features(), domain="unknown"), project_root=tmp_path
    )
    assert result.abstained is True
    assert result.abstention_reasons == ["ACQUISITION_DOMAIN_UNKNOWN"]


def test_exploratory_prediction_fails_closed_for_non_integer_repetitions(tmp_path):
    context = _context(_features())
    malformed = ExploratoryPredictionInput(**{**context.__dict__, "repetition_count": "one"})
    result = run_exploratory_prediction(malformed, project_root=tmp_path)
    assert result.abstained is True
    assert result.abstention_reasons == ["MISSING_REPETITION"]


def test_session_prediction_tries_exploratory_only_after_strict_gate_abstains(monkeypatch):
    import voxneuro.modeling.exploratory as exploratory
    import voxneuro.ui.consumer_pages as consumer_pages

    strict_result = PredictionResult(
        prediction_id="strict-abstain",
        status="ABSTAINED_FAIL_CLOSED",
        abstained=True,
        abstention_reasons=["NO_APPROVED_MODEL_REGISTERED"],
        abstention_reason="No externally validated model is registered.",
        model_id=None,
        model_version="none",
        model_checksum=None,
        research_score=None,
        research_classification=None,
        calibration_status="NOT_APPLICABLE",
    )
    exploratory_result = PredictionResult(
        prediction_id="exploratory-result",
        status="EXPLORATORY_NOT_DOMAIN_VALIDATED",
        abstained=False,
        abstention_reasons=[],
        abstention_reason=None,
        model_id="uams_logistic_research",
        model_version="0.4.0-research",
        model_checksum="a" * 64,
        research_score=-0.25,
        research_classification="HC-pattern candidate",
        calibration_status="UNCALIBRATED_DECISION_SCORE",
        score_kind="uncalibrated_logit",
        decision_threshold=0.0,
        domain_validation_status="NOT_VALIDATED",
    )
    calls = []
    monkeypatch.setattr(consumer_pages, "run_prediction_service", lambda **kwargs: strict_result)

    def fake_exploratory(context):
        calls.append(context)
        return exploratory_result

    monkeypatch.setattr(exploratory, "run_exploratory_prediction", fake_exploratory)
    features = _features()
    actual = consumer_pages.build_session_prediction(
        features=features,
        quality_valid=True,
        capture_origin="user_upload",
        input_domain="laptop_microphone",
        acquisition_domain_source="user_declared",
        conn=None,
        user=None,
        recording_metadata={"duration_seconds": 4.0},
        source_audio_sha256="f" * 64,
    )

    assert actual is exploratory_result
    assert len(calls) == 1
    assert calls[0].acquisition_domain_id == "laptop_microphone"
    assert calls[0].acquisition_domain_source == "user_declared"
    assert calls[0].recording_metadata["duration_seconds"] == 4.0
    assert calls[0].source_audio_sha256 == "f" * 64


def test_session_prediction_preserves_an_approved_result_without_fallback(monkeypatch):
    import voxneuro.ui.consumer_pages as consumer_pages

    approved_result = PredictionResult(
        prediction_id="approved-result",
        status="APPROVED",
        abstained=False,
        abstention_reasons=[],
        abstention_reason=None,
        model_id="approved-model",
        model_version="1.0",
        model_checksum="b" * 64,
        research_score=0.73,
        research_classification="PD-pattern candidate",
        calibration_status="EXTERNALLY_VALIDATED_CALIBRATED",
        score_kind="calibrated_probability",
    )
    monkeypatch.setattr(consumer_pages, "run_prediction_service", lambda **kwargs: approved_result)

    actual = consumer_pages.build_session_prediction(
        features=_features(),
        quality_valid=True,
        capture_origin="user_upload",
        input_domain="laptop_microphone",
        acquisition_domain_source="user_declared",
        conn=None,
        user=None,
    )

    assert actual is approved_result


def _provenance_fixture(tmp_path, monkeypatch):
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    model_dir = tmp_path / "artifacts" / "models"
    model_dir.mkdir(parents=True)
    nested_report = tmp_path / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html"
    nested_report.parent.mkdir(parents=True)
    nested_report.write_text("<html>test report</html>", encoding="utf-8")

    manifest_path = processed / "feature_manifest.csv"
    feature_path = processed / "voice_features.csv"
    metrics_path = processed / "model_metrics.csv"
    predictions_path = processed / "model_oof_predictions.csv"
    extraction_receipt = processed / "feature_extraction_receipt.json"
    evaluation_receipt = processed / "model_evaluation_receipt.json"
    nested_receipt = processed / "nested_uams_evaluation_receipt.json"
    nested_metrics = processed / "nested_uams_metrics.csv"
    nested_predictions = processed / "nested_uams_oof_predictions.csv"
    nested_summary = processed / "nested_uams_summary.csv"
    for path in (
        manifest_path,
        metrics_path,
        predictions_path,
        extraction_receipt,
        evaluation_receipt,
        nested_receipt,
        nested_metrics,
        nested_predictions,
        nested_summary,
    ):
        path.write_text("test artifact\n", encoding="utf-8")
    manifest_path.write_text("sample_id\ns1\ns2\n", encoding="utf-8")
    frame = pd.DataFrame(
        [
            {"participant_id": "p1", **dict.fromkeys(FEATURE_NAMES, 0.0)},
            {"participant_id": "p2", **dict.fromkeys(FEATURE_NAMES, 1.0)},
        ]
    )
    frame.to_csv(feature_path, index=False)

    code_hash = "d" * 64
    monkeypatch.setattr(inference_provenance, "project_code_fingerprint", lambda: code_hash)
    monkeypatch.setattr(inference_provenance, "validate_extraction_receipt", lambda *args: [])
    monkeypatch.setattr(inference_provenance, "validate_evaluation_receipt", lambda *args: [])
    monkeypatch.setattr(
        inference_provenance, "validate_nested_evaluation_receipt", lambda *args: []
    )
    audio = load_config("audio_config.yaml")
    feature = load_config("feature_config.yaml")
    monkeypatch.setattr(
        inference_provenance,
        "load_config",
        lambda name: audio if name == "audio_config.yaml" else feature,
    )
    digest = hashlib.sha256(manifest_path.read_bytes() + feature_path.read_bytes()).hexdigest()
    distribution = {
        "schema_version": "voxneuro.training_distribution.v1",
        "dataset_sha256": digest,
        "source_scope": "final_refit_training_participants_only",
        "feature_schema_fingerprint": schema_fingerprint(),
        "feature_config_fingerprint": feature_config_fingerprint(feature),
        "preprocessing_config_fingerprint": configuration_fingerprint(audio),
        "feature_names": list(FEATURE_NAMES),
        "training_recording_count": 2,
        "training_participant_count": 2,
    }
    distribution_path = model_dir / "uams_logistic_research_distribution.json"
    distribution_path.write_text(json.dumps(distribution, sort_keys=True), encoding="utf-8")
    sidecar = distribution_path.with_suffix(distribution_path.suffix + ".sha256")
    sidecar.write_text(hashlib.sha256(distribution_path.read_bytes()).hexdigest(), encoding="ascii")
    bundle = {
        "code_version": code_hash,
        "dataset_checksum_sha256": digest,
        "training_evaluation_receipt_sha256": inference_provenance.combined_file_sha256(
            evaluation_receipt, nested_receipt
        ),
        "training_distribution_manifest": distribution,
    }
    model_path = model_dir / "uams_logistic_research.joblib"
    return bundle, model_path, distribution_path


def test_local_model_provenance_accepts_current_evidence_and_detects_tampering(
    tmp_path, monkeypatch
):
    bundle, model_path, distribution_path = _provenance_fixture(tmp_path, monkeypatch)
    assert (
        inference_provenance.verify_local_exploratory_provenance(
            bundle, model_path=model_path, project_root=tmp_path
        )
        == []
    )

    bundle["code_version"] = "0" * 64
    bundle["training_distribution_manifest"]["source_scope"] = "all_data"
    issues = inference_provenance.verify_local_exploratory_provenance(
        bundle, model_path=model_path, project_root=tmp_path
    )
    assert any("project-code fingerprint" in issue for issue in issues)
    assert any("source scope" in issue for issue in issues)

    distribution_path.with_suffix(distribution_path.suffix + ".sha256").write_text(
        "bad checksum", encoding="ascii"
    )
    issues = inference_provenance.verify_local_exploratory_provenance(
        {**bundle, "training_distribution_manifest": json.loads(distribution_path.read_text())},
        model_path=model_path,
        project_root=tmp_path,
    )
    assert any("checksum does not match" in issue for issue in issues)


def test_local_model_provenance_abstains_when_receipts_are_missing(tmp_path):
    issues = inference_provenance.verify_local_exploratory_provenance(
        {},
        model_path=tmp_path / "model.joblib",
        project_root=tmp_path,
    )
    assert len(issues) == 1
    assert "Current model evaluation evidence is missing" in issues[0]
