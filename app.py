"""Streamlit interface for private, local voice signal analysis."""

from __future__ import annotations

import hashlib
import html
import json
import logging
from numbers import Real

import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve

from voxneuro.audio.io import decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
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

logger = logging.getLogger("voxneuro.app")

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
.stApp [data-testid="stDataFrame"],
.stApp [data-testid="stTable"],
.stApp table:not(.vox-table),
.stApp .glideDataGridUl,
.stApp .dvn-scroller,
.stApp [data-testid="stDataFrame"] > div {
  background: rgba(10, 25, 34, 0.95) !important;
  background-color: rgba(10, 25, 34, 0.95) !important;
  color: #F3F7F5 !important;
  border: 1px solid rgba(85, 217, 193, 0.25) !important;
  border-radius: 12px !important;
}
.stApp [data-testid="stJson"], .react-json-view {
  background: rgba(10, 25, 34, 0.92) !important;
  background-color: rgba(10, 25, 34, 0.92) !important;
  border: 1px solid rgba(85, 217, 193, 0.28) !important;
  border-radius: 12px !important;
  padding: 1.15rem !important;
  backdrop-filter: blur(16px) !important;
  -webkit-backdrop-filter: blur(16px) !important;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4) !important;
  color: #E2F5F1 !important;
}
.stApp [data-testid="stJson"] * {
  color: #55D9C1 !important;
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
  border: 1px solid rgba(85, 217, 193, 0.32);
  border-radius: 14px;
  overflow-x: auto;
  background: linear-gradient(135deg, rgba(12, 29, 39, 0.85) 0%, rgba(7, 19, 27, 0.92) 100%);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08),
              0 0 25px rgba(85, 217, 193, 0.1);
  margin: 1rem 0 1.35rem;
}
.vox-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.86rem;
  color: #EDF6F7;
  text-align: left;
}
.vox-table th {
  background: linear-gradient(90deg, rgba(18, 48, 62, 0.98) 0%, rgba(12, 34, 45, 0.98) 100%);
  color: #55D9C1;
  padding: 0.85rem 1.25rem;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  border-bottom: 2px solid rgba(85, 217, 193, 0.35);
  white-space: nowrap;
}
.vox-table td {
  padding: 0.8rem 1.25rem;
  border-bottom: 1px solid rgba(38, 62, 71, 0.5);
  vertical-align: middle;
}
.vox-table tr:nth-child(even) { background: rgba(16, 38, 50, 0.35); }
.vox-table tr:last-child td { border-bottom: 0; }
.vox-table tr:hover td {
  background: linear-gradient(90deg, rgba(85, 217, 193, 0.15) 0%, rgba(85, 217, 193, 0.05) 100%)
              !important;
  transition: background 0.18s ease;
}
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
.vox-json-card {
  background: rgba(10, 25, 34, 0.85);
  border: 1px solid rgba(85, 217, 193, 0.22);
  border-radius: 10px;
  padding: 1rem 1.25rem;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  overflow-x: auto;
  margin: 0.5rem 0 1rem;
}
.vox-json-card pre {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: 0.84rem;
  color: #55D9C1;
  line-height: 1.55;
  background: transparent !important;
}
.vox-json-card code {
  color: #67E2CE;
  background: transparent !important;
}
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
  background: linear-gradient(135deg, rgba(16, 44, 56, 0.94) 0%, rgba(9, 26, 36, 0.98) 100%)
              !important;
  background-color: rgba(14, 34, 45, 0.96) !important;
  color: #F3F7F5 !important;
  border: 1px solid rgba(85, 217, 193, 0.45) !important;
  border-radius: 10px !important;
  padding: 0.6rem 1.35rem !important;
  font-weight: 650 !important;
  font-size: 0.88rem !important;
  letter-spacing: 0.025em !important;
  backdrop-filter: blur(16px) !important;
  -webkit-backdrop-filter: blur(16px) !important;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.12),
              0 0 14px rgba(85, 217, 193, 0.12) !important;
  transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
  text-decoration: none !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 0.5rem !important;
}
html body div.stApp button *,
html body div.stApp button p,
html body div.stApp button span,
html body div.stApp button div,
html body div.stApp a[kind="secondary"] *,
html body div.stApp a[kind="secondary"] p,
html body div.stApp a[kind="secondary"] span,
html body div.stApp a[role="button"] *,
html body div.stApp a[download] *,
html body div.stApp .stButton > button *,
html body div.stApp .stDownloadButton > button *,
html body div.stApp .stDownloadButton > a *,
html body div.stApp [data-testid*="DownloadButton"] *,
html body div.stApp [data-testid*="downloadButton"] *,
html body div.stApp div[data-testid="stDownloadButton"] * {
  color: #F3F7F5 !important;
}
html body div.stApp button svg,
html body div.stApp .stDownloadButton svg,
html body div.stApp div[data-testid="stDownloadButton"] svg {
  fill: #55D9C1 !important;
  stroke: #55D9C1 !important;
}
html body div.stApp button:hover,
html body div.stApp button:hover:not(:disabled),
html body div.stApp button:hover:enabled,
html body div.stApp button[kind="secondary"]:hover,
html body div.stApp button[kind="secondary"]:hover:not(:disabled),
html body div.stApp a[kind="secondary"]:hover,
html body div.stApp a[role="button"]:hover,
html body div.stApp a[download]:hover,
html body div.stApp [data-testid*="DownloadButton"] button:hover,
html body div.stApp [data-testid*="DownloadButton"] button:hover:not(:disabled),
html body div.stApp [data-testid*="DownloadButton"] a:hover,
html body div.stApp [data-testid*="DownloadButton"] a:hover:not(:disabled),
html body div.stApp [data-testid*="downloadButton"] button:hover,
html body div.stApp [data-testid*="downloadButton"] button:hover:not(:disabled),
html body div.stApp [data-testid*="downloadButton"] a:hover,
html body div.stApp [data-testid*="downloadButton"] a:hover:not(:disabled),
html body div.stApp [data-testid*="baseButton"]:hover,
html body div.stApp [data-testid*="baseButton"]:hover:not(:disabled),
html body div.stApp [data-testid*="BaseButton"]:hover,
html body div.stApp [data-testid*="BaseButton"]:hover:not(:disabled),
html body div.stApp [data-testid*="stBaseButton"]:hover,
html body div.stApp [data-testid*="stBaseButton"]:hover:not(:disabled),
html body div.stApp .stButton > button:hover,
html body div.stApp .stButton > button:hover:not(:disabled),
html body div.stApp .stDownloadButton > button:hover,
html body div.stApp .stDownloadButton > button:hover:not(:disabled),
html body div.stApp .stDownloadButton > a:hover,
html body div.stApp .stDownloadButton > a:hover:not(:disabled),
html body div.stApp div[data-testid="stDownloadButton"] button:hover,
html body div.stApp div[data-testid="stDownloadButton"] button:hover:not(:disabled),
html body div.stApp div[data-testid="stDownloadButton"] a:hover,
html body div.stApp div[data-testid="stDownloadButton"] a:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(26, 82, 100, 0.98) 0%, rgba(14, 52, 68, 0.98) 100%)
              !important;
  background-color: rgba(20, 64, 78, 0.98) !important;
  border: 1px solid #55D9C1 !important;
  border-color: #55D9C1 !important;
  color: #FFFFFF !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.55), 0 0 24px rgba(85, 217, 193, 0.5),
              inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
  transform: translateY(-2px) !important;
}
html body div.stApp button:hover *,
html body div.stApp button:hover:not(:disabled) *,
html body div.stApp a[kind="secondary"]:hover *,
html body div.stApp a[role="button"]:hover *,
html body div.stApp a[download]:hover *,
html body div.stApp [data-testid*="DownloadButton"] *:hover,
html body div.stApp [data-testid*="downloadButton"] *:hover,
html body div.stApp .stDownloadButton *:hover,
html body div.stApp div[data-testid="stDownloadButton"] *:hover,
html body div.stApp div[data-testid="stDownloadButton"] button:hover *,
html body div.stApp div[data-testid="stDownloadButton"] a:hover * {
  color: #FFFFFF !important;
  fill: #55D9C1 !important;
}
html body div.stApp button:focus,
html body div.stApp button:focus-visible,
html body div.stApp div[data-testid="stDownloadButton"] button:focus,
html body div.stApp div[data-testid="stDownloadButton"] a:focus {
  background: linear-gradient(135deg, rgba(20, 68, 84, 0.98) 0%, rgba(12, 44, 58, 0.98) 100%)
              !important;
  background-color: rgba(16, 56, 70, 0.98) !important;
  border-color: #55D9C1 !important;
  outline: 2px solid rgba(85, 217, 193, 0.6) !important;
  outline-offset: 2px !important;
  color: #FFFFFF !important;
}
html body div.stApp button:active,
html body div.stApp [data-testid*="DownloadButton"] button:active,
html body div.stApp [data-testid*="DownloadButton"] a:active,
html body div.stApp div[data-testid="stDownloadButton"] button:active,
html body div.stApp div[data-testid="stDownloadButton"] a:active {
  background: rgba(16, 50, 64, 0.98) !important;
  border-color: #55D9C1 !important;
  color: #FFFFFF !important;
  transform: translateY(0px) !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4), 0 0 12px rgba(85, 217, 193, 0.25) !important;
}
html body div.stApp button[kind="primary"],
html body div.stApp [data-testid="baseButton-primary"],
html body div.stApp [data-testid="stBaseButton-primary"],
html body div.stApp button[data-testid*="primary"] {
  background: linear-gradient(135deg, #136359 0%, #0B423B 100%) !important;
  background-color: #136359 !important;
  border: 1px solid rgba(85, 217, 193, 0.75) !important;
  color: #FFFFFF !important;
  box-shadow: 0 4px 20px rgba(19, 99, 89, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.2),
              0 0 14px rgba(85, 217, 193, 0.25) !important;
}
html body div.stApp button[kind="primary"]:hover,
html body div.stApp button[kind="primary"]:hover:not(:disabled),
html body div.stApp [data-testid="baseButton-primary"]:hover,
html body div.stApp [data-testid="stBaseButton-primary"]:hover,
html body div.stApp button[data-testid*="primary"]:hover {
  background: linear-gradient(135deg, #187D70 0%, #0E5249 100%) !important;
  background-color: #187D70 !important;
  border-color: #55D9C1 !important;
  color: #FFFFFF !important;
  box-shadow: 0 8px 30px rgba(85, 217, 193, 0.5), 0 0 26px rgba(85, 217, 193, 0.4),
              inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
  transform: translateY(-2px) !important;
}
html body div.stApp button[kind="primary"] *,
html body div.stApp [data-testid="baseButton-primary"] *,
html body div.stApp [data-testid="stBaseButton-primary"] * {
  color: #FFFFFF !important;
}
.stApp [data-testid="stAlert"] {
  background: rgba(10, 25, 34, 0.78) !important;
  backdrop-filter: blur(14px) !important;
  -webkit-backdrop-filter: blur(14px) !important;
  border: 1px solid rgba(85, 217, 193, 0.3) !important;
  border-radius: 12px !important;
  color: #EDF6F7 !important;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3) !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] > div { gap: 0.38rem; }
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
  background: rgba(12, 29, 39, 0.45);
  border: 1px solid rgba(38, 62, 71, 0.45);
  border-radius: 9px;
  padding: 0.5rem 0.85rem;
  transition: all 0.2s ease;
  cursor: pointer;
  color: #C1D5D2;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background: rgba(85, 217, 193, 0.1);
  border-color: rgba(85, 217, 193, 0.4);
  color: #FFFFFF;
  transform: translateX(2px);
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"],
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(85, 217, 193, 0.24), rgba(85, 217, 193, 0.08));
  border-color: rgba(85, 217, 193, 0.75);
  color: #FFFFFF;
  box-shadow: 0 0 16px rgba(85, 217, 193, 0.2);
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
audio {
  filter: invert(0.92) hue-rotate(180deg) brightness(0.95);
  border-radius: 28px;
  margin: 0.6rem 0;
  width: 100%;
}
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: rgba(7, 19, 27, 0.7);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb {
  background: rgba(85, 217, 193, 0.3);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(85, 217, 193, 0.6);
}
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
        min_harmonic_overtone_fraction=float(audio_cfg["min_harmonic_overtone_fraction"]),
        min_second_harmonic_fraction=float(audio_cfg["min_second_harmonic_fraction"]),
        min_waveform_kurtosis=float(audio_cfg["min_waveform_kurtosis"]),
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
            "audio_sha256": hashlib.sha256(payload).hexdigest(),
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
        _render_acoustic_benchmark_cards(st.session_state["voxneuro_features"])
        if quality is not None and record is not None:
            _render_decision_gate_panel(st.session_state["voxneuro_features"], quality)
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
            f'<td style="color:#D6E5E3; font-size:0.83rem;">{method}</td>'
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


def _render_decision_gate_panel(features: dict, quality: AudioQuality) -> None:
    finite_count = sum(
        1 for v in features.values() if isinstance(v, Real) and np.isfinite(float(v))
    )
    schema_ver = html.escape(str(features.get("schema_version", "voxneuro.voice.v3")))
    html_markup = (
        '<div class="vox-glass-card" style="margin-top:1.15rem; '
        'border-color: rgba(85, 217, 193, 0.35);">'
        '<div class="vox-kicker" style="margin-bottom:0.35rem;">'
        "RESEARCH WORKFLOW &amp; DOMAIN SAFETY AUDIT</div>"
        '<p style="color:#A7B8B5; font-size:0.86rem; margin-bottom:1rem; line-height:1.5;">'
        "Evaluates the 5-stage software intake and domain verification workflow before any "
        "downstream analysis."
        "</p>"
        '<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); '
        'gap:0.75rem; margin-bottom:1rem;">'
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 1 · Quality Gate</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; color:#55D9C1;">PASS</div>'
        f'<div class="vox-qc-sub">{quality.duration_seconds:.1f}s · '
        f"{quality.voiced_fraction:.0%} voiced · "
        f"{quality.clipping_fraction:.2%} clipped</div>"
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 2 · Task Plausibility</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; color:#55D9C1;">HEURISTIC PASS</div>'
        '<div class="vox-qc-sub">Phonated-vowel criteria met (acoustic screening)</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 3 · Feature Extraction</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; color:#55D9C1;">PROCESSED</div>'
        f'<div class="vox-qc-sub">{finite_count}/39 finite measures ({schema_ver})</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 4 · Domain Verification</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; color:#E5B56D;">NOT VALIDATED</div>'
        '<div class="vox-qc-sub">Recording-domain compatibility unestablished</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Stage 5 · Safety Policy</div>'
        '<div class="vox-qc-value" style="font-size:1.05rem; color:#55D9C1;">ABSTAIN</div>'
        '<div class="vox-qc-sub">Diagnosis withheld (Fail-closed protocol)</div>'
        "</div>"
        "</div>"
        '<div style="background:rgba(229, 181, 109, 0.08); '
        "border:1px solid rgba(229, 181, 109, 0.28); border-radius:8px; padding:0.85rem 1rem; "
        'font-size:0.84rem; color:#EDF6F7; line-height:1.55;">'
        '<strong style="color:#E5B56D;">Protocol Rationale:</strong> The UAMS research baseline '
        "was collected over telephone lines (8 kHz PSTN) in an uncontrolled clinical trial. "
        "External recording devices (microphones, consumer headsets, audio interfaces) exhibit "
        "distinct acoustic transfer functions and frequency responses. To prevent uncalibrated "
        "predictions and false positives, VoxNeuro operates a strict fail-closed safety gate: "
        "39 acoustic measurements and session telemetry are exported, but disease "
        "classification is ethically and technically abstained."
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

    html = (
        '<div class="vox-glass-card" style="margin-top:1.25rem;">'
        '<div class="vox-kicker" style="margin-bottom:0.4rem;">'
        "CORE ACOUSTIC MEASUREMENTS · SUSTAINED /A/ PHONATION</div>"
        '<p style="color:#A7B8B5; font-size:0.86rem; margin-bottom:1rem; line-height:1.5;">'
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
    st.markdown(html, unsafe_allow_html=True)


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
        "#E5B56D" if "age" in model else "#68746F" if model == "dummy" else "#55D9C1"
        for model in grouped.index
    ]
    fig = Figure(figsize=(8.4, 3.8))
    ax = fig.subplots()
    fig.patch.set_facecolor("#0C1D27")
    fig.patch.set_alpha(0.92)
    ax.set_facecolor("#08151D")
    ax.barh(
        grouped.index,
        grouped["mean"],
        xerr=grouped["std"].fillna(0),
        color=colors,
        alpha=0.9,
        capsize=3,
        error_kw={"ecolor": "#EDF6F7", "elinewidth": 1.2},
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel(
        "Balanced accuracy · mean ± SD across grouped folds",
        color="#EDF6F7",
        fontsize=10,
    )
    ax.set_title("Internal UAMS comparison", color="#55D9C1", fontsize=11.5, fontweight="600")
    ax.grid(axis="x", color="#55D9C1", alpha=0.18, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#263E47")
    ax.tick_params(axis="y", length=0, labelcolor="#F3F7F5", labelsize=9.5)
    ax.tick_params(axis="x", colors="#A7B8B5", labelsize=9)
    fig.tight_layout()
    return fig


def _nested_model_comparison_figure(nested_df: pd.DataFrame):
    df_sorted = nested_df.sort_values("balanced_accuracy_mean")
    colors = [
        "#E5B56D" if "age" in str(m) else "#68746F" if str(m) == "dummy" else "#55D9C1"
        for m in df_sorted["model"]
    ]
    labels = (
        df_sorted["model_label"].tolist()
        if "model_label" in df_sorted.columns
        else df_sorted["model"].tolist()
    )
    fig = Figure(figsize=(9.2, 4.4))
    ax = fig.subplots()
    fig.patch.set_facecolor("#0C1D27")
    fig.patch.set_alpha(0.92)
    ax.set_facecolor("#08151D")
    ax.barh(
        labels,
        df_sorted["balanced_accuracy_mean"],
        xerr=df_sorted["balanced_accuracy_repeat_sd"].fillna(0),
        color=colors,
        alpha=0.9,
        capsize=3,
        error_kw={"ecolor": "#EDF6F7", "elinewidth": 1.2},
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel(
        "Balanced accuracy · repeated nested-CV mean ± SD",
        color="#EDF6F7",
        fontsize=10,
    )
    ax.set_title(
        "Repeated Nested CV: 7 Voice Models vs Confounded Baselines",
        color="#55D9C1",
        fontsize=11.5,
        fontweight="600",
    )
    ax.grid(axis="x", color="#55D9C1", alpha=0.18, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#263E47")
    ax.tick_params(axis="y", length=0, labelcolor="#F3F7F5", labelsize=9)
    ax.tick_params(axis="x", colors="#A7B8B5", labelsize=9)
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
    fig.patch.set_facecolor("#0C1D27")
    fig.patch.set_alpha(0.92)
    ax.set_facecolor("#08151D")
    image = ax.imshow(matrix, cmap="GnBu", vmin=0)
    for (row, column), value in np.ndenumerate(matrix):
        ax.text(
            column,
            row,
            str(value),
            ha="center",
            va="center",
            color="#FFFFFF",
            fontsize=13,
            fontweight="bold",
        )
    ax.set_xticks([0, 1], labels=["HC", "PD"], color="#EDF6F7")
    ax.set_yticks([0, 1], labels=["HC", "PD"], color="#EDF6F7")
    ax.set_xlabel("Predicted group", color="#EDF6F7")
    ax.set_ylabel("Reference group", color="#EDF6F7")
    ax.set_title(
        "Logistic regression · held-out participants",
        color="#55D9C1",
        fontsize=10.5,
        fontweight="600",
    )
    cbar = fig.colorbar(image, ax=ax, label="Participants")
    cbar.ax.yaxis.label.set_color("#EDF6F7")
    cbar.ax.tick_params(colors="#A7B8B5")
    for spine in ax.spines.values():
        spine.set_color("#263E47")
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
    fig.patch.set_facecolor("#0C1D27")
    fig.patch.set_alpha(0.92)
    ax.set_facecolor("#08151D")
    ax.plot(
        false_positive,
        true_positive,
        color="#55D9C1",
        linewidth=2.2,
        label=f"ROC AUC {auc:.3f}",
    )
    ax.plot(
        [0, 1],
        [0, 1],
        color="#E5B56D",
        linewidth=1,
        linestyle="--",
        label="Chance (0.50)",
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False positive rate", color="#EDF6F7")
    ax.set_ylabel("True positive rate", color="#EDF6F7")
    ax.set_title(
        "Pooled out-of-fold ranking",
        color="#55D9C1",
        fontsize=10.5,
        fontweight="600",
    )
    ax.legend(frameon=False, loc="lower right", labelcolor="#EDF6F7")
    ax.grid(color="#55D9C1", alpha=0.18, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#A7B8B5")
    for spine in ax.spines.values():
        spine.set_color("#263E47")
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

    nested_path = PROJECT_ROOT / "data" / "processed" / "nested_uams_summary.csv"
    if nested_path.is_file():
        try:
            nested_df = pd.read_csv(nested_path)
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
            _render_generic_glass_table(
                nested_df[summary_cols].copy(),
                headers=[
                    "Model Family",
                    "Bal. Acc. Mean",
                    "Bal. Acc. SD",
                    "ROC-AUC",
                    "Sensitivity",
                    "Specificity",
                    "F1 Score",
                ],
            )
            findings_html = (
                '<div class="vox-glass-card" style="margin-top:0.85rem;">'
                '<div class="vox-qc-label" style="color:#55D9C1; margin-bottom:0.25rem;">'
                "KEY RESEARCH FINDINGS</div>"
                '<p style="margin:0; font-size:0.88rem; line-height:1.55; color:#EDF6F7;">'
                "<strong>Top Voice Model:</strong> Extra Trees achieved the highest voice-only "
                "discrimination at <strong>76.6% balanced accuracy</strong> (0.766 ± 0.019) and "
                "<strong>0.797 ROC-AUC</strong>.<br>"
                "<strong>Demographic Confounding:</strong> The age-only logistic baseline "
                "achieved <strong>83.9% balanced accuracy</strong> in this markedly "
                "age-imbalanced cohort in UAMS (PD participants were older on average). This "
                "demonstrates that voice discrimination alone must not be mistaken for diagnostic "
                "specificity without age-matched controls."
                "</p></div>"
            )
            st.markdown(findings_html, unsafe_allow_html=True)
        except Exception as exc:
            logger.warning("Could not render nested UAMS summary: %s", exc)

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
    demographics_html = (
        '<div class="vox-glass-card" style="margin-top:1.15rem;">'
        '<div class="vox-kicker" style="margin-bottom:0.35rem;">'
        "COHORT DEMOGRAPHICS, QUALITY ATTRITION &amp; CONFOUNDING ANALYSIS</div>"
        '<p style="color:#A7B8B5; font-size:0.86rem; margin-bottom:1rem; line-height:1.5;">'
        "Transparent reporting of sample retention, class-dependent attrition, and "
        "age confounding in the UAMS telephone-collected dataset."
        "</p>"
        '<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); '
        'gap:0.75rem; margin-bottom:1rem;">'
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Healthy Controls (HC)</div>'
        '<div class="vox-qc-value" style="font-size:1.15rem; color:#67E2CE;">41 / 41 (100%)</div>'
        '<div class="vox-qc-sub">Mean Age: 47.73 ± 14.33 yrs · 0% attrition</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Parkinson\'s Cohort (PD)</div>'
        '<div class="vox-qc-value" style="font-size:1.15rem; color:#E5B56D;">37 / 40 (92.5%)</div>'
        '<div class="vox-qc-sub">Mean Age: 67.04 ± 8.98 yrs · 7.5% clipping attrition</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Demographic Disparity</div>'
        '<div class="vox-qc-value" style="font-size:1.15rem; color:#E27F80;">Δ = 19.3 Years</div>'
        '<div class="vox-qc-sub">Standardized diff: d = -1.61 (p &lt; 0.001)</div>'
        "</div>"
        '<div class="vox-quality-card">'
        '<div class="vox-qc-label">Confounding Implication</div>'
        '<div class="vox-qc-value" style="font-size:1.15rem; color:#EDF6F7;">Age &gt; Voice</div>'
        '<div class="vox-qc-sub">Age baseline (83.9% BA) &gt; Extra Trees (76.6% BA)</div>'
        "</div>"
        "</div>"
        '<div style="background:rgba(18, 39, 51, 0.6); border:1px solid rgba(85, 217, 193, 0.2); '
        "border-radius:8px; padding:0.85rem 1rem; font-size:0.84rem; color:#EDF6F7; "
        'line-height:1.55;">'
        "<strong>Methodological Note:</strong> All 3 excluded UAMS recordings "
        "(uams-045, uams-046, uams-047) belonged to the PD class and were rejected for "
        "digital clipping. The observed performance is consistent with potential age "
        "confounding (as older healthy controls were not available in this cohort), but it "
        "does not establish a causal explanation. VoxNeuro reports this limitation "
        "transparently rather than claiming unvalidated diagnostic accuracy."
        "</div>"
        "</div>"
    )
    st.markdown(demographics_html, unsafe_allow_html=True)
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
    dur = float(report["audio_quality"].get("duration_seconds", 0.0))
    rate = int(report["audio_quality"].get("sample_rate_hz", 0))
    voiced = float(report["audio_quality"].get("voiced_fraction", 0.0))
    finite_count = sum(
        1 for v in features.values() if isinstance(v, Real) and np.isfinite(float(v))
    )
    summary_banner = (
        '<div class="vox-glass-hero" style="margin-bottom:1.35rem;">'
        '<div class="vox-kicker" style="margin-bottom:0.35rem;">'
        "SESSION TELEMETRY · PROVENANCE TRACEABLE</div>"
        '<h3 style="margin:0 0 0.5rem 0; font-size:1.35rem; color:#F3F7F5;">'
        "Voice Signal Analysis Report</h3>"
        '<p style="color:#A7B8B5; font-size:0.88rem; margin:0 0 1rem 0; line-height:1.55;">'
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
        '<span style="font-size:0.78rem; font-weight:700; color:#55D9C1; '
        'letter-spacing:0.06em;">PROVENANCE TELEMETRY &amp; AUDIT RECORD</span>'
        '<span class="vox-badge-ok">HASH RECORDED</span>'
        "</div>"
        '<div style="font-family:ui-monospace, SFMono-Regular, monospace; '
        'font-size:0.82rem; color:#C1D5D2; line-height:1.75;">'
        f'<div><span style="color:#55D9C1;">report_version:</span> '
        f"{html.escape(str(report.get('report_version', '0.3.0')))}</div>"
        f'<div><span style="color:#55D9C1;">generated_utc:</span> '
        f"{html.escape(str(report.get('generated_utc', '')))}</div>"
        f'<div><span style="color:#55D9C1;">schema_version:</span> '
        f"{html.escape(str(schema_info.get('schema_version', '')))}</div>"
        f'<div><span style="color:#55D9C1;">schema_fingerprint:</span> '
        f"{html.escape(str(schema_info.get('schema_fingerprint', '')))}</div>"
        f'<div><span style="color:#55D9C1;">feature_config_fingerprint:</span> '
        f"{html.escape(str(schema_info.get('feature_config_fingerprint', '')))}</div>"
        f'<div><span style="color:#55D9C1;">preprocessing_config_fingerprint:</span> '
        f"{html.escape(str(schema_info.get('preprocessing_config_fingerprint', '')))}</div>"
        f'<div><span style="color:#55D9C1;">audio_sha256:</span> '
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
            "Speech Task Verification",
            "Verify sustained vowel phonation criteria: voiced frame fraction ≥ 40%, positive "
            "SNR, and second-harmonic energy > 5% to reject synthetic sine and square waves.",
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
            f'<div class="vox-glass-card" style="margin-bottom:0.75rem;">'
            f'<div class="vox-step"><strong>{num}</strong>{html.escape(title)}</div>'
            f'<p style="margin:0.35rem 0 0 0; color:#A7B8B5; font-size:0.88rem; line-height:1.5;">'
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

    st.markdown(
        '<div style="margin-top:3.5rem; padding-top:1.25rem; '
        "border-top:1px solid rgba(85, 217, 193, 0.15); "
        'color:#7B928E; font-size:0.76rem; text-align:center; line-height:1.6;">'
        "VoxNeuro Research Prototype is an independent academic research project "
        "and is not affiliated with, sponsored by, or related to VoxNeuro Inc. "
        "(makers of EEG cognitive assessments). · Non-diagnostic research software."
        "</div>",
        unsafe_allow_html=True,
    )


main()
