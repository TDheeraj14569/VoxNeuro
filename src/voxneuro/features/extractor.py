"""Single entry point that enforces the versioned feature order."""

from __future__ import annotations

import logging

import librosa
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

logger = logging.getLogger(__name__)


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
    if (
        isinstance(sample_rate, (bool, np.bool_))
        or not isinstance(sample_rate, (int, np.integer))
        or not (8000 <= int(sample_rate) <= 48000)
    ):
        raise FeatureExtractionError(
            "Feature extraction requires an integer sample rate between 8,000 and 48,000 Hz; "
            f"got {sample_rate!r}."
        )
    if original_sample_rate is not None:
        if (
            isinstance(original_sample_rate, (bool, np.bool_))
            or not isinstance(original_sample_rate, (int, np.integer))
            or not (8000 <= int(original_sample_rate) <= 48000)
        ):
            raise FeatureExtractionError(
                "Original sample rate must be an integer between 8,000 and 48,000 Hz."
            )

    # Validate numeric parameters
    for p_name, p_val in (
        ("pitch_floor_hz", pitch_floor_hz),
        ("pitch_ceiling_hz", pitch_ceiling_hz),
        ("pitch_step_seconds", pitch_step_seconds),
        ("mel_min_hz", mel_min_hz),
        ("common_max_hz", common_max_hz),
        ("spectral_rolloff_fraction", spectral_rolloff_fraction),
    ):
        if (
            isinstance(p_val, (bool, np.bool_))
            or not isinstance(p_val, (int, float, np.number))
            or not np.isfinite(p_val)
        ):
            raise FeatureExtractionError(f"{p_name} must be a finite real number.")

    for p_name, p_val in (
        ("mel_bands", mel_bands),
        ("fft_window_samples", fft_window_samples),
        ("hop_samples", hop_samples),
    ):
        if isinstance(p_val, (bool, np.bool_)) or not isinstance(p_val, (int, np.integer)):
            raise FeatureExtractionError(f"{p_name} must be an integer.")

    if preprocessing_config_fingerprint is not None:
        if (
            isinstance(preprocessing_config_fingerprint, (bool, np.bool_))
            or not isinstance(preprocessing_config_fingerprint, str)
            or len(preprocessing_config_fingerprint) != 64
            or not all(c in "0123456789abcdefABCDEF" for c in preprocessing_config_fingerprint)
        ):
            raise FeatureExtractionError(
                "preprocessing_config_fingerprint must be None or a 64-character hex string."
            )

    if (
        isinstance(pitch_floor_hz, (bool, np.bool_))
        or not isinstance(pitch_floor_hz, (int, float, np.number))
        or not (30.0 < pitch_floor_hz <= 500.0)
    ):
        raise FeatureExtractionError(
            "pitch_floor_hz must be a number strictly between 30.0 and 500.0 Hz."
        )
    if (
        isinstance(pitch_ceiling_hz, (bool, np.bool_))
        or not isinstance(pitch_ceiling_hz, (int, float, np.number))
        or not (60.0 <= pitch_ceiling_hz <= 1200.0)
    ):
        raise FeatureExtractionError(
            "pitch_ceiling_hz must be a number between 60.0 and 1200.0 Hz."
        )
    if pitch_floor_hz >= pitch_ceiling_hz:
        raise FeatureExtractionError("pitch_floor_hz must be strictly less than pitch_ceiling_hz.")
    if (
        isinstance(pitch_step_seconds, (bool, np.bool_))
        or not isinstance(pitch_step_seconds, (int, float, np.number))
        or not (0.001 < pitch_step_seconds <= 0.1)
    ):
        raise FeatureExtractionError(
            "pitch_step_seconds must be a number strictly between 0.001 and 0.1 seconds."
        )
    if mel_bands < 13 or mel_bands > 256:
        raise FeatureExtractionError("mel_bands must be between 13 and 256.")
    if (
        fft_window_samples < 256
        or fft_window_samples > 8192
        or (fft_window_samples & (fft_window_samples - 1)) != 0
    ):
        raise FeatureExtractionError(
            "fft_window_samples must be a power of two between 256 and 8192."
        )
    if hop_samples < 1 or hop_samples > fft_window_samples:
        raise FeatureExtractionError("hop_samples must be positive and <= fft_window_samples.")
    if not (0.0 <= mel_min_hz <= 1000.0):
        raise FeatureExtractionError("mel_min_hz must be between 0.0 and 1000.0 Hz.")
    effective_rate = original_sample_rate if original_sample_rate is not None else sample_rate
    if (
        not (100.0 < common_max_hz <= 24000.0)
        or common_max_hz <= mel_min_hz
        or common_max_hz >= (effective_rate / 2)
    ):
        raise FeatureExtractionError(
            f"common_max_hz must be > mel_min_hz, <= 24000.0 Hz, and strictly below Nyquist "
            f"({effective_rate / 2} Hz)."
        )
    if not (0.0 < spectral_rolloff_fraction < 1.0):
        raise FeatureExtractionError(
            "spectral_rolloff_fraction must be strictly between 0.0 and 1.0."
        )
    try:
        raw = np.asarray(samples)
    except (TypeError, ValueError) as exc:
        raise FeatureExtractionError(
            "Audio samples must form a rectangular numeric array."
        ) from exc
    if (
        isinstance(raw, (bool, np.bool_))
        or raw.dtype == np.bool_
        or not np.issubdtype(raw.dtype, np.floating)
        or np.iscomplexobj(raw)
        or np.issubdtype(raw.dtype, np.complexfloating)
    ):
        raise FeatureExtractionError(
            "Feature extraction requires normalized numeric floating-point audio samples in "
            "[-1.0, 1.0]. Integer PCM must be normalized before extraction."
        )
    x = raw.astype(np.float64, copy=False)
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
    if x.size == 0 or not np.isfinite(x).all():
        raise FeatureExtractionError(
            "Feature input must be finite, non-empty audio with a valid sample rate."
        )
    if np.any(x < -1.0) or np.any(x > 1.0):
        raise FeatureExtractionError(
            f"Audio samples must be normalized to [-1.0, 1.0]; observed peak is "
            f"{float(np.max(np.abs(x))):.3f}."
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
    except (ValueError, TypeError, FloatingPointError, librosa.ParameterError) as exc:
        raise FeatureExtractionError(f"Acoustic feature extraction failed: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error during feature extraction: %s", exc)
        raise FeatureExtractionError(
            f"Unexpected error during acoustic feature extraction: {exc}"
        ) from exc
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
