# VoxNeuro Milestone 3 Baseline Audit Report

**Document ID:** `VN-AUD-M3-BASE-001`  
**Milestone:** M3 (Multi-Task Speech Analysis Baseline)  
**Date:** 2026-11-11  
**Author:** Antigravity (Senior Software Architect & Verification Engineer)  
**Status:** Pre-flight Inspection Complete & Baseline Locked  

---

## 1. Executive Summary

This report establishes the verified starting baseline for Milestone 3 (M3) of the VoxNeuro project. M3 extends the system from sustained-vowel phonation (`/a/`) under the legacy 39-feature schema (`voxneuro.voice.v3`) to a comprehensive multi-task speech analysis architecture:
1. Sustained vowel phonation (`voxneuro.voice.v3`).
2. Diadochokinetic (DDK) syllable repetition (`voxneuro.task.ddk.v1`).
3. Connected speech analysis (`voxneuro.task.connected_speech.v1`).
4. Multi-vowel formant analysis and Vowel Space Area (VSA) (`voxneuro.task.vowel_space.v1`).
5. Unified session envelope (`voxneuro.voice.v4`).

In accordance with global execution rules, M3 establishes engineering and acoustic measurement capabilities without claiming clinical validation, Parkinson's diagnostic accuracy, or validated neurological biomarkers.

---

## 2. Baseline Cryptographic & Provenance Fingerprints

| Parameter | Baseline Value | Integrity Rule |
|:---|:---|:---|
| **Starting Archive Checksum (M2)** | `0faf5588a9e84c8bf1c1679eb11b336459c31923add3c91427871884eefa8327` | Verified against `VoxNeuro_M2_VERIFIED.zip.sha256` |
| **Pipeline Code Fingerprint** | `c595e14ef181902c35cbcbffa285fcf1aa1e10b5b57a338c781776ed73f47db3` | Baseline hash covering `src/`, `scripts/`, `configs/`, entrypoints |
| **Frontend Code Fingerprint** | `af9abde5877765614b0ac60d32bf7cbc3a37bf4ec2506562ed21467d1be8e62a` | WebGL asset hash covering `frontend/acoustic-visualizer/` |
| **Legacy `v3` Schema Fingerprint** | `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` | **IMMUTABLE** (Must remain identical throughout M3) |
| **Core39 Feature Count** | **39 features** | Names, order, units, and formulas locked |

---

## 3. Test Suite Baseline

All tests executed under the locked Python 3.12.16 virtual environment with `uv sync --all-extras --locked`:

- **Unit Tests:** **343 passed** (0 failed, 0 skipped).
- **Integration Tests:** **14 passed** (0 failed, 0 skipped, including 8 Streamlit AppTests).
- **Total Passing Tests:** **357 passed**.
- **Code Standards:** `ruff check .` passed with 0 errors; `ruff format --check .` confirmed 175 files formatted cleanly.
- **Project Verification:** `scripts/verify_project.py` passed all 10 required file checks, package imports, and release provenance checks.
- **Model Verification:** `scripts/verify_model.py` passed bundle reload, prediction consistency, artifact checksum, and fail-closed safety checks.

---

## 4. Current Audio Processing & Application Navigation Baseline

### 4.1 Audio Processing & Quality Gate (`voxneuro.audio`)
The baseline audio pipeline consists of:
- `decode_audio()`: Strict WAV validation, mono conversion, finite float32 normalization.
- `validate_audio()`: Sustained-vowel-specific quality checks including duration (2.0–10.0s), RMS floor (-45 dBFS), peak ceiling (-0.5 dBFS), clipping ratio (<0.5%), pitch tracking continuity, harmonic overtone ratio, and second-harmonic energy criteria specifically engineered for steady `/a/` vowels.
- `preprocess_audio()`: Bandpass filtering and trimming for sustained phonation.

> [!IMPORTANT]
> Because `validate_audio()` contains sustained-vowel-specific heuristics (e.g. harmonicity and second-harmonic requirements), it cannot be applied directly to DDK syllable trains or connected speech. An independent `validate_task_audio()` and `preprocess_task_audio()` pipeline must be developed for M3 tasks without modifying the legacy v3 gates.

### 4.2 Streamlit Application Navigation (`app.py`)
Current navigation features 7 pages:
1. `Overview`
2. `Voice assessment` (Legacy v3 sustained-vowel `/a/` workflow)
3. `Signal analysis`
4. `Feature analysis`
5. `Research model`
6. `Reports`
7. `Method & privacy`

M3 will introduce an 8th page: `Multi-task assessment` (`_show_multitask_assessment()`) in the sidebar while preserving the existing `Voice assessment` page completely intact.

---

## 5. Local Datasets & Model Artifacts

- **UAMS Dataset:** Available locally in `data/raw/uams` (81 source audio recordings, participant demographics, Core39 feature matrices, and evaluation receipts).
- **UCI Dataset:** Available locally in `data/raw/uci`.
- **Model Artifacts:** `artifacts/models/uams_logistic_research.joblib` (SHA-256 verified) and `artifacts/reports/model_evaluation/uams_nested.html`.

---

## 6. Provenance Observation & M3 Plan

As noted in `src/voxneuro/provenance.py`, any modification to `src/`, `scripts/`, or `configs/` changes the pipeline code fingerprint. During M3:
1. Multi-task modules will be authored under `src/voxneuro/audio/` and `src/voxneuro/features/tasks/`.
2. Existing M1 and M2 pipelines will be completely preserved.
3. In Phase 13, the complete M1/M2 receipt refresh sequence will be executed so that all cryptographic receipts, model bundles, and pipeline fingerprints remain synchronized.
4. M3 review bundle generation will be implemented in `scripts/build_ai_review_bundle.py --milestone m3`.

*VoxNeuro Research Prototype &bull; Milestone 3 Baseline Audit &bull; 2026-11-11*
