"""Calibration utilities that require participant-independent predictions."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import brier_score_loss


def calibration_summary(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    """Return the Brier score only for externally generated out-of-fold probabilities."""
    labels = np.asarray(y_true)
    probabilities = np.asarray(probabilities, dtype=float)
    if labels.ndim != 1 or probabilities.ndim != 1:
        raise ValueError("Labels and probabilities must be one-dimensional arrays.")
    try:
        numeric_labels = labels.astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Calibration labels must be binary values 0 or 1.") from exc
    if not np.isfinite(numeric_labels).all() or not np.isin(numeric_labels, [0, 1]).all():
        raise ValueError("Calibration labels must be finite binary values 0 or 1.")
    if len(numeric_labels) != len(probabilities) or not np.isfinite(probabilities).all():
        raise ValueError("Labels and finite probabilities must have matching lengths.")
    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Calibration input must be probabilities in [0, 1].")
    return {
        "brier_score": float(brier_score_loss(numeric_labels.astype(int), probabilities)),
        "n": int(len(numeric_labels)),
    }
