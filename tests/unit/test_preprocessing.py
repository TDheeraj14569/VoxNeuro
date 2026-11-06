import numpy as np
import pytest

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.audio.io import AudioRecord
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.validation import validate_audio
from voxneuro.exceptions import AudioValidationError


def test_preprocessing_removes_dc_and_resamples_deterministically():
    source = sustained_vowel(8000, 3.0) + 0.04
    record = AudioRecord(source.reshape(-1, 1), 8000, 1, "FLOAT", "WAV")
    out1 = preprocess_audio(record, 16000)
    out2 = preprocess_audio(record, 16000)
    assert out1.sample_rate == 16000
    assert out1.samples.size == pytest.approx(source.size * 2, abs=8)
    assert out1.dc_offset_removed == pytest.approx(0.04, abs=0.01)
    assert out1.trimmed_tail_seconds >= 0
    assert out1.retained_duration_seconds >= 1.0
    assert not hasattr(out1, "trim_end_seconds")
    np.testing.assert_array_equal(out1.samples, out2.samples)
    assert np.isfinite(out1.samples).all()


def test_preprocessing_fails_closed_on_invalid_quality():
    record = AudioRecord(np.zeros((1000, 1)), 16000, 1, "FLOAT", "WAV")
    with pytest.raises(AudioValidationError):
        preprocess_audio(record)


def test_preprocessing_revalidates_original_stereo_before_downmixing():
    mono = sustained_vowel(duration=3.0)
    stereo = np.column_stack((mono * 0.4, -mono * 0.2))
    record = AudioRecord(stereo, 16000, 2, "FLOAT", "WAV")

    with pytest.raises(AudioValidationError, match="out of phase"):
        preprocess_audio(record)


def test_preprocessing_rejects_signal_that_is_too_short_after_trimming():
    from voxneuro.audio.validation import AudioValidationConfig

    signal = np.concatenate([np.zeros(16000), sustained_vowel(16000, 0.3), np.zeros(16000)])
    record = AudioRecord(signal.reshape(-1, 1), 16000, 1, "FLOAT", "WAV")
    config = AudioValidationConfig(min_duration_seconds=0.6, min_voiced_fraction=0.05)
    quality = validate_audio(record, config)
    assert quality.valid
    with pytest.raises(AudioValidationError, match="after silence trimming"):
        preprocess_audio(record, validation_config=config)


def test_preprocessing_uses_configured_frame_size_for_silence_trimming():
    from voxneuro.audio.validation import AudioValidationConfig

    signal = np.concatenate([np.zeros(8000), sustained_vowel(duration=2.0), np.zeros(8000)])
    record = AudioRecord(signal.reshape(-1, 1), 16000, 1, "FLOAT", "WAV")
    short_frame = AudioValidationConfig(frame_ms=10, min_voiced_fraction=0.1)
    long_frame = AudioValidationConfig(frame_ms=30, min_voiced_fraction=0.1)
    short_trim = preprocess_audio(record, validation_config=short_frame).trim_start_seconds
    long_trim = preprocess_audio(record, validation_config=long_frame).trim_start_seconds
    assert short_trim != long_trim
