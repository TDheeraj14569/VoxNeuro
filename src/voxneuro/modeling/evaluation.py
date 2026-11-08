"""Grouped out-of-fold metrics, including transparent dummy and demographic baselines."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    auc,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from voxneuro.modeling.pipeline import build_nested_model_searches, build_pipelines
from voxneuro.modeling.splits import grouped_splits


def binary_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_score: np.ndarray | None = None,
    y_probability: np.ndarray | None = None,
) -> dict[str, float]:
    """Compute confusion-derived and ranking metrics with PD treated as positive."""
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    valid_ranking = y_score is not None and len(np.unique(y_true)) == 2
    pr_auc = float("nan")
    average_precision = float("nan")
    roc_auc = float("nan")
    if valid_ranking:
        roc_auc = float(roc_auc_score(y_true, y_score))
        average_precision = float(average_precision_score(y_true, y_score))
        curve_precision, curve_recall, _ = precision_recall_curve(y_true, y_score)
        pr_auc = float(auc(curve_recall, curve_precision))
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "sensitivity": float(tp / (tp + fn)) if tp + fn else float("nan"),
        "specificity": float(tn / (tn + fp)) if tn + fp else float("nan"),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "average_precision": average_precision,
        "brier_score": float(brier_score_loss(y_true, y_probability))
        if y_probability is not None
        else float("nan"),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def _participant_bootstrap_intervals(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_score: np.ndarray | None,
    y_probability: np.ndarray | None,
    *,
    iterations: int,
    random_seed: int,
) -> dict[str, float]:
    """Stratified bootstrap intervals over participant-level out-of-fold rows."""
    rng = np.random.default_rng(random_seed)
    class_indices = [np.flatnonzero(y_true == label) for label in (0, 1)]
    if any(not len(indices) for indices in class_indices):
        return {}
    values: dict[str, list[float]] = {}
    for _ in range(iterations):
        selected = np.concatenate(
            [rng.choice(indices, size=len(indices), replace=True) for indices in class_indices]
        )
        metrics = binary_metrics(
            y_true[selected],
            y_pred[selected],
            y_score[selected] if y_score is not None else None,
            y_probability[selected] if y_probability is not None else None,
        )
        for metric, value in metrics.items():
            if metric in {"tn", "fp", "fn", "tp"} or not np.isfinite(value):
                continue
            values.setdefault(metric, []).append(float(value))
    intervals = {}
    for metric, samples in values.items():
        intervals[f"{metric}_ci_low"] = float(np.quantile(samples, 0.025))
        intervals[f"{metric}_ci_high"] = float(np.quantile(samples, 0.975))
    return intervals


def _validate_binary_labels(y: object) -> np.ndarray:
    """Validate that y contains strictly finite binary integers 0 and 1 without boolean types."""
    if isinstance(y, (list, tuple)):
        if any(isinstance(v, (bool, np.bool_)) for v in y):
            raise ValueError("Labels must contain only finite binary values: 0 and 1.")
    elif isinstance(y, pd.Series):
        if y.dtype == bool or any(isinstance(v, (bool, np.bool_)) for v in y):
            raise ValueError("Labels must contain only finite binary values: 0 and 1.")
    elif isinstance(y, np.ndarray):
        if y.dtype == bool or (
            y.dtype == object and any(isinstance(v, (bool, np.bool_)) for v in y.flat)
        ):
            raise ValueError("Labels must contain only finite binary values: 0 and 1.")
    raw_labels = np.asarray(y)
    if (
        raw_labels.ndim != 1
        or raw_labels.dtype == bool
        or raw_labels.dtype.kind not in "iuf"
        or not np.isfinite(raw_labels).all()
        or not np.isin(raw_labels, [0, 1]).all()
    ):
        raise ValueError("Labels must contain only finite binary values: 0 and 1.")
    return raw_labels.astype(int)


def _validate_additional_predictors(
    name: str,
    predictors: pd.DataFrame,
    X: pd.DataFrame,
    groups: np.ndarray,
    expected_rows: int,
) -> None:
    if not isinstance(predictors, pd.DataFrame) or len(predictors) != expected_rows:
        raise ValueError(f"Predictor table for {name!r} must match labels and be a DataFrame.")
    if not predictors.index.equals(X.index):
        raise ValueError(f"Additional predictor rows for {name!r} must align with X.")

    # Strict sample_id contract
    if "sample_id" in X.columns and "sample_id" not in predictors.columns:
        raise ValueError(
            f"X contains 'sample_id', so predictor table for {name!r} must also "
            "include 'sample_id'."
        )
    if "sample_id" in predictors.columns and "sample_id" not in X.columns:
        raise ValueError(
            f"Predictor table for {name!r} contains 'sample_id', but X does not "
            "contain 'sample_id'."
        )
    if "sample_id" in predictors.columns and "sample_id" in X.columns:
        if predictors["sample_id"].isna().any() or X["sample_id"].isna().any():
            raise ValueError(f"sample_id in {name!r} or X contains missing/NaN values.")
        if not X["sample_id"].is_unique:
            raise ValueError("X contains duplicate sample_id values.")
        if not predictors["sample_id"].is_unique:
            raise ValueError(f"Predictor table for {name!r} contains duplicate sample_id values.")
        if not predictors["sample_id"].equals(X["sample_id"]):
            raise ValueError(
                f"Additional predictor sample_id sequence for {name!r} does not match X."
            )

    # Strict participant_id contract
    if "participant_id" in X.columns and "participant_id" not in predictors.columns:
        raise ValueError(
            f"X contains 'participant_id', so predictor table for {name!r} must also "
            "include 'participant_id'."
        )
    if "participant_id" in predictors.columns and "participant_id" in X.columns:
        if not predictors["participant_id"].equals(X["participant_id"]):
            raise ValueError(
                f"Additional predictor participant_id sequence for {name!r} does not match X."
            )
    elif "participant_id" in predictors.columns:
        if not np.array_equal(predictors["participant_id"].to_numpy(), groups):
            raise ValueError(
                f"Additional predictor participant_id sequence for {name!r} does not match groups."
            )

    feature_cols = [c for c in predictors.columns if c not in ("participant_id", "sample_id")]
    if not feature_cols:
        raise ValueError(
            f"Predictor table for {name!r} must contain at least one feature column "
            "besides identifier metadata."
        )


def evaluate_nested_grouped(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    outer_splits: int = 5,
    inner_splits: int = 3,
    random_seeds: tuple[int, ...] = (2026, 2027, 2028),
    bootstrap_iterations: int = 1000,
    additional_searches: dict[str, tuple[pd.DataFrame, object, dict]] | None = None,
    model_names: tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run repeated nested CV with participant-disjoint outer and inner folds.

    Each model family is tuned only inside the current outer-training participants.
    Metrics are calculated after aggregating repeated recordings to one row per
    participant. Confidence intervals resample participants from the first
    prespecified repeat and are conditional on those fitted outer-fold models.
    """
    labels = _validate_binary_labels(y)
    group_values = np.asarray(groups)
    if not isinstance(X, pd.DataFrame):
        raise ValueError("X must be a pandas DataFrame.")
    if len(X) != len(labels):
        raise ValueError("X and y must contain the same number of rows.")
    x_feature_cols = [c for c in X.columns if c not in ("participant_id", "sample_id")]
    if not x_feature_cols:
        raise ValueError("X must contain at least one feature column besides identifier metadata.")
    if "participant_id" in X.columns and not np.array_equal(
        X["participant_id"].to_numpy(), group_values
    ):
        raise ValueError("X['participant_id'] does not match the supplied groups array.")
    if (
        isinstance(bootstrap_iterations, bool)
        or not isinstance(bootstrap_iterations, (int, np.integer))
        or bootstrap_iterations < 0
    ):
        raise ValueError("bootstrap_iterations must be a non-negative integer.")
    if not random_seeds or len(set(random_seeds)) != len(random_seeds):
        raise ValueError("random_seeds must be non-empty and unique.")

    searches = build_nested_model_searches(random_seeds[0])
    specs: dict[str, tuple[pd.DataFrame, object, dict]] = {
        name: (X, estimator, grid) for name, (estimator, grid) in searches.items()
    }
    for name, (predictors, estimator, grid) in (additional_searches or {}).items():
        if name in specs:
            raise ValueError(f"Additional model name {name!r} conflicts with a built-in model.")
        _validate_additional_predictors(name, predictors, X, group_values, len(labels))
        if estimator is None or not hasattr(estimator, "fit") or not isinstance(grid, dict):
            raise ValueError(
                f"Additional search for {name!r} needs an estimator and parameter grid."
            )
        specs[name] = (predictors, estimator, grid)
    if model_names is not None:
        unknown = set(model_names) - {"dummy", *specs}
        if unknown:
            raise ValueError(f"Unknown nested model(s): {sorted(unknown)}")
        specs = {name: specs[name] for name in model_names if name != "dummy"}

    all_prediction_rows: list[dict] = []
    fold_metric_rows: list[dict] = []
    pooled_metric_rows: list[dict] = []
    model_order = ["dummy", *specs]
    for repeat_index, seed in enumerate(random_seeds):
        outer = list(grouped_splits(labels, group_values, outer_splits, seed))
        repeat_specs = {}
        for name, (predictors, estimator, parameter_grid) in specs.items():
            repeat_estimator = clone(estimator)
            random_state_params = {
                key: seed
                for key in repeat_estimator.get_params(deep=True)
                if key.endswith("random_state")
            }
            if random_state_params:
                repeat_estimator.set_params(**random_state_params)
            repeat_specs[name] = (predictors, repeat_estimator, parameter_grid)
        repeat_predictions: dict[str, list[dict]] = {name: [] for name in model_order}
        for fold_id, (train, test) in enumerate(outer, start=1):
            inner_seed = seed + 1000 * fold_id
            inner = list(
                grouped_splits(labels[train], group_values[train], inner_splits, inner_seed)
            )
            test_records: dict[str, pd.DataFrame] = {}
            x_feat_cols = [c for c in X.columns if c not in ("participant_id", "sample_id")]
            X_feats = X[x_feat_cols] if x_feat_cols else X
            dummy = DummyClassifier(strategy="prior")
            dummy.fit(X_feats.iloc[train], labels[train])
            dummy_pred = dummy.predict(X_feats.iloc[test]).astype(int)
            dummy_probability = dummy.predict_proba(X_feats.iloc[test])[:, 1]
            test_records["dummy"] = pd.DataFrame(
                {
                    "participant_id": group_values[test],
                    "y_true": labels[test],
                    "y_pred": dummy_pred,
                    "score": dummy_probability,
                    "probability": dummy_probability,
                    "score_kind": "uncalibrated_probability",
                    "selected_parameters": "{}",
                    "inner_best_balanced_accuracy": np.nan,
                }
            )
            for name, (predictors, estimator, parameter_grid) in repeat_specs.items():
                train_x = predictors.iloc[train]
                test_x = predictors.iloc[test]
                feat_cols = [
                    c for c in predictors.columns if c not in ("participant_id", "sample_id")
                ]
                train_feats = train_x[feat_cols] if feat_cols else train_x
                test_feats = test_x[feat_cols] if feat_cols else test_x
                search = GridSearchCV(
                    estimator=clone(estimator),
                    param_grid=parameter_grid,
                    scoring="balanced_accuracy",
                    cv=inner,
                    refit=True,
                    n_jobs=1,
                    error_score="raise",
                    return_train_score=False,
                )
                search.fit(train_feats, labels[train])
                fitted = search.best_estimator_
                predicted = fitted.predict(test_feats).astype(int)
                probability = None
                if hasattr(fitted, "predict_proba"):
                    probability = fitted.predict_proba(test_feats)[:, 1]
                    score = probability
                    score_kind = "uncalibrated_probability"
                elif hasattr(fitted, "decision_function"):
                    score = np.asarray(fitted.decision_function(test_feats), dtype=float).reshape(
                        -1
                    )
                    score_kind = "decision_function"
                else:
                    score = predicted.astype(float)
                    score_kind = "hard_label"
                test_records[name] = pd.DataFrame(
                    {
                        "participant_id": group_values[test],
                        "y_true": labels[test],
                        "y_pred": predicted,
                        "score": score,
                        "probability": probability
                        if probability is not None
                        else np.full(len(test), np.nan),
                        "score_kind": score_kind,
                        "selected_parameters": json.dumps(search.best_params_, sort_keys=True),
                        "inner_best_balanced_accuracy": float(search.best_score_),
                    }
                )

            for name, record in test_records.items():
                participant_rows = record.groupby("participant_id", as_index=False).agg(
                    y_true=("y_true", "first"),
                    y_pred=("y_pred", "mean"),
                    score=("score", "mean"),
                    probability=("probability", "mean"),
                    score_kind=("score_kind", "first"),
                    n_recordings=("y_true", "size"),
                    selected_parameters=("selected_parameters", "first"),
                    inner_best_balanced_accuracy=("inner_best_balanced_accuracy", "first"),
                )
                if (
                    "probability" in participant_rows
                    and participant_rows["probability"].notna().all()
                ):
                    is_tied = participant_rows["y_pred"] == 0.5
                    participant_rows.loc[is_tied, "y_pred"] = (
                        participant_rows.loc[is_tied, "probability"] >= 0.5
                    ).astype(int)
                    participant_rows.loc[~is_tied, "y_pred"] = (
                        participant_rows.loc[~is_tied, "y_pred"] > 0.5
                    ).astype(int)
                else:
                    participant_rows["y_pred"] = (participant_rows["y_pred"] >= 0.5).astype(int)
                score_values = participant_rows["score"].to_numpy(dtype=float)
                score_ok = bool(np.isfinite(score_values).all())
                probability_values = participant_rows["probability"].to_numpy(dtype=float)
                probability_ok = bool(np.isfinite(probability_values).all())
                metrics = binary_metrics(
                    participant_rows["y_true"].to_numpy(dtype=int),
                    participant_rows["y_pred"].to_numpy(dtype=int),
                    score_values if score_ok else None,
                    probability_values if probability_ok else None,
                )
                best_score = (
                    float(participant_rows["inner_best_balanced_accuracy"].iloc[0])
                    if name != "dummy"
                    else float("nan")
                )
                fold_metric_rows.append(
                    {
                        "model": name,
                        "repeat_seed": seed,
                        "outer_fold": fold_id,
                        "n_participants": len(participant_rows),
                        "inner_best_balanced_accuracy": best_score,
                        "score_kind": str(participant_rows["score_kind"].iloc[0]),
                        **metrics,
                    }
                )
                participant_rows.insert(0, "outer_fold", fold_id)
                participant_rows.insert(0, "repeat_seed", seed)
                participant_rows.insert(0, "model", name)
                rows = participant_rows.to_dict("records")
                repeat_predictions[name].extend(rows)
                all_prediction_rows.extend(rows)

        for model_index, name in enumerate(model_order):
            participants = pd.DataFrame(repeat_predictions[name])
            if participants.empty or participants["participant_id"].duplicated().any():
                raise ValueError(
                    f"Outer CV must produce exactly one out-of-fold row per participant for {name}."
                )
            y_participant = participants["y_true"].to_numpy(dtype=int)
            pred_participant = participants["y_pred"].to_numpy(dtype=int)
            score_participant = participants["score"].to_numpy(dtype=float)
            probability_participant = participants["probability"].to_numpy(dtype=float)
            score_ok = bool(np.isfinite(score_participant).all())
            probability_ok = bool(np.isfinite(probability_participant).all())
            metrics = binary_metrics(
                y_participant,
                pred_participant,
                score_participant if score_ok else None,
                probability_participant if probability_ok else None,
            )
            model_folds = [
                r for r in fold_metric_rows if r["model"] == name and r["repeat_seed"] == seed
            ]
            fold_aucs = [
                float(r["roc_auc"])
                for r in model_folds
                if "roc_auc" in r and np.isfinite(r["roc_auc"])
            ]
            fold_aps = [
                float(r["average_precision"])
                for r in model_folds
                if "average_precision" in r and np.isfinite(r["average_precision"])
            ]
            outer_auc_mean = float(np.mean(fold_aucs)) if fold_aucs else float("nan")
            outer_auc_sd = float(np.std(fold_aucs, ddof=1)) if len(fold_aucs) > 1 else float("nan")
            outer_ap_mean = float(np.mean(fold_aps)) if fold_aps else float("nan")
            outer_ap_sd = float(np.std(fold_aps, ddof=1)) if len(fold_aps) > 1 else float("nan")
            intervals = (
                _participant_bootstrap_intervals(
                    y_participant,
                    pred_participant,
                    score_participant if score_ok else None,
                    probability_participant if probability_ok else None,
                    iterations=bootstrap_iterations,
                    random_seed=seed + 5000 + model_index,
                )
                if repeat_index == 0 and bootstrap_iterations
                else {}
            )
            pooled_metric_rows.append(
                {
                    "model": name,
                    "repeat_seed": seed,
                    "n_participants": len(participants),
                    "score_kind": str(participants["score_kind"].iloc[0]),
                    "outer_fold_roc_auc_mean": outer_auc_mean,
                    "outer_fold_roc_auc_sd": outer_auc_sd,
                    "outer_fold_ap_mean": outer_ap_mean,
                    "outer_fold_ap_sd": outer_ap_sd,
                    **metrics,
                    **intervals,
                }
            )

    return (
        pd.DataFrame(pooled_metric_rows),
        pd.DataFrame(all_prediction_rows),
        pd.DataFrame(fold_metric_rows),
    )


def evaluate_grouped(
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    n_splits: int = 5,
    random_seed: int = 2026,
    additional_models: dict[str, tuple[pd.DataFrame, object]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate fixed baselines with participant-disjoint folds and fold-local transforms.

    ``additional_models`` maps a model name to its own predictor table and estimator. This
    lets demographic and combined-feature baselines use the identical folds without adding
    demographic columns to voice-only models.
    """
    labels = _validate_binary_labels(y)
    group_values = np.asarray(groups)
    if not isinstance(X, pd.DataFrame):
        raise ValueError("X must be a pandas DataFrame.")
    if len(X) != len(labels):
        raise ValueError("X and y must contain the same number of rows.")
    x_feature_cols = [c for c in X.columns if c not in ("participant_id", "sample_id")]
    if not x_feature_cols:
        raise ValueError("X must contain at least one feature column besides identifier metadata.")
    if "participant_id" in X.columns and not np.array_equal(
        X["participant_id"].to_numpy(), group_values
    ):
        raise ValueError("X['participant_id'] does not match the supplied groups array.")
    folds = list(grouped_splits(labels, group_values, n_splits, random_seed))
    models = {"dummy": None, **build_pipelines(random_seed)}
    predictor_tables = {name: X for name in models}
    for name, (predictors, estimator) in (additional_models or {}).items():
        if name in models:
            raise ValueError(f"Additional model name {name!r} conflicts with a built-in baseline.")
        _validate_additional_predictors(name, predictors, X, group_values, len(labels))
        if estimator is None or not hasattr(estimator, "fit"):
            raise ValueError(f"Estimator for {name!r} must implement fit().")
        models[name] = estimator
        predictor_tables[name] = predictors
    prediction_rows = []
    metric_rows = []
    for name, model in models.items():
        model_X = predictor_tables[name]
        feat_cols = [c for c in model_X.columns if c not in ("participant_id", "sample_id")]
        X_clean = model_X[feat_cols] if feat_cols else model_X
        for fold_id, (train, test) in enumerate(folds, start=1):
            if model is None:
                fitted = DummyClassifier(strategy="prior")
            else:
                fitted = clone(model)
            fitted.fit(X_clean.iloc[train], labels[train])
            predicted = fitted.predict(X_clean.iloc[test]).astype(int)
            score = None
            if hasattr(fitted, "predict_proba"):
                score = fitted.predict_proba(X_clean.iloc[test])[:, 1]
            elif hasattr(fitted, "decision_function"):
                score = fitted.decision_function(X_clean.iloc[test])
            fold_records = pd.DataFrame(
                {
                    "participant_id": group_values[test],
                    "y_true": labels[test],
                    "y_pred": predicted,
                    "score": score if score is not None else np.nan,
                }
            )
            participant_rows = fold_records.groupby("participant_id", as_index=False).agg(
                y_true=("y_true", "first"),
                y_pred=("y_pred", "mean"),
                score=("score", "mean"),
                n_recordings=("y_true", "size"),
            )
            if "score" in participant_rows and participant_rows["score"].notna().all():
                is_tied = participant_rows["y_pred"] == 0.5
                participant_rows.loc[is_tied, "y_pred"] = (
                    participant_rows.loc[is_tied, "score"] >= 0.5
                ).astype(int)
                participant_rows.loc[~is_tied, "y_pred"] = (
                    participant_rows.loc[~is_tied, "y_pred"] > 0.5
                ).astype(int)
            else:
                participant_rows["y_pred"] = (participant_rows["y_pred"] >= 0.5).astype(int)
            participant_score = participant_rows["score"].to_numpy()
            has_score = bool(np.isfinite(participant_score).all())
            metrics = binary_metrics(
                participant_rows["y_true"].to_numpy(),
                participant_rows["y_pred"].to_numpy(),
                participant_score if has_score else None,
            )
            metric_rows.append(
                {
                    "model": name,
                    "fold": fold_id,
                    "n_participants": len(participant_rows),
                    **metrics,
                }
            )
            participant_rows.insert(0, "fold", fold_id)
            participant_rows.insert(0, "model", name)
            prediction_rows.extend(participant_rows.to_dict("records"))
    return pd.DataFrame(metric_rows), pd.DataFrame(prediction_rows)


def age_only_pipeline(random_seed: int = 2026) -> Pipeline:
    """Age-only comparator; caller must cross-validate it with the same groups."""
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced", max_iter=2000, random_state=random_seed
                ),
            ),
        ]
    )
