"""Configurable recording checks that fail closed before feature extraction."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import parselmouth

from voxneuro.audio.io import AudioRecord


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

    def __post_init__(self) -> None:
        if self.min_duration_seconds <= 0:
            raise ValueError("min_duration_seconds must be positive.")
        if self.max_duration_seconds <= self.min_duration_seconds:
            raise ValueError("max_duration_seconds must be greater than min_duration_seconds.")
        if not (0.0 <= self.min_rms <= 1.0):
            raise ValueError("min_rms must be in range [0.0, 1.0].")
        if not (0.0 < self.max_peak <= 1.0):
            raise ValueError("max_peak must be in range (0.0, 1.0].")
        if not (0.0 <= self.clipping_fraction_limit <= 1.0):
            raise ValueError("clipping_fraction_limit must be in range [0.0, 1.0].")
        if not (0.0 <= self.min_voiced_fraction <= 1.0):
            raise ValueError("min_voiced_fraction must be in range [0.0, 1.0].")
        if self.frame_ms <= 0:
            raise ValueError("frame_ms must be a positive integer.")
        if self.pitch_floor_hz <= 0:
            raise ValueError("pitch_floor_hz must be positive.")
        if self.pitch_ceiling_hz <= self.pitch_floor_hz:
            raise ValueError("pitch_ceiling_hz must be greater than pitch_floor_hz.")
        if not (0.0 <= self.min_harmonic_overtone_fraction <= 1.0):
            raise ValueError("min_harmonic_overtone_fraction must be in range [0.0, 1.0].")


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
    x = np.asarray(record.samples, dtype=np.float64)
    errors: list[str] = []
    warnings: list[str] = []
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
    elif mono.size and record.sample_rate > 0:
        valid_f0 = frequencies[np.isfinite(frequencies) & (frequencies > 0)]
        if len(valid_f0) > 0:
            median_f0 = float(np.median(valid_f0))
            fft = np.abs(np.fft.rfft(mono))
            fft_freqs = np.fft.rfftfreq(len(mono), 1.0 / record.sample_rate)
            total_energy = float(np.sum(fft**2))
            if total_energy > 0:
                overtone_energy = float(np.sum(fft[fft_freqs > 1.5 * median_f0] ** 2))
                overtone_fraction = overtone_energy / total_energy
                if overtone_fraction < cfg.min_harmonic_overtone_fraction:
                    errors.append(
                        "Signal lacks harmonic overtones expected of a human voice "
                        "(isolated single-frequency tone or synthetic generator detected). "
                        "Please record a natural sustained vowel /a/."
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
