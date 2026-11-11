"""Deterministic synthetic DDK audio generators for software unit tests."""

from __future__ import annotations

import numpy as np


def synthetic_ddk_train(
    sample_rate: int = 16000,
    duration: float = 4.0,
    target_rate_hz: float = 5.0,
    pulse_duration_s: float = 0.08,
    carrier_freq_hz: float = 250.0,
    amplitude: float = 0.40,
    jitter_sd_s: float = 0.0,
    acceleration_slope_s: float = 0.0,
    rng_seed: int = 42,
) -> np.ndarray:
    """Generate a deterministic train of syllable bursts with known repetition timing."""
    total_samples = int(sample_rate * duration)
    signal = np.zeros(total_samples, dtype=np.float64)

    rng = np.random.default_rng(rng_seed)
    base_interval_s = 1.0 / target_rate_hz

    # Generate event times
    event_times = []
    t_curr = 0.30  # initial silence

    idx = 0
    while t_curr + pulse_duration_s < duration - 0.20:
        event_times.append(t_curr)
        jitter = rng.normal(0, jitter_sd_s) if jitter_sd_s > 0 else 0.0
        drift = idx * acceleration_slope_s
        interval = max(0.09, base_interval_s + jitter + drift)
        t_curr += interval
        idx += 1

    pulse_samples = int(sample_rate * pulse_duration_s)
    t_pulse = np.arange(pulse_samples) / sample_rate

    # Create burst pulse: damped oscillation with smooth attack/decay
    env = np.hanning(pulse_samples)
    carrier = np.sin(2 * np.pi * carrier_freq_hz * t_pulse) + 0.5 * np.sin(
        2 * np.pi * (2 * carrier_freq_hz) * t_pulse
    )
    pulse = amplitude * env * carrier

    for t_ev in event_times:
        start_samp = int(t_ev * sample_rate)
        end_samp = start_samp + pulse_samples
        if end_samp <= total_samples:
            signal[start_samp:end_samp] += pulse

    # Normalize to prevent clipping unless explicitly requested
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * amplitude

    return signal
