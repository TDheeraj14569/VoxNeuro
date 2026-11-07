"""Streamlit interface for private, local voice signal analysis."""

from __future__ import annotations

import hashlib
import html
import json
from numbers import Real

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve

from voxneuro.audio.io import decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.validation import AudioValidationConfig, validate_audio
from voxneuro.config import PROJECT_ROOT, load_config
from voxneuro.dataset.validation import (
    read_json_object,
    validate_evaluation_receipt,
    validate_features,
    validate_manifest,
    validate_nested_evaluation_receipt,
)
from voxneuro.exceptions import (
    AudioReadError,
    AudioValidationError,
    FeatureExtractionError,
    VoxNeuroError,
)
from voxneuro.features.extractor import extract_features
from voxneuro.features.schema import (
    FEATURE_DEFINITIONS,
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.logging_config import configure_logging
from voxneuro.provenance import project_code_fingerprint
from voxneuro.reporting.html_report import render_voice_report_html
from voxneuro.reporting.report import DISCLAIMER, build_report
from voxneuro.visualization.acoustic_3d import (
    decorative_hero_payload,
    render_acoustic_view,
    spectrogram_payload,
    waveform_payload,
)
from voxneuro.visualization.spectrogram import spectrogram_figure
from voxneuro.visualization.waveform import waveform_figure

APP_CONFIG = load_config("application_config.yaml")
AUDIO_CONFIG = load_config("audio_config.yaml")
FEATURE_CONFIG = load_config("feature_config.yaml")
MODEL_CONFIG = load_config("model_config.yaml")
load_config("reviewed_exclusions.yaml")
if APP_CONFIG.get("store_recordings") or APP_CONFIG.get("store_reports_by_default"):
    raise RuntimeError("Persistent audio/report storage is not implemented in this prototype.")
configure_logging()
st.set_page_config(page_title="VoxNeuro · Voice analysis", page_icon="∿", layout="wide")

_STYLE = """
<style>
:root {
  --vox-ink: #F3F7F5;
  --vox-muted: #A7B8B5;
  --vox-teal: #55D9C1;
  --vox-teal-glow: rgba(85, 217, 193, 0.35);
  --vox-teal-wash: #122733;
  --vox-amber: #E5B56D;
  --vox-red: #E27F80;
  --vox-rule: #263E47;
  --vox-paper: #07131B;
  --vox-surface: #0C1D27;
  --vox-surface-glass: rgba(12, 29, 39, 0.72);
  --vox-elevated: #122733;
}
.stApp {
  background: radial-gradient(circle at 18% 12%, rgba(20, 52, 66, 0.45) 0%, transparent 48%),
              radial-gradient(circle at 82% 88%, rgba(14, 40, 52, 0.38) 0%, transparent 52%),
              var(--vox-paper) !important;
  color: var(--vox-ink);
}
header[data-testid="stHeader"] { background: transparent; }
main .block-container {
  max-width: 1220px;
  padding: 2.2rem 3.1rem 4rem;
}
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0A1922 0%, #08151D 100%) !important;
  border-right: 1px solid rgba(85, 217, 193, 0.16) !important;
}
.vox-wordmark {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  color: var(--vox-ink);
  font-size: 1.12rem;
  font-weight: 650;
  letter-spacing: -0.035em;
}
.vox-wave {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 22px;
  color: var(--vox-teal);
}
.vox-wave i {
  display: block;
  width: 2px;
  border-radius: 2px;
  background: currentColor;
}
.vox-wave i:nth-child(1), .vox-wave i:nth-child(7) { height: 6px; }
.vox-wave i:nth-child(2), .vox-wave i:nth-child(6) { height: 12px; }
.vox-wave i:nth-child(3), .vox-wave i:nth-child(5) { height: 17px; }
.vox-wave i:nth-child(4) { height: 22px; }
.vox-kicker {
  color: var(--vox-teal);
  font-size: 0.76rem;
  font-weight: 650;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 0 0 0.5rem 0;
}
.vox-lede {
  color: var(--vox-muted);
  font-size: 1.08rem;
  max-width: 780px;
  line-height: 1.6;
}
.vox-rule {
  border: 0;
  border-top: 1px solid var(--vox-rule);
  margin: 1.35rem 0;
}
.vox-step {
  color: var(--vox-muted);
  font-size: 0.83rem;
  letter-spacing: 0.025em;
}
.vox-step strong {
  color: var(--vox-teal);
  font-size: 0.76rem;
  letter-spacing: 0.09em;
  margin-right: 0.45rem;
}
.vox-note {
  border-left: 3px solid var(--vox-teal);
  padding: 0.15rem 0 0.15rem 0.9rem;
  color: var(--vox-muted);
  line-height: 1.55;
}
.vox-status {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: var(--vox-teal);
  font-size: 0.76rem;
  font-weight: 650;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.vox-status::before {
  content: "";
  width: 7px;
  height: 7px;
  background: currentColor;
  border-radius: 50%;
  box-shadow: 0 0 8px var(--vox-teal);
}
h1, h2, h3 {
  color: var(--vox-ink);
  letter-spacing: -0.035em;
}
.stApp, .stApp p, .stApp label, .stApp li { color: var(--vox-ink); }
.stApp [data-testid="stCaptionContainer"] { color: var(--vox-muted); }
.stApp input, .stApp textarea, .stApp [data-baseweb="select"] > div {
  color: var(--vox-ink); background: var(--vox-surface); border-color: var(--vox-rule);
}
.stApp button:focus-visible, .stApp input:focus-visible, .stApp textarea:focus-visible {
  outline: 2px solid var(--vox-teal); outline-offset: 2px;
}
div[data-testid="stMetric"] {
  background: rgba(12, 29, 39, 0.7) !important;
  border: 1px solid rgba(85, 217, 193, 0.2) !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  border-radius: 10px !important;
  padding: 0.85rem 1rem !important;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.25) !important;
}
.stApp [data-testid="stDataFrame"] {
  border: 1px solid rgba(85, 217, 193, 0.2) !important;
  border-radius: 8px !important;
  background: rgba(12, 29, 39, 0.7) !important;
}
.stApp [data-testid="stJson"], .react-json-view {
  background: rgba(10, 25, 34, 0.75) !important;
  border: 1px solid rgba(85, 217, 193, 0.22) !important;
  border-radius: 10px !important;
  padding: 1rem !important;
  backdrop-filter: blur(14px) !important;
  -webkit-backdrop-filter: blur(14px) !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3) !important;
}
.vox-glass-card {
  background: rgba(12, 29, 39, 0.65);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(85, 217, 193, 0.16);
  border-radius: 12px;
  padding: 1.25rem 1.4rem;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.28);
  margin-bottom: 1.15rem;
}
.vox-glass-hero {
  background: linear-gradient(135deg, rgba(16, 42, 54, 0.7), rgba(8, 22, 30, 0.85));
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(85, 217, 193, 0.25);
  border-radius: 14px;
  padding: 1.5rem 1.8rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 10px 36px rgba(0, 0, 0, 0.35);
}
.vox-table-wrapper {
  border: 1px solid rgba(85, 217, 193, 0.2);
  border-radius: 12px;
  overflow-x: auto;
  background: rgba(10, 25, 34, 0.65);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.3);
  margin: 0.85rem 0 1.15rem;
}
.vox-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
  color: #EDF6F7;
  text-align: left;
}
.vox-table th {
  background: rgba(16, 40, 52, 0.88);
  color: #55D9C1;
  padding: 0.75rem 1rem;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border-bottom: 1px solid rgba(85, 217, 193, 0.25);
  white-space: nowrap;
}
.vox-table td {
  padding: 0.7rem 1rem;
  border-bottom: 1px solid rgba(38, 62, 71, 0.45);
  vertical-align: middle;
}
.vox-table tr:last-child td { border-bottom: 0; }
.vox-table tr:hover td { background: rgba(85, 217, 193, 0.07); }
.vox-val-num {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  color: #67E2CE;
  font-weight: 600;
  white-space: nowrap;
}
.vox-code-pill {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  background: rgba(85, 217, 193, 0.1);
  color: #E2F5F1;
  border: 1px solid rgba(85, 217, 193, 0.2);
  border-radius: 4px;
  padding: 0.15rem 0.45rem;
  font-size: 0.8rem;
  white-space: nowrap;
}
.vox-unit-pill { color: #A7B8B5; font-size: 0.78rem; }
.vox-badge-ok {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(85, 217, 193, 0.12);
  color: #55D9C1;
  border: 1px solid rgba(85, 217, 193, 0.35);
  border-radius: 9999px;
  padding: 0.18rem 0.6rem;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
}
.vox-badge-ok::before {
  content: "";
  width: 5px;
  height: 5px;
  background: #55D9C1;
  border-radius: 50%;
  box-shadow: 0 0 6px #55D9C1;
}
.vox-badge-na {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(229, 181, 109, 0.12);
  color: #E5B56D;
  border: 1px solid rgba(229, 181, 109, 0.35);
  border-radius: 9999px;
  padding: 0.18rem 0.6rem;
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
}
.vox-quality-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.85rem;
  margin: 0.85rem 0 1.25rem;
}
.vox-quality-card {
  background: rgba(12, 29, 39, 0.7);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(85, 217, 193, 0.18);
  border-radius: 10px;
  padding: 0.85rem 1rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  transition: transform 0.2s ease, border-color 0.2s ease;
}
.vox-quality-card:hover {
  transform: translateY(-2px);
  border-color: rgba(85, 217, 193, 0.45);
}
.vox-qc-label {
  color: #A7B8B5;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 0.35rem;
}
.vox-qc-value {
  color: #F3F7F5;
  font-size: 1.3rem;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  line-height: 1.2;
  margin-bottom: 0.25rem;
}
.vox-qc-sub { color: #55D9C1; font-size: 0.74rem; font-weight: 500; }
.stApp button,
.stApp [data-testid="stDownloadButton"] > button,
.stApp button[kind="secondary"],
.stApp [data-testid="stBaseButton-secondary"] {
  background: rgba(16, 39, 51, 0.78) !important;
  color: #EDF6F7 !important;
  border: 1px solid rgba(85, 217, 193, 0.35) !important;
  border-radius: 8px !important;
  backdrop-filter: blur(12px) !important;
  -webkit-backdrop-filter: blur(12px) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.28) !important;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
}
.stApp button:hover,
.stApp [data-testid="stDownloadButton"] > button:hover,
.stApp button[kind="secondary"]:hover,
.stApp [data-testid="stBaseButton-secondary"]:hover {
  background: linear-gradient(135deg, rgba(28, 72, 86, 0.95), rgba(18, 50, 65, 0.95)) !important;
  color: #FFFFFF !important;
  border-color: rgba(85, 217, 193, 0.8) !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.42), 0 0 16px rgba(85, 217, 193, 0.3) !important;
  transform: translateY(-2px) !important;
}
.stApp button:active,
.stApp [data-testid="stDownloadButton"] > button:active {
  background: rgba(22, 58, 72, 0.95) !important;
  border-color: #55D9C1 !important;
  color: #FFFFFF !important;
  transform: translateY(0px) !important;
}
.stApp button p,
.stApp [data-testid="stDownloadButton"] button p {
  color: inherit !important;
  margin: 0 !important;
}
.stApp button[kind="primary"],
.stApp [data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #55D9C1 0%, #34B8A0 100%) !important;
  color: #07131B !important;
  border: 1px solid #55D9C1 !important;
  font-weight: 650 !important;
  box-shadow: 0 4px 16px rgba(85, 217, 193, 0.25) !important;
}
.stApp button[kind="primary"]:hover,
.stApp [data-testid="stBaseButton-primary"]:hover {
  background: linear-gradient(135deg, #6BE6CF 0%, #45C5AD 100%) !important;
  color: #040D13 !important;
  border-color: #6BE6CF !important;
  box-shadow: 0 8px 28px rgba(85, 217, 193, 0.45), 0 0 20px rgba(85, 217, 193, 0.35) !important;
  transform: translateY(-2px) !important;
}
.stApp button[kind="primary"] p,
.stApp [data-testid="stBaseButton-primary"] p {
  color: #07131B !important;
  font-weight: 650 !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] > div { gap: 0.35rem; }
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
  background: rgba(12, 29, 39, 0.4);
  border: 1px solid rgba(38, 62, 71, 0.4);
  border-radius: 8px;
  padding: 0.45rem 0.75rem;
  transition: all 0.2s ease;
  cursor: pointer;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background: rgba(85, 217, 193, 0.08);
  border-color: rgba(85, 217, 193, 0.3);
  color: #FFFFFF;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"],
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(85, 217, 193, 0.22), rgba(85, 217, 193, 0.06));
  border-color: rgba(85, 217, 193, 0.65);
  box-shadow: 0 0 14px rgba(85, 217, 193, 0.15);
}
.stApp [data-baseweb="tab-list"] {
  background: rgba(10, 25, 34, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(38, 62, 71, 0.6);
  border-radius: 10px;
  padding: 0.3rem;
  gap: 0.35rem;
}
.stApp [data-baseweb="tab"] {
  border-radius: 7px;
  padding: 0.45rem 1rem;
  color: #A7B8B5;
  font-weight: 550;
  transition: all 0.2s ease;
  border: 0;
}
.stApp [data-baseweb="tab"]:hover {
  color: #FFFFFF;
  background: rgba(85, 217, 193, 0.1);
}
.stApp [data-baseweb="tab"][aria-selected="true"] {
  background: rgba(85, 217, 193, 0.2);
  color: #55D9C1;
  box-shadow: 0 0 12px rgba(85, 217, 193, 0.2);
}
.stApp [data-baseweb="tab-highlight"] { display: none; }
.stApp [data-testid="stExpander"] {
  background: rgba(10, 25, 34, 0.55);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(38, 62, 71, 0.7);
  border-radius: 10px;
}
.stApp [data-testid="stExpander"] summary {
  color: #EDF6F7;
  font-weight: 550;
}
.stApp [data-testid="stExpander"] summary:hover { color: #55D9C1; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
@media (max-width: 720px) {
  main .block-container {
    padding: 1.3rem 1rem 2.5rem;
  }
}
</style>
"""
st.markdown(_STYLE, unsafe_allow_html=True)


def _analysis_config() -> tuple[AudioValidationConfig, dict, dict]:
    audio_cfg = dict(AUDIO_CONFIG)
    feature_cfg = dict(FEATURE_CONFIG)
    feature_cfg.pop("schema_version", None)
    validation = AudioValidationConfig(
        min_duration_seconds=float(audio_cfg["min_duration_seconds"]),
        max_duration_seconds=float(audio_cfg["max_duration_seconds"]),
        min_rms=float(audio_cfg["min_rms"]),
        max_peak=float(audio_cfg["max_peak"]),
        clipping_fraction_limit=float(audio_cfg["clipping_fraction_limit"]),
        min_voiced_fraction=float(audio_cfg["min_voiced_fraction"]),
        frame_ms=int(audio_cfg["frame_ms"]),
        mono_policy=str(audio_cfg["mono_policy"]),
        pitch_floor_hz=float(feature_cfg["pitch_floor_hz"]),
        pitch_ceiling_hz=float(feature_cfg["pitch_ceiling_hz"]),
    )
    return validation, feature_cfg, audio_cfg


def _clear_assessment() -> None:
    for key in (
        "voxneuro_record",
        "voxneuro_payload",
        "voxneuro_quality",
        "voxneuro_processed",
        "voxneuro_features",
        "voxneuro_report",
        "voxneuro_html_report",
        "voxneuro_analysis_status",
        "voxneuro_analysis_error",
    ):
        st.session_state.pop(key, None)


def _analyze(payload: bytes) -> None:
    _clear_assessment()
    st.session_state["voxneuro_analysis_status"] = "processing"
    max_mb = int(APP_CONFIG["max_upload_mb"])
    if len(payload) > max_mb * 1024 * 1024:
        raise ValueError(f"WAV file exceeds the {max_mb} MB upload limit.")

    validation_config, feature_config, audio_config = _analysis_config()
    record = decode_audio(payload)
    quality = validate_audio(record, validation_config)
    st.session_state["voxneuro_record"] = record
    st.session_state["voxneuro_payload"] = payload
    st.session_state["voxneuro_quality"] = quality
    if not quality.valid:
        st.session_state["voxneuro_analysis_status"] = "quality_failed"
        return

    processed = preprocess_audio(
        record,
        target_sample_rate=int(audio_config["target_sample_rate"]),
        silence_relative_db=float(audio_config["silence_relative_db"]),
        mono_policy=str(audio_config["mono_policy"]),
        validation_config=validation_config,
    )
    st.session_state["voxneuro_processed"] = processed
    features = extract_features(
        processed.samples,
        processed.sample_rate,
        original_sample_rate=record.sample_rate,
        preprocessing_config_fingerprint=configuration_fingerprint(audio_config),
        **feature_config,
    )
    st.session_state["voxneuro_features"] = features
    st.session_state["voxneuro_report"] = build_report(
        {
            "valid": quality.valid,
            "duration_seconds": quality.duration_seconds,
            "sample_rate_hz": record.sample_rate,
            "channels": record.channels,
            "subtype": record.subtype,
            "peak_amplitude_fs": quality.peak_amplitude,
            "rms_amplitude_fs": quality.rms_amplitude,
            "clipping_fraction": quality.clipping_fraction,
            "voiced_fraction": quality.voiced_fraction,
            "active_fraction": quality.active_fraction,
            "warnings": quality.warnings,
        },
        features,
        {
            "target_sample_rate_hz": processed.sample_rate,
            "original_sample_rate_hz": processed.original_sample_rate,
            "dc_offset_removed_fs": processed.dc_offset_removed,
            "trim_start_seconds": processed.trim_start_seconds,
            "trimmed_tail_seconds": processed.trimmed_tail_seconds,
            "retained_duration_seconds": processed.retained_duration_seconds,
            "resampled": processed.resampled,
        },
        model_status=(
            "Unavailable for this recording: recording-domain compatibility and clinical "
            "validation are not established."
        ),
    )
    st.session_state["voxneuro_html_report"] = render_voice_report_html(
        st.session_state["voxneuro_report"],
        processed_samples=processed.samples,
        sample_rate=processed.sample_rate,
    )
    st.session_state["voxneuro_analysis_status"] = "complete"


def _page_heading(
    title: str,
    description: str,
    kicker: str = "VOXNEURO · LOCAL RESEARCH PROTOTYPE",
) -> None:
    st.markdown(f'<div class="vox-kicker">{html.escape(kicker)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="vox-lede">{html.escape(description)}</p>', unsafe_allow_html=True)


def _show_overview() -> None:
    _page_heading(
        "VoxNeuro",
        "A careful research workspace for recording or reviewing a sustained vowel, "
        "checking signal quality, and exploring acoustic measurements in Parkinson’s research.",
        kicker="VOICE SIGNAL ANALYSIS · RESEARCH SOFTWARE",
    )
    st.markdown(
        '<div class="vox-glass-hero">'
        '<p class="vox-lede" style="margin-top:0;">'
        "A careful research workspace for recording or reviewing a sustained vowel, "
        "checking signal quality, and exploring acoustic measurements in Parkinson’s research."
        "</p></div>",
        unsafe_allow_html=True,
    )
    st.button(
        "Start a voice assessment",
        type="primary",
        on_click=lambda: st.session_state.__setitem__("voxneuro_nav", "Voice assessment"),
        key="start_assessment",
    )
    render_acoustic_view(decorative_hero_payload(), height=340)
    st.caption(
        "Decorative acoustic field · no participant recording is represented in this illustration."
    )
    st.markdown(
        """
        <hr class="vox-rule">
        <div class="vox-status">Local session · no recording saved by default</div>
        <p class="vox-note">VoxNeuro analyzes voice signals. It does not diagnose or rule out
        Parkinson’s disease, and it does not classify new microphone recordings.</p>
        """,
        unsafe_allow_html=True,
    )
    st.subheader("A clear, three-step workflow")
    steps = st.columns(3)
    for column, number, label, explanation in zip(
        steps,
        ("01", "02", "03"),
        ("Record", "Check", "Measure"),
        (
            "Capture or upload a short sustained vowel.",
            "Review duration, level, clipping, and voiced frames.",
            "Explore signal plots and versioned acoustic features.",
        ),
        strict=True,
    ):
        with column:
            st.markdown(
                f'<div class="vox-glass-card" style="height:100%;">'
                f'<div class="vox-step"><strong>{number}</strong>{label}</div>'
                f'<p style="margin-top:0.4rem; color:#A7B8B5; font-size:0.9rem;">{explanation}</p>'
                "</div>",
                unsafe_allow_html=True,
            )
    st.subheader("What the current prototype can support")
    left, right = st.columns([1.2, 1])
    with left:
        st.markdown(
            '<div class="vox-glass-card">'
            '<p style="margin:0; line-height:1.6; color:#EDF6F7;">'
            "The application checks a WAV recording, trims leading and trailing silence, "
            "resamples the usable segment, and extracts Praat/Parselmouth and Librosa measures. "
            "Reports remain in the current session unless the user downloads them."
            "</p></div>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            '<div class="vox-glass-card">'
            '<p class="vox-note" style="margin:0;">'
            "Technical quality passing means the signal can be analyzed. "
            "It says nothing about a person’s health."
            "</p></div>",
            unsafe_allow_html=True,
        )


def _show_assessment() -> None:
    _page_heading(
        "Voice assessment",
        "Record or upload one sustained vowel. Review technical quality before "
        "exploring measurements.",
    )
    st.info(
        "Task: hold “ah” (/a/) steadily for about 3–5 seconds. Sit comfortably in a quiet room "
        "and keep the microphone at a steady distance. This duration is guidance, not a diagnostic "
        "threshold."
    )
    st.caption(
        "The workflow returns signal quality and acoustic measurements only. No disease "
        "classification is available for this recording."
    )
    source = st.radio(
        "Audio source",
        ["Record with microphone", "Upload WAV"],
        horizontal=True,
        key="voxneuro_audio_source",
        on_change=_clear_assessment,
    )
    if source == "Record with microphone":
        uploaded = st.audio_input(
            "Record sustained vowel /a/",
            sample_rate=16000,
            key="voxneuro_audio_input",
            on_change=_clear_assessment,
        )
        if uploaded is None:
            st.caption("If the browser blocks microphone access, choose Upload WAV instead.")
    else:
        uploaded = st.file_uploader(
            "Choose a WAV file",
            type=["wav"],
            key="voxneuro_upload",
            on_change=_clear_assessment,
            help=f"Maximum file size: {int(APP_CONFIG['max_upload_mb'])} MB.",
        )
    if uploaded is not None:
        max_bytes = int(APP_CONFIG["max_upload_mb"]) * 1024 * 1024
        upload_size = getattr(uploaded, "size", None)
        if upload_size is not None and upload_size > max_bytes:
            st.error(f"Uploaded audio exceeds the {int(APP_CONFIG['max_upload_mb'])} MB limit.")
            return
        payload = uploaded.getvalue()
        if len(payload) > max_bytes:
            st.error(f"Audio exceeds the {int(APP_CONFIG['max_upload_mb'])} MB limit.")
            return
        st.audio(payload, format="audio/wav")
        if st.button("Analyze this recording", type="primary", key="analyze_recording"):
            try:
                with st.spinner("Checking signal quality and extracting measurements…"):
                    _analyze(payload)
            except (
                AudioReadError,
                AudioValidationError,
                FeatureExtractionError,
                VoxNeuroError,
                OSError,
                ValueError,
            ) as exc:
                st.session_state["voxneuro_analysis_status"] = "failed"
                st.session_state["voxneuro_analysis_error"] = str(exc)
            except Exception as exc:
                st.session_state["voxneuro_analysis_status"] = "failed"
                st.session_state["voxneuro_analysis_error"] = f"Unexpected processing error: {exc}"
    quality = st.session_state.get("voxneuro_quality")
    record = st.session_state.get("voxneuro_record")
    status = st.session_state.get("voxneuro_analysis_status")
    if quality is not None and record is not None:
        st.subheader("Signal quality")
        if quality.valid:
            st.success("Technical quality checks passed. This is not a health assessment.")
            summary = st.columns(4)
            summary[0].metric("Duration", f"{quality.duration_seconds:.2f} s")
            summary[1].metric("Sample rate", f"{record.sample_rate:,} Hz")
            summary[2].metric("Channels", str(record.channels))
            summary[3].metric("Voiced frames", f"{quality.voiced_fraction:.0%}")
            for warning in quality.warnings:
                st.warning(warning)
            if status == "complete":
                st.success("Acoustic analysis complete.")
            elif status == "failed":
                st.error("Quality passed, but feature analysis did not complete.")
                st.write(
                    st.session_state.get("voxneuro_analysis_error", "Please retry the recording.")
                )
            elif status == "processing":
                st.info("Analysis is in progress.")
            else:
                st.info("Quality passed. Run analysis to calculate the acoustic measurements.")
        else:
            st.error("Recording not analyzed because it did not pass technical quality checks.")
            for error in quality.errors:
                st.write(f"- {error}")
    elif status == "failed":
        st.error(
            st.session_state.get("voxneuro_analysis_error", "The recording could not be analyzed.")
        )
    if uploaded is not None and st.session_state.get("voxneuro_features") is not None:
        st.caption(
            f"Feature schema {SCHEMA_VERSION} · measurements are descriptive "
            "and not disease-specific."
        )
        report_columns = st.columns(2)
        report_columns[0].download_button(
            "Download readable HTML report",
            st.session_state["voxneuro_html_report"],
            "voxneuro_voice_analysis.html",
            "text/html",
            key="assessment_html_report_download",
        )
        report_columns[1].download_button(
            "Download JSON data",
            json.dumps(st.session_state["voxneuro_report"], indent=2, allow_nan=False),
            "voxneuro_report.json",
            "application/json",
            key="assessment_report_download",
        )
        st.button("Clear analysis results", on_click=_clear_assessment, key="clear_analysis")


def _show_signal_analysis() -> None:
    _page_heading(
        "Signal analysis",
        "Inspect the decoded recording and its processed version. Plots describe "
        "the waveform, not a diagnosis.",
    )
    record = st.session_state.get("voxneuro_record")
    processed = st.session_state.get("voxneuro_processed")
    if record is None:
        st.info("Record or upload a WAV on the Voice assessment page to populate this view.")
        return
    original = record.samples.mean(axis=1)
    stats = st.columns(4)
    stats[0].metric("Original duration", f"{record.duration_seconds:.2f} s")
    stats[1].metric("Input rate", f"{record.sample_rate:,} Hz")
    stats[2].metric("Channels", str(record.channels))
    stats[3].metric("Encoding", record.subtype)
    payload = st.session_state.get("voxneuro_payload")
    if payload:
        st.audio(payload, format="audio/wav")
    st.subheader("Original waveform")
    st.pyplot(waveform_figure(original, record.sample_rate, "Original waveform"), clear_figure=True)
    if processed is None:
        st.warning(
            "No processed waveform is available because the audio workflow did not complete."
        )
        return
    st.subheader("Interactive 3D signal views")
    visual_mode = st.radio(
        "3D visualization",
        ["Waveform", "Spectrogram"],
        horizontal=True,
        key="signal_3d_mode",
    )
    if visual_mode == "Waveform":
        waveform_duration = len(processed.samples) / processed.sample_rate
        detail_duration = min(0.5, waveform_duration)
        maximum_start = max(0.0, waveform_duration - detail_duration)
        if maximum_start > 0:
            detail_start = st.slider(
                "3D waveform detail start (s)",
                min_value=0.0,
                max_value=maximum_start,
                value=0.0,
                step=min(0.05, maximum_start),
                help=(
                    "Move the 0.5-second 3D view through the processed waveform. "
                    "The plots below show the full recording."
                ),
            )
        else:
            detail_start = 0.0
        first_sample = round(detail_start * processed.sample_rate)
        last_sample = min(
            len(processed.samples),
            first_sample + round(detail_duration * processed.sample_rate),
        )
        render_acoustic_view(
            waveform_payload(processed.samples[first_sample:last_sample], processed.sample_rate),
            height=440,
        )
        st.caption(
            f"The 3D waveform shows actual processed samples from {detail_start:.2f} to "
            f"{detail_start + detail_duration:.2f} seconds. Use the slider to move the detail "
            "window; the plots below show the full recording. Display depth is only a viewing axis."
        )
    else:
        render_acoustic_view(
            spectrogram_payload(
                processed.samples,
                processed.sample_rate,
                maximum_frequency_hz=float(FEATURE_CONFIG["common_max_hz"]),
                window_samples=int(FEATURE_CONFIG["fft_window_samples"]),
                hop_samples=int(FEATURE_CONFIG["hop_samples"]),
            ),
            height=500,
        )
        st.caption(
            "The surface uses a Hann-window STFT: height and color show 20 log10 of magnitude "
            "relative to amplitude 1.0 (dB re 1.0), on a fixed −90 to 0 dB display scale. "
            "It is not calibrated sound pressure level."
        )
    st.markdown('<hr class="vox-rule">', unsafe_allow_html=True)
    st.subheader("Processed signal")
    st.audio(processed.samples, sample_rate=processed.sample_rate)
    st.pyplot(
        waveform_figure(processed.samples, processed.sample_rate, "Processed waveform"),
        clear_figure=True,
    )
    st.pyplot(spectrogram_figure(processed.samples, processed.sample_rate), clear_figure=True)
    st.caption(
        "The spectrogram uses a linear frequency axis and relative dB magnitude; it is not "
        "calibrated sound pressure level. Visualizations do not enter the model pipeline."
    )
    st.subheader("Processing record")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "setting": "Retained duration",
                    "value": f"{processed.retained_duration_seconds:.3f} s",
                },
                {"setting": "Output sample rate", "value": f"{processed.sample_rate:,} Hz"},
                {"setting": "Start trim", "value": f"{processed.trim_start_seconds:.3f} s"},
                {"setting": "Tail trim", "value": f"{processed.trimmed_tail_seconds:.3f} s"},
                {"setting": "Removed DC offset", "value": f"{processed.dc_offset_removed:.6f} FS"},
                {"setting": "Resampled", "value": "Yes" if processed.resampled else "No"},
            ]
        ),
        width="stretch",
        hide_index=True,
    )


def _feature_group(name: str) -> str:
    if name.startswith("f0_"):
        return "Pitch"
    if name in {"jitter_local", "shimmer_local", "hnr_mean_db"}:
        return "Voice stability"
    if name.startswith("mfcc_"):
        return "MFCC"
    return "Spectral"


def _format_measurement(val: object) -> str:
    if val is None or not isinstance(val, Real) or not np.isfinite(float(val)):
        return "—"
    v = float(val)
    if abs(v) >= 100:
        return f"{v:,.2f}"
    if abs(v) >= 1:
        return f"{v:.4f}"
    if abs(v) >= 0.0001:
        return f"{v:.5f}"
    if v == 0.0:
        return "0.00"
    return f"{v:.4e}"


def _render_glass_table(df: pd.DataFrame) -> None:
    rows_html = []
    for _, row in df.iterrows():
        feat = html.escape(str(row["feature"]))
        val_str = html.escape(_format_measurement(row["measurement"]))
        units = html.escape(str(row["units"])) if row["units"] else ""
        method = html.escape(str(row["method and interpretation"]))
        avail = str(row["availability"])
        status_html = (
            '<span class="vox-badge-ok">Available</span>'
            if avail == "Available"
            else '<span class="vox-badge-na">Undefined</span>'
        )
        rows_html.append(
            "<tr>"
            f'<td><span class="vox-code-pill">{feat}</span></td>'
            f'<td class="vox-val-num">{val_str}</td>'
            f'<td><span class="vox-unit-pill">{units}</span></td>'
            f"<td>{method}</td>"
            f"<td>{status_html}</td>"
            "</tr>"
        )
    html_markup = (
        '<div class="vox-table-wrapper">'
        '<table class="vox-table">'
        "<thead><tr>"
        "<th>Feature</th>"
        "<th>Measurement</th>"
        "<th>Units</th>"
        "<th>Method &amp; Interpretation</th>"
        "<th>Status</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table></div>"
    )
    st.markdown(html_markup, unsafe_allow_html=True)


def _render_quality_cards(quality: dict) -> None:
    valid = bool(quality.get("valid", False))
    status_label = "PASSED" if valid else "FLAGGED"
    status_badge = (
        '<span class="vox-badge-ok">VALID SIGNAL</span>'
        if valid
        else '<span class="vox-badge-na">ISSUES DETECTED</span>'
    )
    duration = float(quality.get("duration_seconds", 0.0))
    sample_rate = int(quality.get("sample_rate_hz", 0))
    channels = int(quality.get("channels", 1))
    channel_text = "Mono" if channels == 1 else f"{channels}-ch stereo"
    voiced = float(quality.get("voiced_fraction", 0.0))
    peak = float(quality.get("peak_amplitude_fs", 0.0))
    rms = float(quality.get("rms_amplitude_fs", 0.0))
    clipping = float(quality.get("clipping_fraction", 0.0))
    subtype = str(quality.get("subtype", "PCM_16"))

    min_dur = float(AUDIO_CONFIG.get("min_duration_seconds", 1.0))
    max_dur = float(AUDIO_CONFIG.get("max_duration_seconds", 30.0))
    clipping_limit = float(AUDIO_CONFIG.get("clipping_fraction_limit", 0.01))

    html_markup = (
        '<div class="vox-quality-grid">'
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Technical Check</div>'
        f'<div class="vox-qc-value">{status_label}</div>'
        f'<div class="vox-qc-sub">{status_badge}</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Signal Duration</div>'
        f'<div class="vox-qc-value">{duration:.2f} s</div>'
        f'<div class="vox-qc-sub">Target: {min_dur:.1f} – {max_dur:.1f} s</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Sample Rate</div>'
        f'<div class="vox-qc-value">{sample_rate:,} Hz</div>'
        f'<div class="vox-qc-sub">{html.escape(subtype)} · {channel_text}</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Voiced Activity</div>'
        f'<div class="vox-qc-value">{voiced:.1%}</div>'
        '<div class="vox-qc-sub">Voiced phonation frames</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Peak Amplitude</div>'
        f'<div class="vox-qc-value">{peak:.3f} FS</div>'
        f'<div class="vox-qc-sub">RMS: {rms:.3f} FS</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Clipping Rate</div>'
        f'<div class="vox-qc-value">{clipping:.4%}</div>'
        f'<div class="vox-qc-sub">Limit: ≤ {clipping_limit:.2%}</div>'
        "</div>"
        "</div>"
    )
    st.markdown(html_markup, unsafe_allow_html=True)
    with st.expander("Telemetry & raw quality metadata (JSON)", expanded=False):
        st.json(quality)


def _feature_frame(features: dict) -> pd.DataFrame:
    rows = []
    for definition in FEATURE_DEFINITIONS:
        value = features[definition.name]
        available = isinstance(value, Real) and np.isfinite(float(value))
        rows.append(
            {
                "measurement": float(value) if available else None,
                "units": definition.units,
                "feature": definition.name,
                "method and interpretation": definition.method,
                "availability": "Available" if available else "Undefined for this recording",
                "schema_version": features["schema_version"],
                "schema_fingerprint": features["schema_fingerprint"],
                "feature_config_fingerprint": features["feature_config_fingerprint"],
                "preprocessing_config_fingerprint": features["preprocessing_config_fingerprint"],
            }
        )
    return pd.DataFrame(rows)


def _show_features() -> None:
    _page_heading(
        "Acoustic features",
        "Review the 39 versioned measurements grouped by what they describe. "
        "No reference range or normal/abnormal label is assigned.",
    )
    features = st.session_state.get("voxneuro_features")
    if features is None:
        st.info("Complete a successful voice analysis first.")
        if st.session_state.get("voxneuro_analysis_status") == "failed":
            st.error("Feature extraction did not complete for the current recording.")
        return
    st.caption(
        f"Schema: {features['schema_version']} · schema fingerprint: "
        f"{features['schema_fingerprint'][:16]}… · feature settings: "
        f"{features['feature_config_fingerprint'][:16]}…"
    )
    table = _feature_frame(features)
    groups = ("Pitch", "Voice stability", "MFCC", "Spectral")
    tabs = st.tabs(groups)
    for tab, group in zip(tabs, groups, strict=True):
        with tab:
            subset = table.loc[table["feature"].map(_feature_group).eq(group)]
            _render_glass_table(subset)
            with st.expander(
                f"Interactive data grid ({group} · filter, sort & export)", expanded=False
            ):
                st.dataframe(subset, width="stretch", hide_index=True)
    st.caption(
        "Undefined jitter and shimmer remain missing instead of being replaced with zero. "
        "Units and extraction methods are listed with each measure."
    )
    st.download_button(
        "Download feature table (CSV)",
        table.to_csv(index=False),
        "voxneuro_features.csv",
        "text/csv",
        key="feature_csv_download",
    )


def _evaluation_inputs() -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict | None, list[str]]:
    processed = PROJECT_ROOT / "data" / "processed"
    manifest_path = processed / "feature_manifest.csv"
    feature_path = processed / "voice_features.csv"
    metrics_path = processed / "model_metrics.csv"
    predictions_path = processed / "model_oof_predictions.csv"
    receipt_path = processed / "model_evaluation_receipt.json"
    if not all(
        path.is_file()
        for path in (manifest_path, feature_path, metrics_path, predictions_path, receipt_path)
    ):
        return None, None, None, ["No complete current grouped-evaluation package is available."]
    audio_config = AUDIO_CONFIG
    feature_config = FEATURE_CONFIG
    issues = validate_evaluation_receipt(
        receipt_path,
        manifest_path,
        feature_path,
        metrics_path,
        SCHEMA_VERSION,
        project_code_fingerprint(),
        schema_fingerprint(),
        feature_config_fingerprint(feature_config),
        configuration_fingerprint(audio_config),
        predictions_path,
    )
    if issues:
        return None, None, None, issues
    try:
        manifest = pd.read_csv(manifest_path)
        feature_table = pd.read_csv(feature_path)
        metrics = pd.read_csv(metrics_path)
        predictions = pd.read_csv(predictions_path)
        receipt = read_json_object(receipt_path, "Model evaluation receipt")
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        return None, None, None, [f"Evaluation files could not be read: {exc}"]
    manifest_issues = validate_manifest(manifest, require_integrity=True)
    feature_issues = validate_features(feature_table, FEATURE_NAMES)
    if manifest_issues or feature_issues:
        return None, None, None, [*manifest_issues, *feature_issues]
    if (
        feature_table["sample_id"].duplicated().any()
        or not feature_table["class_label"].isin(["PD", "HC"]).all()
        or not set(feature_table["sample_id"]).issubset(set(manifest["sample_id"]))
    ):
        return (
            None,
            None,
            None,
            ["Feature table identities or labels are inconsistent with the current manifest."],
        )
    required_metrics = {"model", "fold", "balanced_accuracy", "sensitivity", "specificity"}
    if not required_metrics.issubset(metrics.columns) or metrics.empty:
        return (
            None,
            None,
            None,
            ["Evaluation metrics do not match the expected grouped-fold schema."],
        )
    required_predictions = {"model", "participant_id", "y_true", "y_pred", "score"}
    if not required_predictions.issubset(predictions.columns) or predictions.empty:
        return None, None, None, ["Out-of-fold predictions do not match the expected schema."]
    return manifest, feature_table, (receipt, metrics, predictions), []


def _current_nested_evaluation_html() -> str | None:
    processed = PROJECT_ROOT / "data" / "processed"
    manifest_path = processed / "feature_manifest.csv"
    feature_path = processed / "voice_features.csv"
    receipt_path = processed / "nested_uams_evaluation_receipt.json"
    metrics_path = processed / "nested_uams_metrics.csv"
    predictions_path = processed / "nested_uams_oof_predictions.csv"
    summary_path = processed / "nested_uams_summary.csv"
    report_path = PROJECT_ROOT / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html"
    if not manifest_path.is_file() or not feature_path.is_file():
        return None
    expected = {
        "status": "complete",
        "dataset": "uams",
        "code_version": project_code_fingerprint(),
        "feature_schema_version": SCHEMA_VERSION,
        "feature_schema_fingerprint": schema_fingerprint(),
        "feature_config_fingerprint": feature_config_fingerprint(FEATURE_CONFIG),
        "preprocessing_config_fingerprint": configuration_fingerprint(AUDIO_CONFIG),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "feature_table_sha256": hashlib.sha256(feature_path.read_bytes()).hexdigest(),
    }
    issues = validate_nested_evaluation_receipt(
        receipt_path,
        expected,
        {
            "metrics_sha256": metrics_path,
            "predictions_sha256": predictions_path,
            "summary_sha256": summary_path,
            "report_sha256": report_path,
        },
    )
    if issues:
        return None
    try:
        return report_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _model_comparison_figure(metrics: pd.DataFrame):
    grouped = metrics.groupby("model")["balanced_accuracy"].agg(["mean", "std"]).sort_values("mean")
    colors = [
        "#A96F22" if "age" in model else "#68746F" if model == "dummy" else "#176B5B"
        for model in grouped.index
    ]
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    ax.barh(
        grouped.index,
        grouped["mean"],
        xerr=grouped["std"].fillna(0),
        color=colors,
        alpha=0.9,
        capsize=3,
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel("Balanced accuracy · mean ± SD across grouped folds")
    ax.set_title("Internal UAMS comparison")
    ax.grid(axis="x", color="#DCE3DE", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#C8D2CB")
    ax.tick_params(axis="y", length=0, labelcolor="#1B2724")
    ax.tick_params(axis="x", colors="#68746F")
    fig.tight_layout()
    return fig


def _out_of_fold_confusion_figure(predictions: pd.DataFrame):
    selected = predictions.loc[predictions["model"].eq("logistic_regression")]
    matrix = confusion_matrix(
        selected["y_true"].astype(int),
        selected["y_pred"].astype(int),
        labels=[0, 1],
    )
    fig, ax = plt.subplots(figsize=(4.3, 3.4))
    image = ax.imshow(matrix, cmap="Greens", vmin=0)
    for (row, column), value in np.ndenumerate(matrix):
        ax.text(column, row, str(value), ha="center", va="center", color="#1B2724", fontsize=12)
    ax.set_xticks([0, 1], labels=["HC", "PD"])
    ax.set_yticks([0, 1], labels=["HC", "PD"])
    ax.set_xlabel("Predicted group")
    ax.set_ylabel("Reference group")
    ax.set_title("Logistic regression · pooled held-out participants")
    fig.colorbar(image, ax=ax, label="Participants")
    fig.tight_layout()
    return fig


def _out_of_fold_roc_figure(predictions: pd.DataFrame):
    selected = predictions.loc[predictions["model"].eq("logistic_regression")]
    y_true = selected["y_true"].astype(int).to_numpy()
    score = selected["score"].to_numpy(dtype=float)
    if len(np.unique(y_true)) != 2 or not np.isfinite(score).all():
        return None
    false_positive, true_positive, _ = roc_curve(y_true, score)
    auc = roc_auc_score(y_true, score)
    fig, ax = plt.subplots(figsize=(4.3, 3.4))
    ax.plot(false_positive, true_positive, color="#176B5B", linewidth=2, label=f"ROC AUC {auc:.3f}")
    ax.plot([0, 1], [0, 1], color="#A8B2AC", linewidth=1, linestyle="--")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Pooled out-of-fold ranking")
    ax.legend(frameon=False, loc="lower right")
    ax.grid(color="#DCE3DE", linewidth=0.7)
    ax.set_axisbelow(True)
    fig.tight_layout()
    return fig


def _show_model_assessment() -> None:
    _page_heading(
        "Research model",
        "A transparent view of grouped internal experiments. This page never "
        "predicts a result for the current recording.",
    )
    st.warning(
        "Research only. No patient-level classification is available. The UAMS cohort uses "
        "telephone-collected voices; compatibility with laptop or smartphone microphones has "
        "not been established."
    )
    st.write(
        "All recordings from one participant stay in the same cross-validation fold. Scores are "
        "internal estimates, not clinical probabilities or independent external validation."
    )
    st.caption(
        "The UAMS comparison reports age-only, voice-only, and age-plus-voice logistic baselines "
        "on the same participant folds. The combined model is an exploratory confounding check; "
        "it cannot establish that voice adds disease-specific or clinically useful information."
    )
    manifest, feature_table, package, issues = _evaluation_inputs()
    if issues:
        st.info(
            "Current evaluation results are unavailable because their receipt is missing, stale, "
            "or incompatible. Run the documented extraction and grouped-evaluation workflow."
        )
        return
    receipt, metrics, predictions = package
    st.caption(
        f"Dataset: UAMS · {feature_table['participant_id'].nunique()} participants · "
        f"{len(feature_table)} analyzed recordings · {receipt.get('cross_validation_splits')} "
        f"grouped folds · schema {receipt.get('feature_schema_version')} · "
        f"run {receipt.get('created_utc')}"
    )
    st.pyplot(_model_comparison_figure(metrics), clear_figure=True)
    st.caption(
        "Error bars show the standard deviation across folds, not a confidence interval. "
        "Age and recording quality can confound these small-cohort estimates."
    )
    st.subheader("Held-out participant detail")
    matrix_col, roc_col = st.columns(2)
    with matrix_col:
        st.pyplot(_out_of_fold_confusion_figure(predictions), clear_figure=True)
    with roc_col:
        roc_figure = _out_of_fold_roc_figure(predictions)
        if roc_figure is not None:
            st.pyplot(roc_figure, clear_figure=True)
        else:
            st.info("ROC curve is unavailable because both labels and finite scores are required.")
    st.caption(
        "These summaries pool grouped out-of-fold participant predictions. The logistic "
        "regression threshold and score are exploratory; no clinical threshold is selected."
    )
    nested_report = _current_nested_evaluation_html()
    if nested_report is not None:
        st.download_button(
            "Download repeated nested-CV HTML comparison",
            nested_report,
            "voxneuro_uams_nested_evaluation.html",
            "text/html",
            key="nested_model_report_download",
        )
    model_col, cohort_col = st.columns([1.25, 1])
    with model_col:
        st.subheader("Fold-wise results")
        st.dataframe(metrics, width="stretch", hide_index=True)
    with cohort_col:
        st.subheader("Analyzed cohort")
        composition = (
            feature_table.groupby("class_label")
            .agg(recordings=("sample_id", "count"), participants=("participant_id", "nunique"))
            .reset_index()
            .rename(columns={"class_label": "group"})
        )
        st.dataframe(composition, width="stretch", hide_index=True)
        analyzed_ids = set(feature_table["sample_id"])
        excluded = manifest.loc[~manifest["sample_id"].isin(analyzed_ids)]
        excluded_counts = excluded["class_label"].value_counts().to_dict()
        exclusion_summary = (
            ", ".join(f"{count} {label}" for label, count in sorted(excluded_counts.items()))
            or "none"
        )
        st.write(
            f"Excluded from feature extraction: {exclusion_summary}. "
            "The exclusions are listed in the local extraction report. "
            "The age-only comparator is shown because this cohort has a marked age imbalance."
        )
    st.warning(DISCLAIMER)


def _show_reports() -> None:
    _page_heading(
        "Reports",
        "Download the measurements created in this session. Reports omit "
        "filenames, paths, and diagnostic conclusions.",
    )
    report = st.session_state.get("voxneuro_report")
    features = st.session_state.get("voxneuro_features")
    if report is None or features is None:
        st.info("Complete a successful analysis to create a session report.")
        return
    st.caption(
        f"Report {report['report_version']} · generated {report['generated_utc']} · "
        f"feature schema {report['features']['schema_version']}"
    )
    st.subheader("Audio quality")
    _render_quality_cards(report["audio_quality"])
    st.subheader("Feature measurements")
    table = _feature_frame(features)
    _render_glass_table(table)
    with st.expander("Full provenance data grid (interactive filter & export)", expanded=False):
        st.dataframe(table, width="stretch", hide_index=True)
    st.warning(DISCLAIMER)
    html_column, json_column, csv_column = st.columns(3)
    with html_column:
        st.download_button(
            "Download HTML report",
            st.session_state.get("voxneuro_html_report", ""),
            "voxneuro_voice_analysis.html",
            "text/html",
            key="report_html_download",
        )
    with json_column:
        st.download_button(
            "Download JSON data",
            json.dumps(report, indent=2, allow_nan=False),
            "voxneuro_report.json",
            "application/json",
            key="report_download",
        )
    with csv_column:
        st.download_button(
            "Download feature table (CSV)",
            table.to_csv(index=False),
            "voxneuro_features.csv",
            "text/csv",
            key="report_csv_download",
        )


def _show_method_privacy() -> None:
    _page_heading(
        "Method and privacy",
        "What is measured, how the recording is handled, and what the current "
        "evidence does not establish.",
    )
    st.subheader("Processing sequence")
    st.markdown(
        """
        1. Decode the WAV and read its actual sample rate, channel count, duration, and encoding.
        2. Check finite samples, duration, amplitude, clipping, voiced frames, and stereo phase.
        3. Average supported stereo channels after quality checks, remove DC offset, trim silence,
           verify the retained signal, and polyphase-resample to the configured rate.
        4. Extract 39 Praat/Parselmouth and Librosa measurements under the versioned feature schema.
        5. Keep undefined values missing and create a JSON report for this session.
        """
    )
    audio_config = AUDIO_CONFIG
    feature_config = FEATURE_CONFIG
    st.subheader("Current extraction settings")
    st.dataframe(
        pd.DataFrame(
            [{"setting": key, "value": str(value)} for key, value in audio_config.items()]
            + [{"setting": key, "value": str(value)} for key, value in feature_config.items()]
        ),
        width="stretch",
        hide_index=True,
    )
    st.subheader("Privacy boundary")
    st.write(
        "The server binds to 127.0.0.1 by default. Audio and analysis results stay in the active "
        "Streamlit session; the application does not write recordings or reports to disk, and it "
        "does not send audio to a remote analysis service. Downloaded reports are saved only when "
        "you choose a download."
    )
    st.write(
        "Voice audio can identify a person. Analyze only recordings you have permission to use. "
        "Avoid identifying names in filenames or report context. Browser microphone permission is "
        "required for recording; use WAV upload when the browser denies access."
    )
    st.subheader("Limits")
    st.warning(DISCLAIMER)
    st.write(
        "The project currently studies Parkinson’s disease versus healthy controls. It does not "
        "detect other neurological conditions, establish a clinical need, or demonstrate safety "
        "or effectiveness in care. See the clinical validation plan, risk assessment, and "
        "regulatory review before proposing a clinical use."
    )


def main() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="vox-wordmark"><span class="vox-wave" aria-hidden="true">'
            "<i></i><i></i><i></i><i></i><i></i><i></i><i></i>"
            "</span>VoxNeuro</div>",
            unsafe_allow_html=True,
        )
        st.caption("VOICE SIGNAL RESEARCH")
        pages = [
            "Overview",
            "Voice assessment",
            "Signal analysis",
            "Feature analysis",
            "Research model",
            "Reports",
            "Method & privacy",
        ]
        page = st.radio("Workspace", pages, key="voxneuro_nav", label_visibility="collapsed")
        st.markdown('<hr class="vox-rule">', unsafe_allow_html=True)
        st.markdown('<div class="vox-status">Local session</div>', unsafe_allow_html=True)
        st.caption("Parkinson’s research prototype · No diagnosis")
        st.caption("Audio is not saved by default.")
    if page == "Overview":
        _show_overview()
    elif page == "Voice assessment":
        _show_assessment()
    elif page == "Signal analysis":
        _show_signal_analysis()
    elif page == "Feature analysis":
        _show_features()
    elif page == "Research model":
        _show_model_assessment()
    elif page == "Reports":
        _show_reports()
    else:
        _show_method_privacy()


main()
