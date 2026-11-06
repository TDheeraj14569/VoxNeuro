"""Run participant-wise grouped baselines and an age-only comparator."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from voxneuro.config import load_config
from voxneuro.dataset.uci import load_uci_feature_table, uci_schema_fingerprint
from voxneuro.dataset.validation import (
    read_json_object,
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
from voxneuro.modeling.evaluation import age_only_pipeline, binary_metrics, evaluate_grouped
from voxneuro.modeling.pipeline import build_pipelines
from voxneuro.modeling.splits import grouped_splits
from voxneuro.provenance import project_code_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def subgroup_summary(
    predictions: pd.DataFrame, metadata: pd.DataFrame, subgroup_column: str
) -> pd.DataFrame:
    """Compute participant-level subgroup metrics only when each class has at least 10 people."""
    joined = predictions.merge(metadata, on="participant_id", how="left", validate="many_to_one")
    rows = []
    for (model, subgroup_value), subset in joined.groupby(["model", subgroup_column], dropna=False):
        counts = subset["y_true"].value_counts()
        if min(counts.get(0, 0), counts.get(1, 0)) < 10:
            continue
        scores = subset["score"].to_numpy(dtype=float)
        metrics = binary_metrics(
            subset["y_true"].to_numpy(dtype=int),
            subset["y_pred"].to_numpy(dtype=int),
            scores if np.isfinite(scores).all() else None,
        )
        rows.append(
            {
                "model": model,
                "subgroup_variable": subgroup_column,
                "subgroup_value": str(subgroup_value),
                "n_participants": len(subset),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def grouped_voice_importance(
    X: pd.DataFrame, y: np.ndarray, groups: np.ndarray, n_splits: int, random_seed: int
) -> pd.DataFrame:
    """Estimate held-out permutation importance for the voice-only random forest."""
    fold_rows = []
    folds = grouped_splits(y, groups, n_splits, random_seed)
    for fold, (train, test) in enumerate(folds, start=1):
        estimator = build_pipelines(random_seed)["random_forest"]
        estimator.fit(X.iloc[train], y[train])
        importance = permutation_importance(
            estimator,
            X.iloc[test],
            y[test],
            scoring="balanced_accuracy",
            n_repeats=10,
            random_state=random_seed + fold,
            n_jobs=1,
        )
        fold_rows.extend(
            {
                "feature": feature,
                "fold": fold,
                "mean_balanced_accuracy_decrease": float(mean),
                "permutation_sd": float(std),
            }
            for feature, mean, std in zip(
                FEATURE_NAMES,
                importance.importances_mean,
                importance.importances_std,
                strict=True,
            )
        )
    return (
        pd.DataFrame(fold_rows)
        .groupby("feature", as_index=False)
        .agg(
            mean_balanced_accuracy_decrease=("mean_balanced_accuracy_decrease", "mean"),
            fold_sd=("mean_balanced_accuracy_decrease", "std"),
            folds_positive=(
                "mean_balanced_accuracy_decrease",
                lambda values: int((values > 0).sum()),
            ),
        )
        .sort_values("mean_balanced_accuracy_decrease", ascending=False)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["uams", "uci"], default="uams")
    args = parser.parse_args()
    cfg = load_config("model_config.yaml")
    if args.dataset == "uci":
        source = ROOT / "data" / "interim" / "uci" / "pd_speech_features.csv"
        if not source.is_file():
            print("UCI feature CSV missing. Run scripts/inspect_dataset.py first.")
            return 2
        source_receipt_path = source.parent / "uci_extraction_receipt.json"
        archive_path = ROOT / "data" / "raw" / "uci" / "download" / "pd_speech_features.rar"
        if not source_receipt_path.is_file() or not archive_path.is_file():
            print("UCI extraction receipt or official source archive is missing; rerun inspection.")
            return 1
        try:
            source_receipt = read_json_object(source_receipt_path, "UCI extraction receipt")
        except ValueError as exc:
            print(f"UCI extraction receipt cannot be read: {exc}")
            return 1
        if (
            source_receipt.get("archive_sha256")
            != hashlib.sha256(archive_path.read_bytes()).hexdigest()
            or source_receipt.get("csv_sha256") != hashlib.sha256(source.read_bytes()).hexdigest()
            or source_receipt.get("schema_manifest_sha256") != uci_schema_fingerprint()
        ):
            print(
                "UCI source archive, extracted table, and receipt do not match; rerun inspection."
            )
            return 1
        try:
            table = load_uci_feature_table(source)
        except ValueError as exc:
            print(f"UCI feature table failed integrity validation: {exc}")
            return 2
        groups = table["id"].to_numpy()
        y = table["class"].astype(int).to_numpy()
        predictors = table.drop(columns=["id", "gender", "class"])
        metrics, predictions = evaluate_grouped(
            predictors,
            y,
            groups,
            n_splits=int(cfg["cv_splits"]),
            random_seed=int(cfg["random_seed"]),
        )
        out = ROOT / "data" / "processed"
        out.mkdir(parents=True, exist_ok=True)
        metrics.to_csv(out / "uci_model_metrics.csv", index=False)
        predictions.to_csv(out / "uci_oof_predictions.csv", index=False)
        duplicate_mask = table.duplicated(keep="first")
        duplicate_participants = int(table.loc[duplicate_mask, "id"].nunique())
        if duplicate_mask.any():
            unique_table = table.loc[~duplicate_mask].reset_index(drop=True)
            unique_predictors = unique_table.drop(columns=["id", "gender", "class"])
            unique_metrics, unique_predictions = evaluate_grouped(
                unique_predictors,
                unique_table["class"].astype(int).to_numpy(),
                unique_table["id"].to_numpy(),
                n_splits=int(cfg["cv_splits"]),
                random_seed=int(cfg["random_seed"]),
            )
            unique_metrics.to_csv(out / "uci_deduplicated_sensitivity_metrics.csv", index=False)
            unique_predictions.to_csv(
                out / "uci_deduplicated_sensitivity_predictions.csv", index=False
            )
            metric_names = [
                "balanced_accuracy",
                "sensitivity",
                "specificity",
                "roc_auc",
                "average_precision",
            ]
            primary_summary = metrics.groupby("model")[metric_names].agg(["mean", "std"])
            unique_summary = unique_metrics.groupby("model")[metric_names].agg(["mean", "std"])
            sensitivity_rows = []
            for model_name in primary_summary.index:
                for metric in metric_names:
                    full_mean = float(primary_summary.loc[model_name, (metric, "mean")])
                    full_sd = float(primary_summary.loc[model_name, (metric, "std")])
                    unique_mean = float(unique_summary.loc[model_name, (metric, "mean")])
                    unique_sd = float(unique_summary.loc[model_name, (metric, "std")])
                    sensitivity_rows.append(
                        {
                            "model": model_name,
                            "metric": metric,
                            "with_exact_duplicate_mean": full_mean,
                            "with_exact_duplicate_sd": full_sd,
                            "after_exact_duplicate_removal_mean": unique_mean,
                            "after_exact_duplicate_removal_sd": unique_sd,
                            "mean_change_after_removal": unique_mean - full_mean,
                        }
                    )
            sensitivity_path = out / "uci_duplicate_sensitivity.csv"
            pd.DataFrame(sensitivity_rows).to_csv(sensitivity_path, index=False)
        else:
            unique_metrics = metrics
            unique_predictions = predictions
            sensitivity_path = out / "uci_duplicate_sensitivity.csv"
            pd.DataFrame(
                columns=[
                    "model",
                    "metric",
                    "with_exact_duplicate_mean",
                    "with_exact_duplicate_sd",
                    "after_exact_duplicate_removal_mean",
                    "after_exact_duplicate_removal_sd",
                    "mean_change_after_removal",
                ]
            ).to_csv(sensitivity_path, index=False)
        gender = (
            table.groupby("id", as_index=False)["gender"]
            .first()
            .rename(columns={"id": "participant_id"})
        )
        subgroup = subgroup_summary(predictions, gender, "gender")
        subgroup.to_csv(out / "uci_model_subgroup_metrics.csv", index=False)
        evaluation_receipt = {
            "status": "complete",
            "dataset": "uci",
            "created_utc": datetime.now(UTC).isoformat(),
            "archive_sha256": source_receipt.get("archive_sha256"),
            "schema_manifest_sha256": source_receipt.get("schema_manifest_sha256"),
            "publisher_archive_sha256": source_receipt.get("publisher_archive_sha256"),
            "feature_table_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "metrics_sha256": hashlib.sha256(
                (out / "uci_model_metrics.csv").read_bytes()
            ).hexdigest(),
            "duplicate_sensitivity_sha256": hashlib.sha256(
                sensitivity_path.read_bytes()
            ).hexdigest(),
            "code_version": project_code_fingerprint(),
            "cross_validation_splits": int(cfg["cv_splits"]),
            "group_unit": "id; metrics aggregated per participant",
            "source_recordings": int(len(table)),
            "unique_recordings_after_exact_duplicate_removal": int(
                len(table) - duplicate_mask.sum()
            ),
            "participants": int(table["id"].nunique()),
            "exact_duplicate_rows": int(duplicate_mask.sum()),
            "participants_with_exact_duplicate_rows": duplicate_participants,
        }
        (out / "uci_model_evaluation_receipt.json").write_text(
            json.dumps(evaluation_receipt, indent=2), encoding="utf-8"
        )
        print(
            metrics.groupby("model")[
                [
                    "balanced_accuracy",
                    "sensitivity",
                    "specificity",
                    "roc_auc",
                    "average_precision",
                ]
            ]
            .agg(["mean", "std"])
            .to_string()
        )
        print(
            f"Saved separate UCI grouped-fold results ({len(table)} rows, "
            f"{table['id'].nunique()} participants, 752 acoustic predictors; "
            f"{int(duplicate_mask.sum())} exact duplicate row(s) across "
            f"{duplicate_participants} participant(s), with sensitivity report at "
            f"{sensitivity_path.name}). "
            "Age-only baseline unavailable because row-level age is not supplied."
        )
        print(
            "This is a feature-table benchmark; it is not a test of VoxNeuro's raw-audio feature "
            "pipeline."
        )
        return 0
    feature_config = load_config("feature_config.yaml")
    audio_config = load_config("audio_config.yaml")
    feature_schema_hash = schema_fingerprint()
    feature_config_hash = feature_config_fingerprint(feature_config)
    preprocessing_config_hash = configuration_fingerprint(audio_config)
    code_version = project_code_fingerprint()
    path = ROOT / "data" / "processed" / "voice_features.csv"
    manifest_path = ROOT / "data" / "processed" / "feature_manifest.csv"
    extraction_receipt = ROOT / "data" / "processed" / "feature_extraction_receipt.json"
    if not path.is_file():
        print("Feature table is missing; run scripts/extract_features.py first.")
        return 2
    manifest = pd.read_csv(manifest_path) if manifest_path.is_file() else pd.DataFrame()
    manifest_issues = validate_manifest(manifest, require_integrity=True)
    extraction_issues = validate_extraction_receipt(
        extraction_receipt,
        manifest_path,
        path,
        SCHEMA_VERSION,
        feature_schema_hash,
        feature_config_hash,
        preprocessing_config_hash,
        code_version,
    )
    if manifest_issues or extraction_issues:
        for issue in [*manifest_issues, *extraction_issues]:
            print(f"- {issue}")
        print("Evaluation blocked until manifest and extraction provenance are valid.")
        return 1
    frame = (
        pd.read_csv(path).dropna(subset=["class_label", "participant_id"]).reset_index(drop=True)
    )
    y = frame["class_label"].map({"HC": 0, "PD": 1}).to_numpy()
    if pd.isna(y).any() or len(np.unique(y)) != 2:
        print("Valid binary HC/PD labels are required.")
        return 2
    age_present = frame["age"].notna().sum() if "age" in frame else 0
    additional_models = None
    if age_present >= 10:
        additional_models = {
            "age_only_logistic": (
                frame[["age"]],
                age_only_pipeline(int(cfg["random_seed"])),
            ),
            "age_plus_voice_logistic": (
                frame[["age", *FEATURE_NAMES]],
                age_only_pipeline(int(cfg["random_seed"])),
            ),
        }
    metrics, predictions = evaluate_grouped(
        frame[FEATURE_NAMES],
        y,
        frame["participant_id"].to_numpy(),
        n_splits=int(cfg["cv_splits"]),
        random_seed=int(cfg["random_seed"]),
        additional_models=additional_models,
    )
    out = ROOT / "data" / "processed"
    metrics.to_csv(out / "model_metrics.csv", index=False)
    predictions.to_csv(out / "model_oof_predictions.csv", index=False)
    participant_metadata = frame.groupby("participant_id", as_index=False)["sex"].first()
    subgroup = subgroup_summary(predictions, participant_metadata, "sex")
    subgroup.to_csv(out / "model_subgroup_metrics.csv", index=False)
    importance = grouped_voice_importance(
        frame[FEATURE_NAMES],
        y,
        frame["participant_id"].to_numpy(),
        int(cfg["cv_splits"]),
        int(cfg["random_seed"]),
    )
    importance.to_csv(out / "model_feature_importance.csv", index=False)
    evaluation_receipt = {
        "status": "complete",
        "dataset": "uams",
        "created_utc": datetime.now(UTC).isoformat(),
        "feature_schema_version": SCHEMA_VERSION,
        "code_version": code_version,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "feature_table_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "feature_schema_fingerprint": feature_schema_hash,
        "feature_config_fingerprint": feature_config_hash,
        "preprocessing_config_fingerprint": preprocessing_config_hash,
        "metrics_sha256": hashlib.sha256((out / "model_metrics.csv").read_bytes()).hexdigest(),
        "predictions_sha256": hashlib.sha256(
            (out / "model_oof_predictions.csv").read_bytes()
        ).hexdigest(),
        "cross_validation_splits": int(cfg["cv_splits"]),
        "group_unit": "participant_id",
        "comparators": ["voice_only", "age_only", "age_plus_voice"]
        if age_present >= 10
        else ["voice_only"],
        "age_plus_voice_comparator_is_exploratory": True,
        "model_selection_policy": (
            "The logistic model is retained as an interpretable research reference; CV scores "
            "are not used to select a clinical model or threshold."
        ),
    }
    receipt_path = out / "model_evaluation_receipt.json"
    receipt_path.write_text(json.dumps(evaluation_receipt, indent=2), encoding="utf-8")
    print(
        metrics.groupby("model")[
            [
                "balanced_accuracy",
                "sensitivity",
                "specificity",
                "roc_auc",
                "average_precision",
            ]
        ]
        .agg(["mean", "std"])
        .to_string()
    )
    print(
        f"Saved grouped fold metrics and OOF predictions under {out}; "
        f"evaluation receipt: {receipt_path}; no independent external test set exists."
    )
    print(
        "Saved exploratory held-out random-forest permutation importance (not biomarker evidence)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
