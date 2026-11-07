"""Strict validation for the fixed UCI Parkinson's voice feature-table release."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from voxneuro.config import PROJECT_ROOT

EXPECTED_UCI_SHAPE = (756, 755)
EXPECTED_UCI_PARTICIPANTS = 252
EXPECTED_UCI_RECORDINGS_PER_PARTICIPANT = 3
EXPECTED_UCI_PARTICIPANT_CLASS_COUNTS = {0: 64, 1: 188}
UCI_METADATA_COLUMNS = {"id", "class", "gender"}
UCI_SCHEMA_PATH = PROJECT_ROOT / "configs" / "uci470_schema.json"
EXPECTED_UCI_ORDERED_HEADER_SHA256 = (
    "55311b3a9f947d378df1a92b83dd322aff98553c951048cba127dc55cb0a647b"
)


def load_uci_schema() -> dict[str, object]:
    """Load and self-check the pinned ordered header manifest for UCI dataset 470."""
    try:
        raw = UCI_SCHEMA_PATH.read_bytes()
        schema = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"UCI 470 schema manifest cannot be read: {exc}") from exc
    if not isinstance(schema, dict):
        raise ValueError("UCI 470 schema manifest must be a JSON object.")
    required = {
        "manifest_version",
        "dataset_id",
        "dataset_name",
        "doi",
        "publisher_page",
        "official_download_url",
        "rar_member",
        "csv_member",
        "csv_header_record_index",
        "expected_rows",
        "expected_columns",
        "expected_participants",
        "recordings_per_participant",
        "participant_class_counts",
        "gender_codes",
        "metadata_columns",
        "predictor_columns",
        "ordered_columns",
        "ordered_header_sha256",
        "publisher_archive_sha256",
    }
    if required - schema.keys():
        raise ValueError(
            f"UCI 470 schema manifest is missing fields: {sorted(required - schema.keys())}."
        )
    columns = schema["ordered_columns"]
    predictors = schema["predictor_columns"]
    metadata = schema["metadata_columns"]
    if (
        not isinstance(columns, list)
        or not all(isinstance(column, str) and column for column in columns)
        or len(columns) != len(set(columns))
        or not isinstance(predictors, list)
        or not all(isinstance(column, str) and column for column in predictors)
        or len(predictors) != len(set(predictors))
        or not isinstance(metadata, list)
        or len(metadata) != 3
        or columns != [*metadata[:2], *predictors, metadata[2]]
        or metadata != ["id", "gender", "class"]
    ):
        raise ValueError("UCI 470 schema manifest has an invalid ordered column definition.")
    actual_header_hash = hashlib.sha256(
        json.dumps(columns, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (
        schema["ordered_header_sha256"] != EXPECTED_UCI_ORDERED_HEADER_SHA256
        or actual_header_hash != EXPECTED_UCI_ORDERED_HEADER_SHA256
        or schema["expected_rows"] != EXPECTED_UCI_SHAPE[0]
        or schema["expected_columns"] != EXPECTED_UCI_SHAPE[1]
        or len(predictors) != EXPECTED_UCI_SHAPE[1] - len(UCI_METADATA_COLUMNS)
        or schema["expected_participants"] != EXPECTED_UCI_PARTICIPANTS
        or schema["recordings_per_participant"] != EXPECTED_UCI_RECORDINGS_PER_PARTICIPANT
        or schema["participant_class_counts"] != {"0": 64, "1": 188}
        or schema["gender_codes"] != [0, 1]
        or schema["dataset_id"] != 470
        or schema["manifest_version"] != 1
        or type(schema["csv_header_record_index"]) is not int
        or schema["csv_header_record_index"] != 1
        or schema["doi"] != "10.24432/C5MS4X"
        or schema["publisher_page"]
        != "https://archive.ics.uci.edu/dataset/470/parkinson%2Bs%2Bdisease%2Bclassification"
        or schema["official_download_url"]
        != "https://archive.ics.uci.edu/static/public/470/parkinson%2Bs%2Bdisease%2Bclassification.zip"
        or schema["rar_member"] != "pd_speech_features.rar"
        or schema["csv_member"] != "pd_speech_features.csv"
        or type(schema["expected_rows"]) is not int
        or type(schema["expected_columns"]) is not int
        or type(schema["expected_participants"]) is not int
        or type(schema["recordings_per_participant"]) is not int
        or schema["publisher_archive_sha256"] is not None
    ):
        raise ValueError("UCI 470 schema manifest differs from the pinned release contract.")
    return schema


def uci_schema_fingerprint() -> str:
    """Return the integrity fingerprint for the checked-in schema manifest bytes."""
    load_uci_schema()
    return hashlib.sha256(UCI_SCHEMA_PATH.read_bytes()).hexdigest()


def _numeric_metadata(frame: pd.DataFrame, column: str) -> pd.Series:
    raw = frame[column]
    if raw.isna().any():
        raise ValueError(f"UCI metadata column {column!r} contains missing values.")
    if raw.map(lambda value: isinstance(value, (bool, np.bool_))).any():
        raise ValueError(f"UCI metadata column {column!r} contains Boolean values.")
    try:
        numeric = pd.to_numeric(raw, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"UCI metadata column {column!r} contains nonnumeric values.") from exc
    values = numeric.to_numpy(dtype=np.float64)
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ValueError(f"UCI metadata column {column!r} must contain finite integers.")
    return numeric.astype("int64")


def validate_uci_feature_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate a table against the pinned official header and return a normalized copy."""
    frame = frame.copy(deep=True)
    schema = load_uci_schema()
    if frame.shape != EXPECTED_UCI_SHAPE:
        raise ValueError(
            f"UCI feature table has shape {frame.shape}; expected "
            f"{EXPECTED_UCI_SHAPE[0]} recordings by {EXPECTED_UCI_SHAPE[1]} columns."
        )
    if list(frame.columns) != schema["ordered_columns"]:
        raise ValueError(
            "UCI CSV header does not exactly match the pinned release column names and order."
        )
    if not UCI_METADATA_COLUMNS.issubset(frame.columns):
        raise ValueError("UCI feature table is missing id, class, or gender metadata.")

    for column in ("id", "class", "gender"):
        frame[column] = _numeric_metadata(frame, column)
    if not frame["class"].isin({0, 1}).all():
        raise ValueError("UCI class labels must be exactly 0 or 1.")
    if not frame["gender"].isin({0, 1}).all():
        raise ValueError("UCI gender metadata must use the documented 0/1 encoding.")

    participant_counts = frame.groupby("id", sort=False).size()
    if len(participant_counts) != EXPECTED_UCI_PARTICIPANTS:
        raise ValueError(
            f"UCI table has {len(participant_counts)} participants; expected "
            f"{EXPECTED_UCI_PARTICIPANTS}."
        )
    if not participant_counts.eq(EXPECTED_UCI_RECORDINGS_PER_PARTICIPANT).all():
        raise ValueError("Every UCI participant must have exactly three recordings.")
    if frame.groupby("id")["class"].nunique().gt(1).any():
        raise ValueError("UCI participant diagnosis labels disagree across recordings.")
    if frame.groupby("id")["gender"].nunique().gt(1).any():
        raise ValueError("UCI participant gender metadata disagrees across recordings.")
    class_counts = frame.groupby("id")["class"].first().value_counts().to_dict()
    if class_counts != EXPECTED_UCI_PARTICIPANT_CLASS_COUNTS:
        raise ValueError(
            "UCI participant class counts do not match the documented release "
            "(64 controls, 188 Parkinson's participants)."
        )

    predictors = frame.drop(columns=sorted(UCI_METADATA_COLUMNS))
    boolean_columns = [
        column
        for column in predictors
        if predictors[column].map(lambda value: isinstance(value, (bool, np.bool_))).any()
    ]
    if boolean_columns:
        raise ValueError(f"UCI predictors contain Boolean values: {boolean_columns[:10]}.")
    try:
        numeric = predictors.apply(pd.to_numeric, errors="raise")
    except (TypeError, ValueError) as exc:
        raise ValueError("UCI acoustic predictors contain nonnumeric values.") from exc
    if numeric.isna().any().any():
        raise ValueError("UCI acoustic predictors contain missing or malformed values.")
    if not np.isfinite(numeric.to_numpy(dtype=np.float64)).all():
        raise ValueError("UCI acoustic predictors contain infinite or non-finite values.")
    frame.loc[:, numeric.columns] = numeric
    return frame


def load_uci_feature_table(path: Path) -> pd.DataFrame:
    """Read the official 756-row table and reject malformed metadata or predictors."""
    try:
        schema = load_uci_schema()
        frame = pd.read_csv(path, header=int(schema["csv_header_record_index"]))
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not read the UCI feature table: {exc}") from exc
    return validate_uci_feature_table(frame)
