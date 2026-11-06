import numpy as np
import pytest

from voxneuro.modeling.calibration import calibration_summary
from voxneuro.reporting.model_card import model_card_template


def test_calibration_summary_requires_binary_oof_labels_and_probabilities():
    result = calibration_summary(np.array([0, 1]), np.array([0.2, 0.8]))
    assert result["n"] == 2
    assert result["brier_score"] == pytest.approx(0.04)

    for labels, scores in (
        ([0], [0.5, 0.6]),
        ([0, 2], [0.1, 0.9]),
        ([0, float("nan")], [0.1, 0.9]),
        ([0, 1], [0.1, float("inf")]),
        ([[0], [1]], [0.1, 0.9]),
        ([0, 1], [[0.1], [0.9]]),
        ([0, 1], [-0.1, 1.1]),
    ):
        with pytest.raises(ValueError):
            calibration_summary(np.asarray(labels), np.asarray(scores))


def test_model_card_template_keeps_research_only_boundary():
    text = model_card_template()
    assert "Research-only" in text
    assert "no claim of external validation" in text
    assert "does not expose model predictions" in text
