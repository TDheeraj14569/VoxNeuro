"""Configurable recording checks that fail closed before feature extraction."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import parselmouth

from voxneuro.audio.io import (
    MAX_SUPPORTED_SAMPLE_RATE,
    MIN_SUPPORTED_SAMPLE_RATE,
    AudioRecord,
)


@dataclass(frozen=True)
class AudioValidationConfig:
    min_duration_seconds: float = 1.0
    max_duration_seconds: float = 30.0
    min_rms: float = 0.003
    max_peak: float = 0.999
    clipping_fraction_limit: float = 0.01
    min_voiced_fraction: float = 0.15
    frame_ms: int = 20
    mono_policy: str = "average_with_phase_check"
    pitch_floor_hz: float = 75.0
    pitch_ceiling_hz: float = 500.0
    min_harmonic_overtone_fraction: float = 0.005
    min_second_harmonic_fraction: float = 0.002
    min_waveform_kurtosis: float = 1.15

    def __post_init__(self) -> None:
        numeric_fields = (
            "min_duration_seconds",
            "max_duration_seconds",
            "min_rms",
            "max_peak",
            "clipping_fraction_limit",
            "min_voiced_fraction",
            "pitch_floor_hz",
            "pitch_ceiling_hz",
            "min_harmonic_overtone_fraction",
            "min_second_harmonic_fraction",
            "min_waveform_kurtosis",
        )
        for field_name in numeric_fields:
            val = getattr(self, field_name)
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TypeError(f"{field_name} must be numeric, not {type(val).__name__}.")
            if not math.isfinite(val):
                raise ValueError(f"{field_name} must be a finite number.")

        if type(self.frame_ms) is not int or isinstance(self.frame_ms, bool):
            raise TypeError(f"frame_ms must be an int, not {type(self.frame_ms).__name__}.")
        if not (5 <= self.frame_ms <= 100):
            raise ValueError("frame_ms must be an integer between 5 and 100 ms.")

        if not (0.0 < self.min_duration_seconds <= 3600.0):
            raise ValueError("min_duration_seconds must be positive and <= 3600.")
        if not (self.min_duration_seconds < self.max_duration_seconds <= 3600.0):
            raise ValueError(
                "max_duration_seconds must be greater than min_duration_seconds and <= 3600."
            )
        if not (0.0 <= self.min_rms <= 1.0):
            raise ValueError("min_rms must be in range [0.0, 1.0].")
        if not (0.0 < self.max_peak <= 1.0):
            raise ValueError("max_peak must be in range (0.0, 1.0].")
        if not (0.0 <= self.clipping_fraction_limit <= 1.0):
            raise ValueError("clipping_fraction_limit must be in range [0.0, 1.0].")
        if not (0.0 <= self.min_voiced_fraction <= 1.0):
            raise ValueError("min_voiced_fraction must be in range [0.0, 1.0].")
        if not (10.0 <= self.pitch_floor_hz < self.pitch_ceiling_hz <= 2000.0):
            raise ValueError(
                "pitch limits must satisfy 10.0 <= pitch_floor_hz < pitch_ceiling_hz <= 2000.0."
            )
        if not (0.0 <= self.min_harmonic_overtone_fraction <= 1.0):
            raise ValueError("min_harmonic_overtone_fraction must be in range [0.0, 1.0].")
        if not (0.0 <= self.min_second_harmonic_fraction <= 1.0):
            raise ValueError("min_second_harmonic_fraction must be in range [0.0, 1.0].")
        if not (0.0 <= self.min_waveform_kurtosis <= 10.0):
            raise ValueError("min_waveform_kurtosis must be in range [0.0, 10.0].")


@dataclass
class AudioQuality:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    peak_amplitude: float = 0.0
    rms_amplitude: float = 0.0
    clipping_fraction: float = 0.0
    voiced_fraction: float = 0.0
    active_fraction: float = 0.0


def validate_audio(
    record: AudioRecord, config: AudioValidationConfig | None = None
) -> AudioQuality:
    """Check shape, finiteness, duration, level, clipping, and voiced-frame ratio."""
    cfg = config or AudioValidationConfig()
    errors: list[str] = []
    warnings: list[str] = []
    if (
        isinstance(record.sample_rate, bool)
        or not isinstance(record.sample_rate, (int, np.integer))
        or not MIN_SUPPORTED_SAMPLE_RATE <= int(record.sample_rate) <= MAX_SUPPORTED_SAMPLE_RATE
    ):
        errors.append(
            f"Source sample rate must be an integer between {MIN_SUPPORTED_SAMPLE_RATE} "
            f"and {MAX_SUPPORTED_SAMPLE_RATE} Hz."
        )
        return AudioQuality(valid=False, errors=errors, warnings=warnings)
    try:
        raw = np.asarray(record.samples)
    except (TypeError, ValueError):
        return AudioQuality(
            valid=False,
            errors=["Audio samples must form a rectangular numeric array."],
        )
    if (
        isinstance(raw, bool)
        or raw.dtype == bool
        or not np.issubdtype(raw.dtype, np.number)
        or np.issubdtype(raw.dtype, np.complexfloating)
    ):
        return AudioQuality(
            valid=False,
            errors=["Audio samples must contain real numeric values."],
        )
    try:
        x = raw.astype(np.float64, copy=False)
    except (TypeError, ValueError):
        return AudioQuality(
            valid=False,
            errors=["Audio samples must form a rectangular numeric array."],
        )
    if cfg.mono_policy != "average_with_phase_check":
        errors.append(f"Unsupported mono conversion policy: {cfg.mono_policy!r}.")
    if x.ndim != 2 or x.shape[1] not in (1, 2):
        errors.append("Audio must have one or two channels.")
        return AudioQuality(valid=False, errors=errors, warnings=warnings)
    if record.channels != x.shape[1]:
        errors.append("Audio channel metadata does not match the sample-array shape.")
        return AudioQuality(valid=False, errors=errors, warnings=warnings)
    if x.size == 0:
        errors.append("Audio contains no samples.")
    if not np.isfinite(x).all():
        errors.append("Audio contains NaN or infinite samples.")
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    duration = record.duration_seconds if record.sample_rate > 0 else 0.0
    if duration < cfg.min_duration_seconds:
        errors.append(
            f"Recording is too short ({duration:.2f}s; minimum {cfg.min_duration_seconds:.1f}s)."
        )
    if duration > cfg.max_duration_seconds:
        errors.append(
            f"Recording is too long ({duration:.2f}s; maximum {cfg.max_duration_seconds:.1f}s)."
        )
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0
    clipping = float(np.mean(np.abs(x) >= cfg.max_peak)) if x.size else 0.0
    mono = x.mean(axis=1) if x.ndim == 2 and x.size else np.asarray([], dtype=np.float64)
    frame = max(1, int(record.sample_rate * cfg.frame_ms / 1000))
    n_frames = len(mono) // frame
    if n_frames:
        framed = mono[: n_frames * frame].reshape(n_frames, frame)
        levels = np.sqrt(np.mean(np.square(framed), axis=1))
        active = float(np.mean(levels >= max(cfg.min_rms * 0.25, float(levels.max()) * 0.03)))
    else:
        active = 0.0
    voiced = 0.0
    frequencies = np.empty(0, dtype=np.float64)
    if mono.size and record.sample_rate > 0:
        try:
            sound = parselmouth.Sound(mono, sampling_frequency=record.sample_rate)
            pitch = sound.to_pitch_ac(
                time_step=0.01,
                pitch_floor=cfg.pitch_floor_hz,
                pitch_ceiling=cfg.pitch_ceiling_hz,
            )
            frequencies = np.asarray(pitch.selected_array["frequency"], dtype=np.float64)
            voiced = float(np.mean(np.isfinite(frequencies) & (frequencies > 0)))
        except (parselmouth.PraatError, ValueError, RuntimeError):
            voiced = 0.0
            frequencies = np.empty(0, dtype=np.float64)
    if rms < cfg.min_rms:
        errors.append(
            "Signal level is very low or the recording is silent. Move closer and record again."
        )
    # The configured value is the maximum allowed clipped-sample fraction;
    # equality is accepted, and zero means that no clipped samples are allowed.
    if clipping > cfg.clipping_fraction_limit:
        errors.append(
            "Too many samples are clipped. Review the recording or exclude it under the "
            "documented quality-control policy."
        )
    if voiced < cfg.min_voiced_fraction:
        errors.append(
            "Too little voiced signal was detected. Use a steady sustained vowel and retry."
        )
    elif mono.size and record.sample_rate > 0 and frequencies.size > 0:
        valid_f0 = frequencies[np.isfinite(frequencies) & (frequencies > 0)]
        if len(valid_f0) > 0:
            median_f0 = float(np.median(valid_f0))
            mono_centered = mono - float(np.mean(mono))
            fft = np.abs(np.fft.rfft(mono_centered))
            fft_freqs = np.fft.rfftfreq(len(mono_centered), 1.0 / record.sample_rate)
            if fft.size:
                fft[0] = 0.0
            total_energy = float(np.sum(fft**2))
            if total_energy > 0:
                overtone_energy = float(np.sum(fft[fft_freqs > 1.5 * median_f0] ** 2))
                overtone_fraction = overtone_energy / total_energy
                if overtone_fraction < cfg.min_harmonic_overtone_fraction:
                    errors.append(
                        "Configured harmonic criteria not met: signal lacks harmonic overtones "
                        "expected of a phonated vowel. Please record a steady sustained vowel /a/."
                    )
                else:
                    h2_mask = (fft_freqs >= 1.8 * median_f0) & (fft_freqs <= 2.2 * median_f0)
                    h2_fraction = float(np.sum(fft[h2_mask] ** 2) / total_energy)
                    var_val = float(np.var(mono_centered))
                    kurtosis = (
                        float(np.mean(mono_centered**4) / (max(1e-12, var_val) ** 2))
                        if var_val > 1e-12
                        else 1.0
                    )
                    if (
                        overtone_fraction > 0.05 and h2_fraction < cfg.min_second_harmonic_fraction
                    ) or (kurtosis < cfg.min_waveform_kurtosis and len(mono) > 500):
                        errors.append(
                            "Configured harmonic criteria not met: acoustic resonance "
                            "distribution outside expected vocal range. Please record a "
                            "steady sustained vowel /a/."
                        )
    if record.channels == 2:
        centered = x - x.mean(axis=0, keepdims=True)
        corr = np.corrcoef(centered.T)[0, 1] if len(centered) > 1 else 1.0
        if np.isfinite(corr) and corr < -0.5:
            errors.append(
                "Stereo channels are strongly out of phase; safe mono conversion is not possible."
            )
        elif np.isfinite(corr) and corr < 0.0:
            warnings.append(
                "Stereo channels are partly out of phase; inspect the mono mix before use."
            )
    return AudioQuality(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        duration_seconds=duration,
        peak_amplitude=peak,
        rms_amplitude=rms,
        clipping_fraction=clipping,
        voiced_fraction=voiced,
        active_fraction=active,
    )
