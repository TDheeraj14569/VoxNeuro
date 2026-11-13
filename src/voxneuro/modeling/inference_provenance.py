"""Provenance checks required before using the local exploratory research model."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from voxneuro.config import PROJECT_ROOT, load_config
from voxneuro.dataset.validation import (
    validate_evaluation_receipt,
    validate_extraction_receipt,
    validate_nested_evaluation_receipt,
)
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.provenance import combined_file_sha256, project_code_fingerprint


def verify_local_exploratory_provenance(
    bundle: dict[str, Any],
    *,
    model_path: Path,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    """Check the model, current UAMS receipts, training data, and distribution manifest."""
    root = project_root.resolve()
    processed = root / "data" / "processed"
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
    nested_report = root / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html"

    required = (
        manifest_path,
        feature_path,
        metrics_path,
        predictions_path,
        extraction_receipt,
        evaluation_receipt,
        nested_receipt,
        nested_metrics,
        nested_predictions,
        nested_summary,
        nested_report,
    )
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        return ["Current model evaluation evidence is missing: " + ", ".join(sorted(missing))]

    audio_config = load_config("audio_config.yaml")
    feature_config = load_config("feature_config.yaml")
    code_fingerprint = project_code_fingerprint()
    schema_hash = schema_fingerprint()
    feature_hash = feature_config_fingerprint(feature_config)
    preprocessing_hash = configuration_fingerprint(audio_config)
    issues = [
        *validate_extraction_receipt(
            extraction_receipt,
            manifest_path,
            feature_path,
            SCHEMA_VERSION,
            schema_hash,
            feature_hash,
            preprocessing_hash,
            code_fingerprint,
        ),
        *validate_evaluation_receipt(
            evaluation_receipt,
            manifest_path,
            feature_path,
            metrics_path,
            SCHEMA_VERSION,
            code_fingerprint,
            schema_hash,
            feature_hash,
            preprocessing_hash,
            predictions_path,
        ),
        *validate_nested_evaluation_receipt(
            nested_receipt,
            {
                "status": "complete",
                "dataset": "uams",
                "code_version": code_fingerprint,
                "feature_schema_version": SCHEMA_VERSION,
                "feature_schema_fingerprint": schema_hash,
                "feature_config_fingerprint": feature_hash,
                "preprocessing_config_fingerprint": preprocessing_hash,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "feature_table_sha256": hashlib.sha256(feature_path.read_bytes()).hexdigest(),
            },
            {
                "metrics_sha256": nested_metrics,
                "predictions_sha256": nested_predictions,
                "summary_sha256": nested_summary,
                "report_sha256": nested_report,
            },
        ),
    ]
    if issues:
        return issues

    expected_dataset_hash = hashlib.sha256(
        manifest_path.read_bytes() + feature_path.read_bytes()
    ).hexdigest()
    if bundle.get("code_version") != code_fingerprint:
        issues.append("The model was built from a different project-code fingerprint.")
    if bundle.get("dataset_checksum_sha256") != expected_dataset_hash:
        issues.append("The model dataset checksum does not match the current UAMS training data.")
    if bundle.get("training_evaluation_receipt_sha256") != combined_file_sha256(
        evaluation_receipt, nested_receipt
    ):
        issues.append("The model is not bound to the current grouped evaluation receipts.")

    distribution = bundle.get("training_distribution_manifest")
    if not isinstance(distribution, dict):
        issues.append("The model has no training-distribution manifest.")
        return issues
    if distribution.get("dataset_sha256") != expected_dataset_hash:
        issues.append("Training-distribution statistics do not match the current training data.")
    if distribution.get("source_scope") != "final_refit_training_participants_only":
        issues.append("Training-distribution statistics have an invalid source scope.")
    if (
        distribution.get("feature_schema_fingerprint") != schema_hash
        or distribution.get("feature_config_fingerprint") != feature_hash
        or distribution.get("preprocessing_config_fingerprint") != preprocessing_hash
        or distribution.get("feature_names") != list(FEATURE_NAMES)
    ):
        issues.append("Training-distribution statistics do not match the current feature contract.")

    distribution_path = model_path.with_name("uams_logistic_research_distribution.json")
    sidecar = distribution_path.with_suffix(distribution_path.suffix + ".sha256")
    if not distribution_path.is_file() or not sidecar.is_file():
        issues.append(
            "The versioned training-distribution manifest or checksum sidecar is missing."
        )
    else:
        actual_hash = hashlib.sha256(distribution_path.read_bytes()).hexdigest()
        expected_hash = sidecar.read_text(encoding="ascii").strip().casefold()
        if actual_hash != expected_hash:
            issues.append("Training-distribution manifest checksum does not match.")
        try:
            saved_distribution = json.loads(distribution_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            issues.append("Training-distribution manifest cannot be read as JSON.")
        else:
            if saved_distribution != distribution:
                issues.append("Saved and embedded training-distribution manifests differ.")

    try:
        features = pd.read_csv(feature_path)
        training_rows = int(len(features))
        training_participants = int(features["participant_id"].nunique())
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        issues.append("Current UAMS feature table cannot be validated.")
    else:
        if training_rows != distribution.get("training_recording_count"):
            issues.append("Training-distribution recording count does not match training data.")
        if training_participants != distribution.get("training_participant_count"):
            issues.append("Training-distribution participant count does not match training data.")
    return issues
