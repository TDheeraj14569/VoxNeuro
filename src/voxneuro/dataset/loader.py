"""Tabular dataset readers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from voxneuro.exceptions import DatasetError


def load_feature_table(path: Path) -> pd.DataFrame:
    """Load a previously extracted table and require identity/label columns."""
    if not path.is_file():
        raise DatasetError(f"Feature table does not exist: {path}")
    frame = pd.read_csv(path)
    required = {"sample_id", "participant_id", "class_label"}
    missing = required - set(frame.columns)
    if missing:
        raise DatasetError(f"Feature table is missing required columns: {sorted(missing)}")
    return frame
