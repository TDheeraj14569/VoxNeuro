# VoxNeuro Milestone 6 — Architecture Inspection Report & Design Plan

**Date:** 2026-11-12  
**Execution Environment:** Python 3.12.16 (`uv`), Windows 11 AMD64  
**Pre-Flight M4/M5 Baseline Status:** **VERIFIED PASS**  
- `VoxNeuro_M5_VERIFIED.zip` SHA-256: `3CD0640B0B888E09125EED51E470099A5A30D9C0AD404CC4F1376A2664D11BC5`
- Pre-flight test suite (`uv run pytest -q`): **577 passed in 90.57s** (`0` failed, `0` skipped)
- Trust-root & M4/M5 safety invariants verified against `docs/audit/M4_M5_FINAL_ACCEPTANCE_REPORT.md`:
  - `configs/model_config.yaml`: `allow_user_microphone_inference: false`
  - `src/voxneuro/modeling/domains.py`: `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`
  - `configs/recording_domain_registry.yaml`: `approved_domains: []`
  - `ConsentRecord` and migrated `consents`: `permission_to_retain_derived_features = False`

---

## 1. Repository & Package Architecture Map

| Package / Path | Current Responsibilities | Reuse in M6 |
|---|---|---|
| `src/voxneuro/audio/` | WAV/WAVEX decoding, validation (`quality.valid`, clipping, voiced fraction), deterministic preprocessing (pause-preserving vs sustained vowel) | Direct reuse in M6 guided recording assessment & pre-prediction quality gate |
| `src/voxneuro/features/` | Versioned Core39 schema (`voxneuro.voice.v3`) + M3 multi-task engines (`ddk`, `connected_speech`, `vowel_space`, `voxneuro.voice.v4`) | Direct reuse for feature extraction inside M6 dataset readiness, ML training, and prediction engine |
| `src/voxneuro/dataset/` | `loader.py` (`load_feature_table`), `uams.py`, `uci.py` (pinned schema `55311b3a...`, 252 participants / 756 rows), `audit.py` | Reused and wrapped by `voxneuro.modeling.dataset_readiness` with normalized cohort adapters and leakage guards |
| `src/voxneuro/modeling/` | `splits.py` (`grouped_splits`), `pipeline.py` (`build_pipelines`, `build_nested_model_searches`), `training.py`, `evaluation.py` (`evaluate_grouped`, `evaluate_nested_grouped`), `calibration.py`, `model_bundle.py`, `domains.py`, `domain_registry.py`, `domain_shift.py`, `domain_evaluation.py`, `prediction.py`, `trust_registry.py` | Core ML & fail-closed foundation extended with M6 experiment runner (`m6_experiment.py`), calibration curves/ECE, versioned model registry (`model_registry.py`), dataset readiness (`dataset_readiness.py`), and `PredictionService` (`prediction_service.py`) |
| `src/voxneuro/study/` | SQLite + PRAGMA FK runner (`database.py`), migrations `001`–`005`, `registry.py`, `participant.py`, `consent.py`, `session.py` (`OPERATION_AUTHORIZATION_MAP`, `preflight_session_ingestion`), `longitudinal.py`, `reporting.py`, `withdrawal.py`, `audit.py` | Extended via backward-compatible Migration `006`, server-side auth/RBAC, prediction/abstention persistence under explicit retention opt-in, and withdrawal erasure |
| `src/voxneuro/visualization/` | Waveform/STFT payload preparation + 2D plots + local Three.js acoustic visualizer bundle (`visualizer.bundle.js`, 595,161 bytes; note `node`/`npm` absent on host) | Preserved intact for Researcher portal Signal Analysis; hidden from default ordinary-user workflow |
| `src/voxneuro/reporting/` | Sanitized JSON/CSV/HTML report exports + `model_card.py` | Extended with M6 structured JSON/HTML model cards and plain-language user summary export |
| `app.py` | Monolithic Streamlit UI (~3,695 lines) with editorial warm-parchment theme and 9-item sidebar `st.radio("Workspace", ...)` | Transformed into role-based multi-surface digital health UI (`src/voxneuro/ui/` components + `app.py` entrypoint) preserving unmodified `tests/integration/test_app.py` and `test_multitask_app.py` contracts |

---

## 2. Dataset & ML Pipeline Inventory

Verified local data on disk (never distributed inside verification ZIPs per CC BY 4.0 biometric sensitivity and M4/M5 rules):
1. **UAMS Sustained-Vowel `/a/` Cohort (`data/interim/uams/`, `data/processed/voice_features.csv`)**
   - Raw audio: 81 mono 8 kHz WAV files (`41` HC, `40` PD); **78 valid participants** (`37` PD, `41` HC) retained after clipping policy (`3` PD excluded for clipping).
   - Severe age confounding empirically observed in `nested_uams_summary.csv`: `age_only_logistic` achieves ROC-AUC `0.849`, outperforming all voice-only models (`0.746–0.787`). Telephone recording domain only.
2. **UCI Parkinson's Disease Classification #470 (`data/raw/uci/uci-470.zip`)**
   - 756 rows across 252 unique participants (`3` repeats per participant, `188` PD / `64` HC), `752` precomputed acoustic predictors + `gender` (`0`/`1`). **No raw WAV audio** and **no per-row age column**. Useful as a strict participant-grouped feature-table benchmark / domain baseline under `voxneuro.uci470.v1`, never joined with Core39 or microphone inference.
3. **External Multi-Domain Cohorts (`NeuroVoz`, `PC-GITA`, `IPVS`)**
   - **Absent locally (`0` recordings, `0` signed DUAs).** Cannot be evaluated or approved without actual authorized data + signed Ed25519 trust registry + `dataset_access` DUA cross-binding. M6 must state this blocker transparently without inventing external metrics or domains.

Available ML toolset verified in `uv.lock`: `scikit-learn 1.9.1`, `scipy 1.18.1`, `pandas 3.1.1`, `numpy 2.5.4`, `praat-parselmouth 0.4.7`, `librosa 0.11.0`, `itsdangerous 2.2.0`, `starlette 1.10.0`. (`xgboost` and `node`/`npm` are not installed.)

---

## 3. UI/UX Transformation & M0–M5 Regression Architecture Decision

### Challenge
Existing unmodified M0–M5 integration tests (`tests/integration/test_app.py` and `tests/integration/test_multitask_app.py`) interact with `app.py` in headless `AppTest` mode via:
- `app.button[0]` on default Home/Overview page -> expects Voice Assessment (`len(app.audio_input) == 1`)
- `app.session_state["voxneuro_nav"] = "Voice assessment"` -> expects `app.radio[0]` (`"Record with microphone"`, `"Upload WAV"`) and `"Analyze this recording"`
- `app.sidebar.radio[0].set_value(page)` across `["Overview", "Voice assessment", "Multi-task assessment", "Signal analysis", "Feature analysis", "Research model", "Reports", "Method & privacy"]`
- `app.session_state["voxneuro_nav"] = "Research operations"` -> checks `app.title` contains `"Research operations"`

### Resolution (No Test Weakening, Strict Backend Role Enforcement)
1. **Default Public / Ordinary User Experience (`initial_sidebar_state="collapsed"`):**
   - Renders a sleek top navigation bar (`st.pills` so `app.button[0]` on Overview remains the primary Hero CTA `"Start voice check"`!) with approachable routes: **Home**, **Voice Check**, **How It Works**, **Privacy & Safety**, **Help & FAQ**, **Account / Sign In** (plus **My Results** and **History** when active).
   - Default views strip out Core39 tables, DUA jargon, raw feature keys, training internals, and unrequested developer diagnostics.
   - **Mandatory medical disclaimer** is displayed prominently at the top of Voice Check and in every Result / Abstention view.
2. **Server-Side RBAC & Role Portals (`src/voxneuro/study/auth.py`):**
   - Roles: `participant` (ordinary user), `researcher`, `ml_admin`, `admin`.
   - Passwords hashed with per-user 16-byte random salt + PBKDF2-HMAC-SHA256 (`200,000` iterations); opaque CSPRNG session tokens stored server-side in SQLite `user_sessions` with expiry and revocation.
   - All privileged pages (`Research operations`, `Model Admin`, `System Admin`) validate the server-side session & role inside backend service calls (`require_role(conn, token, ...)`), never relying on UI hiding. Selecting `Research operations` without an authenticated `researcher`/`admin` session displays the page title (`Research operations`) plus an inline Sign-In / Authorization Required gate with zero participant or DB exposure.
3. **Backward-Compatible Workspace Selector:**
   - Inside collapsed `st.sidebar`, keep `st.radio("Workspace", LEGACY_PAGES, key="voxneuro_nav", label_visibility="collapsed")` synchronized with the M6 page router, allowing unmodified M0–M5 `AppTest` navigation flows to pass 100% while ordinary users navigate cleanly through the collapsed-sidebar top bar.

---

## 4. Database Schema Extension Plan (Migration `006_m6_platform_and_ml_registry.sql`)

Appends atomically atop existing 12 M5 tables (`schema_migrations`, `protocols`, `studies`, `participants`, `consents`, `dataset_access`, `sessions`, `task_recordings`, `derived_features`, `processing_runs`, `audit_log`, `tombstones`):
- `users` (`user_id`, `username`, `email`, `display_name`, `password_hash`, `role`, `is_active`, `participant_id`, `created_at`, `updated_at`, `last_login_at`)
- `user_sessions` (`session_token`, `user_id`, `role`, `created_at`, `expires_at`, `revoked_at`)
- `password_reset_tokens` (`reset_token_hash`, `user_id`, `expires_at`, `used_at`, `created_at`)
- `training_datasets` (`dataset_record_id`, `dataset_name`, `dataset_version`, `dataset_sha256`, `schema_version`, `participant_count`, `recording_count`, `authorization_status`, `created_at`)
- `training_runs` (`run_id`, `run_name`, `git_or_code_fingerprint`, `dataset_ids_json`, `config_json`, `random_seed`, `status`, `created_by_user_id`, `created_at`, `completed_at`, `receipt_sha256`)
- `model_versions` (`model_id`, `model_version`, `model_family`, `feature_schema_version`, `feature_schema_fingerprint`, `training_run_id`, `artifact_path`, `artifact_sha256`, `lifecycle_state`, `calibration_status`, `clinical_claim_status`, `created_at`, `updated_at`)
- `model_evaluations` (`evaluation_id`, `model_id`, `evaluation_scope`, `dataset_name`, `n_participants`, `roc_auc`, `pr_auc`, `balanced_accuracy`, `sensitivity`, `specificity`, `brier_score`, `ece`, `metrics_json`, `evaluated_at`)
- `model_domain_approvals` (`approval_id`, `model_id`, `domain_id`, `approval_state`, `evidence_sha256`, `approved_by_user_id`, `approved_at`, `notes`)
- `prediction_records` (`prediction_id`, `session_id`, `participant_id`, `user_id`, `model_id`, `model_version`, `model_checksum`, `acquisition_domain_id`, `capture_origin`, `research_score`, `research_classification`, `calibration_status`, `uncertainty_json`, `abstained`, `abstention_reason`, `retention_permitted`, `created_at`) — **never auto-persists predictions unless explicit consent/user prediction retention opt-in is verified**, and erased cleanly upon participant withdrawal.
- `abstention_events` (`abstention_id`, `session_id`, `model_id`, `reason_code`, `reason_detail`, `acquisition_domain_id`, `capture_origin`, `created_at`) — stores aggregate/non-PII operational telemetry when inference abstains.
- `model_lifecycle_events` (`event_id`, `model_id`, `from_state`, `to_state`, `actor_user_id`, `actor_role`, `reason`, `created_at`) — immutable state transition audit trail.

---

## 5. Planned Execution Sequence (M6 Phases)
1. **Migration `006` + Auth/RBAC (`src/voxneuro/study/auth.py` + `migrations/006_m6_platform_and_ml_registry.sql`)** + update `withdrawal.py` to purge retained `prediction_records` on withdrawal.
2. **Dataset Readiness (`src/voxneuro/modeling/dataset_readiness.py`)**: leakage-free adapters for UAMS & UCI, participant-overlap & duplicate checks, M4 DUA authorization verification, external cohort blocker detection, summary artifact generation.
3. **M6 Experiment, Confounding & Calibration Engine (`src/voxneuro/modeling/m6_experiment.py`, `src/voxneuro/modeling/model_registry.py`, `scripts/run_m6_training.py`)**: Logistic, Linear/RBF SVM, Random Forest, Extra Trees, HistGradientBoosting; Models A (Demographic), B (Voice), C (Voice+Covariates), D (Dataset/Domain); reliability bins, ECE, Brier, threshold curves, subgroup/domain sensitivity, structured JSON+HTML model cards, immutable registry lifecycle (`TRAINING` -> `TRAINED` -> `RESEARCH_EVALUATED` -> `EXTERNAL_VALIDATION_PENDING` -> `RESEARCH_INFERENCE_APPROVED` / `REJECTED` / `RETIRED`).
4. **Standalone Fail-Closed Prediction Service (`src/voxneuro/modeling/prediction_service.py`)**: Integrates M5 preflight, audio quality, schema/config verification, registry/checksum verification, domain governance, OOD range checks, mandatory abstention, explicit medical disclaimer, and opt-in prediction retention.
5. **Redesigned Product UI (`src/voxneuro/ui/` + `app.py`)**: Responsive modern consumer design system + public pages + 6-step guided voice check + plain-language results/abstention + history + profile + Researcher / Model Admin / System Admin workspaces.
6. **Comprehensive Verification + Extended Release (`scripts/build_ai_review_bundle.py`, `docs/audit/M6_COMPLETION_REPORT.md`, `VoxNeuro_M6_VERIFIED.zip`)**: Full `pytest`, `ruff`, `verify_project.py`, clean-room extraction verification, and runtime probes.
