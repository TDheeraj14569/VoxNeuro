"""Manifest building helpers with pseudonymous sample IDs."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audio_manifest(root: Path, dataset_source: str, class_label: str | None = None) -> pd.DataFrame:
    """List WAV files and basic identifiers; never infer labels from arbitrary paths."""
    rows = []
    for path in sorted(root.rglob("*.wav")):
        rows.append(
            {
                "sample_id": f"{dataset_source}-{sha256_file(path)[:12]}",
                "participant_id": path.stem,
                "audio_path": str(path.resolve()),
                "class_label": class_label,
                "dataset_source": dataset_source,
                "waveform_sha256": sha256_file(path),
            }
        )
    return pd.DataFrame(rows)
