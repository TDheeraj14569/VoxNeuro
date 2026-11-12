"""Modern, accessible digital-health design system and reusable UI components for VoxNeuro."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from voxneuro.modeling.prediction_service import M6_MEDICAL_DISCLAIMER, PredictionResult

M6_RESPONSIVE_CSS = """
<style>
:root {
  --vx-canvas: #F8FAFC;
  --vx-surface: #FFFFFF;
  --vx-surface-soft: #F1F5F9;
  --vx-ink: #0F172A;
  --vx-ink-secondary: #334155;
  --vx-muted: #64748B;
  --vx-teal: #0D7A70;
  --vx-teal-dark: #0A6159;
  --vx-teal-soft: #E6F4F1;
  --vx-teal-light: #F0FDF4;
  --vx-blue: #1D6FBD;
  --vx-blue-soft: #EFF6FF;
  --vx-sage: #16A34A;
  --vx-sage-bg: #F0FDF4;
  --vx-amber: #D97706;
  --vx-amber-bg: #FFFBEB;
  --vx-amber-border: #FCD34D;
  --vx-rose: #DC2626;
  --vx-rose-bg: #FEF2F2;
  --vx-border: #E2E8F0;
  --vx-shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --vx-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.06);
  --vx-shadow-lg: 0 10px 30px -4px rgba(15, 23, 42, 0.08);
  --vx-radius: 14px;
  --vx-radius-sm: 8px;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--vx-canvas) !important;
  color: var(--vx-ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  overflow-x: hidden !important;
}

.main .block-container {
  max-width: 1140px !important;
  padding-top: 1.25rem !important;
  padding-bottom: 3.5rem !important;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
}

button:focus-visible,
a:focus-visible,
input:focus-visible,
select:focus-visible,
[tabindex]:focus-visible {
  outline: 3px solid var(--vx-teal) !important;
  outline-offset: 2px !important;
}

button[kind="primary"],
.stButton > button[kind="primary"] {
  background: var(--vx-teal) !important;
  border: 1px solid var(--vx-teal-dark) !important;
  color: #FFFFFF !important;
  border-radius: var(--vx-radius-sm) !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em !important;
  padding: 0.55rem 1.25rem !important;
  box-shadow: 0 2px 8px rgba(13, 122, 112, 0.20) !important;
  transition: all 0.18s ease-in-out !important;
}

button[kind="primary"]:hover:not(:disabled),
.stButton > button[kind="primary"]:hover:not(:disabled) {
  background: var(--vx-teal-dark) !important;
  box-shadow: 0 4px 14px rgba(13, 122, 112, 0.30) !important;
  transform: translateY(-1px) !important;
}

button[kind="secondary"],
.stButton > button:not([kind="primary"]) {
  background: var(--vx-surface) !important;
  border: 1px solid var(--vx-border) !important;
  color: var(--vx-ink-secondary) !important;
  border-radius: var(--vx-radius-sm) !important;
  font-weight: 500 !important;
  transition: all 0.15s ease-in-out !important;
}

button[kind="secondary"]:hover:not(:disabled),
.stButton > button:not([kind="primary"]):hover:not(:disabled) {
  border-color: var(--vx-teal) !important;
  color: var(--vx-teal) !important;
  background: var(--vx-teal-soft) !important;
}

.vx-brand-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.85rem 1.35rem;
  background: var(--vx-surface);
  border: 1px solid var(--vx-border);
  border-radius: var(--vx-radius);
  box-shadow: var(--vx-shadow-sm);
  margin-bottom: 0.85rem;
}

.vx-brand-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.vx-logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--vx-teal), #1D6FBD);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
}

.vx-brand-title {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--vx-ink);
  letter-spacing: -0.025em;
}

.vx-pill-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: var(--vx-surface-soft);
  color: var(--vx-muted);
  border: 1px solid var(--vx-border);
}

.vx-pill-teal {
  background: var(--vx-teal-soft);
  color: var(--vx-teal-dark);
  border-color: rgba(13, 122, 112, 0.25);
}

.vx-pill-amber {
  background: var(--vx-amber-bg);
  color: #8A4B00;
  border-color: rgba(217, 119, 6, 0.25);
}

.vx-disclaimer {
  background: var(--vx-amber-bg);
  border: 1px solid var(--vx-amber-border);
  border-left: 4px solid var(--vx-amber);
  border-radius: 10px;
  padding: 0.95rem 1.25rem;
  margin: 0.85rem 0 1.25rem 0;
  font-size: 0.92rem;
  line-height: 1.55;
  color: #78350F;
}

.vx-disclaimer strong {
  color: #92400E;
}

.vx-hero-card {
  background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
  border: 1px solid var(--vx-border);
  border-radius: 18px;
  padding: 2.25rem;
  box-shadow: var(--vx-shadow);
  margin-bottom: 1.25rem;
  position: relative;
  overflow: hidden;
}

.vx-hero-eyebrow {
  color: var(--vx-teal);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.vx-hero-card h1, .vx-hero-card h2 {
  font-size: 2.1rem;
  line-height: 1.25;
  font-weight: 700;
  color: var(--vx-ink);
  letter-spacing: -0.03em;
  margin: 0 0 0.85rem 0;
}

.vx-hero-text {
  font-size: 1.08rem;
  line-height: 1.6;
  color: var(--vx-ink-secondary);
  max-width: 680px;
  margin: 0 0 1.25rem 0;
}

.vx-card {
  background: var(--vx-surface);
  border: 1px solid var(--vx-border);
  border-radius: var(--vx-radius);
  padding: 1.35rem 1.45rem;
  box-shadow: var(--vx-shadow-sm);
  margin-bottom: 1rem;
  height: 100%;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.vx-card:hover {
  box-shadow: var(--vx-shadow);
}

.vx-card h4 {
  margin: 0 0 0.45rem 0;
  color: var(--vx-ink);
  font-size: 1.08rem;
  font-weight: 600;
}

.vx-card p {
  margin: 0;
  color: var(--vx-ink-secondary);
  font-size: 0.93rem;
  line-height: 1.55;
}

.vx-step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: var(--vx-teal-soft);
  color: var(--vx-teal-dark);
  font-weight: 700;
  font-size: 0.85rem;
  margin-bottom: 0.65rem;
}

.vx-stepper {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.5rem 0 1.25rem 0;
}

.vx-step-item {
  flex: 1 1 140px;
  padding: 0.6rem 0.85rem;
  border-radius: 10px;
  font-size: 0.82rem;
  border: 1px solid var(--vx-border);
  background: var(--vx-surface);
  color: var(--vx-muted);
  display: flex;
  align-items: center;
  gap: 0.45rem;
  transition: all 0.2s ease;
}

.vx-step-active {
  background: var(--vx-teal-soft);
  border-color: var(--vx-teal);
  color: var(--vx-teal-dark);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(13, 122, 112, 0.15);
}

.vx-step-done {
  background: var(--vx-sage-bg);
  border-color: rgba(22, 163, 74, 0.35);
  color: var(--vx-sage);
  font-weight: 500;
}

.vx-result-container {
  background: var(--vx-surface);
  border: 1px solid var(--vx-border);
  border-radius: 18px;
  padding: 2rem;
  box-shadow: var(--vx-shadow-lg);
  margin: 1.25rem 0;
}

.vx-gauge-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.5rem 0;
}

.vx-gauge-val {
  font-size: 3.2rem;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--vx-ink);
  line-height: 1;
}

.vx-gauge-label {
  font-size: 1rem;
  font-weight: 600;
  color: var(--vx-ink-secondary);
  margin-top: 0.5rem;
  text-align: center;
}

.vx-gauge-sub {
  font-size: 0.85rem;
  color: var(--vx-muted);
  margin-top: 0.25rem;
  text-align: center;
}

.vx-card-case-a {
  border-left: 6px solid var(--vx-teal);
  background: linear-gradient(180deg, #FFFFFF 0%, var(--vx-teal-light) 100%);
}

.vx-card-case-b {
  border-left: 6px solid #1D6FBD;
  background: linear-gradient(180deg, #FFFFFF 0%, #F0F7FF 100%);
}

.vx-card-case-c {
  border-left: 6px solid var(--vx-amber);
  background: linear-gradient(180deg, #FFFFFF 0%, #FFFDF5 100%);
}

.vx-card-case-d {
  border-left: 6px solid var(--vx-muted);
  background: #F8FAFC;
}

.vx-next-steps {
  background: var(--vx-surface);
  border: 1px solid var(--vx-border);
  border-radius: var(--vx-radius);
  padding: 1.35rem 1.5rem;
  margin-top: 1.5rem;
}

.vx-next-steps h4 {
  margin: 0 0 0.5rem 0;
  color: var(--vx-ink);
  font-size: 1.05rem;
}

.vx-next-steps ul {
  margin: 0;
  padding-left: 1.25rem;
  color: var(--vx-ink-secondary);
  font-size: 0.92rem;
  line-height: 1.6;
}

@media (max-width: 1024px) {
  .main .block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
  .vx-hero-card {
    padding: 1.6rem;
  }
}

@media (max-width: 768px) {
  .vx-brand-bar {
    padding: 0.75rem 1rem;
  }
  .vx-hero-card h1, .vx-hero-card h2 {
    font-size: 1.65rem;
  }
  .vx-hero-text {
    font-size: 0.98rem;
  }
  .vx-step-item {
    flex: 1 1 45%;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
</style>
"""


def render_brand_bar(*, user_display: str | None = None, role: str | None = None) -> None:
    """Render accessible, clean digital health brand header bar with status."""
    if user_display:
        right_badge = (
            '<span class="vx-pill-badge vx-pill-teal">'
            '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.5">'
            '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>'
            '<circle cx="12" cy="7" r="4"/></svg>'
            f"{html.escape(user_display)} ({html.escape(role or 'participant')})</span>"
        )
    else:
        right_badge = (
            '<span class="vx-pill-badge">'
            '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2">'
            '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>'
            "</svg>Health Research Platform · Non-Diagnostic</span>"
        )

    st.markdown(
        '<div class="vx-brand-bar" role="banner">'
        '<div class="vx-brand-left">'
        '<div class="vx-logo-icon" aria-hidden="true">'
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 2v20M17 5v14M7 5v14M22 10v4M2 10v4"/>'
        "</svg>"
        "</div>"
        '<span class="vx-brand-title">VoxNeuro</span>'
        '<span class="vx-pill-badge vx-pill-teal">Voice Biomarker Research</span>'
        "</div>"
        f"<div>{right_badge}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_animated_voice_hero() -> None:
    """Render an elegant soundwave SVG resonance illustration."""
    svg_hero = (
        '<div style="display:flex; justify-content:center; align-items:center; '
        'margin:1.25rem 0 0.5rem 0;" aria-hidden="true">'
        '<svg width="100%" height="70" viewBox="0 0 800 70" preserveAspectRatio="none" '
        'style="max-width:820px; border-radius:10px; background:linear-gradient(90deg, '
        'rgba(13,122,112,0.03) 0%, rgba(29,111,189,0.06) 50%, rgba(13,122,112,0.03) 100%);">'
        "<defs>"
        '<linearGradient id="waveGrad" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#0D7A70" stop-opacity="0.3"/>'
        '<stop offset="30%" stop-color="#0D7A70" stop-opacity="0.85"/>'
        '<stop offset="50%" stop-color="#1D6FBD" stop-opacity="0.95"/>'
        '<stop offset="70%" stop-color="#0D7A70" stop-opacity="0.85"/>'
        '<stop offset="100%" stop-color="#0D7A70" stop-opacity="0.3"/>'
        "</linearGradient>"
        "</defs>"
        '<path d="M 0 35 Q 50 15, 100 35 T 200 35 T 300 20 T 400 35 T 500 50 '
        'T 600 35 T 700 22 T 800 35" fill="none" stroke="url(#waveGrad)" stroke-width="2.5" '
        'stroke-linecap="round"/>'
        '<path d="M 0 35 Q 40 48, 80 35 T 160 35 T 240 45 T 320 35 T 400 18 '
        'T 480 35 T 560 52 T 640 35 T 720 26 T 800 35" fill="none" stroke="url(#waveGrad)" '
        'stroke-width="1.8" stroke-dasharray="4,3" opacity="0.6"/>'
        "</svg>"
        "</div>"
    )
    st.markdown(svg_hero, unsafe_allow_html=True)


def render_medical_disclaimer() -> None:
    """Render the mandatory prominent non-diagnostic research disclaimer."""
    st.markdown(
        f'<div class="vx-disclaimer" role="note">'
        f"<strong>Important Medical Notice:</strong> {html.escape(M6_MEDICAL_DISCLAIMER)}"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_stepper(steps: list[str], active_index: int) -> None:
    """Render accessible, clean multi-step progress indicator."""
    items: list[str] = []
    for idx, label in enumerate(steps):
        cls = "vx-step-item"
        if idx < active_index:
            cls += " vx-step-done"
            status_icon = (
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="3">'
                '<polyline points="20 6 9 17 4 12"/></svg>'
            )
        elif idx == active_index:
            cls += " vx-step-active"
            status_icon = (
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
                'stroke="currentColor" stroke-width="2.5">'
                '<circle cx="12" cy="12" r="10"/>'
                '<circle cx="12" cy="12" r="3" fill="currentColor"/>'
                "</svg>"
            )
        else:
            status_icon = f'<span style="opacity:0.6;">{idx + 1}.</span>'
        items.append(f'<div class="{cls}">{status_icon}<span>{html.escape(label)}</span></div>')
    st.markdown(
        f'<div class="vx-stepper" aria-label="Assessment steps">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def render_plain_quality_summary(quality: Any, record: Any) -> None:
    """Render approachable plain-language recording quality feedback for ordinary users."""
    if quality.valid:
        st.markdown(
            '<div class="vx-card" style="background:var(--vx-teal-light); '
            'border-color:rgba(13,122,112,0.25); margin-bottom:1rem;">'
            '<div style="display:flex; align-items:center; gap:0.5rem; '
            'color:var(--vx-teal-dark); font-weight:700; margin-bottom:0.35rem;">'
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.5">'
            '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>'
            '<polyline points="22 4 12 14.01 9 11.01"/></svg>'
            "Recording Quality: Clear &amp; Valid"
            "</div>"
            f'<p style="color:#1E3A34; font-size:0.92rem; margin:0;">'
            f"Your voice recording ({quality.duration_seconds:.1f} s at {record.sample_rate:,} Hz) "
            f"has sufficient volume and steady sound quality for acoustic measurement."
            f"</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        err_items = "".join(f"<li>{html.escape(e)}</li>" for e in quality.errors)
        st.markdown(
            '<div class="vx-card" style="background:var(--vx-amber-bg); '
            'border-color:var(--vx-amber-border); margin-bottom:1rem;">'
            '<div style="display:flex; align-items:center; gap:0.5rem; color:#92400E; '
            'font-weight:700; margin-bottom:0.35rem;">'
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/>'
            '<line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
            "We could not hear your voice clearly"
            "</div>"
            '<p style="color:#78350F; font-size:0.92rem; margin-bottom:0.5rem;">'
            "This recording did not meet our clarity screening standards for reliable analysis:"
            "</p>"
            f'<ul style="color:#78350F; font-size:0.88rem; margin:0 0 0.5rem 0; '
            f'padding-left:1.25rem;">{err_items}</ul>'
            '<p style="color:#92400E; font-size:0.85rem; margin:0; font-weight:500;">'
            "Tip: Please move to a quieter room, hold the microphone about 15–20 cm away, "
            'and sustain an even "ah" sound for 3 to 5 seconds.'
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )


def render_prediction_outcome_card(prediction: PredictionResult) -> None:
    """Render the primary result card for Cases A, B, C, or D per Section 7."""
    st.markdown('<div class="vx-result-container">', unsafe_allow_html=True)

    if prediction.abstained:
        reason_text = html.escape(
            prediction.abstention_reason
            or "No reliable automated prediction could be produced for this recording."
        )
        st.markdown(
            '<div class="vx-card vx-card-case-c" style="padding:1.5rem;">'
            '<div style="display:flex; align-items:center; gap:0.5rem; color:#92400E; '
            'font-size:1.15rem; font-weight:700; margin-bottom:0.65rem;">'
            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/>'
            '<line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
            "We could not provide a reliable result"
            "</div>"
            f'<p style="font-size:0.95rem; color:#451A03; line-height:1.6; margin-bottom:0.85rem;">'
            f"{reason_text}"
            f"</p>"
            '<div style="background:rgba(255,255,255,0.7); border-radius:8px; '
            'padding:0.85rem 1rem; border:1px solid rgba(217,119,6,0.2);">'
            '<strong style="color:#92400E; font-size:0.88rem;">Why did this happen?</strong>'
            '<p style="color:#78350F; font-size:0.86rem; margin:0.35rem 0 0 0; line-height:1.5;">'
            "To protect against misleading predictions, VoxNeuro withholds disease likelihood "
            "estimates whenever a recording is made on an uncalibrated device, background noise "
            "is detected, or scientific external validation for this microphone type is ongoing."
            "</p>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    elif (
        prediction.calibration_status == "EXTERNALLY_VALIDATED_CALIBRATED"
        and prediction.research_score is not None
    ):
        pct = round(prediction.research_score * 100, 1)
        st.markdown(
            '<div class="vx-card vx-card-case-a" style="padding:1.75rem;">'
            '<div class="vx-hero-eyebrow">Calibrated Voice Assessment</div>'
            '<div class="vx-gauge-wrapper">'
            f'<div class="vx-gauge-val" style="color:var(--vx-teal);">{pct}%</div>'
            '<div class="vx-gauge-label">'
            "Estimated likelihood of Parkinson's disease patterns</div>"
            '<div class="vx-gauge-sub">Based on this sustained vowel voice assessment</div>'
            "</div>"
            '<div style="background:var(--vx-teal-soft); border-radius:10px; '
            'padding:0.85rem 1.15rem; margin-top:1rem; text-align:center;">'
            '<p style="margin:0; font-size:0.90rem; color:var(--vx-teal-dark); font-weight:500;">'
            "This estimate reflects statistical vocal pattern similarity to clinical study "
            "participants. It is an algorithmic estimate, <strong>not a medical diagnosis</strong>."
            "</p>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    elif prediction.research_score is not None:
        pct = round(prediction.research_score * 100, 1)
        sim_word = "moderate"
        if prediction.research_score >= 0.67:
            sim_word = "stronger"
        elif prediction.research_score < 0.33:
            sim_word = "weaker"

        st.markdown(
            '<div class="vx-card vx-card-case-b" style="padding:1.75rem;">'
            '<div style="display:flex; justify-content:space-between; align-items:center; '
            'flex-wrap:wrap; margin-bottom:0.75rem;">'
            '<div class="vx-hero-eyebrow" style="color:#1D6FBD; margin:0;">'
            "Voice Assessment Result</div>"
            '<span class="vx-pill-badge" style="background:#EFF6FF; color:#1D6FBD; '
            'border-color:#BFDBFE;">Research Index</span>'
            "</div>"
            f'<h3 style="margin:0 0 0.5rem 0; color:var(--vx-ink); font-size:1.35rem;">'
            f"Your voice pattern showed a {sim_word} similarity to patterns observed in the study"
            f"</h3>"
            '<div class="vx-gauge-wrapper" style="padding:1rem 0;">'
            f'<div class="vx-gauge-val" style="color:#1D6FBD; font-size:2.8rem;">{pct}%</div>'
            '<div class="vx-gauge-label">Acoustic Similarity Index</div>'
            f'<div class="vx-gauge-sub">Experimental research score · Model version '
            f"{html.escape(prediction.model_version)}</div>"
            "</div>"
            '<div style="background:#F0F7FF; border:1px solid #BFDBFE; border-radius:8px; '
            'padding:0.85rem 1rem;">'
            '<p style="margin:0; font-size:0.88rem; color:#1E40AF; line-height:1.5;">'
            "<strong>Please note:</strong> This score describes acoustic properties only and is "
            "<strong>not a personal disease probability</strong>. It reflects similarity to "
            "telephone-based research recordings and has not been validated for clinical decisions."
            "</p>"
            "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    else:
        st.markdown(
            '<div class="vx-card vx-card-case-d" style="padding:1.5rem;">'
            '<h4 style="color:var(--vx-muted); margin:0 0 0.35rem 0;">'
            "This assessment is currently unavailable</h4>"
            '<p style="color:var(--vx-ink-secondary); font-size:0.92rem; margin:0;">'
            "Automated voice pattern scoring is currently disabled because prospective clinical "
            "validation for your capture method is ongoing. "
            "Descriptive measurements remain available."
            "</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="vx-next-steps">'
        "<h4>Recommended Next Steps</h4>"
        "<ul>"
        "<li><strong>Consult a Healthcare Professional:</strong> Voice changes alone cannot "
        "confirm or rule out Parkinson's disease. A qualified neurologist or physician can "
        "evaluate physical signs, symptoms, medical history, and clinical findings.</li>"
        "<li><strong>Understand Voice Variability:</strong> Temporary factors such as hydration, "
        "fatigue, colds, or ambient noise can alter acoustic steadiness.</li>"
        "<li><strong>Keep a Record:</strong> You can download your detailed summary report below "
        "to share with your care team if desired.</li>"
        "</ul>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)
    render_medical_disclaimer()
