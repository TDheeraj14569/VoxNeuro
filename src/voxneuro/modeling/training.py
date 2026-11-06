"""Fit a research model only after completing grouped cross-validation."""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import GridSearchCV

from voxneuro.modeling.pipeline import build_nested_model_searches, build_pipelines
from voxneuro.modeling.splits import grouped_splits


def fit_final_research_model(
    X: pd.DataFrame, y, model_name: str = "logistic_regression", random_seed: int = 2026
):
    """Fit the requested named pipeline to all development data for research use."""
    pipelines = build_pipelines(random_seed)
    if model_name not in pipelines:
        raise ValueError(f"Unknown model {model_name!r}; choose from {sorted(pipelines)}")
    model = pipelines[model_name]
    model.fit(X, y)
    return model


def fit_tuned_logistic_reference(
    X: pd.DataFrame,
    y,
    groups,
    *,
    n_splits: int = 5,
    random_seed: int = 2026,
):
    """Tune L2 logistic regularization using group CV, then refit on development data.

    This fitting score is model development, not an independent performance estimate.
    The nested-CV report is the separate performance estimate for the tuning procedure.
    """
    estimator, parameter_grid = build_nested_model_searches(random_seed)["logistic_l2"]
    folds = list(grouped_splits(y, groups, n_splits, random_seed))
    search = GridSearchCV(
        estimator=estimator,
        param_grid=parameter_grid,
        scoring="balanced_accuracy",
        cv=folds,
        refit=True,
        n_jobs=1,
        error_score="raise",
        return_train_score=False,
    )
    search.fit(X, y)
    return search.best_estimator_, {
        "selection_metric": "participant-grouped inner-CV balanced accuracy",
        "selected_parameters": search.best_params_,
        "inner_cv_mean_balanced_accuracy": float(search.best_score_),
        "participant_groups": int(pd.Series(groups).nunique()),
        "training_rows": int(len(X)),
        "refit_on_all_development_data": True,
        "performance_claim_source": "repeated nested cross-validation report; not this fit score",
    }
