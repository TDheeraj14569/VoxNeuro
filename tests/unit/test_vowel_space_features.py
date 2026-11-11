"""Unit tests for multi-vowel formant extraction and Vowel Space Area (VSA)."""

from __future__ import annotations

import pytest

from tests.fixtures.synthetic_vowels import synthetic_formant_vowel
from voxneuro.audio.io import AudioRecord
from voxneuro.audio.task_preprocessing import preprocess_task_audio
from voxneuro.features.tasks.schema import (
    VOWEL_SPACE_FEATURE_NAMES,
    VOWEL_SPACE_SCHEMA_VERSION,
    vowel_space_schema_fingerprint,
)
from voxneuro.features.tasks.vowel_space import (
    calculate_vsa_triangle,
    extract_vowel_formants,
    extract_vowel_space_features,
)


def _prep_vowel(vowel_label: str = "a", duration: float = 2.0):
    samples = synthetic_formant_vowel(vowel_label=vowel_label, duration=duration)
    rec = AudioRecord(
        samples=samples.reshape(-1, 1),
        sample_rate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )
    return preprocess_task_audio(rec, task_type="vowel_space", target_sample_rate=16000)


class TestVowelSpaceFeatures:
    """Tests for Burg LPC formant extraction, multi-trial aggregation, and VSA."""

    def test_vowel_space_schema_fingerprint_and_features(self) -> None:
        fp = vowel_space_schema_fingerprint()
        assert isinstance(fp, str) and len(fp) == 64
        assert len(VOWEL_SPACE_FEATURE_NAMES) == 16
        assert "vowel_space_area_hz2" in VOWEL_SPACE_FEATURE_NAMES
        assert "f1_a_median_hz" in VOWEL_SPACE_FEATURE_NAMES

    def test_calculate_vsa_triangle_known_coordinates(self) -> None:
        """Verify triangle shoelace formula on known geometric vertices."""
        # Right-angle triangle in F1-F2 plane:
        # A = (100, 100), B = (400, 100), C = (100, 500)
        # Base = 300, Height = 400, Area = 0.5 * 300 * 400 = 60,000 Hz^2
        area = calculate_vsa_triangle(
            f1_a=100.0,
            f2_a=100.0,
            f1_i=400.0,
            f2_i=100.0,
            f1_u=100.0,
            f2_u=500.0,
        )
        assert area is not None
        assert area == pytest.approx(60000.0, abs=1.0)

    def test_calculate_vsa_triangle_returns_none_if_coordinate_missing(self) -> None:
        assert calculate_vsa_triangle(None, 1100.0, 300.0, 2200.0, 350.0, 850.0) is None
        assert calculate_vsa_triangle(700.0, None, 300.0, 2200.0, 350.0, 850.0) is None
        assert calculate_vsa_triangle(700.0, 1100.0, 300.0, 2200.0, float("nan"), 850.0) is None

    def test_formant_extraction_on_synthetic_vowels(self) -> None:
        # Test /a/
        prep_a = _prep_vowel("a", duration=2.0)
        res_a = extract_vowel_formants(prep_a.samples, prep_a.sample_rate, vowel_label="a")
        assert res_a.is_valid is True
        assert res_a.f1_median_hz is not None and res_a.f2_median_hz is not None
        # /a/ formants should be in expected range: F1 around 650-850 Hz, F2 around 950-1300 Hz
        assert 600.0 <= res_a.f1_median_hz <= 900.0
        assert 900.0 <= res_a.f2_median_hz <= 1400.0

        # Test /i/
        prep_i = _prep_vowel("i", duration=2.0)
        res_i = extract_vowel_formants(prep_i.samples, prep_i.sample_rate, vowel_label="i")
        assert res_i.is_valid is True
        assert res_i.f1_median_hz is not None and res_i.f2_median_hz is not None
        # /i/ formants: F1 low (250-450 Hz), F2 high (1500-2400 Hz)
        assert 200.0 <= res_i.f1_median_hz <= 500.0
        assert 1500.0 <= res_i.f2_median_hz <= 2500.0

        # Test /u/
        prep_u = _prep_vowel("u", duration=2.0)
        res_u = extract_vowel_formants(prep_u.samples, prep_u.sample_rate, vowel_label="u")
        assert res_u.is_valid is True
        assert res_u.f1_median_hz is not None and res_u.f2_median_hz is not None
        # /u/ formants: F1 low (250-500 Hz), F2 low/mid (700-1100 Hz)
        assert 250.0 <= res_u.f1_median_hz <= 550.0
        assert 700.0 <= res_u.f2_median_hz <= 1200.0

    def test_extract_vowel_space_complete_session(self) -> None:
        vowel_dict = {
            "a": _prep_vowel("a"),
            "i": _prep_vowel("i"),
            "u": _prep_vowel("u"),
        }
        vs_res = extract_vowel_space_features(vowel_dict)

        assert vs_res.task_status == "complete"
        assert vs_res.task_schema_version == VOWEL_SPACE_SCHEMA_VERSION
        assert vs_res.vsa_estimable is True

        vsa = vs_res.features["vowel_space_area_hz2"]
        assert vsa is not None
        assert vsa > 20000.0  # Plausible acoustic VSA area in Hz^2

        assert vs_res.features["f1_a_median_hz"] is not None
        assert vs_res.features["f2_i_median_hz"] is not None
        assert vs_res.features["f1_u_median_hz"] is not None

    def test_missing_corner_vowel_results_in_not_estimable(self) -> None:
        # Missing /u/
        vowel_dict = {
            "a": _prep_vowel("a"),
            "i": _prep_vowel("i"),
        }
        vs_res = extract_vowel_space_features(vowel_dict)

        assert vs_res.task_status == "not_estimable"
        assert vs_res.vsa_estimable is False
        assert vs_res.features["vowel_space_area_hz2"] is None
        assert any("NOT ESTIMABLE" in err for err in vs_res.errors)

    def test_multi_trial_aggregation_computes_median(self) -> None:
        trial1_a = _prep_vowel("a", duration=1.5)
        trial2_a = _prep_vowel("a", duration=2.0)
        vowel_dict = {
            "a": [trial1_a, trial2_a],
            "i": _prep_vowel("i"),
            "u": _prep_vowel("u"),
        }
        vs_res = extract_vowel_space_features(vowel_dict)

        assert vs_res.task_status == "complete"
        assert vs_res.features["valid_frames_a_count"] is not None
        assert vs_res.features["valid_frames_a_count"] > 20
