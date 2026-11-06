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
