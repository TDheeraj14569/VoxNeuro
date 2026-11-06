"""Single entry point that enforces the versioned feature order."""

from __future__ import annotations

import numpy as np

from voxneuro.exceptions import FeatureExtractionError
from voxneuro.features.parselmouth_features import extract_praat_features
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.features.spectral_features import extract_spectral_features


def extract_features(
    samples: np.ndarray,
    sample_rate: int,
    *,
    original_sample_rate: int | None = None,
    pitch_floor_hz: float = 75.0,
    pitch_ceiling_hz: float = 500.0,
    pitch_step_seconds: float = 0.01,
    mfcc_count: int = 13,
    mel_bands: int = 40,
    fft_window_samples: int = 1024,
    hop_samples: int = 160,
    mel_min_hz: float = 50.0,
    common_max_hz: float = 3800.0,
    spectral_rolloff_fraction: float = 0.85,
    preprocessing_config_fingerprint: str | None = None,
) -> dict[str, float | str | None]:
    """Extract schema-ordered measures. Failed voice measures remain NaN, never zero."""
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1:
        raise FeatureExtractionError(
            "Feature extraction requires mono audio as a one-dimensional array. "
            "Downmix stereo audio during preprocessing first."
        )
    if (
        isinstance(mfcc_count, (bool, np.bool_))
        or not isinstance(mfcc_count, (int, np.integer))
        or mfcc_count != 13
    ):
        raise FeatureExtractionError(
            "The current feature schema requires exactly 13 MFCC coefficients."
        )
    if sample_rate <= 0 or x.size == 0 or not np.isfinite(x).all():
        raise FeatureExtractionError(
            "Feature input must be finite, non-empty audio with a valid sample rate."
        )
    try:
        values = extract_praat_features(
            x, sample_rate, pitch_floor_hz, pitch_ceiling_hz, pitch_step_seconds
        )
        values.update(
            extract_spectral_features(
                x,
                sample_rate,
                mfcc_count=mfcc_count,
                mel_bands=mel_bands,
                fft_window_samples=fft_window_samples,
                hop_samples=hop_samples,
                mel_min_hz=mel_min_hz,
                common_max_hz=common_max_hz,
                original_sample_rate=original_sample_rate,
                rolloff_fraction=spectral_rolloff_fraction,
            )
        )
    except (ValueError, RuntimeError, FloatingPointError) as exc:
        raise FeatureExtractionError(f"Acoustic feature extraction failed: {exc}") from exc
    missing = set(FEATURE_NAMES) - values.keys()
    if missing:
        raise FeatureExtractionError(
            f"Extractor did not return expected features: {sorted(missing)}"
        )
    row: dict[str, float | str | None] = {name: float(values[name]) for name in FEATURE_NAMES}
    row["schema_version"] = SCHEMA_VERSION
    row["schema_fingerprint"] = schema_fingerprint()
    row["feature_config_fingerprint"] = feature_config_fingerprint(
        {
            "pitch_floor_hz": pitch_floor_hz,
            "pitch_ceiling_hz": pitch_ceiling_hz,
            "pitch_step_seconds": pitch_step_seconds,
            "mfcc_count": mfcc_count,
            "mel_bands": mel_bands,
            "fft_window_samples": fft_window_samples,
            "hop_samples": hop_samples,
            "mel_min_hz": mel_min_hz,
            "common_max_hz": common_max_hz,
            "spectral_rolloff_fraction": spectral_rolloff_fraction,
        }
    )
    row["preprocessing_config_fingerprint"] = preprocessing_config_fingerprint
    return row
