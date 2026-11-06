import hashlib

import pandas as pd
from scripts import audit_dataset

from voxneuro.dataset.audit import demographic_summary
from voxneuro.dataset.validation import UAMS_DATASET_SOURCE


def test_demographic_summary_handles_malformed_missing_boolean_and_out_of_range_ages():
    frame = pd.DataFrame(
        {
            "participant_id": [f"p{i}" for i in range(8)],
            "class_label": ["PD", "HC", "PD", "HC", "PD", "HC", "PD", "HC"],
            "age": pd.Series(["forty", 60, None, True, -1, 200, "50", "70"], dtype="object"),
        }
    )
    summary = demographic_summary(frame)
    assert summary["age_missing_count"] == 1
    assert summary["age_malformed_count"] == 2
    assert summary["age_out_of_range_count"] == 2
    assert summary["age_by_label"]["HC"]["n"] == 2


def test_duplicate_hash_summary_ignores_missing_and_malformed_values():
    values = pd.Series(["a" * 64, "A" * 64, None, "", "invalid", "b" * 64])
    assert audit_dataset.duplicate_waveform_hash_rows(values) == 2


def test_dataset_audit_returns_nonzero_for_label_mismatch(tmp_path, monkeypatch, capsys):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"placeholder")
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame(
        {
            "sample_id": ["sample-1"],
            "participant_id": ["participant-1"],
            "audio_path": [str(audio)],
            "class_label": ["PD"],
            "age": [65],
            "sex": ["F"],
            "metadata_match": [True],
            "label_match": [False],
            "waveform_sha256": [hashlib.sha256(audio.read_bytes()).hexdigest()],
        }
    ).to_csv(processed / "feature_manifest.csv", index=False)
    monkeypatch.setattr(audit_dataset, "ROOT", tmp_path)

    assert audit_dataset.main() == 1
    assert "FAIL: manifest integrity checks did not pass." in capsys.readouterr().out


def test_dataset_audit_handles_missing_match_column_without_traceback(
    tmp_path, monkeypatch, capsys
):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"placeholder")
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame(
        {
            "sample_id": ["sample-1"],
            "participant_id": ["participant-1"],
            "audio_path": [str(audio)],
            "class_label": ["PD"],
            "metadata_match": [True],
            "waveform_sha256": [hashlib.sha256(audio.read_bytes()).hexdigest()],
        }
    ).to_csv(processed / "feature_manifest.csv", index=False)
    monkeypatch.setattr(audit_dataset, "ROOT", tmp_path)

    assert audit_dataset.main() == 1
    output = capsys.readouterr().out
    assert "label_match" in output
    assert "Traceback" not in output


def test_dataset_audit_reports_malformed_and_missing_ages_as_json(tmp_path, monkeypatch, capsys):
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame(
        {
            "sample_id": ["sample-1", "sample-2"],
            "participant_id": ["participant-1", "participant-2"],
            "audio_path": ["missing-1.wav", "missing-2.wav"],
            "class_label": ["PD", "HC"],
            "age": ["forty", None],
            "sex": ["F", "M"],
            "metadata_match": [True, True],
            "label_match": [True, True],
            "waveform_sha256": ["a" * 64, "b" * 64],
        }
    ).to_csv(processed / "feature_manifest.csv", index=False)
    monkeypatch.setattr(audit_dataset, "ROOT", tmp_path)

    assert audit_dataset.main() == 1
    output = capsys.readouterr().out
    payload = __import__("json").loads(output.split("\nFAIL:")[0])
    assert payload["demographics"]["age_malformed_count"] == 1
    assert payload["demographics"]["age_missing_count"] == 1


def test_dataset_audit_fails_for_boolean_age_values(tmp_path, monkeypatch, capsys):
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame(
        {
            "sample_id": ["sample-1"],
            "participant_id": ["sample-1"],
            "source_sample_key": ["sample-1"],
            "audio_path": ["missing/PD_AH/sample-1.wav"],
            "class_label": ["PD"],
            "source_label": ["PD"],
            "age": pd.Series([True], dtype="object"),
            "sex": ["F"],
            "dataset_source": [UAMS_DATASET_SOURCE],
            "metadata_match": [True],
            "label_match": [True],
            "waveform_sha256": ["a" * 64],
        }
    ).to_csv(processed / "feature_manifest.csv", index=False)
    monkeypatch.setattr(audit_dataset, "ROOT", tmp_path)

    assert audit_dataset.main() == 1
    output = capsys.readouterr().out
    payload = __import__("json").loads(output.split("\nFAIL:")[0])
    assert payload["invalid_age_values"] == 1
    assert "age is missing, nonnumeric" in " ".join(payload["issues"])
