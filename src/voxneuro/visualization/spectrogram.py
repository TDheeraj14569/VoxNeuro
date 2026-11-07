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
    arr = np.asarray(samples, dtype=np.float32)
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
    fig.patch.set_facecolor("#0C1D27")
    fig.patch.set_alpha(0.92)
    ax.set_facecolor("#08151D")
    image = librosa.display.specshow(
        db,
        sr=sample_rate,
        hop_length=hop_length,
        x_axis="time",
        y_axis="linear",
        ax=ax,
        cmap="magma",
    )
    ax.set_title("Magnitude spectrogram", color="#55D9C1", fontsize=11, fontweight="600")
    ax.set_xlabel("Time (s)", color="#EDF6F7")
    ax.set_ylabel("Frequency (Hz)", color="#EDF6F7")
    ax.tick_params(colors="#A7B8B5")
    for spine in ax.spines.values():
        spine.set_color("#263E47")
    cbar = fig.colorbar(image, ax=ax, label="Magnitude (dB relative)")
    cbar.ax.yaxis.label.set_color("#EDF6F7")
    cbar.ax.tick_params(colors="#A7B8B5")
    fig.tight_layout()
    return fig
