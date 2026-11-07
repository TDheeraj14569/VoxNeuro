"""Waveform plotting from an actual one-dimensional signal."""

import numpy as np
from matplotlib.figure import Figure


def waveform_figure(samples: np.ndarray, sample_rate: int, title: str = "Waveform"):
    arr = np.asarray(samples, dtype=np.float64)
    if arr.ndim == 2:
        if arr.shape[1] in (1, 2):
            x = arr.mean(axis=1)
        elif arr.shape[0] in (1, 2):
            x = arr.mean(axis=0)
        else:
            raise ValueError(
                f"Multichannel waveform input has unsupported shape {arr.shape}; "
                "expected 1 or 2 channels."
            )
    elif arr.ndim == 1:
        x = arr
    else:
        raise ValueError(
            f"Waveform visualization requires 1D or 2-channel audio array, got ndim={arr.ndim}."
        )
    t = np.arange(len(x)) / sample_rate
    fig = Figure(figsize=(10, 2.7))
    ax = fig.subplots()
    fig.patch.set_facecolor("#0C1D27")
    fig.patch.set_alpha(0.92)
    ax.set_facecolor("#08151D")
    ax.plot(t, x, linewidth=0.7, color="#55D9C1")
    ax.set_title(title, color="#55D9C1", fontsize=11, fontweight="600")
    ax.set_xlabel("Time (s)", color="#EDF6F7")
    ax.set_ylabel("Amplitude (FS)", color="#EDF6F7")
    ax.tick_params(colors="#A7B8B5")
    for spine in ax.spines.values():
        spine.set_color("#263E47")
    ax.grid(alpha=0.18, color="#55D9C1", linewidth=0.6)
    fig.tight_layout()
    return fig
