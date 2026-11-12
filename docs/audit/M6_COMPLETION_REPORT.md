# VoxNeuro — Milestone 6 (M6) Completion & Verification Report

**Release target:** `VoxNeuro_M6_VERIFIED.zip` + `VoxNeuro_M6_VERIFIED.zip.sha256`  
**Baseline verified prior to M6:** `VoxNeuro_M5_VERIFIED.zip` (M0–M5 baseline: 577 passed, 0 failed)  
**Environment:** Python `3.12.16`, locked `uv.lock`, Windows 11 (`Windows-11-10.0.26200-SP0`)

---

## 1. Executive Summary

Milestone 6 completes VoxNeuro's transition from an engineering-heavy single-page prototype into a structured, role-separated voice-analysis research web platform backed by:

1. **Consumer-first guided UI + RBAC-gated specialist portals** (`src/voxneuro/ui/theme.py`, `consumer_pages.py`, `admin_portals.py`, and `app.py`), with collapsed sidebar navigation, calm onboarding, non-technical explanations, mandatory non-diagnostic disclaimers, and strict server-side authorization barriers around Researcher, ML Admin, and System Admin workspaces.
2. **Leakage-free ML readiness auditing, multi-family comparative benchmarking, calibration analysis, and structured Model Cards** (`src/voxneuro/modeling/dataset_readiness.py`, `m6_experiment.py`, `m6_training_ops.py`, `scripts/run_m6_training.py`).
3. **Versioned SQLite ML Model Registry & Fail-Closed Lifecycle Governance** (`src/voxneuro/modeling/model_registry.py`) plus **Database Migration `006`** (`006_m6_platform_and_ml_registry.sql`, `24` tables total with `PRAGMA integrity_check = ok` and `0` foreign key violations) and **PBKDF2/SHA-256 Auth & RBAC** (`src/voxneuro/study/auth.py`).
4. **Standalone Fail-Closed `PredictionService`** (`src/voxneuro/modeling/prediction_service.py`) enforcing quality gating, microphone/user-upload blocking, schema checks, consent/DUA verification, bundle SHA-256 tamper verification, out-of-distribution (OOD) detection, opt-in retention, and abstention telemetry.

**Crucial scientific & clinical honesty statement:** Neither `M6_EXTERNAL_VALIDATION_COMPLETE` nor `M6_RESEARCH_INFERENCE_APPROVED` is claimed or enabled, because no external raw-audio Parkinson's cohorts (NeuroVoz, PC-GITA, Italian IPVS) or signed DUAs are present locally (`0` external recordings, `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`, `approved_domains = []`, `allow_user_microphone_inference = false`).

---

## 2. Dataset Readiness & Leakage Controls

Audited via `voxneuro.modeling.dataset_readiness.build_dataset_readiness_report()` and recorded in `review_evidence/m6_dataset_readiness.json`:

| Cohort | Domain ID | Participants | Recordings | Raw Audio | Core39 Compatible | Readiness Status | Blockers |
|---|---|---:|---:|---|---|---|---|
| **UAMS Sustained Vowel /a/** (`figshare-23849127.v1`, CC BY 4.0) | `uams_telephone` | `78` (`41` HC, `37` PD) | `78` | Yes (`8 kHz` telephone WAV) | Yes | `READY_INTERNAL_RESEARCH_ONLY` | None for internal CV; severe age confounding (mean age HC=`47.73` vs PD=`66.91`) |
| **UCI PD Classification #470** (`doi-10.24432/C5MS4X`, CC BY 4.0) | `uci470_precomputed_44k_mic` | `252` | `756` (`252 x 3`) | No (precomputed CSV only) | No (`752` tabular predictors) | `READY_FEATURE_TABLE_BENCHMARK_ONLY` | No raw WAV audio, no Core39 mapping, no per-participant age, `1` exact duplicate feature row |
| **Italian IPVS** | `italian_parkinsons_headset` | `0` | `0` | No | Candidate (`unknown`) | `BLOCKED_EXTERNAL_DATA_OR_DUA_MISSING` | Local audio/features absent; DUA `NOT_REGISTERED_OR_NO_DB` |
| **NeuroVoz** | `neurovoz_studio` | `0` | `0` | No | Candidate | `BLOCKED_EXTERNAL_DATA_OR_DUA_MISSING` | Local audio/features absent; DUA `NOT_REGISTERED_OR_NO_DB` |
| **PC-GITA** | `pc_gita_soundbooth` | `0` | `0` | No | Candidate | `BLOCKED_EXTERNAL_DATA_OR_DUA_MISSING` | Local audio/features absent; DUA `NOT_REGISTERED_OR_NO_DB` |

Leakage guards verified by unit tests (`test_leakage_prevention_rejects_target_or_id_columns_in_predictors`) and `verify_participant_split_integrity()`: target/ID columns cannot enter predictor matrices, all CV splits are participant-disjoint, and `SimpleImputer` / `StandardScaler` fit strictly inside each training fold.

---

## 3. Empirical Comparative ML Benchmarks, Confounding & Calibration

Executed reproducibly via `uv run python scripts/run_m6_training.py` (5-fold participant-grouped CV, `random_seed=2026`, documented in `review_evidence/m6_experiment_summary.json` and `m6_model_card.json`):

### 3.1 Multi-Family Voice-Only Benchmarks (`Model B`)

| Cohort | Model Family | N Participants | ROC-AUC | PR-AUC | Balanced Accuracy | Brier Score | ECE |
|---|---|---:|---:|---:|---:|---:|---:|
| UAMS (Core39) | `dummy_prior` | 78 | `0.4743` | `0.4606` | `0.5000` | `0.2497` | `0.0001` |
| UAMS (Core39) | `logistic_regression` | 78 | `0.7198` | `0.7288` | `0.6549` | `0.2452` | `0.1759` |
| UAMS (Core39) | `linear_svm_calibrated` | 78 | `0.6664` | `0.6469` | `0.6200` | `0.2292` | `0.0375` |
| UAMS (Core39) | `rbf_svm` (calibrated CV) | 78 | `0.7732` | `0.7235` | `0.7442` | `0.1996` | `0.1338` |
| UAMS (Core39) | `random_forest` | 78 | `0.7877` | `0.7104` | `0.7726` | `0.1844` | `0.0969` |
| UAMS (Core39) | `extra_trees` | 78 | `0.7831` | `0.7091` | `0.7821` | `0.1888` | `0.1354` |
| UAMS (Core39) | `hist_gradient_boosting` | 78 | `0.7126` | `0.7000` | `0.6427` | `0.3051` | `0.2994` |
| UCI #470 (752 predictors) | `dummy_prior` | 252 | `0.4905` | `0.7423` | `0.5000` | `0.1895` | `0.0000` |
| UCI #470 (752 predictors) | `logistic_regression` | 252 | `0.8308` | `0.9306` | `0.7330` | `0.1427` | `0.0988` |
| UCI #470 (752 predictors) | `linear_svm_calibrated` | 252 | `0.8423` | `0.9299` | `0.5781` | `0.1439` | `0.1143` |
| UCI #470 (752 predictors) | `random_forest` | 252 | `0.8479` | `0.9369` | `0.7282` | `0.1314` | `0.0937` |
| UCI #470 (752 predictors) | `extra_trees` | 252 | `0.8494` | `0.9399` | `0.7236` | `0.1273` | `0.0647` |

### 3.2 Confounding & Domain Comparisons (Models A–D)

- **UAMS Model A (`model_a_demographic_only`, age + sex):** ROC-AUC `0.8392`, PR-AUC `0.7626`, Balanced Accuracy `0.7943`, Brier `0.1576`, ECE `0.1005`.
- **UAMS Model B (`logistic_regression`, voice-only):** ROC-AUC `0.7198`, PR-AUC `0.7288`, Balanced Accuracy `0.6549` (voice-only trails age+sex demographic baseline on UAMS).
- **UAMS Model C (`model_c_voice_plus_covariates_logistic` / `_rf`):** ROC-AUC `0.8444` / `0.8965`, Balanced Accuracy `0.7956` / `0.8078`.
- **UCI #470 Model A (`model_a_gender_only`):** ROC-AUC `0.5818`, Balanced Accuracy `0.6049` (voice predictors `0.8494` substantially exceed gender-only on UCI #470, though age is unavailable).
- **Model D (`model_d_dataset_domain_only`):** `NOT_ESTIMABLE_DISJOINT_SCHEMAS` — UAMS Core39 WAV features and UCI #470 precomputed predictors cannot be validly pooled into a cross-domain raw-audio estimate.

### 3.3 UAMS Subgroup Summary (`N >= 10` Threshold Enforced)

- `age_group = 60_plus` (`N=35`): ROC-AUC `0.6071`, Balanced Accuracy `0.6250`
- `age_group = under_60` (`N=43`): ROC-AUC `0.7908`, Balanced Accuracy `0.6569`
- `sex_label = Female` (`N=43`): ROC-AUC `0.7444`, Balanced Accuracy `0.6889`
- `sex_label = Male` (`N=35`): ROC-AUC `0.6974`, Balanced Accuracy `0.6332`

---

## 4. Security, Privacy, Database & Fail-Closed Prediction Verification

- **Database Schema (`006_m6_platform_and_ml_registry.sql`):** Migrates cleanly to `24` SQLite tables with `foreign_keys_enabled = true`, `integrity_check = ["ok"]`, and `0` foreign key violations.
- **Authentication & RBAC (`src/voxneuro/study/auth.py`):** Per-user random salts with PBKDF2-HMAC-SHA256 (`200,000` iterations), opaque session bearer tokens stored solely as SHA-256 digests (`token_hash`), single-use expiring password reset tokens, default `participant` role on self-registration, and server-side RBAC enforcement (`participant`, `researcher`, `ml_admin`, `admin`).
- **Withdrawal & Opt-In Retention (`withdrawal.py` & `prediction_service.py`):** `prediction_records` are only written when explicit user opt-in or active study `permission_to_retain_derived_features` is verified. Participant withdrawal atomically deletes `prediction_records` alongside `derived_features`.
- **Fail-Closed Inference Probe (`review_evidence/m6_prediction_service_summary.json`):** Submitting browser microphone input with failed audio quality returns `abstained = true`, `status = "ABSTAINED_FAIL_CLOSED"`, `abstention_reasons = ["QUALITY_GATE_FAILED", "DISALLOWED_CAPTURE_ORIGIN", "NO_APPROVED_MODEL_REGISTERED"]`, `retention_persisted = false`, `disclaimer_present = true`, and logs a privacy-safe row in `abstention_events`.

---

## 5. Verification Results (Commands Run Directly Before Packaging)

| Check | Outcome |
|---|---|
| `uv run pytest -q --junitxml=<temp>` (via `scripts/generate_m6_evidence.py`) | **590 passed**, `0` failed, `0` skipped (`151.61s`), covering M0–M3 (`465`), M4 (`47`), M5 (`52`), M6 unit (`9`), M6 UI integration (`3`), and M0–M5 Streamlit UI regression (`14`) |
| `uv run python scripts/verify_project.py` | **PASS** — required files (`10`), all 17 core + M6 module imports, release provenance digests |
| `uv run ruff check .` & `uv run ruff format --check` on M6 files | **All checks passed (`0` lint errors)** |
| Headless Chromium Playwright browser automation | **Not available in host environment** (`node`/`npm`/Playwright browser runner unavailable; verified via Streamlit `AppTest` harness + live HTTP health check during clean-room verification) |

---

## 6. Authoritative M6 Completion Flags

| Flag | Status | Honest Rationale |
|---|---|---|
| `M6_UI_REDESIGN_COMPLETE` | **TRUE** | Collapsed sidebar, consumer home/workflow/help/privacy/results/account pages, and role-gated researcher/admin portals verified via `AppTest`. |
| `M6_AUTHENTICATION_RBAC_COMPLETE` | **TRUE** | PBKDF2 auth, hashed bearer sessions, password reset, and server-side RBAC verified across unit and UI tests. |
| `M6_DATABASE_MIGRATION_COMPLETE` | **TRUE** | Migration `006` adds all 11 M6 tables cleanly with 0 FK violations and withdrawal deletion support. |
| `M6_DATASET_AUDIT_COMPLETE` | **TRUE** | UAMS (`78`), UCI #470 (`252`), and missing external cohorts (`0`) audited with zero-leakage assertions. |
| `M6_MODEL_EXPERIMENTS_COMPLETE` | **TRUE** | Models A–D, 7 model families (UAMS) + 5 families (UCI #470), calibration bins, and `N >= 10` subgroups generated reproducibly. |
| `M6_MODEL_CARD_COMPLETE` | **TRUE** | Structured JSON (`m6_model_card.json`) and HTML (`m6_model_card.html`) generated and exportable in UI. |
| `M6_MODEL_REGISTRY_COMPLETE` | **TRUE** | Versioned lifecycle states, SHA-256 tamper verification, and fail-closed approval enforcement tested. |
| `M6_PREDICTION_SERVICE_COMPLETE` | **TRUE** | Standalone fail-closed `PredictionService` with mandatory disclaimer, OOD gate, opt-in retention, and abstention telemetry tested. |
| `M6_EXTERNAL_VALIDATION_COMPLETE` | **FALSE** | Authorized external raw-audio datasets (NeuroVoz, PC-GITA, Italian IPVS) and signed DUAs are absent locally. |
| `M6_RESEARCH_INFERENCE_APPROVED` | **FALSE** | `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`, `approved_domains = []`, and `allow_user_microphone_inference = false` remain locked fail-closed. |
| `M6_RELEASE_PACKAGE_VERIFIED` | **TRUE** | `VoxNeuro_M6_VERIFIED.zip` + `.sha256` built via `--milestone m6`, ZIP CRC tested, and clean-room verified. |
