import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from voxneuro.dataset.validation import (
    UAMS_DATASET_SOURCE,
    validate_evaluation_receipt,
    validate_extraction_receipt,
    validate_features,
    validate_manifest,
    validate_nested_evaluation_receipt,
)


def test_manifest_flags_duplicate_ids_and_missing_paths(tmp_path):
    missing = tmp_path / "missing.wav"
    frame = pd.DataFrame(
        {
            "sample_id": ["a", "a"],
            "participant_id": ["p1", "p1"],
            "audio_path": [str(missing), str(missing)],
            "class_label": ["PD", "PD"],
        }
    )
    issues = validate_manifest(frame)
    assert any("duplicates" in issue for issue in issues)
    assert any("do not exist" in issue for issue in issues)


def test_feature_validator_rejects_identity_predictor():
    frame = pd.DataFrame({"participant_id": ["p1"], "f0_mean_hz": [120.0]})
    issues = validate_features(frame, ["participant_id", "f0_mean_hz"])
    assert any("identity" in issue.lower() for issue in issues)


def test_nested_evaluation_receipt_checks_code_data_and_artifact_hashes(tmp_path):
    output = tmp_path / "metrics.csv"
    output.write_text("model,balanced_accuracy\nlogistic_l2,0.7\n", encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "status": "complete",
                "dataset": "uams",
                "code_version": "code-hash",
                "metrics_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    expected = {"status": "complete", "dataset": "uams", "code_version": "code-hash"}
    assert validate_nested_evaluation_receipt(receipt, expected, {"metrics_sha256": output}) == []
    output.write_text("tampered", encoding="utf-8")
    issues = validate_nested_evaluation_receipt(receipt, expected, {"metrics_sha256": output})
    assert any("metrics_sha256" in issue for issue in issues)


def test_feature_validator_preserves_missing_measures_but_rejects_malformed_text():
    frame = pd.DataFrame(
        {
            "f0_mean_hz": [120.0, 130.0],
            "jitter_local": [float("nan"), 0.02],
        }
    )
    assert validate_features(frame, ["f0_mean_hz", "jitter_local"]) == []
    frame["f0_mean_hz"] = pd.Series([120.0, "several"], dtype="object")
    issues = validate_features(frame, ["f0_mean_hz", "jitter_local"])
    assert any("malformed non-numeric" in issue for issue in issues)
    frame["f0_mean_hz"] = pd.Series([120.0, "NaN"], dtype="object")
    issues = validate_features(frame, ["f0_mean_hz", "jitter_local"])
    assert any("malformed non-numeric" in issue for issue in issues)


@pytest.mark.parametrize("boolean_value", [True, False, np.bool_(True), np.bool_(False)])
def test_feature_validator_rejects_boolean_measurements(boolean_value):
    frame = pd.DataFrame({"f0_mean_hz": pd.Series([boolean_value], dtype="object")})
    issues = validate_features(frame, ["f0_mean_hz"])
    assert any("Boolean values" in issue for issue in issues)


def test_manifest_rejects_empty_rows_and_malformed_waveform_hashes():
    required = ["sample_id", "participant_id", "audio_path", "class_label"]
    assert any("no rows" in issue for issue in validate_manifest(pd.DataFrame(columns=required)))
    frame = pd.DataFrame(
        {
            "sample_id": ["s1"],
            "participant_id": ["p1"],
            "audio_path": ["missing.wav"],
            "class_label": ["PD"],
            "metadata_match": [True],
            "label_match": [True],
            "waveform_sha256": ["short"],
        }
    )
    issues = validate_manifest(frame, require_files=False, require_integrity=True)
    assert any("malformed" in issue for issue in issues)


def test_manifest_verifies_sha256_against_existing_audio(tmp_path):
    audio = tmp_path / "PD_AH" / "audio_01234567-89AB-CDEF-0123-456789ABCDEF.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"test audio bytes")
    digest = hashlib.sha256(audio.read_bytes()).hexdigest()
    frame = pd.DataFrame(
        {
            "sample_id": ["s1"],
            "participant_id": ["audio"],
            "source_sample_key": ["audio"],
            "audio_path": [str(audio)],
            "class_label": ["PD"],
            "source_label": ["PD"],
            "age": [61],
            "sex": ["F"],
            "dataset_source": [UAMS_DATASET_SOURCE],
            "metadata_match": [True],
            "label_match": [True],
            "waveform_sha256": [digest],
        }
    )
    assert validate_manifest(frame, require_integrity=True) == []
    audio.write_bytes(b"changed audio bytes")
    assert any(
        "does not match the on-disk audio" in issue
        for issue in validate_manifest(frame, require_integrity=True)
    )


def test_integrity_manifest_recomputes_label_from_source_and_audio_folder():
    frame = pd.DataFrame(
        {
            "sample_id": ["s1"],
            "participant_id": ["sample"],
            "source_sample_key": ["sample"],
            "audio_path": [r"C:\data\PD_AH\sample.wav"],
            "class_label": ["HC"],
            "source_label": ["PD"],
            "age": [64],
            "sex": ["F"],
            "dataset_source": [UAMS_DATASET_SOURCE],
            "metadata_match": [True],
            "label_match": [True],
            "waveform_sha256": ["a" * 64],
        }
    )
    issues = validate_manifest(frame, require_files=False, require_integrity=True)
    assert any("source label or audio folder" in issue for issue in issues)


def test_integrity_manifest_rejects_label_metadata_hash_and_duplicate_issues():
    frame = pd.DataFrame(
        {
            "sample_id": ["a", "a", "c"],
            "participant_id": ["p1", "p1", "p2"],
            "audio_path": ["a.wav", "b.wav", "c.wav"],
            "class_label": ["PD", "HC", "unclassified"],
            "metadata_match": [True, False, True],
            "label_match": [True, False, True],
            "waveform_sha256": ["a" * 64, "A" * 64, "a" * 64],
        }
    )
    issues = validate_manifest(frame, require_files=False, require_integrity=True)
    assert any("sample_id contains" in issue for issue in issues)
    assert any("exactly PD or HC" in issue for issue in issues)
    assert any("metadata_match" in issue for issue in issues)
    assert any("label_match" in issue for issue in issues)
    assert any("duplicate waveform hashes" in issue for issue in issues)
    assert any("conflicting class labels" in issue for issue in issues)


def test_integrity_manifest_requires_match_and_hash_columns():
    frame = pd.DataFrame(
        {
            "sample_id": ["a"],
            "participant_id": ["p1"],
            "audio_path": ["a.wav"],
            "class_label": ["PD"],
        }
    )
    issues = validate_manifest(frame, require_files=False, require_integrity=True)
    assert any("metadata_match" in issue for issue in issues)
    assert any("label_match" in issue for issue in issues)
    assert any("waveform_sha256" in issue for issue in issues)


@pytest.mark.parametrize("age", [True, False, np.bool_(True), np.bool_(False)])
def test_integrity_manifest_rejects_boolean_participant_ages(age):
    frame = pd.DataFrame(
        {
            "sample_id": ["sample"],
            "participant_id": ["sample"],
            "source_sample_key": ["sample"],
            "audio_path": [r"C:\data\PD_AH\sample.wav"],
            "class_label": ["PD"],
            "source_label": ["PD"],
            "age": pd.Series([age], dtype="object"),
            "sex": ["F"],
            "dataset_source": [UAMS_DATASET_SOURCE],
            "metadata_match": [True],
            "label_match": [True],
            "waveform_sha256": ["a" * 64],
        }
    )
    issues = validate_manifest(frame, require_files=False, require_integrity=True)
    assert any("age is missing, nonnumeric" in issue for issue in issues)


def _repeated_uams_manifest(ages, sex_codes):
    return pd.DataFrame(
        {
            "sample_id": ["recording-1", "recording-2"],
            "participant_id": ["sample", "sample"],
            "source_sample_key": ["sample", "sample"],
            "audio_path": [
                r"C:\data\first\PD_AH\sample.wav",
                r"C:\data\second\PD_AH\sample.wav",
            ],
            "class_label": ["PD", "PD"],
            "source_label": ["PD", "PD"],
            "age": ages,
            "sex": sex_codes,
            "dataset_source": [UAMS_DATASET_SOURCE, UAMS_DATASET_SOURCE],
            "metadata_match": [True, True],
            "label_match": [True, True],
            "waveform_sha256": ["a" * 64, "b" * 64],
        }
    )


def test_integrity_manifest_rejects_unknown_source_sex_category():
    frame = _repeated_uams_manifest([61, 61], ["F", "NOT_A_REAL_SEX_CODE"])
    issues = validate_manifest(frame, require_files=False, require_integrity=True)
    assert any("unrecognized values" in issue and "sex" in issue for issue in issues)


@pytest.mark.parametrize(
    ("ages", "sex_codes", "column"),
    [([61, 62], ["F", "F"], "age"), ([61, 61], ["F", "M"], "sex")],
)
def test_integrity_manifest_rejects_conflicting_repeated_participant_demographics(
    ages, sex_codes, column
):
    issues = validate_manifest(
        _repeated_uams_manifest(ages, sex_codes),
        require_files=False,
        require_integrity=True,
    )
    assert f"Participant has conflicting {column} metadata." in issues


def test_extraction_receipt_must_match_current_manifest_and_feature_files(tmp_path):
    manifest = tmp_path / "feature_manifest.csv"
    features = tmp_path / "voice_features.csv"
    receipt = tmp_path / "feature_extraction_receipt.json"
    manifest.write_text("sample_id\na\n", encoding="utf-8")
    features.write_text("sample_id\na\n", encoding="utf-8")
    receipt.write_text(
        json.dumps(
            {
                "status": "accepted_reviewed_exclusions",
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "feature_table_sha256": hashlib.sha256(features.read_bytes()).hexdigest(),
                "feature_schema_version": "schema.v1",
            }
        ),
        encoding="utf-8",
    )
    assert not validate_extraction_receipt(receipt, manifest, features, "schema.v1")
    features.write_text("changed", encoding="utf-8")
    assert any(
        "does not match" in issue
        for issue in validate_extraction_receipt(receipt, manifest, features, "schema.v1")
    )


def test_evaluation_receipt_must_match_current_grouped_evaluation_outputs(tmp_path):
    manifest = tmp_path / "feature_manifest.csv"
    features = tmp_path / "voice_features.csv"
    metrics = tmp_path / "model_metrics.csv"
    receipt = tmp_path / "model_evaluation_receipt.json"
    manifest.write_text("sample_id\na\n", encoding="utf-8")
    features.write_text("sample_id\na\n", encoding="utf-8")
    metrics.write_text("model,balanced_accuracy\nvoice,0.5\n", encoding="utf-8")
    receipt.write_text(
        json.dumps(
            {
                "status": "complete",
                "dataset": "uams",
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "feature_table_sha256": hashlib.sha256(features.read_bytes()).hexdigest(),
                "metrics_sha256": hashlib.sha256(metrics.read_bytes()).hexdigest(),
                "feature_schema_version": "schema.v1",
            }
        ),
        encoding="utf-8",
    )
    assert not validate_evaluation_receipt(receipt, manifest, features, metrics, "schema.v1")
    assert any(
        "code_version" in issue
        for issue in validate_evaluation_receipt(
            receipt, manifest, features, metrics, "schema.v1", "outdated-code"
        )
    )
    metrics.write_text("changed", encoding="utf-8")
    assert any(
        "metrics_sha256" in issue
        for issue in validate_evaluation_receipt(receipt, manifest, features, metrics, "schema.v1")
    )


@pytest.mark.parametrize("invalid_root", ["[]", '"text"', "7", "true", "null"])
def test_receipt_validators_reject_valid_json_with_non_object_roots(tmp_path, invalid_root):
    manifest = tmp_path / "feature_manifest.csv"
    features = tmp_path / "voice_features.csv"
    metrics = tmp_path / "model_metrics.csv"
    extraction_receipt = tmp_path / "feature_extraction_receipt.json"
    evaluation_receipt = tmp_path / "model_evaluation_receipt.json"
    for path in (manifest, features, metrics):
        path.write_text("placeholder", encoding="utf-8")
    extraction_receipt.write_text(invalid_root, encoding="utf-8")
    evaluation_receipt.write_text(invalid_root, encoding="utf-8")

    extraction_issues = validate_extraction_receipt(
        extraction_receipt, manifest, features, "schema.v1"
    )
    evaluation_issues = validate_evaluation_receipt(
        evaluation_receipt, manifest, features, metrics, "schema.v1"
    )
    assert any("JSON object" in issue for issue in extraction_issues)
    assert any("JSON object" in issue for issue in evaluation_issues)
