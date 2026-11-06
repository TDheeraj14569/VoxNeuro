"""Synthetic grouped tabular data for split tests; not clinical data."""

import numpy as np
import pandas as pd


def binary_groups(n_participants: int = 30, repeats: int = 2):
    rng = np.random.default_rng(4)
    labels = np.tile([0, 1], n_participants // 2)
    groups = np.repeat([f"p{i:03d}" for i in range(n_participants)], repeats)
    y = np.repeat(labels, repeats)
    signal = y + rng.normal(0, 0.7, size=len(y))
    frame = pd.DataFrame({"feature_a": signal, "feature_b": rng.normal(size=len(y))})
    return frame, y, groups
