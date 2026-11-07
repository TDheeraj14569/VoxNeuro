"""Waveform plotting from an actual one-dimensional signal."""

import numpy as np
from matplotlib.figure import Figure


def waveform_figure(samples: np.ndarray, sample_rate: int, title: str = "Waveform"):
    if (
        isinstance(sample_rate, (bool, np.bool_))
        or not isinstance(sample_rate, (int, np.integer))
        or sample_rate <= 0
    ):
        raise ValueError("sample_rate must be a positive integer.")
    try:
        raw = np.asarray(samples)
    except (TypeError, ValueError) as exc:
        raise ValueError("samples must be a numeric array.") from exc
    if (
        isinstance(raw, (bool, np.bool_))
        or raw.dtype == np.bool_
        or not np.issubdtype(raw.dtype, np.number)
        or np.iscomplexobj(raw)
        or np.issubdtype(raw.dtype, np.complexfloating)
    ):
        raise ValueError("samples must contain real numeric values.")
    if not np.isfinite(raw).all():
        raise ValueError("samples must contain finite numeric values without NaN or Inf.")
    arr = raw.astype(np.float64, copy=False)
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
    fig.patch.set_facecolor("#FBFAF6")
    ax.set_facecolor("#FFFFFF")
    ax.plot(t, x, linewidth=0.8, color="#526A91")
    ax.set_title(title, color="#20232B", fontsize=11, fontweight="650")
    ax.set_xlabel("Time (s)", color="#676970", fontsize=9.5)
    ax.set_ylabel("Amplitude (FS)", color="#676970", fontsize=9.5)
    ax.tick_params(colors="#676970", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#D8D3C8")
    ax.grid(alpha=0.55, color="#D8D3C8", linewidth=0.6, linestyle=":")
    fig.tight_layout()
    return fig
