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
    image = librosa.display.specshow(
        db, sr=sample_rate, hop_length=160, x_axis="time", y_axis="linear", ax=ax, cmap="magma"
    )
    ax.set(title="Magnitude spectrogram", ylabel="Frequency (Hz)")
    fig.colorbar(image, ax=ax, label="Magnitude (dB relative)")
    fig.tight_layout()
    return fig
