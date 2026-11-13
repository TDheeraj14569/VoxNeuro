import numpy as np

from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION
from voxneuro.reporting.html_report import render_voice_report_html
from voxneuro.reporting.report import build_report


def test_individual_html_report_contains_actual_features_and_embedded_plots():
    features = {name: float(index + 1) for index, name in enumerate(FEATURE_NAMES)}
    features["schema_version"] = SCHEMA_VERSION
    features["schema_fingerprint"] = "schema-id"
    report = build_report(
        {
            "valid": True,
            "duration_seconds": 2.0,
            "sample_rate_hz": 16000,
            "channels": 1,
            "peak_amplitude_fs": 0.5,
            "rms_amplitude_fs": 0.2,
            "clipping_fraction": 0.0,
            "voiced_fraction": 0.8,
            "active_fraction": 0.9,
            "warnings": [],
        },
        features,
        {"target_sample_rate_hz": 16000, "resampled": False},
        model_status="Unavailable for this recording: domain validation is not established.",
    )
    report["recording_metadata"] = {
        "capture_origin": "user_upload",
        "acquisition_domain_id": "laptop_microphone",
        "acquisition_domain_source": "user_declared",
        "task_type": "sustained_vowel",
        "duration_seconds": 2.0,
        "original_sample_rate_hz": 16000,
        "channels": 1,
        "repetition_count": 1,
    }
    report["model_assessment"].update(
        {
            "status": "EXPLORATORY_NOT_DOMAIN_VALIDATED",
            "research_classification": "PD-pattern candidate",
            "research_score": 0.824,
            "score_kind": "uncalibrated_logit",
            "decision_threshold": 0.0,
            "ood_status": "IN_DISTRIBUTION",
            "domain_validation_status": "NOT_VALIDATED",
            "model_evaluation_metrics": {"balanced_accuracy": 0.72},
        }
    )
    samples = (0.2 * np.sin(2 * np.pi * 180 * np.arange(32000) / 16000)).astype(np.float32)
    rendered = render_voice_report_html(report, processed_samples=samples, sample_rate=16000)
    assert "voxneuro.voice.v3" in rendered
    assert "f0_mean_hz" in rendered
    assert "mfcc_12_sd" in rendered
    assert "Processed voice waveform" in rendered
    assert "Processed audio spectrogram" in rendered
    assert "Provenance and configuration fingerprints" in rendered
    assert "Schema fingerprint" in rendered
    assert "calibrated disease probability" in rendered
    assert "Recording context" in rendered
    assert "laptop_microphone" in rendered
    assert "PD-pattern candidate" in rendered
    assert "+0.824000" in rendered
    assert "not a probability" in rendered
    assert "0.824%" not in rendered
    assert "<script" not in rendered
