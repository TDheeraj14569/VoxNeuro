from io import BytesIO

import pytest
import soundfile as sf

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.audio.io import decode_audio
from voxneuro.exceptions import AudioReadError


def wav_bytes(samples, sample_rate=16000):
    out = BytesIO()
    sf.write(out, samples, sample_rate, format="WAV", subtype="PCM_16")
    return out.getvalue()


def test_decode_audio_reports_actual_metadata():
    record = decode_audio(wav_bytes(sustained_vowel(sample_rate=8000), 8000))
    assert record.sample_rate == 8000
    assert record.channels == 1
    assert record.duration_seconds == pytest.approx(3.0, abs=0.001)
    assert record.subtype == "PCM_16"


def test_decode_audio_accepts_bytesio_directly():
    stream = BytesIO(wav_bytes(sustained_vowel(), 16000))
    record = decode_audio(stream)
    assert record.sample_rate == 16000
    assert record.duration_seconds == pytest.approx(3.0, abs=0.001)


def test_corrupt_wav_is_rejected():
    with pytest.raises(AudioReadError):
        decode_audio(b"not a wave file")


def test_empty_wav_is_rejected():
    out = BytesIO()
    sf.write(out, [], 16000, format="WAV", subtype="PCM_16")
    with pytest.raises(AudioReadError, match="no usable audio samples"):
        decode_audio(out.getvalue())


def test_non_wav_container_is_rejected():
    out = BytesIO()
    sf.write(out, sustained_vowel(), 16000, format="FLAC")
    with pytest.raises(AudioReadError, match="WAV"):
        decode_audio(out.getvalue())


def test_wave_extensible_container_is_accepted():
    out = BytesIO()
    sf.write(out, sustained_vowel(sample_rate=8000), 8000, format="WAVEX", subtype="FLOAT")
    record = decode_audio(out.getvalue())
    assert record.format == "WAVEX"
    assert record.sample_rate == 8000


def test_unsupported_sample_rate_is_rejected():
    out_low = BytesIO()
    sf.write(out_low, sustained_vowel(sample_rate=4000), 4000, format="WAV", subtype="PCM_16")
    with pytest.raises(AudioReadError, match="Unsupported sample rate: 4000 Hz"):
        decode_audio(out_low.getvalue())

    out_high = BytesIO()
    sf.write(out_high, sustained_vowel(sample_rate=96000), 96000, format="WAV", subtype="PCM_16")
    with pytest.raises(AudioReadError, match="Unsupported sample rate: 96000 Hz"):
        decode_audio(out_high.getvalue())


@pytest.mark.parametrize(
    ("sr", "err_type", "match"),
    [
        (16000.5, TypeError, "sample_rate must be an integer"),
        (8000.0, TypeError, "sample_rate must be an integer"),
        (True, TypeError, "sample_rate must be an integer"),
        (4000, ValueError, "sample_rate must be an integer between 8000 and 48000 Hz"),
        (96000, ValueError, "sample_rate must be an integer between 8000 and 48000 Hz"),
    ],
)
def test_audio_record_rejects_invalid_sample_rate(sr, err_type, match):
    import numpy as np

    from voxneuro.audio.io import AudioRecord

    with pytest.raises(err_type, match=match):
        AudioRecord(
            samples=np.zeros((100, 1)),
            sample_rate=sr,
            channels=1,
            subtype="PCM_16",
            format="WAV",
        )
