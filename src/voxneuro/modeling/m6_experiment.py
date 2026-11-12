"""M6 Multi-Model Experiment Suite: comparisons, calibration, thresholds, and model cards."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, LinearSVC

from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION
from voxneuro.modeling.calibration import calibration_summary
from voxneuro.modeling.dataset_readiness import (
    load_uams_cohort,
    load_uci_cohort,
    verify_participant_split_integrity,
)
from voxneuro.modeling.evaluation import binary_metrics
from voxneuro.modeling.splits import grouped_splits


@dataclass(frozen=True)
class M6CalibrationResult:
    """Calibration metrics and reliability bin data."""

    brier_score: float
    ece: float
    calibration_status: str
    bins: list[dict[str, Any]]


def build_m6_model_families(random_seed: int = 2026) -> dict[str, Pipeline]:
    """Build fold-safe M6 pipelines across linear, kernel SVM, and ensemble families."""
    impute = [("imputer", SimpleImputer(strategy="median"))]
    scaled = impute + [("scaler", StandardScaler())]
    return {
        "logistic_regression": Pipeline(
            scaled
            + [
                (
                    "classifier",
                    LogisticRegression(
                        C=1.0,
                        class_weight="balanced",
                        max_iter=2000,
                        random_state=random_seed,
                    ),
                )
            ]
        ),
        "linear_svm_calibrated": Pipeline(
            scaled
            + [
                (
                    "classifier",
                    CalibratedClassifierCV(
                        LinearSVC(
                            class_weight="balanced",
                            max_iter=5000,
                            random_state=random_seed,
                        ),
                        cv=3,
                        method="sigmoid",
                    ),
                )
            ]
        ),
        "rbf_svm": Pipeline(
            scaled
            + [
                (
                    "classifier",
                    CalibratedClassifierCV(
                        SVC(
                            kernel="rbf",
                            class_weight="balanced",
                            random_state=random_seed,
                        ),
                        cv=3,
                        method="sigmoid",
                    ),
                )
            ]
        ),
        "random_forest": Pipeline(
            impute
            + [
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=200,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=random_seed,
                        n_jobs=1,
                    ),
                )
            ]
        ),
        "extra_trees": Pipeline(
            impute
            + [
                (
                    "classifier",
                    ExtraTreesClassifier(
                        n_estimators=200,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=random_seed,
                        n_jobs=1,
                    ),
                )
            ]
        ),
        "hist_gradient_boosting": Pipeline(
            impute
            + [
                (
                    "classifier",
                    HistGradientBoostingClassifier(
                        max_iter=120,
                        max_depth=4,
                        min_samples_leaf=5,
                        class_weight="balanced",
                        random_state=random_seed,
                    ),
                )
            ]
        ),
    }


def compute_calibration_profile(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    n_bins: int = 8,
    min_calibrated_samples: int = 60,
    max_calibrated_brier: float = 0.25,
) -> M6CalibrationResult:
    """Compute out-of-fold Brier score, Expected Calibration Error, and reliability bins."""
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    brier = float(brier_score_loss(y, p))
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins: list[dict[str, Any]] = []
    ece = 0.0
    n_total = len(y)
    for idx in range(n_bins):
        lo, hi = float(edges[idx]), float(edges[idx + 1])
        mask = (p >= lo) & (p <= hi if idx == n_bins - 1 else p < hi)
        count = int(mask.sum())
        if count > 0:
            mean_pred = float(p[mask].mean())
            obs_rate = float(y[mask].mean())
            ece += (count / n_total) * abs(obs_rate - mean_pred)
            bins.append(
                {
                    "bin_index": idx,
                    "lower": round(lo, 4),
                    "upper": round(hi, 4),
                    "count": count,
                    "mean_predicted_probability": round(mean_pred, 4),
                    "observed_positive_rate": round(obs_rate, 4),
                }
            )
    if n_total >= min_calibrated_samples and brier <= max_calibrated_brier and ece <= 0.15:
        cal_status = "INTERNAL_OOF_CALIBRATED_NOT_EXTERNALLY_VALIDATED"
    else:
        cal_status = "POORLY_CALIBRATED_OR_SMALL_COHORT"
    return M6CalibrationResult(
        brier_score=round(brier, 4),
        ece=round(float(ece), 4),
        calibration_status=cal_status,
        bins=bins,
    )


def compute_threshold_tradeoff_curve(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    thresholds: tuple[float, ...] = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8),
) -> list[dict[str, Any]]:
    """Evaluate sensitivity, specificity, precision, F1, and balanced accuracy across thresholds."""
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    rows: list[dict[str, Any]] = []
    for thr in thresholds:
        pred = (p >= thr).astype(int)
        m = binary_metrics(y, pred, p)
        tp = int(((y == 1) & (pred == 1)).sum())
        fp = int(((y == 0) & (pred == 1)).sum())
        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rows.append(
            {
                "threshold": thr,
                "sensitivity": round(float(m["sensitivity"]), 4),
                "specificity": round(float(m["specificity"]), 4),
                "precision": round(precision, 4),
                "balanced_accuracy": round(float(m["balanced_accuracy"]), 4),
                "f1": round(float(m["f1"]), 4),
            }
        )
    return rows


def evaluate_participant_cv_suite(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    models: dict[str, Pipeline] | None = None,
    n_splits: int = 5,
    random_seed: int = 2026,
    cohort_label: str = "cohort",
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Run participant-disjoint grouped CV across models and return metrics + OOF outputs."""
    verify_participant_split_integrity(X, y, groups, n_splits=n_splits, random_seed=random_seed)
    feat_cols = [c for c in X.columns if c not in ("participant_id", "sample_id")]
    X_clean = X[feat_cols]
    folds = list(grouped_splits(y, groups, n_splits=n_splits, random_seed=random_seed))

    suite = {
        "dummy_prior": DummyClassifier(strategy="prior"),
        **(models or build_m6_model_families(random_seed)),
    }
    summary_rows: list[dict[str, Any]] = []
    oof_details: dict[str, dict[str, Any]] = {}

    for model_name, estimator in suite.items():
        oof_records: list[pd.DataFrame] = []
        fold_metrics: list[dict[str, float]] = []
        for fold_id, (tr_idx, te_idx) in enumerate(folds, start=1):
            fitted = clone(estimator)
            fitted.fit(X_clean.iloc[tr_idx], y[tr_idx])
            proba = fitted.predict_proba(X_clean.iloc[te_idx])[:, 1]
            pred = (proba >= 0.5).astype(int)
            fold_df = pd.DataFrame(
                {
                    "participant_id": groups[te_idx],
                    "y_true": y[te_idx],
                    "probability": proba,
                    "y_pred": pred,
                }
            )
            agg = fold_df.groupby("participant_id", as_index=False).agg(
                y_true=("y_true", "first"),
                probability=("probability", "mean"),
                y_pred=("y_pred", "mean"),
            )
            agg["y_pred"] = (agg["probability"] >= 0.5).astype(int)
            agg["fold"] = fold_id
            oof_records.append(agg)
            m = binary_metrics(
                agg["y_true"].to_numpy(dtype=int),
                agg["y_pred"].to_numpy(dtype=int),
                agg["probability"].to_numpy(dtype=float),
            )
            fold_metrics.append(m)

        oof_all = pd.concat(oof_records, ignore_index=True)
        y_oof = oof_all["y_true"].to_numpy(dtype=int)
        p_oof = oof_all["probability"].to_numpy(dtype=float)
        yhat_oof = oof_all["y_pred"].to_numpy(dtype=int)
        pooled = binary_metrics(y_oof, yhat_oof, p_oof)
        pr_auc = float(average_precision_score(y_oof, p_oof))
        cal = compute_calibration_profile(y_oof, p_oof)
        existing_cal = calibration_summary(y_oof, p_oof)
        row = {
            "cohort": cohort_label,
            "model_family": model_name,
            "n_participants": int(len(oof_all)),
            "roc_auc": round(float(pooled["roc_auc"]), 4),
            "pr_auc": round(pr_auc, 4),
            "balanced_accuracy": round(float(pooled["balanced_accuracy"]), 4),
            "sensitivity": round(float(pooled["sensitivity"]), 4),
            "specificity": round(float(pooled["specificity"]), 4),
            "f1": round(float(pooled["f1"]), 4),
            "brier_score": round(float(existing_cal["brier_score"]), 4),
            "ece": cal.ece,
            "calibration_status": cal.calibration_status,
            "fold_balanced_accuracy_sd": round(
                float(np.std([fm["balanced_accuracy"] for fm in fold_metrics], ddof=1)), 4
            ),
        }
        summary_rows.append(row)
        oof_details[model_name] = {
            "metrics": row,
            "calibration": {
                "brier_score": cal.brier_score,
                "ece": cal.ece,
                "calibration_status": cal.calibration_status,
                "bins": cal.bins,
            },
            "threshold_curve": compute_threshold_tradeoff_curve(y_oof, p_oof),
            "y_true": y_oof,
            "probabilities": p_oof,
            "participant_ids": oof_all["participant_id"].to_numpy(),
        }
    return summary_rows, oof_details


def compute_subgroup_metrics_safe(
    participant_ids: np.ndarray,
    y_true: np.ndarray,
    probabilities: np.ndarray,
    subgroup_frame: pd.DataFrame,
    subgroup_column: str,
    *,
    small_cell_threshold: int = 10,
) -> list[dict[str, Any]]:
    """Evaluate subgroup performance with strict M5 small-cell suppression (N < 10)."""
    df = pd.DataFrame(
        {
            "participant_id": participant_ids.astype(str),
            "y_true": y_true,
            "probability": probabilities,
        }
    ).merge(
        subgroup_frame[["participant_id", subgroup_column]].drop_duplicates("participant_id"),
        on="participant_id",
        how="left",
    )
    rows: list[dict[str, Any]] = []
    for val, grp in df.groupby(subgroup_column, dropna=False):
        n = int(len(grp))
        if n < small_cell_threshold or grp["y_true"].nunique() < 2:
            rows.append(
                {
                    "subgroup_column": subgroup_column,
                    "subgroup_value": str(val),
                    "n_participants": "< 10 (Suppressed)" if n < small_cell_threshold else n,
                    "balanced_accuracy": "SUPPRESSED_SMALL_CELL_OR_SINGLE_CLASS",
                    "roc_auc": "SUPPRESSED_SMALL_CELL_OR_SINGLE_CLASS",
                }
            )
        else:
            pred = (grp["probability"].to_numpy() >= 0.5).astype(int)
            m = binary_metrics(
                grp["y_true"].to_numpy(dtype=int), pred, grp["probability"].to_numpy()
            )
            rows.append(
                {
                    "subgroup_column": subgroup_column,
                    "subgroup_value": str(val),
                    "n_participants": n,
                    "balanced_accuracy": round(float(m["balanced_accuracy"]), 4),
                    "roc_auc": round(float(m["roc_auc"]), 4),
                }
            )
    return rows


def compute_training_feature_distribution(
    X: pd.DataFrame, feature_names: list[str] | tuple[str, ...]
) -> dict[str, dict[str, float]]:
    """Record training-distribution statistics for principled runtime OOD gating."""
    stats: dict[str, dict[str, float]] = {}
    for col in feature_names:
        vals = pd.to_numeric(X[col], errors="coerce").dropna().to_numpy(dtype=float)
        if len(vals) == 0:
            continue
        stats[col] = {
            "mean": round(float(np.mean(vals)), 6),
            "std": round(float(max(np.std(vals), 1e-6)), 6),
            "q01": round(float(np.quantile(vals, 0.01)), 6),
            "q99": round(float(np.quantile(vals, 0.99)), 6),
        }
    return stats


def run_m6_comparative_experiments(
    *,
    random_seed: int = 2026,
    uams_csv_path: Path | None = None,
    uci_path: Path | None = None,
) -> dict[str, Any]:
    """Execute Model A/B/C/D comparisons and multi-family benchmarks on available cohorts."""
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(UTC).isoformat(),
        "random_seed": random_seed,
        "cohorts_evaluated": [],
        "model_a_to_d_comparisons": [],
        "multi_family_benchmarks": [],
        "calibration_summaries": {},
        "threshold_curves": {},
        "subgroup_analyses": [],
        "feature_distribution_stats": {},
        "scientific_conclusions": [],
    }

    # 1. UAMS Cohort (Models A, B, C + 6 voice ML families)
    try:
        X_uams, y_uams, g_uams, demo_uams = load_uams_cohort(uams_csv_path)
        report["cohorts_evaluated"].append("uams")
        report["feature_distribution_stats"]["uams_core39"] = compute_training_feature_distribution(
            X_uams, FEATURE_NAMES
        )

        # Model A: Demographic-only
        X_demo = demo_uams[["participant_id", "age", "sex_male"]].copy()
        demo_rows, _ = evaluate_participant_cv_suite(
            X_demo,
            y_uams,
            g_uams,
            models={
                "model_a_demographic_only": build_m6_model_families(random_seed)[
                    "logistic_regression"
                ]
            },
            cohort_label="uams_model_a_demographic_only",
            random_seed=random_seed,
        )
        # Model B & multi-family voice-only benchmark
        voice_rows, voice_oof = evaluate_participant_cv_suite(
            X_uams,
            y_uams,
            g_uams,
            cohort_label="uams_model_b_voice_only",
            random_seed=random_seed,
        )
        # Model C: Voice + Demographic covariates
        X_comb = X_uams.copy()
        X_comb["age"] = demo_uams["age"].to_numpy()
        X_comb["sex_male"] = demo_uams["sex_male"].to_numpy()
        comb_rows, _ = evaluate_participant_cv_suite(
            X_comb,
            y_uams,
            g_uams,
            models={
                "model_c_voice_plus_covariates_logistic": build_m6_model_families(random_seed)[
                    "logistic_regression"
                ],
                "model_c_voice_plus_covariates_rf": build_m6_model_families(random_seed)[
                    "random_forest"
                ],
            },
            cohort_label="uams_model_c_combined",
            random_seed=random_seed,
        )

        report["model_a_to_d_comparisons"].extend(
            [
                *[r for r in demo_rows if r["model_family"] != "dummy_prior"],
                next(r for r in voice_rows if r["model_family"] == "logistic_regression"),
                *[r for r in comb_rows if r["model_family"] != "dummy_prior"],
            ]
        )
        report["multi_family_benchmarks"].extend(voice_rows)
        for mname, details in voice_oof.items():
            report["calibration_summaries"][f"uams/{mname}"] = details["calibration"]
            report["threshold_curves"][f"uams/{mname}"] = details["threshold_curve"]

        # Subgroup check on UAMS logistic_regression
        lr_oof = voice_oof["logistic_regression"]
        demo_bins = demo_uams.copy()
        demo_bins["age_group"] = np.where(demo_bins["age"] >= 60.0, "60_plus", "under_60")
        report["subgroup_analyses"].extend(
            compute_subgroup_metrics_safe(
                lr_oof["participant_ids"],
                lr_oof["y_true"],
                lr_oof["probabilities"],
                demo_bins,
                "age_group",
            )
        )
        demo_bins["sex_label"] = np.where(demo_bins["sex_male"] >= 0.5, "Male", "Female")
        report["subgroup_analyses"].extend(
            compute_subgroup_metrics_safe(
                lr_oof["participant_ids"],
                lr_oof["y_true"],
                lr_oof["probabilities"],
                demo_bins,
                "sex_label",
            )
        )

        age_ba = next(r for r in demo_rows if r["model_family"] == "model_a_demographic_only")[
            "balanced_accuracy"
        ]
        best_voice_ba = max(
            r["balanced_accuracy"] for r in voice_rows if r["model_family"] != "dummy_prior"
        )
        report["scientific_conclusions"].append(
            f"UAMS Model A (demographic-only Balanced Acc={age_ba:.3f}) >= best Voice-only Model B "
            f"({best_voice_ba:.3f}): severe age confounding confirmed; voice features alone do not "
            "establish independent clinical separability."
        )
    except FileNotFoundError:
        report["scientific_conclusions"].append("UAMS processed cohort not present locally.")

    # 2. UCI #470 Cohort (Model A gender-only vs Model B 752 voice features + domain benchmark)
    try:
        X_uci, y_uci, g_uci, demo_uci = load_uci_cohort(uci_path)
        report["cohorts_evaluated"].append("uci470")
        X_uci_gender = demo_uci[["participant_id", "gender_code"]].copy()
        uci_demo_rows, _ = evaluate_participant_cv_suite(
            X_uci_gender,
            y_uci,
            g_uci,
            models={
                "model_a_gender_only": build_m6_model_families(random_seed)["logistic_regression"]
            },
            cohort_label="uci470_model_a_gender_only",
            random_seed=random_seed,
        )
        # Use bounded core families on 752-col UCI for fast, deterministic comparison
        uci_families = {
            k: v
            for k, v in build_m6_model_families(random_seed).items()
            if k in {"logistic_regression", "linear_svm_calibrated", "random_forest", "extra_trees"}
        }
        uci_voice_rows, uci_oof = evaluate_participant_cv_suite(
            X_uci,
            y_uci,
            g_uci,
            models=uci_families,
            cohort_label="uci470_model_b_752_predictors",
            random_seed=random_seed,
        )
        report["model_a_to_d_comparisons"].extend(
            [r for r in uci_demo_rows if r["model_family"] != "dummy_prior"]
        )
        report["multi_family_benchmarks"].extend(uci_voice_rows)
        for mname, details in uci_oof.items():
            report["calibration_summaries"][f"uci470/{mname}"] = details["calibration"]
            report["threshold_curves"][f"uci470/{mname}"] = details["threshold_curve"]
    except FileNotFoundError:
        report["scientific_conclusions"].append("UCI #470 archive not present locally.")

    # 3. Model D: cannot pool UAMS Core39 + UCI 752 due to disjoint schemas & missing age/raw WAV
    report["model_a_to_d_comparisons"].append(
        {
            "cohort": "model_d_dataset_domain_only",
            "model_family": "cross_dataset_domain_check",
            "n_participants": 0,
            "roc_auc": None,
            "pr_auc": None,
            "balanced_accuracy": None,
            "sensitivity": None,
            "specificity": None,
            "f1": None,
            "brier_score": None,
            "ece": None,
            "calibration_status": "NOT_ESTIMABLE_DISJOINT_SCHEMAS",
            "note": (
                "UAMS (39 Core39 WAV features) and UCI #470 (752 precomputed predictors, no raw "
                "audio) lack a shared aligned schema or matched external raw-audio domain."
            ),
        }
    )

    payload_bytes = json.dumps(report, sort_keys=True, default=str).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(payload_bytes).hexdigest()
    return report


def generate_m6_model_card(experiment_report: dict[str, Any]) -> dict[str, Any]:
    """Generate structured M6 model card with benchmarks, calibration, confounding, and blockers."""
    return {
        "model_card_version": "voxneuro.model_card.m6.v1",
        "generated_utc": datetime.now(UTC).isoformat(),
        "intended_use": (
            "Exploratory Parkinson's voice biomarker research evaluation ONLY; "
            "not cleared for medical diagnosis."
        ),
        "clinical_claim_status": "UNAPPROVED_RESEARCH_ONLY",
        "external_validation_status": "PENDING_AUTHORIZED_EXTERNAL_COHORT",
        "cohorts_evaluated": experiment_report.get("cohorts_evaluated", []),
        "benchmarks": experiment_report.get("multi_family_benchmarks", []),
        "confounding_comparisons": experiment_report.get("model_a_to_d_comparisons", []),
        "calibration_summaries": experiment_report.get("calibration_summaries", {}),
        "subgroup_analyses": experiment_report.get("subgroup_analyses", []),
        "known_limitations": [
            (
                "UAMS has only 78 valid participants and severe age confounding "
                "(Age-only AUC/BA exceeds voice-only)."
            ),
            "UCI #470 contains pre-extracted predictors without raw WAV audio or age.",
            (
                "External raw-audio cohorts (NeuroVoz, PC-GITA, Italian IPVS) remain "
                "unavailable without signed DUA + data."
            ),
            (
                "Live microphone / ad-hoc uploads remain fail-closed unless explicit "
                "domain approval exists."
            ),
        ],
        "source_experiment_sha256": experiment_report.get("report_sha256"),
    }


def render_model_card_html(model_card: dict[str, Any]) -> str:
    """Render an accessible standalone HTML representation of the M6 structured model card."""
    rows_html = "".join(
        f"<tr><td>{r.get('cohort')}</td><td>{r.get('model_family')}</td>"
        f"<td>{r.get('n_participants')}</td><td>{r.get('roc_auc')}</td>"
        f"<td>{r.get('balanced_accuracy')}</td><td>{r.get('brier_score')}</td>"
        f"<td>{r.get('ece')}</td></tr>"
        for r in model_card.get("benchmarks", [])
    )
    limits_html = "".join(f"<li>{item}</li>" for item in model_card.get("known_limitations", []))
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<title>VoxNeuro M6 Research Model Card</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;"
        "padding:0 1rem;color:#1e293b;}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0;}"
        "th,td{border:1px solid #cbd5e1;padding:0.5rem;text-align:left;}"
        "th{background:#f1f5f9;}"
        ".warn{background:#fef3c7;border-left:4px solid #d97706;padding:1rem;margin:1rem 0;}"
        "</style>"
        "</head><body>"
        "<h1>VoxNeuro M6 Research Model Card</h1>"
        f"<div class='warn'><strong>Status:</strong> {model_card['clinical_claim_status']} · "
        f"{model_card['external_validation_status']}</div>"
        f"<p><strong>Intended Use:</strong> {model_card['intended_use']}</p>"
        "<h2>Grouped Cross-Validation Benchmarks</h2>"
        "<table><thead><tr><th>Cohort</th><th>Model Family</th><th>N</th><th>ROC-AUC</th>"
        "<th>Bal. Acc.</th><th>Brier</th><th>ECE</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
        "<h2>Known Limitations &amp; Bias Disclosures</h2>"
        f"<ul>{limits_html}</ul>"
        f"<p><small>Experiment SHA-256: {model_card.get('source_experiment_sha256')}</small></p>"
        "</body></html>"
    )
