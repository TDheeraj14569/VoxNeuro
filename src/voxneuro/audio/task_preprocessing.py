"""Task-specific audio preprocessing for multi-task speech analysis.

Implements pause-preserving preprocessing for DDK and connected speech,
and conservative margin trimming for discrete vowel formant analysis.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy.signal import resample_poly

from voxneuro.audio.io import (
    MAX_SUPPORTED_SAMPLE_RATE,
    MIN_SUPPORTED_SAMPLE_RATE,
    AudioRecord,
)
from voxneuro.audio.task_validation import (
    TaskAudioValidationConfig,
    validate_task_audio,
)
from voxneuro.exceptions import AudioValidationError


@dataclass(frozen=True)
class TaskPreprocessingResult:
    """Preprocessed normalized mono audio samples and transformation metadata."""

    samples: np.ndarray
    sample_rate: int
    original_sample_rate: int
    original_channels: int
    dc_offset_removed: float
    trim_start_seconds: float
    trimmed_tail_seconds: float
    retained_duration_seconds: float
    resampled: bool
    preprocessing_fingerprint: str

    def to_metadata(self) -> dict[str, object]:
        """Return JSON-serializable metadata without raw sample arrays."""
        d = asdict(self)
        d.pop("samples")
        return d


def preprocess_task_audio(
    record: AudioRecord,
    task_type: str = "ddk",
    target_sample_rate: int = 16000,
    validation_config: TaskAudioValidationConfig | None = None,
    preserve_full_duration: bool | None = None,
) -> TaskPreprocessingResult:
    """Validate, downmix to mono, remove DC offset, optionally trim margins, and resample.

    For DDK and connected speech, full task duration and internal pauses are
    preserved by default to avoid corrupting speech rate and pause statistics.
    For vowel formant trials, silence margins outside the vowel are trimmed.
    """
    cfg = validation_config or TaskAudioValidationConfig.for_task(task_type)
    quality = validate_task_audio(record, task_type=task_type, config=cfg)
    if not quality.valid:
        raise AudioValidationError(
            f"Task audio validation failed for '{task_type}': {' '.join(quality.errors)}"
        )

    if (
        isinstance(target_sample_rate, bool)
        or not isinstance(target_sample_rate, (int, np.integer))
        or not (MIN_SUPPORTED_SAMPLE_RATE <= int(target_sample_rate) <= MAX_SUPPORTED_SAMPLE_RATE)
    ):
        raise ValueError(
            f"Target sample rate must be an integer between {MIN_SUPPORTED_SAMPLE_RATE} "
            f"and {MAX_SUPPORTED_SAMPLE_RATE} Hz."
        )

    raw = np.asarray(record.samples, dtype=np.float64)
    if raw.ndim == 1:
        mono = raw
        channels = 1
    elif raw.ndim == 2:
        channels = raw.shape[1]
        mono = raw.mean(axis=1)
    else:
        raise ValueError(f"Expected 1D or 2D audio array, got ndim={raw.ndim}")

    orig_sr = int(record.sample_rate)
    target_sr = int(target_sample_rate)

    # 1. DC Offset Removal
    dc_offset = float(np.mean(mono))
    centered = mono - dc_offset

    # 2. Timing Preservation & Trimming Decision
    # For DDK and connected speech, preserve full duration.
    # For vowel space trials, trim silence beyond 40 dBFS with 100ms padding.
    should_preserve = preserve_full_duration
    if should_preserve is None:
        should_preserve = task_type.lower() in ("ddk", "connected_speech")

    trim_start_s = 0.0
    trim_tail_s = 0.0

    if should_preserve or len(centered) == 0:
        processed_mono = centered
    else:
        # Conservative silence trimming for isolated vowel trials
        abs_sig = np.abs(centered)
        max_val = float(np.max(abs_sig))
        if max_val > 1e-5:
            threshold = max(max_val * 0.01, 0.001)  # ~40 dB below peak
            above = np.where(abs_sig >= threshold)[0]
            if len(above) > 0:
                pad_samples = int(orig_sr * 0.10)  # 100 ms padding
                first_idx = max(0, int(above[0]) - pad_samples)
                last_idx = min(len(centered), int(above[-1]) + 1 + pad_samples)
                trim_start_s = float(first_idx / orig_sr)
                trim_tail_s = float((len(centered) - last_idx) / orig_sr)
                processed_mono = centered[first_idx:last_idx]
            else:
                processed_mono = centered
        else:
            processed_mono = centered

    # 3. Resampling
    resampled = False
    if target_sr != orig_sr and len(processed_mono) > 0:
        gcd = math.gcd(target_sr, orig_sr)
        up = target_sr // gcd
        down = orig_sr // gcd
        resampled_samples = resample_poly(processed_mono, up, down).astype(np.float64)
        resampled = True
    else:
        resampled_samples = processed_mono.astype(np.float64)

    # Re-normalize to max peak 1.0 if resampling introduced slight overshoot
    peak = float(np.max(np.abs(resampled_samples))) if len(resampled_samples) > 0 else 0.0
    if peak > 1.0:
        resampled_samples = resampled_samples / peak

    retained_dur_s = float(len(resampled_samples) / target_sr) if target_sr > 0 else 0.0

    # Deterministic fingerprint of preprocessing configuration
    params = {
        "task_type": task_type,
        "target_sample_rate": target_sr,
        "original_sample_rate": orig_sr,
        "channels": channels,
        "preserve_full_duration": bool(should_preserve),
    }
    param_bytes = json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fp = hashlib.sha256(param_bytes).hexdigest()

    return TaskPreprocessingResult(
        samples=resampled_samples,
        sample_rate=target_sr,
        original_sample_rate=orig_sr,
        original_channels=channels,
        dc_offset_removed=round(dc_offset, 6),
        trim_start_seconds=round(trim_start_s, 4),
        trimmed_tail_seconds=round(trim_tail_s, 4),
        retained_duration_seconds=round(retained_dur_s, 4),
        resampled=resampled,
        preprocessing_fingerprint=fp,
    )
