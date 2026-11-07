"""Safe WAV decoding and recording metadata."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
import soundfile as sf

from voxneuro.exceptions import AudioReadError

MIN_SUPPORTED_SAMPLE_RATE: int = 8000
MAX_SUPPORTED_SAMPLE_RATE: int = 48000


@dataclass(frozen=True)
class AudioRecord:
    samples: np.ndarray
    sample_rate: int
    channels: int
    subtype: str
    format: str

    def __post_init__(self) -> None:
        if isinstance(self.sample_rate, bool) or not isinstance(
            self.sample_rate, (int, np.integer)
        ):
            raise TypeError(
                f"sample_rate must be an integer, not {type(self.sample_rate).__name__}."
            )
        if not (MIN_SUPPORTED_SAMPLE_RATE <= int(self.sample_rate) <= MAX_SUPPORTED_SAMPLE_RATE):
            raise ValueError(
                f"sample_rate must be an integer between {MIN_SUPPORTED_SAMPLE_RATE} "
                f"and {MAX_SUPPORTED_SAMPLE_RATE} Hz, got {self.sample_rate}."
            )
        if isinstance(self.channels, bool) or not isinstance(self.channels, (int, np.integer)):
            raise TypeError(f"channels must be an integer, not {type(self.channels).__name__}.")
        if self.channels not in (1, 2):
            raise ValueError(f"channels must be 1 (mono) or 2 (stereo), got {self.channels}.")
        if not isinstance(self.subtype, str) or not self.subtype.strip():
            raise TypeError("subtype must be a non-empty string.")
        if not isinstance(self.format, str) or not self.format.strip():
            raise TypeError("format must be a non-empty string.")
        try:
            arr = np.asarray(self.samples)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"samples must be a valid array: {exc}") from exc
        if np.iscomplexobj(arr) or np.issubdtype(arr.dtype, np.complexfloating):
            raise TypeError("samples cannot be complex-valued.")
        if not np.issubdtype(arr.dtype, np.number):
            raise TypeError(f"samples must have a real numeric dtype, got {arr.dtype}.")

    @property
    def duration_seconds(self) -> float:
        return float(len(self.samples) / self.sample_rate)


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
    channels = int(raw.shape[1])
    if channels not in (1, 2):
        raise AudioReadError(
            f"Unsupported channel count: {channels}. Only mono (1) and stereo (2) "
            "WAV files are supported."
        )
    return AudioRecord(
        samples=np.asarray(raw),
        sample_rate=int(sample_rate),
        channels=channels,
        subtype=str(info.subtype),
        format=str(info.format),
    )
