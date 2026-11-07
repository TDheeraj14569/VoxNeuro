import numpy as np
import pandas as pd
import pytest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from tests.fixtures.synthetic_manifest import binary_groups
from voxneuro.modeling.evaluation import (
    binary_metrics,
    evaluate_grouped,
    evaluate_nested_grouped,
)
from voxneuro.modeling.pipeline import build_nested_model_searches


def test_pr_auc_and_average_precision_are_distinct_and_brier_needs_probabilities():
    metrics = binary_metrics(
        np.asarray([1, 0, 1, 0]),
        np.asarray([1, 0, 1, 0]),
        np.asarray([0.9, 0.8, 0.7, 0.6]),
    )
    assert "average_precision" in metrics
    assert "pr_auc" in metrics
    assert metrics["pr_auc"] != metrics["average_precision"]
    assert np.isnan(metrics["brier_score"])
    with_probabilities = binary_metrics(
        np.asarray([0, 1, 1, 0]),
        np.asarray([0, 1, 0, 0]),
        np.asarray([0.1, 0.8, 0.4, 0.2]),
        np.asarray([0.1, 0.8, 0.4, 0.2]),
    )
    assert 0 <= with_probabilities["brier_score"] <= 1


def test_grouped_baselines_produce_fold_metrics_and_oof_rows():
    X, y, groups = binary_groups(30, 2)
    metrics, predictions = evaluate_grouped(X, y, groups, n_splits=5)
    assert set(metrics.model) == {
        "dummy",
        "logistic_regression",
        "support_vector_machine",
        "random_forest",
    }
    assert len(predictions[predictions.model == "logistic_regression"]) == len(set(groups))
    assert metrics.balanced_accuracy.between(0, 1).all()


def test_demographic_and_combined_baselines_share_grouped_folds():
    voice, y, groups = binary_groups(30, 2)
    age = voice[["feature_a"]].rename(columns={"feature_a": "age"}) + 45
    combined = age.join(voice)
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(class_weight="balanced", max_iter=1000)),
        ]
    )
    metrics, predictions = evaluate_grouped(
        voice,
        y,
        groups,
        n_splits=5,
        additional_models={
            "age_only_logistic": (age, pipeline),
            "age_plus_voice_logistic": (combined, pipeline),
        },
    )
    assert set(metrics.model) >= {"age_only_logistic", "age_plus_voice_logistic"}
    fold_maps = []
    for name in ("age_only_logistic", "age_plus_voice_logistic"):
        selected = predictions.loc[predictions.model.eq(name)]
        assert len(selected) == len(set(groups))
        fold_maps.append(selected.set_index("participant_id")["fold"].sort_index())
    assert fold_maps[0].equals(fold_maps[1])
    voice_folds = (
        predictions.loc[predictions.model.eq("logistic_regression")]
        .set_index("participant_id")["fold"]
        .sort_index()
    )
    assert fold_maps[0].equals(voice_folds)


def test_nested_search_candidates_are_fold_safe_and_bounded():
    searches = build_nested_model_searches()
    assert set(searches) == {
        "logistic_l2",
        "logistic_elastic_net",
        "linear_svm",
        "rbf_svm",
        "random_forest",
        "extra_trees",
        "hist_gradient_boosting",
    }
    for estimator, grid in searches.values():
        assert "imputer" in estimator.named_steps
        assert grid


def test_nested_evaluation_keeps_each_participant_in_one_outer_fold():
    X, y, groups = binary_groups(30, 2)
    metrics, predictions, folds = evaluate_nested_grouped(
        X,
        y,
        groups,
        outer_splits=3,
        inner_splits=2,
        random_seeds=(17, 18),
        bootstrap_iterations=100,
        model_names=("logistic_l2",),
    )
    assert set(metrics.model) == {"dummy", "logistic_l2"}
    assert len(folds) == 12
    assert len(metrics) == 4
    assert len(predictions) == 120
    for _, model_predictions in predictions.groupby(["model", "repeat_seed"]):
        assert model_predictions.participant_id.nunique() == 30
        assert not model_predictions.participant_id.duplicated().any()
        assert model_predictions.groupby("participant_id").outer_fold.nunique().eq(1).all()
    fitted = metrics.loc[metrics.model.eq("logistic_l2") & metrics.repeat_seed.eq(17)].iloc[0]
    assert fitted["balanced_accuracy_ci_low"] <= fitted["balanced_accuracy"]
    assert fitted["balanced_accuracy"] <= fitted["balanced_accuracy_ci_high"]
    assert np.isnan(
        metrics.loc[
            metrics.model.eq("logistic_l2") & metrics.repeat_seed.eq(18), "balanced_accuracy_ci_low"
        ].iloc[0]
    )


def test_evaluate_grouped_rejects_invalid_labels_and_dimensions():
    X, valid_y, groups = binary_groups(20, 2)
    # Valid binary inputs must pass
    metrics, _ = evaluate_grouped(X, valid_y, groups, n_splits=3)
    assert not metrics.empty

    # Fractional labels must be rejected
    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, [0, 0.5, 1, 1] * 10, groups, n_splits=3)

    # Multi-class / out-of-range labels must be rejected
    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, [0, 2, 1, 0] * 10, groups, n_splits=3)

    # Non-finite / NaN labels must be rejected
    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, [0, np.nan, 1, 0] * 10, groups, n_splits=3)

    # Boolean labels must be rejected
    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, [False, True] * 20, groups, n_splits=3)

    # Mixed numpy boolean and integer labels must be rejected
    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, [np.bool_(False), 1] * 20, groups, n_splits=3)

    # Boolean numpy array must be rejected
    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, np.array([False, True] * 20), groups, n_splits=3)

    # Mixed boolean and integer labels must be rejected
    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, [False, 1] * 20, groups, n_splits=3)

    with pytest.raises(ValueError, match="Labels must contain only finite binary values"):
        evaluate_grouped(X, pd.Series([False, 1] * 20), groups, n_splits=3)

    # Non-DataFrame X must be rejected
    with pytest.raises(ValueError, match="X must be a pandas DataFrame"):
        evaluate_grouped(X.to_numpy(), valid_y, groups, n_splits=3)

    # Length mismatch between X and y must be rejected
    with pytest.raises(ValueError, match="X and y must contain the same number of rows"):
        evaluate_grouped(X.iloc[:-2], valid_y, groups, n_splits=3)


def test_evaluate_grouped_and_nested_reject_misaligned_additional_predictors():
    voice, y, groups = binary_groups(20, 2)
    # Permute index to simulate row misalignment
    misaligned_age = voice[["feature_a"]].rename(columns={"feature_a": "age"}).sample(frac=1.0)
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(class_weight="balanced", max_iter=1000)),
        ]
    )
    with pytest.raises(ValueError, match="Additional predictor rows for .* must align with X"):
        evaluate_grouped(
            voice,
            y,
            groups,
            n_splits=3,
            additional_models={"age_only": (misaligned_age, pipeline)},
        )

    with pytest.raises(ValueError, match="Additional predictor rows for .* must align with X"):
        evaluate_nested_grouped(
            voice,
            y,
            groups,
            outer_splits=3,
            inner_splits=2,
            random_seeds=(42,),
            additional_searches={
                "age_only": (misaligned_age, pipeline, {"classifier__C": [0.1, 1.0]})
            },
        )

    # Permute rows and reset index with participant_id column present
    voice_with_id = voice.copy()
    voice_with_id["participant_id"] = groups
    shuffled_age_reset = (
        pd.DataFrame({"participant_id": groups, "age": np.linspace(40, 80, len(groups))})
        .sample(frac=1.0)
        .reset_index(drop=True)
    )
    with pytest.raises(ValueError, match="Additional predictor participant_id sequence for"):
        evaluate_grouped(
            voice_with_id,
            y,
            groups,
            n_splits=3,
            additional_models={"age_only": (shuffled_age_reset, pipeline)},
        )

    # X participant_id mismatch against groups must be rejected
    bad_x_id = voice_with_id.copy()
    bad_x_id["participant_id"] = np.roll(groups, 1)
    with pytest.raises(ValueError, match="X\\['participant_id'\\] does not match"):
        evaluate_grouped(bad_x_id, y, groups, n_splits=3)

    # Identifiers present in X and predictors are cleanly stripped before fitting
    voice_with_both_ids = voice.copy()
    voice_with_both_ids["participant_id"] = groups
    voice_with_both_ids["sample_id"] = [f"s_{i}" for i in range(len(groups))]
    age_with_both_ids = pd.DataFrame(
        {
            "participant_id": groups,
            "sample_id": [f"s_{i}" for i in range(len(groups))],
            "age": np.linspace(40, 80, len(groups)),
        }
    )
    res_m, res_p = evaluate_grouped(
        voice_with_both_ids,
        y,
        groups,
        n_splits=3,
        additional_models={"age_only": (age_with_both_ids, pipeline)},
    )
    assert not res_m.empty


def test_elastic_net_candidate_configures_l1_ratio_correctly():
    searches = build_nested_model_searches()
    pipe, grid = searches["logistic_elastic_net"]
    clf = pipe.named_steps["classifier"]
    assert clf.l1_ratio == 0.5
    assert clf.solver == "saga"
    # Verify candidate fits cleanly on synthetic binary data
    X, y, _ = binary_groups(10, 2)
    pipe.fit(X, y)
    preds = pipe.predict(X)
    assert len(preds) == len(y)


def test_evaluation_rejects_identifier_only_predictor_tables():
    voice, y, groups = binary_groups(10, 2)
    id_only = pd.DataFrame(
        {"participant_id": groups, "sample_id": [f"s_{i}" for i in range(len(groups))]}
    )
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("classifier", LogisticRegression()),
        ]
    )
    with pytest.raises(ValueError, match="must contain at least one feature column"):
        evaluate_grouped(id_only, y, groups, n_splits=2)

    with pytest.raises(ValueError, match="must contain at least one feature column"):
        evaluate_grouped(
            voice,
            y,
            groups,
            n_splits=2,
            additional_models={"id_only": (id_only, pipeline)},
        )


@pytest.mark.parametrize("invalid_iter", [1.5, True, False, -1, "100"])
def test_nested_evaluation_rejects_invalid_bootstrap_iterations(invalid_iter):
    X, y, groups = binary_groups(10, 2)
    with pytest.raises(ValueError, match="bootstrap_iterations must be a non-negative integer"):
        evaluate_nested_grouped(
            X,
            y,
            groups,
            outer_splits=2,
            inner_splits=2,
            random_seeds=(42,),
            bootstrap_iterations=invalid_iter,
        )
