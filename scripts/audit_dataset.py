"""Audit manifest integrity and demographic confounding."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from voxneuro.dataset.audit import demographic_summary
from voxneuro.dataset.validation import _is_true, validate_manifest

ROOT = Path(__file__).resolve().parents[1]


def duplicate_waveform_hash_rows(values: pd.Series) -> int:
    """Count only repeated, correctly formatted SHA-256 values; ignore bad/missing values."""
    hashes = values.fillna("").astype(str).str.strip().str.casefold()
    valid = hashes.loc[hashes.str.fullmatch(r"[0-9a-f]{64}")]
    return int(valid.duplicated(keep=False).sum())


def main() -> int:
    path = ROOT / "data" / "processed" / "feature_manifest.csv"
    if not path.is_file():
        print("Manifest not found. Run scripts/build_manifest.py first.")
        return 2
    try:
        frame = pd.read_csv(path)
    except (OSError, UnicodeDecodeError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
        print(f"Could not read manifest: {exc}")
        return 1
    issues = validate_manifest(frame, require_integrity=True)
    summary = demographic_summary(frame)
    age_data_errors = sum(
        int(summary.get(key, 0) or 0)
        for key in ("age_missing_count", "age_malformed_count", "age_out_of_range_count")
    )
    label_mismatches = (
        int((~frame["label_match"].map(_is_true)).sum()) if "label_match" in frame else None
    )
    duplicate_hash_rows = None
    if "waveform_sha256" in frame:
        duplicate_hash_rows = duplicate_waveform_hash_rows(frame["waveform_sha256"])
    payload = {
        "rows": len(frame),
        "class_counts": frame["class_label"].value_counts().to_dict()
        if "class_label" in frame
        else {},
        "issues": issues,
        "demographics": summary,
        "participant_id_count": int(frame["participant_id"].nunique())
        if "participant_id" in frame
        else 0,
        "duplicate_waveform_hash_rows": duplicate_hash_rows,
        "label_mapping_mismatches": label_mismatches,
        "invalid_age_values": age_data_errors,
    }
    print(json.dumps(payload, indent=2, default=str))
    if issues or label_mismatches or duplicate_hash_rows or age_data_errors:
        print("FAIL: manifest integrity checks did not pass.")
        return 1
    print("PASS: manifest integrity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
