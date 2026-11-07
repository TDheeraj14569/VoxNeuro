"""Librosa MFCC and spectral summaries within the versioned common frequency band."""

from __future__ import annotations

import librosa
import numpy as np
from scipy.signal import butter, sosfiltfilt


def extract_spectral_features(
    samples: np.ndarray,
    sample_rate: int,
    mfcc_count: int = 13,
    mel_bands: int = 40,
    fft_window_samples: int = 1024,
    hop_samples: int = 160,
    mel_min_hz: float = 50.0,
    common_max_hz: float = 3800.0,
    original_sample_rate: int | None = None,
    rolloff_fraction: float = 0.85,
) -> dict[str, float]:
    """Calculate temporal summaries after enforcing a shared source-compatible band."""
    try:
        raw = np.asarray(samples)
    except (TypeError, ValueError) as exc:
        raise ValueError("Spectral extraction requires a rectangular numeric array.") from exc
    if (
        isinstance(raw, (bool, np.bool_))
        or raw.dtype == np.bool_
        or not np.issubdtype(raw.dtype, np.number)
        or np.iscomplexobj(raw)
        or np.issubdtype(raw.dtype, np.complexfloating)
    ):
        raise ValueError("Spectral extraction requires real numeric audio samples.")
    x = raw.astype(np.float32, copy=False)
    if x.ndim != 1:
        raise ValueError("Spectral extraction requires mono 1D audio.")
    if x.size < max(fft_window_samples // 2, 64):
        raise ValueError("Audio is too short for stable spectral summaries.")
    if sample_rate <= 0:
        raise ValueError("Sample rate must be positive.")
    if original_sample_rate is not None and original_sample_rate <= 0:
        raise ValueError("Original sample rate must be positive when supplied.")
    nyquist = float(sample_rate) / 2
    highest = min(
        float(common_max_hz),
        float((original_sample_rate or sample_rate) / 2),
        nyquist,
    )
    if highest <= mel_min_hz:
        raise ValueError("Source sample rate is too low for the configured common frequency band.")
    if highest >= nyquist:
        raise ValueError(
            f"Effective cutoff ({highest:g} Hz) must be strictly below sample-rate Nyquist "
            f"({nyquist:g} Hz); lower common_max_hz or increase sample_rate."
        )
    sos = butter(8, highest, btype="lowpass", fs=sample_rate, output="sos")
    band_limited = sosfiltfilt(sos, x).astype(np.float32, copy=False)
    mfcc = librosa.feature.mfcc(
        y=band_limited,
        sr=sample_rate,
        n_mfcc=mfcc_count,
        n_fft=fft_window_samples,
        hop_length=hop_samples,
        n_mels=mel_bands,
        fmin=mel_min_hz,
        fmax=highest,
    )
    result: dict[str, float] = {}
    for index, row in enumerate(mfcc):
        result[f"mfcc_{index:02d}_mean"] = float(np.mean(row))
        result[f"mfcc_{index:02d}_sd"] = float(np.std(row, ddof=1)) if row.size > 1 else np.nan
    spectrum = np.abs(
        librosa.stft(
            band_limited,
            n_fft=fft_window_samples,
            hop_length=hop_samples,
            center=True,
        )
    )
    frequencies = librosa.fft_frequencies(sr=sample_rate, n_fft=fft_window_samples)
    spectrum[frequencies > highest, :] = 0.0
    centroid = librosa.feature.spectral_centroid(S=spectrum, sr=sample_rate)
    rolloff = librosa.feature.spectral_rolloff(
        S=spectrum, sr=sample_rate, roll_percent=rolloff_fraction
    )[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=spectrum, sr=sample_rate, centroid=centroid)[0]
    zcr = librosa.feature.zero_crossing_rate(
        y=band_limited, frame_length=fft_window_samples, hop_length=hop_samples
    )[0]
    result.update(
        spectral_centroid_mean_hz=float(np.mean(centroid)),
        spectral_rolloff_mean_hz=float(np.mean(rolloff)),
        spectral_bandwidth_mean_hz=float(np.mean(bandwidth)),
        zero_crossing_rate_mean=float(np.mean(zcr)),
    )
    return result
