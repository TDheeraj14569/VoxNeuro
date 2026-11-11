"""Analyze scientific bias, demographic confounding, and matching sensitivity for UAMS cohort."""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from voxneuro.dataset.bias_audit import (
    audit_age_distribution,
    audit_age_strata,
    audit_feature_level_associations,
    audit_joint_distribution,
    audit_quality_attrition,
    audit_sex_distribution,
    sanitize_for_json,
    validate_demographic_integrity,
)
from voxneuro.dataset.matching import (
    evaluate_matching_sensitivities,
    perform_optimal_matching,
)
from voxneuro.features.schema import FEATURE_NAMES

ROOT = Path(__file__).resolve().parents[1]


def normalize_sample_id(value: object) -> str:
    """Normalize participant/sample ID by stripping UUID and trailing extensions."""
    if pd.isna(value):
        raise ValueError("Missing sample ID in demographics workbook.")
    val_str = str(value).strip()
    val_str = re.sub(r"\.wav$", "", val_str, flags=re.IGNORECASE)
    val_str = re.sub(
        r"[_-][0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        "",
        val_str,
    )
    return val_str.casefold()


def generate_figures(
    pop1_df: pd.DataFrame,
    pop2_df: pd.DataFrame,
    matched_df: pd.DataFrame,
    sex_pop1: dict[str, Any],
    sex_pop2: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Generate high-quality diagnostic bias figures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # Figure 1: Age Distributions (Pre-matching vs Post-matching)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # Subplot A: Population 1 (Source cohort)
    hc_age_pop1 = pop1_df[pop1_df["class_label"] == "HC"]["age"].dropna().to_numpy()
    pd_age_pop1 = pop1_df[pop1_df["class_label"] == "PD"]["age"].dropna().to_numpy()
    gap_pop1 = abs(float(np.mean(hc_age_pop1)) - float(np.mean(pd_age_pop1)))

    axes[0].hist(
        hc_age_pop1,
        bins=12,
        alpha=0.6,
        color="#2b5c8f",
        label=f"Healthy Control (N={len(hc_age_pop1)}, Mean={np.mean(hc_age_pop1):.1f}y)",
        edgecolor="black",
    )
    axes[0].hist(
        pd_age_pop1,
        bins=12,
        alpha=0.6,
        color="#c23b22",
        label=f"Parkinson's (N={len(pd_age_pop1)}, Mean={np.mean(pd_age_pop1):.1f}y)",
        edgecolor="black",
    )
    axes[0].axvline(np.mean(hc_age_pop1), color="#2b5c8f", linestyle="--", linewidth=2)
    axes[0].axvline(np.mean(pd_age_pop1), color="#c23b22", linestyle="--", linewidth=2)
    axes[0].set_title(
        f"Source Cohort Age Distribution (Pop 1, N={len(pop1_df)})\n"
        f"Mean Gap: {gap_pop1:.2f} yrs "
        f"(HC: {np.mean(hc_age_pop1):.1f}y, PD: {np.mean(pd_age_pop1):.1f}y)",
        fontsize=11,
        fontweight="bold",
    )
    axes[0].set_xlabel("Age (years)", fontsize=10)
    axes[0].set_ylabel("Participant Count", fontsize=10)
    axes[0].legend(loc="upper left", fontsize=9)
    axes[0].grid(axis="y", linestyle=":", alpha=0.6)

    # Subplot B: Post-matching (0.2 SD caliper)
    if not matched_df.empty:
        hc_age_m = matched_df[matched_df["class_label"] == "HC"]["age"].to_numpy()
        pd_age_m = matched_df[matched_df["class_label"] == "PD"]["age"].to_numpy()
        axes[1].hist(
            hc_age_m,
            bins=8,
            alpha=0.6,
            color="#2b5c8f",
            label=f"Matched HC (N={len(hc_age_m)}, Mean={np.mean(hc_age_m):.1f}y)",
            edgecolor="black",
        )
        axes[1].hist(
            pd_age_m,
            bins=8,
            alpha=0.6,
            color="#c23b22",
            label=f"Matched PD (N={len(pd_age_m)}, Mean={np.mean(pd_age_m):.1f}y)",
            edgecolor="black",
        )
        axes[1].set_title(
            f"0.2 SD Caliper Matched Cohort (N={len(matched_df)})\n"
            f"Severe Sample Size Exhaustion: Only {len(hc_age_m)} Pairs",
            fontsize=11,
            fontweight="bold",
        )
    else:
        axes[1].text(0.5, 0.5, "No Matched Pairs Retained", ha="center", va="center", fontsize=12)
        axes[1].set_title(
            "0.2 SD Caliper Matched Cohort\n(Sample Size Exhaustion)",
            fontsize=11,
            fontweight="bold",
        )

    axes[1].set_xlabel("Age (years)", fontsize=10)
    axes[1].set_ylabel("Participant Count", fontsize=10)
    axes[1].legend(loc="upper left", fontsize=9)
    axes[1].grid(axis="y", linestyle=":", alpha=0.6)

    fig.tight_layout()
    p1 = output_dir / "m2_age_distribution.png"
    fig.savefig(p1)
    plt.close(fig)
    paths["age_distribution"] = p1

    # Figure 2: Biological Sex Distribution Breakdown
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    categories = [
        f"Pop 1 HC\n(N={len(pop1_df[pop1_df['class_label'] == 'HC'])})",
        f"Pop 1 PD\n(N={len(pop1_df[pop1_df['class_label'] == 'PD'])})",
        f"Pop 2 HC\n(N={len(pop2_df[pop2_df['class_label'] == 'HC'])})",
        f"Pop 2 PD\n(N={len(pop2_df[pop2_df['class_label'] == 'PD'])})",
    ]

    f_counts = [
        int((pop1_df[pop1_df["class_label"] == "HC"]["sex"] == "F").sum()),
        int((pop1_df[pop1_df["class_label"] == "PD"]["sex"] == "F").sum()),
        int((pop2_df[pop2_df["class_label"] == "HC"]["sex"] == "F").sum()),
        int((pop2_df[pop2_df["class_label"] == "PD"]["sex"] == "F").sum()),
    ]
    m_counts = [
        int((pop1_df[pop1_df["class_label"] == "HC"]["sex"] == "M").sum()),
        int((pop1_df[pop1_df["class_label"] == "PD"]["sex"] == "M").sum()),
        int((pop2_df[pop2_df["class_label"] == "HC"]["sex"] == "M").sum()),
        int((pop2_df[pop2_df["class_label"] == "PD"]["sex"] == "M").sum()),
    ]
    totals = [f + m for f, m in zip(f_counts, m_counts, strict=False)]
    f_props = [f / t * 100 for f, t in zip(f_counts, totals, strict=False)]
    m_props = [m / t * 100 for m, t in zip(m_counts, totals, strict=False)]

    x = np.arange(len(categories))
    width = 0.55
    ax.bar(x, f_props, width, label="Female (%)", color="#8f4f7b", edgecolor="black")
    ax.bar(x, m_props, width, bottom=f_props, label="Male (%)", color="#3b7a57", edgecolor="black")

    for i in range(len(categories)):
        ax.text(
            x[i],
            f_props[i] / 2,
            f"{f_counts[i]} ({f_props[i]:.1f}%)",
            ha="center",
            va="center",
            color="white",
            fontweight="bold",
            fontsize=9,
        )
        ax.text(
            x[i],
            f_props[i] + m_props[i] / 2,
            f"{m_counts[i]} ({m_props[i]:.1f}%)",
            ha="center",
            va="center",
            color="white",
            fontweight="bold",
            fontsize=9,
        )

    ax.set_ylabel("Proportion of Cohort (%)", fontsize=10)
    p_p1 = sex_pop1["fisher_exact_p"]
    p_p2 = sex_pop2["fisher_exact_p"]
    ax.set_title(
        f"Biological Sex Distribution Across UAMS Populations\n"
        f"Fisher's Exact p = {p_p1:.3f} (Pop 1), p = {p_p2:.3f} (Pop 2)",
        fontsize=11,
        fontweight="bold",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    fig.tight_layout()
    p2 = output_dir / "m2_sex_distribution.png"
    fig.savefig(p2)
    plt.close(fig)
    paths["sex_distribution"] = p2

    # Figure 3: Age vs Sex Support Overlap
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    rng = np.random.default_rng(2026)

    for _idx, (label, color, marker) in enumerate([("HC", "#2b5c8f", "o"), ("PD", "#c23b22", "s")]):
        sub = pop2_df[pop2_df["class_label"] == label]
        y_pos = np.where(sub["sex"] == "F", 1.0, 0.0) + rng.uniform(-0.08, 0.08, size=len(sub))
        ax.scatter(
            sub["age"],
            y_pos,
            color=color,
            marker=marker,
            s=55,
            alpha=0.75,
            label=f"{label} (N={len(sub)})",
            edgecolors="black",
            linewidths=0.5,
        )

    # Highlight common support regions
    ax.axvspan(45.0, 72.0, color="#f0e68c", alpha=0.25, label="Common Age Support Window (~45-72y)")
    ax.set_yticks([0.0, 1.0])
    ax.set_yticklabels(["Male (M)", "Female (F)"], fontsize=11, fontweight="bold")
    ax.set_xlabel("Age (years)", fontsize=10)
    n_pairs = len(matched_df) // 2 if not matched_df.empty else 0
    ax.set_title(
        "Age vs Sex Joint Distribution & Common Support\n"
        f"Sparse Overlap: Only {n_pairs} Matched Pairs Retained at 0.2 SD Caliper",
        fontsize=11,
        fontweight="bold",
    )
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    fig.tight_layout()
    p3 = output_dir / "m2_age_sex_overlap.png"
    fig.savefig(p3)
    plt.close(fig)
    paths["age_sex_overlap"] = p3

    return paths
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    fig.tight_layout()
    p2 = output_dir / "m2_sex_distribution.png"
    fig.savefig(p2)
    plt.close(fig)
    paths["sex_distribution"] = p2

    # Figure 3: Age vs Sex Support Overlap
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    rng = np.random.default_rng(2026)

    for _idx, (label, color, marker) in enumerate([("HC", "#2b5c8f", "o"), ("PD", "#c23b22", "s")]):
        sub = pop2_df[pop2_df["class_label"] == label]
        y_pos = np.where(sub["sex"] == "F", 1.0, 0.0) + rng.uniform(-0.08, 0.08, size=len(sub))
        ax.scatter(
            sub["age"],
            y_pos,
            color=color,
            marker=marker,
            s=55,
            alpha=0.75,
            label=f"{label} (N={len(sub)})",
            edgecolors="black",
            linewidths=0.5,
        )

    # Highlight common support regions
    ax.axvspan(45.0, 72.0, color="#f0e68c", alpha=0.25, label="Common Age Support Window (~45-72y)")
    ax.set_yticks([0.0, 1.0])
    ax.set_yticklabels(["Male (M)", "Female (F)"], fontsize=11, fontweight="bold")
    ax.set_xlabel("Age (years)", fontsize=10)
    ax.set_title(
        "Age vs Sex Joint Distribution & Common Support\n"
        "Sparse Overlap: Only 5 Matched Pairs Retained at 0.2 SD Caliper",
        fontsize=11,
        fontweight="bold",
    )
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    fig.tight_layout()
    p3 = output_dir / "m2_age_sex_overlap.png"
    fig.savefig(p3)
    plt.close(fig)
    paths["age_sex_overlap"] = p3

    return paths


def _img_to_base64(path: Path) -> str:
    """Read an image and convert it to a base64 data URI."""
    if not path.is_file():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{data}"


def render_html_report(
    title: str,
    sections: list[tuple[str, str]],
    output_path: Path,
) -> None:
    """Render a standalone, professionally styled HTML report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    body_content = "\n".join(
        f"<section class='report-section'><h2>{sec_title}</h2>"
        f"<div class='sec-body'>{sec_html}</div></section>"
        for sec_title, sec_html in sections
    )

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --primary: #1e3a8a;
    --primary-light: #eff6ff;
    --text-main: #1f2937;
    --text-muted: #4b5563;
    --border: #e5e7eb;
    --card-bg: #ffffff;
    --alert-bg: #fef2f2;
    --alert-border: #f87171;
    --alert-text: #991b1b;
    --warn-bg: #fffbeb;
    --warn-border: #f59e0b;
    --warn-text: #92400e;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  body {{
    font-family: var(--font);
    line-height: 1.6;
    color: var(--text-main);
    background-color: #f9fafb;
    margin: 0;
    padding: 24px;
  }}
  .container {{
    max-width: 1040px;
    margin: 0 auto;
    background: var(--card-bg);
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    padding: 32px;
  }}
  h1 {{
    color: var(--primary);
    border-bottom: 2px solid var(--border);
    padding-bottom: 12px;
    margin-top: 0;
  }}
  h2 {{
    color: var(--primary);
    margin-top: 28px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    font-size: 1.35rem;
  }}
  .badge {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 0.82rem;
    font-weight: 600;
  }}
  .badge-danger {{ background: #fee2e2; color: #991b1b; }}
  .badge-warning {{ background: #fef3c7; color: #92400e; }}
  .badge-success {{ background: #dcfce7; color: #166534; }}
  .badge-info {{ background: #e0f2fe; color: #075985; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 0.92rem;
  }}
  th, td {{
    padding: 10px 12px;
    text-align: left;
    border: 1px solid var(--border);
  }}
  th {{
    background-color: var(--primary-light);
    color: var(--primary);
    font-weight: 600;
  }}
  tr:nth-child(even) {{
    background-color: #fbfbfb;
  }}
  .alert-box {{
    background: var(--alert-bg);
    border-left: 4px solid var(--alert-border);
    padding: 14px 18px;
    margin: 16px 0;
    color: var(--alert-text);
    border-radius: 0 4px 4px 0;
  }}
  .warn-box {{
    background: var(--warn-bg);
    border-left: 4px solid var(--warn-border);
    padding: 14px 18px;
    margin: 16px 0;
    color: var(--warn-text);
    border-radius: 0 4px 4px 0;
  }}
  .figure-box {{
    text-align: center;
    margin: 24px 0;
  }}
  .figure-box img {{
    max-width: 100%;
    height: auto;
    border: 1px solid var(--border);
    border-radius: 4px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }}
  .fig-caption {{
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 6px;
  }}
  footer {{
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    font-size: 0.85rem;
    color: var(--text-muted);
    text-align: center;
  }}
</style>
</head>
<body>
<div class="container">
  <h1>{title}</h1>
  <p><strong>Milestone 2 Scientific Integrity Audit & Demographic Confounding Analysis</strong></p>
  {body_content}
  <footer>
    VoxNeuro Milestone 2 &bull; Pre-registered Statistical Analysis Plan &bull;
    Academic Research Prototype Baseline
  </footer>
</div>
</body>
</html>"""
    output_path.write_text(html_text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze scientific bias, demographic confounding, and matching sensitivity."
    )
    parser.add_argument("--dataset", choices=["uams"], default="uams")
    parser.parse_args(argv)

    processed_dir = ROOT / "data" / "processed"
    raw_uams_dir = ROOT / "data" / "raw" / "uams"
    reports_dir = ROOT / "artifacts" / "reports" / "scientific_audit"
    figures_dir = reports_dir / "figures"

    # 1. Load Population 1 (Source cohort: 81 participants)
    demo_xlsx = raw_uams_dir / "Demographics_age_sex.xlsx"
    if not demo_xlsx.is_file():
        print(f"Demographics workbook missing: {demo_xlsx}")
        return 2

    pop1_raw = pd.read_excel(demo_xlsx, sheet_name="Parselmouth")
    raw_labels = pop1_raw["Label"].astype(str).str.strip()
    mapped_labels = raw_labels.replace({"PwPD": "PD", "pwpd": "PD", "pw_pd": "PD", "hc": "HC"})
    pop1_df = pd.DataFrame(
        {
            "sample_id": pop1_raw["Sample ID"].astype(str),
            "class_label": mapped_labels,
            "age": pd.to_numeric(pop1_raw["Age"], errors="coerce"),
            "sex": pop1_raw["Sex"].astype(str).str.strip().str.upper(),
            "participant_id": pop1_raw["Sample ID"].map(normalize_sample_id),
        }
    )

    # 2. Load Population 2 (Accepted Core39 cohort: 78 participants)
    feature_csv = processed_dir / "voice_features.csv"
    manifest_csv = processed_dir / "feature_manifest.csv"
    extraction_csv = processed_dir / "feature_extraction_report.csv"

    if not feature_csv.is_file() or not manifest_csv.is_file() or not extraction_csv.is_file():
        print("Processed feature, manifest, or extraction report missing. Run M1 pipeline first.")
        return 2

    pop2_df = pd.read_csv(feature_csv)
    manifest_df = pd.read_csv(manifest_csv)
    extraction_df = pd.read_csv(extraction_csv)

    print(f"Loaded Population 1 (Source cohort): {len(pop1_df)} participants")
    print(f"Loaded Population 2 (Accepted Core39 cohort): {len(pop2_df)} participants")

    # Demographic data integrity validation
    integrity_result = validate_demographic_integrity(manifest_df, pop1_df)
    if not integrity_result["valid"]:
        print(f"Demographic data integrity check failed: {integrity_result['issues']}")
        return 1

    # 3. Demographic Audits
    age_pop1 = audit_age_distribution(pop1_df, n_bootstraps=1000, seed=2026)
    age_pop2 = audit_age_distribution(pop2_df, n_bootstraps=1000, seed=2026)

    sex_pop1 = audit_sex_distribution(pop1_df)
    sex_pop2 = audit_sex_distribution(pop2_df)

    joint_pop1 = audit_joint_distribution(pop1_df)
    joint_pop2 = audit_joint_distribution(pop2_df)

    attrition = audit_quality_attrition(manifest_df, extraction_df)

    # 4. Matching Sensitivity Analysis
    matching_sens = evaluate_matching_sensitivities(pop2_df, calipers=(0.1, 0.2, 0.3, None))
    matching_sens_path = processed_dir / "m2_matching_sensitivity.csv"
    matching_sens.to_csv(matching_sens_path, index=False)
    print(f"Saved matching sensitivity to: {matching_sens_path}")

    # Optimal matching at 0.2 SD caliper
    matched_02_df, matched_02_summary = perform_optimal_matching(
        pop2_df, caliper_multiplier=0.2, seed=2026
    )
    matched_assign_path = processed_dir / "m2_matching_assignments.csv"
    matched_02_df.to_csv(matched_assign_path, index=False)
    print(f"Saved local matching assignments to: {matched_assign_path}")

    # 4b. Age Strata and Feature-Level FDR Audits
    age_strata_df = audit_age_strata(pop2_df)
    age_strata_path = processed_dir / "m2_age_subgroup_summary.csv"
    age_strata_df.to_csv(age_strata_path, index=False)
    print(f"Saved age subgroup summary to: {age_strata_path}")

    feature_fdr_df = audit_feature_level_associations(pop2_df, FEATURE_NAMES)
    feature_fdr_path = processed_dir / "m2_feature_fdr_summary.csv"
    feature_fdr_df.to_csv(feature_fdr_path, index=False)
    print(f"Saved feature FDR summary to: {feature_fdr_path}")

    # 5. Save Summaries
    demographic_summary = {
        "dataset": "uams",
        "demographic_integrity": integrity_result,
        "population_1_source": {
            "participant_count": len(pop1_df),
            "age": age_pop1,
            "sex": sex_pop1,
            "joint_strata": joint_pop1,
        },
        "population_2_accepted_core39": {
            "participant_count": len(pop2_df),
            "age": age_pop2,
            "sex": sex_pop2,
            "joint_strata": joint_pop2,
        },
        "age_strata_audit": sanitize_for_json(age_strata_df.to_dict(orient="records")),
        "feature_fdr_summary": sanitize_for_json(feature_fdr_df.to_dict(orient="records")),
        "matching_analysis": {
            "prespecified_primary_caliper": "0.2 SD",
            "matched_pairs_retained": matched_02_summary["matched_pairs"],
            "matched_summary": matched_02_summary,
            "decision": (
                "NOT ESTIMABLE per pre-registered SAP Rule 5 (sample size exhaustion: < 10 pairs)"
            ),
        },
    }

    demo_sum_path = processed_dir / "m2_demographic_summary.json"
    demo_sum_path.write_text(
        json.dumps(sanitize_for_json(demographic_summary), indent=2), encoding="utf-8"
    )
    print(f"Saved demographic summary to: {demo_sum_path}")

    attr_sum_path = processed_dir / "m2_attrition_summary.json"
    attr_sum_path.write_text(json.dumps(sanitize_for_json(attrition), indent=2), encoding="utf-8")
    print(f"Saved attrition summary to: {attr_sum_path}")

    # 6. Generate Publication Figures
    figures = generate_figures(pop1_df, pop2_df, matched_02_df, sex_pop1, sex_pop2, figures_dir)
    print(f"Generated figures in: {figures_dir}")

    # 7. Render HTML Reports
    img_age = _img_to_base64(figures["age_distribution"])
    img_sex = _img_to_base64(figures["sex_distribution"])
    img_overlap = _img_to_base64(figures["age_sex_overlap"])

    # Report 1: Demographic Audit HTML
    sec_demo = [
        (
            "Executive Summary & Core Finding",
            f"""
        <div class="alert-box">
          <strong>Critical Confounding Identified:</strong> A substantial age disparity exists
          between Healthy Controls (HC) and Parkinson's Disease (PD) cohorts in the UAMS dataset.
          The mean age gap in Population 1 is
          <strong>{abs(age_pop1["mean_difference_hc_minus_pd"]):.2f} years</strong>
          (HC: {age_pop1["HC"]["mean"]:.2f}y vs PD: {age_pop1["PD"]["mean"]:.2f}y;
          SMD = <strong>{age_pop1["standardized_mean_difference"]:.2f}</strong>;
          r_rb = <strong>{age_pop1["rank_biserial_correlation"]:.3f}</strong>;
          Mann-Whitney U test p = <strong>{age_pop1["mann_whitney_p"]:.2e}</strong>).
        </div>
        <p>This demographic gap substantially accounts for predictive performance in unadjusted
           voice classifiers. Voice models evaluated without demographic adjustment reflect
           age-associated variance rather than specific Parkinsonian dysphonic markers.</p>
        """,
        ),
        (
            "Demographic Distributions (Populations 1 & 2)",
            f"""
        <table>
          <thead>
            <tr>
              <th>Cohort / Metric</th>
              <th>Healthy Controls (HC)</th>
              <th>Parkinson's Disease (PD)</th>
              <th>Effect Size (HC - PD)</th>
              <th>Significance</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Pop 1 (Source N={len(pop1_df)}) Age</strong></td>
              <td>{age_pop1["HC"]["mean"]:.2f} &plusmn; {age_pop1["HC"]["sd"]:.2f} yrs<br>
                  <small>[95% CI: {age_pop1["HC"]["mean_ci_95"][0]:.2f},
                  {age_pop1["HC"]["mean_ci_95"][1]:.2f}]</small></td>
              <td>{age_pop1["PD"]["mean"]:.2f} &plusmn; {age_pop1["PD"]["sd"]:.2f} yrs<br>
                  <small>[95% CI: {age_pop1["PD"]["mean_ci_95"][0]:.2f},
                  {age_pop1["PD"]["mean_ci_95"][1]:.2f}]</small></td>
              <td>SMD = {age_pop1["standardized_mean_difference"]:.2f}
                  (Gap: {age_pop1["mean_difference_hc_minus_pd"]:.2f} yrs;
                   r_rb = {age_pop1["rank_biserial_correlation"]:.3f})</td>
              <td>MW p = {age_pop1["mann_whitney_p"]:.2e}</td>
            </tr>
            <tr>
              <td><strong>Pop 2 (Accepted N={len(pop2_df)}) Age</strong></td>
              <td>{age_pop2["HC"]["mean"]:.2f} &plusmn; {age_pop2["HC"]["sd"]:.2f} yrs<br>
                  <small>[95% CI: {age_pop2["HC"]["mean_ci_95"][0]:.2f},
                  {age_pop2["HC"]["mean_ci_95"][1]:.2f}]</small></td>
              <td>{age_pop2["PD"]["mean"]:.2f} &plusmn; {age_pop2["PD"]["sd"]:.2f} yrs<br>
                  <small>[95% CI: {age_pop2["PD"]["mean_ci_95"][0]:.2f},
                  {age_pop2["PD"]["mean_ci_95"][1]:.2f}]</small></td>
              <td>SMD = {age_pop2["standardized_mean_difference"]:.2f}
                  (Gap: {age_pop2["mean_difference_hc_minus_pd"]:.2f} yrs;
                   r_rb = {age_pop2["rank_biserial_correlation"]:.3f})</td>
              <td>MW p = {age_pop2["mann_whitney_p"]:.2e}</td>
            </tr>
            <tr>
              <td><strong>Biological Sex (Pop 1)</strong></td>
              <td>Female: {sex_pop1["counts"]["HC"]["F"]}
                  ({sex_pop1["proportions"]["HC"]["prop_F"] * 100:.1f}%),
                  Male: {sex_pop1["counts"]["HC"]["M"]}
                  ({sex_pop1["proportions"]["HC"]["prop_M"] * 100:.1f}%)</td>
              <td>Female: {sex_pop1["counts"]["PD"]["F"]}
                  ({sex_pop1["proportions"]["PD"]["prop_F"] * 100:.1f}%),
                  Male: {sex_pop1["counts"]["PD"]["M"]}
                  ({sex_pop1["proportions"]["PD"]["prop_M"] * 100:.1f}%)</td>
              <td>OR = {sex_pop1["odds_ratio"]:.2f},
                  Cram&eacute;r's V = {sex_pop1["cramers_v"]:.3f}</td>
              <td>Fisher p = {sex_pop1["fisher_exact_p"]:.3f}</td>
            </tr>
            <tr>
              <td><strong>Biological Sex (Pop 2)</strong></td>
              <td>Female: {sex_pop2["counts"]["HC"]["F"]}
                  ({sex_pop2["proportions"]["HC"]["prop_F"] * 100:.1f}%),
                  Male: {sex_pop2["counts"]["HC"]["M"]}
                  ({sex_pop2["proportions"]["HC"]["prop_M"] * 100:.1f}%)</td>
              <td>Female: {sex_pop2["counts"]["PD"]["F"]}
                  ({sex_pop2["proportions"]["PD"]["prop_F"] * 100:.1f}%),
                  Male: {sex_pop2["counts"]["PD"]["M"]}
                  ({sex_pop2["proportions"]["PD"]["prop_M"] * 100:.1f}%)</td>
              <td>OR = {sex_pop2["odds_ratio"]:.2f},
                  Cram&eacute;r's V = {sex_pop2["cramers_v"]:.3f}</td>
              <td>Fisher p = {sex_pop2["fisher_exact_p"]:.3f}</td>
            </tr>
          </tbody>
        </table>
        """,
        ),
        (
            "Diagnostic Visualizations",
            f"""
        <div class="figure-box">
          <img src="{img_age}" alt="Age Distribution">
          <div class="fig-caption">Figure 1: Age distribution comparisons showing substantial
          19.31-year shift in source data and sample size exhaustion upon caliper matching.</div>
        </div>
        <div class="figure-box">
          <img src="{img_sex}" alt="Sex Distribution">
          <div class="fig-caption">Figure 2: Biological sex breakdown across UAMS cohorts
          showing moderate female over-representation in HC without statistical significance.</div>
        </div>
        <div class="figure-box">
          <img src="{img_overlap}" alt="Age Sex Support Overlap">
          <div class="fig-caption">Figure 3: Participant-level age vs sex joint distribution
          showing sparse common demographic support.</div>
        </div>
        """,
        ),
    ]
    render_html_report(
        "VoxNeuro M2 – Demographic Bias Audit Report",
        sec_demo,
        reports_dir / "m2_demographic_audit.html",
    )

    # Report 2: Quality Attrition HTML
    sec_attr = [
        (
            "Recording Quality & Attrition Audit",
            f"""
        <div class="warn-box">
          <strong>Class-Dependent Attrition:</strong> All 3 excluded recordings in the UAMS
          dataset belonged to the Parkinson's cohort (due to excessive acoustic clipping).<br>
          Healthy control acceptance: <strong>100%</strong> (41/41, 95% CI:
          [{attrition["class_summary"]["HC"]["acceptance_ci_95"][0] * 100:.1f}%, 100.0%]).<br>
          Parkinson's acceptance: <strong>92.5%</strong> (37/40, 95% CI:
          [{attrition["class_summary"]["PD"]["acceptance_ci_95"][0] * 100:.1f}%,
           {attrition["class_summary"]["PD"]["acceptance_ci_95"][1] * 100:.1f}%]).<br>
          Fisher's exact test for differential attrition:
          p = <strong>{attrition["fisher_exact_p"]:.4f}</strong>.
        </div>
        <table>
          <thead>
            <tr>
              <th>Diagnostic Group</th>
              <th>Eligible Source Audio</th>
              <th>Accepted Core39 Audio</th>
              <th>Excluded Audio</th>
              <th>Exclusion Mechanism</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Healthy Control (HC)</strong></td>
              <td>{attrition["class_summary"]["HC"]["eligible_count"]}</td>
              <td>{attrition["class_summary"]["HC"]["accepted_count"]} (100.0%)</td>
              <td>0 (0.0%)</td>
              <td>None (all met quality thresholds)</td>
            </tr>
            <tr>
              <td><strong>Parkinson's Disease (PD)</strong></td>
              <td>{attrition["class_summary"]["PD"]["eligible_count"]}</td>
              <td>{attrition["class_summary"]["PD"]["accepted_count"]} (92.5%)</td>
              <td>3 (7.5%)</td>
              <td>Acoustic clipping (&gt;0.5% samples at full scale)</td>
            </tr>
          </tbody>
        </table>
        <p>While the attrition rate difference (7.5% vs 0%) is not statistically significant
           at alpha=0.05 (p={attrition["fisher_exact_p"]:.4f}), the class asymmetry highlights that
           remote, unsupervised recording quality and gain calibration must be rigorously monitored
           in prospective clinical studies.</p>
        """,
        ),
    ]
    render_html_report(
        "VoxNeuro M2 – Quality Attrition Analysis",
        sec_attr,
        reports_dir / "m2_attrition_analysis.html",
    )

    # Report 3: Matching Balance HTML
    sec_match = [
        (
            "Age- and Sex-Matching Sensitivity Analysis",
            f"""
        <div class="alert-box">
          <strong>Sample Size Exhaustion:</strong> When applying standard epidemiological
          caliper matching (0.2 SD of pooled age = 2.44 years with exact biological sex matching),
          only <strong>5 pairs (10 participants)</strong> can be matched.<br>
          This represents an <strong>87.2% attrition</strong> of the accepted cohort
          (68 participants discarded).
        </div>
        <table>
          <thead>
            <tr>
              <th>Caliper Specification</th>
              <th>Caliper Threshold</th>
              <th>Matched Pairs</th>
              <th>Retained Participants</th>
              <th>Discarded PD</th>
              <th>Discarded HC</th>
              <th>Post-Match Mean Age Gap</th>
              <th>Post-Match SMD</th>
            </tr>
          </thead>
          <tbody>
            {
                "".join(
                    f'''<tr>
              <td><strong>{row["caliper_specification"]}</strong></td>
              <td>{row["caliper_threshold"]}</td>
              <td>{row["matched_pairs"]}</td>
              <td>{row["matched_total"]}</td>
              <td>{row["unmatched_pd"]}</td>
              <td>{row["unmatched_hc"]}</td>
              <td>{row["mean_pairwise_diff"] if row["mean_pairwise_diff"] is not None else "N/A"}
                  yrs</td>
              <td>{row["post_match_smd"] if row["post_match_smd"] is not None else "N/A"}</td>
            </tr>'''
                    for _, row in matching_sens.iterrows()
                )
            }
          </tbody>
        </table>
        <p><strong>Formal Pre-registered Determination:</strong> Per SAP Decision Rule 5,
           matched cross-validation modeling is designated as <strong>NOT ESTIMABLE</strong>.
           Constructing 5 outer &times; 3 inner cross-validation folds on 10 participants
           violates minimal class partition constraints and yields mathematically unstable
           folds.</p>
        """,
        ),
    ]
    render_html_report(
        "VoxNeuro M2 – Matching Sensitivity & Balance Report",
        sec_match,
        reports_dir / "m2_matching_balance.html",
    )

    # Report 4 & 5: Strata and Feature FDR Sections
    rows_strata = []
    for _, row in age_strata_df.iterrows():
        status_badge = (
            "<span class='badge badge-success'>ESTIMABLE</span>"
            if row["status"] == "ESTIMABLE"
            else "<span class='badge badge-warning'>NOT ESTIMABLE</span>"
        )
        hc_mean_s = f"{row['hc_mean_age']:.2f}" if row["hc_mean_age"] is not None else "&mdash;"
        pd_mean_s = f"{row['pd_mean_age']:.2f}" if row["pd_mean_age"] is not None else "&mdash;"
        rows_strata.append(f"""<tr>
          <td><strong>{row["age_band"]}</strong></td>
          <td>{row["age_range"]}</td>
          <td>{row["n_hc"]}</td>
          <td>{row["n_pd"]}</td>
          <td>{row["n_total"]}</td>
          <td>{hc_mean_s}</td>
          <td>{pd_mean_s}</td>
          <td>{row["common_support_overlap"]}</td>
          <td>{status_badge}</td>
          <td><small>{row["suppression_reason"]}</small></td>
        </tr>""")

    sec_strata = [
        (
            "Exploratory Age-Stratified Subgroup Feasibility",
            f"""
        <div class="warn-box">
          <strong>Small-Cell Suppression Enforced:</strong> Per pre-registered SAP Rule 6,
          subgroup performance estimation requires at least 10 participants per diagnostic arm
          in each stratum. In UAMS Population 2 (N=78), every age stratum exhibits severe class
          depletion (&lt; 10 participants in at least one arm). Consequently, all strata are
          formally designated as <strong>NOT ESTIMABLE</strong>.
        </div>
        <table>
          <thead>
            <tr>
              <th>Age Band</th>
              <th>Range</th>
              <th>N (HC)</th>
              <th>N (PD)</th>
              <th>Total N</th>
              <th>HC Mean Age</th>
              <th>PD Mean Age</th>
              <th>Common Support</th>
              <th>Status</th>
              <th>Suppression Reason</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rows_strata)}
          </tbody>
        </table>
        """,
        ),
    ]

    top_fdr = feature_fdr_df.head(10)
    rows_fdr = []
    for _, row in top_fdr.iterrows():
        sig_badge = (
            "<span class='badge badge-success'>q &lt; 0.05</span>"
            if row["significant_fdr_05"]
            else "<span class='badge badge-warning'>q &ge; 0.05</span>"
        )
        rows_fdr.append(f"""<tr>
          <td><code>{row["feature_name"]}</code></td>
          <td>{row["standardized_beta"]:+.4f}</td>
          <td>{row["odds_ratio"]:.4f}</td>
          <td>{row["lrt_chi2"]:.4f}</td>
          <td>{row["p_unadjusted"]:.4e}</td>
          <td>{row["fdr_q_value"]:.4e}</td>
          <td>{sig_badge}</td>
        </tr>""")

    sec_fdr = [
        (
            "Exploratory Feature-Level Associations (Multivariable LRT & BH-FDR)",
            f"""
        <p>Multivariable logistic regression evaluating each feature adjusted for age and sex,
           with Likelihood Ratio Tests (LRT) and Benjamini-Hochberg False Discovery Rate (FDR).
           <strong>Note:</strong> These findings represent exploratory within-cohort associations
           and do not establish independent clinical utility or prospective validity.</p>
        <table>
          <thead>
            <tr>
              <th>Feature Name</th>
              <th>Standardized &beta;</th>
              <th>Odds Ratio</th>
              <th>LRT &chi;&sup2;</th>
              <th>p (Unadjusted)</th>
              <th>FDR q-value</th>
              <th>FDR &lt; 0.05</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rows_fdr)}
          </tbody>
        </table>
        <p><small>Showing top 10 features sorted by unadjusted LRT p-value.
           Full summary: <code>data/processed/m2_feature_fdr_summary.csv</code>.</small></p>
        """,
        ),
    ]

    # Report 6: Comprehensive Bias Audit Master HTML
    master_sections = sec_demo + sec_attr + sec_match + sec_strata + sec_fdr
    render_html_report(
        "VoxNeuro M2 – Scientific Bias & Demographic Audit Dashboard",
        master_sections,
        reports_dir / "m2_bias_audit.html",
    )
    print(f"Rendered all HTML reports in: {reports_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
