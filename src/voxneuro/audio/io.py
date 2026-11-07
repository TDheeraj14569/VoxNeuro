"""Safe WAV decoding and recording metadata."""

from __future__ import annotations

import math
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
        object.__setattr__(self, "samples", arr)

    @property
    def duration_seconds(self) -> float:
        return float(len(self.samples) / self.sample_rate)


def decode_audio(
    payload: bytes | bytearray | BytesIO,
    *,
    max_duration_seconds: float = 300.0,
) -> AudioRecord:
    """Decode an audio byte stream while retaining the original channel layout.

    Parameters
    ----------
    payload : bytes | bytearray | BytesIO
        Raw audio byte stream to decode.
    max_duration_seconds : float, default=300.0
        Coarse file-level container reading ceiling (default 300 s) to guard against
        decompression memory bombs. Fine-grained vocal task duration (e.g. 30 s) is
        enforced downstream by AudioValidationConfig during validate_audio.
    """
    if (
        isinstance(max_duration_seconds, (bool, np.bool_))
        or not isinstance(max_duration_seconds, (int, float, np.number))
        or not math.isfinite(max_duration_seconds)
        or max_duration_seconds <= 0
    ):
        raise ValueError("max_duration_seconds must be a finite, positive, non-boolean number.")

    try:
        data = payload.getvalue() if isinstance(payload, BytesIO) else bytes(payload)
        info = sf.info(BytesIO(data))
    except (RuntimeError, ValueError, TypeError, sf.LibsndfileError) as exc:
        raise AudioReadError(
            "Could not read this audio file. Check that it is a supported WAV or WAVEX file."
        ) from exc
    # libsndfile distinguishes the WAVE extensible variant as WAVEX. It is
    # still a RIFF/WAVE container and is used by the public UAMS recordings.
    if str(info.format).upper() not in {"WAV", "WAVEX"}:
        raise AudioReadError("Unsupported audio container. Upload a WAV file.")
    if info.frames == 0 or info.samplerate <= 0:
        raise AudioReadError("The WAV file contains no usable audio samples.")
    if info.samplerate < MIN_SUPPORTED_SAMPLE_RATE or info.samplerate > MAX_SUPPORTED_SAMPLE_RATE:
        raise AudioReadError(
            f"Unsupported sample rate: {info.samplerate} Hz. Supported range is "
            f"{MIN_SUPPORTED_SAMPLE_RATE} Hz to {MAX_SUPPORTED_SAMPLE_RATE} Hz."
        )
    if info.channels not in (1, 2):
        raise AudioReadError(
            f"Unsupported channel count: {info.channels}. Only mono (1) and stereo (2) "
            "WAV files are supported."
        )
    if info.duration > max_duration_seconds:
        raise AudioReadError(
            f"Audio duration of {info.duration:.1f} s exceeds maximum allowed "
            f"{max_duration_seconds:.1f} s."
        )
    try:
        raw, sample_rate = sf.read(BytesIO(data), dtype="float64", always_2d=True)
    except (RuntimeError, ValueError, TypeError, sf.LibsndfileError) as exc:
        raise AudioReadError("Could not decode audio samples from file.") from exc
    if raw.size == 0 or sample_rate <= 0:
        raise AudioReadError("The WAV file contains no usable audio samples.")
    return AudioRecord(
        samples=np.asarray(raw),
        sample_rate=int(sample_rate),
        channels=int(raw.shape[1]),
        subtype=str(info.subtype),
        format=str(info.format),
    )
