"""Demographic sensitivity, comparator models, and paired incremental voice analysis."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import LinearSVC

from voxneuro.features.schema import FEATURE_NAMES
from voxneuro.modeling.evaluation import binary_metrics
from voxneuro.modeling.splits import grouped_splits

MODEL_LABELS = {
    "majority_classifier": "Majority class baseline",
    "voice_only_svm": "Voice-only linear SVM",
    "voice_only_logistic": "Voice-only logistic regression (L2)",
    "age_only_logistic": "Age-only logistic comparator",
    "sex_only_logistic": "Sex-only logistic comparator",
    "age_plus_sex_logistic": "Age + sex logistic comparator",
    "age_plus_voice_logistic": "Age + voice logistic comparator",
    "age_plus_sex_plus_voice_logistic": "Age + sex + voice logistic comparator",
    "matched_voice_svm": "Matched cohort voice SVM (NOT ESTIMABLE)",
}


def build_demographic_comparator_pipelines(
    feature_names: list[str] | None = None,
    seed: int = 2026,
) -> dict[str, tuple[list[str], Pipeline | DummyClassifier, dict[str, list[Any]]]]:
    """Construct sklearn Pipelines, column subsets, and tuning grids for the 8 comparator models."""
    feats = list(feature_names or FEATURE_NAMES)

    num_scale = [
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ]
    cat_ohe = [
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(drop="first", sparse_output=False, handle_unknown="ignore")),
    ]

    c_grid_lr = {"classifier__C": [0.01, 0.1, 1.0, 10.0, 100.0]}
    c_grid_svm = {"classifier__C": [0.01, 0.1, 1.0, 10.0]}

    # 1. Majority classifier
    majority = DummyClassifier(strategy="most_frequent")

    # 2. Voice-only Linear SVM
    pipe_voice_svm = Pipeline(
        num_scale
        + [
            (
                "classifier",
                LinearSVC(
                    class_weight="balanced",
                    dual="auto",
                    max_iter=10000,
                    random_state=seed,
                ),
            )
        ]
    )

    # 3. Voice-only Logistic Regression
    pipe_voice_lr = Pipeline(
        num_scale
        + [
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=seed,
                ),
            )
        ]
    )

    # 4. Age-only Logistic Regression
    pipe_age_lr = Pipeline(
        num_scale
        + [
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=seed,
                ),
            )
        ]
    )

    # 5. Sex-only Logistic Regression
    pipe_sex_lr = Pipeline(
        [
            ("prep", ColumnTransformer([("cat", Pipeline(cat_ohe), ["sex"])])),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=seed,
                ),
            ),
        ]
    )

    # 6. Age + Sex Logistic Regression
    pipe_age_sex_lr = Pipeline(
        [
            (
                "prep",
                ColumnTransformer(
                    [
                        ("num", Pipeline(num_scale), ["age"]),
                        ("cat", Pipeline(cat_ohe), ["sex"]),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=seed,
                ),
            ),
        ]
    )

    # 7. Age + Voice Logistic Regression
    pipe_age_voice_lr = Pipeline(
        num_scale
        + [
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=seed,
                ),
            )
        ]
    )

    # 8. Age + Sex + Voice Logistic Regression
    pipe_age_sex_voice_lr = Pipeline(
        [
            (
                "prep",
                ColumnTransformer(
                    [
                        ("num", Pipeline(num_scale), ["age"] + feats),
                        ("cat", Pipeline(cat_ohe), ["sex"]),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=seed,
                ),
            ),
        ]
    )

    return {
        "majority_classifier": (["age"], majority, {}),
        "voice_only_svm": (feats, pipe_voice_svm, c_grid_svm),
        "voice_only_logistic": (feats, pipe_voice_lr, c_grid_lr),
        "age_only_logistic": (["age"], pipe_age_lr, c_grid_lr),
        "sex_only_logistic": (["sex"], pipe_sex_lr, c_grid_lr),
        "age_plus_sex_logistic": (["age", "sex"], pipe_age_sex_lr, c_grid_lr),
        "age_plus_voice_logistic": (["age"] + feats, pipe_age_voice_lr, c_grid_lr),
        "age_plus_sex_plus_voice_logistic": (
            ["age", "sex"] + feats,
            pipe_age_sex_voice_lr,
            c_grid_lr,
        ),
    }


def _paired_bootstrap_ci(
    y_true: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    *,
    iterations: int = 1000,
    seed: int = 2026,
) -> tuple[float, float]:
    """Compute 95% bootstrap CI for paired difference in balanced accuracy (A minus B)."""
    rng = np.random.default_rng(seed)
    class_indices = [np.flatnonzero(y_true == c) for c in (0, 1)]
    if any(len(idx) == 0 for idx in class_indices):
        return float("nan"), float("nan")

    diffs = np.empty(iterations, dtype=float)
    for i in range(iterations):
        selected = np.concatenate(
            [rng.choice(idx, size=len(idx), replace=True) for idx in class_indices]
        )
        y_b = y_true[selected]
        m_a = binary_metrics(y_b, pred_a[selected])
        m_b = binary_metrics(y_b, pred_b[selected])
        diffs[i] = m_a["balanced_accuracy"] - m_b["balanced_accuracy"]

    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def evaluate_demographic_models(
    frame: pd.DataFrame,
    *,
    feature_names: list[str] | None = None,
    outer_splits: int = 5,
    inner_splits: int = 3,
    random_seeds: tuple[int, ...] = (2026, 2027, 2028),
    bootstrap_iterations: int = 1000,
) -> dict[str, Any]:
    """Execute repeated nested CV across the 8 prespecified comparator models."""
    feats = list(feature_names or FEATURE_NAMES)
    required = {"participant_id", "class_label", "age", "sex"} | set(feats)
    if not required <= set(frame.columns):
        raise ValueError(f"Frame missing required columns: {required - set(frame.columns)}")

    labels = frame["class_label"].map({"HC": 0, "PD": 1}).to_numpy(dtype=int)
    groups = frame["participant_id"].to_numpy()

    all_fold_records: list[dict[str, Any]] = []
    all_oof_predictions: list[dict[str, Any]] = []
    repeat_model_metrics: dict[str, list[dict[str, float]]] = {}
    primary_predictions: dict[str, pd.DataFrame] = {}

    model_specs_template = build_demographic_comparator_pipelines(feats, seed=random_seeds[0])
    model_names = list(model_specs_template.keys())

    for name in model_names:
        repeat_model_metrics[name] = []

    for seed in random_seeds:
        specs = build_demographic_comparator_pipelines(feats, seed=seed)
        outer_cv = list(grouped_splits(labels, groups, n_splits=outer_splits, random_seed=seed))

        oof_by_model: dict[str, list[dict[str, Any]]] = {m: [] for m in model_names}

        for fold_id, (train_idx, test_idx) in enumerate(outer_cv, start=1):
            inner_seed = seed + 1000 * fold_id
            inner_cv = list(
                grouped_splits(
                    labels[train_idx],
                    groups[train_idx],
                    n_splits=inner_splits,
                    random_seed=inner_seed,
                )
            )

            for name, (cols, estimator, param_grid) in specs.items():
                train_x = frame.iloc[train_idx][cols]
                test_x = frame.iloc[test_idx][cols]
                train_y = labels[train_idx]
                test_y = labels[test_idx]

                if param_grid:
                    search = GridSearchCV(
                        estimator=clone(estimator),
                        param_grid=param_grid,
                        scoring="balanced_accuracy",
                        cv=inner_cv,
                        refit=True,
                        n_jobs=1,
                    )
                    search.fit(train_x, train_y)
                    best_model = search.best_estimator_
                    selected_params = json.dumps(search.best_params_, sort_keys=True)
                    inner_score = float(search.best_score_)
                else:
                    best_model = clone(estimator).fit(train_x, train_y)
                    selected_params = "{}"
                    inner_score = float("nan")

                preds = best_model.predict(test_x).astype(int)

                scores = None
                probs = None
                if hasattr(best_model, "predict_proba"):
                    probs = best_model.predict_proba(test_x)[:, 1]
                    scores = probs
                    score_kind = "probability"
                elif hasattr(best_model, "decision_function"):
                    scores = np.asarray(best_model.decision_function(test_x), dtype=float).reshape(
                        -1
                    )
                    score_kind = "decision_function"
                else:
                    scores = preds.astype(float)
                    score_kind = "hard_label"

                # Store per-sample fold predictions
                for i, sample_idx in enumerate(test_idx):
                    oof_by_model[name].append(
                        {
                            "sample_id": frame["sample_id"].iloc[sample_idx]
                            if "sample_id" in frame.columns
                            else f"s{sample_idx}",
                            "participant_id": groups[sample_idx],
                            "class_label": frame["class_label"].iloc[sample_idx],
                            "sex": frame["sex"].iloc[sample_idx],
                            "age": float(frame["age"].iloc[sample_idx]),
                            "model": name,
                            "repeat_seed": seed,
                            "outer_fold": fold_id,
                            "y_true": test_y[i],
                            "y_pred": preds[i],
                            "score": scores[i] if scores is not None else float("nan"),
                            "probability": probs[i] if probs is not None else float("nan"),
                            "score_kind": score_kind,
                            "selected_parameters": selected_params,
                            "inner_best_balanced_accuracy": inner_score,
                        }
                    )

                fold_m = binary_metrics(
                    test_y, preds, scores if scores is not None else None, probs
                )
                all_fold_records.append(
                    {
                        "model": name,
                        "repeat_seed": seed,
                        "outer_fold": fold_id,
                        "n_samples": len(test_idx),
                        "inner_best_balanced_accuracy": inner_score,
                        **fold_m,
                    }
                )

        # Calculate pooled metrics for this repeat
        for name in model_names:
            rep_df = pd.DataFrame(oof_by_model[name])
            # Aggregate to participant level
            part_df = rep_df.groupby("participant_id", as_index=False).agg(
                {
                    "y_true": "first",
                    "y_pred": "mean",
                    "score": "mean",
                    "probability": "mean",
                    "sex": "first",
                    "age": "first",
                    "score_kind": "first",
                    "selected_parameters": "first",
                }
            )
            part_df["y_pred_binary"] = (part_df["y_pred"] >= 0.5).astype(int)

            y_t = part_df["y_true"].to_numpy(dtype=int)
            y_p = part_df["y_pred_binary"].to_numpy(dtype=int)
            y_s = part_df["score"].to_numpy(dtype=float) if part_df["score"].notna().all() else None
            y_prob = (
                part_df["probability"].to_numpy(dtype=float)
                if part_df["probability"].notna().all()
                else None
            )

            metrics_rep = binary_metrics(y_t, y_p, y_s, y_prob)
            repeat_model_metrics[name].append(metrics_rep)

            if seed == random_seeds[0]:
                primary_predictions[name] = part_df

            all_oof_predictions.extend(rep_df.to_dict("records"))

    # Compute cross-repeat summary and primary-repeat bootstrap CIs
    comparator_rows = []
    primary_seed = random_seeds[0]

    for name in model_names:
        reps = repeat_model_metrics[name]
        mean_ba = float(np.mean([r["balanced_accuracy"] for r in reps]))
        sd_ba = (
            float(np.std([r["balanced_accuracy"] for r in reps], ddof=1)) if len(reps) > 1 else 0.0
        )
        mean_roc = float(np.mean([r["roc_auc"] for r in reps if np.isfinite(r["roc_auc"])]))
        mean_sens = float(np.mean([r["sensitivity"] for r in reps]))
        mean_spec = float(np.mean([r["specificity"] for r in reps]))
        mean_f1 = float(np.mean([r["f1"] for r in reps]))
        mean_acc = float(np.mean([r["accuracy"] for r in reps]))
        mean_brier = (
            float(np.mean([r["brier_score"] for r in reps if np.isfinite(r["brier_score"])]))
            if any(np.isfinite(r["brier_score"]) for r in reps)
            else float("nan")
        )
        mean_mcc = float(np.mean([r["mcc"] for r in reps]))

        # Primary-seed bootstrap CI
        p_df = primary_predictions[name]
        y_true_p = p_df["y_true"].to_numpy(dtype=int)
        y_pred_p = p_df["y_pred_binary"].to_numpy(dtype=int)

        # 1000 participant bootstrap for BA
        rng = np.random.default_rng(primary_seed)
        class_idx = [np.flatnonzero(y_true_p == c) for c in (0, 1)]
        boot_bas = np.empty(bootstrap_iterations, dtype=float)
        for b in range(bootstrap_iterations):
            sel = np.concatenate(
                [rng.choice(idx, size=len(idx), replace=True) for idx in class_idx]
            )
            boot_bas[b] = binary_metrics(y_true_p[sel], y_pred_p[sel])["balanced_accuracy"]

        ba_ci_low = float(np.percentile(boot_bas, 2.5))
        ba_ci_high = float(np.percentile(boot_bas, 97.5))

        comparator_rows.append(
            {
                "model": name,
                "model_label": MODEL_LABELS.get(name, name),
                "status": "ESTIMATED",
                "balanced_accuracy_mean": round(mean_ba, 4),
                "balanced_accuracy_sd": round(sd_ba, 4),
                "balanced_accuracy_ci_95": [round(ba_ci_low, 4), round(ba_ci_high, 4)],
                "roc_auc_mean": round(mean_roc, 4),
                "sensitivity_mean": round(mean_sens, 4),
                "specificity_mean": round(mean_spec, 4),
                "f1_mean": round(mean_f1, 4),
                "accuracy_mean": round(mean_acc, 4),
                "brier_score_mean": round(mean_brier, 4) if np.isfinite(mean_brier) else None,
                "mcc_mean": round(mean_mcc, 4),
            }
        )

    # Append matched_voice_svm as NOT ESTIMABLE per SAP decision rules
    comparator_rows.append(
        {
            "model": "matched_voice_svm",
            "model_label": MODEL_LABELS["matched_voice_svm"],
            "status": "NOT ESTIMABLE",
            "balanced_accuracy_mean": None,
            "balanced_accuracy_sd": None,
            "balanced_accuracy_ci_95": None,
            "roc_auc_mean": None,
            "sensitivity_mean": None,
            "specificity_mean": None,
            "f1_mean": None,
            "accuracy_mean": None,
            "brier_score_mean": None,
            "mcc_mean": None,
            "suppression_reason": (
                "Sample size exhaustion: only 5 pairs (10 participants) satisfy the pre-registered "
                "0.2 SD caliper (2.44 years). Stratified 5-fold cross-validation requires at least "
                "5 participants per class, leaving only 4 training participants per class, which "
                "cannot sustain 3-fold inner cross-validation."
            ),
        }
    )

    comparator_metrics_df = pd.DataFrame(comparator_rows)

    # Calculate paired incremental voice comparisons (Primary seed 2026)
    p_age = primary_predictions["age_only_logistic"]
    p_age_voice = primary_predictions["age_plus_voice_logistic"]
    p_age_sex = primary_predictions["age_plus_sex_logistic"]
    p_age_sex_voice = primary_predictions["age_plus_sex_plus_voice_logistic"]

    # Ensure identical participant alignment
    assert (p_age["participant_id"].to_numpy() == p_age_voice["participant_id"].to_numpy()).all()
    assert (
        p_age_sex["participant_id"].to_numpy() == p_age_sex_voice["participant_id"].to_numpy()
    ).all()

    y_t = p_age["y_true"].to_numpy(dtype=int)
    pred_age = p_age["y_pred_binary"].to_numpy(dtype=int)
    pred_av = p_age_voice["y_pred_binary"].to_numpy(dtype=int)
    pred_as = p_age_sex["y_pred_binary"].to_numpy(dtype=int)
    pred_asv = p_age_sex_voice["y_pred_binary"].to_numpy(dtype=int)

    # Primary Seed Point Estimates (the exact estimand for the paired bootstrap CI)
    m_age_p = binary_metrics(y_t, pred_age)
    m_av_p = binary_metrics(y_t, pred_av)
    m_as_p = binary_metrics(y_t, pred_as)
    m_asv_p = binary_metrics(y_t, pred_asv)

    delta_av_ba_primary = float(m_av_p["balanced_accuracy"] - m_age_p["balanced_accuracy"])
    delta_asv_ba_primary = float(m_asv_p["balanced_accuracy"] - m_as_p["balanced_accuracy"])

    # Secondary Repeated-CV Estimand across all random seeds
    delta_av_ba_repeated = float(
        np.mean([r["balanced_accuracy"] for r in repeat_model_metrics["age_plus_voice_logistic"]])
        - np.mean([r["balanced_accuracy"] for r in repeat_model_metrics["age_only_logistic"]])
    )
    delta_asv_ba_repeated = float(
        np.mean(
            [
                r["balanced_accuracy"]
                for r in repeat_model_metrics["age_plus_sex_plus_voice_logistic"]
            ]
        )
        - np.mean([r["balanced_accuracy"] for r in repeat_model_metrics["age_plus_sex_logistic"]])
    )

    # Paired participant bootstrap CIs (class-stratified, primary seed 2026)
    ci_av_low, ci_av_high = _paired_bootstrap_ci(
        y_t, pred_av, pred_age, iterations=bootstrap_iterations, seed=primary_seed
    )
    ci_asv_low, ci_asv_high = _paired_bootstrap_ci(
        y_t, pred_asv, pred_as, iterations=bootstrap_iterations, seed=primary_seed
    )

    # Supplementary McNemar discordance test (overall paired classification error)
    b_av = int(np.sum((pred_av == y_t) & (pred_age != y_t)))
    c_av = int(np.sum((pred_av != y_t) & (pred_age == y_t)))
    mcnemar_av_p = float(binomtest(b_av, b_av + c_av, 0.5).pvalue) if (b_av + c_av) > 0 else 1.0

    b_asv = int(np.sum((pred_asv == y_t) & (pred_as != y_t)))
    c_asv = int(np.sum((pred_asv != y_t) & (pred_as == y_t)))
    mcnemar_asv_p = (
        float(binomtest(b_asv, b_asv + c_asv, 0.5).pvalue) if (b_asv + c_asv) > 0 else 1.0
    )

    # SAP Decision Rule: Supported ONLY if 95% bootstrap CI strictly excludes zero on positive side
    supported_av = bool(ci_av_low > 0.0)
    supported_asv = bool(ci_asv_low > 0.0)

    standard_inference = (
        "No statistically supported positive incremental voice contribution was established "
        "in the current UAMS cohort. However, the available confidence intervals do not "
        "establish that the true incremental contribution is zero or that a clinically "
        "meaningful contribution is impossible."
    )

    paired_incremental_df = pd.DataFrame(
        [
            {
                "comparison": "Age + Voice vs Age Only",
                "model_tested": "age_plus_voice_logistic",
                "baseline_model": "age_only_logistic",
                "delta_balanced_accuracy": round(delta_av_ba_primary, 4),
                "delta_ci_95": [round(ci_av_low, 4), round(ci_av_high, 4)],
                "secondary_repeated_cv_delta_ba": round(delta_av_ba_repeated, 4),
                "discordant_b_model_correct": b_av,
                "discordant_c_baseline_correct": c_av,
                "supplementary_mcnemar_exact_p": round(mcnemar_av_p, 4),
                "statistically_supported_incremental_contribution": supported_av,
                "inference": (
                    "Statistically supported positive incremental voice contribution established."
                    if supported_av
                    else standard_inference
                ),
            },
            {
                "comparison": "Age + Sex + Voice vs Age + Sex",
                "model_tested": "age_plus_sex_plus_voice_logistic",
                "baseline_model": "age_plus_sex_logistic",
                "delta_balanced_accuracy": round(delta_asv_ba_primary, 4),
                "delta_ci_95": [round(ci_asv_low, 4), round(ci_asv_high, 4)],
                "secondary_repeated_cv_delta_ba": round(delta_asv_ba_repeated, 4),
                "discordant_b_model_correct": b_asv,
                "discordant_c_baseline_correct": c_asv,
                "supplementary_mcnemar_exact_p": round(mcnemar_asv_p, 4),
                "statistically_supported_incremental_contribution": supported_asv,
                "inference": (
                    "Statistically supported positive incremental voice contribution established."
                    if supported_asv
                    else standard_inference
                ),
            },
        ]
    )

    # Sex Subgroup Analysis
    subgroup_records = []
    for sex_cat in ["F", "M"]:
        for name in [
            "voice_only_svm",
            "voice_only_logistic",
            "age_only_logistic",
            "age_plus_sex_logistic",
            "age_plus_sex_plus_voice_logistic",
        ]:
            p_df = primary_predictions[name]
            sub = p_df[p_df["sex"] == sex_cat]
            n_hc = int((sub["y_true"] == 0).sum())
            n_pd = int((sub["y_true"] == 1).sum())
            n_total = len(sub)

            is_suppressed = bool(n_hc < 10 or n_pd < 10)

            if n_hc > 0 and n_pd > 0:
                y_sub_t = sub["y_true"].to_numpy(dtype=int)
                y_sub_p = sub["y_pred_binary"].to_numpy(dtype=int)
                y_sub_s = sub["score"].to_numpy(dtype=float) if sub["score"].notna().all() else None
                m_sub = binary_metrics(y_sub_t, y_sub_p, y_sub_s)
                ba_val = round(m_sub["balanced_accuracy"], 4)
                roc_val = round(m_sub["roc_auc"], 4) if np.isfinite(m_sub["roc_auc"]) else None
                sens_val = round(m_sub["sensitivity"], 4)
                spec_val = round(m_sub["specificity"], 4)
            else:
                ba_val = None
                roc_val = None
                sens_val = None
                spec_val = None

            subgroup_records.append(
                {
                    "subgroup_sex": sex_cat,
                    "model": name,
                    "model_label": MODEL_LABELS.get(name, name),
                    "n_hc": n_hc,
                    "n_pd": n_pd,
                    "n_total": n_total,
                    "small_cell_suppression": is_suppressed,
                    "balanced_accuracy": ba_val,
                    "roc_auc": roc_val,
                    "sensitivity": sens_val,
                    "specificity": spec_val,
                }
            )

    sex_subgroups_df = pd.DataFrame(subgroup_records)

    return {
        "comparator_metrics": comparator_metrics_df,
        "paired_incremental": paired_incremental_df,
        "sex_subgroups": sex_subgroups_df,
        "fold_metrics": pd.DataFrame(all_fold_records),
        "oof_predictions": pd.DataFrame(all_oof_predictions),
    }
