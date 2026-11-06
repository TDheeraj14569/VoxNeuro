"""Reload and exercise a saved model bundle with schema-aligned features."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from voxneuro.config import load_config
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
from voxneuro.modeling.model_bundle import load_bundle
from voxneuro.provenance import combined_file_sha256, project_code_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    bundle_path = ROOT / "artifacts" / "models" / "uams_logistic_research.joblib"
    feature_path = ROOT / "data" / "processed" / "voice_features.csv"
    processed = ROOT / "data" / "processed"
    manifest_path = processed / "feature_manifest.csv"
    evaluation_receipt = processed / "model_evaluation_receipt.json"
    metrics_path = processed / "model_metrics.csv"
    nested_receipt = processed / "nested_uams_evaluation_receipt.json"
    nested_artifacts = {
        "metrics_sha256": processed / "nested_uams_metrics.csv",
        "predictions_sha256": processed / "nested_uams_oof_predictions.csv",
        "summary_sha256": processed / "nested_uams_summary.csv",
        "report_sha256": ROOT / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html",
    }
    if not bundle_path.is_file() or not feature_path.is_file() or not manifest_path.is_file():
        print(
            "Model bundle or UAMS feature table missing; run dataset extraction and "
            "model training first."
        )
        return 2
    audio_config = load_config("audio_config.yaml")
    feature_config = load_config("feature_config.yaml")
    code_version = project_code_fingerprint()
    schema_hash = schema_fingerprint()
    feature_config_hash = feature_config_fingerprint(feature_config)
    preprocessing_config_hash = configuration_fingerprint(audio_config)
    receipts = [
        *validate_extraction_receipt(
            processed / "feature_extraction_receipt.json",
            manifest_path,
            feature_path,
            SCHEMA_VERSION,
            schema_hash,
            feature_config_hash,
            preprocessing_config_hash,
            code_version,
        ),
        *validate_evaluation_receipt(
            evaluation_receipt,
            manifest_path,
            feature_path,
            metrics_path,
            SCHEMA_VERSION,
            code_version,
            schema_hash,
            feature_config_hash,
            preprocessing_config_hash,
        ),
        *validate_nested_evaluation_receipt(
            nested_receipt,
            {
                "status": "complete",
                "dataset": "uams",
                "code_version": code_version,
                "feature_schema_version": SCHEMA_VERSION,
                "feature_schema_fingerprint": schema_hash,
                "feature_config_fingerprint": feature_config_hash,
                "preprocessing_config_fingerprint": preprocessing_config_hash,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "feature_table_sha256": hashlib.sha256(feature_path.read_bytes()).hexdigest(),
            },
            nested_artifacts,
        ),
    ]
    if receipts:
        for issue in receipts:
            print(f"- {issue}")
        return 1
    bundle = load_bundle(bundle_path)
    evaluation_sha256 = combined_file_sha256(evaluation_receipt, nested_receipt)
    expected_dataset_sha256 = hashlib.sha256(
        manifest_path.read_bytes() + feature_path.read_bytes()
    ).hexdigest()
    if (
        bundle.get("training_evaluation_receipt_sha256") != evaluation_sha256
        or bundle.get("dataset_checksum_sha256") != expected_dataset_sha256
        or bundle.get("code_version") != code_version
    ):
        print("FAIL model bundle provenance does not match current dataset/evaluation/code.")
        return 1
    row = pd.read_csv(feature_path)[FEATURE_NAMES].iloc[[0]]
    first = bundle["model"].predict(row)
    second = load_bundle(bundle_path)["model"].predict(row)
    if not np.array_equal(first, second):
        print("FAIL reload prediction is not consistent")
        return 1
    if (
        bundle.get("domain_compatibility_verified") is not False
        or bundle.get("research_only") is not True
    ):
        print("FAIL safety status metadata missing")
        return 1
    print("PASS bundle reload and prediction consistency")
    print("PASS model artifact checksum and current provenance")
    print("PASS research-only/domain-compatibility status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
