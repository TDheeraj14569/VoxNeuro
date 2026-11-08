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


@pytest.mark.parametrize("invalid_rate", [16000.5, True, False, 4000, 96000, "16000", -8000])
def test_preprocessing_rejects_invalid_target_sample_rates(invalid_rate):
    source = sustained_vowel(8000, 3.0)
    record = AudioRecord(source.reshape(-1, 1), 8000, 1, "FLOAT", "WAV")
    with pytest.raises(
        ValueError, match="Target sample rate must be an integer between 8000 and 48000 Hz."
    ):
        preprocess_audio(record, target_sample_rate=invalid_rate)


def test_preprocessing_uses_configured_frame_size_for_silence_trimming():
    from voxneuro.audio.validation import AudioValidationConfig

    signal = np.concatenate([np.zeros(8000), sustained_vowel(duration=2.0), np.zeros(8000)])
    record = AudioRecord(signal.reshape(-1, 1), 16000, 1, "FLOAT", "WAV")
    short_frame = AudioValidationConfig(frame_ms=10, min_voiced_fraction=0.1)
    long_frame = AudioValidationConfig(frame_ms=30, min_voiced_fraction=0.1)
    short_trim = preprocess_audio(record, validation_config=short_frame).trim_start_seconds
    long_trim = preprocess_audio(record, validation_config=long_frame).trim_start_seconds
    assert short_trim != long_trim


@pytest.mark.parametrize("sr", [22050, 44100, 48000])
def test_preprocessing_resampling_filter_overshoot_is_bounded(sr):
    from voxneuro.features.extractor import extract_features

    # Synthetic signal normalized close to full-scale (0.998)
    sig = sustained_vowel(sample_rate=sr, duration=2.0)
    sig = sig / np.max(np.abs(sig)) * 0.998
    rec = AudioRecord(sig.reshape(-1, 1), sr, 1, "FLOAT", "WAV")
    res = preprocess_audio(rec, target_sample_rate=16000)
    peak = float(np.max(np.abs(res.samples)))
    assert peak <= 1.0
    # Strict feature extraction check must pass without amplitude range error
    feats = extract_features(res.samples, res.sample_rate)
    assert len(feats) >= 39
