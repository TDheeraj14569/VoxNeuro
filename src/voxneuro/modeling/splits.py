"""Participant-disjoint cross-validation splits with explicit leakage checks."""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

from voxneuro.exceptions import DatasetError


def grouped_splits(y: np.ndarray, groups: np.ndarray, n_splits: int = 5, random_seed: int = 2026):
    """Yield stratified grouped folds; reject missing IDs and any group overlap."""
    raw_y = np.asarray(y)
    if raw_y.dtype.kind not in "iuf" or raw_y.dtype.kind == "b":
        raise DatasetError("Labels must be numeric binary values coded 0 (HC) and 1 (PD).")
    if not np.isfinite(raw_y).all() or not np.isin(raw_y, [0, 1]).all():
        raise DatasetError("Labels must contain only finite binary values coded 0 (HC) and 1 (PD).")
    y = raw_y.astype(int)
    groups = np.asarray(groups)
    if isinstance(n_splits, bool) or not isinstance(n_splits, int) or n_splits < 2:
        raise DatasetError("Grouped cross-validation requires an integer fold count of at least 2.")
    if (
        y.ndim != 1
        or groups.ndim != 1
        or len(y) != len(groups)
        or len(y) == 0
        or pd_is_missing(groups).any()
        or pd_is_missing(y).any()
    ):
        raise DatasetError(
            "Binary labels and participant IDs must be present as 1D arrays "
            "of matching nonzero length."
        )
    if not set(np.unique(y)).issubset({0, 1}) or len(np.unique(y)) != 2:
        raise DatasetError("Both binary classes 0 (HC) and 1 (PD) are required for evaluation.")
    if len(np.unique(groups)) < n_splits:
        raise DatasetError(f"Only {len(np.unique(groups))} participants for {n_splits} folds.")
    group_labels = {}
    for group, label in zip(groups, y, strict=True):
        try:
            group_labels.setdefault(group, set()).add(int(label))
        except TypeError as exc:
            raise DatasetError("Participant IDs must be hashable values.") from exc
    if any(len(labels) != 1 for labels in group_labels.values()):
        raise DatasetError("Each participant must have exactly one consistent diagnosis label.")
    participants_per_class = {
        label: sum(labels == {label} for labels in group_labels.values()) for label in (0, 1)
    }
    if min(participants_per_class.values()) < n_splits:
        raise DatasetError(
            f"Each class needs at least {n_splits} distinct participants for {n_splits}-fold CV."
        )

    def _generate_folds():
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_seed)
        for train, test in splitter.split(np.zeros(len(y)), y, groups):
            overlap = set(groups[train]) & set(groups[test])
            if overlap:
                raise DatasetError(f"Participant leakage detected: {len(overlap)} overlapping IDs.")
            if set(np.unique(y[train])) != {0, 1} or set(np.unique(y[test])) != {0, 1}:
                raise DatasetError(
                    "A grouped fold does not contain both diagnosis classes; reduce the fold count."
                )
            yield train, test

    return _generate_folds()


def pd_is_missing(values: np.ndarray) -> np.ndarray:
    """Use pandas' missing-value semantics without exposing arbitrary ID values."""
    import pandas as pd

    return pd.isna(values)
