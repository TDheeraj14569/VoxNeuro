"""Connected speech analysis and voice activity segmentation.

Implements Voice Activity Detection (VAD), pause timing, speech bout statistics,
fundamental frequency prosody (median, SD, range in semitones), and intensity dynamics.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import parselmouth

from voxneuro.audio.task_preprocessing import TaskPreprocessingResult
from voxneuro.features.schema import configuration_fingerprint
from voxneuro.features.tasks.schema import (
    CONNECTED_SPEECH_FEATURE_NAMES,
    CONNECTED_SPEECH_SCHEMA_VERSION,
    connected_speech_schema_fingerprint,
)

STANDARD_PASSAGE_TEXT = (
    "The North Wind and the Sun were disputing which was the stronger, "
    "when a traveler came along wrapped in a warm cloak. "
    "They agreed that the one who first succeeded in making the traveler take his cloak off "
    "should be considered stronger than the other. "
    "Then the North Wind blew as hard as he could, but the more he blew the more closely did "
    "the traveler fold his cloak around him; and at last the North Wind gave up the attempt. "
    "Then the Sun shined out warmly, and immediately the traveler took off his cloak. "
    "And so the North Wind was obliged to confess that the Sun was the stronger of the two."
)

STANDARD_PASSAGE_ID = "north_wind_sun_en_v1"
STANDARD_LANGUAGE_CODE = "en-US"


@dataclass(frozen=True)
class ConnectedSpeechConfig:
    """Configurable parameters for connected speech segmentation and prosodic analysis."""

    frame_ms: float = 25.0
    hop_ms: float = 10.0
    min_pause_ms: float = 200.0  # Pauses >= 200ms
    min_speech_bout_ms: float = 100.0  # Minimum continuous speech bout
    short_pause_merge_ms: float = 60.0  # Merge closures shorter than 60ms
    pitch_floor_hz: float = 75.0
    pitch_ceiling_hz: float = 500.0
    min_voiced_frames: int = 10


@dataclass
class ConnectedSpeechResult:
    """Complete acoustic output for a connected speech task."""

    task_id: str
    task_type: str
    task_schema_version: str
    task_schema_fingerprint: str
    task_status: str
    stimulus_id: str
    language_code: str
    features: dict[str, float | None]
    pause_intervals_s: list[tuple[float, float]]
    speech_bout_intervals_s: list[tuple[float, float]]
    quality: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    configuration_fingerprint: str = ""
    preprocessing_status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        """Return standardized JSON-serializable task dictionary."""
        d = asdict(self)
        d.pop("pause_intervals_s", None)
        d.pop("speech_bout_intervals_s", None)
        return d


def segment_speech_activity(
    samples: np.ndarray,
    sample_rate: int,
    config: ConnectedSpeechConfig | None = None,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], np.ndarray, np.ndarray]:
    """Segment audio into speech bouts and silent pauses using energy-based VAD.

    Returns:
        speech_bouts: list of (start_s, end_s) intervals for continuous speech.
        pauses: list of (start_s, end_s) intervals for pauses >= min_pause_ms.
        frame_times: 1D array of frame center timestamps.
        frame_rms_values: 1D array of frame RMS amplitudes.
    """
    cfg = config or ConnectedSpeechConfig()
    x = np.asarray(samples, dtype=np.float64)
    total_dur_s = float(len(x) / sample_rate) if sample_rate > 0 else 0.0

    if len(x) == 0:
        return [], [], np.array([], dtype=np.float64), np.array([], dtype=np.float64)

    frame_len = max(int(sample_rate * (cfg.frame_ms / 1000.0)), 16)
    hop_len = max(int(sample_rate * (cfg.hop_ms / 1000.0)), 4)

    n_frames = max((len(x) - frame_len) // hop_len + 1, 1)
    frame_rms_vals = np.zeros(n_frames, dtype=np.float64)
    frame_times = (np.arange(n_frames) * hop_len + frame_len / 2.0) / sample_rate

    for i in range(n_frames):
        start = i * hop_len
        end = min(start + frame_len, len(x))
        frame = x[start:end]
        frame_rms_vals[i] = math.sqrt(np.mean(frame**2)) if len(frame) > 0 else 0.0

    # Adaptive noise floor and energy threshold
    noise_floor = float(np.percentile(frame_rms_vals, 10))
    peak_rms = float(np.max(frame_rms_vals))
    dynamic_range = peak_rms - noise_floor

    if dynamic_range < 1e-5:
        # Signal is uniform (silence or flat tone)
        return [], [(0.0, total_dur_s)], frame_times, frame_rms_vals

    vad_threshold = max(noise_floor + (dynamic_range * 0.12), 0.002)
    is_active = frame_rms_vals >= vad_threshold

    # Group active frames into raw bouts
    raw_bouts: list[tuple[float, float]] = []
    in_speech = False
    bout_start = 0.0

    for idx, active in enumerate(is_active):
        t = frame_times[idx]
        if active and not in_speech:
            in_speech = True
            bout_start = max(0.0, t - (cfg.hop_ms / 2000.0))
        elif not active and in_speech:
            in_speech = False
            bout_end = t + (cfg.hop_ms / 2000.0)
            if (bout_end - bout_start) * 1000.0 >= cfg.min_speech_bout_ms:
                raw_bouts.append((bout_start, bout_end))

    if in_speech:
        raw_bouts.append((bout_start, total_dur_s))

    # Merge very short gaps between speech bouts (e.g. stop consonant closures)
    merged_bouts: list[tuple[float, float]] = []
    for bout in raw_bouts:
        if not merged_bouts:
            merged_bouts.append(bout)
        else:
            prev_start, prev_end = merged_bouts[-1]
            gap_duration_ms = (bout[0] - prev_end) * 1000.0
            if gap_duration_ms < cfg.short_pause_merge_ms:
                merged_bouts[-1] = (prev_start, bout[1])
            else:
                merged_bouts.append(bout)

    # Derive pauses from intervals between speech bouts
    pauses: list[tuple[float, float]] = []
    current_time = 0.0

    for b_start, b_end in merged_bouts:
        if b_start > current_time:
            pause_dur_ms = (b_start - current_time) * 1000.0
            if pause_dur_ms >= cfg.min_pause_ms:
                pauses.append((current_time, b_start))
        current_time = max(current_time, b_end)

    if current_time < total_dur_s:
        tail_pause_ms = (total_dur_s - current_time) * 1000.0
        if tail_pause_ms >= cfg.min_pause_ms:
            pauses.append((current_time, total_dur_s))

    return merged_bouts, pauses, frame_times, frame_rms_vals


def extract_connected_speech_features(
    prep_result: TaskPreprocessingResult,
    task_id: str = "connected_speech_passage",
    stimulus_id: str = STANDARD_PASSAGE_ID,
    language_code: str = STANDARD_LANGUAGE_CODE,
    config: ConnectedSpeechConfig | None = None,
) -> ConnectedSpeechResult:
    """Extract speech timing, pause distributions, and prosodic variations."""
    cfg = config or ConnectedSpeechConfig()
    warnings: list[str] = []
    errors: list[str] = []

    samples = prep_result.samples
    sr = prep_result.sample_rate
    total_dur_s = prep_result.retained_duration_seconds

    # Initialize all features to null per schema contract
    features: dict[str, float | None] = {name: None for name in CONNECTED_SPEECH_FEATURE_NAMES}
    features["total_recording_duration_s"] = round(total_dur_s, 4)

    speech_bouts, pauses, _, frame_rms_vals = segment_speech_activity(samples, sr, config=cfg)

    # 1. Timing and Pause Metrics
    bout_durations = [end - start for start, end in speech_bouts]
    pause_durations = [end - start for start, end in pauses]

    active_speech_s = float(sum(bout_durations))
    silence_dur_s = max(0.0, float(total_dur_s - active_speech_s))

    features["estimated_active_speech_duration_s"] = round(active_speech_s, 4)
    features["estimated_silence_duration_s"] = round(silence_dur_s, 4)

    if total_dur_s > 0.0:
        features["speech_activity_fraction"] = round(float(active_speech_s / total_dur_s), 4)
        features["pause_fraction"] = round(float(silence_dur_s / total_dur_s), 4)

    features["speech_bout_count"] = float(len(speech_bouts))
    if speech_bouts:
        features["mean_speech_bout_duration_s"] = round(float(np.mean(bout_durations)), 4)
        features["median_speech_bout_duration_s"] = round(float(np.median(bout_durations)), 4)

    features["pause_count"] = float(len(pauses))
    if pauses:
        features["mean_pause_duration_s"] = round(float(np.mean(pause_durations)), 4)
        features["median_pause_duration_s"] = round(float(np.median(pause_durations)), 4)
        features["max_pause_duration_s"] = round(float(np.max(pause_durations)), 4)
        if len(pauses) >= 2:
            features["pause_duration_sd_s"] = round(float(np.std(pause_durations, ddof=1)), 4)
    else:
        warnings.append("No pauses exceeding the minimum pause threshold (> 200 ms) detected.")

    # 2. Prosodic Pitch (F0) Metrics
    if len(samples) > int(sr * 0.5):
        try:
            sound = parselmouth.Sound(samples, sampling_frequency=sr)
            pitch = sound.to_pitch_ac(
                time_step=cfg.hop_ms / 1000.0,
                pitch_floor=cfg.pitch_floor_hz,
                pitch_ceiling=cfg.pitch_ceiling_hz,
            )
            f0_vals = pitch.selected_array["frequency"]
            voiced_f0 = f0_vals[f0_vals > 0]

            if len(voiced_f0) >= cfg.min_voiced_frames:
                f0_med = float(np.median(voiced_f0))
                f0_sd = float(np.std(voiced_f0, ddof=1))
                q10 = float(np.percentile(voiced_f0, 10))
                q90 = float(np.percentile(voiced_f0, 90))

                features["f0_median_hz"] = round(f0_med, 2)
                features["f0_sd_hz"] = round(f0_sd, 2)
                features["f0_q10_hz"] = round(q10, 2)
                features["f0_q90_hz"] = round(q90, 2)

                if q10 > 0.0 and q90 >= q10:
                    semitones = float(12.0 * math.log2(q90 / q10))
                    features["f0_range_semitones"] = round(semitones, 2)
            else:
                warnings.append(
                    f"Fewer than {cfg.min_voiced_frames} voiced frames detected; "
                    "pitch metrics unavailable."
                )
        except Exception as exc:
            warnings.append(f"Pitch tracking could not be completed: {exc}")

    # 3. Intensity Dynamics
    if len(frame_rms_vals) > 0:
        # Convert RMS to dBFS
        safe_rms = np.maximum(frame_rms_vals, 1e-5)
        intensity_db = 20.0 * np.log10(safe_rms)

        features["intensity_median_dbfs"] = round(float(np.median(intensity_db)), 2)
        if len(intensity_db) >= 10:
            iqr = float(np.percentile(intensity_db, 75) - np.percentile(intensity_db, 25))
            features["intensity_iqr_db"] = round(iqr, 2)

    # Status determination
    if active_speech_s >= 1.0 and features["f0_median_hz"] is not None:
        task_status = "complete"
    elif active_speech_s >= 0.5:
        task_status = "complete"
    elif active_speech_s > 0.0:
        task_status = "not_estimable"
    else:
        task_status = "insufficient_signal"
        errors.append("Insufficient speech activity detected in connected speech recording.")

    return ConnectedSpeechResult(
        task_id=task_id,
        task_type="connected_speech",
        task_schema_version=CONNECTED_SPEECH_SCHEMA_VERSION,
        task_schema_fingerprint=connected_speech_schema_fingerprint(),
        task_status=task_status,
        stimulus_id=stimulus_id,
        language_code=language_code,
        features=features,
        pause_intervals_s=[(round(s, 4), round(e, 4)) for s, e in pauses],
        speech_bout_intervals_s=[(round(s, 4), round(e, 4)) for s, e in speech_bouts],
        quality={
            "total_duration_s": total_dur_s,
            "active_speech_s": active_speech_s,
            "silence_duration_s": silence_dur_s,
            "pause_count": len(pauses),
            "speech_bout_count": len(speech_bouts),
            "preprocessing_fingerprint": prep_result.preprocessing_fingerprint,
        },
        warnings=warnings,
        errors=errors,
        configuration_fingerprint=configuration_fingerprint(asdict(cfg)),
        preprocessing_status="completed",
    )
