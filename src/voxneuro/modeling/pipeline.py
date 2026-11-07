"""Fold-safe preprocessing and baseline classifiers."""

from __future__ import annotations

from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, LinearSVC


def build_pipelines(random_seed: int = 2026) -> dict[str, Pipeline]:
    """Create sklearn Pipelines so imputation/scaling fit only in training folds."""
    # All-missing columns are omitted for that fold rather than silently filled with zero.
    common = [("imputer", SimpleImputer(strategy="median"))]
    scaled = common + [("scaler", StandardScaler())]
    return {
        "logistic_regression": Pipeline(
            scaled
            + [
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced", max_iter=2000, random_state=random_seed
                    ),
                )
            ]
        ),
        "support_vector_machine": Pipeline(
            scaled
            + [("classifier", SVC(kernel="rbf", class_weight="balanced", random_state=random_seed))]
        ),
        "random_forest": Pipeline(
            common
            + [
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=300,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=random_seed,
                        n_jobs=1,
                    ),
                )
            ]
        ),
    }


def _elastic_net_logistic_regression(random_seed: int = 2026) -> LogisticRegression:
    """Build a LogisticRegression configured for elastic net across scikit-learn versions."""
    kwargs: dict[str, object] = {
        "solver": "saga",
        "l1_ratio": 0.5,
        "class_weight": "balanced",
        "max_iter": 5000,
        "random_state": random_seed,
    }
    # In scikit-learn < 1.8, l1_ratio requires penalty='elasticnet'.
    # In scikit-learn >= 1.8, penalty is deprecated and l1_ratio alone configures elastic net.
    if getattr(LogisticRegression(), "penalty", None) != "deprecated":
        kwargs["penalty"] = "elasticnet"
    return LogisticRegression(**kwargs)


def build_nested_model_searches(random_seed: int = 2026) -> dict[str, tuple[Pipeline, dict]]:
    """Return bounded candidate grids for nested, participant-grouped CV.

    Every operation learned from data stays inside a scikit-learn pipeline. The
    grids are intentionally small for the available cohorts; no model family is
    presumed to be best before the outer folds are evaluated.
    """
    impute = [("imputer", SimpleImputer(strategy="median"))]
    scaled = impute + [("scaler", StandardScaler())]

    def pipeline(preprocessing: list[tuple[str, object]], classifier: object) -> Pipeline:
        return Pipeline(preprocessing + [("classifier", classifier)])

    return {
        "logistic_l2": (
            pipeline(
                scaled,
                LogisticRegression(
                    solver="lbfgs",
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=random_seed,
                ),
            ),
            {"classifier__C": [0.01, 0.1, 1.0, 10.0, 100.0]},
        ),
        "logistic_elastic_net": (
            pipeline(scaled, _elastic_net_logistic_regression(random_seed)),
            {
                "classifier__C": [0.1, 1.0, 10.0],
                "classifier__l1_ratio": [0.25, 0.75],
            },
        ),
        "linear_svm": (
            pipeline(
                scaled,
                LinearSVC(
                    class_weight="balanced",
                    dual="auto",
                    max_iter=10000,
                    random_state=random_seed,
                ),
            ),
            {"classifier__C": [0.01, 0.1, 1.0, 10.0]},
        ),
        "rbf_svm": (
            pipeline(
                scaled,
                SVC(kernel="rbf", class_weight="balanced", random_state=random_seed),
            ),
            {
                "classifier__C": [0.1, 1.0, 10.0],
                "classifier__gamma": ["scale", 0.01],
            },
        ),
        "random_forest": (
            pipeline(
                impute,
                RandomForestClassifier(
                    n_estimators=200,
                    class_weight="balanced",
                    random_state=random_seed,
                    n_jobs=1,
                ),
            ),
            {
                "classifier__max_depth": [None, 4],
                "classifier__min_samples_leaf": [2, 4],
            },
        ),
        "extra_trees": (
            pipeline(
                impute,
                ExtraTreesClassifier(
                    n_estimators=200,
                    class_weight="balanced",
                    random_state=random_seed,
                    n_jobs=1,
                ),
            ),
            {
                "classifier__max_depth": [None, 4],
                "classifier__min_samples_leaf": [2, 4],
            },
        ),
        "hist_gradient_boosting": (
            pipeline(
                impute,
                HistGradientBoostingClassifier(
                    learning_rate=0.05,
                    max_iter=75,
                    min_samples_leaf=5,
                    class_weight="balanced",
                    early_stopping=False,
                    random_state=random_seed,
                ),
            ),
            {
                "classifier__max_leaf_nodes": [7, 15],
                "classifier__l2_regularization": [1.0, 10.0],
            },
        ),
    }
