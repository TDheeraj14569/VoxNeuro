"""Unit tests for VoxNeuro consumer theme and card rendering functions."""

from __future__ import annotations

import numpy as np
import streamlit as st

from voxneuro.audio.io import AudioRecord
from voxneuro.audio.validation import AudioQuality
from voxneuro.modeling.prediction_service import PredictionResult
from voxneuro.ui.theme import (
    render_animated_voice_hero,
    render_brand_bar,
    render_medical_disclaimer,
    render_plain_quality_summary,
    render_prediction_outcome_card,
    render_stepper,
)


def test_theme_and_disclaimer_render(monkeypatch):
    calls = []
    monkeypatch.setattr(st, "markdown", lambda content, **kwargs: calls.append(content))
    render_medical_disclaimer()
    assert any("Important Medical Notice" in c for c in calls)

    render_animated_voice_hero()
    assert any("waveGrad" in c for c in calls)

    render_brand_bar(user_display="Dr. Smith", role="admin")
    assert any("Dr. Smith" in c for c in calls)

    render_stepper(["Step 1", "Step 2", "Step 3"], active_index=1)
    assert any("Step 2" in c for c in calls)


def test_render_plain_quality_summary_valid_and_invalid(monkeypatch):
    calls = []
    monkeypatch.setattr(st, "markdown", lambda content, **kwargs: calls.append(content))

    record = AudioRecord(
        samples=np.zeros(16000, dtype=np.float32),
        sample_rate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )
    valid_qual = AudioQuality(
        valid=True,
        clipping_fraction=0.0,
        duration_seconds=3.5,
        errors=[],
        warnings=[],
    )
    render_plain_quality_summary(valid_qual, record)
    assert any("Recording Quality: Clear" in c for c in calls)

    calls.clear()
    invalid_qual = AudioQuality(
        valid=False,
        clipping_fraction=0.15,
        duration_seconds=1.2,
        errors=["Audio too noisy", "Excessive clipping detected"],
        warnings=[],
    )
    render_plain_quality_summary(invalid_qual, record)
    assert any("We could not hear your voice clearly" in c for c in calls)


def test_render_prediction_outcome_card_all_cases(monkeypatch):
    calls = []
    monkeypatch.setattr(st, "markdown", lambda content, **kwargs: calls.append(content))

    # Case C: Abstained
    case_c = PredictionResult(
        prediction_id="pred_c",
        status="ABSTAINED",
        abstained=True,
        abstention_reasons=["Microphone domain not validated"],
        abstention_reason="Microphone domain not validated",
        model_id="extra_trees_v1",
        model_version="1.0.0",
        model_checksum="sha256:abc",
        research_score=None,
        research_classification=None,
        calibration_status="UNCALIBRATED",
    )
    render_prediction_outcome_card(case_c)
    assert any("We could not provide a reliable result" in c for c in calls)

    # Case A: Externally Validated & Calibrated
    calls.clear()
    case_a = PredictionResult(
        prediction_id="pred_a",
        status="ESTIMATED",
        abstained=False,
        abstention_reasons=[],
        abstention_reason=None,
        model_id="extra_trees_v1",
        model_version="1.0.0",
        model_checksum="sha256:abc",
        research_score=0.742,
        research_classification="PD_LIKE",
        calibration_status="EXTERNALLY_VALIDATED_CALIBRATED",
    )
    render_prediction_outcome_card(case_a)
    assert any("Calibrated Voice Assessment" in c for c in calls)
    assert any("74.2%" in c for c in calls)

    # Case B: Uncalibrated research score (high, medium, low)
    for score, expected_word in [(0.85, "stronger"), (0.50, "moderate"), (0.20, "weaker")]:
        calls.clear()
        case_b = PredictionResult(
            prediction_id="pred_b",
            status="ESTIMATED",
            abstained=False,
            abstention_reasons=[],
            abstention_reason=None,
            model_id="extra_trees_v1",
            model_version="1.0.0",
            model_checksum="sha256:abc",
            research_score=score,
            research_classification="PD_LIKE",
            calibration_status="UNCALIBRATED",
        )
        render_prediction_outcome_card(case_b)
        assert any("Acoustic Similarity Index" in c for c in calls)
        assert any(expected_word in c for c in calls)

    # Case D: Inconclusive / unestimable
    calls.clear()
    case_d = PredictionResult(
        prediction_id="pred_d",
        status="UNKNOWN",
        abstained=False,
        abstention_reasons=[],
        abstention_reason=None,
        model_id="extra_trees_v1",
        model_version="1.0.0",
        model_checksum="sha256:abc",
        research_score=None,
        research_classification=None,
        calibration_status="UNCALIBRATED",
    )
    render_prediction_outcome_card(case_d)
    assert any("vx-card-case-d" in c for c in calls)
