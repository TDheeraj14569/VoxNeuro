"""Praat-compatible phonation measures calculated with Parselmouth."""

from __future__ import annotations

import logging

import numpy as np
import parselmouth
from parselmouth.praat import call

logger = logging.getLogger(__name__)


def extract_praat_features(
    samples: np.ndarray,
    sample_rate: int,
    pitch_floor_hz: float = 75.0,
    pitch_ceiling_hz: float = 500.0,
    pitch_step_seconds: float = 0.01,
) -> dict[str, float]:
    """Return F0 summaries, local jitter/shimmer, and mean HNR; invalid measures are NaN."""
    if isinstance(sample_rate, (bool, np.bool_)) or not isinstance(sample_rate, (int, np.integer)):
        raise TypeError(f"sample_rate must be an integer, not {type(sample_rate).__name__}.")
    if not (8000 <= int(sample_rate) <= 48000):
        raise ValueError(
            f"sample_rate must be an integer between 8000 and 48000 Hz, got {sample_rate}."
        )
    try:
        raw = np.asarray(samples)
    except (TypeError, ValueError) as exc:
        raise ValueError("Praat feature extraction requires a rectangular numeric array.") from exc
    if (
        isinstance(raw, (bool, np.bool_))
        or raw.dtype == np.bool_
        or not np.issubdtype(raw.dtype, np.number)
        or np.iscomplexobj(raw)
        or np.issubdtype(raw.dtype, np.complexfloating)
    ):
        raise ValueError("Praat feature extraction requires real numeric audio samples.")
    x = raw.astype(np.float64, copy=False)
    if x.ndim != 1:
        raise ValueError("Praat feature extraction requires mono one-dimensional audio.")
    if x.size == 0 or not np.isfinite(x).all():
        raise ValueError("Praat feature extraction requires finite, non-empty audio samples.")
    if np.any(x < -1.0) or np.any(x > 1.0):
        raise ValueError(
            f"Praat feature extraction requires normalized audio in [-1.0, 1.0]; observed peak is "
            f"{float(np.max(np.abs(x))):.3f}."
        )
    sound = parselmouth.Sound(x, sampling_frequency=sample_rate)
    pitch = sound.to_pitch_ac(
        time_step=pitch_step_seconds,
        pitch_floor=pitch_floor_hz,
        pitch_ceiling=pitch_ceiling_hz,
    )
    f0 = np.asarray(pitch.selected_array["frequency"], dtype=np.float64)
    f0 = f0[np.isfinite(f0) & (f0 > 0)]
    enough_pitch_frames = f0.size >= 3
    values: dict[str, float] = {
        "f0_mean_hz": float(np.mean(f0)) if enough_pitch_frames else np.nan,
        "f0_median_hz": float(np.median(f0)) if enough_pitch_frames else np.nan,
        "f0_sd_hz": float(np.std(f0, ddof=1)) if enough_pitch_frames else np.nan,
        "f0_min_hz": float(np.min(f0)) if enough_pitch_frames else np.nan,
        "f0_max_hz": float(np.max(f0)) if enough_pitch_frames else np.nan,
        "f0_range_hz": float(np.ptp(f0)) if enough_pitch_frames else np.nan,
        "jitter_local": np.nan,
        "shimmer_local": np.nan,
        "hnr_mean_db": np.nan,
    }
    try:
        pulses = call(sound, "To PointProcess (periodic, cc)", pitch_floor_hz, pitch_ceiling_hz)
        jitter = call(pulses, "Get jitter (local)", 0.0, 0.0, 0.0001, 0.02, 1.3)
        if np.isfinite(jitter):
            values["jitter_local"] = float(jitter)
        shimmer = call([sound, pulses], "Get shimmer (local)", 0.0, 0.0, 0.0001, 0.02, 1.3, 1.6)
        if np.isfinite(shimmer):
            values["shimmer_local"] = float(shimmer)
    except (parselmouth.PraatError, ValueError, RuntimeError) as exc:
        logger.debug("Praat pulse/jitter/shimmer extraction failed: %s", exc)
    try:
        harmonicity = sound.to_harmonicity_cc(
            time_step=pitch_step_seconds,
            minimum_pitch=pitch_floor_hz,
            silence_threshold=0.1,
            periods_per_window=1.0,
        )
        hnr = np.asarray(harmonicity.values, dtype=np.float64).reshape(-1)
        hnr = hnr[np.isfinite(hnr) & (hnr > -199.0)]
        if hnr.size:
            values["hnr_mean_db"] = float(np.mean(hnr))
    except (parselmouth.PraatError, ValueError, RuntimeError) as exc:
        logger.debug("Praat harmonicity extraction failed: %s", exc)
    return values
