"""Run nested participant-wise model tuning on the current UAMS raw-audio table."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from voxneuro.config import load_config
from voxneuro.dataset.validation import (
    validate_extraction_receipt,
    validate_manifest,
)
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling.evaluation import evaluate_nested_grouped
from voxneuro.modeling.splits import grouped_splits
from voxneuro.provenance import project_code_fingerprint
from voxneuro.reporting.ml_report import render_nested_evaluation_html, summarize_nested_metrics

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run repeated nested participant-grouped tuning on the UAMS Core39 table. "
            "This experiment does not enable app microphone classification."
        )
    )
    parser.add_argument("--dataset", choices=["uams"], default="uams")
    parser.parse_args()

    cfg = load_config("model_config.yaml")
    processed = ROOT / "data" / "processed"
    feature_path = processed / "voice_features.csv"
    manifest_path = processed / "feature_manifest.csv"
    extraction_receipt = processed / "feature_extraction_receipt.json"
    if not feature_path.is_file() or not manifest_path.is_file():
        print(
            "Current UAMS feature table is missing; run dataset audit and feature extraction first."
        )
        return 2
    manifest = pd.read_csv(manifest_path)
    manifest_issues = validate_manifest(manifest, require_integrity=True)
    audio_config = load_config("audio_config.yaml")
    feature_config = load_config("feature_config.yaml")
    code_version = project_code_fingerprint()
    schema_hash = schema_fingerprint()
    feature_config_hash = feature_config_fingerprint(feature_config)
    preprocessing_config_hash = configuration_fingerprint(audio_config)
    extraction_issues = validate_extraction_receipt(
        extraction_receipt,
        manifest_path,
        feature_path,
        SCHEMA_VERSION,
        schema_hash,
        feature_config_hash,
        preprocessing_config_hash,
        code_version,
    )
    if manifest_issues or extraction_issues:
        for issue in [*manifest_issues, *extraction_issues]:
            print(f"- {issue}")
        print("Nested evaluation blocked until dataset and extraction provenance are current.")
        return 1

    frame = pd.read_csv(feature_path).dropna(subset=["class_label", "participant_id"])
    if frame["sample_id"].duplicated().any():
        print("Duplicate sample IDs found in the feature table; refusing to evaluate.")
        return 1
    if not frame["class_label"].isin(["HC", "PD"]).all():
        print("Unknown class labels found in the feature table; refusing to evaluate.")
        return 1
    labels = frame["class_label"].map({"HC": 0, "PD": 1}).to_numpy(dtype=int)
    groups = frame["participant_id"].to_numpy()
    # Validate both the outer and inner group counts before starting an expensive search.
    list(grouped_splits(labels, groups, int(cfg["cv_splits"]), int(cfg["random_seed"])))
    for fold_seed in range(int(cfg["cv_splits"])):
        outer = list(
            grouped_splits(
                labels,
                groups,
                int(cfg["cv_splits"]),
                int(cfg["random_seed"]) + fold_seed,
            )
        )
        for train, _ in outer:
            list(
                grouped_splits(
                    labels[train],
                    groups[train],
                    int(cfg["inner_cv_splits"]),
                    int(cfg["random_seed"]) + 1000 + fold_seed,
                )
            )
    age_available = "age" in frame and frame["age"].notna().sum() >= 10
    additional_searches = None
    if age_available:
        age_pipeline = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=5000,
                        random_state=int(cfg["random_seed"]),
                    ),
                ),
            ]
        )
        grid = {"classifier__C": [0.01, 0.1, 1.0, 10.0, 100.0]}
        age = frame[["age"]].copy()
        age_plus_voice = frame[["age", *FEATURE_NAMES]].copy()
        additional_searches = {
            "age_only_logistic": (age, age_pipeline, grid),
            "age_plus_voice_logistic": (age_plus_voice, age_pipeline, grid),
        }

    repeat_seeds = tuple(
        int(cfg["random_seed"]) + offset for offset in range(int(cfg["cv_repeats"]))
    )
    start = time.perf_counter()
    metrics, predictions, fold_metrics = evaluate_nested_grouped(
        frame[FEATURE_NAMES],
        labels,
        groups,
        outer_splits=int(cfg["cv_splits"]),
        inner_splits=int(cfg["inner_cv_splits"]),
        random_seeds=repeat_seeds,
        bootstrap_iterations=int(cfg["bootstrap_iterations"]),
        additional_searches=additional_searches,
    )
    elapsed_seconds = time.perf_counter() - start
    summary = summarize_nested_metrics(metrics, repeat_seeds[0])
    out = processed
    metrics_path = out / "nested_uams_metrics.csv"
    predictions_path = out / "nested_uams_oof_predictions.csv"
    folds_path = out / "nested_uams_fold_metrics.csv"
    summary_path = out / "nested_uams_summary.csv"
    metrics.to_csv(metrics_path, index=False)
    predictions.to_csv(predictions_path, index=False)
    fold_metrics.to_csv(folds_path, index=False)
    summary.to_csv(summary_path, index=False)

    tuning = predictions.groupby(
        ["model", "repeat_seed", "outer_fold"], as_index=False, sort=False
    )["selected_parameters"].first()
    pd_counts = frame.groupby("class_label")["participant_id"].nunique().to_dict()
    hc_count = int(pd_counts.get("HC", 0))
    pd_count = int(pd_counts.get("PD", 0))
    report_path = ROOT / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_html = render_nested_evaluation_html(
        dataset_name="UAMS raw-audio Core39 cohort",
        source_description=(
            "UAMS sustained-vowel recordings, Figshare DOI 10.6084/m9.figshare.23849127.v1; "
            "telephone-collected, with the local source archive and manifest checks verified."
        ),
        participant_count=int(frame["participant_id"].nunique()),
        pd_participants=pd_count,
        hc_participants=hc_count,
        recording_count=len(frame),
        feature_description=(
            f"{len(FEATURE_NAMES)} Core39 acoustic features from the current {SCHEMA_VERSION} "
            "schema; age and sex are excluded from voice-only models."
        ),
        outer_splits=int(cfg["cv_splits"]),
        inner_splits=int(cfg["inner_cv_splits"]),
        repeat_seeds=repeat_seeds,
        summary=summary,
        predictions=predictions,
        primary_seed=repeat_seeds[0],
        fold_metrics=fold_metrics,
        tuning_results=tuning,
        limitations=(
            (
                "Only 78 participants have usable features: 37 PD and 41 HC. Three clipped source "
                "recordings are excluded, all from the PD group."
            ),
            (
                "The HC and PD groups differ substantially in age. The age-only comparator can "
                "outperform voice models; this prevents disease-specific attribution."
            ),
            (
                "This is internal cross-validation on a small retrospective cohort, not an "
                "independent external test or clinical validation."
            ),
            (
                "The dataset is telephone-collected. Compatibility with laptop, smartphone, "
                "browser microphone, other languages, and other recording tasks is unverified."
            ),
            (
                "Probability outputs are uncalibrated. No clinical decision threshold or "
                "diagnostic interpretation is available."
            ),
        ),
    )
    report_path.write_text(report_html, encoding="utf-8")

    receipt = {
        "status": "complete",
        "dataset": "uams",
        "created_utc": datetime.now(UTC).isoformat(),
        "code_version": code_version,
        "feature_schema_version": SCHEMA_VERSION,
        "feature_schema_fingerprint": schema_hash,
        "feature_config_fingerprint": feature_config_hash,
        "preprocessing_config_fingerprint": preprocessing_config_hash,
        "manifest_sha256": _sha256(manifest_path),
        "feature_table_sha256": _sha256(feature_path),
        "outer_splits": int(cfg["cv_splits"]),
        "inner_splits": int(cfg["inner_cv_splits"]),
        "repeat_seeds": list(repeat_seeds),
        "bootstrap_iterations": int(cfg["bootstrap_iterations"]),
        "bootstrap_method": (
            "class-stratified participant bootstrap on primary-seed outer-fold OOF predictions"
        ),
        "group_unit": "participant_id",
        "selection_metric": "inner-fold balanced accuracy",
        "threshold_policy": "default estimator decision rule; no outer-fold threshold selection",
        "probability_calibration": "not fitted; predict_proba values are uncalibrated",
        "elapsed_seconds": round(elapsed_seconds, 3),
        "metrics_sha256": _sha256(metrics_path),
        "predictions_sha256": _sha256(predictions_path),
        "fold_metrics_sha256": _sha256(folds_path),
        "summary_sha256": _sha256(summary_path),
        "report_sha256": _sha256(report_path),
    }
    receipt_path = processed / "nested_uams_evaluation_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        summary[
            [
                "model",
                "balanced_accuracy_mean",
                "balanced_accuracy_repeat_sd",
                "precision_mean",
                "sensitivity_mean",
                "specificity_mean",
                "roc_auc_mean",
                "pr_auc_mean",
                "average_precision_mean",
            ]
        ].to_string(index=False)
    )
    print(f"Nested report: {report_path}")
    print(f"Receipt: {receipt_path}")
    print(
        "All estimates are participant-level internal CV. The probability scores are uncalibrated; "
        "this procedure does not authorize or enable microphone disease predictions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
