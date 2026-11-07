"""Linear-frequency spectrogram plot from an actual waveform."""

import librosa
import librosa.display
import numpy as np
from matplotlib.figure import Figure


def spectrogram_figure(
    samples: np.ndarray,
    sample_rate: int,
    *,
    n_fft: int = 1024,
    hop_length: int = 160,
):
    if (
        isinstance(sample_rate, (bool, np.bool_))
        or not isinstance(sample_rate, (int, np.integer))
        or sample_rate <= 0
    ):
        raise ValueError("sample_rate must be a positive integer.")
    if (
        isinstance(n_fft, (bool, np.bool_))
        or not isinstance(n_fft, (int, np.integer))
        or n_fft <= 0
    ):
        raise ValueError("n_fft must be a positive integer.")
    if (
        isinstance(hop_length, (bool, np.bool_))
        or not isinstance(hop_length, (int, np.integer))
        or hop_length <= 0
        or hop_length > n_fft
    ):
        raise ValueError("hop_length must be a positive integer less than or equal to n_fft.")
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
    arr = raw.astype(np.float32, copy=False)
    if arr.ndim == 2:
        if arr.shape[1] in (1, 2):
            x = arr.mean(axis=1)
        elif arr.shape[0] in (1, 2):
            x = arr.mean(axis=0)
        else:
            raise ValueError(
                f"Multichannel spectrogram input has unsupported shape {arr.shape}; "
                "expected 1 or 2 channels."
            )
    elif arr.ndim == 1:
        x = arr
    else:
        raise ValueError(
            f"Spectrogram visualization requires 1D or 2-channel audio array, got ndim={arr.ndim}."
        )
    spectrum = librosa.stft(x, n_fft=n_fft, hop_length=hop_length)
    db = librosa.amplitude_to_db(np.abs(spectrum), ref=np.max)
    fig = Figure(figsize=(10, 3.2))
    ax = fig.subplots()
    fig.patch.set_facecolor("#FBFAF6")
    ax.set_facecolor("#FFFFFF")
    image = librosa.display.specshow(
        db,
        sr=sample_rate,
        hop_length=hop_length,
        x_axis="time",
        y_axis="linear",
        ax=ax,
        cmap="cividis",
    )
    ax.set_title("Magnitude spectrogram", color="#20232B", fontsize=11, fontweight="650")
    ax.set_xlabel("Time (s)", color="#676970", fontsize=9.5)
    ax.set_ylabel("Frequency (Hz)", color="#676970", fontsize=9.5)
    ax.tick_params(colors="#676970", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#D8D3C8")
    cbar = fig.colorbar(image, ax=ax, label="Magnitude (dB relative)")
    cbar.ax.yaxis.label.set_color("#676970")
    cbar.ax.tick_params(colors="#676970", labelsize=9)
    cbar.outline.set_edgecolor("#D8D3C8")
    fig.tight_layout()
    return fig
