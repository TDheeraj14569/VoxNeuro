"""Scientific bias audit: demographic confounding, quality attrition, and feature associations."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import beta, chi2, contingency, fisher_exact, mannwhitneyu, t
from sklearn.linear_model import LogisticRegression


def sanitize_for_json(obj: Any) -> Any:
    """Ensure all floats, numbers, and keys are RFC 8259 JSON compliant.

    - Preserves full floating-point precision for p-values and effect sizes without rounding.
    - Represents NaN and positive/negative infinity as None (null in JSON).
    - Preserves zero exactly as 0.0 or 0.
    - Preserves small positive scientific numbers (e.g., 1.75e-8).
    - Converts tuple dictionary keys into underscore-separated strings.
    """
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            key_str = "_".join(str(item) for item in k) if isinstance(k, tuple) else str(k)
            sanitized[key_str] = sanitize_for_json(v)
        return sanitized
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        f_val = float(obj)
        if math.isnan(f_val) or math.isinf(f_val):
            return None
        return f_val
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    return obj


def _clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact Clopper-Pearson 95% confidence interval for a binomial proportion."""
    if n == 0:
        return 0.0, 1.0
    lower = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    upper = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lower, upper


def _pooled_sd(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate Cohen's pooled sample standard deviation."""
    n_a, n_b = len(a), len(b)
    if n_a + n_b <= 2:
        return 0.0
    var_a = float(np.var(a, ddof=1)) if n_a > 1 else 0.0
    var_b = float(np.var(b, ddof=1)) if n_b > 1 else 0.0
    return math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))


def validate_demographic_integrity(
    manifest_df: pd.DataFrame,
    demographics_df: pd.DataFrame,
) -> dict[str, Any]:
    """Validate demographic data integrity, schema consistency, and one-to-one joins.

    Checks:
    - Valid diagnostic class labels ('HC', 'PD').
    - Valid biological sex values ('F', 'M').
    - Absence of missing or null demographic values.
    - Valid numeric age values (positive finite floats).
    - Absence of duplicate participant identifiers.
    - Exact one-to-one join between manifest and demographics.
    """
    issues: list[str] = []

    # Participant identifier uniqueness
    if manifest_df["participant_id"].duplicated().any():
        dups = manifest_df[manifest_df["participant_id"].duplicated()]["participant_id"].tolist()
        issues.append(f"Duplicate participant IDs in manifest: {dups}")
    if demographics_df["participant_id"].duplicated().any():
        dups = demographics_df[demographics_df["participant_id"].duplicated()][
            "participant_id"
        ].tolist()
        issues.append(f"Duplicate participant IDs in demographics: {dups}")

    # One-to-one join validation
    m_ids = set(manifest_df["participant_id"])
    d_ids = set(demographics_df["participant_id"])
    unmatched_manifest = list(m_ids - d_ids)
    unmatched_demo = list(d_ids - m_ids)
    if unmatched_manifest:
        issues.append(f"Manifest participants missing in demographics: {unmatched_manifest}")
    if unmatched_demo:
        issues.append(f"Demographics participants missing in manifest: {unmatched_demo}")

    # Label validation
    valid_labels = {"HC", "PD"}
    labels_found = set(demographics_df["class_label"].unique())
    if not labels_found <= valid_labels:
        issues.append(f"Invalid class labels found: {labels_found - valid_labels}")

    # Sex validation
    valid_sex = {"F", "M"}
    sex_found = set(demographics_df["sex"].dropna().unique())
    if not sex_found <= valid_sex:
        issues.append(f"Invalid sex categories found: {sex_found - valid_sex}")

    # Age validation
    ages = pd.to_numeric(demographics_df["age"], errors="coerce")
    if ages.isna().any():
        issues.append(f"Missing or malformed age values found: {int(ages.isna().sum())}")
    if (ages < 0).any() or (ages > 120).any():
        issues.append("Age values outside plausible physiological range (0-120).")

    return {
        "valid": len(issues) == 0,
        "n_manifest": len(manifest_df),
        "n_demographics": len(demographics_df),
        "issues": issues,
        "unmatched_manifest_count": len(unmatched_manifest),
        "unmatched_demographics_count": len(unmatched_demo),
    }


def audit_age_distribution(
    frame: pd.DataFrame,
    *,
    n_bootstraps: int = 1000,
    seed: int = 2026,
) -> dict[str, Any]:
    """Audit age distributions, standardized mean differences, and rank statistics.

    Rank-biserial sign convention:
    Calculated under the convention HC minus PD.
    When HC ages are lower than PD ages, r_rb is negative.
    Formula: r_rb = (2 * U_HC) / (n_HC * n_PD) - 1.0
    """
    if "age" not in frame.columns or "class_label" not in frame.columns:
        raise ValueError("DataFrame must contain 'age' and 'class_label' columns.")

    clean = frame[["age", "class_label"]].dropna()
    clean["age"] = pd.to_numeric(clean["age"], errors="coerce")
    clean = clean.dropna()

    groups = {
        str(label): group["age"].to_numpy(dtype=float)
        for label, group in clean.groupby("class_label")
    }

    if "HC" not in groups or "PD" not in groups:
        raise ValueError("Both 'HC' and 'PD' class labels must be present.")

    hc_age = groups["HC"]
    pd_age = groups["PD"]

    def _stats(arr: np.ndarray) -> dict[str, float | int | str]:
        q25, q75 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
        mean = float(np.mean(arr))
        sd = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        n = len(arr)
        se = sd / math.sqrt(n) if n > 0 else 0.0
        t_crit = float(t.ppf(0.975, df=n - 1)) if n > 1 else 1.96
        return {
            "n": n,
            "mean": mean,
            "sd": sd,
            "median": float(np.median(arr)),
            "iqr": q75 - q25,
            "q25": q25,
            "q75": q75,
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean_ci_lower_95": mean - t_crit * se,
            "mean_ci_upper_95": mean + t_crit * se,
            "mean_ci_95": [float(mean - t_crit * se), float(mean + t_crit * se)],
            "ci_method": "Student's t distribution (df=n-1, 95% two-sided)",
        }

    hc_stats = _stats(hc_age)
    pd_stats = _stats(pd_age)

    # Effect sizes (HC minus PD)
    mean_diff = float(hc_stats["mean"] - pd_stats["mean"])
    median_diff = float(hc_stats["median"] - pd_stats["median"])
    pooled = _pooled_sd(hc_age, pd_age)
    smd = (mean_diff / pooled) if pooled > 0 else 0.0

    # Mann-Whitney U test (u_stat counts times HC > PD)
    u_test = mannwhitneyu(hc_age, pd_age, alternative="two-sided")
    u_stat = float(u_test.statistic)
    p_val = float(u_test.pvalue)

    # Rank-biserial correlation under HC minus PD convention
    n_hc, n_pd = len(hc_age), len(pd_age)
    rank_biserial = (2.0 * u_stat) / (n_hc * n_pd) - 1.0 if (n_hc * n_pd) > 0 else 0.0

    # Participant bootstrap for mean difference and SMD
    rng = np.random.default_rng(seed)
    boot_mean_diffs = np.empty(n_bootstraps, dtype=float)
    boot_smds = np.empty(n_bootstraps, dtype=float)

    for i in range(n_bootstraps):
        b_hc = rng.choice(hc_age, size=n_hc, replace=True)
        b_pd = rng.choice(pd_age, size=n_pd, replace=True)
        b_diff = float(np.mean(b_hc) - np.mean(b_pd))
        b_pooled = _pooled_sd(b_hc, b_pd)
        boot_mean_diffs[i] = b_diff
        boot_smds[i] = (b_diff / b_pooled) if b_pooled > 0 else 0.0

    return {
        "HC": hc_stats,
        "PD": pd_stats,
        "mean_difference_hc_minus_pd": mean_diff,
        "median_difference_hc_minus_pd": median_diff,
        "pooled_sd": pooled,
        "standardized_mean_difference": smd,
        "mann_whitney_u": u_stat,
        "mann_whitney_p": p_val,
        "rank_biserial_correlation": rank_biserial,
        "mean_diff_bootstrap_ci_95": [
            float(np.percentile(boot_mean_diffs, 2.5)),
            float(np.percentile(boot_mean_diffs, 97.5)),
        ],
        "smd_bootstrap_ci_95": [
            float(np.percentile(boot_smds, 2.5)),
            float(np.percentile(boot_smds, 97.5)),
        ],
    }


def audit_sex_distribution(frame: pd.DataFrame) -> dict[str, Any]:
    """Audit biological sex representation, Fisher's exact test, and Cramér's V.

    Cramér's V is computed using standard Pearson chi-square without Yates'
    continuity correction to assess association magnitude separately from
    Fisher's exact test.
    """
    if "sex" not in frame.columns or "class_label" not in frame.columns:
        raise ValueError("DataFrame must contain 'sex' and 'class_label' columns.")

    clean = frame[["sex", "class_label"]].copy()
    missing_sex = int(clean["sex"].isna().sum())
    clean = clean.dropna()

    counts: dict[str, dict[str, int]] = {}
    proportions: dict[str, dict[str, float]] = {}

    for label in ["HC", "PD"]:
        sub = clean[clean["class_label"] == label]
        n_label = len(sub)
        n_f = int((sub["sex"] == "F").sum())
        n_m = int((sub["sex"] == "M").sum())
        counts[label] = {"F": n_f, "M": n_m, "total": n_label}
        proportions[label] = {
            "prop_F": (n_f / n_label) if n_label > 0 else 0.0,
            "prop_M": (n_m / n_label) if n_label > 0 else 0.0,
        }

    # 2x2 contingency table: [[HC_F, HC_M], [PD_F, PD_M]]
    table = [[counts["HC"]["F"], counts["HC"]["M"]], [counts["PD"]["F"], counts["PD"]["M"]]]

    odds_ratio, p_val = fisher_exact(table, alternative="two-sided")

    # Log-odds standard error for 95% CI of odds ratio
    ci_lower, ci_upper = 0.0, 0.0
    if all(cell > 0 for row in table for cell in row):
        log_or = math.log(odds_ratio)
        se_log_or = math.sqrt(sum(1.0 / cell for row in table for cell in row))
        ci_lower = math.exp(log_or - 1.96 * se_log_or)
        ci_upper = math.exp(log_or + 1.96 * se_log_or)

    # Cramér's V using standard Pearson chi-square without Yates' continuity correction
    chi2_val = float(contingency.chi2_contingency(table, correction=False)[0])
    n_total = sum(sum(row) for row in table)
    cramers_v = math.sqrt(chi2_val / n_total) if n_total > 0 else 0.0

    return {
        "counts": counts,
        "proportions": proportions,
        "missing_sex_count": missing_sex,
        "contingency_table": table,
        "fisher_exact_p": float(p_val),
        "odds_ratio": float(odds_ratio),
        "odds_ratio_ci_95": [float(ci_lower), float(ci_upper)],
        "cramers_v": float(cramers_v),
        "cramers_v_method": "Standard Pearson chi-square without Yates continuity correction",
    }


def audit_joint_distribution(frame: pd.DataFrame) -> dict[str, Any]:
    """Audit age within sex strata and assess common demographic support."""
    if not {"age", "sex", "class_label"} <= set(frame.columns):
        raise ValueError("DataFrame must contain 'age', 'sex', and 'class_label'.")

    clean = frame[["age", "sex", "class_label"]].dropna().copy()
    clean["age"] = pd.to_numeric(clean["age"], errors="coerce")
    clean = clean.dropna()

    strata_results: dict[str, Any] = {}
    for sex_cat in ["F", "M"]:
        sub = clean[clean["sex"] == sex_cat]
        hc_ages = sub[sub["class_label"] == "HC"]["age"].to_numpy(dtype=float)
        pd_ages = sub[sub["class_label"] == "PD"]["age"].to_numpy(dtype=float)

        hc_mean = float(np.mean(hc_ages)) if len(hc_ages) > 0 else 0.0
        pd_mean = float(np.mean(pd_ages)) if len(pd_ages) > 0 else 0.0
        hc_sd = float(np.std(hc_ages, ddof=1)) if len(hc_ages) > 1 else 0.0
        pd_sd = float(np.std(pd_ages, ddof=1)) if len(pd_ages) > 1 else 0.0

        # Overlap interval
        overlap_min = (
            max(float(np.min(hc_ages)), float(np.min(pd_ages)))
            if len(hc_ages) and len(pd_ages)
            else None
        )
        overlap_max = (
            min(float(np.max(hc_ages)), float(np.max(pd_ages)))
            if len(hc_ages) and len(pd_ages)
            else None
        )
        has_overlap = bool(
            overlap_min is not None and overlap_max is not None and overlap_min <= overlap_max
        )

        p_val = (
            float(mannwhitneyu(hc_ages, pd_ages, alternative="two-sided").pvalue)
            if len(hc_ages) and len(pd_ages)
            else 1.0
        )

        hc_min = float(np.min(hc_ages)) if len(hc_ages) > 0 else None
        hc_max = float(np.max(hc_ages)) if len(hc_ages) > 0 else None
        pd_min = float(np.min(pd_ages)) if len(pd_ages) > 0 else None
        pd_max = float(np.max(pd_ages)) if len(pd_ages) > 0 else None

        strata_results[sex_cat] = {
            "HC": {
                "n": len(hc_ages),
                "mean": hc_mean,
                "sd": hc_sd,
                "min": hc_min,
                "max": hc_max,
            },
            "PD": {
                "n": len(pd_ages),
                "mean": pd_mean,
                "sd": pd_sd,
                "min": pd_min,
                "max": pd_max,
            },
            "age_diff_hc_minus_pd": (hc_mean - pd_mean) if len(hc_ages) and len(pd_ages) else None,
            "mann_whitney_p": p_val,
            "common_support_overlap": [overlap_min, overlap_max] if has_overlap else None,
            "has_common_support": has_overlap,
        }

    return strata_results


def audit_age_strata(
    frame: pd.DataFrame,
    *,
    bands: tuple[tuple[str, float, float], ...] = (
        ("Under 50", 0.0, 50.0),
        ("50-59", 50.0, 60.0),
        ("60-69", 60.0, 70.0),
        ("70 and above", 70.0, 150.0),
    ),
    min_cell_per_class: int = 10,
) -> pd.DataFrame:
    """Exploratory post-hoc age-stratified subgroup audit with small-cell suppression rules.

    Computes participant counts, age distributions, common support, and enforces
    pre-registered small-cell suppression: performance metrics are marked NOT ESTIMABLE
    if either diagnostic arm has fewer than min_cell_per_class participants.
    """
    clean = frame[["participant_id", "class_label", "age"]].dropna().copy()
    clean["age"] = pd.to_numeric(clean["age"], errors="coerce")
    clean = clean.dropna()

    # Aggregate to unique participant level if input has multiple rows
    part_df = clean.groupby("participant_id", as_index=False).first()

    records = []
    for band_name, low, high in bands:
        sub = part_df[(part_df["age"] >= low) & (part_df["age"] < high)]
        hc_ages = sub[sub["class_label"] == "HC"]["age"].to_numpy(dtype=float)
        pd_ages = sub[sub["class_label"] == "PD"]["age"].to_numpy(dtype=float)

        n_hc = len(hc_ages)
        n_pd = len(pd_ages)
        n_total = len(sub)

        has_support = bool(n_hc > 0 and n_pd > 0)
        overlap_range = (
            f"[{max(float(np.min(hc_ages)), float(np.min(pd_ages))):.1f}, "
            f"{min(float(np.max(hc_ages)), float(np.max(pd_ages))):.1f}]"
            if has_support
            and max(float(np.min(hc_ages)), float(np.min(pd_ages)))
            <= min(float(np.max(hc_ages)), float(np.max(pd_ages)))
            else "None"
        )

        is_estimable = bool(n_hc >= min_cell_per_class and n_pd >= min_cell_per_class)
        status = "ESTIMABLE" if is_estimable else "NOT ESTIMABLE"
        reason = (
            "Adequate class support"
            if is_estimable
            else (
                f"Small-cell suppression: < {min_cell_per_class} participants "
                f"in at least one class (HC={n_hc}, PD={n_pd})"
            )
        )

        records.append(
            {
                "age_band": band_name,
                "age_range": f"[{low:.0f}, {high:.0f})" if high < 120 else f">={low:.0f}",
                "n_hc": n_hc,
                "n_pd": n_pd,
                "n_total": n_total,
                "hc_mean_age": round(float(np.mean(hc_ages)), 2) if n_hc > 0 else None,
                "pd_mean_age": round(float(np.mean(pd_ages)), 2) if n_pd > 0 else None,
                "common_support_overlap": overlap_range,
                "status": status,
                "suppression_reason": reason,
            }
        )

    return pd.DataFrame(records)


def audit_feature_level_associations(
    frame: pd.DataFrame,
    feature_names: list[str],
) -> pd.DataFrame:
    """Evaluate multivariable logistic associations adjusting for age and sex.

    Statistical specification:
    For each feature j in feature_names:
      Model 0: logit(P(Y=1)) = beta_0 + beta_age * z(age) + beta_sex * sex
      Model 1: logit(P(Y=1)) = beta_0 + beta_age * z(age) + beta_sex * sex + beta_j * z(feature_j)
      LRT Statistic: Lambda = 2 * (ll_1 - ll_0) ~ Chi2(df=1)
      p_unadjusted: chi2.sf(Lambda, df=1)

    Multiplicity:
      Benjamini-Hochberg False Discovery Rate across all tested hypotheses.
    """
    # Participant-level aggregation
    part_df = frame.groupby("participant_id", as_index=False).first().copy()
    y = (part_df["class_label"] == "PD").astype(int).to_numpy()

    age_num = pd.to_numeric(part_df["age"], errors="coerce").to_numpy(dtype=float)
    age_mean = float(np.nanmean(age_num))
    age_std = float(np.nanstd(age_num)) or 1.0
    age_z = ((age_num - age_mean) / age_std).reshape(-1, 1)

    sex_binary = (
        (part_df["sex"].str.strip().str.upper() == "M").astype(int).to_numpy().reshape(-1, 1)
    )
    x0 = np.hstack([age_z, sex_binary])

    # Fit Model 0 (Demographics only)
    m0 = LogisticRegression(C=1e5, solver="lbfgs", max_iter=2000).fit(x0, y)
    prob0 = np.clip(m0.predict_proba(x0)[:, 1], 1e-15, 1 - 1e-15)
    ll0 = float(np.sum(y * np.log(prob0) + (1 - y) * np.log(1 - prob0)))

    results = []
    for feat in feature_names:
        raw_vals = pd.to_numeric(part_df[feat], errors="coerce").to_numpy(dtype=float)
        f_mean = float(np.nanmean(raw_vals))
        f_std = float(np.nanstd(raw_vals)) or 1.0
        feat_z = np.nan_to_num((raw_vals - f_mean) / f_std, nan=0.0).reshape(-1, 1)

        x1 = np.hstack([x0, feat_z])
        m1 = LogisticRegression(C=1e5, solver="lbfgs", max_iter=2000).fit(x1, y)
        prob1 = np.clip(m1.predict_proba(x1)[:, 1], 1e-15, 1 - 1e-15)
        ll1 = float(np.sum(y * np.log(prob1) + (1 - y) * np.log(1 - prob1)))

        lrt_stat = max(0.0, 2.0 * (ll1 - ll0))
        p_val = float(chi2.sf(lrt_stat, df=1))
        beta_val = float(m1.coef_[0, -1])
        odds_ratio = float(np.exp(beta_val))

        results.append(
            {
                "feature_name": feat,
                "standardized_beta": round(beta_val, 4),
                "odds_ratio": round(odds_ratio, 4),
                "lrt_chi2": round(lrt_stat, 4),
                "p_unadjusted": p_val,
            }
        )

    res_df = pd.DataFrame(results).sort_values("p_unadjusted").reset_index(drop=True)
    m_hypotheses = len(res_df)
    p_sorted = res_df["p_unadjusted"].to_numpy()

    # Benjamini-Hochberg procedure
    q_vals = np.empty(m_hypotheses, dtype=float)
    running_min = 1.0
    for i in range(m_hypotheses - 1, -1, -1):
        rank = i + 1
        q_val = min(1.0, (m_hypotheses / rank) * p_sorted[i])
        running_min = min(running_min, q_val)
        q_vals[i] = running_min

    res_df["fdr_q_value"] = q_vals
    res_df["significant_fdr_05"] = res_df["fdr_q_value"] < 0.05
    return res_df


def audit_quality_attrition(
    manifest: pd.DataFrame,
    extraction_report: pd.DataFrame,
) -> dict[str, Any]:
    """Audit class-dependent recording-quality attrition and clipping exclusions."""
    if "sample_id" not in manifest.columns or "class_label" not in manifest.columns:
        raise ValueError("Manifest must contain 'sample_id' and 'class_label'.")
    if (
        "sample_id" not in extraction_report.columns
        or "extraction_status" not in extraction_report.columns
    ):
        raise ValueError("Extraction report must contain 'sample_id' and 'extraction_status'.")

    merged = pd.merge(manifest[["sample_id", "class_label"]], extraction_report, on="sample_id")
    merged["is_accepted"] = merged["extraction_status"].str.strip().str.casefold() == "success"

    classes = ["HC", "PD"]
    summary: dict[str, Any] = {}
    table = [[0, 0], [0, 0]]  # [[HC_acc, HC_excl], [PD_acc, PD_excl]]

    for idx, c in enumerate(classes):
        sub = merged[merged["class_label"] == c]
        total = len(sub)
        accepted = int(sub["is_accepted"].sum())
        excluded = total - accepted
        rate = accepted / total if total > 0 else 0.0
        ci_low, ci_high = _clopper_pearson(accepted, total)

        summary[c] = {
            "eligible_count": total,
            "accepted_count": accepted,
            "excluded_count": excluded,
            "acceptance_rate": rate,
            "exclusion_rate": 1.0 - rate,
            "acceptance_ci_95": [ci_low, ci_high],
        }
        table[idx] = [accepted, excluded]

    odds_ratio, p_val = fisher_exact(table, alternative="two-sided")

    # Document failure mechanisms
    failed_rows = merged[~merged["is_accepted"]]
    reasons = failed_rows.get("failure_reason", pd.Series(dtype=str)).tolist()
    clipping_count = sum("clip" in str(r).casefold() for r in reasons)

    return {
        "class_summary": summary,
        "contingency_table": table,
        "fisher_exact_p": float(p_val),
        "odds_ratio": float(odds_ratio),
        "total_excluded": len(failed_rows),
        "clipping_exclusions": clipping_count,
        "other_exclusions": len(failed_rows) - clipping_count,
    }
