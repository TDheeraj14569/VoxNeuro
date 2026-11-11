"""Unit tests for demographic bias audit and quality attrition analysis."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy.stats import contingency, t

from voxneuro.dataset.bias_audit import (
    _clopper_pearson,
    _pooled_sd,
    audit_age_distribution,
    audit_age_strata,
    audit_feature_level_associations,
    audit_joint_distribution,
    audit_quality_attrition,
    audit_sex_distribution,
    sanitize_for_json,
    validate_demographic_integrity,
)


def test_sanitize_for_json_precision_and_types():
    """Verify that sanitize_for_json preserves full float precision, handles scientific notation,

    and converts NaN/Inf to None without truncation.
    """
    raw = {
        "p_val_tiny": 1.74698e-8,
        "p_val_extreme": 1e-12,
        "standard_float": 0.00123456789,
        "exact_zero": 0.0,
        "integer_val": 42,
        "bool_val": True,
        "nan_val": float("nan"),
        "inf_pos": float("inf"),
        "inf_neg": float("-inf"),
        ("tuple", "key"): [float("nan"), 1.23e-5, None],
    }

    sanitized = sanitize_for_json(raw)

    assert sanitized["p_val_tiny"] == 1.74698e-8
    assert sanitized["p_val_extreme"] == 1e-12
    assert sanitized["standard_float"] == 0.00123456789
    assert sanitized["exact_zero"] == 0.0
    assert sanitized["integer_val"] == 42
    assert sanitized["bool_val"] is True
    assert sanitized["nan_val"] is None
    assert sanitized["inf_pos"] is None
    assert sanitized["inf_neg"] is None
    assert "tuple_key" in sanitized
    assert sanitized["tuple_key"][0] is None
    assert sanitized["tuple_key"][1] == 1.23e-5


def test_clopper_pearson_bounds():
    low, high = _clopper_pearson(0, 10)
    assert low == 0.0
    assert 0.0 < high < 1.0

    low, high = _clopper_pearson(10, 10)
    assert 0.0 < low < 1.0
    assert high == 1.0

    low, high = _clopper_pearson(5, 10)
    assert 0.0 < low < 0.5 < high < 1.0


def test_pooled_sd_calculation():
    a = np.array([10.0, 12.0, 14.0])
    b = np.array([20.0, 22.0, 24.0])
    # Both have variance 4.0, sd 2.0
    pooled = _pooled_sd(a, b)
    assert np.isclose(pooled, 2.0)


def test_audit_age_distribution():
    data = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(20)],
            "class_label": ["HC"] * 10 + ["PD"] * 10,
            "age": [30, 32, 34, 36, 38, 40, 42, 44, 46, 48]
            + [60, 62, 64, 66, 68, 70, 72, 74, 76, 78],
        }
    )

    result = audit_age_distribution(data, n_bootstraps=100, seed=42)

    assert result["HC"]["n"] == 10
    assert result["PD"]["n"] == 10
    assert np.isclose(result["HC"]["mean"], 39.0)
    assert np.isclose(result["PD"]["mean"], 69.0)
    assert result["mean_difference_hc_minus_pd"] == -30.0
    assert result["standardized_mean_difference"] < -3.0
    assert result["mann_whitney_p"] < 0.001
    assert len(result["mean_diff_bootstrap_ci_95"]) == 2
    assert result["mean_diff_bootstrap_ci_95"][0] < result["mean_diff_bootstrap_ci_95"][1]


def test_rank_biserial_sign_convention():
    """Verify rank-biserial correlation sign under HC minus PD convention.

    When HC is younger than PD, r_rb must be strictly negative.
    When HC is older than PD, r_rb must be strictly positive.
    """
    # HC younger than PD
    df_younger_hc = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(20)],
            "class_label": ["HC"] * 10 + ["PD"] * 10,
            "age": [30, 32, 34, 36, 38, 40, 42, 44, 46, 48]
            + [60, 62, 64, 66, 68, 70, 72, 74, 76, 78],
        }
    )
    res_young = audit_age_distribution(df_younger_hc, n_bootstraps=50, seed=2026)
    assert res_young["rank_biserial_correlation"] == -1.0  # complete separation

    # HC older than PD
    df_older_hc = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(20)],
            "class_label": ["HC"] * 10 + ["PD"] * 10,
            "age": [70, 72, 74, 76, 78, 80, 82, 84, 86, 88]
            + [40, 42, 44, 46, 48, 50, 52, 54, 56, 58],
        }
    )
    res_old = audit_age_distribution(df_older_hc, n_bootstraps=50, seed=2026)
    assert res_old["rank_biserial_correlation"] == 1.0


def test_age_student_t_confidence_intervals():
    """Verify that age distribution uses exact Student's t critical values for 95% CIs."""
    ages = [40.0, 45.0, 50.0, 55.0, 60.0]
    df = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(10)],
            "class_label": ["HC"] * 5 + ["PD"] * 5,
            "age": ages + [65.0, 70.0, 75.0, 80.0, 85.0],
        }
    )
    res = audit_age_distribution(df, n_bootstraps=50, seed=2026)

    hc_m = np.mean(ages)
    hc_sd = np.std(ages, ddof=1)
    se = hc_sd / math.sqrt(5)
    t_crit = t.ppf(0.975, df=4)
    expected_low = hc_m - t_crit * se
    expected_high = hc_m + t_crit * se

    assert np.isclose(res["HC"]["mean_ci_95"][0], expected_low)
    assert np.isclose(res["HC"]["mean_ci_95"][1], expected_high)


def test_cramers_v_without_yates():
    """Verify that Cramér's V uses standard Pearson chi-square without Yates correction."""
    data = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(40)],
            "class_label": ["HC"] * 20 + ["PD"] * 20,
            "sex": ["F"] * 15 + ["M"] * 5 + ["F"] * 8 + ["M"] * 12,
        }
    )
    result = audit_sex_distribution(data)
    table = [[15, 5], [8, 12]]
    chi2_val = contingency.chi2_contingency(table, correction=False)[0]
    expected_v = math.sqrt(chi2_val / 40)
    assert np.isclose(result["cramers_v"], expected_v)


def test_audit_age_distribution_missing_columns():
    with pytest.raises(ValueError, match="must contain 'age' and 'class_label'"):
        audit_age_distribution(pd.DataFrame({"participant_id": [1]}))


def test_audit_age_distribution_missing_class():
    with pytest.raises(ValueError, match="Both 'HC' and 'PD'"):
        audit_age_distribution(pd.DataFrame({"class_label": ["HC"], "age": [50]}))


def test_audit_sex_distribution():
    data = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(20)],
            "class_label": ["HC"] * 10 + ["PD"] * 10,
            "sex": ["F"] * 6 + ["M"] * 4 + ["F"] * 3 + ["M"] * 7,
        }
    )

    result = audit_sex_distribution(data)

    assert result["counts"]["HC"]["F"] == 6
    assert result["counts"]["HC"]["M"] == 4
    assert result["counts"]["PD"]["F"] == 3
    assert result["counts"]["PD"]["M"] == 7
    assert 0.0 <= result["fisher_exact_p"] <= 1.0
    assert result["odds_ratio"] > 1.0  # (6/4)/(3/7) = 3.5
    assert 0.0 <= result["cramers_v"] <= 1.0
    assert result["missing_sex_count"] == 0


def test_audit_sex_distribution_missing_values():
    data = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3", "p4"],
            "class_label": ["HC", "HC", "PD", "PD"],
            "sex": ["F", None, "M", "M"],
        }
    )
    result = audit_sex_distribution(data)
    assert result["missing_sex_count"] == 1


def test_audit_joint_distribution():
    data = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(12)],
            "class_label": ["HC", "HC", "HC", "PD", "PD", "PD"] * 2,
            "sex": ["F"] * 6 + ["M"] * 6,
            "age": [40, 45, 50, 48, 55, 60] + [50, 55, 60, 58, 65, 70],
        }
    )

    result = audit_joint_distribution(data)
    assert "F" in result and "M" in result
    assert result["F"]["has_common_support"] is True
    assert result["F"]["common_support_overlap"] == [48.0, 50.0]
    assert result["M"]["has_common_support"] is True
    assert result["M"]["common_support_overlap"] == [58.0, 60.0]


def test_audit_joint_distribution_no_support():
    data = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3", "p4"],
            "class_label": ["HC", "HC", "PD", "PD"],
            "sex": ["F", "F", "F", "F"],
            "age": [20, 25, 60, 65],
        }
    )
    result = audit_joint_distribution(data)
    assert result["F"]["has_common_support"] is False
    assert result["F"]["common_support_overlap"] is None


def test_validate_demographic_integrity():
    """Verify demographic data integrity validation on clean and corrupted datasets."""
    clean_manifest = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3"],
            "class_label": ["HC", "HC", "PD"],
        }
    )
    clean_demo = pd.DataFrame(
        {
            "participant_id": ["p1", "p2", "p3"],
            "class_label": ["HC", "HC", "PD"],
            "sex": ["F", "M", "F"],
            "age": [45.0, 50.0, 65.0],
        }
    )

    clean_res = validate_demographic_integrity(clean_manifest, clean_demo)
    assert clean_res["valid"] is True
    assert len(clean_res["issues"]) == 0

    # Corrupted: missing participant in demographics
    corrupt_demo = clean_demo.iloc[:2].copy()
    corrupt_res = validate_demographic_integrity(clean_manifest, corrupt_demo)
    assert corrupt_res["valid"] is False
    assert corrupt_res["unmatched_manifest_count"] == 1


def test_audit_age_strata_small_cell_suppression():
    """Verify that age strata enforce small-cell suppression (< 10 per class)."""
    # 5 HC and 2 PD in under 50; 12 HC and 15 PD in 50-59
    frame = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(34)],
            "class_label": ["HC"] * 5 + ["PD"] * 2 + ["HC"] * 12 + ["PD"] * 15,
            "age": [45.0] * 5 + [48.0] * 2 + [55.0] * 12 + [57.0] * 15,
        }
    )
    strata_df = audit_age_strata(frame, min_cell_per_class=10)

    under_50 = strata_df[strata_df["age_band"] == "Under 50"].iloc[0]
    assert under_50["status"] == "NOT ESTIMABLE"
    assert "Small-cell suppression" in under_50["suppression_reason"]

    band_50_59 = strata_df[strata_df["age_band"] == "50-59"].iloc[0]
    assert band_50_59["status"] == "ESTIMABLE"
    assert band_50_59["suppression_reason"] == "Adequate class support"


def test_audit_feature_level_associations():
    """Verify multivariable logistic LRT and Benjamini-Hochberg FDR multiplicity control."""
    rng = np.random.default_rng(2026)
    n = 30
    frame = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(n)],
            "class_label": ["HC"] * (n // 2) + ["PD"] * (n // 2),
            "age": rng.uniform(40, 80, size=n),
            "sex": ["F", "M"] * (n // 2),
            "feat_sig": [0.0] * (n // 2) + [3.0] * (n // 2) + rng.normal(0, 0.5, size=n),
            "feat_noise": rng.normal(0, 1.0, size=n),
        }
    )

    fdr_df = audit_feature_level_associations(frame, ["feat_sig", "feat_noise"])
    assert len(fdr_df) == 2
    assert "p_unadjusted" in fdr_df.columns
    assert "fdr_q_value" in fdr_df.columns
    assert "significant_fdr_05" in fdr_df.columns
    # Check monotonicity of BH q-values
    assert fdr_df["fdr_q_value"].iloc[0] <= fdr_df["fdr_q_value"].iloc[1]


def test_audit_quality_attrition():
    manifest = pd.DataFrame(
        {
            "sample_id": ["s1", "s2", "s3", "s4"],
            "class_label": ["HC", "HC", "PD", "PD"],
        }
    )
    extraction = pd.DataFrame(
        {
            "sample_id": ["s1", "s2", "s3", "s4"],
            "extraction_status": ["success", "success", "success", "failed"],
            "failure_reason": [None, None, None, "Excessive clipping detected in audio."],
        }
    )

    result = audit_quality_attrition(manifest, extraction)

    assert result["class_summary"]["HC"]["accepted_count"] == 2
    assert result["class_summary"]["HC"]["excluded_count"] == 0
    assert result["class_summary"]["PD"]["accepted_count"] == 1
    assert result["class_summary"]["PD"]["excluded_count"] == 1
    assert result["clipping_exclusions"] == 1
    assert result["total_excluded"] == 1
    assert 0.0 <= result["fisher_exact_p"] <= 1.0
