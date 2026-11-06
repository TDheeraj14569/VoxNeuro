"""Waveform plotting from an actual one-dimensional signal."""

import matplotlib.pyplot as plt
import numpy as np


def waveform_figure(samples: np.ndarray, sample_rate: int, title: str = "Waveform"):
    x = np.asarray(samples).reshape(-1)
    t = np.arange(len(x)) / sample_rate
    fig, ax = plt.subplots(figsize=(10, 2.7))
    ax.plot(t, x, linewidth=0.55, color="#2878A5")
    ax.set(title=title, xlabel="Time (s)", ylabel="Amplitude (FS)")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    return fig
