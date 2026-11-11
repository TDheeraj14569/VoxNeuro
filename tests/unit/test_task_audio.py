"""Unit tests for task-specific audio validation and preprocessing."""

from __future__ import annotations

import numpy as np
import pytest

from tests.fixtures.synthetic_connected_speech import synthetic_connected_speech
from tests.fixtures.synthetic_ddk_audio import synthetic_ddk_train
from tests.fixtures.synthetic_vowels import synthetic_formant_vowel
from voxneuro.audio.io import AudioRecord
from voxneuro.audio.task_preprocessing import preprocess_task_audio
from voxneuro.audio.task_validation import (
    validate_task_audio,
)
from voxneuro.exceptions import AudioValidationError


def _make_record(samples: np.ndarray, sr: int = 16000, channels: int = 1) -> AudioRecord:
    arr = samples.reshape(-1, channels) if samples.ndim == 1 else samples
    return AudioRecord(
        samples=arr,
        sample_rate=sr,
        channels=channels,
        subtype="PCM_16",
        format="WAV",
    )


class TestTaskAudioValidation:
    """Tests for task-specific audio validation gates."""

    def test_ddk_audio_validation_succeeds_on_valid_train(self) -> None:
        samples = synthetic_ddk_train(sample_rate=16000, duration=4.0, target_rate_hz=5.0)
        rec = _make_record(samples)
        quality = validate_task_audio(rec, task_type="ddk")

        assert quality.valid is True
        assert quality.status == "complete"
        assert len(quality.errors) == 0
        assert quality.duration_seconds == pytest.approx(4.0, abs=0.05)
        assert quality.clipping_fraction < 0.001

    def test_connected_speech_validation_succeeds_with_pauses(self) -> None:
        samples = synthetic_connected_speech(sample_rate=16000)
        rec = _make_record(samples)
        quality = validate_task_audio(rec, task_type="connected_speech")

        assert quality.valid is True
        assert quality.status == "complete"
        assert len(quality.errors) == 0
        assert quality.active_speech_fraction > 0.30

    def test_vowel_space_validation_succeeds_on_corner_vowels(self) -> None:
        for v in ("a", "i", "u"):
            samples = synthetic_formant_vowel(vowel_label=v, duration=2.0)
            rec = _make_record(samples)
            quality = validate_task_audio(rec, task_type="vowel_space")

            assert quality.valid is True
            assert quality.status == "complete"
            assert quality.duration_seconds == pytest.approx(2.0, abs=0.05)

    def test_validation_fails_on_too_short_recording(self) -> None:
        samples = np.sin(2 * np.pi * 200 * np.arange(8000) / 16000) * 0.3
        rec = _make_record(samples)  # 0.5s duration
        quality = validate_task_audio(rec, task_type="ddk")

        assert quality.valid is False
        assert any("below the minimum required" in err for err in quality.errors)

    def test_validation_fails_on_nan_and_infinite_values(self) -> None:
        samples = synthetic_ddk_train(sample_rate=16000, duration=3.0)
        samples[100] = np.nan
        rec = _make_record(samples)
        quality = validate_task_audio(rec, task_type="ddk")

        assert quality.valid is False
        assert any("NaN or infinite" in err for err in quality.errors)

    def test_validation_fails_on_excessive_clipping(self) -> None:
        samples = synthetic_ddk_train(sample_rate=16000, duration=3.0)
        # Clip top 5% of samples to 1.0
        samples[samples > 0.05] = 1.0
        rec = _make_record(samples)
        quality = validate_task_audio(rec, task_type="ddk")

        assert quality.valid is False
        assert any("clipping" in err.lower() for err in quality.errors)

    def test_validation_detects_destructive_stereo_phase(self) -> None:
        ch0 = np.sin(2 * np.pi * 300 * np.arange(32000) / 16000) * 0.4
        ch1 = -ch0  # Exactly 180 degrees out of phase
        stereo_samples = np.column_stack([ch0, ch1])
        rec = _make_record(stereo_samples, channels=2)
        quality = validate_task_audio(rec, task_type="connected_speech")

        assert quality.valid is False
        assert any("phase cancellation" in err for err in quality.errors)


class TestTaskAudioPreprocessing:
    """Tests for task-specific audio preprocessing."""

    def test_ddk_preprocessing_preserves_full_duration_and_removes_dc(self) -> None:
        samples = synthetic_ddk_train(sample_rate=16000, duration=4.0) + 0.08  # DC offset
        rec = _make_record(samples)
        prep = preprocess_task_audio(rec, task_type="ddk", target_sample_rate=16000)

        assert abs(float(np.mean(prep.samples))) < 1e-4
        assert prep.dc_offset_removed == pytest.approx(0.08, abs=0.01)
        assert prep.retained_duration_seconds == pytest.approx(4.0, abs=0.05)
        assert prep.sample_rate == 16000
        assert prep.preprocessing_fingerprint != ""

    def test_connected_speech_preprocessing_preserves_pauses(self) -> None:
        samples = synthetic_connected_speech(sample_rate=16000)
        rec = _make_record(samples)
        prep = preprocess_task_audio(rec, task_type="connected_speech", target_sample_rate=16000)

        # Full duration preserved without aggressive edge trimming
        assert prep.retained_duration_seconds > 4.5
        assert prep.trim_start_seconds == 0.0
        assert prep.trimmed_tail_seconds == 0.0

    def test_vowel_space_preprocessing_trims_silent_margins(self) -> None:
        # Vowel with 1.0s silence on both sides
        vowel_core = synthetic_formant_vowel(vowel_label="a", duration=1.5)
        pad = np.zeros(16000, dtype=np.float64)  # 1.0s silence
        padded_vowel = np.concatenate([pad, vowel_core, pad])

        rec = _make_record(padded_vowel)
        prep = preprocess_task_audio(rec, task_type="vowel_space", target_sample_rate=16000)

        assert prep.trim_start_seconds > 0.5
        assert prep.trimmed_tail_seconds > 0.5
        assert prep.retained_duration_seconds < len(padded_vowel) / 16000

    def test_preprocessing_resamples_cleanly(self) -> None:
        samples = synthetic_ddk_train(sample_rate=22050, duration=3.0)
        rec = _make_record(samples, sr=22050)
        prep = preprocess_task_audio(rec, task_type="ddk", target_sample_rate=16000)

        assert prep.resampled is True
        assert prep.original_sample_rate == 22050
        assert prep.sample_rate == 16000
        assert prep.retained_duration_seconds == pytest.approx(3.0, abs=0.05)

    def test_preprocessing_raises_on_invalid_audio(self) -> None:
        # 0.1s audio is too short for DDK
        short_samples = np.zeros(1600, dtype=np.float64)
        rec = _make_record(short_samples)
        with pytest.raises(AudioValidationError):
            preprocess_task_audio(rec, task_type="ddk")
