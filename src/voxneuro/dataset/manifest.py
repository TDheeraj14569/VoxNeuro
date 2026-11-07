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
        file_hash = sha256_file(path)
        try:
            rel_path = path.relative_to(root).as_posix()
        except ValueError:
            rel_path = str(path.resolve())
        rows.append(
            {
                "sample_id": f"{dataset_source}-{file_hash[:12]}",
                "participant_id": path.stem,
                "audio_path": rel_path,
                "class_label": class_label,
                "dataset_source": dataset_source,
                "waveform_sha256": file_hash,
            }
        )
    return pd.DataFrame(rows)
