"""Unit tests for M2 Report-Data Consistency and Scientific Integrity.

Verifies that all Markdown reports, summary JSON files, and CSV evidence tables
agree on demographic age strata, multivariable feature FDR rankings, Core39 schema
adherence, and prospective protocol specifications.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

import pytest

from voxneuro.features.schema import FEATURE_NAMES


def _find_evidence_path(filename: str) -> Path:
    """Locate an evidence file in data/processed or review_evidence."""
    candidates = [
        Path("data/processed") / filename,
        Path("review_evidence") / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Could not locate evidence file: {filename}")


def _load_age_subgroup_csv() -> list[dict[str, Any]]:
    path = _find_evidence_path("m2_age_subgroup_summary.csv")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append(
                {
                    "age_band": r["age_band"],
                    "age_range": r["age_range"],
                    "n_hc": int(r["n_hc"]),
                    "n_pd": int(r["n_pd"]),
                    "n_total": int(r["n_total"]),
                    "hc_mean_age": float(r["hc_mean_age"]),
                    "pd_mean_age": float(r["pd_mean_age"]),
                    "common_support_overlap": r["common_support_overlap"],
                    "status": r["status"],
                    "suppression_reason": r["suppression_reason"],
                }
            )
        return rows


def _load_demographic_json() -> dict[str, Any]:
    path = _find_evidence_path("m2_demographic_summary.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_feature_fdr_csv() -> list[dict[str, Any]]:
    path = _find_evidence_path("m2_feature_fdr_summary.csv")
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows.append(
                {
                    "feature_name": r["feature_name"],
                    "standardized_beta": float(r["standardized_beta"]),
                    "odds_ratio": float(r["odds_ratio"]),
                    "lrt_chi2": float(r["lrt_chi2"]),
                    "p_unadjusted": float(r["p_unadjusted"]),
                    "fdr_q_value": float(r["fdr_q_value"]),
                    "significant_fdr_05": r["significant_fdr_05"].strip().lower() == "true",
                }
            )
        return rows


def _parse_markdown_age_table(markdown_text: str) -> list[dict[str, Any]]:
    sec_match = re.search(
        r"## 10\. Exploratory Age Strata Subgroup Analysis(.*?)(?=## 11|\Z)",
        markdown_text,
        re.DOTALL,
    )
    assert sec_match, "Section 10 not found in Markdown report"
    sec_text = sec_match.group(1)

    table_rows: list[dict[str, Any]] = []
    for line in sec_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if not parts or parts[0].startswith(":") or "Age Band" in parts[0]:
            continue

        band_clean = parts[0].replace("**", "").strip()
        age_range = parts[1].replace("$", "").strip()
        n_hc = int(parts[2])
        n_pd = int(parts[3])
        n_total = int(parts[4])
        hc_mean = float(parts[5].replace("$", "").strip())
        pd_mean = float(parts[6].replace("$", "").strip())
        common_support = parts[7].replace("$", "").strip()
        status = parts[8].replace("**", "").strip()
        reason = parts[9]

        table_rows.append(
            {
                "age_band": band_clean,
                "age_range": age_range,
                "n_hc": n_hc,
                "n_pd": n_pd,
                "n_total": n_total,
                "hc_mean_age": hc_mean,
                "pd_mean_age": pd_mean,
                "common_support": common_support,
                "status": status,
                "reason": reason,
            }
        )
    return table_rows


def _parse_markdown_fdr_table(markdown_text: str) -> list[dict[str, Any]]:
    sec_match = re.search(
        r"## 11\. Exploratory Feature-Level Multivariable Associations(.*?)(?=## 12|\Z)",
        markdown_text,
        re.DOTALL,
    )
    assert sec_match, "Section 11 not found in Markdown report"
    sec_text = sec_match.group(1)

    table_rows: list[dict[str, Any]] = []
    for line in sec_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if not parts or parts[0].startswith(":") or "Feature Name" in parts[0]:
            continue

        feat_clean = parts[0].replace("`", "").strip()
        beta = float(parts[1].replace("$", "").replace("+", "").strip())
        odds_ratio = float(parts[2].replace("$", "").strip())
        lrt = float(parts[3].replace("$", "").strip())

        p_str = parts[4].replace("$", "").strip()
        if r"\times 10^{" in p_str:
            base, exp = p_str.split(r"\times 10^{")
            exp = exp.replace("}", "").strip()
            p_val = float(base.strip()) * (10 ** float(exp))
        else:
            p_val = float(p_str)

        fdr_q = float(parts[5].replace("$", "").strip())
        sig_str = parts[6].replace("**", "").strip()

        table_rows.append(
            {
                "feature_name": feat_clean,
                "standardized_beta": beta,
                "odds_ratio": odds_ratio,
                "lrt_chi2": lrt,
                "p_unadjusted": p_val,
                "fdr_q_value": fdr_q,
                "significant_display": sig_str,
            }
        )
    return table_rows


class TestM2ReportDataConsistency:
    """Validates full consistency between M2 authoritative evidence and documentation."""

    def test_age_subgroup_csv_agrees_with_json(self) -> None:
        csv_rows = _load_age_subgroup_csv()
        json_data = _load_demographic_json()
        json_rows = json_data.get("age_strata_audit", [])

        assert len(csv_rows) == 4, f"Expected 4 age strata, got {len(csv_rows)}"
        assert len(json_rows) == 4, f"Expected 4 age strata in JSON, got {len(json_rows)}"

        for c_row, j_row in zip(csv_rows, json_rows, strict=True):
            assert c_row["age_band"] == j_row["age_band"]
            assert c_row["n_hc"] == j_row["n_hc"]
            assert c_row["n_pd"] == j_row["n_pd"]
            assert c_row["n_total"] == j_row["n_total"]
            assert pytest.approx(c_row["hc_mean_age"], abs=0.01) == j_row["hc_mean_age"]
            assert pytest.approx(c_row["pd_mean_age"], abs=0.01) == j_row["pd_mean_age"]
            assert c_row["common_support_overlap"] == j_row["common_support_overlap"]
            assert c_row["status"] == "NOT ESTIMABLE"
            assert j_row["status"] == "NOT ESTIMABLE"

        total_hc = sum(r["n_hc"] for r in csv_rows)
        total_pd = sum(r["n_pd"] for r in csv_rows)
        assert total_hc == 41, f"Expected 41 total HC, got {total_hc}"
        assert total_pd == 37, f"Expected 37 total PD in accepted cohort, got {total_pd}"

    def test_markdown_report_age_table_matches_csv_and_json(self) -> None:
        report_path = Path("docs/reports/M2_BIAS_AUDIT_REPORT.md")
        assert report_path.exists(), "M2_BIAS_AUDIT_REPORT.md must exist"
        markdown_text = report_path.read_text(encoding="utf-8")

        md_rows = _parse_markdown_age_table(markdown_text)
        csv_rows = _load_age_subgroup_csv()

        assert len(md_rows) == 4, f"Expected 4 parsed markdown rows, got {len(md_rows)}"

        for idx, (md_row, c_row) in enumerate(zip(md_rows, csv_rows, strict=True)):
            assert md_row["n_hc"] == c_row["n_hc"], (
                f"Stratum {idx} HC mismatch: MD {md_row['n_hc']} vs CSV {c_row['n_hc']}"
            )
            assert md_row["n_pd"] == c_row["n_pd"], (
                f"Stratum {idx} PD mismatch: MD {md_row['n_pd']} vs CSV {c_row['n_pd']}"
            )
            assert md_row["n_total"] == c_row["n_total"]
            assert pytest.approx(md_row["hc_mean_age"], abs=0.05) == c_row["hc_mean_age"]
            assert pytest.approx(md_row["pd_mean_age"], abs=0.05) == c_row["pd_mean_age"]
            assert md_row["common_support"] == c_row["common_support_overlap"]
            assert md_row["status"] == "NOT ESTIMABLE"

    def test_feature_fdr_csv_schema_and_integrity(self) -> None:
        fdr_rows = _load_feature_fdr_csv()
        assert len(fdr_rows) == 39, f"Expected exactly 39 Core39 features, got {len(fdr_rows)}"

        csv_feature_names = [r["feature_name"] for r in fdr_rows]
        assert set(csv_feature_names) == set(FEATURE_NAMES), (
            "FDR CSV feature names do not perfectly match canonical Core39 schema"
        )

        for i in range(len(fdr_rows) - 1):
            assert fdr_rows[i]["lrt_chi2"] >= fdr_rows[i + 1]["lrt_chi2"], (
                f"Rows {i} and {i + 1} not sorted by LRT chi2 descending"
            )

    def test_markdown_report_top5_fdr_features_match_csv(self) -> None:
        report_path = Path("docs/reports/M2_BIAS_AUDIT_REPORT.md")
        markdown_text = report_path.read_text(encoding="utf-8")

        md_fdr_rows = _parse_markdown_fdr_table(markdown_text)
        csv_fdr_rows = _load_feature_fdr_csv()

        assert len(md_fdr_rows) == 5, f"Expected top 5 FDR rows in report, got {len(md_fdr_rows)}"

        for idx, (md_r, csv_r) in enumerate(zip(md_fdr_rows, csv_fdr_rows[:5], strict=True)):
            assert md_r["feature_name"] == csv_r["feature_name"], (
                f"Rank {idx + 1} mismatch: MD {md_r['feature_name']} vs CSV {csv_r['feature_name']}"
            )
            assert md_r["feature_name"] in FEATURE_NAMES, (
                f"Reported feature {md_r['feature_name']} not in Core39 schema"
            )
            assert pytest.approx(md_r["standardized_beta"], abs=0.001) == csv_r["standardized_beta"]
            assert pytest.approx(md_r["odds_ratio"], abs=0.001) == csv_r["odds_ratio"]
            assert pytest.approx(md_r["lrt_chi2"], abs=0.001) == csv_r["lrt_chi2"]
            assert pytest.approx(md_r["fdr_q_value"], abs=0.0001) == csv_r["fdr_q_value"]

    def test_no_obsolete_feature_names_in_m2_reports(self) -> None:
        obsolete_names = [
            "f0_contour_median_hz",
            "f0_contour_mean_hz",
            "local_jitter_relative",
        ]
        target_files = [
            Path("docs/reports/M2_BIAS_AUDIT_REPORT.md"),
            Path("docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md"),
            Path("docs/audit/M2_COMPLETION_REPORT.md"),
        ]

        for file_path in target_files:
            if not file_path.exists():
                continue
            content = file_path.read_text(encoding="utf-8")
            for obsolete in obsolete_names:
                assert obsolete not in content, (
                    f"Found obsolete feature name '{obsolete}' in {file_path}"
                )

    def test_scientific_wording_conformance(self) -> None:
        bias_report = Path("docs/reports/M2_BIAS_AUDIT_REPORT.md").read_text(encoding="utf-8")
        completion_report = Path("docs/audit/M2_COMPLETION_REPORT.md").read_text(encoding="utf-8")

        assert "Predictive redundancy of acoustic features" not in completion_report
        assert "2. **Predictive Redundancy:**" not in bias_report

        required_phrase = (
            "The retrospective cohort did not establish supported incremental predictive benefit "
            "from adding the current voice features beyond demographic comparators"
        )
        assert required_phrase in bias_report
        assert required_phrase in completion_report

        assert "Statistical Association" in bias_report
        assert "Predictive Performance" in bias_report
        assert "Incremental Predictive Contribution" in bias_report
        assert "External Clinical Validity" in bias_report

    def test_external_protocol_scientific_rigor(self) -> None:
        protocol_path = Path("docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md")
        content = protocol_path.read_text(encoding="utf-8")

        for sd_val in ["0.15", "0.20", "0.22", "0.25", "0.30"]:
            assert sd_val in content, f"Missing SD sensitivity scenario {sd_val}"

        assert (
            "Provisional Planning Assumption" in content
            or "exploratory planning assumption" in content
        )
        assert "cross-validation fold variability" in content.lower()

        assert "illustrative recruitment planning" in content.lower()
        assert "not a validated or statistically guaranteed sample size" in content.lower()

        assert "biostatistician" in content.lower()

        flawed = (
            "conclusively demonstrating that sustained-vowel "
            "acoustic analysis lacks clinical utility"
        )
        assert flawed not in content

        assert "clinically meaningful threshold" in content.lower()
        assert "absence of evidence is not evidence of absence" in content.lower()

        assert "biometric" in content.lower()
        assert "not render voice audio completely anonymized" in content.lower()
        assert "dpdp act 2023" in content.lower()

    def test_negative_age_table_mutation_fails(self) -> None:
        corrupted_markdown = (
            "## 10. Exploratory Age Strata Subgroup Analysis\n\n"
            "| Age Band | Range | N (HC) | N (PD) | Total N | HC Mean | PD Mean | "
            "Common Support | Status | Reason |\n"
            "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---|\n"
            "| **Under 50** | $[0, 50)$ | 25 | 3 | 28 | $37.36$ | $46.88$ | "
            "$[43.1, 49.0]$ | **NOT ESTIMABLE** | Reason |\n"
            "| **50–59** | $[50, 60)$ | 9 | 6 | 15 | $54.33$ | $56.96$ | "
            "$[51.0, 59.0]$ | **NOT ESTIMABLE** | Reason |\n"
            "| **60–69** | $[60, 70)$ | 3 | 14 | 17 | $63.33$ | $65.25$ | "
            "$[62.0, 64.0]$ | **NOT ESTIMABLE** | Reason |\n"
            r"| **70 and above** | $\ge 70$ | 4 | 14 | 18 | $74.75$ | $77.17$ | "
            "$[71.0, 79.0]$ | **NOT ESTIMABLE** | Reason |\n"
        )
        parsed_corrupted = _parse_markdown_age_table(corrupted_markdown)
        csv_rows = _load_age_subgroup_csv()

        with pytest.raises(AssertionError, match="Stratum 0 HC mismatch"):
            assert parsed_corrupted[0]["n_hc"] == csv_rows[0]["n_hc"], (
                f"Stratum 0 HC mismatch: MD {parsed_corrupted[0]['n_hc']} "
                f"vs CSV {csv_rows[0]['n_hc']}"
            )

    def test_negative_obsolete_feature_name_injection_fails(self) -> None:
        corrupted_fdr_markdown = (
            "## 11. Exploratory Feature-Level Multivariable Associations (BH-FDR)\n\n"
            "| Feature Name | Standardized $\\beta$ | Odds Ratio | LRT $\\chi^2$ (df=1) | "
            "p (Unadjusted) | FDR q-value | Significant ($q < 0.05$)? |\n"
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|\n"
            "| `f0_contour_median_hz` | $2.3034$ | $10.0080$ | $16.3545$ | "
            "$5.2532 \\times 10^{-5}$ | $0.0010244$ | **Yes (Exploratory)** |\n"
        )
        parsed_corrupted = _parse_markdown_fdr_table(corrupted_fdr_markdown)
        with pytest.raises(AssertionError, match="not in Core39 schema"):
            feat = parsed_corrupted[0]["feature_name"]
            assert feat in FEATURE_NAMES, f"Reported feature {feat} not in Core39 schema"

    def test_negative_corrupted_fdr_q_value_fails(self) -> None:
        corrupted_fdr_markdown = (
            "## 11. Exploratory Feature-Level Multivariable Associations (BH-FDR)\n\n"
            "| Feature Name | Standardized $\\beta$ | Odds Ratio | LRT $\\chi^2$ (df=1) | "
            "p (Unadjusted) | FDR q-value | Significant ($q < 0.05$)? |\n"
            "|:---|:---:|:---:|:---:|:---:|:---:|:---:|\n"
            "| `mfcc_10_sd` | $2.1997$ | $9.0222$ | $21.3094$ | "
            "$3.9081 \\times 10^{-6}$ | $0.9999999$ | **Yes (Exploratory)** |\n"
        )
        parsed_corrupted = _parse_markdown_fdr_table(corrupted_fdr_markdown)
        csv_rows = _load_feature_fdr_csv()

        with pytest.raises(AssertionError):
            assert (
                pytest.approx(parsed_corrupted[0]["fdr_q_value"], abs=0.0001)
                == csv_rows[0]["fdr_q_value"]
            )
