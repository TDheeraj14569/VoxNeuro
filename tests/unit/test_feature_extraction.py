import hashlib
import json
import sys

import pandas as pd
from scripts import extract_features
from scripts.extract_features import _reviewed_exclusion_failures


def test_partial_extraction_requires_explicit_reviewed_policy():
    statuses = [
        {
            "sample_id": "uams-045",
            "extraction_status": "failed",
            "failure_reason": "Too many samples are clipped.",
        }
    ]
    policy = {
        "reviewed_exclusions": {
            "uams-045": {
                "review_status": "reviewed",
                "category": "clipping",
                "expected_failure_fragment": "Too many samples are clipped",
            }
        }
    }
    assert not _reviewed_exclusion_failures(statuses, policy, requested=False)[0]
    assert _reviewed_exclusion_failures(statuses, policy, requested=True) == (True, [])


def test_reviewed_exclusion_does_not_allow_different_failure_modes():
    statuses = [
        {
            "sample_id": "uams-045",
            "extraction_status": "failed",
            "failure_reason": "Audio is too short.",
        }
    ]
    policy = {
        "reviewed_exclusions": {
            "uams-045": {
                "review_status": "reviewed",
                "category": "clipping",
                "expected_failure_fragment": "Too many samples are clipped",
            }
        }
    }
    assert not _reviewed_exclusion_failures(statuses, policy, requested=True)[0]


def test_extraction_script_validates_manifest_before_processing(tmp_path, monkeypatch):
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"placeholder")
    pd.DataFrame(
        {
            "sample_id": ["sample-1"],
            "participant_id": ["participant-1"],
            "audio_path": [str(audio)],
            "class_label": ["PD"],
            "metadata_match": [True],
            "label_match": [False],
            "waveform_sha256": [hashlib.sha256(audio.read_bytes()).hexdigest()],
        }
    ).to_csv(processed / "feature_manifest.csv", index=False)
    monkeypatch.setattr(extract_features, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["extract_features.py"])

    assert extract_features.main() == 1
    receipt = json.loads((processed / "feature_extraction_receipt.json").read_text())
    assert receipt["status"] == "blocked_invalid_manifest"
    assert not (processed / "voice_features.csv").exists()


def test_partial_failure_cannot_write_successful_feature_table(tmp_path, monkeypatch):
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    audio = tmp_path / "PD_AH" / "sample-1.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"placeholder")
    pd.DataFrame(
        {
            "sample_id": ["sample-1"],
            "participant_id": ["sample-1"],
            "source_sample_key": ["sample-1"],
            "audio_path": [str(audio)],
            "class_label": ["PD"],
            "source_label": ["PD"],
            "age": [65],
            "sex": ["F"],
            "dataset_source": ["UAMS Figshare DOI 10.6084/m9.figshare.23849127"],
            "metadata_match": [True],
            "label_match": [True],
            "waveform_sha256": [hashlib.sha256(audio.read_bytes()).hexdigest()],
        }
    ).to_csv(processed / "feature_manifest.csv", index=False)

    def fail_decode(_payload):
        raise ValueError("Synthetic decode failure")

    monkeypatch.setattr(extract_features, "ROOT", tmp_path)
    monkeypatch.setattr(extract_features, "decode_audio", fail_decode)
    monkeypatch.setattr(sys, "argv", ["extract_features.py"])

    assert extract_features.main() == 1
    receipt = json.loads((processed / "feature_extraction_receipt.json").read_text())
    assert receipt["status"] == "blocked_unreviewed_exclusions"
    assert not (processed / "voice_features.csv").exists()
