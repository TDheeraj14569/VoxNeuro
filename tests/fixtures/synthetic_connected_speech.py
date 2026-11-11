"""Deterministic synthetic connected speech generators for software unit tests."""

from __future__ import annotations

import numpy as np


def synthetic_connected_speech(
    sample_rate: int = 16000,
    bout_durations_s: tuple[float, ...] = (1.5, 2.0, 1.8),
    pause_durations_s: tuple[float, ...] = (0.4, 0.5),
    base_f0_hz: float = 140.0,
    amplitude: float = 0.35,
    noise_level: float = 0.001,
    rng_seed: int = 123,
) -> np.ndarray:
    """Generate deterministic multi-bout connected speech with known pauses and pitch.

    Interleaves voiced speech bouts with silent pauses of exact duration.
    """
    rng = np.random.default_rng(rng_seed)
    signal_parts: list[np.ndarray] = []

    # Leading quiet margin
    signal_parts.append(np.zeros(int(sample_rate * 0.15), dtype=np.float64))

    n_bouts = len(bout_durations_s)
    for i in range(n_bouts):
        b_dur = bout_durations_s[i]
        n_samples = int(sample_rate * b_dur)
        t = np.arange(n_samples) / sample_rate

        # Speech-like harmonic excitation with smooth pitch contour and vibrato
        f0 = base_f0_hz + 15.0 * np.sin(2 * np.pi * 1.2 * t) + (i * 8.0)
        phase = 2 * np.pi * np.cumsum(f0) / sample_rate

        # Multi-harmonic series
        bout_audio = np.zeros(n_samples, dtype=np.float64)
        for h in range(1, 6):
            bout_audio += (amplitude / h) * np.sin(h * phase)

        # Smooth envelope on speech bout
        env = np.ones(n_samples, dtype=np.float64)
        edge = min(int(sample_rate * 0.04), n_samples // 4)
        if edge > 0:
            env[:edge] = np.linspace(0.0, 1.0, edge)
            env[-edge:] = np.linspace(1.0, 0.0, edge)

        bout_audio = bout_audio * env
        signal_parts.append(bout_audio)

        # Insert pause between bouts if not last bout
        if i < len(pause_durations_s):
            p_dur = pause_durations_s[i]
            p_samples = int(sample_rate * p_dur)
            pause_noise = rng.normal(0, noise_level, p_samples).astype(np.float64)
            signal_parts.append(pause_noise)

    # Trailing quiet margin
    signal_parts.append(np.zeros(int(sample_rate * 0.15), dtype=np.float64))

    full_signal = np.concatenate(signal_parts)
    peak = np.max(np.abs(full_signal))
    if peak > 0:
        full_signal = full_signal / peak * amplitude

    return full_signal
