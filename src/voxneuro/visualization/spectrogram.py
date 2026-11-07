"""Linear-frequency spectrogram plot from an actual waveform."""

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np


def spectrogram_figure(samples: np.ndarray, sample_rate: int):
    x = np.asarray(samples, dtype=np.float32).reshape(-1)
    spectrum = librosa.stft(x, n_fft=1024, hop_length=160)
    db = librosa.amplitude_to_db(np.abs(spectrum), ref=np.max)
    fig, ax = plt.subplots(figsize=(10, 3.2))
    fig.patch.set_facecolor("#0C1D27")
    fig.patch.set_alpha(0.92)
    ax.set_facecolor("#08151D")
    image = librosa.display.specshow(
        db, sr=sample_rate, hop_length=160, x_axis="time", y_axis="linear", ax=ax, cmap="magma"
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
