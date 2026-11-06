"""Integrity checks for manifests and feature tables."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from voxneuro.exceptions import DatasetError

SOURCE_LABEL_MAP = {
    "pd": "PD",
    "pwpd": "PD",
    "parkinson disease": "PD",
    "parkinson's disease": "PD",
    "hc": "HC",
    "healthy": "HC",
    "healthy control": "HC",
    "control": "HC",
}
UAMS_DATASET_SOURCE = "UAMS Figshare DOI 10.6084/m9.figshare.23849127"
SOURCE_SEX_CODEBOOKS = {UAMS_DATASET_SOURCE: frozenset({"F", "M"})}


def normalize_label(value: object) -> str:
    """Map explicitly recognized diagnosis text to PD/HC; reject unknown values."""
    if value is None or pd.isna(value):
        raise ValueError("Missing diagnosis label.")
    label = str(value).strip().casefold()
    if label not in SOURCE_LABEL_MAP:
        raise ValueError(f"Unknown diagnosis label {value!r}; expected an explicit PD or HC label.")
    return SOURCE_LABEL_MAP[label]


def _is_true(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json_object(path: Path, description: str) -> dict[str, object]:
    """Read UTF-8 JSON that must have an object at its root."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} cannot be read as valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object at its root.")
    return value


def _path_label(path_value: object) -> str | None:
    if path_value is None or pd.isna(path_value):
        return None
    classes = {part.casefold() for part in Path(str(path_value)).parts} & {"pd_ah", "hc_ah"}
    if len(classes) != 1:
        return None
    return "PD" if "pd_ah" in classes else "HC"


def _path_sample_key(path_value: object) -> str | None:
    if path_value is None or pd.isna(path_value):
        return None
    stem = Path(str(path_value)).stem
    stem = re.sub(
        r"[_-][0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
        "",
        stem,
    )
    return stem.casefold()


def validate_manifest(
    frame: pd.DataFrame, require_files: bool = True, require_integrity: bool = False
) -> list[str]:
    """Return manifest defects, including cohort metadata and waveform integrity failures."""
    required = {"sample_id", "participant_id", "audio_path", "class_label"}
    if require_integrity:
        required |= {
            "metadata_match",
            "label_match",
            "waveform_sha256",
            "source_label",
            "source_sample_key",
            "age",
            "sex",
            "dataset_source",
        }
    missing = required - set(frame.columns)
    issues: list[str] = []
    if frame.empty:
        issues.append("Manifest contains no rows")
    if missing:
        issues.append(f"Manifest is missing required columns: {sorted(missing)}")
    if not {"sample_id", "participant_id", "audio_path", "class_label"}.issubset(frame.columns):
        return issues
    for column in ("sample_id", "participant_id", "audio_path", "class_label"):
        empty = frame[column].isna() | frame[column].astype(str).str.strip().eq("")
        if empty.any():
            issues.append(f"{column} contains {int(empty.sum())} missing or empty values")
    invalid_labels = sorted(set(frame["class_label"].dropna().astype(str)) - {"PD", "HC"})
    if invalid_labels:
        issues.append(f"class_label contains values other than exactly PD or HC: {invalid_labels}")
    if frame["sample_id"].duplicated().any():
        issues.append(f"sample_id contains {int(frame['sample_id'].duplicated().sum())} duplicates")
    participants = frame.dropna(subset=["participant_id", "class_label"])
    if participants.groupby("participant_id")["class_label"].nunique().gt(1).any():
        issues.append("participant_id maps to conflicting class labels")
    for column in ("metadata_match", "label_match"):
        if column in frame:
            failed = ~frame[column].map(_is_true)
            if failed.any():
                issues.append(f"{column} is false or missing for {int(failed.sum())} manifest rows")
    if require_integrity and required.issubset(frame.columns):
        label_mismatches = 0
        source_label_errors = 0
        sample_key_mismatches = 0
        for row in frame.to_dict("records"):
            class_label = str(row.get("class_label", "")).strip()
            try:
                source_label = normalize_label(row.get("source_label"))
            except ValueError:
                source_label_errors += 1
                continue
            if source_label != class_label or _path_label(row.get("audio_path")) != class_label:
                label_mismatches += 1
            path_key = _path_sample_key(row.get("audio_path"))
            source_key = str(row.get("source_sample_key", "")).strip().casefold()
            participant_id = str(row.get("participant_id", "")).strip().casefold()
            if path_key is None or source_key != path_key or participant_id != path_key:
                sample_key_mismatches += 1
        if source_label_errors:
            issues.append(f"source_label is missing or unrecognized for {source_label_errors} rows")
        if label_mismatches:
            issues.append(
                "class_label disagrees with explicit source label or audio folder for "
                f"{label_mismatches} rows"
            )
        if sample_key_mismatches:
            issues.append(
                "participant/source sample ID disagrees with audio filename for "
                f"{sample_key_mismatches} rows"
            )
        raw_ages = frame["age"]
        boolean_ages = raw_ages.map(lambda value: isinstance(value, (bool, np.bool_)))
        numeric_ages = pd.to_numeric(raw_ages.mask(boolean_ages), errors="coerce")
        invalid_ages = numeric_ages.isna() | numeric_ages.lt(0) | numeric_ages.gt(120)
        if invalid_ages.any():
            issues.append(
                "age is missing, nonnumeric, or outside the source metadata range in "
                f"{int(invalid_ages.sum())} rows"
            )
        normalized_ages = numeric_ages.mask(numeric_ages.lt(0) | numeric_ages.gt(120))
        normalized_sex = frame["sex"].astype("string").str.strip().str.upper()
        demographics = pd.DataFrame(
            {
                "participant_id": frame["participant_id"],
                "age": normalized_ages,
                "sex": normalized_sex,
            }
        )
        for column in ("age", "sex"):
            conflicts = demographics.groupby("participant_id", dropna=False)[column].nunique(
                dropna=False
            )
            if conflicts.gt(1).any():
                issues.append(f"Participant has conflicting {column} metadata.")

        sources = frame["dataset_source"].astype("string").str.strip()
        unregistered_sources = sorted(set(sources.dropna().tolist()) - set(SOURCE_SEX_CODEBOOKS))
        if unregistered_sources:
            issues.append(
                "No source-specific sex codebook is registered for dataset_source values: "
                f"{unregistered_sources}"
            )
        for source, allowed_values in SOURCE_SEX_CODEBOOKS.items():
            source_rows = sources.eq(source)
            invalid_sex = (
                source_rows & normalized_sex.notna() & ~normalized_sex.isin(allowed_values)
            )
            if invalid_sex.any():
                issues.append(
                    f"sex contains {int(invalid_sex.sum())} unrecognized values for "
                    f"dataset_source {source!r}; expected {sorted(allowed_values)}."
                )
        for column in ("sex", "dataset_source"):
            missing_values = frame[column].isna() | frame[column].astype(str).str.strip().eq("")
            if missing_values.any():
                issues.append(f"{column} is missing for {int(missing_values.sum())} rows")
    if "waveform_sha256" in frame:
        hash_values = frame["waveform_sha256"].fillna("").astype(str).str.strip().str.casefold()
        missing_hash = hash_values.eq("")
        if missing_hash.any():
            issues.append(f"waveform_sha256 is missing for {int(missing_hash.sum())} manifest rows")
        malformed_hash = ~missing_hash & ~hash_values.str.fullmatch(r"[0-9a-f]{64}")
        if malformed_hash.any():
            issues.append(
                f"waveform_sha256 is malformed for {int(malformed_hash.sum())} manifest rows"
            )
        hash_rows = frame.loc[~missing_hash].copy()
        hash_rows["__normalized_hash"] = hash_values.loc[~missing_hash]
        valid_hash_rows = hash_rows.loc[
            hash_rows["__normalized_hash"].str.fullmatch(r"[0-9a-f]{64}")
        ]
        duplicated_hash = valid_hash_rows["__normalized_hash"].duplicated(keep=False)
        if duplicated_hash.any():
            duplicates = valid_hash_rows.loc[duplicated_hash]
            cross_participant = int(
                (duplicates.groupby("__normalized_hash")["participant_id"].nunique() > 1).sum()
            )
            same_participant = int(
                (duplicates.groupby("__normalized_hash")["participant_id"].nunique() == 1).sum()
            )
            issues.append(
                "duplicate waveform hashes found "
                f"({cross_participant} across participants, {same_participant} within participants)"
            )
    absent = 0
    mismatched_hashes = 0
    if "audio_path" in frame:
        for row in frame.to_dict("records"):
            path_value = row.get("audio_path")
            if pd.isna(path_value) or not str(path_value).strip():
                continue
            audio_path = Path(str(path_value))
            if not audio_path.is_file():
                absent += 1
                continue
            expected_hash = str(row.get("waveform_sha256", "")).strip().casefold()
            if (
                re.fullmatch(r"[0-9a-f]{64}", expected_hash)
                and _sha256_file(audio_path) != expected_hash
            ):
                mismatched_hashes += 1
    if require_files and absent:
        issues.append(f"{absent} audio paths do not exist")
    if mismatched_hashes:
        issues.append(
            f"waveform_sha256 does not match the on-disk audio for {mismatched_hashes} rows"
        )
    return issues


def validate_features(frame: pd.DataFrame, feature_columns: list[str]) -> list[str]:
    """Report unexpected non-feature inputs and entirely invalid features."""
    issues: list[str] = []
    if frame.empty:
        issues.append("Feature table contains no rows")
    absent = set(feature_columns) - set(frame.columns)
    if absent:
        raise DatasetError(f"Missing feature columns: {sorted(absent)}")
    source = frame[feature_columns]
    numeric = pd.DataFrame(index=source.index)
    malformed_columns = {}
    boolean_columns = {}
    for column in feature_columns:
        raw = source[column]
        boolean_values = raw.map(lambda value: isinstance(value, (bool, np.bool_)))
        if boolean_values.any():
            boolean_columns[column] = int(boolean_values.sum())
        numeric[column] = pd.to_numeric(raw.mask(boolean_values), errors="coerce")
        # Only native pandas/NumPy missing values are permitted. Text such as
        # "nan" or "null" is malformed input, not an acoustic undefined value.
        present = raw.notna()
        malformed = present & numeric[column].isna() & ~boolean_values
        if malformed.any():
            malformed_columns[column] = int(malformed.sum())
    if boolean_columns:
        issues.append(
            f"Features contain Boolean values, not numeric measurements: {boolean_columns}"
        )
    if malformed_columns:
        issues.append(f"Features contain malformed non-numeric values: {malformed_columns}")
    if numeric.isin([float("inf"), float("-inf")]).any().any():
        issues.append("Features contain infinite values")
    all_missing = numeric.columns[numeric.isna().all()].tolist()
    if all_missing:
        issues.append(f"Features entirely missing: {all_missing}")
    forbidden_tokens = (
        "participant",
        "filename",
        "audio_path",
        "sample_id",
        "label",
        "diagnosis",
        "dataset",
    )
    bad = [
        column
        for column in feature_columns
        if any(token in column.lower() for token in forbidden_tokens)
    ]
    if bad:
        issues.append(f"Identity or label columns included as predictors: {bad}")
    return issues


def validate_extraction_receipt(
    receipt_path: Path,
    manifest_path: Path,
    feature_path: Path,
    expected_schema_version: str,
    expected_schema_fingerprint: str | None = None,
    expected_feature_config_fingerprint: str | None = None,
    expected_preprocessing_config_fingerprint: str | None = None,
    expected_code_version: str | None = None,
) -> list[str]:
    """Prevent modeling with stale, blocked, or schema-incompatible extraction outputs."""
    if not receipt_path.is_file():
        return ["Feature extraction receipt is missing; rerun scripts/extract_features.py."]
    if not manifest_path.is_file() or not feature_path.is_file():
        return ["Manifest or feature table is missing."]
    try:
        receipt = read_json_object(receipt_path, "Feature extraction receipt")
    except ValueError as exc:
        return [f"Feature extraction receipt cannot be read: {exc}"]
    issues = []
    if receipt.get("status") not in {"complete", "accepted_reviewed_exclusions"}:
        issues.append("Feature extraction is blocked by unreviewed or failed recordings.")
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    feature_hash = hashlib.sha256(feature_path.read_bytes()).hexdigest()
    if receipt.get("manifest_sha256") != manifest_hash:
        issues.append("Feature extraction receipt does not match the current manifest.")
    if receipt.get("feature_table_sha256") != feature_hash:
        issues.append("Feature extraction receipt does not match the current feature table.")
    if receipt.get("feature_schema_version") != expected_schema_version:
        issues.append("Feature extraction receipt uses a different feature schema version.")
    expected = {
        "feature_schema_fingerprint": expected_schema_fingerprint,
        "feature_config_fingerprint": expected_feature_config_fingerprint,
        "preprocessing_config_fingerprint": expected_preprocessing_config_fingerprint,
        "code_version": expected_code_version,
    }
    for key, value in expected.items():
        if value is not None and receipt.get(key) != value:
            issues.append(f"Feature extraction receipt has stale or incompatible {key}.")
    return issues


def validate_evaluation_receipt(
    receipt_path: Path,
    manifest_path: Path,
    feature_path: Path,
    metrics_path: Path,
    expected_schema_version: str,
    expected_code_version: str | None = None,
    expected_schema_fingerprint: str | None = None,
    expected_feature_config_fingerprint: str | None = None,
    expected_preprocessing_config_fingerprint: str | None = None,
    predictions_path: Path | None = None,
) -> list[str]:
    """Require grouped evaluation outputs from the current dataset and feature table."""
    paths = (manifest_path, feature_path, metrics_path)
    if not receipt_path.is_file():
        return [
            "Model evaluation receipt is missing; run scripts/evaluate_model.py --dataset uams."
        ]
    if any(not path.is_file() for path in paths):
        return ["Manifest, feature table, or grouped evaluation metrics are missing."]
    try:
        receipt = read_json_object(receipt_path, "Model evaluation receipt")
    except ValueError as exc:
        return [f"Model evaluation receipt cannot be read: {exc}"]
    expected = {
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "feature_table_sha256": hashlib.sha256(feature_path.read_bytes()).hexdigest(),
        "metrics_sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
        "feature_schema_version": expected_schema_version,
        "status": "complete",
        "dataset": "uams",
    }
    if expected_code_version is not None:
        expected["code_version"] = expected_code_version
    if expected_schema_fingerprint is not None:
        expected["feature_schema_fingerprint"] = expected_schema_fingerprint
    if expected_feature_config_fingerprint is not None:
        expected["feature_config_fingerprint"] = expected_feature_config_fingerprint
    if expected_preprocessing_config_fingerprint is not None:
        expected["preprocessing_config_fingerprint"] = expected_preprocessing_config_fingerprint
    if predictions_path is not None:
        if not predictions_path.is_file():
            return [
                *[
                    f"Model evaluation receipt has stale or incompatible {key}."
                    for key, value in expected.items()
                    if receipt.get(key) != value
                ],
                "Out-of-fold prediction table is missing.",
            ]
        expected["predictions_sha256"] = hashlib.sha256(predictions_path.read_bytes()).hexdigest()
    return [
        f"Model evaluation receipt has stale or incompatible {key}."
        for key, value in expected.items()
        if receipt.get(key) != value
    ]


def validate_nested_evaluation_receipt(
    receipt_path: Path,
    expected_fields: dict[str, object],
    artifacts: dict[str, Path],
) -> list[str]:
    """Check nested-CV provenance and hashes before model training consumes it."""
    if not receipt_path.is_file():
        return [
            "Nested model evaluation receipt is missing; run scripts/evaluate_nested_models.py."
        ]
    try:
        receipt = read_json_object(receipt_path, "Nested evaluation receipt")
    except ValueError as exc:
        return [f"Nested evaluation receipt cannot be read: {exc}"]
    issues = [
        f"Nested evaluation receipt has stale or incompatible {key}."
        for key, value in expected_fields.items()
        if receipt.get(key) != value
    ]
    for digest_key, path in artifacts.items():
        if not path.is_file():
            issues.append(f"Nested evaluation artifact {path.name} is missing.")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if receipt.get(digest_key) != actual:
            issues.append(f"Nested evaluation receipt has stale or incompatible {digest_key}.")
    return issues
