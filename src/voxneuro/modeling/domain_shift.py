"""Descriptive and inferential analysis of acoustic recording-domain shift."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from voxneuro.features.schema import FEATURE_NAMES
from voxneuro.modeling.domain_assessment import DomainShiftSummary


def compare_acquisition_metadata(ref_meta: dict[str, Any], cand_meta: dict[str, Any]) -> list[str]:
    """Compare physical and digital acquisition properties between two domains."""
    diffs: list[str] = []

    dev_ref = ref_meta.get("device_category", "unknown")
    dev_cand = cand_meta.get("device_category", "unknown")
    if dev_ref != dev_cand:
        diffs.append(
            f"Device category mismatch: reference is {dev_ref!r}, candidate is {dev_cand!r}."
        )

    mic_ref = ref_meta.get("microphone_type", "unknown")
    mic_cand = cand_meta.get("microphone_type", "unknown")
    if mic_ref != mic_cand:
        diffs.append(
            f"Microphone transducer mismatch: reference is {mic_ref!r}, candidate is {mic_cand!r}."
        )

    sr_ref = ref_meta.get("original_sample_rate")
    sr_cand = cand_meta.get("original_sample_rate")
    if sr_ref and sr_cand and sr_ref != sr_cand:
        diffs.append(
            f"Original sampling rate shift: reference is {sr_ref} Hz, candidate is {sr_cand} Hz."
        )

    env_ref = ref_meta.get("recording_environment", "unknown")
    env_cand = cand_meta.get("recording_environment", "unknown")
    if env_ref != env_cand:
        diffs.append(
            f"Acoustic environment shift: reference is {env_ref!r}, candidate is {env_cand!r}."
        )

    codec_ref = ref_meta.get("audio_codec", "unknown")
    codec_cand = cand_meta.get("audio_codec", "unknown")
    if codec_ref != codec_cand:
        diffs.append(
            f"Audio codec difference: reference is {codec_ref!r}, candidate is {codec_cand!r}."
        )

    agc_ref = ref_meta.get("automatic_gain_control", "unknown")
    agc_cand = cand_meta.get("automatic_gain_control", "unknown")
    if agc_ref != agc_cand:
        diffs.append(
            f"Automatic gain control divergence: reference is {agc_ref!r}, "
            f"candidate is {agc_cand!r}."
        )

    return diffs


def compute_standardized_mean_difference(x_ref: np.ndarray, x_cand: np.ndarray) -> float:
    """Calculate Cohen's d with pooled variance for finite real vectors."""
    ref_clean = x_ref[np.isfinite(x_ref)]
    cand_clean = x_cand[np.isfinite(x_cand)]
    n_ref = len(ref_clean)
    n_cand = len(cand_clean)

    if n_ref < 2 or n_cand < 2:
        return float("nan")

    var_ref = np.var(ref_clean, ddof=1)
    var_cand = np.var(cand_clean, ddof=1)
    pooled_var = ((n_ref - 1) * var_ref + (n_cand - 1) * var_cand) / (n_ref + n_cand - 2)

    if pooled_var <= 1e-12:
        return 0.0

    return float((np.mean(cand_clean) - np.mean(ref_clean)) / math.sqrt(pooled_var))


def benjamini_hochberg_fdr(p_values: list[float], alpha: float = 0.05) -> list[float]:
    """Calculate Benjamini-Hochberg FDR-adjusted q-values for a sequence of p-values."""
    m = len(p_values)
    if m == 0:
        return []

    # Sort indices by p-value
    sorted_pairs = sorted(enumerate(p_values), key=lambda x: x[1])
    q_values = [0.0] * m

    min_q = 1.0
    for rank_idx in range(m - 1, -1, -1):
        original_idx, p_val = sorted_pairs[rank_idx]
        rank = rank_idx + 1
        q_val = min(min_q, (p_val * m) / rank)
        min_q = q_val
        q_values[original_idx] = float(min(1.0, max(0.0, q_val)))

    return q_values


def compute_feature_shift(
    reference_features: pd.DataFrame,
    candidate_features: pd.DataFrame,
    feature_names: list[str] | None = None,
    alpha: float = 0.05,
    allow_identical: bool = False,
) -> pd.DataFrame:
    """Compute comprehensive feature-level shift metrics and multiplicity-corrected tests."""
    if not allow_identical and (
        reference_features is candidate_features
        or (
            len(reference_features) > 0
            and len(candidate_features) > 0
            and reference_features.equals(candidate_features)
        )
    ):
        raise ValueError(
            "Reference and candidate feature tables are identical. "
            "Self-comparison cannot be evaluated as an independent external domain comparison."
        )

    names = feature_names or FEATURE_NAMES
    records: list[dict[str, Any]] = []
    raw_p_values: list[float] = []

    for name in names:
        if name not in reference_features.columns or name not in candidate_features.columns:
            continue

        ref_vals = pd.to_numeric(reference_features[name], errors="coerce").dropna().values
        cand_vals = pd.to_numeric(candidate_features[name], errors="coerce").dropna().values

        ref_mean = float(np.mean(ref_vals)) if len(ref_vals) > 0 else float("nan")
        ref_sd = float(np.std(ref_vals, ddof=1)) if len(ref_vals) > 1 else float("nan")
        ref_median = float(np.median(ref_vals)) if len(ref_vals) > 0 else float("nan")
        ref_iqr = (
            float(np.percentile(ref_vals, 75) - np.percentile(ref_vals, 25))
            if len(ref_vals) > 0
            else float("nan")
        )

        cand_mean = float(np.mean(cand_vals)) if len(cand_vals) > 0 else float("nan")
        cand_sd = float(np.std(cand_vals, ddof=1)) if len(cand_vals) > 1 else float("nan")
        cand_median = float(np.median(cand_vals)) if len(cand_vals) > 0 else float("nan")
        cand_iqr = (
            float(np.percentile(cand_vals, 75) - np.percentile(cand_vals, 25))
            if len(cand_vals) > 0
            else float("nan")
        )

        smd = compute_standardized_mean_difference(ref_vals, cand_vals)

        # Two-sample Kolmogorov-Smirnov test
        if len(ref_vals) >= 2 and len(cand_vals) >= 2:
            res = ks_2samp(ref_vals, cand_vals)
            ks_stat = float(res.statistic)
            p_val = float(res.pvalue)
        else:
            ks_stat = float("nan")
            p_val = 1.0

        raw_p_values.append(p_val)

        records.append(
            {
                "feature": name,
                "ref_mean": ref_mean,
                "ref_sd": ref_sd,
                "ref_median": ref_median,
                "ref_iqr": ref_iqr,
                "cand_mean": cand_mean,
                "cand_sd": cand_sd,
                "cand_median": cand_median,
                "cand_iqr": cand_iqr,
                "smd_cohen_d": smd,
                "abs_smd": abs(smd) if np.isfinite(smd) else float("nan"),
                "ks_statistic": ks_stat,
                "p_value_raw": p_val,
            }
        )

    if not records:
        return pd.DataFrame(
            columns=[
                "feature",
                "ref_mean",
                "ref_sd",
                "ref_median",
                "ref_iqr",
                "cand_mean",
                "cand_sd",
                "cand_median",
                "cand_iqr",
                "smd_cohen_d",
                "abs_smd",
                "ks_statistic",
                "p_value_raw",
                "p_value_fdr",
                "p_value_bonferroni",
                "shift_significant_fdr",
                "shift_significant_bonferroni",
            ]
        )

    fdr_q = benjamini_hochberg_fdr(raw_p_values, alpha=alpha)
    m = len(raw_p_values)

    for i, rec in enumerate(records):
        bonf = min(1.0, raw_p_values[i] * m)
        rec["p_value_fdr"] = fdr_q[i]
        rec["p_value_bonferroni"] = bonf
        rec["shift_significant_fdr"] = bool(fdr_q[i] < alpha)
        rec["shift_significant_bonferroni"] = bool(bonf < alpha)

    return pd.DataFrame(records)


def summarize_domain_shift(
    shift_df: pd.DataFrame, acquisition_differences: list[str] | None = None
) -> DomainShiftSummary:
    """Summarize feature-level shift findings into a compact DomainShiftSummary."""
    if shift_df.empty:
        return DomainShiftSummary(
            n_features_evaluated=0,
            n_features_significant_shift_fdr=0,
            n_features_significant_shift_bonferroni=0,
            max_absolute_smd=None,
            mean_absolute_smd=None,
            acquisition_differences=list(acquisition_differences or []),
        )

    n_eval = len(shift_df)
    n_fdr = int(shift_df["shift_significant_fdr"].sum())
    n_bonf = int(shift_df["shift_significant_bonferroni"].sum())

    abs_smd = shift_df["abs_smd"].dropna()
    max_smd = float(abs_smd.max()) if not abs_smd.empty else None
    mean_smd = float(abs_smd.mean()) if not abs_smd.empty else None

    return DomainShiftSummary(
        n_features_evaluated=n_eval,
        n_features_significant_shift_fdr=n_fdr,
        n_features_significant_shift_bonferroni=n_bonf,
        max_absolute_smd=max_smd,
        mean_absolute_smd=mean_smd,
        acquisition_differences=list(acquisition_differences or []),
    )
