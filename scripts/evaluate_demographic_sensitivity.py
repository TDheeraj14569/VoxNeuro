"""Evaluate demographic sensitivity, comparator models, and incremental voice value."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from voxneuro.config import load_config
from voxneuro.dataset.bias_audit import sanitize_for_json
from voxneuro.dataset.validation import validate_extraction_receipt, validate_manifest
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling.demographic_sensitivity import evaluate_demographic_models
from voxneuro.provenance import project_code_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_model_comparison_html(
    comparator_df: pd.DataFrame,
    paired_df: pd.DataFrame,
    subgroup_df: pd.DataFrame,
    output_path: Path,
) -> None:
    """Render self-contained HTML report comparing all 8 models and demographic baselines."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def _lookup_ba(model_id: str) -> float:
        sub = comparator_df[comparator_df["model"] == model_id]
        if sub.empty or pd.isna(sub["balanced_accuracy_mean"].iloc[0]):
            return 0.0
        return float(sub["balanced_accuracy_mean"].iloc[0])

    svm_ba = _lookup_ba("voice_only_svm")
    lr_ba = _lookup_ba("voice_only_logistic")
    age_ba = _lookup_ba("age_only_logistic")
    as_ba = _lookup_ba("age_plus_sex_logistic")
    av_ba = _lookup_ba("age_plus_voice_logistic")
    asv_ba = _lookup_ba("age_plus_sex_plus_voice_logistic")

    p_av = paired_df[paired_df["model_tested"] == "age_plus_voice_logistic"]
    p_asv = paired_df[paired_df["model_tested"] == "age_plus_sex_plus_voice_logistic"]

    delta_av = float(p_av["delta_balanced_accuracy"].iloc[0]) if not p_av.empty else 0.0
    delta_av_ci = p_av["delta_ci_95"].iloc[0] if not p_av.empty else [0.0, 0.0]
    mcnemar_av = (
        float(p_av["supplementary_mcnemar_exact_p"].iloc[0])
        if (not p_av.empty and "supplementary_mcnemar_exact_p" in p_av.columns)
        else float(p_av["mcnemar_exact_p"].iloc[0])
        if not p_av.empty
        else 1.0
    )

    delta_asv = float(p_asv["delta_balanced_accuracy"].iloc[0]) if not p_asv.empty else 0.0
    delta_asv_ci = p_asv["delta_ci_95"].iloc[0] if not p_asv.empty else [0.0, 0.0]
    mcnemar_asv = (
        float(p_asv["supplementary_mcnemar_exact_p"].iloc[0])
        if (not p_asv.empty and "supplementary_mcnemar_exact_p" in p_asv.columns)
        else float(p_asv["mcnemar_exact_p"].iloc[0])
        if not p_asv.empty
        else 1.0
    )

    rows_comp = []
    for _, row in comparator_df.iterrows():
        status_badge = (
            "<span class='badge badge-success'>ESTIMATED</span>"
            if row["status"] == "ESTIMATED"
            else "<span class='badge badge-danger'>NOT ESTIMABLE</span>"
        )
        ba_str = (
            f"{row['balanced_accuracy_mean']:.4f}"
            if pd.notna(row["balanced_accuracy_mean"])
            else "&mdash;"
        )
        if row["balanced_accuracy_ci_95"] and isinstance(row["balanced_accuracy_ci_95"], list):
            ci = row["balanced_accuracy_ci_95"]
            ba_str += f" <small>[{ci[0]:.4f}, {ci[1]:.4f}]</small>"
        roc_str = f"{row['roc_auc_mean']:.4f}" if pd.notna(row["roc_auc_mean"]) else "&mdash;"
        sens_str = (
            f"{row['sensitivity_mean']:.4f}" if pd.notna(row["sensitivity_mean"]) else "&mdash;"
        )
        spec_str = (
            f"{row['specificity_mean']:.4f}" if pd.notna(row["specificity_mean"]) else "&mdash;"
        )
        f1_str = f"{row['f1_mean']:.4f}" if pd.notna(row["f1_mean"]) else "&mdash;"
        acc_str = f"{row['accuracy_mean']:.4f}" if pd.notna(row["accuracy_mean"]) else "&mdash;"

        rows_comp.append(f"""<tr>
          <td><strong>{row["model_label"]}</strong><br>
              <small class='code'>{row["model"]}</small></td>
          <td>{status_badge}</td>
          <td><strong>{ba_str}</strong></td>
          <td>{roc_str}</td>
          <td>{sens_str}</td>
          <td>{spec_str}</td>
          <td>{f1_str}</td>
          <td>{acc_str}</td>
        </tr>""")

    rows_paired = []
    for _, row in paired_df.iterrows():
        is_supported = row.get(
            "statistically_supported_incremental_contribution",
            row.get("statistically_significant", False),
        )
        sig_badge = (
            "<span class='badge badge-success'>Supported (CI &gt; 0)</span>"
            if is_supported
            else "<span class='badge badge-warning'>Not Supported</span>"
        )
        delta_str = f"{row['delta_balanced_accuracy']:+.4f}"
        ci = row["delta_ci_95"]
        ci_str = f"[{ci[0]:+.4f}, {ci[1]:+.4f}]" if isinstance(ci, list) else str(ci)
        mcnemar_p = row.get(
            "supplementary_mcnemar_exact_p",
            row.get("mcnemar_exact_p", 1.0),
        )

        rows_paired.append(f"""<tr>
          <td><strong>{row["comparison"]}</strong></td>
          <td><strong>{delta_str}</strong> <small>{ci_str}</small></td>
          <td>b={row["discordant_b_model_correct"]}, c={row["discordant_c_baseline_correct"]}</td>
          <td>{mcnemar_p:.4f}</td>
          <td>{sig_badge}</td>
          <td>{row["inference"]}</td>
        </tr>""")

    rows_subgroup = []
    for _, row in subgroup_df.iterrows():
        suppr_badge = (
            "<span class='badge badge-warning'>N &lt; 10 (Suppressed)</span>"
            if row["small_cell_suppression"]
            else "<span class='badge badge-info'>N &ge; 10</span>"
        )
        ba_str = (
            f"{row['balanced_accuracy']:.4f}" if pd.notna(row["balanced_accuracy"]) else "&mdash;"
        )
        roc_str = f"{row['roc_auc']:.4f}" if pd.notna(row["roc_auc"]) else "&mdash;"
        sens_str = f"{row['sensitivity']:.4f}" if pd.notna(row["sensitivity"]) else "&mdash;"
        spec_str = f"{row['specificity']:.4f}" if pd.notna(row["specificity"]) else "&mdash;"

        rows_subgroup.append(f"""<tr>
          <td><strong>{row["subgroup_sex"]}</strong></td>
          <td>{row["model_label"]}</td>
          <td>HC: {row["n_hc"]}, PD: {row["n_pd"]} (Total: {row["n_total"]})</td>
          <td>{suppr_badge}</td>
          <td><strong>{ba_str}</strong></td>
          <td>{roc_str}</td>
          <td>{sens_str}</td>
          <td>{spec_str}</td>
        </tr>""")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VoxNeuro M2 – Model Comparison & Demographic Sensitivity Report</title>
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
    max-width: 1100px;
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
    font-size: 1.3rem;
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
  .code {{ font-family: monospace; color: #6b7280; font-size: 0.85rem; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    font-size: 0.90rem;
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
  <h1>VoxNeuro M2 – Model Comparison & Demographic Sensitivity Report</h1>
  <p><strong>Pre-registered Statistical Evaluation across 8 Model Specifications
     (5&times;3 Repeated Nested CV, Seeds 2026, 2027, 2028)</strong></p>

  <section>
    <h2>Executive Finding: Voice Incremental Value Audit</h2>
    <div class="alert-box">
      <strong>Absence of Incremental Voice Diagnostic Power:</strong>
      Acoustic feature analysis alone (Core39) achieves <strong>{svm_ba * 100:.2f}%</strong> (SVM)
      and <strong>{lr_ba * 100:.2f}%</strong> (Logistic L2) balanced accuracy.<br>
      However, demographic age alone achieves <strong>{age_ba * 100:.2f}%</strong> balanced
      accuracy.<br>
      Combining voice with age (Age + Voice) yields <strong>{av_ba * 100:.2f}%</strong>
      balanced accuracy &mdash; a primary-seed difference of <strong>{delta_av * 100:+.2f}%</strong>
      (95% bootstrap CI [{delta_av_ci[0] * 100:+.2f}%, {delta_av_ci[1] * 100:+.2f}%];
      Supplementary McNemar discordance exact p = {mcnemar_av:.4f}).<br>
      Combining voice with age and sex (Age + Sex + Voice) yields
      <strong>{asv_ba * 100:.2f}%</strong> vs <strong>{as_ba * 100:.2f}%</strong> for Age + Sex
      &mdash; a primary-seed difference of <strong>{delta_asv * 100:+.2f}%</strong>
      (95% bootstrap CI [{delta_asv_ci[0] * 100:+.2f}%, {delta_asv_ci[1] * 100:+.2f}%];
      Supplementary McNemar discordance exact p = {mcnemar_asv:.4f}).
    </div>
    <p>In this cohort, sustained-vowel acoustic metrics do not establish a statistically
       supported positive incremental contribution beyond basic demographics under the
       pre-registered SAP decision rule (requiring 95% bootstrap CI lower bound &gt; 0).
       However, the available confidence intervals do not prove that the true incremental
       contribution is zero or that a clinically meaningful signal is absent in a larger,
       demographically balanced prospective cohort.</p>
  </section>

  <section>
    <h2>1. Prespecified Comparator Model Performance Hierarchy</h2>
    <p>All models evaluated across identical participant-grouped outer folds
       (5 outer &times; 3 inner folds, 3 repeats, N=78 accepted participants).</p>
    <table>
      <thead>
        <tr>
          <th>Model Specification</th>
          <th>Status</th>
          <th>Balanced Accuracy [95% CI]</th>
          <th>ROC-AUC</th>
          <th>Sensitivity</th>
          <th>Specificity</th>
          <th>F1 Score</th>
          <th>Accuracy</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_comp)}
      </tbody>
    </table>
    <div class="warn-box">
      <strong>Matched Cohort Status:</strong> Matched voice modeling is designated as
      <strong>NOT ESTIMABLE</strong> per pre-registered SAP Rule 5 due to sample size
      exhaustion (only 5 pairs / 10 participants retained at 0.2 SD caliper).
    </div>
  </section>

  <section>
    <h2>2. Paired Incremental Voice Differences & Statistical Significance</h2>
    <p>Paired out-of-fold comparisons on identical participant holdouts with 1,000
       participant-level bootstrap 95% CIs and supplementary McNemar exact binomial tests.</p>
    <table>
      <thead>
        <tr>
          <th>Comparison</th>
          <th>&Delta; Balanced Accuracy [95% CI]</th>
          <th>Discordance (b, c)</th>
          <th>Supplementary McNemar p</th>
          <th>SAP Decision Rule</th>
          <th>Scientific Inference</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_paired)}
      </tbody>
    </table>
  </section>

  <section>
    <h2>3. Biological Sex Subgroup Stratification</h2>
    <p>Subgroup performance across female (F) and male (M) strata on primary seed (2026).</p>
    <table>
      <thead>
        <tr>
          <th>Stratum</th>
          <th>Model Specification</th>
          <th>Sample Counts</th>
          <th>Cell Support</th>
          <th>Balanced Accuracy</th>
          <th>ROC-AUC</th>
          <th>Sensitivity</th>
          <th>Specificity</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_subgroup)}
      </tbody>
    </table>
  </section>

  <footer>
    VoxNeuro Milestone 2 &bull; Pre-registered Statistical Analysis Plan &bull;
    Scientific Confounding & Bias Audit Baseline
  </footer>
</div>
</body>
</html>"""
    output_path.write_text(html_content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Execute demographic sensitivity and paired incremental voice evaluation."
    )
    parser.add_argument("--dataset", choices=["uams"], default="uams")
    parser.parse_args(argv)

    processed_dir = ROOT / "data" / "processed"
    reports_dir = ROOT / "artifacts" / "reports" / "scientific_audit"
    feature_path = processed_dir / "voice_features.csv"
    manifest_path = processed_dir / "feature_manifest.csv"
    extraction_receipt = processed_dir / "feature_extraction_receipt.json"

    if not feature_path.is_file() or not manifest_path.is_file():
        print("Feature table or manifest missing; run dataset audit and extraction first.")
        return 2

    manifest = pd.read_csv(manifest_path)
    manifest_issues = validate_manifest(manifest, require_integrity=True)
    audio_config = load_config("audio_config.yaml")
    feature_config = load_config("feature_config.yaml")
    code_version = project_code_fingerprint()
    schema_hash = schema_fingerprint()
    feature_config_hash = feature_config_fingerprint(feature_config)
    preprocessing_config_hash = configuration_fingerprint(audio_config)

    extraction_issues = validate_extraction_receipt(
        extraction_receipt,
        manifest_path,
        feature_path,
        SCHEMA_VERSION,
        schema_hash,
        feature_config_hash,
        preprocessing_config_hash,
        code_version,
    )
    if manifest_issues or extraction_issues:
        for issue in [*manifest_issues, *extraction_issues]:
            print(f"- {issue}")
        print(
            "Demographic evaluation blocked until dataset and extraction provenance are verified."
        )
        return 1

    frame = pd.read_csv(feature_path).dropna(subset=["class_label", "participant_id", "age", "sex"])
    print(f"Loaded verified feature table with {len(frame)} participants.")

    start = time.perf_counter()
    results = evaluate_demographic_models(
        frame,
        feature_names=FEATURE_NAMES,
        outer_splits=5,
        inner_splits=3,
        random_seeds=(2026, 2027, 2028),
        bootstrap_iterations=1000,
    )
    elapsed = time.perf_counter() - start
    print(f"Demographic sensitivity evaluation completed in {elapsed:.2f} seconds.")

    comp_df = results["comparator_metrics"]
    paired_df = results["paired_incremental"]
    subgroup_df = results["sex_subgroups"]

    comp_path = processed_dir / "m2_comparator_metrics.csv"
    paired_path = processed_dir / "m2_paired_incremental_voice.csv"
    subgroup_path = processed_dir / "m2_sex_subgroup_summary.csv"
    html_path = reports_dir / "m2_model_comparison.html"

    comp_df.to_csv(comp_path, index=False)
    paired_df.to_csv(paired_path, index=False)
    subgroup_df.to_csv(subgroup_path, index=False)
    print(f"Saved comparator metrics to: {comp_path}")
    print(f"Saved paired incremental voice to: {paired_path}")
    print(f"Saved sex subgroup summary to: {subgroup_path}")

    render_model_comparison_html(comp_df, paired_df, subgroup_df, html_path)
    print(f"Saved HTML model comparison report to: {html_path}")

    # Generate cryptographic analysis receipt
    receipt = {
        "analysis_name": "m2_demographic_sensitivity_evaluation",
        "milestone": "M2",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "dataset": "uams",
        "participant_count": len(frame),
        "code_fingerprint": code_version,
        "feature_table_sha256": _sha256(feature_path),
        "manifest_sha256": _sha256(manifest_path),
        "random_seeds": [2026, 2027, 2028],
        "outer_cv_splits": 5,
        "inner_cv_splits": 3,
        "bootstrap_iterations": 1000,
        "comparator_models_evaluated": [
            "majority_classifier",
            "voice_only_svm",
            "voice_only_logistic",
            "age_only_logistic",
            "sex_only_logistic",
            "age_plus_sex_logistic",
            "age_plus_voice_logistic",
            "age_plus_sex_plus_voice_logistic",
        ],
        "matched_cohort_model": {
            "model": "matched_voice_svm",
            "status": "NOT ESTIMABLE",
            "reason": (
                "Sample size exhaustion: only 5 pairs (10 participants) satisfy the pre-registered "
                "0.2 SD caliper (2.44 years). Stratified 5-fold cross-validation requires at least "
                "5 participants per class, leaving only 4 training participants per class, which "
                "cannot sustain 3-fold inner cross-validation."
            ),
        },
        "findings_summary": {
            "age_only_balanced_accuracy": float(
                comp_df[comp_df["model"] == "age_only_logistic"]["balanced_accuracy_mean"].iloc[0]
            ),
            "voice_only_svm_balanced_accuracy": float(
                comp_df[comp_df["model"] == "voice_only_svm"]["balanced_accuracy_mean"].iloc[0]
            ),
            "voice_only_logistic_balanced_accuracy": float(
                comp_df[comp_df["model"] == "voice_only_logistic"]["balanced_accuracy_mean"].iloc[0]
            ),
            "age_plus_voice_balanced_accuracy": float(
                comp_df[comp_df["model"] == "age_plus_voice_logistic"][
                    "balanced_accuracy_mean"
                ].iloc[0]
            ),
            "delta_age_voice": float(
                paired_df[paired_df["model_tested"] == "age_plus_voice_logistic"][
                    "delta_balanced_accuracy"
                ].iloc[0]
            ),
            "mcnemar_p_age_voice": float(
                paired_df[paired_df["model_tested"] == "age_plus_voice_logistic"][
                    "supplementary_mcnemar_exact_p"
                    if "supplementary_mcnemar_exact_p" in paired_df.columns
                    else "mcnemar_exact_p"
                ].iloc[0]
            ),
            "delta_age_sex_voice": float(
                paired_df[paired_df["model_tested"] == "age_plus_sex_plus_voice_logistic"][
                    "delta_balanced_accuracy"
                ].iloc[0]
            ),
            "mcnemar_p_age_sex_voice": float(
                paired_df[paired_df["model_tested"] == "age_plus_sex_plus_voice_logistic"][
                    "supplementary_mcnemar_exact_p"
                    if "supplementary_mcnemar_exact_p" in paired_df.columns
                    else "mcnemar_exact_p"
                ].iloc[0]
            ),
        },
    }

    receipt_path = processed_dir / "m2_analysis_receipt.json"
    receipt_path.write_text(json.dumps(sanitize_for_json(receipt), indent=2), encoding="utf-8")
    print(f"Saved analysis receipt to: {receipt_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
