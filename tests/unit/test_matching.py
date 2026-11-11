"""Unit tests for demographic matching algorithms and sensitivity analyses."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from voxneuro.dataset.matching import (
    evaluate_matching_sensitivities,
    perform_optimal_matching,
)


def test_perform_optimal_matching_exact_sex():
    data = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(8)],
            "class_label": ["HC", "HC", "HC", "HC", "PD", "PD", "PD", "PD"],
            "sex": ["F", "F", "M", "M", "F", "F", "M", "M"],
            "age": [50.0, 52.0, 60.0, 62.0, 51.0, 53.0, 61.0, 63.0],
        }
    )

    matched_df, summary = perform_optimal_matching(data, caliper_multiplier=0.5)

    assert summary["matched_pairs"] == 4
    assert len(matched_df) == 8

    # Verify every pair has exact same sex
    for _, group in matched_df.groupby("pair_id"):
        assert len(group) == 2
        assert group["sex"].nunique() == 1
        assert group["class_label"].nunique() == 2
        age_diff = abs(group["age"].iloc[0] - group["age"].iloc[1])
        assert np.isclose(group["match_age_distance"].iloc[0], age_diff)


def test_caliper_enforcement_filters_distant_pairs():
    data = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3", "p4"],
            "class_label": ["HC", "HC", "PD", "PD"],
            "sex": ["F", "F", "F", "F"],
            "age": [30.0, 32.0, 70.0, 72.0],  # 40-year difference, large SD
        }
    )

    # With tight caliper (0.1 SD), no pairs should match
    matched_df, summary = perform_optimal_matching(data, caliper_multiplier=0.1)
    assert summary["matched_pairs"] == 0
    assert matched_df.empty

    # With uncalipered matching, all 2 pairs match despite large distance
    matched_df, summary = perform_optimal_matching(data, caliper_multiplier=None)
    assert summary["matched_pairs"] == 2
    assert summary["mean_pairwise_age_diff"] == 40.0


def test_matching_reduces_smd():
    data = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(10)],
            "class_label": ["HC"] * 5 + ["PD"] * 5,
            "sex": ["M"] * 10,
            "age": [40.0, 45.0, 50.0, 55.0, 60.0] + [52.0, 58.0, 65.0, 70.0, 75.0],
        }
    )

    matched_df, summary = perform_optimal_matching(data, caliper_multiplier=0.5)
    assert summary["matched_pairs"] > 0
    # Post-match SMD should be closer to 0 than pre-match SMD
    assert abs(summary["post_match_smd"]) < abs(summary["pre_match_smd"])


def test_matching_input_validation():
    with pytest.raises(ValueError, match="must contain columns"):
        perform_optimal_matching(pd.DataFrame({"participant_id": [1]}))

    with pytest.raises(ValueError, match="Both HC and PD groups must have valid participants"):
        perform_optimal_matching(
            pd.DataFrame(
                {
                    "participant_id": ["p1", "p2"],
                    "class_label": ["HC", "HC"],
                    "sex": ["F", "F"],
                    "age": [50.0, 55.0],
                }
            )
        )


def test_evaluate_matching_sensitivities_monotonicity():
    data = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(12)],
            "class_label": ["HC"] * 6 + ["PD"] * 6,
            "sex": ["F", "F", "M", "M", "F", "M"] * 2,
            "age": [35.0, 42.0, 48.0, 55.0, 62.0, 70.0] + [50.0, 54.0, 60.0, 68.0, 72.0, 78.0],
        }
    )

    table = evaluate_matching_sensitivities(data, calipers=(0.1, 0.2, 0.5, None))

    assert len(table) == 4
    pairs = table["matched_pairs"].tolist()
    # Tighter calipers must produce <= looser calipers
    assert pairs[0] <= pairs[1] <= pairs[2] <= pairs[3]
