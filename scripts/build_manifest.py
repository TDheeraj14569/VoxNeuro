"""Build a pseudonymous UAMS audio/metadata manifest."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
import soundfile as sf

from voxneuro.dataset.validation import normalize_label

ROOT = Path(__file__).resolve().parents[1]


def sample_key(path: Path) -> str:
    stem = path.stem
    return re.sub(
        r"[_-][0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        "",
        stem,
    )


def normalize_sample_id(value: object) -> str:
    if pd.isna(value):
        raise ValueError("Missing sample ID in demographics workbook.")
    value = str(value).strip()
    value = re.sub(r"\.wav$", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"[_-][0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        "",
        value,
    )
    return value.casefold()


def class_from_audio_path(path: Path) -> str:
    classes = {part.casefold() for part in path.parts} & {"pd_ah", "hc_ah"}
    if len(classes) != 1:
        raise ValueError(f"Audio path must contain exactly one PD_AH or HC_AH folder: {path}")
    return "PD" if "pd_ah" in classes else "HC"


def validate_duplicate_metadata(
    demo: pd.DataFrame,
    key_column: str,
    label_column: str,
    identity_column: str | None = None,
) -> None:
    """Reject duplicate normalized IDs whose diagnosis or metadata disagree."""
    metadata_columns = [
        column for column in demo.columns if column not in {key_column, identity_column}
    ]
    for key, rows in demo.groupby(key_column, dropna=False):
        if len(rows) < 2:
            continue
        for column in metadata_columns:
            values = rows[column]
            if column == label_column:
                values = values.map(normalize_label)
            comparable = values.map(
                lambda value: "<MISSING>" if pd.isna(value) else str(value).strip().casefold()
            )
            if comparable.nunique(dropna=False) > 1:
                raise ValueError(
                    f"Conflicting workbook rows for normalized sample ID {key!r} "
                    f"in column {column!r}."
                )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    raw = ROOT / "data" / "raw" / "uams"
    files = list((ROOT / "data" / "interim" / "uams").rglob("*.wav"))
    workbook = raw / "Demographics_age_sex.xlsx"
    if not files or not workbook.is_file():
        print("UAMS WAV files/workbook missing. Run scripts/inspect_dataset.py first.")
        return 2
    tables = pd.read_excel(workbook, sheet_name=None)
    if "Parselmouth" not in tables:
        print(f"Expected workbook sheet 'Parselmouth'; found {list(tables)}")
        return 2
    demo = tables["Parselmouth"].copy()
    normalized = {str(c).strip().casefold().replace(" ", "_"): c for c in demo.columns}
    id_col = next(
        (original for key, original in normalized.items() if "sample" in key and "id" in key), None
    )
    age_col = next((original for key, original in normalized.items() if "age" in key), None)
    sex_col = next(
        (
            original
            for key, original in normalized.items()
            if key in {"sex", "gender"} or "sex" in key
        ),
        None,
    )
    label_col = next(
        (
            original
            for key, original in normalized.items()
            if key in {"label", "group", "diagnosis", "class"}
        ),
        None,
    )
    if id_col is None:
        print(f"Could not identify sample ID column in workbook: {list(demo.columns)}")
        return 2
    if label_col is None or age_col is None or sex_col is None:
        print("The Parselmouth sheet must contain Sample ID, Label, Age, and Sex columns.")
        return 2
    demo["__sample_key"] = demo[id_col].map(normalize_sample_id)
    try:
        demo["__normalized_label"] = demo[label_col].map(normalize_label)
        validate_duplicate_metadata(
            demo.drop(columns=["__normalized_label"]), "__sample_key", label_col, id_col
        )
    except ValueError as exc:
        print(f"Invalid demographics workbook: {exc}")
        return 1
    demo = demo.drop_duplicates("__sample_key")
    lookup = demo.set_index("__sample_key")
    rows = []
    for path in sorted(files):
        try:
            label = class_from_audio_path(path)
        except ValueError as exc:
            print(f"Invalid audio folder mapping: {exc}")
            return 1
        key = sample_key(path).casefold()
        metadata = lookup.loc[key] if key in lookup.index else None
        info = sf.info(path)
        rows.append(
            {
                "sample_id": f"uams-{len(rows) + 1:03d}",
                "participant_id": key,
                "source_sample_key": key,
                "waveform_sha256": sha256_file(path),
                "audio_path": str(path.resolve()),
                "class_label": label,
                "dataset_source": "UAMS Figshare DOI 10.6084/m9.figshare.23849127",
                "original_sampling_rate_hz": int(info.samplerate),
                "channels": int(info.channels),
                "recording_duration_seconds": float(info.duration),
                "recording_task": "sustained vowel /a/ via telephone voice message",
                "recording_device": "participant telephone; model unspecified",
                "age": metadata[age_col] if metadata is not None and age_col else None,
                "sex": metadata[sex_col] if metadata is not None and sex_col else None,
                "source_label": metadata[label_col]
                if metadata is not None and label_col
                else label,
                "metadata_match": metadata is not None,
                "label_match": metadata is not None and metadata["__normalized_label"] == label,
            }
        )
    manifest = pd.DataFrame(rows)
    output = ROOT / "data" / "processed" / "feature_manifest.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(output, index=False)
    unmatched = int((~manifest["metadata_match"]).sum())
    print(f"Wrote {len(manifest)} pseudonymous rows to {output}")
    print(
        f"Class counts: {manifest['class_label'].value_counts().to_dict()}; "
        f"metadata matches: {len(manifest) - unmatched}; unmatched: {unmatched}"
    )
    label_mismatches = int((~manifest["label_match"]).sum())
    print(f"Workbook label mapping mismatches: {label_mismatches}")
    if unmatched or label_mismatches:
        print(
            "The source workbook and audio naming keys differ; inspect the ID mapping before "
            "modeling."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
