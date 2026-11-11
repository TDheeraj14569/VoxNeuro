"""Unit tests for demographic sensitivity modeling and comparator baselines."""

from __future__ import annotations

import numpy as np
import pandas as pd

from voxneuro.modeling.demographic_sensitivity import (
    _paired_bootstrap_ci,
    build_demographic_comparator_pipelines,
    evaluate_demographic_models,
)


def test_build_demographic_comparator_pipelines():
    pipelines = build_demographic_comparator_pipelines(feature_names=["f1", "f2"], seed=2026)
    expected_models = {
        "majority_classifier",
        "voice_only_svm",
        "voice_only_logistic",
        "age_only_logistic",
        "sex_only_logistic",
        "age_plus_sex_logistic",
        "age_plus_voice_logistic",
        "age_plus_sex_plus_voice_logistic",
    }
    assert set(pipelines.keys()) == expected_models
    for _name, (cols, est, grid) in pipelines.items():
        assert len(cols) > 0
        assert hasattr(est, "fit")
        assert isinstance(grid, dict)


def test_paired_bootstrap_ci_identical():
    y_true = np.array([0, 1, 0, 1, 0, 1, 0, 1])
    pred = np.array([0, 1, 0, 1, 0, 1, 0, 1])
    low, high = _paired_bootstrap_ci(y_true, pred, pred, iterations=100, seed=42)
    assert np.isclose(low, 0.0)
    assert np.isclose(high, 0.0)


def test_paired_bootstrap_ci_reproducibility():
    """Verify that paired bootstrap CI produces identical intervals with same random seed."""
    rng = np.random.default_rng(123)
    y_true = rng.integers(0, 2, size=50)
    pred_a = rng.integers(0, 2, size=50)
    pred_b = rng.integers(0, 2, size=50)

    low1, high1 = _paired_bootstrap_ci(y_true, pred_a, pred_b, iterations=200, seed=2026)
    low2, high2 = _paired_bootstrap_ci(y_true, pred_a, pred_b, iterations=200, seed=2026)

    assert low1 == low2
    assert high1 == high2


def test_evaluate_demographic_models_synthetic_and_decision_rules():
    """Verify demographic model evaluation, participant pairing, and SAP decision rules."""
    rng = np.random.default_rng(42)
    n = 24
    frame = pd.DataFrame(
        {
            "sample_id": [f"s{i}" for i in range(n)],
            "participant_id": [f"p{i}" for i in range(n)],
            "class_label": ["HC"] * (n // 2) + ["PD"] * (n // 2),
            "age": [30.0 + i for i in range(n // 2)] + [60.0 + i for i in range(n // 2)],
            "sex": ["F", "M"] * (n // 2),
            "feat1": rng.normal(size=n),
            "feat2": rng.normal(size=n),
        }
    )

    results = evaluate_demographic_models(
        frame,
        feature_names=["feat1", "feat2"],
        outer_splits=2,
        inner_splits=2,
        random_seeds=(2026, 2027),
        bootstrap_iterations=50,
    )

    assert "comparator_metrics" in results
    assert "paired_incremental" in results
    assert "sex_subgroups" in results
    assert "fold_metrics" in results
    assert "oof_predictions" in results

    comp = results["comparator_metrics"]
    assert "matched_voice_svm" in comp["model"].values
    matched_row = comp[comp["model"] == "matched_voice_svm"].iloc[0]
    assert matched_row["status"] == "NOT ESTIMABLE"

    paired = results["paired_incremental"]
    assert len(paired) == 2

    # Check that paired comparisons have required columns
    for _, row in paired.iterrows():
        assert "delta_balanced_accuracy" in row
        assert "delta_ci_95" in row
        assert "secondary_repeated_cv_delta_ba" in row
        assert "supplementary_mcnemar_exact_p" in row
        assert "statistically_supported_incremental_contribution" in row
        assert "inference" in row

        # Decision rule: positive contribution supported ONLY if CI lower bound > 0
        ci = row["delta_ci_95"]
        expected_supported = bool(ci[0] > 0.0)
        assert row["statistically_supported_incremental_contribution"] == expected_supported

    # Participant pairing check in OOF predictions
    oof = results["oof_predictions"]
    pred_age = oof[(oof["model"] == "age_only_logistic") & (oof["repeat_seed"] == 2026)]
    pred_av = oof[(oof["model"] == "age_plus_voice_logistic") & (oof["repeat_seed"] == 2026)]
    assert len(pred_age) == n
    assert len(pred_av) == n
    assert (pred_age["participant_id"].to_numpy() == pred_av["participant_id"].to_numpy()).all()
