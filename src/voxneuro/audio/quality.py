"""Signal-level quality summaries for a single recording."""

import numpy as np


def frame_rms(
    samples: np.ndarray, sample_rate: int, frame_ms: int = 20
) -> tuple[np.ndarray, np.ndarray]:
    """Return frame times and RMS levels in linear amplitude units."""
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive.")
    if frame_ms <= 0:
        raise ValueError("Frame duration must be positive.")
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError("Frame RMS requires mono one-dimensional audio.")
    if not np.isfinite(x).all():
        raise ValueError("Frame RMS requires finite audio samples.")
    width = max(1, int(sample_rate * frame_ms / 1000))
    count = len(x) // width
    if count == 0:
        return np.asarray([], dtype=np.float64), np.asarray([], dtype=np.float64)
    frames = x[: count * width].reshape(count, width)
    levels = np.sqrt(np.mean(np.square(frames), axis=1))
    times = (np.arange(count, dtype=np.float64) + 0.5) * width / sample_rate
    return times, levels
