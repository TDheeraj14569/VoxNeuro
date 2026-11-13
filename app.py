"""Streamlit interface for private, local voice signal analysis."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import uuid
from numbers import Real
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve

from voxneuro.audio.io import decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.task_preprocessing import preprocess_task_audio
from voxneuro.audio.validation import AudioQuality, AudioValidationConfig, validate_audio
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
from voxneuro.features.tasks.connected_speech import extract_connected_speech_features
from voxneuro.features.tasks.ddk import extract_ddk_features
from voxneuro.features.tasks.pipeline import (
    MultiTaskSessionResult,
    analyze_multitask_session,
)
from voxneuro.features.tasks.vowel_space import extract_vowel_space_features
from voxneuro.logging_config import configure_logging
from voxneuro.modeling.prediction_service import PredictionResult
from voxneuro.provenance import project_code_fingerprint
from voxneuro.reporting.html_report import render_voice_report_html
from voxneuro.reporting.multitask_report import render_multitask_report_html
from voxneuro.reporting.report import DISCLAIMER, build_report
from voxneuro.study.audit import list_audit_events
from voxneuro.study.auth import resolve_session_user
from voxneuro.study.consent import (
    list_dataset_access,
    record_consent,
    register_dataset_access,
)
from voxneuro.study.database import (
    get_connection,
    run_migrations,
)
from voxneuro.study.longitudinal import calculate_longitudinal_feature_changes
from voxneuro.study.participant import list_participants, register_participant
from voxneuro.study.qc import (
    calculate_cohort_attrition,
    calculate_cohort_qc_metrics,
)
from voxneuro.study.registry import (
    create_protocol,
    create_study,
    list_protocols,
    list_studies,
)
from voxneuro.study.reporting import (
    RESEARCH_DISCLAIMER,
    export_report_to_csv,
    generate_cohort_attrition_report,
    generate_longitudinal_descriptive_report,
    generate_session_completion_report,
    generate_study_overview_report,
)
from voxneuro.study.schema import (
    ConsentRecord,
    DatasetAccessRecord,
    Participant,
    ProtocolDefinition,
    ResearchSession,
    Study,
    generate_pseudonymous_id,
    utc_now_iso,
)
from voxneuro.study.session import (
    create_session,
    ingest_session_multitask_audio,
    list_sessions,
    preflight_session_ingestion,
)
from voxneuro.study.withdrawal import withdraw_participant
from voxneuro.ui.admin_portals import (
    show_ml_admin_portal,
    show_researcher_portal,
    show_system_admin_portal,
)
from voxneuro.ui.consumer_pages import (
    WIZARD_STEPS,
    build_session_prediction,
    show_about_page,
    show_account_portal,
    show_consumer_home,
    show_guided_consent_step,
    show_help_faq,
    show_how_it_works,
    show_plain_results_page,
    show_privacy_and_safety,
    show_user_dashboard,
    show_user_history_page,
)
from voxneuro.ui.theme import (
    M6_RESPONSIVE_CSS,
    render_brand_bar,
    render_medical_disclaimer,
    render_plain_quality_summary,
    render_prediction_outcome_card,
    render_stepper,
)
from voxneuro.visualization.acoustic_3d import (
    render_acoustic_view,
    spectrogram_payload,
    waveform_payload,
)
from voxneuro.visualization.spectrogram import spectrogram_figure
from voxneuro.visualization.waveform import waveform_figure

logger = logging.getLogger("voxneuro.app")

APP_CONFIG = load_config("application_config.yaml")
AUDIO_CONFIG = load_config("audio_config.yaml")
FEATURE_CONFIG = load_config("feature_config.yaml")
MODEL_CONFIG = load_config("model_config.yaml")
load_config("reviewed_exclusions.yaml")
if APP_CONFIG.get("store_recordings") or APP_CONFIG.get("store_reports_by_default"):
    raise RuntimeError("Persistent audio/report storage is not implemented in this prototype.")
configure_logging()
st.set_page_config(
    page_title="VoxNeuro · Voice Acoustic Analysis",
    page_icon="∿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_STYLE = """
<style>
:root {
  --vox-canvas: #F3F0E8;
  --vox-canvas-subtle: #EBE7DE;
  --vox-surface: #FBFAF6;
  --vox-surface-elevated: #FFFFFF;
  --vox-ink: #20232B;
  --vox-secondary: #676970;
  --vox-muted: #898982;
  --vox-border: #D8D3C8;
  --vox-border-subtle: #E8E4DA;
  --vox-vermilion: #B95E46;
  --vox-vermilion-hover: #A34F39;
  --vox-vermilion-tint: rgba(185, 94, 70, 0.08);
  --vox-aubergine: #51445D;
  --vox-aubergine-tint: rgba(81, 68, 93, 0.08);
  --vox-blue: #526A91;
  --vox-blue-tint: rgba(82, 106, 145, 0.09);
  --vox-olive: #788064;
  --vox-success: #39745A;
  --vox-warning: #A76F24;
  --vox-error: #A3423D;
  --vox-radius: 6px;
  --vox-shadow-sm: 0 1px 3px rgba(32, 35, 43, 0.05);
  --vox-shadow-md: 0 4px 14px rgba(32, 35, 43, 0.06);
}

/* Global resets & canvas */
.stApp {
  background-color: var(--vox-canvas) !important;
  color: var(--vox-ink) !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif !important;
  -webkit-font-smoothing: antialiased;
}

header[data-testid="stHeader"] {
  background: transparent !important;
}

main .block-container {
  max-width: 1220px;
  padding: 2.2rem 3rem 4rem;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
  background-color: var(--vox-canvas-subtle) !important;
  border-right: 1px solid var(--vox-border) !important;
}

section[data-testid="stSidebar"] .block-container {
  padding: 1.8rem 1.25rem 2rem;
}

/* Typography hierarchy */
h1, h2, h3 {
  font-family: "Newsreader", "Charter", "Georgia", "Cambria", serif !important;
  color: var(--vox-ink) !important;
  letter-spacing: -0.02em !important;
  font-weight: 650 !important;
}

h1 {
  font-size: 2.25rem !important;
  line-height: 1.2 !important;
  margin-bottom: 0.5rem !important;
}
h2 {
  font-size: 1.55rem !important;
  line-height: 1.25 !important;
  margin-top: 1.8rem !important;
  margin-bottom: 0.75rem !important;
}
h3 {
  font-size: 1.2rem !important;
  line-height: 1.3 !important;
  margin-top: 1.25rem !important;
  margin-bottom: 0.5rem !important;
}

p, li, label, .stApp p, .stApp li {
  color: var(--vox-ink);
  line-height: 1.6;
}

.stApp [data-testid="stCaptionContainer"] {
  color: var(--vox-secondary) !important;
  font-size: 0.82rem;
}

/* Brand Wordmark */
.vox-wordmark {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--vox-ink);
  font-family: "Newsreader", "Charter", "Georgia", serif;
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 0.2rem;
}

.vox-wave {
  display: inline-flex;
  align-items: center;
  gap: 2.5px;
  height: 22px;
  color: var(--vox-vermilion);
}

.vox-wave i {
  display: block;
  width: 2.5px;
  border-radius: 2px;
  background: currentColor;
}

.vox-wave i:nth-child(1), .vox-wave i:nth-child(7) { height: 6px; }
.vox-wave i:nth-child(2), .vox-wave i:nth-child(6) { height: 12px; }
.vox-wave i:nth-child(3), .vox-wave i:nth-child(5) { height: 17px; }
.vox-wave i:nth-child(4) { height: 22px; color: var(--vox-aubergine); }

.vox-kicker {
  color: var(--vox-vermilion);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin: 0 0 0.4rem 0;
}

.vox-lede {
  color: var(--vox-secondary);
  font-size: 1.06rem;
  max-width: 820px;
  line-height: 1.65;
  margin-bottom: 1.25rem;
}

.vox-rule {
  border: 0;
  border-top: 1px solid var(--vox-border);
  margin: 1.35rem 0;
}

.vox-status {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: var(--vox-success);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.vox-status::before {
  content: "";
  width: 7px;
  height: 7px;
  background: var(--vox-success);
  border-radius: 50%;
}

.vox-note {
  border-left: 3px solid var(--vox-vermilion);
  padding: 0.25rem 0 0.25rem 0.95rem;
  color: var(--vox-secondary);
  line-height: 1.6;
  font-size: 0.92rem;
}

/* Sidebar navigation styling */
section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
  gap: 0.45rem;
}

section[data-testid="stSidebar"] [data-testid="stRadio"] label {
  background: var(--vox-surface);
  border: 1px solid var(--vox-border);
  border-radius: var(--vox-radius);
  padding: 0.55rem 0.85rem;
  transition: all 0.18s ease;
  cursor: pointer;
  color: var(--vox-ink);
  font-size: 0.88rem;
  font-weight: 500;
}

section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background: var(--vox-surface-elevated);
  border-color: var(--vox-vermilion);
  color: var(--vox-vermilion);
  transform: translateX(2px);
}

section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"],
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
  background: var(--vox-surface-elevated);
  border-color: var(--vox-vermilion);
  border-left: 3.5px solid var(--vox-vermilion);
  color: var(--vox-vermilion);
  font-weight: 650;
  box-shadow: var(--vox-shadow-sm);
}

/* Streamlit Metric boxes */
div[data-testid="stMetric"] {
  background: var(--vox-surface-elevated) !important;
  border: 1px solid var(--vox-border) !important;
  border-radius: var(--vox-radius) !important;
  padding: 0.85rem 1.1rem !important;
  box-shadow: var(--vox-shadow-sm) !important;
}

div[data-testid="stMetric"] label {
  color: var(--vox-secondary) !important;
  font-size: 0.74rem !important;
  font-weight: 650 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
  color: var(--vox-ink) !important;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace !important;
  font-weight: 700 !important;
}

/* Editorial Hero & Feature Containers */
.vox-editorial-hero {
  background: var(--vox-surface-elevated);
  border: 1px solid var(--vox-border);
  border-left: 4px solid var(--vox-vermilion);
  border-radius: var(--vox-radius);
  padding: 1.5rem 1.75rem;
  margin-bottom: 1.35rem;
  box-shadow: var(--vox-shadow-sm);
}

.vox-editorial-card {
  background: var(--vox-surface-elevated);
  border: 1px solid var(--vox-border);
  border-radius: var(--vox-radius);
  padding: 1.25rem 1.4rem;
  margin-bottom: 1rem;
  box-shadow: var(--vox-shadow-sm);
}

.vox-step-num {
  font-family: "Newsreader", "Georgia", serif;
  font-size: 1.55rem;
  font-weight: 700;
  color: var(--vox-vermilion);
  line-height: 1;
  margin-bottom: 0.35rem;
}

/* Scientific Table System */
.vox-table-wrapper {
  border: 1px solid var(--vox-border);
  border-radius: var(--vox-radius);
  overflow-x: auto;
  background: var(--vox-surface-elevated);
  box-shadow: var(--vox-shadow-sm);
  margin: 0.85rem 0 1.25rem;
}

.vox-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
  color: var(--vox-ink);
  text-align: left;
}

.vox-table th {
  background: #EDE8DE;
  color: var(--vox-aubergine);
  padding: 0.75rem 1.15rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  border-bottom: 2px solid var(--vox-border);
  white-space: nowrap;
}

.vox-table td {
  padding: 0.75rem 1.15rem;
  border-bottom: 1px solid var(--vox-border-subtle);
  vertical-align: middle;
}

.vox-table tr:nth-child(even) { background: #FAF8F3; }
.vox-table tr:last-child td { border-bottom: 0; }
.vox-table tr:hover td {
  background: #F1ECE2 !important;
  transition: background 0.15s ease;
}

.vox-val-num {
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
  color: var(--vox-ink);
  font-weight: 600;
  white-space: nowrap;
}

.vox-code-pill {
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  background: #EFECE4;
  color: var(--vox-aubergine);
  border: 1px solid var(--vox-border);
  border-radius: 4px;
  padding: 0.15rem 0.45rem;
  font-size: 0.78rem;
  font-weight: 600;
  white-space: nowrap;
}

.vox-unit-pill {
  color: var(--vox-secondary);
  font-size: 0.78rem;
  font-style: italic;
}

.vox-badge-ok {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(57, 116, 90, 0.08);
  color: var(--vox-success);
  border: 1px solid rgba(57, 116, 90, 0.3);
  border-radius: 4px;
  padding: 0.15rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 650;
  white-space: nowrap;
}

.vox-badge-ok::before {
  content: "";
  width: 5px;
  height: 5px;
  background: var(--vox-success);
  border-radius: 50%;
}

.vox-badge-na {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(167, 111, 36, 0.08);
  color: var(--vox-warning);
  border: 1px solid rgba(167, 111, 36, 0.35);
  border-radius: 4px;
  padding: 0.15rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 650;
  white-space: nowrap;
}

/* Quality Telemetry Grid */
.vox-quality-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 0.75rem;
  margin: 0.85rem 0 1.15rem;
}

.vox-quality-card {
  background: var(--vox-surface-elevated);
  border: 1px solid var(--vox-border);
  border-radius: var(--vox-radius);
  padding: 0.85rem 1rem;
  box-shadow: var(--vox-shadow-sm);
  transition: transform 0.15s ease, border-color 0.15s ease;
}

.vox-quality-card:hover {
  transform: translateY(-1px);
  border-color: var(--vox-vermilion);
}

.vox-qc-label {
  color: var(--vox-secondary);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 0.3rem;
}

.vox-qc-value {
  color: var(--vox-ink);
  font-size: 1.25rem;
  font-weight: 700;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  margin-bottom: 0.2rem;
}

.vox-qc-sub {
  color: var(--vox-blue);
  font-size: 0.74rem;
  font-weight: 500;
}

.vox-json-card {
  background: var(--vox-surface);
  border: 1px solid var(--vox-border);
  border-radius: var(--vox-radius);
  padding: 1rem 1.25rem;
  overflow-x: auto;
  margin: 0.5rem 0 1rem;
}

.vox-json-card pre {
  margin: 0;
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.82rem;
  color: var(--vox-ink);
  line-height: 1.55;
  background: transparent !important;
}

/* Buttons Design System */
html body div.stApp button,
html body div.stApp button[kind="secondary"],
html body div.stApp a[kind="secondary"],
html body div.stApp a[role="button"],
html body div.stApp a[download],
html body div.stApp .stButton > button,
html body div.stApp .stDownloadButton > button,
html body div.stApp .stDownloadButton > a,
html body div.stApp [data-testid*="DownloadButton"] button,
html body div.stApp [data-testid*="DownloadButton"] a,
html body div.stApp [data-testid*="downloadButton"] button,
html body div.stApp [data-testid*="downloadButton"] a,
html body div.stApp [data-testid*="baseButton"],
html body div.stApp [data-testid*="BaseButton"],
html body div.stApp [data-testid*="stBaseButton"],
html body div.stApp div[data-testid="stDownloadButton"] button,
html body div.stApp div[data-testid="stDownloadButton"] a {
  background: var(--vox-surface-elevated) !important;
  background-color: var(--vox-surface-elevated) !important;
  color: var(--vox-ink) !important;
  border: 1px solid var(--vox-border) !important;
  border-radius: var(--vox-radius) !important;
  padding: 0.55rem 1.25rem !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.015em !important;
  box-shadow: var(--vox-shadow-sm) !important;
  transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1) !important;
  text-decoration: none !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 0.45rem !important;
}

html body div.stApp button *,
html body div.stApp a[kind="secondary"] *,
html body div.stApp a[role="button"] *,
html body div.stApp a[download] *,
html body div.stApp .stButton > button *,
html body div.stApp .stDownloadButton > button *,
html body div.stApp div[data-testid="stDownloadButton"] * {
  color: var(--vox-ink) !important;
}

html body div.stApp button:hover:not(:disabled),
html body div.stApp button:hover:enabled,
html body div.stApp a[kind="secondary"]:hover:not(:disabled),
html body div.stApp a[role="button"]:hover:not(:disabled),
html body div.stApp a[download]:hover:not(:disabled),
html body div.stApp [data-testid*="DownloadButton"] button:hover:not(:disabled),
html body div.stApp .stButton > button:hover:not(:disabled),
html body div.stApp .stDownloadButton > button:hover:not(:disabled),
html body div.stApp div[data-testid="stDownloadButton"] button:hover:not(:disabled) {
  background: #FAF8F3 !important;
  background-color: #FAF8F3 !important;
  border-color: var(--vox-vermilion) !important;
  color: var(--vox-vermilion) !important;
  box-shadow: var(--vox-shadow-md) !important;
  transform: translateY(-1px) !important;
}

html body div.stApp button:hover:not(:disabled) *,
html body div.stApp a[kind="secondary"]:hover * {
  color: var(--vox-vermilion) !important;
}

html body div.stApp button[kind="primary"],
html body div.stApp [data-testid="baseButton-primary"],
html body div.stApp [data-testid="stBaseButton-primary"],
html body div.stApp button[data-testid*="primary"] {
  background: var(--vox-vermilion) !important;
  background-color: var(--vox-vermilion) !important;
  border: 1px solid var(--vox-vermilion-hover) !important;
  color: #FFFFFF !important;
  box-shadow: 0 2px 8px rgba(185, 94, 70, 0.25) !important;
}

html body div.stApp button[kind="primary"] *,
html body div.stApp [data-testid="baseButton-primary"] *,
html body div.stApp [data-testid="stBaseButton-primary"] * {
  color: #FFFFFF !important;
}

html body div.stApp button[kind="primary"]:hover:not(:disabled),
html body div.stApp [data-testid="baseButton-primary"]:hover:not(:disabled),
html body div.stApp [data-testid="stBaseButton-primary"]:hover:not(:disabled),
html body div.stApp button[data-testid*="primary"]:hover:not(:disabled) {
  background: var(--vox-vermilion-hover) !important;
  background-color: var(--vox-vermilion-hover) !important;
  border-color: #8F422E !important;
  color: #FFFFFF !important;
  box-shadow: 0 4px 14px rgba(185, 94, 70, 0.35) !important;
  transform: translateY(-1px) !important;
}

html body div.stApp button:disabled,
html body div.stApp button[disabled],
html body div.stApp .stButton > button:disabled,
html body div.stApp .stDownloadButton > button:disabled {
  opacity: 0.45 !important;
  cursor: not-allowed !important;
  transform: none !important;
  box-shadow: none !important;
  border-color: var(--vox-border) !important;
}

html body div.stApp button:focus-visible {
  outline: 2px solid var(--vox-vermilion) !important;
  outline-offset: 2px !important;
}

/* Tabs & Segmented Controls */
.stApp [data-baseweb="tab-list"] {
  background: var(--vox-canvas-subtle) !important;
  border: 1px solid var(--vox-border) !important;
  border-radius: var(--vox-radius) !important;
  padding: 0.25rem !important;
  gap: 0.25rem !important;
}

.stApp [data-baseweb="tab"] {
  border-radius: 4px !important;
  padding: 0.45rem 1rem !important;
  color: var(--vox-secondary) !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  transition: all 0.15s ease !important;
  border: 0 !important;
}

.stApp [data-baseweb="tab"]:hover {
  color: var(--vox-ink) !important;
  background: var(--vox-surface) !important;
}

.stApp [data-baseweb="tab"][aria-selected="true"] {
  background: var(--vox-surface-elevated) !important;
  color: var(--vox-vermilion) !important;
  box-shadow: var(--vox-shadow-sm) !important;
}

.stApp [data-baseweb="tab-highlight"] { display: none !important; }

/* Alerts & Notices */
.stApp [data-testid="stAlert"] {
  background: var(--vox-surface-elevated) !important;
  border: 1px solid var(--vox-border) !important;
  border-left: 4px solid var(--vox-blue) !important;
  border-radius: var(--vox-radius) !important;
  color: var(--vox-ink) !important;
  box-shadow: var(--vox-shadow-sm) !important;
}

.stApp [data-testid="stAlert"] p {
  color: var(--vox-ink) !important;
  font-size: 0.88rem !important;
}

/* Expanders */
.stApp [data-testid="stExpander"] {
  background: var(--vox-surface-elevated) !important;
  border: 1px solid var(--vox-border) !important;
  border-radius: var(--vox-radius) !important;
  box-shadow: var(--vox-shadow-sm) !important;
}

.stApp [data-testid="stExpander"] summary {
  color: var(--vox-ink) !important;
  font-weight: 600 !important;
}

/* Audio Player */
audio {
  border-radius: 24px;
  margin: 0.5rem 0;
  width: 100%;
}

/* Scrollbars */
::-webkit-scrollbar {
  width: 7px;
  height: 7px;
}

::-webkit-scrollbar-track {
  background: var(--vox-canvas);
}

::-webkit-scrollbar-thumb {
  background: var(--vox-border);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--vox-secondary);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

@media (max-width: 720px) {
  main .block-container {
    padding: 1.25rem 1rem 2.5rem;
  }
}
</style>
"""
st.markdown(_STYLE, unsafe_allow_html=True)
st.markdown(M6_RESPONSIVE_CSS, unsafe_allow_html=True)


def _current_db_path():
    import os
    from pathlib import Path

    import voxneuro.study.database as _db_mod

    env_path = os.environ.get("VOXNEURO_DB_PATH")
    return Path(env_path) if env_path else _db_mod.DEFAULT_DB_PATH


def _runtime_db_connection():
    """Return a migrated SQLite connection ONLY if runtime DB already exists."""
    db_path = _current_db_path()
    if not db_path.is_file():
        return None
    run_migrations(db_path)
    return get_connection(db_path)


def _ensure_initialized_db_connection():
    """Initialize workspace SQLite DB if needed and return migrated connection."""
    db_path = _current_db_path()
    run_migrations(db_path)
    return get_connection(db_path)


def _active_authenticated_user(conn):
    """Resolve current user strictly from server-side session token."""
    token = st.session_state.get("voxneuro_auth_token")
    if conn is None or not token:
        st.session_state.pop("voxneuro_current_user", None)
        return None
    user = resolve_session_user(conn, token)
    if user is None:
        st.session_state.pop("voxneuro_auth_token", None)
        st.session_state.pop("voxneuro_current_user", None)
    else:
        st.session_state["voxneuro_current_user"] = user
    return user


def _analysis_config() -> tuple[AudioValidationConfig, dict, dict]:
    audio_cfg = dict(AUDIO_CONFIG)
    feature_cfg = dict(FEATURE_CONFIG)
    feature_cfg.pop("schema_version", None)
    validation = AudioValidationConfig.from_dict(audio_cfg, feature_cfg)
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
        "voxneuro_prediction",
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
    source_audio_sha256 = hashlib.sha256(payload).hexdigest()

    validation_config, feature_config, audio_config = _analysis_config()
    record = decode_audio(payload)
    quality = validate_audio(record, validation_config)
    st.session_state["voxneuro_record"] = record
    st.session_state["voxneuro_payload"] = payload
    st.session_state["voxneuro_quality"] = quality
    src_mode = st.session_state.get("voxneuro_audio_source", "Record with microphone")
    cap_origin = "live_browser_mic" if src_mode == "Record with microphone" else "user_upload"
    in_domain = st.session_state.get("voxneuro_acquisition_domain", "unknown")
    domain_source = "user_declared"
    recording_metadata = {
        "capture_origin": cap_origin,
        "acquisition_domain_id": in_domain,
        "acquisition_domain_source": domain_source,
        "task_type": "sustained_vowel",
        "duration_seconds": quality.duration_seconds,
        "original_sample_rate_hz": record.sample_rate,
        "channels": record.channels,
        "repetition_count": 1,
    }
    conn = _runtime_db_connection()
    try:
        active_user = _active_authenticated_user(conn)
        if not quality.valid:
            st.session_state["voxneuro_prediction"] = build_session_prediction(
                features=None,
                quality_valid=False,
                capture_origin=cap_origin,
                input_domain=in_domain,
                acquisition_domain_source=domain_source,
                conn=conn,
                user=active_user,
                recording_metadata=recording_metadata,
                source_audio_sha256=source_audio_sha256,
            )
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
        pred = build_session_prediction(
            features=features,
            quality_valid=True,
            capture_origin=cap_origin,
            input_domain=in_domain,
            acquisition_domain_source=domain_source,
            conn=conn,
            user=active_user,
            recording_metadata=recording_metadata,
            source_audio_sha256=source_audio_sha256,
        )
        st.session_state["voxneuro_prediction"] = pred
    finally:
        if conn is not None:
            conn.close()
    prediction = st.session_state["voxneuro_prediction"]
    report = build_report(
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
            "audio_sha256": source_audio_sha256,
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
            (prediction.abstention_reason or prediction.status)
            if prediction.abstained
            else (
                "Exploratory result; domain compatibility and clinical validation are not "
                "established."
            )
        ),
    )
    report["recording_metadata"] = recording_metadata
    report["model_assessment"].update(prediction.to_dict())
    report["model_assessment"]["interpretation"] = (
        "Exploratory research output only. This is not a diagnosis, disease probability, or "
        "clinical decision. Voice measures are not specific to Parkinson's disease."
    )
    st.session_state["voxneuro_report"] = report
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


def _start_guided_assessment() -> None:
    st.session_state["voxneuro_nav"] = "Voice assessment"
    st.session_state["_prev_voxneuro_nav"] = "Voice assessment"
    st.session_state["voxneuro_m6_view"] = None


def _nav_to_how_it_works() -> None:
    st.session_state["voxneuro_m6_view"] = "How It Works"


def _show_overview() -> None:
    show_consumer_home(_start_guided_assessment, _nav_to_how_it_works)


def _show_assessment() -> None:
    _page_heading(
        "Voice assessment",
        "Hold a relaxed 'ah' sound for 3 to 5 seconds. We check sound quality first and "
        "explain every measurement clearly.",
    )
    status_cur = st.session_state.get("voxneuro_analysis_status")
    quality = st.session_state.get("voxneuro_quality")
    active_step = (
        4
        if status_cur == "complete"
        else (3 if status_cur == "quality_failed" else (2 if quality else 1))
    )
    render_stepper(WIZARD_STEPS, active_step)
    render_medical_disclaimer()

    domain_options = {
        "unknown": "Unknown / I do not know the recording device",
        "uams_telephone": "Telephone / PSTN recording (only for known telephone-source audio)",
        "laptop_microphone": "Laptop or desktop built-in microphone",
        "laptop_webcam_microphone": "Webcam microphone",
        "smartphone_microphone": "Smartphone microphone",
        "consumer_headset": "Consumer headset",
        "laboratory_microphone": "Laboratory microphone",
        "neurovoz_studio": "NeuroVoz studio recording",
        "pc_gita_condenser": "PC-GITA condenser microphone",
        "italian_parkinsons_headset": "Italian Parkinson's voice-study headset",
    }
    st.selectbox(
        "Recording device / acquisition domain",
        options=list(domain_options),
        format_func=lambda value: domain_options[value],
        key="voxneuro_acquisition_domain",
        on_change=_clear_assessment,
        help=(
            "This is a self-reported device category, not evidence of model validation. "
            "Upload method does not reveal which device recorded the audio."
        ),
    )
    st.caption(
        "For WAVs from the included UAMS research cohort, select Telephone / PSTN. "
        "Exact training WAVs are then recognized and withheld from individual scoring because "
        "an in-sample result would be misleading. Use participant-grouped evaluation for those "
        "known recordings. Device selection does not establish clinical validation."
    )

    conn_consent = _runtime_db_connection()
    try:
        active_user = _active_authenticated_user(conn_consent)
        with st.expander("Step 1 · Introduction & Informed Consent", expanded=False):
            show_guided_consent_step(conn_consent, active_user)
    finally:
        if conn_consent is not None:
            conn_consent.close()

    st.markdown(
        '<div class="vx-card" style="margin-bottom:1rem; '
        'background:var(--vx-teal-light); border-color:rgba(13,122,112,0.25);">'
        '<div style="display:flex; align-items:center; gap:0.5rem; '
        'color:var(--vx-teal-dark); font-weight:700; font-size:0.95rem;">'
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2.5">'
        '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>'
        '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>'
        '<line x1="12" y1="19" x2="12" y2="23"/>'
        '<line x1="8" y1="23" x2="16" y2="23"/>'
        "</svg>"
        "Step 2 · Device &amp; Microphone Check: Ready"
        "</div>"
        '<p style="color:#1E3A34; font-size:0.90rem; margin:0.35rem 0 0 0;">'
        "Your microphone is ready. Find a quiet room, hold the microphone about 15–20 cm away, "
        'take an easy breath, and sustain an even "ah" sound for 3 to 5 seconds.'
        "</p>"
        "</div>",
        unsafe_allow_html=True,
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
                with st.status("Processing your voice assessment…", expanded=True) as stat:
                    st.write("1. Preparing your recording & verifying format…")
                    st.write("2. Analysing your voice & extracting acoustic features…")
                    st.write("3. Reviewing the assessment & screening audio quality…")
                    _analyze(payload)
                    st.write("4. Preparing your result & plain-language summary…")
                    stat.update(
                        label="Voice assessment complete!", state="complete", expanded=False
                    )
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
                logger.exception("Unexpected error in voice assessment: %s", exc)
                st.session_state["voxneuro_analysis_status"] = "failed"
                st.session_state["voxneuro_analysis_error"] = (
                    "An unexpected error occurred during audio processing. "
                    "Please verify the audio format and try again."
                )
    quality = st.session_state.get("voxneuro_quality")
    record = st.session_state.get("voxneuro_record")
    status = st.session_state.get("voxneuro_analysis_status")
    if quality is not None and record is not None:
        st.subheader("Signal quality")
        if quality.valid:
            st.info(
                "Audio quality checks passed. This means measurements can be calculated; "
                "it is not a Parkinson's or health result."
            )
            summary = st.columns(4)
            summary[0].metric("Duration", f"{quality.duration_seconds:.2f} s")
            summary[1].metric("Sample rate", f"{record.sample_rate:,} Hz")
            summary[2].metric("Channels", str(record.channels))
            voiced_display = (
                "Not measured"
                if (quality.voiced_fraction is None or np.isnan(quality.voiced_fraction))
                else f"{quality.voiced_fraction:.0%}"
            )
            summary[3].metric("Voiced frames", voiced_display)
            for warning in quality.warnings:
                st.warning(warning)
            if status == "complete":
                st.info("Acoustic measurements are ready. No diagnosis is made by this status.")
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
        pred_state = st.session_state.get("voxneuro_prediction")
        if pred_state is not None:
            render_plain_quality_summary(quality, record)
            render_prediction_outcome_card(pred_state)
    elif status == "failed":
        st.error(
            st.session_state.get("voxneuro_analysis_error", "The recording could not be analyzed.")
        )
    if uploaded is not None and st.session_state.get("voxneuro_features") is not None:
        _render_acoustic_benchmark_cards(st.session_state["voxneuro_features"])
        if quality is not None and record is not None:
            _render_decision_gate_panel(
                st.session_state["voxneuro_features"],
                quality,
                st.session_state.get("voxneuro_prediction"),
            )
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


def _clear_multitask_session() -> None:
    for key in (
        "voxneuro_mt_ddk_runs",
        "voxneuro_mt_cs_run",
        "voxneuro_mt_vs_result",
        "voxneuro_mt_vs_trials",
        "voxneuro_mt_session_envelope",
    ):
        st.session_state.pop(key, None)


def _render_task_status_pill(status: str) -> str:
    s = str(status).strip().lower()
    if s == "complete":
        return '<span class="vox-badge-ok">COMPLETE</span>'
    elif s == "insufficient_signal":
        return '<span class="vox-badge-na">INSUFFICIENT SIGNAL</span>'
    elif s in ("quality_failed", "processing_failed"):
        return '<span class="vox-badge-err">FAILED</span>'
    return f'<span class="vox-code-pill">{html.escape(s.upper())}</span>'


def _vowel_triangle_figure(
    f1_a: float,
    f2_a: float,
    f1_i: float,
    f2_i: float,
    f1_u: float,
    f2_u: float,
    vsa_val: float | None = None,
) -> Figure:
    fig = Figure(figsize=(5.5, 4.0))
    ax = fig.subplots()
    fig.patch.set_facecolor("#FBFAF6")
    ax.set_facecolor("#FFFFFF")
    xs = [f2_i, f2_u, f2_a, f2_i]
    ys = [f1_i, f1_u, f1_a, f1_i]
    ax.plot(xs, ys, "o-", color="#B95E46", linewidth=2.0, markersize=8)
    ax.fill(xs, ys, color="#B95E46", alpha=0.15)
    labels = ["/i/", "/u/", "/a/"]
    coords = [(f2_i, f1_i), (f2_u, f1_u), (f2_a, f1_a)]
    for lbl, (x, y) in zip(labels, coords, strict=True):
        ax.text(x, y - 25, lbl, fontsize=11, fontweight="bold", color="#51445D", ha="center")
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.set_xlabel("F2 frequency (Hz)", fontsize=9, color="#20232B")
    ax.set_ylabel("F1 frequency (Hz)", fontsize=9, color="#20232B")
    title = (
        f"Acoustic Vowel Triangle (VSA = {vsa_val:,.1f} Hz²)"
        if vsa_val is not None
        else "Acoustic Vowel Triangle"
    )
    ax.set_title(title, fontsize=10, fontweight="bold", color="#20232B")
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    return fig


def _show_multitask_assessment() -> None:
    _page_heading(
        "Multi-task speech assessment",
        "Record or upload speech across multiple independent paradigms: "
        "sustained vowels, diadochokinetic syllable repetition, connected speech, "
        "and multi-vowel formant area. Engineered for reproducible acoustic extraction.",
        kicker="VOXNEURO · MULTI-TASK BATTERY (SCHEMA V4)",
    )

    st.warning(DISCLAIMER)

    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.caption(
            "Multi-task speech analysis extracts objective acoustic descriptors across motor, "
            "prosodic, and articulatory subsystems. Audio remains in ephemeral session memory only."
        )
    with top_col2:
        st.button("Clear multi-task session", on_click=_clear_multitask_session, key="mt_clear_btn")

    if "voxneuro_mt_ddk_runs" not in st.session_state:
        st.session_state["voxneuro_mt_ddk_runs"] = {}
    if "voxneuro_mt_vs_trials" not in st.session_state:
        st.session_state["voxneuro_mt_vs_trials"] = {}

    tab_ddk, tab_cs, tab_vs, tab_summary = st.tabs(
        [
            "1. Diadochokinetic (DDK)",
            "2. Connected speech",
            "3. Vowel space area (VSA)",
            "4. Unified session & export",
        ]
    )

    with tab_ddk:
        st.subheader("Diadochokinetic (DDK) Syllable Repetition")
        st.info(
            "Protocol: Take a deep breath and repeat the syllable as rapidly, clearly, "
            "and steadily as possible on a single expiration for 3 to 10 seconds. "
            "Sit comfortably with the microphone at a steady distance."
        )
        ddk_col1, ddk_col2 = st.columns([1, 1])
        with ddk_col1:
            stimulus_label = st.radio(
                "DDK Stimulus",
                ["/pa/ (AMR_PA)", "/ta/ (AMR_TA)", "/ka/ (AMR_KA)", "/pa-ta-ka/ (SMR_PATAKA)"],
                key="mt_ddk_stimulus_radio",
            )
            stim_map = {
                "/pa/ (AMR_PA)": ("pa", "AMR_PA"),
                "/ta/ (AMR_TA)": ("ta", "AMR_TA"),
                "/ka/ (AMR_KA)": ("ka", "AMR_KA"),
                "/pa-ta-ka/ (SMR_PATAKA)": ("pataka", "SMR_PATAKA"),
            }
            stim_key, stim_code = stim_map[stimulus_label]

            ddk_file = st.file_uploader(
                f"Upload WAV recording for {stimulus_label}",
                type=["wav"],
                key=f"mt_ddk_file_{stim_key}",
            )
            if ddk_file is not None:
                if st.button(f"Analyze {stim_code}", key=f"mt_ddk_btn_{stim_key}"):
                    try:
                        record = decode_audio(ddk_file.getvalue())
                        prep = preprocess_task_audio(record, task_type="ddk")
                        ddk_res = extract_ddk_features(
                            prep, task_id=f"ddk_{stim_key}", stimulus=stim_code
                        )
                        st.session_state["voxneuro_mt_ddk_runs"][stim_key] = {
                            "record": record,
                            "prep": prep,
                            "result": ddk_res,
                            "filename": ddk_file.name,
                        }
                        st.success(f"Analysis complete for {stim_code}")
                    except AudioValidationError as ave:
                        st.error(f"Acoustic quality validation failed: {ave}")
                    except Exception as exc:
                        st.error(f"Processing error: {exc}")

        with ddk_col2:
            st.markdown("#### Analysis Results")
            ddk_entry = st.session_state["voxneuro_mt_ddk_runs"].get(stim_key)
            if ddk_entry:
                res = ddk_entry["result"]
                st.markdown(
                    f"**Task ID:** `{res.task_id}` &nbsp;|&nbsp; "
                    f"**Status:** {_render_task_status_pill(res.task_status)}",
                    unsafe_allow_html=True,
                )
                feats = res.features
                v_count = int(feats.get("estimated_event_count") or 0)
                v_rate = (
                    f"{feats['estimated_event_rate_per_s']:.2f}"
                    if feats.get("estimated_event_rate_per_s") is not None
                    else "—"
                )
                v_iei = (
                    f"{feats['mean_inter_event_interval_s']:.3f}"
                    if feats.get("mean_inter_event_interval_s") is not None
                    else "—"
                )
                v_cv = (
                    f"{feats['cv_inter_event_interval']:.3f}"
                    if feats.get("cv_inter_event_interval") is not None
                    else "—"
                )
                st.markdown(
                    f'<div class="vox-grid-2">'
                    f'<div class="vox-card"><div class="vox-qc-label">Syllable Event Count</div>'
                    f'<div class="vox-qc-value">{v_count}</div>'
                    f'<div class="vox-qc-sub">Events detected</div></div>'
                    f'<div class="vox-card"><div class="vox-qc-label">Syllable Rate</div>'
                    f'<div class="vox-qc-value">{v_rate}</div>'
                    f'<div class="vox-qc-sub">Syllables / s</div></div>'
                    f'<div class="vox-card">'
                    f'<div class="vox-qc-label">Mean Inter-Event Interval</div>'
                    f'<div class="vox-qc-value">{v_iei}</div>'
                    f'<div class="vox-qc-sub">Seconds</div></div>'
                    f'<div class="vox-card"><div class="vox-qc-label">Variability (CV IEI)</div>'
                    f'<div class="vox-qc-value">{v_cv}</div>'
                    f'<div class="vox-qc-sub">Unitless ratio</div></div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
                if feats.get("inter_event_interval_slope_s_per_event") is not None:
                    drift_val = feats["inter_event_interval_slope_s_per_event"]
                    st.caption(f"IEI drift slope: {drift_val:+.4f} s/event")
            else:
                st.info(
                    f"No recording analyzed yet for {stim_code}. "
                    "Upload a WAV file and click Analyze."
                )

    with tab_cs:
        st.subheader("Connected Speech Analysis")
        st.info(
            "Protocol: Read the standardized phonetically balanced passage aloud at a natural, "
            "comfortable speaking pace and volume. Do not rush or pause artificially."
        )
        with st.expander("Standard Reading Stimulus (Bamboo Passage)"):
            st.markdown(
                "> *Cheaply made bamboo boats can be useful for light travel. "
                "They carry few people and float easily upon the smooth surface. "
                "Strong reeds and tall stalks bend in the quiet wind.*"
            )
        cs_col1, cs_col2 = st.columns([1, 1])
        with cs_col1:
            cs_file = st.file_uploader(
                "Upload Connected Speech recording (WAV)",
                type=["wav"],
                key="mt_cs_file_uploader",
            )
            if cs_file is not None:
                if st.button("Analyze Connected Speech", key="mt_cs_btn"):
                    try:
                        record = decode_audio(cs_file.getvalue())
                        prep = preprocess_task_audio(record, task_type="connected_speech")
                        cs_res = extract_connected_speech_features(prep)
                        st.session_state["voxneuro_mt_cs_run"] = {
                            "record": record,
                            "prep": prep,
                            "result": cs_res,
                            "filename": cs_file.name,
                        }
                        st.success("Analysis complete for connected speech")
                    except AudioValidationError as ave:
                        st.error(f"Acoustic quality validation failed: {ave}")
                    except Exception as exc:
                        st.error(f"Processing error: {exc}")

        with cs_col2:
            st.markdown("#### Analysis Results")
            cs_entry = st.session_state.get("voxneuro_mt_cs_run")
            if cs_entry:
                res = cs_entry["result"]
                st.markdown(
                    f"**Task ID:** `{res.task_id}` &nbsp;|&nbsp; "
                    f"**Status:** {_render_task_status_pill(res.task_status)}",
                    unsafe_allow_html=True,
                )
                feats = res.features
                v_dur = f"{feats.get('total_recording_duration_s', 0.0):.2f} s"
                v_pause = (
                    f"{feats.get('pause_fraction', 0.0) * 100:.1f}%"
                    if feats.get("pause_fraction") is not None
                    else "—"
                )
                v_act = (
                    f"{feats.get('speech_activity_fraction', 0.0) * 100:.1f}%"
                    if feats.get("speech_activity_fraction") is not None
                    else "—"
                )
                v_f0 = (
                    f"{feats.get('f0_median_hz'):.1f} Hz"
                    if feats.get("f0_median_hz") is not None
                    else "—"
                )
                v_f0_sd = (
                    f"Pitch SD: {feats.get('f0_sd_hz'):.1f} Hz"
                    if feats.get("f0_sd_hz") is not None
                    else "—"
                )
                v_range = (
                    f"{feats.get('f0_range_semitones'):.1f} st"
                    if feats.get("f0_range_semitones") is not None
                    else "—"
                )
                st.markdown(
                    f'<div class="vox-grid-2">'
                    f'<div class="vox-card"><div class="vox-qc-label">Total Duration</div>'
                    f'<div class="vox-qc-value">{v_dur}</div>'
                    f'<div class="vox-qc-sub">Recording length</div></div>'
                    f'<div class="vox-card"><div class="vox-qc-label">Pause Fraction</div>'
                    f'<div class="vox-qc-value">{v_pause}</div>'
                    f'<div class="vox-qc-sub">Pause ratio</div></div>'
                    f'<div class="vox-card"><div class="vox-qc-label">Speech Activity</div>'
                    f'<div class="vox-qc-value">{v_act}</div>'
                    f'<div class="vox-qc-sub">Active speech ratio</div></div>'
                    f'<div class="vox-card"><div class="vox-qc-label">Median Pitch (F0)</div>'
                    f'<div class="vox-qc-value">{v_f0}</div>'
                    f'<div class="vox-qc-sub">{v_f0_sd}</div></div>'
                    f'<div class="vox-card"><div class="vox-qc-label">Pitch Range (Semitones)</div>'
                    f'<div class="vox-qc-value">{v_range}</div>'
                    f'<div class="vox-qc-sub">Prosodic dynamic range</div></div>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info(
                    "No connected speech recording analyzed yet. "
                    "Upload a WAV file and click Analyze."
                )

    with tab_vs:
        st.subheader("Vowel Space Area (VSA) & Formant Analysis")
        st.info(
            "Protocol: Phonate the corner vowels clearly, comfortably, and steadily: "
            "/a/ (open back/central, as in 'father'), /i/ (high front, as in 'beet'), "
            "and /u/ (high back, as in 'boot') for 2–4 seconds each. "
            "VSA evaluates articulatory range of motion in the oral cavity."
        )
        vs_col1, vs_col2, vs_col3 = st.columns(3)
        vowel_files: dict[str, Any] = {}
        with vs_col1:
            st.markdown("##### Corner Vowel /a/")
            f_a = st.file_uploader("Upload /a/ WAV", type=["wav"], key="mt_vs_file_a")
            if f_a:
                vowel_files["a"] = f_a
        with vs_col2:
            st.markdown("##### Corner Vowel /i/")
            f_i = st.file_uploader("Upload /i/ WAV", type=["wav"], key="mt_vs_file_i")
            if f_i:
                vowel_files["i"] = f_i
        with vs_col3:
            st.markdown("##### Corner Vowel /u/")
            f_u = st.file_uploader("Upload /u/ WAV", type=["wav"], key="mt_vs_file_u")
            if f_u:
                vowel_files["u"] = f_u

        if st.button("Compute Vowel Space Area", key="mt_vs_compute_btn"):
            if not ("a" in vowel_files and "i" in vowel_files and "u" in vowel_files):
                st.warning(
                    "Please upload WAV recordings for all three corner vowels (/a/, /i/, and /u/)."
                )
            else:
                try:
                    trials_map: dict[str, list[Any]] = {}
                    for v_key in ("a", "i", "u"):
                        rec = decode_audio(vowel_files[v_key].getvalue())
                        prep = preprocess_task_audio(rec, task_type="vowel_space")
                        trials_map[v_key] = [prep]
                    vs_res = extract_vowel_space_features(trials_map)
                    st.session_state["voxneuro_mt_vs_result"] = vs_res
                    st.session_state["voxneuro_mt_vs_trials"] = trials_map
                    st.success("Vowel Space Area successfully computed")
                except AudioValidationError as ave:
                    st.error(f"Vowel acoustic validation error: {ave}")
                except Exception as exc:
                    st.error(f"VSA computation error: {exc}")

        vs_res = st.session_state.get("voxneuro_mt_vs_result")
        if vs_res:
            st.markdown("---")
            v_list_str = ", ".join(f"/{v}/" for v in sorted(vs_res.per_vowel_results.keys()))
            st.markdown(
                f"**Task Status:** {_render_task_status_pill(vs_res.task_status)} &nbsp;|&nbsp; "
                f"**Corner Vowels Provided:** {v_list_str}",
                unsafe_allow_html=True,
            )
            vsa_m1, vsa_m2 = st.columns(2)
            feats = vs_res.features
            vsa_val = feats.get("vowel_space_area_hz2")
            vsa_str = f"{vsa_val:,.1f}" if vsa_val is not None else "—"

            with vsa_m1:
                st.markdown(
                    f'<div class="vox-card"><div class="vox-qc-label">Triangular VSA</div>'
                    f'<div class="vox-qc-value">{vsa_str}</div>'
                    f'<div class="vox-qc-sub">Hz² (F1-F2 triangular area)</div></div>',
                    unsafe_allow_html=True,
                )
            with vsa_m2:
                vsa_status_text = "Estimable" if vs_res.vsa_estimable else "Incomplete"
                st.markdown(
                    f'<div class="vox-card"><div class="vox-qc-label">VSA Status</div>'
                    f'<div class="vox-qc-value">{vsa_status_text}</div>'
                    f'<div class="vox-qc-sub">Corner vowels available</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("##### Extracted Formants & Acoustic Triangle")
            f_col1, f_col2 = st.columns([1, 1])
            with f_col1:
                formant_rows = []
                for v in ("a", "i", "u"):
                    f1 = feats.get(f"f1_{v}_median_hz")
                    f2 = feats.get(f"f2_{v}_median_hz")
                    formant_rows.append(
                        {
                            "Vowel": f"/{v}/",
                            "F1 Median (Hz)": f"{f1:.1f}" if f1 is not None else "—",
                            "F2 Median (Hz)": f"{f2:.1f}" if f2 is not None else "—",
                        }
                    )
                st.table(pd.DataFrame(formant_rows))

            with f_col2:
                f1_a = feats.get("f1_a_median_hz")
                f2_a = feats.get("f2_a_median_hz")
                f1_i = feats.get("f1_i_median_hz")
                f2_i = feats.get("f2_i_median_hz")
                f1_u = feats.get("f1_u_median_hz")
                f2_u = feats.get("f2_u_median_hz")
                if all(val is not None for val in (f1_a, f2_a, f1_i, f2_i, f1_u, f2_u)):
                    fig = _vowel_triangle_figure(f1_a, f2_a, f1_i, f2_i, f1_u, f2_u, vsa_val)
                    st.pyplot(fig, clear_figure=True)

    with tab_summary:
        st.subheader("Multi-Task Session Envelope (Schema v4)")
        st.caption(
            "Synthesizes acoustic results across all completed tasks into a versioned "
            "voxneuro.voice.v4 session receipt and standalone HTML dashboard."
        )

        if st.button("Assemble Multi-Task Session", key="mt_assemble_btn"):
            ddk_recs = {}
            for sk, run in st.session_state.get("voxneuro_mt_ddk_runs", {}).items():
                ddk_recs[sk] = run["record"]

            cs_run = st.session_state.get("voxneuro_mt_cs_run")
            cs_rec = cs_run["record"] if cs_run else None

            vs_trials = st.session_state.get("voxneuro_mt_vs_trials")
            v_a = st.session_state.get("voxneuro_record")

            if not (ddk_recs or cs_rec or vs_trials or v_a):
                st.warning(
                    "No task recordings have been analyzed yet. Please complete at least one task."
                )
            else:
                sess_result = analyze_multitask_session(
                    sustained_vowel=v_a,
                    ddk_recordings=ddk_recs if ddk_recs else None,
                    connected_speech=cs_rec,
                    vowel_space_recordings=vs_trials,
                )
                st.session_state["voxneuro_mt_session_envelope"] = sess_result
                st.success("Multi-task session successfully assembled")

        envelope: MultiTaskSessionResult | None = st.session_state.get(
            "voxneuro_mt_session_envelope"
        )
        if envelope:
            overall_pill = _render_task_status_pill(envelope.overall_processing_status)
            st.markdown(
                f'<div class="vox-grid-2">'
                f'<div class="vox-card"><div class="vox-qc-label">Session ID</div>'
                f'<div class="vox-qc-value" style="font-size:0.95rem;">{envelope.session_id}</div>'
                f'<div class="vox-qc-sub">UUIDv4 Session Identifier</div></div>'
                f'<div class="vox-card"><div class="vox-qc-label">Overall Status</div>'
                f'<div class="vox-qc-value">{overall_pill}</div>'
                f'<div class="vox-qc-sub">Envelope Schema: {envelope.schema_version}</div></div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("##### Task Inventory")
            inv_rows = []
            for t_name, t_data in envelope.tasks.items():
                inv_rows.append(
                    {
                        "Task Identifier": t_name,
                        "Task Type": t_data.get("task_type", "—"),
                        "Schema Version": t_data.get("task_schema_version", "—"),
                        "Status": t_data.get("task_status", "—"),
                        "Feature Count": len(t_data.get("features", {})),
                    }
                )
            st.table(pd.DataFrame(inv_rows))

            st.markdown("##### Export Artifacts")
            down_col1, down_col2 = st.columns(2)
            with down_col1:
                json_str = envelope.to_json()
                st.download_button(
                    "Download Session JSON (v4)",
                    data=json_str,
                    file_name=f"voxneuro_session_v4_{envelope.session_id[:8]}.json",
                    mime="application/json",
                    key="mt_download_json_btn",
                )
            with down_col2:
                html_str = render_multitask_report_html(envelope)
                st.download_button(
                    "Download Standalone HTML Report",
                    data=html_str,
                    file_name=f"voxneuro_report_v4_{envelope.session_id[:8]}.html",
                    mime="text/html",
                    key="mt_download_html_btn",
                )


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
            waveform_payload(
                processed.samples[first_sample:last_sample],
                processed.sample_rate,
                start_seconds=detail_start,
            ),
            height=440,
        )
        st.caption(
            f"The 3D waveform shows actual processed samples from {detail_start:.2f} to "
            f"{detail_start + detail_duration:.2f} seconds. Ribbon depth varies with "
            "instantaneous absolute amplitude. Use the slider to move the detail window; "
            "the plots below show the full recording."
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
    proc_df = pd.DataFrame(
        [
            {
                "setting": "Retained duration",
                "value": f"{processed.retained_duration_seconds:.3f} s",
            },
            {"setting": "Output sample rate", "value": f"{processed.sample_rate:,} Hz"},
            {"setting": "Start trim", "value": f"{processed.trim_start_seconds:.3f} s"},
            {"setting": "Tail trim", "value": f"{processed.trimmed_tail_seconds:.3f} s"},
            {
                "setting": "Removed DC offset",
                "value": f"{processed.dc_offset_removed:.6f} FS",
            },
            {"setting": "Resampled", "value": "Yes" if processed.resampled else "No"},
        ]
    )
    _render_generic_glass_table(proc_df, headers=["Processing Step", "Measured Parameter"])


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
            f'<td style="color:#676970; font-size:0.83rem;">{method}</td>'
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


def _render_generic_glass_table(df: pd.DataFrame, headers: list[str] | None = None) -> None:
    display_headers = (
        headers if headers is not None else [str(c).replace("_", " ").title() for c in df.columns]
    )
    rows_html = []
    for _, row in df.iterrows():
        cells_html = []
        for i, val in enumerate(row):
            col_name = str(df.columns[i]).lower()
            if val is None or (isinstance(val, float) and not np.isfinite(val)):
                formatted = '<span style="color:var(--vox-muted);">—</span>'
            elif isinstance(val, (float, np.floating)):
                if any(
                    k in col_name
                    for k in (
                        "accuracy",
                        "auc",
                        "rate",
                        "fraction",
                        "f1",
                        "sensitivity",
                        "specificity",
                        "precision",
                    )
                ):
                    if 0.0 <= val <= 1.0:
                        formatted = f'<span class="vox-val-num">{val * 100:.1f}%</span>'
                    else:
                        formatted = f'<span class="vox-val-num">{val:.3f}</span>'
                elif abs(val) >= 100:
                    formatted = f'<span class="vox-val-num">{val:,.2f}</span>'
                elif abs(val) >= 1:
                    formatted = f'<span class="vox-val-num">{val:.4f}</span>'
                else:
                    formatted = f'<span class="vox-val-num">{val:.5f}</span>'
            elif isinstance(val, (bool, np.bool_)):
                if val:
                    formatted = '<span class="vox-badge-ok">True</span>'
                else:
                    formatted = '<span class="vox-badge-na">False</span>'
            elif isinstance(val, (int, np.integer)):
                formatted = f'<span class="vox-val-num">{val:,}</span>'
            elif str(val).lower() in ("valid", "true", "yes", "available", "hc"):
                formatted = f'<span class="vox-badge-ok">{html.escape(str(val))}</span>'
            elif str(val).lower() in ("flagged", "false", "no", "undefined", "pd"):
                formatted = f'<span class="vox-badge-na">{html.escape(str(val))}</span>'
            elif i == 0 and any(
                k in col_name for k in ("setting", "step", "feature", "model", "param", "property")
            ):
                formatted = f'<span class="vox-code-pill">{html.escape(str(val))}</span>'
            else:
                formatted = html.escape(str(val))
            cells_html.append(f"<td>{formatted}</td>")
        rows_html.append(f"<tr>{''.join(cells_html)}</tr>")

    th_html = "".join(f"<th>{html.escape(h)}</th>" for h in display_headers)
    html_markup = (
        '<div class="vox-table-wrapper">'
        '<table class="vox-table">'
        f"<thead><tr>{th_html}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table></div>"
    )
    st.markdown(html_markup, unsafe_allow_html=True)


def _render_quality_cards(quality: dict) -> None:
    valid = bool(quality.get("valid", False))
    status_label = "VALID" if valid else "FLAGGED"
    status_badge = (
        '<span class="vox-badge-ok">READY FOR ANALYSIS</span>'
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
        f'<div class="vox-qc-sub">Suggested: 3–5 s · Range: {min_dur:.1f}–{max_dur:.1f} s</div>'
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
        raw_json = html.escape(json.dumps(quality, indent=2))
        st.markdown(
            f'<div class="vox-json-card"><pre><code>{raw_json}</code></pre></div>',
            unsafe_allow_html=True,
        )


def _render_decision_gate_panel(
    features: dict, quality: AudioQuality, prediction: PredictionResult | None = None
) -> None:
    finite_count = sum(
        1 for v in features.values() if isinstance(v, Real) and np.isfinite(float(v))
    )
    schema_ver = html.escape(str(features.get("schema_version", "voxneuro.voice.v3")))
    voiced_text = (
        "Not measured"
        if (quality.voiced_fraction is None or np.isnan(quality.voiced_fraction))
        else f"{quality.voiced_fraction:.0%} voiced"
    )
    stage_five = (
        "EXPLORATORY CANDIDATE"
        if prediction is not None and not prediction.abstained
        else "ABSTAIN"
    )
    stage_five_detail = (
        prediction.research_classification
        if prediction is not None and not prediction.abstained
        else (
            prediction.abstention_reason
            if prediction is not None
            else "No model result is available."
        )
    )
    domain_summary = (
        f"{prediction.acquisition_domain_id} · {prediction.acquisition_domain_source}"
        if prediction is not None
        else "Unknown"
    )
    html_markup = (
        '<div class="vox-editorial-card" style="margin-top:1.15rem; '
        'border-color: var(--vox-border);">'
        '<div class="vox-kicker" style="margin-bottom:0.35rem;">'
        "RESEARCH WORKFLOW &amp; DOMAIN SAFETY AUDIT</div>"
        '<p style="color:var(--vox-secondary); font-size:0.86rem; '
        'margin-bottom:1rem; line-height:1.55;">'
        "Evaluates the 5-stage software intake and domain verification workflow before any "
        "downstream analysis."
        "</p>"
        '<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); '
        'gap:0.75rem; margin-bottom:1rem;">'
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 1 · Quality Gate</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; color:var(--vox-success);">PASS</div>'
        f'<div class="vox-qc-sub">{quality.duration_seconds:.1f}s · '
        f"{voiced_text} · "
        f"{quality.clipping_fraction:.2%} clipped</div>"
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 2 · Task Plausibility</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; '
        'color:var(--vox-success);">HEURISTIC PASS</div>'
        '<div class="vox-qc-sub">Phonated-vowel criteria met (acoustic screening)</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 3 · Feature Extraction</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; '
        'color:var(--vox-success);">PROCESSED</div>'
        f'<div class="vox-qc-sub">{finite_count}/39 finite measures ({schema_ver})</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 4 · Domain Status</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; '
        'color:var(--vox-warning);">NOT VALIDATED</div>'
        f'<div class="vox-qc-sub">{html.escape(domain_summary)} · compatibility unvalidated</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 5 · Safety Policy</div>'
        f'<div class="vox-qc-value" style="font-size:1.05rem; '
        f'color:var(--vox-vermilion);">{html.escape(stage_five)}</div>'
        f'<div class="vox-qc-sub">{html.escape(str(stage_five_detail))}</div>'
        "</div>"
        "</div>"
        '<div style="background:#FAF5EC; '
        "border:1px solid #E5D3B8; border-left:3px solid var(--vox-vermilion); border-radius:4px; "
        'padding:0.85rem 1rem; font-size:0.84rem; color:var(--vox-ink); line-height:1.6;">'
        '<strong style="color:var(--vox-vermilion);">Protocol Rationale:</strong> '
        "The UAMS research baseline "
        "was collected over telephone lines (8 kHz PSTN) in an uncontrolled clinical trial. "
        "External recording devices (microphones, consumer headsets, audio interfaces) exhibit "
        "distinct acoustic transfer functions and frequency responses. To prevent uncalibrated "
        "predictions and false positives, VoxNeuro operates a strict fail-closed safety gate: "
        "39 acoustic measurements and session telemetry are exported, but disease "
        "any displayed candidate is explicitly exploratory, uncalibrated, and not validated for "
        "the selected device."
        "</div>"
        "</div>"
    )
    st.markdown(html_markup, unsafe_allow_html=True)


def _render_acoustic_benchmark_cards(features: dict) -> None:
    f0 = features.get("f0_mean_hz")
    jitter = features.get("jitter_local")
    shimmer = features.get("shimmer_local")
    hnr = features.get("hnr_mean_db")

    f0_str = f"{f0:.1f} Hz" if isinstance(f0, Real) and np.isfinite(f0) else "—"
    jitter_str = (
        f"{jitter * 100.0:.3f}%" if isinstance(jitter, Real) and np.isfinite(jitter) else "—"
    )
    shimmer_str = (
        f"{shimmer * 100.0:.2f}%" if isinstance(shimmer, Real) and np.isfinite(shimmer) else "—"
    )
    hnr_str = f"{hnr:.1f} dB" if isinstance(hnr, Real) and np.isfinite(hnr) else "—"

    html_str = (
        '<div class="vox-editorial-card" style="margin-top:1.25rem;">'
        '<div class="vox-kicker" style="margin-bottom:0.4rem;">'
        "CORE ACOUSTIC MEASUREMENTS · SUSTAINED /A/ PHONATION</div>"
        '<p style="color:var(--vox-secondary); font-size:0.86rem; '
        'margin-bottom:1rem; line-height:1.55;">'
        "Descriptive vocal stability and harmonic measurements extracted from the recording. "
        "Strictly exploratory for bioengineering analysis; no universal normal range or "
        "diagnostic disease threshold is assigned."
        "</p>"
        '<div class="vox-quality-grid">'
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Mean Pitch (F0)</div>'
        f'<div class="vox-qc-value">{f0_str}</div>'
        '<div class="vox-qc-sub">Estimated fundamental frequency</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Local Jitter</div>'
        f'<div class="vox-qc-value">{jitter_str}</div>'
        '<div class="vox-qc-sub">Cycle-to-cycle frequency variation</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Local Shimmer</div>'
        f'<div class="vox-qc-value">{shimmer_str}</div>'
        '<div class="vox-qc-sub">Cycle-to-cycle amplitude variation</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Harmonics-to-Noise</div>'
        f'<div class="vox-qc-value">{hnr_str}</div>'
        '<div class="vox-qc-sub">Relative periodic vs noise energy</div>'
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(html_str, unsafe_allow_html=True)


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


def _current_nested_evaluation_package() -> tuple[pd.DataFrame | None, list[str]]:
    processed = PROJECT_ROOT / "data" / "processed"
    manifest_path = processed / "feature_manifest.csv"
    feature_path = processed / "voice_features.csv"
    receipt_path = processed / "nested_uams_evaluation_receipt.json"
    metrics_path = processed / "nested_uams_metrics.csv"
    predictions_path = processed / "nested_uams_oof_predictions.csv"
    summary_path = processed / "nested_uams_summary.csv"
    report_path = PROJECT_ROOT / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html"
    for p in (
        manifest_path,
        feature_path,
        receipt_path,
        metrics_path,
        predictions_path,
        summary_path,
        report_path,
    ):
        if not p.is_file():
            return None, [f"Missing required nested evaluation artifact: {p.name}"]
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
        return None, issues
    try:
        df = pd.read_csv(summary_path)
    except Exception as exc:
        return None, [f"Could not parse nested UAMS summary: {exc}"]
    required_cols = {"model", "model_label", "balanced_accuracy_mean", "roc_auc_mean"}
    if not required_cols.issubset(df.columns) or df.empty or df["model"].duplicated().any():
        return None, ["Nested evaluation summary does not meet structural requirements."]

    if df["model"].isna().any() or df["model_label"].isna().any():
        return None, ["Nested evaluation summary contains missing model identifiers or labels."]
    models = df["model"].astype(str).str.strip()
    labels = df["model_label"].astype(str).str.strip()
    if any(not m or m.lower() == "nan" or "<" in m or ">" in m for m in models):
        return None, ["Nested evaluation contains invalid or unescaped model identifiers."]
    if any(not lbl or lbl.lower() == "nan" or "<" in lbl or ">" in lbl for lbl in labels):
        return None, ["Nested evaluation contains invalid or unescaped model labels."]

    metric_cols = [
        c
        for c in [
            "balanced_accuracy_mean",
            "roc_auc_mean",
            "sensitivity_mean",
            "specificity_mean",
            "f1_mean",
        ]
        if c in df.columns
    ]
    for col in metric_cols:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.isna().any() or not vals.between(0.0, 1.0).all():
            return None, [f"Nested evaluation metric '{col}' contains values outside [0.0, 1.0]."]

    sd_cols = [
        c
        for c in ["balanced_accuracy_repeat_sd", "roc_auc_repeat_sd", "f1_repeat_sd"]
        if c in df.columns
    ]
    for col in sd_cols:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.isna().any() or (vals < 0.0).any():
            return None, [
                f"Nested evaluation metric '{col}' contains negative standard deviations."
            ]

    if "age_only_logistic" not in set(models):
        return None, ["Nested evaluation summary must contain 'age_only_logistic' baseline."]
    voice_models = set(models) - {"dummy", "age_only_logistic", "age_plus_voice_logistic"}
    if not voice_models:
        return None, ["Nested evaluation summary must contain at least one voice model candidate."]

    return df, []


def _current_nested_evaluation_html() -> str | None:
    df, issues = _current_nested_evaluation_package()
    if issues or df is None:
        return None
    report_path = PROJECT_ROOT / "artifacts" / "reports" / "model_evaluation" / "uams_nested.html"
    try:
        return report_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _model_comparison_figure(metrics: pd.DataFrame):
    grouped = metrics.groupby("model")["balanced_accuracy"].agg(["mean", "std"]).sort_values("mean")
    colors = [
        "#B95E46" if "age" in model else "#898982" if model == "dummy" else "#526A91"
        for model in grouped.index
    ]
    fig = Figure(figsize=(8.4, 3.8))
    ax = fig.subplots()
    fig.patch.set_facecolor("#FBFAF6")
    ax.set_facecolor("#FFFFFF")
    ax.barh(
        grouped.index,
        grouped["mean"],
        xerr=grouped["std"].fillna(0),
        color=colors,
        alpha=0.92,
        capsize=3,
        error_kw={"ecolor": "#20232B", "elinewidth": 1.1},
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel(
        "Balanced accuracy · mean ± SD across grouped folds",
        color="#676970",
        fontsize=9.5,
    )
    ax.set_title("Internal UAMS comparison", color="#20232B", fontsize=11, fontweight="650")
    ax.grid(axis="x", color="#D8D3C8", alpha=0.55, linewidth=0.6, linestyle=":")
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#D8D3C8")
    ax.tick_params(axis="y", length=0, labelcolor="#20232B", labelsize=9.5)
    ax.tick_params(axis="x", colors="#676970", labelsize=9)
    fig.tight_layout()
    return fig


def _nested_model_comparison_figure(nested_df: pd.DataFrame):
    df_sorted = nested_df.sort_values("balanced_accuracy_mean")
    colors = [
        "#B95E46" if "age" in str(m) else "#898982" if str(m) == "dummy" else "#526A91"
        for m in df_sorted["model"]
    ]
    labels = (
        df_sorted["model_label"].tolist()
        if "model_label" in df_sorted.columns
        else df_sorted["model"].tolist()
    )
    fig = Figure(figsize=(9.2, 4.4))
    ax = fig.subplots()
    fig.patch.set_facecolor("#FBFAF6")
    ax.set_facecolor("#FFFFFF")
    ax.barh(
        labels,
        df_sorted["balanced_accuracy_mean"],
        xerr=df_sorted["balanced_accuracy_repeat_sd"].fillna(0),
        color=colors,
        alpha=0.92,
        capsize=3,
        error_kw={"ecolor": "#20232B", "elinewidth": 1.1},
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel(
        "Balanced accuracy · repeated nested-CV mean ± SD",
        color="#676970",
        fontsize=9.5,
    )
    ax.set_title(
        "Repeated Nested CV: 7 Voice Models vs Confounded Baselines",
        color="#20232B",
        fontsize=11.5,
        fontweight="650",
    )
    ax.grid(axis="x", color="#D8D3C8", alpha=0.55, linewidth=0.6, linestyle=":")
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#D8D3C8")
    ax.tick_params(axis="y", length=0, labelcolor="#20232B", labelsize=9)
    ax.tick_params(axis="x", colors="#676970", labelsize=9)
    fig.tight_layout()
    return fig


def _out_of_fold_confusion_figure(predictions: pd.DataFrame):
    selected = predictions.loc[predictions["model"].eq("logistic_regression")]
    matrix = confusion_matrix(
        selected["y_true"].astype(int),
        selected["y_pred"].astype(int),
        labels=[0, 1],
    )
    fig = Figure(figsize=(4.3, 3.4))
    ax = fig.subplots()
    fig.patch.set_facecolor("#FBFAF6")
    ax.set_facecolor("#FFFFFF")
    image = ax.imshow(matrix, cmap="Blues", vmin=0)
    for (row, column), value in np.ndenumerate(matrix):
        text_color = "#FFFFFF" if value > 20 else "#20232B"
        ax.text(
            column,
            row,
            str(value),
            ha="center",
            va="center",
            color=text_color,
            fontsize=12,
            fontweight="bold",
        )
    ax.set_xticks([0, 1], labels=["HC", "PD"], color="#20232B")
    ax.set_yticks([0, 1], labels=["HC", "PD"], color="#20232B")
    ax.set_xlabel("Predicted group", color="#676970", fontsize=9)
    ax.set_ylabel("Reference group", color="#676970", fontsize=9)
    ax.set_title(
        "Logistic regression · held-out participants",
        color="#20232B",
        fontsize=10,
        fontweight="650",
    )
    cbar = fig.colorbar(image, ax=ax, label="Participants")
    cbar.ax.yaxis.label.set_color("#676970")
    cbar.ax.tick_params(colors="#676970")
    cbar.outline.set_edgecolor("#D8D3C8")
    for spine in ax.spines.values():
        spine.set_color("#D8D3C8")
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
    fig = Figure(figsize=(4.3, 3.4))
    ax = fig.subplots()
    fig.patch.set_facecolor("#FBFAF6")
    ax.set_facecolor("#FFFFFF")
    ax.plot(
        false_positive,
        true_positive,
        color="#B95E46",
        linewidth=2.0,
        label=f"ROC AUC {auc:.3f}",
    )
    ax.plot(
        [0, 1],
        [0, 1],
        color="#898982",
        linewidth=1,
        linestyle="--",
        label="Chance (0.50)",
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False positive rate", color="#676970", fontsize=9)
    ax.set_ylabel("True positive rate", color="#676970", fontsize=9)
    ax.set_title(
        "Pooled out-of-fold ranking",
        color="#20232B",
        fontsize=10,
        fontweight="650",
    )
    ax.legend(
        frameon=True,
        facecolor="#FFFFFF",
        edgecolor="#D8D3C8",
        loc="lower right",
        labelcolor="#20232B",
        fontsize=8.5,
    )
    ax.grid(color="#D8D3C8", alpha=0.55, linewidth=0.6, linestyle=":")
    ax.set_axisbelow(True)
    ax.tick_params(colors="#676970")
    for spine in ax.spines.values():
        spine.set_color("#D8D3C8")
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

    nested_df, nested_issues = _current_nested_evaluation_package()
    voice_candidates = pd.DataFrame()
    age_match = pd.DataFrame()
    best_voice = None
    ba_mean = 0.0
    ba_sd = 0.0
    auc_mean = 0.0
    age_ba = 0.0
    if nested_df is not None:
        try:
            st.subheader(
                "Repeated nested cross-validation (7 voice models + 2 age baselines + dummy)"
            )
            st.caption(
                "Repeated grouped nested cross-validation with hyperparameter tuning in inner "
                "folds. Evaluates generalization and assesses demographic confounding."
            )
            st.pyplot(_nested_model_comparison_figure(nested_df), clear_figure=True)
            summary_cols = [
                c
                for c in [
                    "model_label",
                    "balanced_accuracy_mean",
                    "balanced_accuracy_repeat_sd",
                    "roc_auc_mean",
                    "sensitivity_mean",
                    "specificity_mean",
                    "f1_mean",
                ]
                if c in nested_df.columns
            ]
            col_to_header = {
                "model_label": "Model Family",
                "balanced_accuracy_mean": "Bal. Acc. Mean",
                "balanced_accuracy_repeat_sd": "Bal. Acc. SD",
                "roc_auc_mean": "ROC-AUC",
                "sensitivity_mean": "Sensitivity",
                "specificity_mean": "Specificity",
                "f1_mean": "F1 Score",
            }
            summary_headers = [
                col_to_header.get(c, c.replace("_", " ").title()) for c in summary_cols
            ]
            _render_generic_glass_table(
                nested_df[summary_cols].copy(),
                headers=summary_headers,
            )
            voice_candidates = nested_df[
                ~nested_df["model"].isin(["age_only_logistic", "age_plus_voice_logistic", "dummy"])
            ]
            age_match = nested_df[nested_df["model"] == "age_only_logistic"]
            if not voice_candidates.empty and not age_match.empty:
                best_voice = voice_candidates.loc[
                    voice_candidates["balanced_accuracy_mean"].idxmax()
                ]
                top_label = best_voice["model_label"]
                ba_mean = float(best_voice["balanced_accuracy_mean"])
                ba_sd = float(best_voice.get("balanced_accuracy_repeat_sd", 0.0))
                auc_mean = float(best_voice["roc_auc_mean"])
                age_row = age_match.iloc[0]
                age_ba = float(age_row["balanced_accuracy_mean"])
                top_model_text = (
                    f"{top_label} achieved the highest voice-only discrimination at "
                    f"<strong>{ba_mean * 100:.1f}% balanced accuracy</strong> "
                    f"({ba_mean:.3f} ± {ba_sd:.3f}) and <strong>{auc_mean:.3f} ROC-AUC</strong>."
                )
                age_confound_text = (
                    f"The age-only logistic baseline achieved "
                    f"<strong>{age_ba * 100:.1f}% balanced accuracy</strong> "
                    f"({age_ba:.3f}) in this markedly age-imbalanced cohort in UAMS "
                    "(PD participants were older on average). This demonstrates that "
                    "voice discrimination alone must not be mistaken for diagnostic "
                    "specificity without age-matched controls."
                )
            else:
                top_model_text = (
                    "Voice-only candidate models are evaluated via repeated nested "
                    "participant-grouped cross-validation on sustained vowel recordings."
                )
                age_confound_text = (
                    "Demographic comparators assess age confounding in the retrospective cohort."
                )
            findings_html = (
                '<div class="vox-editorial-card" style="margin-top:0.85rem;">'
                '<div class="vox-kicker" style="margin-bottom:0.25rem;">'
                "KEY RESEARCH FINDINGS</div>"
                '<p style="margin:0; font-size:0.88rem; line-height:1.6; color:#20232B;">'
                f"<strong>Top Voice Model:</strong> {top_model_text}<br>"
                f"<strong>Demographic Confounding:</strong> {age_confound_text}"
                "</p></div>"
            )
            st.markdown(findings_html, unsafe_allow_html=True)
        except Exception as exc:
            logger.warning("Could not render nested UAMS summary: %s", exc)
    elif nested_issues:
        st.info(
            "Nested cross-validation results are currently unavailable: "
            + "; ".join(nested_issues[:2])
        )

    manifest, feature_table, package, issues = _evaluation_inputs()
    if issues:
        st.info(
            "Current evaluation results are unavailable because their receipt is missing, stale, "
            "or incompatible. Run the documented extraction and grouped-evaluation workflow."
        )
        return
    receipt, metrics, predictions = package
    st.subheader("Fixed 5-fold cross-validation baseline")
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
        _render_generic_glass_table(metrics)
    with cohort_col:
        st.subheader("Analyzed cohort")
        composition = (
            feature_table.groupby("class_label")
            .agg(
                recordings=("sample_id", "count"),
                participants=("participant_id", "nunique"),
            )
            .reset_index()
            .rename(columns={"class_label": "group"})
        )
        _render_generic_glass_table(composition)
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
    analyzed_sample_ids = set(feature_table["sample_id"])
    hc_manifest = manifest[manifest["class_label"] == "HC"]
    pd_manifest = manifest[manifest["class_label"] == "PD"]
    hc_analyzed = feature_table[feature_table["class_label"] == "HC"]
    pd_analyzed = feature_table[feature_table["class_label"] == "PD"]

    hc_tot, hc_kept = len(hc_manifest), len(hc_analyzed)
    pd_tot, pd_kept = len(pd_manifest), len(pd_analyzed)
    hc_pct = (hc_kept / hc_tot * 100) if hc_tot > 0 else 0.0
    pd_pct = (pd_kept / pd_tot * 100) if pd_tot > 0 else 0.0
    hc_att = 100.0 - hc_pct
    pd_att = 100.0 - pd_pct

    hc_ages = pd.to_numeric(hc_manifest["age"], errors="coerce").dropna()
    pd_ages = pd.to_numeric(pd_manifest["age"], errors="coerce").dropna()
    hc_sd_sample = float(hc_ages.std(ddof=1)) if len(hc_ages) > 1 else 0.0
    hc_sd_pop = float(hc_ages.std(ddof=0)) if len(hc_ages) > 0 else 0.0
    pd_sd_sample = float(pd_ages.std(ddof=1)) if len(pd_ages) > 1 else 0.0
    pd_sd_pop = float(pd_ages.std(ddof=0)) if len(pd_ages) > 0 else 0.0
    hc_age_str = (
        f"{float(hc_ages.mean()):.2f} ± {hc_sd_sample:.2f} yrs (sample; pop: ±{hc_sd_pop:.2f})"
        if len(hc_ages) >= 2
        else f"{float(hc_ages.mean()):.2f} yrs"
        if len(hc_ages) == 1
        else "N/A"
    )
    pd_age_str = (
        f"{float(pd_ages.mean()):.2f} ± {pd_sd_sample:.2f} yrs (sample; pop: ±{pd_sd_pop:.2f})"
        if len(pd_ages) >= 2
        else f"{float(pd_ages.mean()):.2f} yrs"
        if len(pd_ages) == 1
        else "N/A"
    )
    if not hc_ages.empty and not pd_ages.empty:
        age_diff = abs(float(pd_ages.mean()) - float(hc_ages.mean()))
        age_diff_str = f"Δ = {age_diff:.2f} Years"
    else:
        age_diff_str = "Δ = N/A"

    excluded = manifest.loc[~manifest["sample_id"].isin(analyzed_sample_ids)]
    excl_count = len(excluded)
    if excl_count > 0:
        excl_by_class = excluded["class_label"].value_counts().to_dict()
        excl_parts = [
            f"{cls}: {excl_by_class.get(cls, 0)}"
            for cls in sorted(manifest["class_label"].unique())
        ]
        excl_aggregate_text = (
            f"{excl_count} recordings not included in feature table — {', '.join(excl_parts)}"
        )
    else:
        excl_aggregate_text = "0 recordings excluded (100% feature table retention)"

    if nested_df is not None and not voice_candidates.empty and not age_match.empty:
        best_voice_label = best_voice["model_label"]
        if age_ba > ba_mean:
            confound_title = "Age &gt; Voice"
            confound_sub = (
                f"Age baseline ({age_ba * 100:.1f}% BA) &gt; "
                f"{best_voice_label} ({ba_mean * 100:.1f}% BA)"
            )
        elif ba_mean > age_ba:
            confound_title = "Voice &gt; Age"
            confound_sub = (
                f"{best_voice_label} ({ba_mean * 100:.1f}% BA) &gt; "
                f"Age baseline ({age_ba * 100:.1f}% BA)"
            )
        else:
            confound_title = "Voice = Age"
            confound_sub = f"{best_voice_label} tied with Age baseline ({ba_mean * 100:.1f}% BA)"
    else:
        confound_title = "Comparison unavailable"
        confound_sub = "Nested demographic baselines not loaded"

    demographics_html = (
        '<div class="vox-editorial-card" style="margin-top:1.15rem;">'
        '<div class="vox-kicker" style="margin-bottom:0.35rem;">'
        "COHORT DEMOGRAPHICS, QUALITY ATTRITION &amp; CONFOUNDING ANALYSIS</div>"
        '<p style="color:#676970; font-size:0.86rem; margin-bottom:1rem; line-height:1.55;">'
        "Transparent reporting of sample retention, class-dependent attrition, and "
        "age confounding in the UAMS telephone-collected dataset."
        "</p>"
        '<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); '
        'gap:0.75rem; margin-bottom:1rem;">'
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Healthy Controls (HC) · Manifest N=41</div>'
        f'<div class="vox-qc-value" style="font-size:1.15rem; color:#39745A;">'
        f"{hc_kept} / {hc_tot} ({hc_pct:.1f}%)</div>"
        f'<div class="vox-qc-sub">Age: {hc_age_str} · '
        f"{hc_att:.1f}% attrition</div>"
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Parkinson\'s Cohort (PD) · Manifest N=40</div>'
        f'<div class="vox-qc-value" style="font-size:1.15rem; color:#A76F24;">'
        f"{pd_kept} / {pd_tot} ({pd_pct:.1f}%)</div>"
        f'<div class="vox-qc-sub">Age: {pd_age_str} · '
        f"{pd_att:.1f}% attrition</div>"
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Demographic Disparity</div>'
        f'<div class="vox-qc-value" style="font-size:1.15rem; color:#B95E46;">'
        f"{age_diff_str}</div>"
        '<div class="vox-qc-sub">Marked age disparity between diagnostic groups</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Confounding Implication</div>'
        f'<div class="vox-qc-value" style="font-size:1.15rem; color:#20232B;">'
        f"{confound_title}</div>"
        f'<div class="vox-qc-sub">{confound_sub}</div>'
        "</div>"
        "</div>"
        '<div style="background:#FAF5EC; border:1px solid #E5D3B8; '
        "border-left:3px solid var(--vox-vermilion); "
        "border-radius:4px; padding:0.85rem 1rem; font-size:0.84rem; color:#20232B; "
        'line-height:1.6;">'
        f"<strong>Methodological Note:</strong> {excl_aggregate_text}. All excluded "
        "recordings were rejected during automated quality checks. The observed performance "
        "is consistent with potential age confounding (as older healthy controls were not "
        "available in this cohort), but it does not establish a causal explanation. "
        "VoxNeuro reports this limitation transparently rather than claiming unvalidated "
        "diagnostic accuracy."
        "</div>"
        "</div>"
    )
    st.markdown(demographics_html, unsafe_allow_html=True)
    st.warning(DISCLAIMER)


def _show_research_operations() -> None:
    _page_heading(
        "Research operations",
        "Milestone 5 · Privacy-preserving study management, longitudinal tracking, "
        "and operational audit.",
    )
    st.warning(RESEARCH_DISCLAIMER)

    # Server-side RBAC gate: only authenticated researchers or admins may access study operations
    conn_auth = _runtime_db_connection()
    try:
        auth_user = _active_authenticated_user(conn_auth)
    finally:
        if conn_auth is not None:
            conn_auth.close()
    if auth_user is None or auth_user.role not in {"researcher", "admin"}:
        st.warning(
            "Researcher or Administrator authentication required to access study operations "
            "and participant records. Open the Account tab to sign in."
        )
        return

    # Database initialization check
    active_db = _current_db_path()
    if not active_db.is_file():
        st.info(
            f"The SQLite research study database has not been initialized yet at `{active_db}`."
        )
        col1, _ = st.columns([1, 2])
        with col1:
            if st.button("Initialize research database", key="m5_init_db"):
                try:
                    applied = run_migrations(active_db)
                    st.success(f"Initialized database with {len(applied)} migration(s).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Migration error: {e}")
        return

    conn = get_connection(active_db)
    try:
        tab_studies, tab_participants, tab_sessions, tab_longitudinal, tab_audit = st.tabs(
            [
                "Studies & Protocols",
                "DUA & Participants",
                "Sessions & Ingestion",
                "QC & Longitudinal Tracking",
                "Audit Trail & Reports",
            ]
        )

        with tab_studies:
            st.subheader("Registered Studies")
            studies = list_studies(conn)
            if not studies:
                st.info("No studies registered yet.")
            else:
                s_data = [
                    {
                        "Study ID": s.study_id,
                        "Name": s.study_name,
                        "Protocol": f"{s.protocol_id} (v{s.protocol_version})",
                        "Status": s.study_status,
                        "Dataset": f"{s.dataset_id} ({s.dataset_version})",
                        "Created": s.created_at[:10],
                    }
                    for s in studies
                ]
                st.dataframe(pd.DataFrame(s_data), use_container_width=True)

            with st.expander("Register New Study", expanded=False):
                with st.form("form_create_study"):
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        f_study_id = st.text_input(
                            "Study ID", placeholder="STUDY-002", key="f_s_id"
                        )
                        f_study_name = st.text_input(
                            "Study Name",
                            placeholder="Cross-Domain Longitudinal Voice",
                            key="f_s_name",
                        )
                        f_study_desc = st.text_input(
                            "Study Description", value="Longitudinal voice study", key="f_s_desc"
                        )
                    with col_s2:
                        protocols = list_protocols(conn)
                        proto_choices = [
                            f"{p.protocol_id} (v{p.protocol_version})" for p in protocols
                        ]
                        if proto_choices:
                            f_proto_sel = st.selectbox("Protocol", proto_choices, key="f_s_proto")
                            f_proto_id = f_proto_sel.split(" (v")[0]
                            f_proto_ver = f_proto_sel.split(" (v")[1].rstrip(")")
                        else:
                            f_proto_id = st.text_input(
                                "Protocol ID", value="PROTO-001", key="f_s_proto_id"
                            )
                            f_proto_ver = st.text_input(
                                "Protocol Version", value="1.0.0", key="f_s_proto_ver"
                            )
                        f_ds_id = st.text_input("Dataset ID", value="DATASET-001", key="f_s_ds_id")
                        f_ds_ver = st.text_input("Dataset Version", value="1.0", key="f_s_ds_ver")

                    submit_study = st.form_submit_button("Register Study")
                    if submit_study:
                        if not f_study_id.strip() or not f_study_name.strip():
                            st.error("Study ID and Study Name are required.")
                        else:
                            try:
                                new_study = Study(
                                    study_id=f_study_id.strip(),
                                    study_name=f_study_name.strip(),
                                    study_description=f_study_desc.strip(),
                                    protocol_id=f_proto_id.strip(),
                                    protocol_version=f_proto_ver.strip(),
                                    dataset_id=f_ds_id.strip(),
                                    dataset_version=f_ds_ver.strip(),
                                    study_status="active",
                                )
                                create_study(conn, new_study)
                                st.success(f"Study '{f_study_id.strip()}' registered successfully.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to register study: {e}")

            st.subheader("Protocol Definitions")
            protocols = list_protocols(conn)
            if not protocols:
                st.info("No protocols registered yet.")
            else:
                p_data = [
                    {
                        "Protocol ID": p.protocol_id,
                        "Version": p.protocol_version,
                        "Tasks": ", ".join(p.tasks),
                        "Expected Visits": p.visits_expected,
                        "Min Interval (days)": p.minimum_interval_days,
                    }
                    for p in protocols
                ]
                st.dataframe(pd.DataFrame(p_data), use_container_width=True)

            with st.expander("Create Protocol Definition", expanded=False):
                with st.form("form_create_protocol"):
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        f_p_id = st.text_input("Protocol ID", placeholder="PROTO-002", key="f_p_id")
                        f_p_ver = st.text_input("Protocol Version", value="1.0.0", key="f_p_ver")
                        f_p_tasks = st.multiselect(
                            "Tasks",
                            ["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
                            default=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
                            key="f_p_tasks",
                        )
                    with col_p2:
                        f_p_visits = st.number_input(
                            "Expected Visits", min_value=1, value=3, key="f_p_visits"
                        )
                        f_p_interval = st.number_input(
                            "Min Interval (Days)", min_value=0, value=7, key="f_p_interval"
                        )
                        f_p_instructions = st.text_area(
                            "Instructions",
                            value="Standard research protocol instructions.",
                            key="f_p_inst",
                        )

                    submit_proto = st.form_submit_button("Create Protocol")
                    if submit_proto:
                        if not f_p_id.strip() or not f_p_ver.strip() or not f_p_tasks:
                            st.error("Protocol ID, Version, and at least one task are required.")
                        else:
                            try:
                                new_proto = ProtocolDefinition(
                                    protocol_id=f_p_id.strip(),
                                    protocol_version=f_p_ver.strip(),
                                    tasks=list(f_p_tasks),
                                    visits_expected=int(f_p_visits),
                                    minimum_interval_days=int(f_p_interval),
                                    instructions=f_p_instructions.strip(),
                                )
                                create_protocol(conn, new_proto)
                                st.success(
                                    f"Protocol '{f_p_id.strip()} (v{f_p_ver.strip()})' "
                                    "created successfully."
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to create protocol: {e}")

        with tab_participants:
            st.subheader("Data Use Agreements (DUA)")
            duas = list_dataset_access(conn)
            if duas:
                d_table = [
                    {
                        "Dataset ID": d.dataset_id,
                        "Version": d.dataset_version,
                        "Approval": d.access_approval_state,
                        "DUA State": d.dua_state,
                        "Permitted Tasks": ", ".join(d.permitted_tasks),
                        "Restrictions": d.storage_restrictions,
                        "Expires": d.expiration_date or "No Expiry",
                    }
                    for d in duas
                ]
                st.dataframe(pd.DataFrame(d_table), use_container_width=True)
            else:
                st.info("No Data Use Agreements registered yet.")

            with st.expander("Register / Authorize Data Use Agreement (DUA)", expanded=False):
                with st.form("form_register_dua"):
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        f_dua_ds_id = st.text_input(
                            "Dataset ID", value="DATASET-001", key="f_d_ds_id"
                        )
                        f_dua_ds_ver = st.text_input(
                            "Dataset Version", value="1.0", key="f_d_ds_ver"
                        )
                        f_dua_owner = st.text_input(
                            "Dataset Owner", value="Research Consortium", key="f_d_owner"
                        )
                        f_dua_lic = st.text_input(
                            "License Type", value="Research Only", key="f_d_lic"
                        )
                    with col_d2:
                        f_dua_app_state = st.selectbox(
                            "Approval State",
                            ["APPROVED", "PENDING", "DENIED", "EXPIRED"],
                            key="f_d_app",
                        )
                        f_dua_state = st.selectbox(
                            "DUA State",
                            [
                                "ACTIVE",
                                "PENDING",
                                "NOT_REQUIRED",
                                "RESTRICTED",
                                "DENIED",
                                "EXPIRED",
                            ],
                            key="f_d_state",
                        )
                        f_dua_tasks = st.multiselect(
                            "Permitted Tasks",
                            ["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
                            default=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
                            key="f_d_tasks",
                        )
                        f_dua_exp = st.text_input(
                            "Expiration Date (YYYY-MM-DD)", value="2030-12-31", key="f_d_exp"
                        )

                    submit_dua = st.form_submit_button("Register DUA")
                    if submit_dua:
                        try:
                            dua_rec = DatasetAccessRecord(
                                dataset_id=f_dua_ds_id.strip(),
                                dataset_version=f_dua_ds_ver.strip(),
                                dataset_owner=f_dua_owner.strip(),
                                license_type=f_dua_lic.strip(),
                                access_approval_state=f_dua_app_state,
                                dua_state=f_dua_state,
                                permitted_tasks=list(f_dua_tasks),
                                permitted_data_processing_operations=[
                                    "research_audio_ingestion",
                                    "feature_extraction",
                                    "longitudinal_analysis",
                                ],
                                storage_restrictions="local_ephemeral_processing_only",
                                expiration_date=f_dua_exp.strip() or None,
                            )
                            register_dataset_access(conn, dua_rec)
                            st.success(
                                f"DUA for dataset '{f_dua_ds_id.strip()}' registered successfully."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to register DUA: {e}")

            st.subheader("Enrolled Pseudonymous Cohort")
            parts = list_participants(conn)
            if not parts:
                st.info("No participants enrolled yet.")
            else:
                p_table = [
                    {
                        "Participant ID": p.participant_id,
                        "Study ID": p.study_id,
                        "Enrollment Status": p.enrollment_status,
                        "Consent Status": p.consent_status,
                        "Consent Version": p.consent_version,
                        "Site ID": p.site_id,
                        "Metadata Safety": p.participant_metadata_status,
                    }
                    for p in parts
                ]
                st.dataframe(pd.DataFrame(p_table), use_container_width=True)

            with st.expander("Enroll New Participant", expanded=False):
                with st.form("form_register_participant"):
                    studies = list_studies(conn)
                    study_ids = [s.study_id for s in studies]
                    if study_ids:
                        f_p_study = st.selectbox("Study ID", study_ids, key="f_part_study")
                    else:
                        f_p_study = st.text_input(
                            "Study ID", value="STUDY-001", key="f_part_study_txt"
                        )
                    f_part_id = st.text_input(
                        "Participant ID (leave blank to auto-generate pseudonymous ID)",
                        placeholder="PT-XXXXXXXXXXXX",
                        key="f_part_id",
                    )
                    f_site_id = st.text_input("Site ID", value="SITE-01", key="f_part_site")
                    st.caption(
                        "Enrollment rule: New participants default to "
                        "consent_status='pending' and consent_version='none'."
                    )
                    submit_part = st.form_submit_button("Enroll Participant")
                    if submit_part:
                        try:
                            assigned_id = (
                                f_part_id.strip()
                                if f_part_id.strip()
                                else generate_pseudonymous_id()
                            )
                            new_part = Participant(
                                participant_id=assigned_id,
                                study_id=f_p_study.strip(),
                                site_id=f_site_id.strip(),
                                enrollment_status="enrolled",
                                consent_status="pending",
                                consent_version="none",
                            )
                            register_participant(conn, new_part)
                            st.success(
                                f"Enrolled participant '{assigned_id}' with pending consent."
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to enroll participant: {e}")

            st.subheader("Record Informed Consent")
            with st.expander("Record Informed Consent for Participant", expanded=False):
                with st.form("form_record_consent"):
                    col_c1, col_c2 = st.columns(2)
                    with col_c1:
                        c_part_id = st.text_input(
                            "Participant ID", placeholder="PT-XXXXXXXXXXXX", key="f_c_part_id"
                        )
                        c_study_id = st.text_input(
                            "Study ID", placeholder="STUDY-001", key="f_c_study_id"
                        )
                        c_ver = st.text_input("Consent Form Version", value="1.0", key="f_c_ver")
                    with col_c2:
                        c_tasks = st.multiselect(
                            "Permitted Recording Tasks",
                            ["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
                            default=["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
                            key="f_c_tasks",
                        )
                        c_retain = st.checkbox(
                            "Permission to retain derived features", value=True, key="f_c_retain"
                        )
                        c_long = st.checkbox(
                            "Permission for longitudinal tracking", value=True, key="f_c_long"
                        )

                    submit_consent = st.form_submit_button("Record Consent")
                    if submit_consent:
                        if not c_part_id.strip() or not c_study_id.strip():
                            st.error("Participant ID and Study ID are required.")
                        else:
                            try:
                                c_rec_id = f"CONSENT-{uuid.uuid4().hex[:8].upper()}"
                                uses = ["biomarker_research"]
                                if c_long:
                                    uses.append("longitudinal_analysis")
                                consent_rec = ConsentRecord(
                                    consent_record_id=c_rec_id,
                                    participant_id=c_part_id.strip(),
                                    study_id=c_study_id.strip(),
                                    consent_form_version=c_ver.strip(),
                                    consent_date=utc_now_iso()[:10],
                                    scope_of_permission=["voice_recording", "feature_retention"],
                                    permitted_recording_tasks=list(c_tasks),
                                    permitted_research_uses=uses,
                                    permission_to_retain_derived_features=c_retain,
                                    permission_to_retain_audio=False,
                                )
                                record_consent(conn, consent_rec)
                                st.success(f"Recorded active consent for {c_part_id.strip()}.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to record consent: {e}")

            st.subheader("Participant Withdrawal & Data Deletion")
            st.caption(
                "Withdrawal blocks future processing, marks participant as withdrawn, "
                "deletes derived acoustic features, restricts sessions, and logs an "
                "irreversible cryptographic tombstone."
            )
            w_col1, w_col2 = st.columns([2, 1])
            with w_col1:
                withdraw_id = st.text_input(
                    "Participant ID to withdraw",
                    placeholder="PT-XXXXXXXXXXXX",
                    key="m5_withdraw_id",
                )
            with w_col2:
                st.write("")
                st.write("")
                if st.button("Execute withdrawal", key="m5_withdraw_btn"):
                    if withdraw_id.strip():
                        try:
                            res = withdraw_participant(conn, withdraw_id.strip())
                            n_del = res.get("derived_features_deleted", 0)
                            n_rest = res.get("sessions_restricted", 0)
                            st.success(
                                f"Status: {res['status']} · Deleted {n_del} feature record(s) · "
                                f"Restricted {n_rest} session(s)."
                            )
                            if "tombstone_id" in res:
                                st.code(f"Tombstone ID: {res['tombstone_id']}")
                        except Exception as e:
                            st.error(f"Withdrawal failed: {e}")
                    else:
                        st.warning("Please enter a valid participant ID.")

        with tab_sessions:
            st.subheader("Research Sessions")
            sessions = list_sessions(conn)
            if not sessions:
                st.info("No research sessions created yet.")
            else:
                sess_table = [
                    {
                        "Session ID": s.session_id,
                        "Study ID": s.study_id,
                        "Participant ID": s.participant_id,
                        "Visit": f"{s.visit_label} (#{s.visit_index})",
                        "Status": s.overall_session_status,
                        "Domain": s.acquisition_domain_id,
                        "Consent Ref": s.consent_reference,
                        "Recorded": s.recording_timestamp[:16],
                    }
                    for s in sessions
                ]
                st.dataframe(pd.DataFrame(sess_table), use_container_width=True)

            with st.expander("Schedule Research Session", expanded=False):
                with st.form("form_create_session"):
                    col_sess1, col_sess2 = st.columns(2)
                    with col_sess1:
                        studies = list_studies(conn)
                        st_ids = [s.study_id for s in studies]
                        if st_ids:
                            f_sess_study = st.selectbox("Study ID", st_ids, key="f_sess_study")
                        else:
                            f_sess_study = st.text_input(
                                "Study ID", value="STUDY-001", key="f_sess_study_txt"
                            )
                        f_sess_part = st.text_input(
                            "Participant ID", placeholder="PT-XXXXXXXXXXXX", key="f_sess_part"
                        )
                        f_sess_id = st.text_input(
                            "Session ID (leave blank to auto-generate)",
                            placeholder="SESS-XXXXXXXX",
                            key="f_sess_id",
                        )
                    with col_sess2:
                        f_sess_visit = st.number_input(
                            "Visit Index", min_value=1, value=1, key="f_sess_visit"
                        )
                        f_sess_proto = st.text_input(
                            "Protocol Version", value="1.0.0", key="f_sess_proto"
                        )
                        f_sess_label = st.text_input(
                            "Visit Label",
                            value="Baseline" if f_sess_visit == 1 else f"Visit {f_sess_visit}",
                            key="f_sess_label",
                        )
                        f_sess_domain = st.selectbox(
                            "Recording Domain",
                            [
                                "uams_telephone",
                                "neurovoz_clinic",
                                "pcgita_booth",
                                "italian_parkinsons_phone",
                            ],
                            key="f_sess_domain",
                        )

                    submit_sess = st.form_submit_button("Schedule Session")
                    if submit_sess:
                        if not f_sess_part.strip():
                            st.error("Participant ID is required.")
                        else:
                            try:
                                sess_gen_id = (
                                    f_sess_id.strip()
                                    if f_sess_id.strip()
                                    else f"SESS-{uuid.uuid4().hex[:8].upper()}"
                                )
                                new_session = ResearchSession(
                                    session_id=sess_gen_id,
                                    study_id=f_sess_study.strip(),
                                    protocol_version=f_sess_proto.strip(),
                                    participant_id=f_sess_part.strip(),
                                    visit_index=int(f_sess_visit),
                                    visit_label=f_sess_label.strip(),
                                    acquisition_domain_id=f_sess_domain,
                                )
                                create_session(conn, new_session)
                                st.success(f"Session '{sess_gen_id}' created successfully.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to create session: {e}")

            st.subheader("Preflight Validation & Multi-Task Audio Ingestion")
            st.caption(
                "Preflight validation inspects all 15 operational, consent, DUA, domain, "
                "and participant authorization checks before audio is processed."
            )
            col_pre1, col_pre2 = st.columns([1, 1])
            with col_pre1:
                target_sess_id = st.text_input(
                    "Target Session ID", placeholder="SESS-XXXXXXXX", key="f_target_sess"
                )
                if st.button("Run Preflight Validation", key="btn_run_preflight"):
                    if not target_sess_id.strip():
                        st.warning("Please enter a Session ID to evaluate.")
                    else:
                        try:
                            is_auth, reason, meta = preflight_session_ingestion(
                                conn, target_sess_id.strip()
                            )
                            if is_auth:
                                st.success(f"Preflight AUTHORIZED: {reason}")
                            else:
                                st.error(f"Preflight REJECTED: {reason}")
                            with st.expander("Preflight Evaluation Details", expanded=True):
                                st.json(meta)
                        except Exception as e:
                            st.error(f"Preflight check error: {e}")

            with col_pre2:
                st.markdown("**Upload Multi-Task Audio Files (WAV)**")
                up_vowel = st.file_uploader(
                    "1. Sustained Vowel (/a/)", type=["wav"], key="m5_up_vowel"
                )
                up_ddk = st.file_uploader(
                    "2. Diadochokinetic (/pa-ta-ka/)", type=["wav"], key="m5_up_ddk"
                )
                up_conn = st.file_uploader("3. Connected Speech", type=["wav"], key="m5_up_conn")
                up_vs = st.file_uploader("4. Vowel Space (/i/, /u/)", type=["wav"], key="m5_up_vs")

                if st.button("Execute Ingestion Pipeline", key="btn_execute_ingest"):
                    if not target_sess_id.strip():
                        st.warning("Please specify a Target Session ID.")
                    elif not any([up_vowel, up_ddk, up_conn, up_vs]):
                        st.warning("Please upload at least one audio file to ingest.")
                    else:
                        try:
                            sv_rec = decode_audio(up_vowel.getvalue()) if up_vowel else None
                            cs_rec = decode_audio(up_conn.getvalue()) if up_conn else None
                            ddk_dict = (
                                {"pataka": decode_audio(up_ddk.getvalue())} if up_ddk else None
                            )
                            vs_dict = {"i": decode_audio(up_vs.getvalue())} if up_vs else None

                            ingest_res = ingest_session_multitask_audio(
                                conn,
                                session_id=target_sess_id.strip(),
                                sustained_vowel=sv_rec,
                                ddk_recordings=ddk_dict,
                                connected_speech=cs_rec,
                                vowel_space_recordings=vs_dict,
                            )
                            st.success(
                                f"Ingestion {ingest_res.overall_processing_status} · "
                                f"Tasks: {len(ingest_res.tasks)} · "
                                f"Schema: {ingest_res.schema_version}"
                            )
                            with st.expander("Ingestion Receipt Details", expanded=True):
                                st.json(ingest_res.to_dict())
                        except Exception as e:
                            st.error(f"Ingestion failed: {e}")

        with tab_longitudinal:
            st.subheader("Operational QC & Attrition")
            qc = calculate_cohort_qc_metrics(conn, suppress_small_cells=True)
            c_m = qc["cohort_metrics"]
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                st.metric("Total Enrolled", str(c_m["total_enrolled"]))
            with m_col2:
                st.metric("Active Consented", str(c_m["active_consented"]))
            with m_col3:
                st.metric("Withdrawn", str(c_m["withdrawn"]))

            st.subheader("Visit Retention & Cohort Attrition")
            attrition = calculate_cohort_attrition(conn, suppress_small_cells=True)
            if attrition["visits"]:
                att_table = [
                    {
                        "Visit Index": v["visit_index"],
                        "Participants Present": v["participants_present"],
                        "Retention Rate": f"{v['retention_rate'] * 100:.1f}%",
                        "Attrition Rate": f"{v['attrition_rate'] * 100:.1f}%",
                    }
                    for v in attrition["visits"]
                ]
                st.dataframe(pd.DataFrame(att_table), use_container_width=True)
            else:
                st.info("No visit sessions recorded yet.")

            st.subheader("Descriptive Longitudinal Acoustic Changes")
            st.caption(
                "STRICT SCIENTIFIC NOTICE: Observations are purely descriptive acoustic "
                "deltas (Visit_k - Visit_1) and do not represent disease progression "
                "or clinical status."
            )
            long_res = calculate_longitudinal_feature_changes(
                conn, task_type="sustained_vowel", suppress_small_cells=True
            )
            mean_days = long_res["visit_interval_summary"].get("mean_days", "N/A")
            st.write(
                f"Evaluated Participants: **{long_res['participants_evaluated']}** · "
                f"Mean Interval: **{mean_days} days**"
            )
            summaries = long_res.get("feature_change_summaries", {})
            if summaries:
                summary_rows = [
                    {
                        "Feature": fn,
                        "Mean Delta": f"{data.get('mean_change', 'N/A')}",
                        "Median Delta": f"{data.get('median_change', 'N/A')}",
                        "IQR Delta": f"{data.get('iqr_change', 'N/A')}",
                        "Observations": data.get("n_observations", "N/A"),
                    }
                    for fn, data in summaries.items()
                    if isinstance(data, dict)
                ]
                st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

        with tab_audit:
            st.subheader("Recent Privacy-Safe Audit Events")
            events = list_audit_events(conn, limit=15)
            if events:
                ev_data = [
                    {
                        "Timestamp (UTC)": e["timestamp_utc"],
                        "Operation": e["operation_type"],
                        "Entity Type": e["entity_type"],
                        "Entity ID": e["entity_id"],
                        "Actor Role": e["actor_role"],
                    }
                    for e in events
                ]
                st.dataframe(pd.DataFrame(ev_data), use_container_width=True)
            else:
                st.info("No audit events recorded.")

            st.subheader("M5 Research Report Exports")
            r_col1, r_col2 = st.columns(2)
            with r_col1:
                overview_rep = generate_study_overview_report(conn)
                st.download_button(
                    "Download Study Overview (JSON)",
                    json.dumps(overview_rep, indent=2),
                    "study_overview_report.json",
                    "application/json",
                    key="m5_rep_overview",
                )
                attr_rep = generate_cohort_attrition_report(conn)
                st.download_button(
                    "Download Attrition Report (CSV)",
                    export_report_to_csv(attr_rep, "visits"),
                    "cohort_attrition_report.csv",
                    "text/csv",
                    key="m5_rep_attrition_csv",
                )
            with r_col2:
                sess_rep = generate_session_completion_report(conn)
                st.download_button(
                    "Download Session Completion (CSV)",
                    export_report_to_csv(sess_rep, "session_breakdown"),
                    "session_completion_report.csv",
                    "text/csv",
                    key="m5_rep_session_csv",
                )
                long_rep = generate_longitudinal_descriptive_report(conn)
                st.download_button(
                    "Download Longitudinal Report (JSON)",
                    json.dumps(long_rep, indent=2),
                    "longitudinal_descriptive_report.json",
                    "application/json",
                    key="m5_rep_long_json",
                )
    finally:
        conn.close()


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
    dur = float(report["audio_quality"].get("duration_seconds", 0.0))
    rate = int(report["audio_quality"].get("sample_rate_hz", 0))
    voiced = float(report["audio_quality"].get("voiced_fraction", 0.0))
    finite_count = sum(
        1 for v in features.values() if isinstance(v, Real) and np.isfinite(float(v))
    )
    summary_banner = (
        '<div class="vox-editorial-hero" style="margin-bottom:1.35rem;">'
        '<div class="vox-kicker" style="margin-bottom:0.35rem;">'
        "SESSION TELEMETRY · PROVENANCE TRACEABLE</div>"
        '<h3 style="margin:0 0 0.5rem 0; font-size:1.35rem; color:#20232B;">'
        "Voice Signal Analysis Report</h3>"
        '<p style="color:#676970; font-size:0.88rem; margin:0 0 1rem 0; line-height:1.55;">'
        f"Generated {html.escape(str(report.get('generated_utc', '')))} · "
        f"Schema: {html.escape(str(report.get('features', {}).get('schema_version', '')))} · "
        "Audio quality checks passed. Schema and configuration fingerprints recorded."
        "</p>"
        '<div style="display:flex; flex-wrap:wrap; gap:0.6rem; align-items:center;">'
        '<span class="vox-badge-ok">QUALITY CHECKS PASSED</span>'
        f'<span class="vox-code-pill">Core39: {finite_count}/39 finite measures</span>'
        f'<span class="vox-unit-pill">Duration: {dur:.2f} s</span>'
        f'<span class="vox-unit-pill">Rate: {rate:,} Hz</span>'
        f'<span class="vox-unit-pill">Voiced: {voiced:.0%}</span>'
        "</div>"
        "</div>"
    )
    st.markdown(summary_banner, unsafe_allow_html=True)
    st.caption(
        f"Report {report['report_version']} · generated {report['generated_utc']} · "
        f"feature schema {report['features']['schema_version']}"
    )
    st.subheader("Audio quality")
    _render_quality_cards(report["audio_quality"])
    st.subheader("Feature measurements")
    table = _feature_frame(features)
    _render_glass_table(table)
    st.subheader("Provenance telemetry & audit record")
    schema_info = report.get("features", {})
    audio_q = report.get("audio_quality", {})
    provenance_card = (
        '<div class="vox-json-card">'
        '<div style="display:flex; justify-content:space-between; align-items:center; '
        'margin-bottom:0.75rem;">'
        '<span style="font-size:0.78rem; font-weight:700; color:#51445D; '
        'letter-spacing:0.06em;">PROVENANCE TELEMETRY &amp; AUDIT RECORD</span>'
        '<span class="vox-badge-ok">HASH RECORDED</span>'
        "</div>"
        '<div style="font-family:ui-monospace, SFMono-Regular, monospace; '
        'font-size:0.82rem; color:#20232B; line-height:1.8;">'
        f'<div><span style="color:#51445D; font-weight:600;">report_version:</span> '
        f"{html.escape(str(report.get('report_version', '0.3.0')))}</div>"
        f'<div><span style="color:#51445D; font-weight:600;">generated_utc:</span> '
        f"{html.escape(str(report.get('generated_utc', '')))}</div>"
        f'<div><span style="color:#51445D; font-weight:600;">schema_version:</span> '
        f"{html.escape(str(schema_info.get('schema_version', '')))}</div>"
        f'<div><span style="color:#51445D; font-weight:600;">schema_fingerprint:</span> '
        f"{html.escape(str(schema_info.get('schema_fingerprint', '')))}</div>"
        f'<div><span style="color:#51445D; font-weight:600;">feature_config_fingerprint:</span> '
        f"{html.escape(str(schema_info.get('feature_config_fingerprint', '')))}</div>"
        '<div><span style="color:#51445D; font-weight:600;">'
        "preprocessing_config_fingerprint:</span> "
        f"{html.escape(str(schema_info.get('preprocessing_config_fingerprint', '')))}</div>"
        f'<div><span style="color:#51445D; font-weight:600;">audio_sha256:</span> '
        f"{html.escape(str(audio_q.get('audio_sha256', 'n/a')))}</div>"
        "</div>"
        "</div>"
    )
    st.markdown(provenance_card, unsafe_allow_html=True)
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
    steps = [
        (
            "01",
            "Decode & Validate Container",
            "Decode the WAV recording and read its sample rate (8–48 kHz), channel count, "
            "duration, RMS amplitude, clipping fraction, and stereo phase correlation.",
        ),
        (
            "02",
            "Task Plausibility & Acoustic Screening",
            "Verify sustained-vowel phonation screening criteria: voiced frame fraction ≥ 15%, "
            "adequate active frame RMS level, and natural harmonic overtone structure to screen "
            "unvoiced noise and synthetic tones.",
        ),
        (
            "03",
            "Preprocess Usable Audio",
            "Average supported stereo channels after phase verification, remove DC offset, "
            "trim leading/trailing silence, verify audio, and polyphase-resample to 16 kHz.",
        ),
        (
            "04",
            "Extract 39 Versioned Acoustic Features",
            "Extract 39 Praat/Parselmouth and Librosa measures: F0 stats, jitter/shimmer, "
            "HNR, MFCCs 1–13 means & SDs, and spectral properties under schema.",
        ),
        (
            "05",
            "Audit Integrity & In-Memory Report",
            "Keep undefined values missing (never zero-fill), generate SHA-256 provenance hashes, "
            "and create a private in-memory JSON session report without persisting audio to disk.",
        ),
    ]
    for num, title, desc in steps:
        st.markdown(
            f'<div class="vox-editorial-card" style="margin-bottom:0.75rem;">'
            f'<div style="display:flex; align-items:center; gap:0.6rem; '
            'margin-bottom:0.25rem;">'
            f'<span class="vox-code-pill" style="color:var(--vox-vermilion); '
            f'font-weight:700;">{num}</span>'
            f'<strong style="color:#20232B; font-size:0.95rem;">{html.escape(title)}</strong>'
            f"</div>"
            f'<p style="margin:0.25rem 0 0 0; color:#676970; font-size:0.88rem; line-height:1.55;">'
            f"{html.escape(desc)}</p></div>",
            unsafe_allow_html=True,
        )
    audio_config = AUDIO_CONFIG
    feature_config = FEATURE_CONFIG
    st.subheader("Current extraction settings")
    settings_df = pd.DataFrame(
        [{"setting": key, "value": str(value)} for key, value in audio_config.items()]
        + [{"setting": key, "value": str(value)} for key, value in feature_config.items()]
    )
    _render_generic_glass_table(
        settings_df, headers=["Configuration Setting", "Active Parameter Value"]
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


def _on_m6_pill_change() -> None:
    picked = st.session_state.get("voxneuro_m6_pill")
    if picked == "Home":
        st.session_state["voxneuro_m6_view"] = None
        st.session_state["voxneuro_nav"] = "Overview"
        st.session_state["_prev_voxneuro_nav"] = "Overview"
    elif picked in ("Voice Assessment", "Voice Check"):
        st.session_state["voxneuro_m6_view"] = None
        st.session_state["voxneuro_nav"] = "Voice assessment"
        st.session_state["_prev_voxneuro_nav"] = "Voice assessment"
    elif picked in ("Results", "My Results"):
        st.session_state["voxneuro_m6_view"] = "Results"
    elif picked in ("Account", "My Account"):
        st.session_state["voxneuro_m6_view"] = "Account"
    elif picked:
        st.session_state["voxneuro_m6_view"] = picked


def main() -> None:
    conn = _runtime_db_connection()
    active_user = _active_authenticated_user(conn)
    token = st.session_state.get("voxneuro_auth_token")

    try:
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
                "Multi-task assessment",
                "Signal analysis",
                "Feature analysis",
                "Research model",
                "Research operations",
                "Reports",
                "Method & privacy",
            ]
            page = st.radio("Workspace", pages, key="voxneuro_nav", label_visibility="collapsed")
            st.markdown('<hr class="vox-rule">', unsafe_allow_html=True)
            st.markdown('<div class="vox-status">Local session</div>', unsafe_allow_html=True)
            st.caption("Parkinson’s research prototype · No diagnosis")
            st.caption("Audio is not saved by default.")

        # Detect direct sidebar or programmatic AppTest voxneuro_nav changes cleanly
        if "_prev_voxneuro_nav" not in st.session_state:
            st.session_state["_prev_voxneuro_nav"] = page
        elif st.session_state["_prev_voxneuro_nav"] != page:
            st.session_state["_prev_voxneuro_nav"] = page
            st.session_state["voxneuro_m6_view"] = None

        render_brand_bar(
            user_display=active_user.display_name if active_user else None,
            role=active_user.role if active_user else None,
        )
        if active_user is None:
            nav_options = [
                "Home",
                "How It Works",
                "Voice Assessment",
                "My Results",
                "About VoxNeuro",
                "My Account",
            ]
        else:
            nav_options = [
                "Home",
                "Dashboard",
                "Voice Assessment",
                "My Results",
                "How It Works",
                "About VoxNeuro",
                "My History",
                "My Account",
            ]
            if active_user.role in {"researcher", "admin"}:
                nav_options.append("Researcher")
            if active_user.role in {"ml_admin", "admin"}:
                nav_options.append("Model Admin")
            if active_user.role == "admin":
                nav_options.append("System Admin")

        st.pills(
            "Navigation",
            nav_options,
            key="voxneuro_m6_pill",
            label_visibility="collapsed",
            on_change=_on_m6_pill_change,
        )

        m6_view = st.session_state.get("voxneuro_m6_view")
        if m6_view in ("Results", "My Results"):
            show_plain_results_page(
                st.session_state.get("voxneuro_prediction"),
                st.session_state.get("voxneuro_features"),
                st.session_state.get("voxneuro_quality"),
                st.session_state.get("voxneuro_record"),
                html_report=st.session_state.get("voxneuro_html_report"),
                report_dict=st.session_state.get("voxneuro_report"),
            )
        elif m6_view == "How It Works":
            show_how_it_works()
        elif m6_view in ("About VoxNeuro", "About"):
            show_about_page()
        elif m6_view == "Privacy & Safety":
            show_privacy_and_safety()
        elif m6_view in ("Help", "Help & FAQ"):
            show_help_faq()
        elif m6_view in ("Account", "My Account"):
            acc_conn = conn or _ensure_initialized_db_connection()
            try:
                show_account_portal(acc_conn)
            finally:
                if conn is None:
                    acc_conn.close()
        elif m6_view == "Dashboard":
            if active_user is not None:
                show_user_dashboard(conn, active_user, _start_guided_assessment)
            else:
                acc_conn = conn or _ensure_initialized_db_connection()
                try:
                    show_account_portal(acc_conn)
                finally:
                    if conn is None:
                        acc_conn.close()
        elif m6_view == "My History":
            show_user_history_page(conn, active_user)
        elif m6_view == "Researcher":
            show_researcher_portal(conn, token)
        elif m6_view == "Model Admin":
            show_ml_admin_portal(conn, token)
        elif m6_view == "System Admin":
            show_system_admin_portal(conn, token, _current_db_path())
        elif page == "Overview":
            _show_overview()
        elif page == "Voice assessment":
            _show_assessment()
        elif page == "Multi-task assessment":
            _show_multitask_assessment()
        elif page == "Signal analysis":
            _show_signal_analysis()
        elif page == "Feature analysis":
            _show_features()
        elif page == "Research model":
            _show_model_assessment()
        elif page == "Research operations":
            _show_research_operations()
        elif page == "Reports":
            _show_reports()
        else:
            _show_method_privacy()

        st.markdown(
            '<div style="margin-top:3.5rem; padding-top:1.25rem; '
            "border-top:1px solid #D8D3C8; "
            'color:#898982; font-size:0.76rem; text-align:center; line-height:1.6;">'
            "VoxNeuro Research Prototype is an independent academic research project "
            "and is not affiliated with, sponsored by, or related to VoxNeuro Inc. "
            "(makers of EEG cognitive assessments). · Non-diagnostic research software."
            "</div>",
            unsafe_allow_html=True,
        )
    finally:
        if conn is not None:
            conn.close()


main()
