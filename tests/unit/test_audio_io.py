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


def test_audio_record_rejects_complex_samples():
    import numpy as np

    from voxneuro.audio.io import AudioRecord

    mono = np.zeros(100, dtype=np.complex128) + 0.1j
    with pytest.raises(TypeError, match="samples cannot be complex-valued"):
        AudioRecord(mono.reshape(-1, 1), 16000, 1, "FLOAT", "WAV")


def test_audio_record_rejects_non_numeric_samples():
    import numpy as np

    from voxneuro.audio.io import AudioRecord

    with pytest.raises(TypeError, match="samples must have a real numeric dtype"):
        AudioRecord(np.array([["a"], ["b"]], dtype=object), 16000, 1, "FLOAT", "WAV")


def test_three_channel_wav_is_rejected_with_audio_read_error():
    from io import BytesIO

    import numpy as np
    import soundfile as sf

    from tests.fixtures.synthetic_audio import sustained_vowel
    from voxneuro.audio.io import decode_audio
    from voxneuro.exceptions import AudioReadError

    mono = sustained_vowel()
    tri = np.column_stack((mono, mono, mono))
    out = BytesIO()
    sf.write(out, tri, 16000, format="WAV", subtype="PCM_16")
    with pytest.raises(AudioReadError, match="Unsupported channel count: 3"):
        decode_audio(out.getvalue())


def test_audio_record_converts_list_samples_to_numpy_array():
    import numpy as np

    from voxneuro.audio.io import AudioRecord

    record = AudioRecord(
        samples=[[0.1], [0.2], [-0.1]],
        sample_rate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )
    assert isinstance(record.samples, np.ndarray)
    assert record.samples.shape == (3, 1)


def test_decode_audio_rejects_audio_exceeding_duration_limit(monkeypatch):
    import soundfile as sf

    from voxneuro.audio.io import decode_audio
    from voxneuro.exceptions import AudioReadError

    dummy_wav = wav_bytes(sustained_vowel(duration=0.1), 16000)

    class FakeInfo:
        format = "WAV"
        subtype = "PCM_16"
        samplerate = 16000
        channels = 1
        frames = 16000 * 305
        duration = 305.0

    monkeypatch.setattr(sf, "info", lambda _: FakeInfo())
    with pytest.raises(AudioReadError, match="Audio duration of 305.0 s exceeds maximum"):
        decode_audio(dummy_wav)


@pytest.mark.parametrize(
    "bad_max_dur",
    [float("nan"), float("inf"), float("-inf"), -1.0, 0.0, True, False, "300"],
)
def test_decode_audio_rejects_invalid_max_duration_seconds(bad_max_dur):
    dummy_wav = wav_bytes(sustained_vowel(duration=0.1), 16000)
    with pytest.raises(ValueError, match="max_duration_seconds"):
        decode_audio(dummy_wav, max_duration_seconds=bad_max_dur)
