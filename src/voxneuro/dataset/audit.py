"""Dataset summary and demographic confounding audit."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu


def demographic_summary(frame: pd.DataFrame) -> dict[str, object]:
    """Summarize age/sex by label and calculate an age-distribution test when possible."""
    result: dict[str, object] = {
        "n_records": len(frame),
        "n_participants": frame.get("participant_id", pd.Series(dtype=str)).nunique(),
    }
    if {"age", "class_label"} <= set(frame.columns):
        source_age = frame["age"]
        numeric_age = pd.to_numeric(source_age, errors="coerce")
        boolean_age = source_age.map(lambda value: isinstance(value, (bool, np.bool_)))
        numeric_age = numeric_age.mask(boolean_age)
        result["age_missing_count"] = int(source_age.isna().sum())
        result["age_malformed_count"] = int((source_age.notna() & numeric_age.isna()).sum())
        out_of_range = numeric_age.notna() & ((numeric_age < 0) | (numeric_age > 120))
        result["age_out_of_range_count"] = int(out_of_range.sum())
        numeric_age = numeric_age.mask(out_of_range)
        age = pd.DataFrame({"age": numeric_age, "class_label": frame["class_label"]}).dropna(
            subset=["age", "class_label"]
        )
        groups = {
            label: values["age"].astype(float) for label, values in age.groupby("class_label")
        }
        result["age_by_label"] = {
            str(label): {
                "n": len(values),
                "mean": float(values.mean()),
                "sd": float(values.std(ddof=1)),
                "median": float(values.median()),
                "min": float(values.min()),
                "max": float(values.max()),
            }
            for label, values in groups.items()
        }
        if len(groups) == 2 and all(len(values) > 1 for values in groups.values()):
            a, b = list(groups.values())
            test = mannwhitneyu(a, b, alternative="two-sided")
            pooled = (
                (a.var(ddof=1) * (len(a) - 1) + b.var(ddof=1) * (len(b) - 1))
                / max(1, len(a) + len(b) - 2)
            ) ** 0.5
            result["age_mann_whitney_u"] = float(test.statistic)
            result["age_mann_whitney_p"] = float(test.pvalue)
            result["age_standardized_mean_difference"] = (
                float((a.mean() - b.mean()) / pooled) if pooled else None
            )
    if {"sex", "class_label"} <= set(frame.columns):
        result["sex_counts_by_label"] = (
            frame.groupby(["class_label", "sex"], dropna=False)
            .size()
            .unstack(fill_value=0)
            .to_dict()
        )
    return result
