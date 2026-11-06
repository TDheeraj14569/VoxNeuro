from io import BytesIO

import soundfile as sf

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.audio.io import decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.validation import validate_audio
from voxneuro.features.extractor import extract_features


def test_valid_wav_runs_end_to_end_to_features():
    out = BytesIO()
    sf.write(out, sustained_vowel(), 16000, format="WAV")
    record = decode_audio(out.getvalue())
    quality = validate_audio(record)
    assert quality.valid
    processed = preprocess_audio(record)
    features = extract_features(
        processed.samples, processed.sample_rate, original_sample_rate=record.sample_rate
    )
    assert features["f0_mean_hz"] > 0
