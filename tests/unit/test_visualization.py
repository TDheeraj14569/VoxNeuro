import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.visualization.metrics import fold_metric_figure
from voxneuro.visualization.spectrogram import spectrogram_figure
from voxneuro.visualization.waveform import waveform_figure


def test_waveform_and_spectrogram_figures_render_for_valid_signal():
    signal = sustained_vowel()
    waveform = waveform_figure(signal, 16000, "Synthetic waveform")
    spectrogram = spectrogram_figure(signal, 16000)
    try:
        assert len(waveform.axes) == 1
        assert len(spectrogram.axes) == 2
        assert waveform.axes[0].get_xlabel()
        assert spectrogram.axes[0].get_ylabel()
    finally:
        plt.close(waveform)
        plt.close(spectrogram)


def test_grouped_metric_plot_has_research_baseline_labels():
    import pandas as pd

    metrics = pd.DataFrame(
        {
            "model": ["logistic_regression", "random_forest"],
            "balanced_accuracy": [0.65, 0.72],
        }
    )
    figure = fold_metric_figure(metrics)
    try:
        assert len(figure.axes) == 1
        assert figure.axes[0].get_title() == "Participant-wise cross-validation: balanced_accuracy"
        assert figure.axes[0].get_xlabel() == "Research baseline"
    finally:
        plt.close(figure)


def test_waveform_and_spectrogram_handle_multichannel_downmix_safely():
    import numpy as np

    stereo = np.column_stack([sustained_vowel(), sustained_vowel()])
    waveform = waveform_figure(stereo, 16000)
    spectrogram = spectrogram_figure(stereo, 16000)
    try:
        assert len(waveform.axes) == 1
        assert len(spectrogram.axes) == 2
    finally:
        plt.close(waveform)
        plt.close(spectrogram)

    import pytest

    four_channel = np.ones((1600, 4))
    with pytest.raises(ValueError, match="Multichannel"):
        waveform_figure(four_channel, 16000)
    with pytest.raises(ValueError, match="Multichannel"):
        spectrogram_figure(four_channel, 16000)


def test_waveform_and_spectrogram_validate_arguments():
    import numpy as np
    import pytest

    valid_samples = sustained_vowel()
    for bad_sr in (0, -16000, 16000.5, True, False, "16000"):
        with pytest.raises(ValueError, match="sample_rate"):
            waveform_figure(valid_samples, bad_sr)
        with pytest.raises(ValueError, match="sample_rate"):
            spectrogram_figure(valid_samples, bad_sr)

    with pytest.raises(ValueError, match="finite"):
        waveform_figure(np.array([1.0, np.nan, 2.0]), 16000)
    with pytest.raises(ValueError, match="finite"):
        spectrogram_figure(np.array([1.0, np.inf, 2.0]), 16000)

    with pytest.raises(ValueError, match="numeric"):
        waveform_figure(np.array([1.0 + 1.0j, 2.0]), 16000)
    with pytest.raises(ValueError, match="numeric"):
        spectrogram_figure(np.array([1.0 + 1.0j, 2.0]), 16000)

    with pytest.raises(ValueError, match="n_fft"):
        spectrogram_figure(valid_samples, 16000, n_fft=0)
    with pytest.raises(ValueError, match="hop_length"):
        spectrogram_figure(valid_samples, 16000, hop_length=2048, n_fft=1024)
