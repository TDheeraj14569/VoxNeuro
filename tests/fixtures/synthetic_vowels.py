"""Deterministic synthetic vowel generators for formant and VSA software testing."""

from __future__ import annotations

import numpy as np
import scipy.signal as signal


def _apply_formant_filter(
    sig: np.ndarray, f_res: float, bandwidth: float, sample_rate: int
) -> np.ndarray:
    """Apply second-order digital resonator filter (all-pole formant resonance)."""
    r = np.exp(-np.pi * bandwidth / sample_rate)
    theta = 2.0 * np.pi * f_res / sample_rate
    b = [1.0 - 2.0 * r * np.cos(theta) + r**2]
    a = [1.0, -2.0 * r * np.cos(theta), r**2]
    return signal.lfilter(b, a, sig)


def synthetic_formant_vowel(
    vowel_label: str = "a",
    sample_rate: int = 16000,
    duration: float = 2.0,
    pitch_hz: float = 125.0,
    amplitude: float = 0.35,
    custom_f1_hz: float | None = None,
    custom_f2_hz: float | None = None,
) -> np.ndarray:
    """Generate a deterministic sustained vowel with formant resonances for /a/, /i/, or /u/."""
    v = vowel_label.strip().lower()

    # Canonical adult vowel formant targets (Hz)
    default_formants = {
        "a": (730.0, 1090.0, 2440.0),
        "i": (280.0, 2250.0, 3000.0),
        "u": (320.0, 850.0, 2400.0),
    }

    f1_tgt, f2_tgt, f3_tgt = default_formants.get(v, (500.0, 1500.0, 2500.0))
    if custom_f1_hz is not None:
        f1_tgt = float(custom_f1_hz)
    if custom_f2_hz is not None:
        f2_tgt = float(custom_f2_hz)

    n_samples = int(sample_rate * duration)
    period = max(int(sample_rate / pitch_hz), 1)

    # Glottal impulse train
    excitation = np.zeros(n_samples, dtype=np.float64)
    excitation[::period] = 1.0

    # Glottal wave shaping via 1-pole low-pass filter
    excitation = signal.lfilter([1.0], [1.0, -0.96], excitation)

    # Formant filtering cascade
    s = _apply_formant_filter(excitation, f1_tgt, 80.0, sample_rate)
    s = _apply_formant_filter(s, f2_tgt, 100.0, sample_rate)
    s = _apply_formant_filter(s, f3_tgt, 120.0, sample_rate)

    # Lip radiation filter (first-order differentiator)
    s = np.diff(s, prepend=s[0])

    # Smooth window onset and offset
    env = np.ones(n_samples, dtype=np.float64)
    edge = min(int(sample_rate * 0.05), n_samples // 4)
    if edge > 0:
        env[:edge] = np.linspace(0.0, 1.0, edge)
        env[-edge:] = np.linspace(1.0, 0.0, edge)

    s = s * env
    peak = float(np.max(np.abs(s)))
    if peak > 0:
        s = s / peak * amplitude

    return s
