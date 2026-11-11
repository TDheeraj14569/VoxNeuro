"""Unit tests for Diadochokinetic (DDK) syllable repetition analysis."""

from __future__ import annotations

import numpy as np
import pytest

from tests.fixtures.synthetic_ddk_audio import synthetic_ddk_train
from voxneuro.audio.io import AudioRecord
from voxneuro.audio.task_preprocessing import (
    TaskPreprocessingResult,
    preprocess_task_audio,
)
from voxneuro.features.tasks.ddk import (
    DDK_FEATURE_NAMES,
    DDK_SCHEMA_VERSION,
    extract_ddk_features,
)
from voxneuro.features.tasks.schema import ddk_schema_fingerprint


def _prep_train(
    rate_hz: float = 5.0,
    duration: float = 4.0,
    jitter_sd: float = 0.0,
    drift_slope: float = 0.0,
):
    samples = synthetic_ddk_train(
        sample_rate=16000,
        duration=duration,
        target_rate_hz=rate_hz,
        jitter_sd_s=jitter_sd,
        acceleration_slope_s=drift_slope,
    )
    rec = AudioRecord(
        samples=samples.reshape(-1, 1),
        sample_rate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )
    return preprocess_task_audio(rec, task_type="ddk", target_sample_rate=16000)


class TestDDKFeatures:
    """Tests for DDK event detection and temporal feature extraction."""

    def test_ddk_schema_fingerprint_and_feature_names(self) -> None:
        fp = ddk_schema_fingerprint()
        assert isinstance(fp, str) and len(fp) == 64
        assert len(DDK_FEATURE_NAMES) == 11
        assert "estimated_event_rate_per_s" in DDK_FEATURE_NAMES
        assert "rmssd_inter_event_interval_s" in DDK_FEATURE_NAMES

    def test_event_detection_accuracy_on_known_rate(self) -> None:
        # 5.0 Hz over 4.0 seconds (approx 17-19 pulses)
        prep = _prep_train(rate_hz=5.0, duration=4.0)
        res = extract_ddk_features(prep, task_id="ddk_pa", stimulus="AMR_PA")

        assert res.task_status == "complete"
        assert res.task_schema_version == DDK_SCHEMA_VERSION
        assert res.features["estimated_event_count"] >= 15
        # Rate should be close to 5.0 Hz
        rate = res.features["estimated_event_rate_per_s"]
        assert rate is not None
        assert rate == pytest.approx(5.0, abs=0.40)

        # Interval duration should be close to 0.20s (1 / 5.0 Hz)
        mean_iei = res.features["mean_inter_event_interval_s"]
        assert mean_iei is not None
        assert mean_iei == pytest.approx(0.20, abs=0.02)

    def test_variability_metrics_on_uniform_vs_jittered_trains(self) -> None:
        # Uniform timing
        prep_uniform = _prep_train(rate_hz=5.0, duration=4.0, jitter_sd=0.0)
        res_uniform = extract_ddk_features(prep_uniform)

        # Jittered timing
        prep_jitter = _prep_train(rate_hz=5.0, duration=4.0, jitter_sd=0.035)
        res_jitter = extract_ddk_features(prep_jitter)

        sd_uniform = res_uniform.features["sd_inter_event_interval_s"]
        sd_jitter = res_jitter.features["sd_inter_event_interval_s"]

        assert sd_uniform is not None and sd_jitter is not None
        assert sd_jitter > sd_uniform

    def test_rate_drift_slope_detects_acceleration(self) -> None:
        # Accelerating rate: intervals decrease sequentially
        prep_drift = _prep_train(rate_hz=4.0, duration=4.0, drift_slope=-0.005)
        res_drift = extract_ddk_features(prep_drift)

        slope = res_drift.features["inter_event_interval_slope_s_per_event"]
        assert slope is not None
        assert slope < 0.0  # Decreasing interval length = acceleration

    def test_insufficient_signal_returns_null_features(self) -> None:
        # Signal with no detectible syllables
        silent = np.zeros(32000, dtype=np.float64)
        prep = TaskPreprocessingResult(
            samples=silent,
            sample_rate=16000,
            original_sample_rate=16000,
            original_channels=1,
            dc_offset_removed=0.0,
            trim_start_seconds=0.0,
            trimmed_tail_seconds=0.0,
            retained_duration_seconds=2.0,
            resampled=False,
            preprocessing_fingerprint="test_fp",
        )
        res = extract_ddk_features(prep)

        assert res.task_status == "insufficient_signal"
        assert res.features["estimated_event_count"] == 0.0
        assert res.features["estimated_event_rate_per_s"] is None
        assert res.features["mean_inter_event_interval_s"] is None
        assert res.features["sd_inter_event_interval_s"] is None

    def test_four_stimuli_types_supported(self) -> None:
        prep = _prep_train(rate_hz=5.0, duration=3.0)
        stimuli = ["AMR_PA", "AMR_TA", "AMR_KA", "SMR_PATAKA"]

        for stim in stimuli:
            res = extract_ddk_features(prep, task_id=f"ddk_{stim.lower()}", stimulus=stim)
            assert res.stimulus == stim
            assert res.task_status == "complete"
            assert res.features["estimated_event_rate_per_s"] is not None
