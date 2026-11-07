import numpy as np
import pytest

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.audio.io import AudioRecord
from voxneuro.audio.validation import AudioValidationConfig, validate_audio


def record(samples, sample_rate=16000):
    return AudioRecord(np.asarray(samples).reshape(-1, 1), sample_rate, 1, "FLOAT", "WAV")


def test_valid_sustained_vowel_passes():
    result = validate_audio(record(sustained_vowel()))
    assert result.valid
    assert result.voiced_fraction > 0.8


def test_silence_and_short_input_are_rejected_with_reasons():
    result = validate_audio(record(np.zeros(1000)))
    assert not result.valid
    assert any("short" in message for message in result.errors)
    assert any("silent" in message for message in result.errors)


def test_clipping_is_rejected():
    x = np.full(16000 * 2, 1.0)
    result = validate_audio(record(x), AudioValidationConfig(clipping_fraction_limit=0.01))
    assert not result.valid
    assert any("clipped" in message for message in result.errors)


def test_zero_clipping_limit_accepts_a_clean_recording():
    result = validate_audio(
        record(sustained_vowel()), AudioValidationConfig(clipping_fraction_limit=0.0)
    )
    assert result.valid
    assert result.clipping_fraction == 0.0


def test_clipping_limit_accepts_equality_and_rejects_only_above_it():
    samples = sustained_vowel()
    samples[:20] = 1.0
    audio = record(samples)
    measured = validate_audio(audio, AudioValidationConfig(clipping_fraction_limit=1.0))
    threshold = measured.clipping_fraction
    assert threshold > 0

    equal = validate_audio(audio, AudioValidationConfig(clipping_fraction_limit=threshold))
    below = validate_audio(
        audio,
        AudioValidationConfig(clipping_fraction_limit=np.nextafter(threshold, 0.0)),
    )
    above = validate_audio(
        audio,
        AudioValidationConfig(clipping_fraction_limit=np.nextafter(threshold, 1.0)),
    )

    assert equal.valid
    assert not below.valid
    assert any("clipped" in message for message in below.errors)
    assert above.valid


@pytest.mark.parametrize(
    ("samples", "channels", "message"),
    [
        (np.zeros(48000), 2, "Audio must have one or two channels"),
        (np.zeros((2, 48000, 2)), 2, "Audio must have one or two channels"),
        (
            np.zeros((48000, 2)),
            1,
            "channel metadata does not match the sample-array shape",
        ),
    ],
)
def test_invalid_audio_dimensions_return_structured_validation_errors(samples, channels, message):
    malformed = AudioRecord(samples, 16000, channels, "FLOAT", "WAV")

    result = validate_audio(malformed)

    assert not result.valid
    assert any(message in error for error in result.errors)


def test_nonfinite_samples_are_rejected():
    x = sustained_vowel()
    x[50] = np.nan
    result = validate_audio(record(x))
    assert not result.valid
    assert any("NaN" in message for message in result.errors)


def test_empty_audio_is_rejected():
    result = validate_audio(record(np.array([], dtype=np.float64)))
    assert not result.valid
    assert any("no samples" in message for message in result.errors)


def test_quiet_nonzero_audio_is_rejected_as_low_level():
    quiet = sustained_vowel() * 0.01
    result = validate_audio(record(quiet))
    assert not result.valid
    assert result.rms_amplitude > 0
    assert any("very low" in message for message in result.errors)


def test_long_audio_is_rejected():
    result = validate_audio(record(sustained_vowel(duration=31.0)))
    assert not result.valid
    assert any("too long" in message for message in result.errors)


def test_unvoiced_noise_is_rejected():
    noise = np.random.default_rng(7).normal(0.0, 0.1, 16000 * 2)
    result = validate_audio(record(noise))
    assert not result.valid
    assert any("voiced signal" in message for message in result.errors)


def test_stereo_phase_cancellation_is_rejected():
    mono = sustained_vowel()
    stereo = np.column_stack((mono, -mono))
    audio = AudioRecord(stereo, 16000, 2, "FLOAT", "WAV")
    result = validate_audio(audio)
    assert not result.valid
    assert any("out of phase" in message for message in result.errors)


def test_stereo_phase_cancellation_is_invalid_before_processing():
    mono = sustained_vowel()
    stereo = np.column_stack((mono, -mono))
    result = validate_audio(AudioRecord(stereo, 16000, 2, "FLOAT", "WAV"))
    assert not result.valid
    assert result.voiced_fraction == 0.0


def test_unknown_mono_policy_fails_closed():
    cfg = AudioValidationConfig(mono_policy="select_first_channel")
    result = validate_audio(record(sustained_vowel()), cfg)
    assert not result.valid
    assert any("Unsupported mono conversion policy" in message for message in result.errors)


def test_audio_validation_config_enforces_numeric_ranges():
    with pytest.raises(ValueError, match="min_duration_seconds must be positive"):
        AudioValidationConfig(min_duration_seconds=-1.0)
    with pytest.raises(ValueError, match="max_duration_seconds must be greater"):
        AudioValidationConfig(min_duration_seconds=5.0, max_duration_seconds=2.0)
    with pytest.raises(ValueError, match="min_rms must be in range"):
        AudioValidationConfig(min_rms=-0.5)
    with pytest.raises(ValueError, match="max_peak must be in range"):
        AudioValidationConfig(max_peak=1.5)
    with pytest.raises(ValueError, match="clipping_fraction_limit must be in range"):
        AudioValidationConfig(clipping_fraction_limit=2.0)
    with pytest.raises(ValueError, match="min_voiced_fraction must be in range"):
        AudioValidationConfig(min_voiced_fraction=-0.1)
    with pytest.raises(ValueError, match="frame_ms must be a positive integer"):
        AudioValidationConfig(frame_ms=0)
    with pytest.raises(ValueError, match="pitch_floor_hz must be positive"):
        AudioValidationConfig(pitch_floor_hz=-50.0)
    with pytest.raises(ValueError, match="pitch_ceiling_hz must be greater"):
        AudioValidationConfig(pitch_floor_hz=300.0, pitch_ceiling_hz=200.0)


def test_pure_sine_tone_is_rejected_as_non_vocal():
    # Exactly replicating reviewer's synthetic 3-second, 130 Hz tone with amplitude 0.2 at 16 kHz
    fs = 16000
    duration = 3.0
    t = np.arange(int(fs * duration), dtype=np.float64) / fs
    sine_wave = 0.2 * np.sin(2 * np.pi * 130.0 * t)
    result = validate_audio(record(sine_wave, fs))
    assert not result.valid
    assert any("harmonic overtones" in err for err in result.errors)
