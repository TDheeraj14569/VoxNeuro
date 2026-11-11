# VoxNeuro Milestone 1: Completion Report
## Dataset Acquisition, Reproducible Processing, Model Evaluation, Training and M1 Verified Archive

**Date:** 2026-11-11  
**Milestone:** M1 – Dataset Acquisition, Reproducible Processing, Model Evaluation, Training and M1 Verified Archive  
**Agent:** Antigravity (Gemini 3.8 Flash High)  
**Target Environment:** CPython 3.12.16, Windows 11 via `uv` 0.13.7  

---

## 1. Executive Summary

Milestone 1 (M1) of the VoxNeuro research prototype has been fully completed in strict accordance with the scientific methodology, reproducibility requirements, and privacy/safety constraints.

Key achievements:
1. **Official Research Dataset Acquisition:** Acquired both primary research datasets—the UAMS Parkinson's Voice dataset from Figshare (DOI `10.6084/m9.figshare.23849127.v1`) and the UCI Parkinson's Disease Classification dataset 470 (DOI `10.24432/C5MS4X`).
2. **Cryptographic Integrity & Archive Validation:** Both UAMS audio archives matched the exact built-in MD5 constants (`PD_AH.zip`: `2e525e419abdad509e5cbf201e30ef36`, `HC_AH.zip`: `55fd33d365380372dcfbae4f7f520246`). UCI RAR extraction was executed using native libarchive bsdtar and verified against `configs/uci470_schema.json`.
3. **Manifest & Demographic Confounding Audit:** Generated `data/processed/feature_manifest.csv` containing 81 unique participants (40 PD, 41 HC). Documented massive age disparity between cohorts (HC mean age 47.73 ± 14.33 vs. PD mean age 67.04 ± 8.98, Mann-Whitney U = 223.0, p = 1.75×10⁻⁸, SMD = -1.61).
4. **Core39 Acoustic Feature Extraction:** Successfully processed all 81 recordings under the documented reviewed clipping exclusion policy (`configs/reviewed_exclusions.yaml`), accepting 78 recordings (41 HC, 37 PD) and appropriately rejecting the 3 clipped PD samples.
5. **Grouped & Repeated Nested Cross-Validation:** Executed 5-fold participant-grouped evaluation and 5x3 repeated nested cross-validation across 8 model families plus age-only and age-plus-voice comparators. Extra Trees achieved top voice-only balanced accuracy (**0.766 ± 0.008**), but was substantially out-performed by the age-only baseline (**0.839 ± 0.007**), confirming that acoustic models in this cohort primarily reflect demographic confounding rather than isolated Parkinson's pathophysiology.
6. **Research Reference Model Training & Verification:** Trained the selected L2 logistic reference model on all 78 valid development cohort participants, generating `artifacts/models/uams_logistic_research.joblib` and its matching SHA-256 sidecar. Successfully passed `scripts/verify_model.py`.
7. **Separate UCI Benchmark Evaluation:** Conducted independent 5-fold grouped evaluation on UCI's 756 recordings (252 participants, 752 acoustic predictors), including exact duplicate row sensitivity analysis.
8. **Streamlit App Integration:** Verified Streamlit application with AppTests. The research section properly renders live evaluation reports, validates model checksums, and enforces safety boundaries: user microphone disease prediction remains strictly disabled (`allow_user_microphone_inference: false`).
9. **Full Regression & M0 Preservation:** Verified all 318 automated pytest unit and integration tests pass with 0 failures. Ruff linting and formatting are 100% clean.
10. **Canonical Privacy-Safe M1 Distribution Package:** Built and verified `VoxNeuro_M1_VERIFIED.zip` via `scripts.build_ai_review_bundle --output VoxNeuro_M1_VERIFIED.zip`, providing complete source at the root and aggregate-only research evidence under `review_evidence/`, with zero private audio, participant-level data, or model binaries included.

---

## 2. Phase-by-Phase Execution Details

### Phase 0: Baseline Environment Verification
- Verified Python environment: CPython 3.12.16 on Windows 11.
- Locked dependencies: 71 packages resolved and locked via `uv sync --all-extras --locked`.
- Disk space: 254.68 GB free.
- Archive tools: Windows 11 system bsdtar 3.8.4 (libarchive 3.8.4) confirmed with native RAR archive handling.
- Full pytest suite: 318 passed in 24.76s.
- Created `docs/audit/M1_BASELINE_REPORT.md`.

### Phase 1: UAMS Dataset Acquisition
- Downloaded official Figshare files to `data/raw/uams/`:
  - `Demographics_age_sex.xlsx`: 122,854 bytes, SHA-256 `af622ccbd8b8051f19326688ad4138c4c72983f4b21aaae3ca58f6e1566a7305`
  - `PD_AH.zip`: 2,247,417 bytes, MD5 `2e525e419abdad509e5cbf201e30ef36` (exact match to Figshare API)
  - `HC_AH.zip`: 2,007,786 bytes, MD5 `55fd33d365380372dcfbae4f7f520246` (exact match to Figshare API)
- Created `docs/audit/M1_DATA_ACQUISITION_REPORT.md`.

### Phase 2: UAMS Dataset Inspection & Manifest
- Executed `uv run python scripts/inspect_dataset.py --dataset uams`.
  - Safely verified and staged extraction to `data/interim/uams/pd` (40 WAVs) and `data/interim/uams/hc` (41 WAVs).
  - All 81 recordings validated: WAVEX/FLOAT, 8000 Hz mono, 0 corrupt files, 0 duplicate waveforms.
- Executed `uv run python scripts/build_manifest.py`.
  - Built `data/processed/feature_manifest.csv` (81 rows, 81 unique participants, 40 PD, 41 HC, 100% metadata match, 0 label mismatches).
- Executed `uv run python scripts/audit_dataset.py`.
  - Discovered and quantified significant demographic confounding: HC mean age 47.73 ± 14.33 vs PD mean age 67.04 ± 8.98 (Mann-Whitney U = 223.0, p = 1.75×10⁻⁸).

### Phase 3: UAMS Core39 Feature Extraction
- Executed `uv run python scripts/extract_features.py --allow-reviewed-exclusions`.
  - Preprocessing: resampled to 16 kHz, pre-emphasis, windowed Praat phonation analysis.
  - Successfully extracted Core39 features for 78 recordings.
  - Exactly 3 recordings failed due to excessive waveform clipping (3 clipped PD recordings), matching reviewed exclusion policy.
  - Output files: `data/processed/voice_features.csv`, `feature_extraction_report.csv`, and `feature_extraction_receipt.json`.
  - Verified: schema `voxneuro.voice.v3`, 39 feature columns, 0 NaNs/Infs, 78 unique participants, valid class labels (41 HC, 37 PD).

### Phase 4: UAMS Model Evaluation
- Fixed grouped evaluation (`uv run python scripts/evaluate_model.py --dataset uams`):
  - Logistic regression: balanced accuracy = 0.659 ± 0.167, ROC-AUC = 0.741 ± 0.125
  - Support vector machine: balanced accuracy = 0.760 ± 0.066, ROC-AUC = 0.781 ± 0.106
  - Random forest: balanced accuracy = 0.771 ± 0.063, ROC-AUC = 0.794 ± 0.092
  - Age-only comparator: balanced accuracy = **0.825 ± 0.074**, ROC-AUC = **0.851 ± 0.091**
  - Age-plus-voice comparator: balanced accuracy = 0.798 ± 0.158, ROC-AUC = 0.846 ± 0.137
- Repeated nested cross-validation (`uv run python scripts/evaluate_nested_models.py --dataset uams`):
  - 5 outer folds × 3 inner folds, seeds 2026, 2027, 2028, 1000 participant bootstrap iterations.
  - Extra Trees: balanced accuracy = **0.766 ± 0.008**, precision = 0.734, sensitivity = 0.793, specificity = 0.740, ROC-AUC = 0.785
  - L2 Logistic: balanced accuracy = 0.739 ± 0.007, precision = 0.723, sensitivity = 0.730, specificity = 0.748, ROC-AUC = 0.770
  - Age-only comparator: balanced accuracy = **0.839 ± 0.007**, ROC-AUC = **0.849 ± 0.013**
  - Age-plus-voice comparator: balanced accuracy = 0.771 ± 0.012, ROC-AUC = 0.814 ± 0.024
  - Generated `artifacts/reports/model_evaluation/uams_nested.html`.

### Phase 5: UAMS Research Model Training
- Executed `uv run python scripts/train_model.py --dataset uams`.
  - Trained L2 logistic reference model on all 78 valid development cohort samples.
  - Saved model bundle: `artifacts/models/uams_logistic_research.joblib` and SHA-256 sidecar.
  - Generated exploratory coefficients: `data/processed/uams_logistic_coefficients.csv`.
- Executed `uv run python scripts/verify_model.py`.
  - Reloaded model bundle; verified deterministic sample predictions, artifact checksums, provenance receipts, and research-only / domain-incompatible status.

### Phase 6: UCI Dataset Acquisition & Independent Evaluation
- Downloaded UCI-470 official archive to `data/raw/uci/download/pd_speech_features.rar`.
- Inspected archive via `scripts/inspect_dataset.py --dataset uci`.
  - Extracted `data/interim/uci/pd_speech_features.csv` (756 rows, 252 participants, 755 columns).
  - Verified 1 exact duplicate row for 1 participant.
- Evaluated models via `scripts/evaluate_model.py --dataset uci`.
  - Logistic regression: balanced accuracy = **0.766 ± 0.043**, sensitivity = 0.878 ± 0.014, specificity = 0.655 ± 0.093, ROC-AUC = 0.826 ± 0.036, average precision = 0.924 ± 0.032.
  - Executed duplicate sensitivity analysis: confirmed zero meaningful difference when deduplicated.

### Phase 7: Reproducibility & Receipt Validation
- All receipts verified with zero discrepancies:
  - `feature_extraction_receipt.json`
  - `model_evaluation_receipt.json`
  - `nested_uams_evaluation_receipt.json`
  - `uci_model_evaluation_receipt.json`
  - `uci_extraction_receipt.json`
- Every receipt cryptographically binds to:
  - Current source code fingerprint (`810380b1866780c402b17abee2a2619f0604bee281dbe1c4d44e2d0c6e2283f1`)
  - Feature schema version and fingerprint (`voxneuro.voice.v3`)
  - Dataset manifest and table checksums.

### Phase 8: Streamlit Application Integration
- Executed full suite of Streamlit AppTests (`tests/integration/test_app.py`): 8 passed in 8.32s.
- Verified application renders Research Model metrics from verified receipt files.
- Confirmed safety guards: `allow_user_microphone_inference: false` strictly enforced; model prediction is never executed on browser microphone recordings.

### Phase 9: Documentation Updates
- Updated `docs/REPRODUCIBILITY.md` and `docs/testing/VERIFICATION_REPORT.md` with active environment versions, code fingerprints, and receipt checksums.
- Maintained all documented clinical limitations across `docs/reports/MODEL_CARD.md`, `docs/dataset/UAMS_DATASET_REPORT.md`, and `docs/dataset/UCI_DATASET_REPORT.md`.

### Phase 10: Full Test and Regression Verification
- Pytest suite: **318 passed** in 25.77s.
- Linters: `ruff check .` passed with 0 errors.
- Code formatter: `ruff format --check .` passed across 158 files.
- Project verification: `python scripts/verify_project.py` passed.
- Model verification: `python scripts/verify_model.py` passed.
- M0 tests and provenance: 100% passing.

---

## 3. Deliverables and Checksums

### Local Training Artifacts & Sidecars
- `artifacts/models/uams_logistic_research.joblib`: 7,374 bytes
  - SHA-256: `28981b0d1216c76d692b3e1b0d2ce21ba71b0a77ac68c5d34ff6d78f1dbc33b6`
- `artifacts/models/uams_logistic_research.joblib.sha256`: matches model hash exactly.

### Evaluation Reports
- `artifacts/reports/model_evaluation/uams_nested.html`: 26,455 bytes
- `artifacts/reports/dataset_audit/uams_dataset_audit.html`: 2,492 bytes

### Final Distributable Archive
- `VoxNeuro_M1_VERIFIED.zip`
  - Generated via: `uv run python -m scripts.build_ai_review_bundle --output VoxNeuro_M1_VERIFIED.zip`
  - Members: 201 total files (190 project source files at root, `AI_REVIEW_BUNDLE_README.txt`, and 10 aggregate review attachments in `review_evidence/`).
  - Privacy verification: 0 audio files, 0 model binaries, 0 participant IDs in review attachments, 0 private credentials.
- `VoxNeuro_M1_VERIFIED.zip.sha256`: External sidecar.

---

## 4. M1 Acceptance Criteria Checklist

| Category | Criterion | Status | Verification Summary |
|---|---|---|---|
| **UAMS** | Official dataset acquired | **PASS** | Figshare 23849127 downloaded and stored in `data/raw/uams/`. |
| **UAMS** | Built-in archive checksums pass | **PASS** | `PD_AH.zip` and `HC_AH.zip` MD5 match exact expected constants. |
| **UAMS** | WAV counts & headers validate | **PASS** | 81 WAVs, WAVEX/FLOAT, 8000 Hz mono, 0 corrupt files. |
| **UAMS** | Manifest integrity checks pass | **PASS** | 81 rows, 81 unique participants, 100% metadata match. |
| **UAMS** | Demographic audit completes | **PASS** | Quantified significant age confound (Mann-Whitney U = 223, p = 1.75e-8). |
| **UAMS** | Core39 feature extraction completes | **PASS** | 78 accepted, 3 PD clipping exclusions under reviewed policy. |
| **UAMS** | Feature extraction receipt valid | **PASS** | Cryptographic hash matches feature table and current code. |
| **UAMS** | Grouped evaluation succeeds | **PASS** | 5-fold grouped CV completed across all model families. |
| **UAMS** | Nested evaluation succeeds | **PASS** | 5x3 repeated nested CV completed; Extra Trees BA = 0.766, Age-only = 0.839. |
| **UAMS** | Evaluation receipts valid | **PASS** | `model_evaluation_receipt.json` & `nested_uams_evaluation_receipt.json` verified. |
| **UAMS** | Research model trained | **PASS** | L2 logistic reference model trained and saved. |
| **UAMS** | Model checksum verification passes | **PASS** | SHA-256 sidecar matches joblib artifact. |
| **UAMS** | `verify_model.py` passes | **PASS** | Bundle reload, prediction consistency, provenance checks passed. |
| **UCI** | Official dataset acquired | **PASS** | UCI dataset 470 downloaded. |
| **UCI** | RAR-capable extraction succeeds | **PASS** | Extracted via bsdtar; 756 rows, 252 participants, 755 columns. |
| **UCI** | Schema validation passes | **PASS** | Verified against `configs/uci470_schema.json`. |
| **UCI** | Extraction receipt valid | **PASS** | `uci_extraction_receipt.json` generated and verified. |
| **UCI** | Grouped evaluation succeeds | **PASS** | 5-fold grouped CV completed (Logistic BA = 0.766, ROC-AUC = 0.826). |
| **UCI** | Duplicate sensitivity analysis completes | **PASS** | Evaluated 1 exact duplicate row; confirmed zero impact. |
| **UCI** | UCI evaluation receipt valid | **PASS** | `uci_model_evaluation_receipt.json` generated and verified. |
| **UCI** | Results remain separate from UAMS | **PASS** | Strict separation maintained; no joining of feature tables. |
| **App** | Research model section displays results | **PASS** | Streamlit AppTests verified research model display. |
| **App** | Reports accessible | **PASS** | Nested HTML and dataset audit reports verified. |
| **App** | Model integrity checks pass | **PASS** | Validated via `scripts/verify_model.py`. |
| **App** | Microphone disease prediction disabled | **PASS** | `allow_user_microphone_inference: false` strictly enforced. |
| **App** | No diagnostic claims introduced | **PASS** | Explicit investigational disclaimers maintained. |
| **Testing** | Full test suite passes | **PASS** | **318 passed** in 25.77s. |
| **Testing** | Ruff lint passes | **PASS** | All checks clean across all modules. |
| **Testing** | Ruff formatting passes | **PASS** | 158 files cleanly formatted. |
| **Testing** | Project verification passes | **PASS** | 11 imports, 10 required files verified. |
| **Testing** | Model verification passes | **PASS** | All reload and provenance checks passed. |
| **Testing** | M0 regressions absent | **PASS** | All M0 archive and provenance tests pass. |
| **Archive** | Final ZIP generated by builder | **PASS** | Generated via `scripts.build_ai_review_bundle`. |
| **Archive** | Root source package complete | **PASS** | Complete project source at archive root. |
| **Archive** | Aggregate review evidence present | **PASS** | 10 aggregate evidence files in `review_evidence/`. |
| **Archive** | Evidence checksums valid | **PASS** | Verified in `AI_REVIEW_BUNDLE_README.txt`. |
| **Archive** | Participant data excluded | **PASS** | Privacy scan verified 0 participant IDs in review attachments. |
| **Archive** | Raw datasets excluded | **PASS** | 0 audio or raw archive files present in ZIP. |
| **Archive** | Model binaries excluded | **PASS** | 0 `.joblib`/`.pkl` files in ZIP. |
| **Archive** | CRC verification passes | **PASS** | `testzip()` returned None. |
| **Archive** | Clean extraction passes | **PASS** | Extracted and verified in clean temporary directory. |
| **Archive** | Provenance verification passes | **PASS** | `verify_project.py` and provenance fingerprints pass from extraction. |
| **Archive** | SHA-256 sidecar generated | **PASS** | `VoxNeuro_M1_VERIFIED.zip.sha256` written. |

---

## 5. Strict Stop Condition Enforced

Milestone 1 is complete. In adherence to Section 17 of the user requirements:
- No age-matched cohort acquisition has been initiated.
- DDK, connected-speech analysis, and Vowel Space Area were not implemented.
- No external database or persistent storage layer was introduced.
- Microphone inference remains strictly disabled.
- The domain validation allowlist remains untouched.
- Clinical deployment activities have not commenced.
- Milestone 2 has not been started.
