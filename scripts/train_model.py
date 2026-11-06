"""Fit a research model only after current grouped evaluation has completed."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import platform
from pathlib import Path

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
from voxneuro.modeling.model_bundle import make_bundle, save_bundle
from voxneuro.modeling.training import fit_tuned_logistic_reference
from voxneuro.provenance import combined_file_sha256, project_code_fingerprint

ROOT = Path(__file__).resolve().parents[1]
DATASET_VERSION = "UAMS Figshare 10.6084/m9.figshare.23849127.v1"


def _versions() -> dict[str, str]:
    """Capture runtime and all direct signal/model dependencies used by this project."""
    versions = {
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    for package in (
        "joblib",
        "matplotlib",
        "librosa",
        "numpy",
        "pandas",
        "praat-parselmouth",
        "PyYAML",
        "scikit-learn",
        "scipy",
        "soundfile",
        "streamlit",
    ):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        choices=["uams"],
        default="uams",
        help="Only the raw-UAMS feature schema is supported here.",
    )
    parser.parse_args()
    processed = ROOT / "data" / "processed"
    path = processed / "voice_features.csv"
    manifest_path = processed / "feature_manifest.csv"
    extraction_receipt = processed / "feature_extraction_receipt.json"
    evaluation_receipt = processed / "model_evaluation_receipt.json"
    metrics_path = processed / "model_metrics.csv"
    nested_receipt_path = processed / "nested_uams_evaluation_receipt.json"
    nested_metrics_path = processed / "nested_uams_metrics.csv"
    nested_predictions_path = processed / "nested_uams_oof_predictions.csv"
    nested_summary_path = processed / "nested_uams_summary.csv"
    nested_report_path = ROOT / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html"
    if not path.is_file():
        print(
            "No UAMS feature table. Run inspect_dataset.py, build_manifest.py, "
            "and extract_features.py first."
        )
        return 2
    audio_config = load_config("audio_config.yaml")
    feature_config = load_config("feature_config.yaml")
    code_version = project_code_fingerprint()
    schema_hash = schema_fingerprint()
    feature_config_hash = feature_config_fingerprint(feature_config)
    preprocessing_config_hash = configuration_fingerprint(audio_config)
    extraction_issues = validate_extraction_receipt(
        extraction_receipt,
        manifest_path,
        path,
        SCHEMA_VERSION,
        schema_hash,
        feature_config_hash,
        preprocessing_config_hash,
        code_version,
    )
    evaluation_issues = validate_evaluation_receipt(
        evaluation_receipt,
        manifest_path,
        path,
        metrics_path,
        SCHEMA_VERSION,
        code_version,
        schema_hash,
        feature_config_hash,
        preprocessing_config_hash,
    )
    nested_issues = validate_nested_evaluation_receipt(
        nested_receipt_path,
        {
            "status": "complete",
            "dataset": "uams",
            "code_version": code_version,
            "feature_schema_version": SCHEMA_VERSION,
            "feature_schema_fingerprint": schema_hash,
            "feature_config_fingerprint": feature_config_hash,
            "preprocessing_config_fingerprint": preprocessing_config_hash,
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            if manifest_path.is_file()
            else "",
            "feature_table_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_file()
            else "",
        },
        {
            "metrics_sha256": nested_metrics_path,
            "predictions_sha256": nested_predictions_path,
            "summary_sha256": nested_summary_path,
            "report_sha256": nested_report_path,
        },
    )
    if extraction_issues or evaluation_issues or nested_issues:
        for issue in [*extraction_issues, *evaluation_issues, *nested_issues]:
            print(f"- {issue}")
        print(
            "Training blocked: run and verify the current extraction and grouped evaluation first."
        )
        return 1
    model_config = load_config("model_config.yaml")
    if model_config.get("allow_user_microphone_inference") is not False:
        print("Microphone inference is disabled by this prototype; refusing configuration change.")
        return 1
    frame = pd.read_csv(path).dropna(subset=["class_label", "participant_id"])
    if (
        frame["sample_id"].duplicated().any()
        or frame["participant_id"].duplicated().any()
        or not frame["class_label"].isin(["PD", "HC"]).all()
    ):
        print(
            "The single-recording UAMS model needs unique sample and participant IDs and valid "
            "labels; refusing to fit."
        )
        return 1
    if frame[FEATURE_NAMES].empty or frame["class_label"].nunique() != 2:
        print("Expected non-empty features and both HC and PD labels; refusing to fit.")
        return 2
    X = frame[FEATURE_NAMES]
    y = frame["class_label"].map({"HC": 0, "PD": 1})
    if y.isna().any():
        print("Expected exactly HC and PD labels; refusing to fit.")
        return 2
    # Keep logistic regression as the interpretable exploratory reference model.
    # It is not selected for top CV score; small-fold differences are not enough
    # to justify choosing a more complex candidate without independent validation.
    model, training_details = fit_tuned_logistic_reference(
        X,
        y.astype(int),
        frame["participant_id"].to_numpy(),
        n_splits=int(model_config["cv_splits"]),
        random_seed=int(model_config["random_seed"]),
    )
    checksum = hashlib.sha256(manifest_path.read_bytes() + path.read_bytes()).hexdigest()
    bundle = make_bundle(
        model,
        dataset_provenance=("UAMS Figshare DOI 10.6084/m9.figshare.23849127; see dataset report"),
        dataset_version=DATASET_VERSION,
        dataset_checksum_sha256=checksum,
        code_version=code_version,
        training_evaluation_receipt_sha256=combined_file_sha256(
            evaluation_receipt, nested_receipt_path
        ),
        validation_method=(
            f"Repeated {model_config['cv_repeats']}×{model_config['cv_splits']} outer and "
            f"{model_config['inner_cv_splits']}-fold inner StratifiedGroupKFold participant-wise "
            "evaluation; final L2 logistic reference refit on all development participants"
        ),
        software_versions=_versions(),
        preprocessing_config=audio_config,
        feature_config=feature_config,
        allow_user_microphone_inference=bool(model_config["allow_user_microphone_inference"]),
        training_details=training_details,
    )
    destination = ROOT / "artifacts" / "models" / "uams_logistic_research.joblib"
    save_bundle(bundle, destination)
    classifier = model.named_steps["classifier"]
    imputer = model.named_steps["imputer"]
    coefficient_names = imputer.get_feature_names_out(FEATURE_NAMES)
    coefficients = pd.DataFrame(
        {
            "feature": coefficient_names,
            "standardized_logistic_coefficient": classifier.coef_[0],
        }
    )
    coefficients["absolute_coefficient"] = coefficients["standardized_logistic_coefficient"].abs()
    coefficients.sort_values("absolute_coefficient", ascending=False).to_csv(
        processed / "uams_logistic_coefficients.csv", index=False
    )
    print(
        f"Saved research-only bundle with {frame['participant_id'].nunique()} participants "
        f"to {destination}"
    )
    print(
        "This cohort model is not exposed for new microphone audio; "
        "domain compatibility is unverified."
    )
    print("Saved exploratory coefficients; these are associations, not biomarkers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
