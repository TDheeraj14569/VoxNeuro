"""Deterministic mono conversion, silence trimming, and resampling."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.signal import resample_poly

from voxneuro.audio.io import (
    MAX_SUPPORTED_SAMPLE_RATE,
    MIN_SUPPORTED_SAMPLE_RATE,
    AudioRecord,
)
from voxneuro.audio.validation import AudioValidationConfig, validate_audio
from voxneuro.exceptions import AudioValidationError


@dataclass(frozen=True)
class PreprocessingResult:
    samples: np.ndarray
    sample_rate: int
    original_sample_rate: int
    original_channels: int
    dc_offset_removed: float
    trim_start_seconds: float
    trimmed_tail_seconds: float
    retained_duration_seconds: float
    resampled: bool


def preprocess_audio(
    record: AudioRecord,
    target_sample_rate: int = 16000,
    silence_relative_db: float = 35.0,
    mono_policy: str = "average_with_phase_check",
    validation_config: AudioValidationConfig | None = None,
) -> PreprocessingResult:
    """Validate, average stereo after checks, remove DC, trim margins, and resample."""
    config = validation_config or AudioValidationConfig()
    # Validate the original channels before downmixing can erase phase evidence.
    report = validate_audio(record, config)
    if not report.valid:
        raise AudioValidationError(" ".join(report.errors))
    if (
        isinstance(target_sample_rate, bool)
        or not isinstance(target_sample_rate, (int, np.integer))
        or not MIN_SUPPORTED_SAMPLE_RATE <= int(target_sample_rate) <= MAX_SUPPORTED_SAMPLE_RATE
    ):
        raise ValueError(
            f"Target sample rate must be an integer between {MIN_SUPPORTED_SAMPLE_RATE} "
            f"and {MAX_SUPPORTED_SAMPLE_RATE} Hz."
        )
    if (
        isinstance(silence_relative_db, bool)
        or not isinstance(silence_relative_db, (int, float))
        or not math.isfinite(silence_relative_db)
        or not (0.0 < float(silence_relative_db) <= 100.0)
    ):
        raise ValueError("silence_relative_db must be a finite positive number in (0.0, 100.0] dB.")
    if mono_policy != "average_with_phase_check":
        raise ValueError(f"Unsupported mono conversion policy: {mono_policy!r}.")
    original = record.samples
    mono = original.mean(axis=1) if original.ndim == 2 else original.copy()
    offset = float(np.mean(mono))
    mono = np.asarray(mono - offset, dtype=np.float64)
    frame = max(1, int(record.sample_rate * config.frame_ms / 1000))
    count = len(mono) // frame
    if count:
        blocks = mono[: count * frame].reshape(count, frame)
        rms = np.sqrt(np.mean(blocks * blocks, axis=1))
        threshold = max(float(rms.max()) * 10 ** (-silence_relative_db / 20), 1e-5)
        active = np.flatnonzero(rms >= threshold)
        if active.size:
            start = max(0, int(active[0]) * frame - int(0.05 * record.sample_rate))
            stop = min(len(mono), (int(active[-1]) + 1) * frame + int(0.05 * record.sample_rate))
        else:
            start, stop = 0, len(mono)
    else:
        start, stop = 0, len(mono)
    segment = mono[start:stop]
    if len(segment) == 0:
        raise AudioValidationError("No signal remained after trimming silence.")
    trimmed_record = AudioRecord(
        samples=segment[:, np.newaxis],
        sample_rate=record.sample_rate,
        channels=1,
        subtype=record.subtype,
        format=record.format,
    )
    trimmed_quality = validate_audio(trimmed_record, config)
    if not trimmed_quality.valid:
        raise AudioValidationError(
            "Signal did not remain usable after silence trimming. "
            + " ".join(trimmed_quality.errors)
        )
    if record.sample_rate != target_sample_rate:
        from math import gcd

        common = gcd(record.sample_rate, target_sample_rate)
        processed = resample_poly(
            segment, target_sample_rate // common, record.sample_rate // common
        )
    else:
        processed = segment
    processed = np.asarray(processed, dtype=np.float64)
    if not np.isfinite(processed).all() or processed.ndim != 1 or processed.size == 0:
        raise AudioValidationError("Preprocessing produced invalid samples.")
    return PreprocessingResult(
        samples=processed,
        sample_rate=target_sample_rate,
        original_sample_rate=record.sample_rate,
        original_channels=record.channels,
        dc_offset_removed=offset,
        trim_start_seconds=start / record.sample_rate,
        trimmed_tail_seconds=(len(mono) - stop) / record.sample_rate,
        retained_duration_seconds=len(segment) / record.sample_rate,
        resampled=record.sample_rate != target_sample_rate,
    )
