"""Diadochokinetic (DDK) speech analysis and syllable event timing extraction.

Implements acoustic event detection, syllable repetition rate estimation,
inter-event interval variability (SD, CV, RMSSD), and rate acceleration/drift
for Alternating Motion Rate (/pa/, /ta/, /ka/) and Sequential Motion Rate (/pa-ta-ka/).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.signal import find_peaks

from voxneuro.audio.task_preprocessing import TaskPreprocessingResult
from voxneuro.features.schema import configuration_fingerprint
from voxneuro.features.tasks.schema import (
    DDK_FEATURE_NAMES,
    DDK_SCHEMA_VERSION,
    ddk_schema_fingerprint,
)


@dataclass(frozen=True)
class DDKConfig:
    """Configurable parameters for DDK syllable event detection and analysis."""

    frame_ms: float = 20.0
    hop_ms: float = 5.0
    min_event_distance_ms: float = 80.0  # Refractory period (~12.5 Hz max)
    relative_prominence_fraction: float = 0.12  # Fraction of envelope dynamic range
    min_events_for_rate: int = 3
    min_intervals_for_variability: int = 3
    min_intervals_for_drift: int = 4


@dataclass
class DDKResult:
    """Complete acoustic output for a DDK speech task."""

    task_id: str
    task_type: str
    task_schema_version: str
    task_schema_fingerprint: str
    task_status: str
    stimulus: str
    features: dict[str, float | None]
    event_times_s: list[float]
    inter_event_intervals_s: list[float]
    quality: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    configuration_fingerprint: str = ""
    preprocessing_status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        """Return standardized JSON-serializable task dictionary."""
        d = asdict(self)
        d.pop("event_times_s", None)
        d.pop("inter_event_intervals_s", None)
        return d


def detect_ddk_events(
    samples: np.ndarray,
    sample_rate: int,
    config: DDKConfig | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Detect syllable acoustic burst/energy peak events and compute inter-event intervals.

    Returns:
        event_times: 1D array of detected event peak timestamps in seconds.
        envelope: 1D array of the computed RMS energy envelope.
    """
    cfg = config or DDKConfig()
    x = np.asarray(samples, dtype=np.float64)
    if len(x) == 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    frame_len = max(int(sample_rate * (cfg.frame_ms / 1000.0)), 16)
    hop_len = max(int(sample_rate * (cfg.hop_ms / 1000.0)), 4)

    # Compute short-time energy / RMS envelope
    n_frames = max((len(x) - frame_len) // hop_len + 1, 1)
    envelope = np.zeros(n_frames, dtype=np.float64)

    for i in range(n_frames):
        start = i * hop_len
        end = min(start + frame_len, len(x))
        frame = x[start:end]
        envelope[i] = math.sqrt(np.mean(frame**2)) if len(frame) > 0 else 0.0

    # Smooth envelope slightly with moving average (approx 15 ms window)
    smooth_len = max(int(15.0 / cfg.hop_ms), 3)
    if smooth_len % 2 == 0:
        smooth_len += 1
    if len(envelope) >= smooth_len:
        kernel = np.ones(smooth_len) / smooth_len
        smoothed = np.convolve(envelope, kernel, mode="same")
    else:
        smoothed = envelope

    # Dynamic peak detection parameters
    min_dist_frames = max(int(cfg.min_event_distance_ms / cfg.hop_ms), 1)
    env_max = float(np.max(smoothed))
    env_min = float(np.min(smoothed))
    dynamic_range = env_max - env_min

    if dynamic_range < 1e-5:
        return np.array([], dtype=np.float64), smoothed

    prominence = max(dynamic_range * cfg.relative_prominence_fraction, 0.001)
    height_floor = env_min + (dynamic_range * 0.10)

    peak_indices, _ = find_peaks(
        smoothed,
        distance=min_dist_frames,
        prominence=prominence,
        height=height_floor,
    )

    event_times = peak_indices * (hop_len / sample_rate)
    return event_times, smoothed


def extract_ddk_features(
    prep_result: TaskPreprocessingResult,
    task_id: str = "ddk_pa",
    stimulus: str = "AMR_PA",
    config: DDKConfig | None = None,
) -> DDKResult:
    """Extract temporal regularity and rate features for DDK syllable repetition."""
    cfg = config or DDKConfig()
    warnings: list[str] = []
    errors: list[str] = []

    samples = prep_result.samples
    sr = prep_result.sample_rate
    task_duration_s = prep_result.retained_duration_seconds

    # Initialize all features to null per schema contract
    features: dict[str, float | None] = {name: None for name in DDK_FEATURE_NAMES}
    features["task_duration_s"] = round(task_duration_s, 4)

    event_times, _ = detect_ddk_events(samples, sr, config=cfg)
    n_events = len(event_times)
    features["estimated_event_count"] = float(n_events)

    if n_events == 0:
        return DDKResult(
            task_id=task_id,
            task_type="ddk",
            task_schema_version=DDK_SCHEMA_VERSION,
            task_schema_fingerprint=ddk_schema_fingerprint(),
            task_status="insufficient_signal",
            stimulus=stimulus,
            features=features,
            event_times_s=[],
            inter_event_intervals_s=[],
            quality={
                "task_duration_s": task_duration_s,
                "event_count": 0,
                "preprocessing_fingerprint": prep_result.preprocessing_fingerprint,
            },
            warnings=["No syllable acoustic events detected in recording."],
            errors=["Insufficient speech signal for DDK evaluation."],
        )

    # Compute inter-event intervals (IEI)
    ieis = np.diff(event_times) if n_events >= 2 else np.array([], dtype=np.float64)
    n_intervals = len(ieis)
    features["valid_intervals_count"] = float(n_intervals)

    active_duration_s = float(event_times[-1] - event_times[0]) if n_events >= 2 else 0.0
    features["active_speech_duration_s"] = round(active_duration_s, 4) if n_events >= 2 else None

    # Syllable rate (events per second over active duration)
    if n_events >= cfg.min_events_for_rate and active_duration_s > 0.10:
        # Rate is defined as (N-1) / active_speech_duration_s = 1 / mean(IEI)
        event_rate = float(n_intervals / active_duration_s)
        features["estimated_event_rate_per_s"] = round(event_rate, 4)
    else:
        warnings.append(
            f"Fewer than {cfg.min_events_for_rate} events detected; repetition rate not estimable."
        )

    # Central tendencies of interval duration
    if n_intervals >= 2:
        mean_iei = float(np.mean(ieis))
        median_iei = float(np.median(ieis))
        features["mean_inter_event_interval_s"] = round(mean_iei, 4)
        features["median_inter_event_interval_s"] = round(median_iei, 4)
    else:
        mean_iei = None

    # Variability metrics (SD, CV, RMSSD)
    if n_intervals >= cfg.min_intervals_for_variability and mean_iei is not None:
        sd_iei = float(np.std(ieis, ddof=1))
        features["sd_inter_event_interval_s"] = round(sd_iei, 4)

        if mean_iei > 1e-5:
            cv_iei = float(sd_iei / mean_iei)
            features["cv_inter_event_interval"] = round(cv_iei, 4)

        # RMSSD: Root mean square of successive interval differences
        if n_intervals >= 3:
            succ_diffs = np.diff(ieis)
            rmssd = float(math.sqrt(np.mean(succ_diffs**2)))
            features["rmssd_inter_event_interval_s"] = round(rmssd, 4)

    # Rate drift / acceleration slope over event sequence
    if n_intervals >= cfg.min_intervals_for_drift:
        indices = np.arange(n_intervals, dtype=np.float64)
        # Linear fit: IEI_k = slope * k + intercept
        slope, _ = np.polyfit(indices, ieis, deg=1)
        features["inter_event_interval_slope_s_per_event"] = round(float(slope), 6)

    # Status determination
    if features["estimated_event_rate_per_s"] is not None:
        task_status = "complete"
    elif n_events > 0:
        task_status = "not_estimable"
    else:
        task_status = "insufficient_signal"

    return DDKResult(
        task_id=task_id,
        task_type="ddk",
        task_schema_version=DDK_SCHEMA_VERSION,
        task_schema_fingerprint=ddk_schema_fingerprint(),
        task_status=task_status,
        stimulus=stimulus,
        features=features,
        event_times_s=[round(t, 4) for t in event_times.tolist()],
        inter_event_intervals_s=[round(dt, 4) for dt in ieis.tolist()],
        quality={
            "task_duration_s": task_duration_s,
            "active_duration_s": active_duration_s,
            "event_count": n_events,
            "interval_count": n_intervals,
            "preprocessing_fingerprint": prep_result.preprocessing_fingerprint,
        },
        warnings=warnings,
        errors=errors,
        configuration_fingerprint=configuration_fingerprint(asdict(cfg)),
        preprocessing_status="completed",
    )
