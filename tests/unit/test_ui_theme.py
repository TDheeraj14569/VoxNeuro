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
    assert any("Audio quality checks passed — not a health result" in c for c in calls)
    assert any("does not indicate Parkinson's disease" in c for c in calls)

    calls.clear()
    invalid_qual = AudioQuality(
        valid=False,
        clipping_fraction=0.15,
        duration_seconds=1.2,
        errors=["Audio too noisy", "Excessive clipping detected"],
        warnings=[],
    )
    render_plain_quality_summary(invalid_qual, record)
    assert any("Audio quality checks did not pass" in c for c in calls)


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
    assert any("INDIVIDUAL CLASSIFICATION UNAVAILABLE" in c for c in calls)
    assert not any("vx-result-container" in c for c in calls)
    assert not any("background noise is detected" in c for c in calls)

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
        score_kind="calibrated_probability",
    )
    render_prediction_outcome_card(case_a)
    assert any("Externally validated research estimate" in c for c in calls)
    assert any("74.2%" in c for c in calls)

    # Uncalibrated values are rendered as raw scores, never likelihood percentages.
    for score in (0.85, 0.50, 0.20):
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
        rendered = "".join(calls)
        assert "Uncalibrated research output" in rendered
        assert f"{score:+.6f}" in rendered
        assert f"{score * 100:.1f}%" not in rendered

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


def test_exploratory_result_card_shows_raw_score_without_probability(monkeypatch):
    calls = []
    monkeypatch.setattr(st, "markdown", lambda content, **kwargs: calls.append(content))
    prediction = PredictionResult(
        prediction_id="pred_exploratory",
        status="EXPLORATORY_NOT_DOMAIN_VALIDATED",
        abstained=False,
        abstention_reasons=[],
        abstention_reason=None,
        model_id="uams_logistic_research",
        model_version="0.4.0-research",
        model_checksum="a" * 64,
        research_score=0.824,
        research_classification="PD-pattern candidate",
        calibration_status="UNCALIBRATED_DECISION_SCORE",
        ood_status="IN_DISTRIBUTION",
        acquisition_domain_id="laptop_microphone",
        capture_origin="user_upload",
        score_kind="uncalibrated_logit",
        decision_threshold=0.0,
        model_evaluation_metrics={"balanced_accuracy": 0.72},
        domain_validation_status="NOT_VALIDATED",
        acquisition_domain_source="user_declared",
    )

    render_prediction_outcome_card(prediction)
    rendered = "".join(calls)
    assert "EXPLORATORY RESULT · NOT DOMAIN VALIDATED" in rendered
    assert "PD-pattern candidate" in rendered
    assert "+0.824000" in rendered
    assert "not a probability" in rendered
    assert "0.824%" not in rendered
    assert "vx-result-container" not in rendered


def test_consumer_pages_render_edge_cases(monkeypatch):
    from voxneuro.ui.consumer_pages import (
        show_account_portal,
        show_consumer_home,
        show_user_history_page,
    )

    calls = []
    monkeypatch.setattr(st, "info", lambda msg: calls.append(("info", msg)))
    monkeypatch.setattr(st, "warning", lambda msg: calls.append(("warning", msg)))
    monkeypatch.setattr(st, "title", lambda msg: calls.append(("title", msg)))
    monkeypatch.setattr(st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        st,
        "columns",
        lambda spec, *args, **kwargs: [
            type(
                "Col",
                (),
                {"__enter__": lambda s: s, "__exit__": lambda s, *a: None},
            )()
            for _ in range(len(spec) if isinstance(spec, (list, tuple)) else spec)
        ],
    )
    monkeypatch.setattr(st, "button", lambda *args, **kwargs: False)

    # 1. History without user
    show_user_history_page(None, None)
    assert any("Please sign in" in c[1] for c in calls)

    # 2. Account without connection
    calls.clear()
    show_account_portal(None)
    assert any("Account storage database is not initialized" in c[1] for c in calls)

    # 3. Consumer home landing page
    calls.clear()
    show_consumer_home(on_start_assessment=lambda: None)
    assert any(c[0] == "title" and "VoxNeuro" in c[1] for c in calls)


def test_consumer_informational_pages_and_dashboard(monkeypatch):
    from pathlib import Path

    from voxneuro.study.auth import UserAccount
    from voxneuro.ui.admin_portals import (
        show_ml_admin_portal,
        show_researcher_portal,
        show_system_admin_portal,
    )
    from voxneuro.ui.consumer_pages import (
        show_about_page,
        show_help_faq,
        show_how_it_works,
        show_privacy_and_safety,
        show_user_dashboard,
    )

    calls = []
    monkeypatch.setattr(st, "title", lambda msg: calls.append(("title", msg)))
    monkeypatch.setattr(st, "write", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "info", lambda msg: calls.append(("info", msg)))
    monkeypatch.setattr(st, "warning", lambda msg: calls.append(("warning", msg)))
    monkeypatch.setattr(st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        st,
        "expander",
        lambda *args, **kwargs: type(
            "Exp", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: None}
        )(),
    )
    monkeypatch.setattr(
        st,
        "columns",
        lambda spec, *args, **kwargs: [
            type("Col", (), {"__enter__": lambda s: s, "__exit__": lambda s, *a: None})()
            for _ in range(len(spec) if isinstance(spec, (list, tuple)) else spec)
        ],
    )

    # 1. How it works
    show_how_it_works()
    assert any(c[0] == "title" and "How VoxNeuro Works" in c[1] for c in calls)

    # 2. Privacy & Safety
    calls.clear()
    show_privacy_and_safety()
    assert any(c[0] == "title" and "Privacy & Safety" in c[1] for c in calls)

    # 3. Help / FAQ
    calls.clear()
    show_help_faq()
    assert any(c[0] == "title" and "Help & Frequently Asked Questions" in c[1] for c in calls)

    # 4. About
    calls.clear()
    show_about_page()
    assert any(c[0] == "title" and "About VoxNeuro" in c[1] for c in calls)

    # 5. User dashboard
    dummy_user = UserAccount(
        user_id="usr_test_123",
        username="test_user",
        email="test@voxneuro.org",
        display_name="Test Subject",
        role="consumer",
        is_active=True,
        participant_id=None,
        study_id=None,
        prediction_retention_opt_in=True,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        last_login_at=None,
    )
    calls.clear()
    show_user_dashboard(None, dummy_user, on_start_assessment=lambda: None)
    assert any(c[0] == "title" and "Welcome back" in c[1] for c in calls)

    # 6. Admin portals gating when unauthenticated
    calls.clear()
    show_researcher_portal(None, None)
    show_ml_admin_portal(None, None)
    show_system_admin_portal(None, None, Path("dummy.db"))
    assert any("Access Restricted" in c[1] for c in calls)
