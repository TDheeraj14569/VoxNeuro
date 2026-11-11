"""Task-specific audio quality validation for multi-task speech analysis.

Implements independent validation rules for Diadochokinetic (DDK) speech,
connected speech, multi-vowel formant trials, and legacy sustained vowels,
avoiding the application of steady-vowel harmonic heuristics to dynamic speech.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from voxneuro.audio.io import (
    MAX_SUPPORTED_SAMPLE_RATE,
    MIN_SUPPORTED_SAMPLE_RATE,
    AudioRecord,
)
from voxneuro.audio.quality import frame_rms


@dataclass(frozen=True)
class TaskAudioValidationConfig:
    """Configurable boundaries for task-specific audio validation."""

    min_duration_seconds: float = 2.0
    max_duration_seconds: float = 120.0
    min_rms: float = 0.002
    max_peak: float = 0.999
    clipping_fraction_limit: float = 0.01
    min_active_duration_seconds: float = 0.8
    frame_ms: int = 20
    mono_policy: str = "average_with_phase_check"

    @classmethod
    def for_task(cls, task_type: str) -> TaskAudioValidationConfig:
        """Return default validation parameters tailored to a specific speech task."""
        t = task_type.strip().lower()
        if t == "ddk":
            return cls(
                min_duration_seconds=2.0,
                max_duration_seconds=20.0,
                min_rms=0.002,
                max_peak=0.999,
                clipping_fraction_limit=0.01,
                min_active_duration_seconds=0.6,
                frame_ms=20,
            )
        if t == "connected_speech":
            return cls(
                min_duration_seconds=5.0,
                max_duration_seconds=180.0,
                min_rms=0.002,
                max_peak=0.999,
                clipping_fraction_limit=0.01,
                min_active_duration_seconds=1.5,
                frame_ms=25,
            )
        if t == "vowel_space":
            return cls(
                min_duration_seconds=1.0,
                max_duration_seconds=15.0,
                min_rms=0.003,
                max_peak=0.999,
                clipping_fraction_limit=0.01,
                min_active_duration_seconds=0.5,
                frame_ms=20,
            )
        # Sustained vowel default
        return cls(
            min_duration_seconds=1.5,
            max_duration_seconds=30.0,
            min_rms=0.003,
            max_peak=0.999,
            clipping_fraction_limit=0.01,
            min_active_duration_seconds=0.8,
            frame_ms=20,
        )


@dataclass
class TaskAudioQuality:
    """Detailed quality and diagnostic report for task audio."""

    valid: bool
    task_type: str
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    peak_amplitude: float = 0.0
    rms_amplitude: float = 0.0
    clipping_fraction: float = 0.0
    active_speech_fraction: float = 0.0
    estimated_snr_db: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)


def validate_task_audio(
    record: AudioRecord,
    task_type: str = "ddk",
    config: TaskAudioValidationConfig | None = None,
) -> TaskAudioQuality:
    """Validate audio specifically for the designated task without sustained-vowel bias.

    Checks:
      - Supported sample rate (8000 Hz to 48000 Hz)
      - Finite, real numeric values
      - Array dimensionality (1 or 2 channels)
      - Stereo phase cancellation check
      - Task-specific duration bounds
      - Peak level ceiling and clipping threshold
      - RMS energy floor
      - Task-specific activity / signal presence
    """
    cfg = config or TaskAudioValidationConfig.for_task(task_type)
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Sample rate check
    sr = record.sample_rate
    if (
        isinstance(sr, bool)
        or not isinstance(sr, (int, np.integer))
        or not (MIN_SUPPORTED_SAMPLE_RATE <= int(sr) <= MAX_SUPPORTED_SAMPLE_RATE)
    ):
        errors.append(
            f"Sample rate must be an integer between {MIN_SUPPORTED_SAMPLE_RATE} "
            f"and {MAX_SUPPORTED_SAMPLE_RATE} Hz, got {sr}."
        )
        return TaskAudioQuality(
            valid=False,
            task_type=task_type,
            status="quality_failed",
            errors=errors,
            warnings=warnings,
        )

    # 2. Array shape & numeric finiteness check
    try:
        raw = np.asarray(record.samples)
    except (TypeError, ValueError):
        return TaskAudioQuality(
            valid=False,
            task_type=task_type,
            status="quality_failed",
            errors=["Audio samples must form a rectangular numeric array."],
            warnings=warnings,
        )

    if (
        isinstance(raw, bool)
        or raw.dtype == bool
        or not np.issubdtype(raw.dtype, np.number)
        or np.issubdtype(raw.dtype, np.complexfloating)
    ):
        return TaskAudioQuality(
            valid=False,
            task_type=task_type,
            status="quality_failed",
            errors=["Audio samples must contain real numeric values."],
            warnings=warnings,
        )

    if raw.size == 0:
        return TaskAudioQuality(
            valid=False,
            task_type=task_type,
            status="quality_failed",
            errors=["Audio recording is empty (zero samples)."],
            warnings=warnings,
        )

    # Reshape 1D to (N, 1) if necessary
    if raw.ndim == 1:
        x = raw[:, np.newaxis].astype(np.float64, copy=False)
    elif raw.ndim == 2:
        x = raw.astype(np.float64, copy=False)
    else:
        return TaskAudioQuality(
            valid=False,
            task_type=task_type,
            status="quality_failed",
            errors=[f"Audio samples array must be 1D or 2D, got ndim={raw.ndim}."],
            warnings=warnings,
        )

    if x.shape[1] not in (1, 2):
        return TaskAudioQuality(
            valid=False,
            task_type=task_type,
            status="quality_failed",
            errors=[f"Channel count must be 1 or 2, got {x.shape[1]}."],
            warnings=warnings,
        )

    if not np.all(np.isfinite(x)):
        return TaskAudioQuality(
            valid=False,
            task_type=task_type,
            status="quality_failed",
            errors=["Audio samples contain NaN or infinite values."],
            warnings=warnings,
        )

    # 3. Stereo Phase Check
    if x.shape[1] == 2:
        ch0, ch1 = x[:, 0], x[:, 1]
        std0, std1 = np.std(ch0), np.std(ch1)
        if std0 > 1e-6 and std1 > 1e-6:
            corr = float(np.corrcoef(ch0, ch1)[0, 1])
            if corr < -0.85:
                errors.append(
                    f"Stereo channels exhibit severe destructive phase cancellation (r={corr:.2f})."
                )
        mono_x = 0.5 * (ch0 + ch1)
    else:
        mono_x = x[:, 0]

    n_samples = len(mono_x)
    duration_s = float(n_samples / sr)

    # 4. Duration Bounds
    if duration_s < cfg.min_duration_seconds:
        errors.append(
            f"Recording duration ({duration_s:.2f} s) is below the minimum required "
            f"for task '{task_type}' ({cfg.min_duration_seconds:.2f} s)."
        )
    if duration_s > cfg.max_duration_seconds:
        errors.append(
            f"Recording duration ({duration_s:.2f} s) exceeds maximum allowable limit "
            f"({cfg.max_duration_seconds:.2f} s)."
        )

    # 5. Amplitude, Peak, and Clipping Metrics
    abs_samples = np.abs(mono_x)
    peak_amp = float(np.max(abs_samples)) if n_samples > 0 else 0.0
    rms_amp = float(np.sqrt(np.mean(mono_x**2))) if n_samples > 0 else 0.0
    clipping_count = int(np.count_nonzero(abs_samples >= cfg.max_peak))
    clipping_fraction = float(clipping_count / n_samples) if n_samples > 0 else 0.0

    if peak_amp >= cfg.max_peak and clipping_fraction > cfg.clipping_fraction_limit:
        errors.append(
            f"Severe acoustic clipping detected: {clipping_fraction:.2%} of samples reach "
            f"full scale (limit: {cfg.clipping_fraction_limit:.2%})."
        )
    elif peak_amp >= cfg.max_peak:
        warnings.append("Isolated peak samples touch full scale; gain staging advised.")

    if rms_amp < cfg.min_rms:
        errors.append(
            f"Audio level is too quiet: RMS amplitude ({rms_amp:.4f}) is below minimum "
            f"threshold ({cfg.min_rms:.4f})."
        )

    # 6. Active Speech Activity & Dynamic Range Estimation
    mono_ac = mono_x - float(np.mean(mono_x)) if n_samples > 0 else mono_x
    _, f_rms = frame_rms(mono_ac, sample_rate=int(sr), frame_ms=int(cfg.frame_ms))

    if len(f_rms) > 0:
        peak_rms = float(np.max(f_rms))
        raw_floor = float(np.percentile(f_rms, 10))
        noise_floor = min(raw_floor, peak_rms * 0.1)
        active_thresh = max(cfg.min_rms * 0.5, peak_rms * 0.05, noise_floor * 2.0)
        active_frames = np.count_nonzero(f_rms >= active_thresh)
        active_fraction = float(active_frames / len(f_rms))
        active_duration_s = float(active_fraction * duration_s)

        snr_est_db = float(20.0 * math.log10(max(peak_rms, 1e-6) / max(noise_floor, 1e-6)))
    else:
        active_fraction = 0.0
        active_duration_s = 0.0
        snr_est_db = 0.0

    # Task-specific activity validation
    if active_duration_s < cfg.min_active_duration_seconds:
        errors.append(
            f"Insufficient active speech detected ({active_duration_s:.2f} s; minimum "
            f"required is {cfg.min_active_duration_seconds:.2f} s)."
        )

    status = "complete"
    if errors:
        # Distinguish general quality failure from insufficient signal
        if any("Insufficient active speech" in e or "too quiet" in e for e in errors):
            status = "insufficient_signal"
        else:
            status = "quality_failed"

    return TaskAudioQuality(
        valid=len(errors) == 0,
        task_type=task_type,
        status=status,
        errors=errors,
        warnings=warnings,
        duration_seconds=round(duration_s, 4),
        peak_amplitude=round(peak_amp, 4),
        rms_amplitude=round(rms_amp, 6),
        clipping_fraction=round(clipping_fraction, 6),
        active_speech_fraction=round(active_fraction, 4),
        estimated_snr_db=round(snr_est_db, 2),
        metrics={
            "sample_rate": sr,
            "channels": x.shape[1],
            "total_samples": n_samples,
            "active_duration_seconds": round(active_duration_s, 4),
        },
    )
