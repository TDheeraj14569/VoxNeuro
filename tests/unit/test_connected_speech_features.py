"""Unit tests for connected speech segmentation, pause, and prosodic analysis."""

from __future__ import annotations

import pytest

from tests.fixtures.synthetic_connected_speech import synthetic_connected_speech
from voxneuro.audio.io import AudioRecord
from voxneuro.audio.task_preprocessing import preprocess_task_audio
from voxneuro.features.tasks.connected_speech import (
    CONNECTED_SPEECH_FEATURE_NAMES,
    CONNECTED_SPEECH_SCHEMA_VERSION,
    extract_connected_speech_features,
)
from voxneuro.features.tasks.schema import connected_speech_schema_fingerprint


def _prep_connected(
    bouts=(1.5, 2.0, 1.8),
    pauses=(0.4, 0.5),
    f0=140.0,
):
    samples = synthetic_connected_speech(
        sample_rate=16000,
        bout_durations_s=bouts,
        pause_durations_s=pauses,
        base_f0_hz=f0,
    )
    rec = AudioRecord(
        samples=samples.reshape(-1, 1),
        sample_rate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )
    return preprocess_task_audio(rec, task_type="connected_speech", target_sample_rate=16000)


class TestConnectedSpeechFeatures:
    """Tests for connected speech VAD, pause timing, and prosodic features."""

    def test_connected_speech_schema_fingerprint_and_features(self) -> None:
        fp = connected_speech_schema_fingerprint()
        assert isinstance(fp, str) and len(fp) == 64
        assert len(CONNECTED_SPEECH_FEATURE_NAMES) == 20
        assert "pause_count" in CONNECTED_SPEECH_FEATURE_NAMES
        assert "f0_range_semitones" in CONNECTED_SPEECH_FEATURE_NAMES

    def test_segmentation_detects_known_bouts_and_pauses(self) -> None:
        # 3 bouts (1.5, 2.0, 1.8s) separated by 2 pauses (0.4, 0.5s)
        prep = _prep_connected(bouts=(1.5, 2.0, 1.8), pauses=(0.4, 0.5))
        res = extract_connected_speech_features(prep)

        assert res.task_status == "complete"
        assert res.task_schema_version == CONNECTED_SPEECH_SCHEMA_VERSION

        # Speech bouts should be 3
        bout_count = res.features["speech_bout_count"]
        assert bout_count is not None
        assert int(bout_count) == 3

        # Pause count should be at least 2 (the two inter-bout pauses, plus possible edge margins)
        pause_count = res.features["pause_count"]
        assert pause_count is not None
        assert int(pause_count) >= 2

        # Active speech duration should be approx 1.5 + 2.0 + 1.8 = 5.3s
        active_dur = res.features["estimated_active_speech_duration_s"]
        assert active_dur is not None
        assert active_dur == pytest.approx(5.3, abs=0.5)

    def test_prosodic_pitch_metrics_accuracy(self) -> None:
        # Base pitch 150 Hz
        prep = _prep_connected(f0=150.0)
        res = extract_connected_speech_features(prep)

        f0_med = res.features["f0_median_hz"]
        assert f0_med is not None
        assert f0_med == pytest.approx(150.0, abs=15.0)

        f0_sd = res.features["f0_sd_hz"]
        assert f0_sd is not None
        assert f0_sd > 0.0  # Vibrato/prosodic pitch variation detected

        f0_range_st = res.features["f0_range_semitones"]
        assert f0_range_st is not None
        assert f0_range_st > 0.5

    def test_intensity_metrics_extracted(self) -> None:
        prep = _prep_connected()
        res = extract_connected_speech_features(prep)

        intensity_med = res.features["intensity_median_dbfs"]
        assert intensity_med is not None
        assert -40.0 < intensity_med < 0.0

        intensity_iqr = res.features["intensity_iqr_db"]
        assert intensity_iqr is not None
        assert intensity_iqr > 0.0
