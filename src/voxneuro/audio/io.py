"""Safe WAV decoding and recording metadata."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import soundfile as sf

from voxneuro.exceptions import AudioReadError


@dataclass(frozen=True)
class AudioRecord:
    samples: np.ndarray
    sample_rate: int
    channels: int
    subtype: str
    format: str

    @property
    def duration_seconds(self) -> float:
        return float(len(self.samples) / self.sample_rate)


MIN_SUPPORTED_SAMPLE_RATE: int = 8000
MAX_SUPPORTED_SAMPLE_RATE: int = 48000


def decode_audio(payload: bytes | bytearray | BytesIO) -> AudioRecord:
    """Decode an audio byte stream while retaining the original channel layout."""
    try:
        data = payload.getvalue() if isinstance(payload, BytesIO) else bytes(payload)
        raw, sample_rate = sf.read(BytesIO(data), dtype="float64", always_2d=True)
        info = sf.info(BytesIO(data))
    except (RuntimeError, ValueError, TypeError, sf.LibsndfileError) as exc:
        raise AudioReadError(
            "Could not read this audio file. Check that it is a supported WAV or WAVEX file."
        ) from exc
    if raw.size == 0 or sample_rate <= 0:
        raise AudioReadError("The WAV file contains no usable audio samples.")
    if sample_rate < MIN_SUPPORTED_SAMPLE_RATE or sample_rate > MAX_SUPPORTED_SAMPLE_RATE:
        raise AudioReadError(
            f"Unsupported sample rate: {sample_rate} Hz. Supported range is "
            f"{MIN_SUPPORTED_SAMPLE_RATE} Hz to {MAX_SUPPORTED_SAMPLE_RATE} Hz."
        )
    # libsndfile distinguishes the WAVE extensible variant as WAVEX. It is
    # still a RIFF/WAVE container and is used by the public UAMS recordings.
    if str(info.format).upper() not in {"WAV", "WAVEX"}:
        raise AudioReadError("Unsupported audio container. Upload a WAV file.")
    return AudioRecord(
        samples=np.asarray(raw),
        sample_rate=int(sample_rate),
        channels=int(raw.shape[1]),
        subtype=str(info.subtype),
        format=str(info.format),
    )
