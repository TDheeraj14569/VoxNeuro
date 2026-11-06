import sys
import zipfile
from hashlib import md5
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import soundfile as sf
from scripts import evaluate_model, inspect_dataset
from scripts.inspect_dataset import _validate_uci_members, extract_zip_once

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.dataset.uci import (
    load_uci_schema,
    validate_uci_feature_table,
)


def _wav_payload() -> bytes:
    stream = BytesIO()
    sf.write(stream, sustained_vowel(), 16000, format="WAV", subtype="PCM_16")
    return stream.getvalue()


def _archive(path: Path, member: str = "PD_AH/synthetic.wav") -> str:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, _wav_payload())
    return md5(path.read_bytes()).hexdigest()


def _uci_table() -> pd.DataFrame:
    ids = pd.Series(range(252)).repeat(3).reset_index(drop=True)
    classes = pd.Series([1] * 188 + [0] * 64).repeat(3).reset_index(drop=True)
    gender = (ids % 2).astype(int)
    schema = load_uci_schema()
    metadata = pd.DataFrame({"id": ids, "gender": gender})
    predictors = pd.DataFrame(
        np.full((756, len(schema["predictor_columns"])), 0.25),
        columns=schema["predictor_columns"],
    )
    return pd.concat((metadata, predictors, classes.rename("class")), axis=1)


def test_extract_zip_refreshes_partial_existing_output(tmp_path):
    archive = tmp_path / "PD_AH.zip"
    checksum = _archive(archive)
    destination = tmp_path / "interim" / "pd"
    destination.mkdir(parents=True)
    (destination / "partial.txt").write_text("interrupted", encoding="utf-8")

    extract_zip_once(
        archive,
        destination,
        expected_md5=checksum,
        expected_wavs=1,
        expected_class_folder="PD_AH",
    )

    assert (destination / "PD_AH" / "synthetic.wav").is_file()
    assert not (destination / "partial.txt").exists()
    assert len(list(destination.rglob("*.wav"))) == 1


def test_extract_zip_rejects_checksum_mismatch_without_touching_output(tmp_path):
    archive = tmp_path / "PD_AH.zip"
    _archive(archive)
    destination = tmp_path / "interim" / "pd"
    destination.mkdir(parents=True)
    sentinel = destination / "keep.txt"
    sentinel.write_text("prior output", encoding="utf-8")

    with pytest.raises(ValueError, match="Checksum mismatch"):
        extract_zip_once(
            archive,
            destination,
            expected_md5="0" * 32,
            expected_wavs=1,
            expected_class_folder="PD_AH",
        )

    assert sentinel.read_text(encoding="utf-8") == "prior output"


def test_extract_zip_rejects_path_traversal(tmp_path):
    archive = tmp_path / "PD_AH.zip"
    checksum = _archive(archive, "../escape.wav")

    with pytest.raises(ValueError, match="Unsafe archive member"):
        extract_zip_once(
            archive,
            tmp_path / "interim" / "pd",
            expected_md5=checksum,
            expected_wavs=1,
            expected_class_folder="PD_AH",
        )
    assert not (tmp_path / "escape.wav").exists()


def test_extract_zip_rejects_windows_absolute_member_paths(tmp_path):
    archive = tmp_path / "PD_AH.zip"
    checksum = _archive(archive, r"C:\outside\synthetic.wav")
    with pytest.raises(ValueError, match="Unsafe archive member"):
        extract_zip_once(
            archive,
            tmp_path / "interim" / "pd",
            expected_md5=checksum,
            expected_wavs=1,
            expected_class_folder="PD_AH",
        )
    assert not Path(r"C:\outside\synthetic.wav").exists()


def test_extract_zip_rejects_alternate_stream_member_paths(tmp_path):
    archive = tmp_path / "PD_AH.zip"
    checksum = _archive(archive, "PD_AH/synthetic.wav:payload")
    with pytest.raises(ValueError, match="Unsafe archive member"):
        extract_zip_once(
            archive,
            tmp_path / "interim" / "pd",
            expected_md5=checksum,
            expected_wavs=1,
            expected_class_folder="PD_AH",
        )


@pytest.mark.parametrize(
    ("members", "verbose"),
    [
        (["../outside.csv"], "-rw-r--r-- 0 0 10 Feb 1 ../outside.csv"),
        (["pd_speech_features.csv"], "lrwxrwxrwx 0 0 20 Feb 1 pd_speech_features.csv"),
        (["pd_speech_features.csv", "extra.txt"], "-rw-r--r-- 0 0 10 Feb 1 pd_speech_features.csv"),
    ],
)
def test_uci_archive_listing_rejects_unsafe_or_unexpected_members(members, verbose):
    with pytest.raises(ValueError):
        _validate_uci_members(members, verbose)


def test_uci_table_accepts_the_documented_repeated_participant_structure():
    original = _uci_table()
    before = original.copy(deep=True)
    frame = validate_uci_feature_table(original)
    pd.testing.assert_frame_equal(original, before)
    assert frame is not original
    assert frame.shape == (756, 755)
    assert frame.groupby("id").size().eq(3).all()
    assert frame.groupby("id")["class"].first().value_counts().to_dict() == {1: 188, 0: 64}


@pytest.mark.parametrize(
    ("column", "row", "value", "message"),
    [
        ("id", 755, 0, "exactly three recordings"),
        ("gender", 0, None, "missing values"),
        ("gender", 0, 2, "0/1 encoding"),
        ("class", 0, 0, "class counts"),
        ("PPE", 0, "corrupt", "nonnumeric"),
        ("PPE", 0, float("inf"), "non-finite"),
        ("PPE", 0, True, "Boolean"),
    ],
)
def test_uci_table_rejects_invalid_metadata_and_predictors(column, row, value, message):
    frame = _uci_table()
    if column == "class":
        frame.loc[frame["id"] == frame.at[row, "id"], column] = value
    else:
        if column == "PPE":
            frame[column] = frame[column].astype(object)
        frame.at[row, column] = value
    with pytest.raises(ValueError, match=message):
        validate_uci_feature_table(frame)


def test_uci_table_rejects_header_name_or_order_drift():
    frame = _uci_table()
    frame = frame[[*frame.columns[1:], frame.columns[0]]]
    with pytest.raises(ValueError, match="pinned release column names and order"):
        validate_uci_feature_table(frame)

    frame = _uci_table()
    frame = frame.rename(columns={frame.columns[2]: "renamed_predictor"})
    with pytest.raises(ValueError, match="pinned release column names and order"):
        validate_uci_feature_table(frame)


def test_uci_inspection_reextracts_csv_without_a_matching_archive_receipt(tmp_path, monkeypatch):
    raw = tmp_path / "data" / "raw" / "uci" / "download"
    raw.mkdir(parents=True)
    archive = raw / "pd_speech_features.rar"
    archive.write_bytes(b"source archive")
    output = tmp_path / "data" / "interim" / "uci"
    output.mkdir(parents=True)
    csv_path = output / "pd_speech_features.csv"
    csv_path.write_bytes(b"stale partial CSV")
    (output / "uci_extraction_receipt.json").write_text("[]", encoding="utf-8")
    docs = tmp_path / "docs" / "dataset"
    docs.mkdir(parents=True)
    monkeypatch.setattr(inspect_dataset, "ROOT", tmp_path)

    def fake_tar(args, **kwargs):
        if "-tf" in args:
            return SimpleNamespace(stdout="pd_speech_features.csv\n")
        if "-tvf" in args:
            return SimpleNamespace(stdout="-rw-r--r-- 0 0 16 Feb 1 pd_speech_features.csv\n")
        if "-xf" in args:
            Path(args[-1], "pd_speech_features.csv").write_bytes(b"fresh extracted CSV")
            return SimpleNamespace(stdout="")
        raise AssertionError(args)

    frame = pd.DataFrame({"id": [1, 1, 2], "class": [1, 1, 0], "gender": [0, 0, 1]})
    monkeypatch.setattr(inspect_dataset.subprocess, "run", fake_tar)
    monkeypatch.setattr(inspect_dataset, "_load_uci_table", lambda path: frame.copy())

    report = inspect_dataset.inspect_uci()
    assert report["rows"] == 3
    assert csv_path.read_bytes() == b"fresh extracted CSV"
    assert (output / "uci_extraction_receipt.json").is_file()


def test_uci_evaluation_rejects_non_object_source_receipt(tmp_path, monkeypatch, capsys):
    raw = tmp_path / "data" / "raw" / "uci" / "download"
    raw.mkdir(parents=True)
    (raw / "pd_speech_features.rar").write_bytes(b"archive")
    source_dir = tmp_path / "data" / "interim" / "uci"
    source_dir.mkdir(parents=True)
    (source_dir / "pd_speech_features.csv").write_text("table", encoding="utf-8")
    (source_dir / "uci_extraction_receipt.json").write_text("null", encoding="utf-8")
    monkeypatch.setattr(evaluate_model, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["evaluate_model.py", "--dataset", "uci"])

    assert evaluate_model.main() == 1
    assert "JSON object" in capsys.readouterr().out


def test_inspector_supports_uci_only_without_calling_uams(tmp_path, monkeypatch, capsys):
    temporary_root = tmp_path
    raw = temporary_root / "data" / "raw" / "uci" / "download"
    raw.mkdir(parents=True)
    (raw / "pd_speech_features.rar").write_bytes(b"synthetic UCI archive")
    (temporary_root / "docs" / "dataset").mkdir(parents=True)
    monkeypatch.setattr(inspect_dataset, "ROOT", temporary_root)
    monkeypatch.setattr(sys, "argv", ["inspect_dataset.py", "--dataset", "uci"])
    monkeypatch.setattr(
        inspect_dataset,
        "inspect_uams",
        lambda: pytest.fail("UCI-only inspection must not require UAMS files"),
    )
    frame = pd.DataFrame({"id": [1, 1, 2], "class": [1, 1, 0], "gender": [0, 0, 1]})

    def extract_uci(_archive, _output, csv_path):
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("synthetic csv", encoding="utf-8")
        return frame

    monkeypatch.setattr(inspect_dataset, "_extract_uci_rar", extract_uci)

    assert inspect_dataset.main() == 0
    output = capsys.readouterr().out
    assert "Inspecting UCI archive" in output
    assert "Inspecting UAMS archive" not in output
    assert not (temporary_root / "data" / "raw" / "uams").exists()
