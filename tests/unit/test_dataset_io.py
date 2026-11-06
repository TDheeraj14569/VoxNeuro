import hashlib

import pytest

from voxneuro.dataset.loader import load_feature_table
from voxneuro.dataset.manifest import audio_manifest, sha256_file
from voxneuro.exceptions import DatasetError


def test_load_feature_table_requires_path_and_identity_columns(tmp_path):
    with pytest.raises(DatasetError, match="does not exist"):
        load_feature_table(tmp_path / "missing.csv")

    path = tmp_path / "bad.csv"
    path.write_text("feature\n0.5\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="missing required columns"):
        load_feature_table(path)

    path.write_text("sample_id,participant_id,class_label,f0\ns1,p1,PD,110\n", encoding="utf-8")
    frame = load_feature_table(path)
    assert frame.iloc[0]["sample_id"] == "s1"


def test_generic_audio_manifest_never_guesses_class_and_uses_content_hash(tmp_path):
    audio_dir = tmp_path / "unexpected-folder"
    audio_dir.mkdir()
    audio = audio_dir / "subject-1.wav"
    audio.write_bytes(b"synthetic wav payload")

    inferred = audio_manifest(tmp_path, "synthetic-source")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    assert inferred.loc[0, "class_label"] is None
    assert inferred.loc[0, "waveform_sha256"] == digest
    assert sha256_file(audio) == digest

    explicit = audio_manifest(tmp_path, "synthetic-source", class_label="PD")
    assert explicit.loc[0, "class_label"] == "PD"
