import numpy as np
import pytest

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.visualization.acoustic_3d import (
    MAX_SPECTROGRAM_FREQUENCY_BINS,
    MAX_SPECTROGRAM_TIME_BINS,
    MAX_WAVEFORM_POINTS,
    decorative_hero_payload,
    spectrogram_payload,
    viewer_html,
    waveform_payload,
)


def test_waveform_payload_is_mono_finite_and_render_bounded():
    samples = sustained_vowel(duration=4.0)

    payload = waveform_payload(samples, 16000)

    assert payload["mode"] == "waveform"
    assert len(payload["points"]) <= MAX_WAVEFORM_POINTS
    assert payload["duration_seconds"] == pytest.approx(4.0)
    assert payload["points"][0][0] == 0
    assert all(np.isfinite(point).all() for point in payload["points"])


def test_waveform_downsampling_preserves_short_transients():
    samples = np.zeros(5000, dtype=np.float64)
    samples[1234] = 1.0
    samples[3456] = -1.0

    payload = waveform_payload(samples, 1000)

    assert len(payload["points"]) <= MAX_WAVEFORM_POINTS
    amplitudes = [point[1] for point in payload["points"]]
    assert max(amplitudes) == 1.0
    assert min(amplitudes) == -1.0


@pytest.mark.parametrize(
    "samples",
    [
        np.column_stack((sustained_vowel(duration=1.0), sustained_vowel(duration=1.0))),
        np.array([0.0, np.nan, 1.0]),
        np.array([], dtype=np.float64),
    ],
)
def test_waveform_payload_rejects_invalid_samples(samples):
    with pytest.raises(ValueError):
        waveform_payload(samples, 16000)


def test_spectrogram_payload_is_bounded_and_uses_fixed_db_scale():
    payload = spectrogram_payload(sustained_vowel(duration=4.0), 16000)

    assert payload["mode"] == "spectrogram"
    assert payload["magnitude_scale"] == "20 log10(|STFT| / 1.0), dB re 1.0"
    assert payload["display_db_min"] == -90.0
    assert payload["display_db_max"] == 0.0
    assert len(payload["times"]) <= MAX_SPECTROGRAM_TIME_BINS
    assert len(payload["frequencies_hz"]) <= MAX_SPECTROGRAM_FREQUENCY_BINS
    assert len(payload["magnitude_db"]) == len(payload["frequencies_hz"])
    assert all(len(row) == len(payload["times"]) for row in payload["magnitude_db"])
    assert np.isfinite(np.asarray(payload["magnitude_db"])).all()


def test_spectrogram_payload_rejects_nyquist_and_stereo_input():
    mono = sustained_vowel(duration=1.0)
    with pytest.raises(ValueError, match="below the sample-rate Nyquist"):
        spectrogram_payload(mono, 16000, maximum_frequency_hz=8000)
    with pytest.raises(ValueError, match="mono 1D audio"):
        spectrogram_payload(np.column_stack((mono, mono)), 16000)


def test_local_viewer_embeds_the_built_bundle_and_has_a_fallback():
    html = viewer_html(waveform_payload(sustained_vowel(duration=1.0), 16000))

    assert "VoxNeuro3D.mount" in html
    assert "webgl2" in html
    assert "2D view is shown instead" in html
    assert "data-reset-view" in html
    assert '<script src="https://' not in html
    assert "cdnjs.cloudflare.com" not in html


def test_home_visualization_identifies_its_decorative_status():
    assert decorative_hero_payload() == {"mode": "hero"}
