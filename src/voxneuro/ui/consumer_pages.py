"""Approachable, accessible public and participant digital-health pages for VoxNeuro."""

from __future__ import annotations

import html
import json
import math
import sqlite3
from collections.abc import Callable
from typing import Any

import pandas as pd
import streamlit as st

from voxneuro.modeling.prediction_service import (
    PredictionResult,
    run_prediction_service,
)
from voxneuro.study.auth import (
    AuthorizationError,
    UserAccount,
    authenticate_user,
    complete_password_reset,
    issue_password_reset_token,
    register_user,
    revoke_session,
    update_user_profile_preferences,
)
from voxneuro.study.consent import get_active_consent_for_participant, record_consent
from voxneuro.study.participant import get_participant, register_participant
from voxneuro.study.registry import get_study, list_studies
from voxneuro.ui.theme import (
    render_animated_voice_hero,
    render_medical_disclaimer,
    render_plain_quality_summary,
    render_prediction_outcome_card,
)

WIZARD_STEPS = [
    "Introduction & Consent",
    "Device & Mic Check",
    "Voice Recording",
    "Quality Check",
    "Processing & Results",
]


def show_consumer_home(
    on_start_assessment: Callable[[], None],
    on_how_it_works: Callable[[], None] | None = None,
) -> None:
    """Landing and Overview experience for ordinary users per Section 5.1."""
    st.title("VoxNeuro")
    st.markdown(
        '<div class="vx-hero-card">'
        '<div class="vx-hero-eyebrow">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.5">'
        '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>'
        "Guided Voice Assessment Platform</div>"
        "<h1>Your voice can tell a story. Start listening to it.</h1>"
        '<p class="vx-hero-text">'
        "VoxNeuro helps assess voice patterns associated with Parkinson's disease through "
        "a guided voice assessment. Complete a calm, private 3–5 second voice check to evaluate "
        "acoustic steadiness, clarity, and subtle vocal properties."
        "</p>"
        '<div style="display:flex; flex-wrap:wrap; gap:0.5rem; margin-bottom:1.25rem;">'
        '<span class="vx-pill-badge vx-pill-teal">'
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.5">'
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
        "Private In-Memory Analysis</span>"
        '<span class="vx-pill-badge">'
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2">'
        '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
        "Under 1 Minute</span>"
        '<span class="vx-pill-badge">'
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2">'
        '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
        '<polyline points="22 4 12 14.01 9 11.01"/></svg>'
        "No Technical Jargon</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    c_btn1, c_btn2, _ = st.columns([1.3, 1.1, 2.5])
    with c_btn1:
        st.button(
            "Start Voice Assessment",
            type="primary",
            on_click=on_start_assessment,
            key="m6_hero_start_cta",
            help="Begin your guided, private 3–5 second voice assessment.",
        )
    with c_btn2:
        if on_how_it_works is not None:
            st.button(
                "How It Works",
                on_click=on_how_it_works,
                key="m6_hero_how_cta",
                help="Learn how VoxNeuro measures voice acoustics.",
            )

    render_animated_voice_hero()
    render_medical_disclaimer()

    st.markdown(
        '<h3 style="margin:1.5rem 0 1rem 0; font-weight:700;">How It Works</h3>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            '<div class="vx-card">'
            '<div class="vx-step-num">1</div>'
            "<h4>Record your voice</h4>"
            "<p>Take a comfortable breath and hold a relaxed, steady &ldquo;ah&rdquo; sound for "
            "3 to 5 seconds using your phone, laptop, or tablet microphone.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            '<div class="vx-card">'
            '<div class="vx-step-num">2</div>'
            "<h4>Let VoxNeuro analyse your recording</h4>"
            "<p>Our pipeline screens sound clarity, verifies background noise levels, and "
            "extracts 39 standard acoustic stability measurements in memory.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            '<div class="vx-card">'
            '<div class="vx-step-num">3</div>'
            "<h4>Understand your results</h4>"
            "<p>View clear, plain-language feedback on your vocal stability, review recommended "
            "next steps, and download a summary report for your doctor.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="vx-card" style="margin-top:1.5rem; background:#FFFFFF; '
        'border-left:4px solid var(--vx-teal);">'
        '<h4 style="color:var(--vx-teal-dark);">Why Voice Assessment?</h4>'
        '<p style="margin-bottom:0.65rem;">'
        "Changes in voice and speech may be associated with Parkinson's disease. Early motor "
        "changes in the muscles governing vocal fold tension, breath support, and articulation "
        "can cause subtle variations in vocal frequency (pitch), loudness stability, and voice "
        "quality before other signs are noticed."
        "</p>"
        '<p style="margin:0; font-size:0.90rem; color:var(--vx-muted);">'
        "<strong>Important note:</strong> Voice changes can also arise from common temporary "
        "causes such as colds, vocal strain, fatigue, or dry air. Voice assessment alone "
        "cannot establish or rule out a medical diagnosis, but it provides useful objective "
        "data to discuss with your healthcare provider."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<h3 style="margin:2rem 0 0.85rem 0; font-weight:700;">Trust &amp; Privacy</h3>',
        unsafe_allow_html=True,
    )
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(
            '<div class="vx-card">'
            "<h4>In-Memory Only</h4>"
            "<p>Your voice recording is processed temporarily in memory to extract acoustic "
            "properties. Audio is discarded immediately and never saved to disk without your "
            "explicit consent.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            '<div class="vx-card">'
            "<h4>Voluntary &amp; Controlled</h4>"
            "<p>Participation is completely voluntary. You decide whether to opt in to saving "
            "summary results in your account, and you can withdraw or delete your data anytime.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with p3:
        st.markdown(
            '<div class="vx-card">'
            "<h4>No Commercial Sharing</h4>"
            "<p>VoxNeuro is an academic research platform. We never sell personal data, track "
            "users across third-party sites, or send audio to commercial advertising networks.</p>"
            "</div>",
            unsafe_allow_html=True,
        )


def show_how_it_works() -> None:
    """Friendly visual and step-by-step explanation for first-time visitors per Section 5.1."""
    st.title("How VoxNeuro Works")
    st.write(
        "VoxNeuro is engineered so anyone can comfortably complete a voice assessment "
        "without needing technical knowledge of audio engineering, signal processing, or "
        "machine learning."
    )
    render_animated_voice_hero()
    render_medical_disclaimer()

    steps = [
        (
            "Step 1 · Informed Consent & Room Preparation",
            "Find a quiet room with minimal background noise. Sit upright and comfortable. "
            "Before recording, you review what the assessment measures and provide consent. "
            "Your audio remains transient in memory by default.",
        ),
        (
            "Step 2 · One Relaxed Breath (Sustained Vowel)",
            "Take an easy breath and sustain a clear, natural 'ah' (/a/) sound at your normal "
            "speaking loudness for about 3 to 5 seconds. Hold the microphone about 15–20 cm "
            "(6–8 inches) from your mouth.",
        ),
        (
            "Step 3 · Automatic Sound Clarity Check",
            "VoxNeuro instantly screens your recording for adequate volume, room silence, "
            "clipping distortion, and sufficient duration. If background noise or microphone "
            "distance interferes, the app gives actionable feedback so you can re-record easily.",
        ),
        (
            "Step 4 · Acoustic Measurement & Analysis",
            "Our algorithms measure 39 physical acoustic properties of your vocal soundwave, "
            "including pitch stability (jitter), loudness micro-fluctuations (shimmer), and "
            "harmonic-to-noise ratio (clarity).",
        ),
        (
            "Step 5 · Calibrated Evaluation or Honest Abstention",
            "If an approved model calibrated for your recording device is available, you see "
            "an understandable assessment. If external validation for your microphone type is "
            "still pending, VoxNeuro honestly abstains rather than returning an unreliable guess.",
        ),
        (
            "Step 6 · Understand Your Result & Next Steps",
            "Review plain-language explanations of your voice properties, learn what temporary "
            "factors influence voice acoustics, and download a summary report to share with your "
            "physician if desired.",
        ),
    ]
    for title, body in steps:
        st.markdown(
            f'<div class="vx-card" style="margin-bottom:0.85rem;">'
            f'<h4 style="color:var(--vx-teal);">{html.escape(title)}</h4>'
            f"<p>{html.escape(body)}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )


def show_privacy_and_safety() -> None:
    """Clear, jargon-free privacy, retention, and safety explanation per Section 11."""
    st.title("Privacy & Safety")
    render_medical_disclaimer()

    st.write(
        "Voice recordings contain biometric characteristics that can identify individuals. "
        "VoxNeuro was built from the ground up with a privacy-by-design architecture to keep "
        "your data secure."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="vx-card">'
            '<h4 style="color:var(--vx-teal-dark);">Audio Is Never Stored by Default</h4>'
            "<p>Your voice recording is decoded and evaluated entirely in transient memory. "
            "Once acoustic feature extraction finishes, the raw audio data is purged. "
            "No audio files are saved to disk unless you are enrolled in an explicit IRB-approved "
            "research study.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="vx-card">'
            '<h4 style="color:var(--vx-teal-dark);">Strict Non-Diagnostic Guardrails</h4>'
            "<p>VoxNeuro refuses to output disease probability estimates on uncalibrated "
            "microphones or noisy recordings. This fail-closed safety gate prevents misleading "
            "impressions and ensures the system is never mistaken for a diagnostic tool.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    c3, c4 = st.columns(2)
    with c3:
        st.markdown(
            '<div class="vx-card">'
            '<h4 style="color:var(--vx-teal-dark);">Explicit, Granular Consent</h4>'
            "<p>Consent is collected voluntarily before recording. Account creation does "
            "not automatically opt you into data retention; you have separate control over "
            "whether mathematical summary metrics are saved in your account history.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            '<div class="vx-card">'
            '<h4 style="color:var(--vx-teal-dark);">Complete Deletion &amp; Withdrawal</h4>'
            "<p>You maintain full ownership of your records. You can view, download, or "
            "permanently delete your assessment history at any time from your Account settings, "
            "leaving no residual traces.</p>"
            "</div>",
            unsafe_allow_html=True,
        )


def show_help_faq() -> None:
    """Clear FAQ for recording problems, microphone permissions, and interpreting results."""
    st.title("Help & Frequently Asked Questions")
    faqs = [
        (
            "What does VoxNeuro do?",
            "VoxNeuro is a voice assessment research tool designed to analyze acoustic "
            "properties of sustained vowel phonations (/a/). It measures pitch steadiness, "
            "amplitude stability, and vocal harmonics associated with motor speech control.",
        ),
        (
            "Can VoxNeuro diagnose Parkinson's disease?",
            "No. VoxNeuro is an assessment and research-support tool, NOT a diagnostic medical "
            "device. A diagnosis of Parkinson's disease requires a comprehensive clinical "
            "neurological examination, motor symptom evaluation, and medical history assessment "
            "by a qualified physician.",
        ),
        (
            "Why did my assessment say 'We could not provide a reliable result'?",
            "VoxNeuro has strict scientific safety gates. It will abstain from predicting "
            "whenever: (1) the recording was made on an uncalibrated consumer microphone, "
            "(2) background noise or room echo was detected, (3) audio quality was insufficient, "
            "or (4) prospective clinical validation for the device is still ongoing. "
            "Abstaining ensures we never provide misleading or fabricated predictions.",
        ),
        (
            "How should I position my microphone for best results?",
            "Sit upright in a quiet room away from fans or open windows. Hold the microphone "
            "about 15 to 20 cm (6 to 8 inches) from your mouth at roughly a 45-degree angle "
            "to avoid direct breath puffing.",
        ),
        (
            "What should I do if my browser blocks microphone access?",
            "Click the lock or camera/microphone icon in your browser's address bar and select "
            "'Allow' for microphone access, then refresh the page. Alternatively, you can record a "
            "WAV audio file on your device and use the 'Upload WAV' tab.",
        ),
        (
            "Can I share my results with my healthcare provider?",
            "Yes! You can download a clean summary report (HTML or JSON) from the Results "
            "page to bring to your doctor. Clinicians often appreciate having objective "
            "voice recordings and acoustic stability trends.",
        ),
    ]
    for q, a in faqs:
        with st.expander(q, expanded=False):
            st.write(a)


def show_about_page() -> None:
    """About VoxNeuro page describing mission, scientific foundation, and academic context."""
    st.title("About VoxNeuro")
    render_animated_voice_hero()
    st.markdown(
        '<div class="vx-card" style="margin-bottom:1.25rem;">'
        '<h4 style="color:var(--vx-teal-dark);">Our Mission</h4>'
        '<p style="font-size:1rem; line-height:1.65;">'
        "VoxNeuro is an academic research platform developed to advance the science of acoustic "
        "biomarkers in neurological health. By developing open, transparent, and reproducible "
        "tools to measure subtle vocal stability parameters, we aim to support healthcare "
        "professionals and clinical researchers in understanding voice characteristics associated "
        "with Parkinson's disease."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="vx-card">'
            "<h4>Scientific Foundation</h4>"
            "<p>Our feature extraction engine implements the verified Core39 acoustic schema, "
            "incorporating established Praat-based pitch and perturbation metrics (Parselmouth) "
            "and Mel-frequency cepstral coefficients (Librosa) from sustained phonations.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="vx-card">'
            "<h4>Commitment to Honesty</h4>"
            "<p>We transparently report demographic confounding, prevent data leakage across "
            "participant cohorts, and enforce fail-closed safety boundaries so that unvalidated "
            "laboratory models are never misapplied to real-world clinical decision-making.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.caption(
        "VoxNeuro Research Platform is an independent academic project and is not affiliated with, "
        "sponsored by, or related to VoxNeuro Inc. (makers of EEG cognitive assessments)."
    )
    render_medical_disclaimer()


def show_user_dashboard(
    conn: sqlite3.Connection | None,
    user: UserAccount,
    on_start_assessment: Callable[[], None],
) -> None:
    """Clean, approachable dashboard for authenticated users per Section 5.3."""
    st.title(f"Welcome back, {user.display_name}")
    st.caption(f"Account: {user.username} · Role: {user.role.capitalize()}")

    st.markdown(
        '<div class="vx-hero-card" style="padding:1.5rem 1.75rem; margin-bottom:1.25rem;">'
        '<div class="vx-hero-eyebrow">Ready for your voice check?</div>'
        '<h3 style="margin:0 0 0.5rem 0;">Complete today\'s voice assessment</h3>'
        '<p style="color:var(--vx-ink-secondary); margin:0 0 1rem 0; font-size:0.95rem;">'
        "A quick 3–5 second sustained vowel recording helps monitor acoustic stability over time."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.button(
        "Start Voice Assessment",
        type="primary",
        on_click=on_start_assessment,
        key="dash_start_cta",
    )

    col1, col2, col3 = st.columns(3)
    n_records = 0
    last_date = "None yet"
    last_status = "No assessments"
    if conn is not None:
        row = conn.execute(
            """
            SELECT COUNT(*) as count, MAX(created_at) as last_created
            FROM prediction_records
            WHERE user_id = ? OR (participant_id IS NOT NULL AND participant_id = ?);
            """,
            (user.user_id, user.participant_id or "__none__"),
        ).fetchone()
        if row and row["count"] > 0:
            n_records = int(row["count"])
            last_date = str(row["last_created"])[:10] if row["last_created"] else "Recently"
            last_status = "Completed"

    with col1:
        st.markdown(
            f'<div class="vx-card"><h4>Saved Assessments</h4>'
            f'<div style="font-size:2rem; font-weight:800; color:var(--vx-teal);">{n_records}</div>'
            f'<p style="font-size:0.85rem; color:var(--vx-muted);">In account history</p></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="vx-card"><h4>Last Voice Check</h4>'
            f'<div style="font-size:1.4rem; font-weight:700; color:var(--vx-ink); '
            f'margin-top:0.35rem;">{last_date}</div>'
            f'<p style="font-size:0.85rem; color:var(--vx-muted);">{last_status}</p></div>',
            unsafe_allow_html=True,
        )
    with col3:
        ret_status = "Enabled" if user.prediction_retention_opt_in else "Off (Transient)"
        color = "#16A34A" if user.prediction_retention_opt_in else "var(--vx-muted)"
        st.markdown(
            f'<div class="vx-card"><h4>Summary Retention</h4>'
            f'<div style="font-size:1.4rem; font-weight:700; color:{color}; '
            f'margin-top:0.35rem;">{ret_status}</div>'
            f'<p style="font-size:0.85rem; color:var(--vx-muted);">Audio is never saved</p></div>',
            unsafe_allow_html=True,
        )

    render_medical_disclaimer()


def show_guided_consent_step(conn: sqlite3.Connection | None, user: UserAccount | None) -> bool:
    """Render Step 1 Consent check/capture backed by real SQLite consents when signed in."""
    if user is None or conn is None:
        st.info(
            "Guest Mode (Temporary Only): Your voice recording is processed in temporary memory "
            "and never saved to disk. Sign in on the Account page if you wish to track your "
            "history over time."
        )
        ack = st.checkbox(
            "I voluntary consent to this voice assessment and understand that VoxNeuro is a "
            "research platform and NOT a medical diagnosis tool.",
            value=bool(st.session_state.get("voxneuro_guest_consent_ack", False)),
            key="voxneuro_guest_consent_checkbox",
        )
        st.session_state["voxneuro_guest_consent_ack"] = ack
        return ack

    if not user.participant_id or not user.study_id:
        ret_label = "Opted In" if user.prediction_retention_opt_in else "Off (Transient)"
        st.info(
            f"Signed in as {user.display_name}. Your voice recording will be evaluated in "
            f"temporary memory. Summary retention: {ret_label}."
        )
        ack = st.checkbox(
            "I voluntary consent to this voice assessment and understand that VoxNeuro is a "
            "research platform and NOT a medical diagnosis tool.",
            value=bool(st.session_state.get("voxneuro_user_consent_ack", False)),
            key="voxneuro_user_consent_checkbox",
        )
        st.session_state["voxneuro_user_consent_ack"] = ack
        return ack

    active = get_active_consent_for_participant(conn, user.participant_id, study_id=user.study_id)
    if active:
        ret_txt = "Opted In" if active.permission_to_retain_derived_features else "Off (transient)"
        st.success(
            f"Active study consent verified (Form {active.consent_form_version}, recorded "
            f"{active.consent_date[:10]}). Summary retention: {ret_txt}."
        )
        return True

    st.warning("Study research consent is required before saving any session measurements.")
    agree = st.checkbox(
        "I voluntarily consent to sustained vowel voice recording for Parkinson's biomarker "
        "research.",
        key="m6_study_consent_agree",
    )
    retain_feats = st.checkbox(
        "Optional: allow saving derived acoustic features & research summaries (never raw audio).",
        value=False,
        key="m6_study_consent_retain",
    )
    if st.button("Confirm & Record Consent", key="m6_submit_consent_btn", disabled=not agree):
        try:
            try:
                get_participant(conn, user.participant_id)
            except KeyError:
                studies = list_studies(conn)
                if studies:
                    register_participant(
                        conn,
                        participant_id=user.participant_id,
                        study_id=user.study_id,
                        allowed_research_scopes=["voice_analysis", "feature_extraction"],
                    )
            if user.study_id and get_study(conn, user.study_id):
                record_consent(
                    conn,
                    participant_id=user.participant_id,
                    study_id=user.study_id,
                    consent_form_version="m6-participant-v1",
                    scope_of_permission=["voice_analysis", "feature_extraction"],
                    permitted_recording_tasks=["sustained_vowel"],
                    permitted_research_uses=["biomarker_research", "feature_extraction"],
                    permission_to_retain_derived_features=bool(retain_feats),
                    permission_to_retain_audio=False,
                    source_document_reference="ui://guided-consent-m6",
                )
                st.success("Your research consent has been recorded securely.")
                st.rerun()
        except Exception as exc:
            st.error(f"Could not record consent: {exc}")
    return False


def show_plain_results_page(
    prediction: PredictionResult | None,
    features: dict[str, Any] | None,
    quality: Any | None,
    record: Any | None,
    html_report: str | None = None,
    report_dict: dict[str, Any] | None = None,
) -> None:
    """Plain-language summary page showing quality, calibrated prediction, and safe export."""
    st.title("Your Voice Check Results")
    render_medical_disclaimer()

    if prediction is None or quality is None:
        st.info("Complete a Voice Assessment first to view your personal results summary here.")
        return

    if record is not None:
        render_plain_quality_summary(quality, record)

    render_prediction_outcome_card(prediction)

    if features:
        st.markdown(
            '<h3 style="margin:1.75rem 0 0.5rem 0; font-weight:700;">'
            "Plain-Language Voice Highlights</h3>",
            unsafe_allow_html=True,
        )
        st.caption(
            "These physical acoustic properties describe the steadiness and clarity of your "
            "soundwave. They describe physical vocal properties and cannot diagnose or rule "
            "out any health condition."
        )

        def _safe_fmt(val: Any, unit: str = "", factor: float = 1.0, fmt: str = ".1f") -> str:
            if val is None:
                return "N/A"
            try:
                fval = float(val)
                if not math.isfinite(fval):
                    return "N/A"
                return f"{fval * factor:{fmt}} {unit}".strip()
            except (TypeError, ValueError):
                return "N/A"

        f0_disp = _safe_fmt(features.get("f0_mean_hz"), unit="Hz", fmt=".1f")
        jit_disp = _safe_fmt(features.get("jitter_local"), unit="%", factor=100.0, fmt=".2f")
        shim_disp = _safe_fmt(features.get("shimmer_local"), unit="%", factor=100.0, fmt=".2f")
        hnr_val = features.get("hnr_mean_db")
        hnr_raw = hnr_val if hnr_val is not None else features.get("hnr_db")
        hnr_disp = _safe_fmt(hnr_raw, unit="dB", fmt=".1f")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                '<div class="vx-card">'
                '<div style="font-size:0.80rem; font-weight:700; color:var(--vx-teal); '
                'text-transform:uppercase;">Pitch (F0)</div>'
                f'<div style="font-size:1.8rem; font-weight:700; color:var(--vx-ink); '
                f'margin:0.25rem 0;">{f0_disp}</div>'
                '<p style="font-size:0.80rem; color:var(--vx-muted);">'
                "Vocal fold vibration rate</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                '<div class="vx-card">'
                '<div style="font-size:0.80rem; font-weight:700; color:var(--vx-teal); '
                'text-transform:uppercase;">Pitch Steadiness</div>'
                f'<div style="font-size:1.8rem; font-weight:700; color:var(--vx-ink); '
                f'margin:0.25rem 0;">{jit_disp}</div>'
                '<p style="font-size:0.80rem; color:var(--vx-muted);">'
                "Frequency variation</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                '<div class="vx-card">'
                '<div style="font-size:0.80rem; font-weight:700; color:var(--vx-teal); '
                'text-transform:uppercase;">Volume Steadiness</div>'
                f'<div style="font-size:1.8rem; font-weight:700; color:var(--vx-ink); '
                f'margin:0.25rem 0;">{shim_disp}</div>'
                '<p style="font-size:0.80rem; color:var(--vx-muted);">'
                "Loudness variation</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                '<div class="vx-card">'
                '<div style="font-size:0.80rem; font-weight:700; color:var(--vx-teal); '
                'text-transform:uppercase;">Voice Clarity</div>'
                f'<div style="font-size:1.8rem; font-weight:700; color:var(--vx-ink); '
                f'margin:0.25rem 0;">{hnr_disp}</div>'
                '<p style="font-size:0.80rem; color:var(--vx-muted);">'
                "Harmonics-to-noise</p>"
                "</div>",
                unsafe_allow_html=True,
            )

    if html_report and report_dict:
        st.markdown(
            '<h4 style="margin:1.5rem 0 0.5rem 0;">Export Your Results</h4>',
            unsafe_allow_html=True,
        )
        d1, d2, _ = st.columns([1.3, 1.3, 1.5])
        with d1:
            st.download_button(
                "Download Summary Report (HTML)",
                html_report,
                "voxneuro_summary_report.html",
                "text/html",
                key="m6_res_html_dl",
            )
        with d2:
            st.download_button(
                "Download Session Data (JSON)",
                json.dumps(
                    {**report_dict, "prediction_summary": prediction.to_dict()},
                    indent=2,
                    allow_nan=False,
                    default=str,
                ),
                "voxneuro_session_result.json",
                "application/json",
                key="m6_res_json_dl",
            )


def show_user_history_page(conn: sqlite3.Connection | None, user: UserAccount | None) -> None:
    """Participant-scoped assessment history page per Section 9."""
    st.title("My Assessment History")
    if user is None or conn is None:
        st.info("Please sign in from the Account page to view saved assessment records.")
        return

    if not user.prediction_retention_opt_in:
        st.info(
            "Result retention is currently OFF for your account. New voice checks run in "
            "transient memory only and are not saved to history unless you opt in on your "
            "Account page."
        )

    rows = conn.execute(
        """
        SELECT prediction_id, model_version, acquisition_domain_id, research_score,
               research_classification, calibration_status, abstained, abstention_reason, created_at
        FROM prediction_records
        WHERE user_id = ? OR (participant_id IS NOT NULL AND participant_id = ?)
        ORDER BY created_at DESC;
        """,
        (user.user_id, user.participant_id or "__none__"),
    ).fetchall()

    if not rows:
        st.info("No saved voice check summaries are stored for your account.")
        return

    st.caption(
        "Important: Longitudinal comparisons reflect day-to-day acoustic variations. "
        "Do not interpret small changes in scores as clinical deterioration or recovery."
    )
    df = pd.DataFrame([dict(r) for r in rows])
    st.dataframe(df, use_container_width=True)


def show_account_portal(conn: sqlite3.Connection | None) -> None:
    """Account sign-in, self-registration, password reset, and profile retention controls."""
    st.title("Account & Preferences")
    if conn is None:
        st.warning("Account storage database is not initialized yet.")
        return

    token = st.session_state.get("voxneuro_auth_token")
    current_user = st.session_state.get("voxneuro_current_user")
    if current_user is not None:
        st.success(
            f"Signed in as **{current_user.display_name}** (`{current_user.username}`, "
            f"role: `{current_user.role}`)"
        )
        with st.form("m6_profile_prefs_form"):
            new_name = st.text_input("Display Name", value=current_user.display_name)
            opt_in = st.checkbox(
                "Opt in to saving future voice check research summaries to My History "
                "(audio is never saved)",
                value=current_user.prediction_retention_opt_in,
            )
            if st.form_submit_button("Save Preferences"):
                try:
                    updated = update_user_profile_preferences(
                        conn, token, display_name=new_name, prediction_retention_opt_in=opt_in
                    )
                    st.session_state["voxneuro_current_user"] = updated
                    st.success("Preferences updated.")
                except Exception as exc:
                    st.error(f"Update failed: {exc}")

        if st.button("Sign Out", key="m6_signout_btn"):
            if token:
                revoke_session(conn, token)
            st.session_state.pop("voxneuro_auth_token", None)
            st.session_state.pop("voxneuro_current_user", None)
            st.success("Signed out safely.")
            st.rerun()
        return

    tab_login, tab_register, tab_reset = st.tabs(["Sign In", "Create Account", "Reset Password"])
    with tab_login:
        with st.form("m6_login_form"):
            ident = st.text_input("Username or Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                try:
                    user, raw_token = authenticate_user(conn, identifier=ident, password=pw)
                    st.session_state["voxneuro_auth_token"] = raw_token
                    st.session_state["voxneuro_current_user"] = user
                    st.success(f"Welcome back, {user.display_name}.")
                    st.rerun()
                except AuthorizationError as exc:
                    st.error(str(exc))
    with tab_register:
        with st.form("m6_register_form"):
            r_user = st.text_input("Choose a username (min 3 chars)")
            r_email = st.text_input("Email address")
            r_name = st.text_input("Display name")
            r_pw = st.text_input("Password (min 8 chars)", type="password")
            r_opt_in = st.checkbox(
                "Allow saving optional research summaries to my history", value=False
            )
            if st.form_submit_button("Create Participant Account"):
                try:
                    created = register_user(
                        conn,
                        username=r_user,
                        email=r_email,
                        password=r_pw,
                        display_name=r_name,
                        role="participant",
                        prediction_retention_opt_in=bool(r_opt_in),
                    )
                    user, raw_token = authenticate_user(
                        conn, identifier=created.username, password=r_pw
                    )
                    st.session_state["voxneuro_auth_token"] = raw_token
                    st.session_state["voxneuro_current_user"] = user
                    st.success("Account created and signed in.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Registration failed: {exc}")
    with tab_reset:
        with st.form("m6_reset_req_form"):
            reset_email = st.text_input("Registered email address")
            if st.form_submit_button("Request Password Recovery"):
                issue_password_reset_token(conn, email=reset_email)
                st.info(
                    "If an active account is associated with this email, a single-use "
                    "recovery token has been recorded. To protect participant privacy and "
                    "prevent account takeover, tokens are not displayed publicly. In this "
                    "local prototype, obtain your token from your study administrator."
                )
        with st.form("m6_reset_complete_form"):
            st.caption("Enter the single-use recovery token provided by your study administrator:")
            tok_input = st.text_input("Reset token", type="password")
            new_pw = st.text_input("New password (min 8 chars)", type="password")
            if st.form_submit_button("Reset Password"):
                try:
                    complete_password_reset(conn, reset_token=tok_input, new_password=new_pw)
                    st.success("Password updated. You can now sign in with your new password.")
                except Exception as exc:
                    st.error(f"Password reset failed: {exc}")


def build_session_prediction(
    *,
    features: dict[str, Any] | None,
    quality_valid: bool,
    capture_origin: str,
    input_domain: str,
    conn: sqlite3.Connection | None,
    user: UserAccount | None,
) -> PredictionResult:
    """Execute fail-closed PredictionService with the active user/domain context."""
    from voxneuro.modeling.prediction import InputCaptureContext

    ctx = InputCaptureContext(
        capture_origin=capture_origin, task_type="sustained_vowel", verified_origin=False
    )
    return run_prediction_service(
        features=features,
        quality_valid=quality_valid,
        capture_context=ctx,
        input_domain=input_domain,
        conn=conn,
        model_id=st.session_state.get("voxneuro_selected_model_id"),
        user_id=user.user_id if user else None,
        participant_id=user.participant_id if user else None,
        allow_prediction_retention=bool(user and user.prediction_retention_opt_in),
    )
