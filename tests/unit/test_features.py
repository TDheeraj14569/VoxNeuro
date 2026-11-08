import shutil

import numpy as np
import pytest
import yaml

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro import config
from voxneuro.exceptions import FeatureExtractionError
from voxneuro.features.extractor import extract_features
from voxneuro.features.parselmouth_features import extract_praat_features
from voxneuro.features.schema import (
    FEATURE_DEFINITIONS,
    FEATURE_NAMES,
    SCHEMA_VERSION,
    feature_config_fingerprint,
    schema_fingerprint,
)


def test_features_follow_versioned_schema_and_are_finite_when_defined():
    result = extract_features(sustained_vowel(), 16000)
    repeated = extract_features(sustained_vowel(), 16000)
    assert result["schema_version"] == SCHEMA_VERSION
    assert [key for key in result if key in FEATURE_NAMES] == FEATURE_NAMES
    assert result["schema_fingerprint"] == schema_fingerprint()
    assert len(result["feature_config_fingerprint"]) == 64
    assert result["preprocessing_config_fingerprint"] is None
    assert all(np.isclose(result[name], repeated[name], equal_nan=True) for name in FEATURE_NAMES)
    assert np.isfinite(result["f0_mean_hz"])
    assert 150 < result["f0_mean_hz"] < 200
    assert np.isfinite(result["mfcc_00_mean"])
    assert "jitter_local" in result and "shimmer_local" in result


def test_feature_schema_has_no_identity_or_label_columns():
    forbidden = ("participant", "filename", "diagnosis", "class_label", "dataset")
    assert not any(token in name.casefold() for name in FEATURE_NAMES for token in forbidden)


def test_mfcc_names_are_zero_based_and_feature_band_is_versioned():
    assert "mfcc_00_mean" in FEATURE_NAMES
    assert "mfcc_12_sd" in FEATURE_NAMES
    assert "mfcc_13_mean" not in FEATURE_NAMES
    definition = next(item for item in FEATURE_DEFINITIONS if item.name == "mfcc_00_mean")
    assert "index 0 (zero-based)" in definition.method


def test_feature_configuration_fingerprint_changes_with_extraction_settings():
    assert feature_config_fingerprint({"pitch_floor_hz": 75}) != feature_config_fingerprint(
        {"pitch_floor_hz": 80}
    )


def test_feature_configuration_schema_version_must_match_implementation(tmp_path, monkeypatch):
    from copy import deepcopy

    values = deepcopy(config.load_config("feature_config.yaml"))
    original_config_root = config.PROJECT_ROOT / "configs"
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    shutil.copyfile(original_config_root / "audio_config.yaml", config_dir / "audio_config.yaml")
    path = config_dir / "feature_config.yaml"
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    values["schema_version"] = SCHEMA_VERSION
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    assert config.load_config("feature_config.yaml")["schema_version"] == SCHEMA_VERSION

    values["schema_version"] = "voxneuro.voice.v2"
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    with pytest.raises(ValueError, match="must exactly match the implementation schema"):
        config.load_config("feature_config.yaml")
    assert feature_config_fingerprint({"schema_version": SCHEMA_VERSION, "pitch_floor_hz": 75}) == (
        feature_config_fingerprint({"pitch_floor_hz": 75})
    )


def test_feature_extractor_rejects_multichannel_input_instead_of_interleaving():
    mono = sustained_vowel(duration=3.0)
    stereo = np.column_stack((mono, mono))
    with pytest.raises(FeatureExtractionError, match="one-dimensional array"):
        extract_features(stereo, 16000)


def test_standalone_spectral_extractor_rejects_stereo_instead_of_flattening():
    from voxneuro.features.spectral_features import extract_spectral_features

    stereo = np.column_stack((sustained_vowel(duration=3.0), sustained_vowel(duration=3.0)))
    with pytest.raises(ValueError, match="requires mono 1D audio"):
        extract_spectral_features(stereo, 16000)


def test_spectral_extractor_rejects_cutoff_at_effective_nyquist():
    from voxneuro.features.spectral_features import extract_spectral_features

    with pytest.raises(ValueError, match="strictly below sample-rate Nyquist"):
        extract_spectral_features(sustained_vowel(duration=3.0), 16000, common_max_hz=8000.0)


@pytest.mark.parametrize("duration", [0.04, 0.06])
def test_f0_summaries_require_at_least_three_voiced_frames(duration):
    values = extract_praat_features(sustained_vowel(duration=duration), 16000)
    for name in (
        "f0_mean_hz",
        "f0_median_hz",
        "f0_sd_hz",
        "f0_min_hz",
        "f0_max_hz",
        "f0_range_hz",
    ):
        assert np.isnan(values[name])


@pytest.mark.parametrize("count", [12, 14, 13.0, True])
def test_current_schema_rejects_non_13_mfcc_counts(count):
    with pytest.raises(FeatureExtractionError, match="exactly 13"):
        extract_features(sustained_vowel(), 16000, mfcc_count=count)


def test_mfcc_units_and_standard_deviation_validity_are_explicit():
    mfcc_sd = next(item for item in FEATURE_DEFINITIONS if item.name == "mfcc_00_sd")
    assert mfcc_sd.units == "dimensionless numerical coefficient"
    assert mfcc_sd.validity == "At least two frames"


def test_hnr_calculation_excludes_praat_undefined_unvoiced_frames():
    import parselmouth

    fs = 16000
    vowel = sustained_vowel(duration=1.0)
    silence = np.zeros(fs)
    interrupted_signal = np.concatenate([vowel, silence])

    values = extract_praat_features(interrupted_signal, fs)
    assert np.isfinite(values["hnr_mean_db"])
    assert values["hnr_mean_db"] > 0.0

    sound = parselmouth.Sound(interrupted_signal, sampling_frequency=float(fs))
    harmonicity = sound.to_harmonicity_cc(
        time_step=0.01,
        minimum_pitch=75.0,
        silence_threshold=0.1,
        periods_per_window=1.0,
    )
    praat_mean = parselmouth.praat.call(harmonicity, "Get mean", 0.0, 0.0)
    assert np.isclose(values["hnr_mean_db"], praat_mean, atol=1e-4)


@pytest.mark.parametrize(
    "bad_samples",
    [
        np.array([1.0 + 2.0j, 3.0 + 4.0j]),
        np.array([True, False, True]),
        np.array(["1.0", "2.0", "3.0"], dtype=object),
        [[1.0], [2.0, 3.0]],
    ],
)
def test_extract_features_rejects_complex_boolean_and_string_arrays(bad_samples):
    with pytest.raises(FeatureExtractionError, match="numeric"):
        extract_features(bad_samples, 16000)


@pytest.mark.parametrize("bad_sr", [16000.5, True, False, 4000, 96000, "16000", -16000])
def test_extract_features_rejects_invalid_sample_rates(bad_sr):
    with pytest.raises(FeatureExtractionError, match="sample rate"):
        extract_features(sustained_vowel(), bad_sr)


@pytest.mark.parametrize(
    "bad_orig_sr",
    [16000.5, True, False, 0, 4000, 96000, "16000", -16000],
)
def test_extract_features_rejects_invalid_original_sample_rates(bad_orig_sr):
    with pytest.raises(FeatureExtractionError, match="Original sample rate"):
        extract_features(sustained_vowel(), 16000, original_sample_rate=bad_orig_sr)


def test_lower_level_extractors_reject_non_numeric_and_complex_arrays():
    from voxneuro.features.parselmouth_features import extract_praat_features
    from voxneuro.features.spectral_features import extract_spectral_features

    complex_arr = np.array([1.0 + 1.0j, 2.0 - 1.0j])
    bool_arr = np.array([True, False, True])
    obj_arr = np.array(["1.0", "2.0"], dtype=object)

    for bad in (complex_arr, bool_arr, obj_arr):
        with pytest.raises(ValueError, match="numeric"):
            extract_praat_features(bad, 16000)
        with pytest.raises(ValueError, match="numeric"):
            extract_spectral_features(bad, 16000)


@pytest.mark.parametrize(
    ("param_kwargs", "err_match"),
    [
        ({"pitch_floor_hz": 0.0}, "pitch_floor_hz"),
        ({"pitch_floor_hz": 600.0, "pitch_ceiling_hz": 500.0}, "pitch_floor_hz"),
        ({"pitch_ceiling_hz": 40.0}, "pitch_ceiling_hz"),
        (
            {"pitch_floor_hz": 300.0, "pitch_ceiling_hz": 200.0},
            "pitch_floor_hz must be strictly less",
        ),
        ({"pitch_step_seconds": 0.5}, "pitch_step_seconds"),
        ({"mel_bands": 10}, "mel_bands"),
        ({"fft_window_samples": 1000}, "fft_window_samples"),
        ({"hop_samples": 2048, "fft_window_samples": 1024}, "hop_samples"),
        ({"mel_min_hz": -10.0}, "mel_min_hz"),
        ({"common_max_hz": 50.0}, "common_max_hz"),
        ({"common_max_hz": 30000.0}, "common_max_hz"),
        ({"spectral_rolloff_fraction": 1.5}, "spectral_rolloff_fraction"),
    ],
)
def test_extract_features_validates_parameter_bounds(param_kwargs, err_match):
    with pytest.raises(FeatureExtractionError, match=err_match):
        extract_features(sustained_vowel(), 16000, **param_kwargs)


@pytest.mark.parametrize("peak", [1.000001, -1.000001, 2.5, -3.0])
def test_extract_features_rejects_unnormalized_amplitude(peak):
    samples = sustained_vowel()
    samples[0] = peak
    with pytest.raises(FeatureExtractionError, match=r"normalized to \[-1\.0, 1\.0\]"):
        extract_features(samples, 16000)
