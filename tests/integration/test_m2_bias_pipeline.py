"""Integration tests for the Milestone 2 scientific bias and demographic pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from scripts.analyze_scientific_bias import main as run_bias_analysis

ROOT = Path(__file__).resolve().parents[2]


def test_m2_bias_analysis_pipeline_execution():
    """Verify that analyze_scientific_bias executes and produces all required artifacts."""
    raw_demo = ROOT / "data" / "raw" / "uams" / "Demographics_age_sex.xlsx"
    if not raw_demo.is_file():
        pytest.skip(
            "DATA REQUIRED: Raw UAMS demographic data is not packaged in distribution archive "
            "(privacy-safe release)."
        )

    exit_code = run_bias_analysis([])
    assert exit_code == 0

    processed_dir = ROOT / "data" / "processed"
    reports_dir = ROOT / "artifacts" / "reports" / "scientific_audit"
    figures_dir = reports_dir / "figures"

    # Verify data files
    demo_sum_path = processed_dir / "m2_demographic_summary.json"
    attr_sum_path = processed_dir / "m2_attrition_summary.json"
    match_sens_path = processed_dir / "m2_matching_sensitivity.csv"
    match_assign_path = processed_dir / "m2_matching_assignments.csv"
    age_strata_path = processed_dir / "m2_age_subgroup_summary.csv"
    feature_fdr_path = processed_dir / "m2_feature_fdr_summary.csv"

    assert demo_sum_path.is_file()
    assert attr_sum_path.is_file()
    assert match_sens_path.is_file()
    assert match_assign_path.is_file()
    assert age_strata_path.is_file()
    assert feature_fdr_path.is_file()

    # Verify figures
    assert (figures_dir / "m2_age_distribution.png").is_file()
    assert (figures_dir / "m2_sex_distribution.png").is_file()
    assert (figures_dir / "m2_age_sex_overlap.png").is_file()

    # Verify HTML reports
    assert (reports_dir / "m2_demographic_audit.html").is_file()
    assert (reports_dir / "m2_attrition_analysis.html").is_file()
    assert (reports_dir / "m2_matching_balance.html").is_file()
    assert (reports_dir / "m2_bias_audit.html").is_file()

    # Validate demographic findings
    demo_data = json.loads(demo_sum_path.read_text(encoding="utf-8"))
    pop1_age = demo_data["population_1_source"]["age"]
    assert pop1_age["HC"]["n"] == 41
    assert pop1_age["PD"]["n"] == 40
    assert abs(pop1_age["mean_difference_hc_minus_pd"] - (-19.31)) < 0.2
    assert abs(pop1_age["standardized_mean_difference"] - (-1.61)) < 0.1
    assert pop1_age["mann_whitney_p"] < 1e-6
    assert pop1_age["rank_biserial_correlation"] < 0.0  # HC younger than PD

    # Validate matching sample size exhaustion
    matching_df = pd.read_csv(match_sens_path)
    row_02 = matching_df[matching_df["caliper_specification"] == "0.2 SD"].iloc[0]
    assert row_02["matched_pairs"] == 5
    assert row_02["matched_total"] == 10
    assert demo_data["matching_analysis"]["matched_pairs_retained"] == 5

    # Validate attrition findings
    attr_data = json.loads(attr_sum_path.read_text(encoding="utf-8"))
    assert attr_data["class_summary"]["HC"]["accepted_count"] == 41
    assert attr_data["class_summary"]["HC"]["excluded_count"] == 0
    assert attr_data["class_summary"]["PD"]["accepted_count"] == 37
    assert attr_data["class_summary"]["PD"]["excluded_count"] == 3
    assert attr_data["clipping_exclusions"] == 3


def test_m2_demographic_evaluation_outputs_validation():
    """Verify that demographic sensitivity outputs conform to pre-registered SAP criteria."""
    processed_dir = ROOT / "data" / "processed"
    reports_dir = ROOT / "artifacts" / "reports" / "scientific_audit"

    comp_path = processed_dir / "m2_comparator_metrics.csv"
    paired_path = processed_dir / "m2_paired_incremental_voice.csv"
    receipt_path = processed_dir / "m2_analysis_receipt.json"
    html_path = reports_dir / "m2_model_comparison.html"

    # If already generated, test structure and decision rules
    if comp_path.is_file():
        comp_df = pd.read_csv(comp_path)
        assert len(comp_df) == 9  # 8 models + matched_voice_svm

        # Check matched cohort status
        matched_row = comp_df[comp_df["model"] == "matched_voice_svm"].iloc[0]
        assert matched_row["status"] == "NOT ESTIMABLE"
        assert pd.isna(matched_row["balanced_accuracy_mean"])

        # Check age-only performance
        age_row = comp_df[comp_df["model"] == "age_only_logistic"].iloc[0]
        assert age_row["balanced_accuracy_mean"] > 0.80

    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["milestone"] == "M2"
        assert receipt["analysis_name"] == "m2_demographic_sensitivity_evaluation"

    if html_path.is_file():
        assert html_path.stat().st_size > 0

    if paired_path.is_file():
        paired_df = pd.read_csv(paired_path)
        assert len(paired_df) == 2
        for _, row in paired_df.iterrows():
            has_supp = (
                "statistically_supported_incremental_contribution" in row
                or "statistically_significant" in row
            )
            assert has_supp
            p_val = row.get(
                "supplementary_mcnemar_exact_p",
                row.get("mcnemar_exact_p", 1.0),
            )
            assert p_val >= 0.05


def test_m2_report_data_consistency():
    """Verify numerical consistency between processed summaries and M2_BIAS_AUDIT_REPORT.md."""
    processed_dir = ROOT / "data" / "processed"
    demo_sum_path = processed_dir / "m2_demographic_summary.json"
    report_md_path = ROOT / "docs" / "reports" / "M2_BIAS_AUDIT_REPORT.md"

    if not demo_sum_path.is_file() or not report_md_path.is_file():
        pytest.skip("Summary JSON or markdown report not generated yet.")

    demo = json.loads(demo_sum_path.read_text(encoding="utf-8"))
    report_text = report_md_path.read_text(encoding="utf-8")

    # Check key demographic figures
    pop1_age = demo["population_1_source"]["age"]
    assert "19.31" in report_text
    assert "-1.61" in report_text
    assert "-0.728" in report_text or f"{pop1_age['rank_biserial_correlation']:.3f}" in report_text
    assert "5 matched pairs" in report_text.lower() or "5 pairs" in report_text.lower()
    assert "not estimable" in report_text.lower()
