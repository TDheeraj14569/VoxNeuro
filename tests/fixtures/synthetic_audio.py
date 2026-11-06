"""Deterministic synthetic sustained vowel used only for software tests."""

import numpy as np


def sustained_vowel(
    sample_rate: int = 16000, duration: float = 3.0, amplitude: float = 0.15
) -> np.ndarray:
    t = np.arange(int(sample_rate * duration), dtype=np.float64) / sample_rate
    f0 = 175 + 2.0 * np.sin(2 * np.pi * 4.5 * t)
    phase = 2 * np.pi * np.cumsum(f0) / sample_rate
    signal = sum((amplitude / harmonic) * np.sin(harmonic * phase) for harmonic in range(1, 9))
    edge = min(int(0.08 * sample_rate), len(signal) // 4)
    envelope = np.ones_like(signal)
    if edge:
        envelope[:edge] = np.linspace(0, 1, edge)
        envelope[-edge:] = np.linspace(1, 0, edge)
    return signal * envelope
