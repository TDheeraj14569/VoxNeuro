"""Reproducible age- and sex-matching sensitivity algorithms for observational cohorts."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


def _pooled_sd(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate Cohen's pooled sample standard deviation."""
    n_a, n_b = len(a), len(b)
    if n_a + n_b <= 2:
        return 0.0
    var_a = float(np.var(a, ddof=1)) if n_a > 1 else 0.0
    var_b = float(np.var(b, ddof=1)) if n_b > 1 else 0.0
    return math.sqrt(((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2))


def perform_optimal_matching(
    frame: pd.DataFrame,
    *,
    caliper_multiplier: float | None = 0.2,
    seed: int = 2026,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Perform optimal 1:1 matching without replacement with exact sex constraint.

    Parameters
    ----------
    frame:
        Input DataFrame containing 'participant_id', 'class_label', 'age', and 'sex'.
    caliper_multiplier:
        Multiplier for pooled SD of age (e.g. 0.2). If None, no caliper is applied.
    seed:
        Fixed random seed for deterministic tie-breaking.

    Returns
    -------
    tuple[pd.DataFrame, dict[str, Any]]:
        Matched subset DataFrame with 'pair_id' and 'match_age_distance', plus summary dict.
    """
    required = {"participant_id", "class_label", "age", "sex"}
    if not required <= set(frame.columns):
        raise ValueError(f"Input frame must contain columns: {required}")

    clean = frame.dropna(subset=list(required)).copy()
    clean["age"] = pd.to_numeric(clean["age"], errors="coerce")
    clean = clean.dropna(subset=["age"])

    hc_all = clean[clean["class_label"] == "HC"]["age"].to_numpy(dtype=float)
    pd_all = clean[clean["class_label"] == "PD"]["age"].to_numpy(dtype=float)

    if len(hc_all) == 0 or len(pd_all) == 0:
        raise ValueError("Both HC and PD groups must have valid participants.")

    pooled_sd = _pooled_sd(hc_all, pd_all)
    caliper_val = (
        (caliper_multiplier * pooled_sd) if caliper_multiplier is not None else float("inf")
    )

    pre_smd = float((np.mean(hc_all) - np.mean(pd_all)) / pooled_sd) if pooled_sd > 0 else 0.0

    matched_rows: list[pd.Series] = []
    pair_counter = 1
    total_avail_pd = len(pd_all)
    total_avail_hc = len(hc_all)

    # Perform matching within each biological sex stratum
    for sex_cat in sorted(clean["sex"].unique()):
        sub_pd = clean[(clean["class_label"] == "PD") & (clean["sex"] == sex_cat)].copy()
        sub_hc = clean[(clean["class_label"] == "HC") & (clean["sex"] == sex_cat)].copy()

        if sub_pd.empty or sub_hc.empty:
            continue

        pd_ages = sub_pd["age"].to_numpy(dtype=float)
        hc_ages = sub_hc["age"].to_numpy(dtype=float)

        # Distance matrix (rows: PD, cols: HC)
        cost_matrix = np.abs(pd_ages[:, np.newaxis] - hc_ages[np.newaxis, :])

        # Hungarian algorithm for global minimum total distance
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        for r, c in zip(row_ind, col_ind, strict=False):
            dist = float(cost_matrix[r, c])
            if dist <= caliper_val:
                pd_row = sub_pd.iloc[r].copy()
                hc_row = sub_hc.iloc[c].copy()

                pd_row["pair_id"] = pair_counter
                pd_row["match_age_distance"] = dist
                hc_row["pair_id"] = pair_counter
                hc_row["match_age_distance"] = dist

                matched_rows.append(pd_row)
                matched_rows.append(hc_row)
                pair_counter += 1

    matched_df = pd.DataFrame(matched_rows) if matched_rows else pd.DataFrame(columns=clean.columns)

    if not matched_df.empty:
        matched_hc = matched_df[matched_df["class_label"] == "HC"]["age"].to_numpy(dtype=float)
        matched_pd = matched_df[matched_df["class_label"] == "PD"]["age"].to_numpy(dtype=float)
        post_pooled = _pooled_sd(matched_hc, matched_pd)
        post_smd = (
            float((np.mean(matched_hc) - np.mean(matched_pd)) / post_pooled)
            if post_pooled > 0
            else 0.0
        )
        distances = matched_df["match_age_distance"].dropna().to_numpy(dtype=float)
        unique_distances = distances[::2]  # One per pair

        summary: dict[str, Any] = {
            "available_pd": total_avail_pd,
            "available_hc": total_avail_hc,
            "matched_pairs": len(unique_distances),
            "matched_pd": len(matched_pd),
            "matched_hc": len(matched_hc),
            "unmatched_pd": total_avail_pd - len(matched_pd),
            "unmatched_hc": total_avail_hc - len(matched_hc),
            "caliper_multiplier": caliper_multiplier,
            "caliper_threshold_years": round(caliper_val, 3)
            if caliper_multiplier is not None
            else None,
            "pooled_sd_years": round(pooled_sd, 3),
            "pre_match_age_mean_hc": round(float(np.mean(hc_all)), 2),
            "pre_match_age_mean_pd": round(float(np.mean(pd_all)), 2),
            "post_match_age_mean_hc": round(float(np.mean(matched_hc)), 2),
            "post_match_age_mean_pd": round(float(np.mean(matched_pd)), 2),
            "pre_match_smd": round(pre_smd, 3),
            "post_match_smd": round(post_smd, 3),
            "mean_pairwise_age_diff": round(float(np.mean(unique_distances)), 3),
            "median_pairwise_age_diff": round(float(np.median(unique_distances)), 3),
            "max_pairwise_age_diff": round(float(np.max(unique_distances)), 3),
            "age_range_retained_hc": [
                round(float(np.min(matched_hc)), 1),
                round(float(np.max(matched_hc)), 1),
            ],
            "age_range_retained_pd": [
                round(float(np.min(matched_pd)), 1),
                round(float(np.max(matched_pd)), 1),
            ],
            "sex_counts": matched_df.groupby(["class_label", "sex"]).size().to_dict(),
        }
    else:
        summary = {
            "available_pd": total_avail_pd,
            "available_hc": total_avail_hc,
            "matched_pairs": 0,
            "matched_pd": 0,
            "matched_hc": 0,
            "unmatched_pd": total_avail_pd,
            "unmatched_hc": total_avail_hc,
            "caliper_multiplier": caliper_multiplier,
            "caliper_threshold_years": round(caliper_val, 3)
            if caliper_multiplier is not None
            else None,
            "pooled_sd_years": round(pooled_sd, 3),
            "pre_match_smd": round(pre_smd, 3),
            "post_match_smd": None,
            "mean_pairwise_age_diff": None,
            "max_pairwise_age_diff": None,
        }

    return matched_df, summary


def evaluate_matching_sensitivities(
    frame: pd.DataFrame,
    calipers: tuple[float | None, ...] = (0.1, 0.2, 0.3, None),
) -> pd.DataFrame:
    """Run sensitivity analysis across specified caliper thresholds."""
    records = []
    for cal in calipers:
        _, summary = perform_optimal_matching(frame, caliper_multiplier=cal)
        label = f"{cal} SD" if cal is not None else "Uncalipered (Max Match)"
        cal_years = (
            f"{summary['caliper_threshold_years']:.2f} yrs"
            if summary.get("caliper_threshold_years")
            else "None"
        )
        records.append(
            {
                "caliper_specification": label,
                "caliper_threshold": cal_years,
                "available_pd": summary["available_pd"],
                "available_hc": summary["available_hc"],
                "matched_pairs": summary["matched_pairs"],
                "matched_total": summary["matched_pairs"] * 2,
                "unmatched_pd": summary["unmatched_pd"],
                "unmatched_hc": summary["unmatched_hc"],
                "post_match_age_hc": summary.get("post_match_age_mean_hc"),
                "post_match_age_pd": summary.get("post_match_age_mean_pd"),
                "post_match_smd": summary.get("post_match_smd"),
                "mean_pairwise_diff": summary.get("mean_pairwise_age_diff"),
                "max_pairwise_diff": summary.get("max_pairwise_age_diff"),
            }
        )
    return pd.DataFrame(records)
