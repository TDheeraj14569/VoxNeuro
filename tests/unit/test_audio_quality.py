import numpy as np
import pytest

from voxneuro.audio.quality import frame_rms


def test_frame_rms_returns_seconds_and_nonnegative_levels():
    sample_rate = 1000
    x = np.concatenate([np.zeros(100), np.ones(300) * 0.2])
    times, levels = frame_rms(x, sample_rate, frame_ms=100)
    assert len(times) == len(levels) == 4
    assert times[0] == 0.05
    assert levels[0] == 0.0
    assert levels[-1] == pytest.approx(0.2)


@pytest.mark.parametrize(("sample_rate", "frame_ms"), [(0, 20), (16000, 0), (16000, -1)])
def test_frame_rms_rejects_invalid_configuration(sample_rate, frame_ms):
    with pytest.raises(ValueError):
        frame_rms(np.ones(320), sample_rate, frame_ms)


def test_frame_rms_rejects_stereo_instead_of_flattening_channels():
    with pytest.raises(ValueError, match="mono one-dimensional"):
        frame_rms(np.ones((320, 2)), 16000)


def test_frame_rms_rejects_non_finite_samples():
    with pytest.raises(ValueError, match="finite"):
        frame_rms(np.asarray([0.0, np.nan, 1.0]), 16000)
