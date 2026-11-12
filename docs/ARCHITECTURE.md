# Architecture and release boundaries

## Application data flow

```text
Browser microphone or WAV upload
  → soundfile decodes bytes and reads source metadata
  → audio quality gate (duration, finite samples, level, clipping, voicing)
  → mono conversion, DC correction, silence trim, resampling
  → downsampled local Three.js waveform/STFT surfaces, plus 2D fallback plots
  → versioned Praat/Parselmouth and Librosa measurements
  → schema validation and local JSON/CSV report
```

The browser sends an audio object to the local Streamlit process. Processing is in memory; audio and reports are not persisted by default. The default server binds to `127.0.0.1`. The app reports signal quality and measurements only. It does not invoke the research model for a user's recording.

## Package responsibilities

| Package | Responsibility |
|---|---|
| `voxneuro.audio` | Decode WAV/WAVEX, inspect and validate signals, preprocess deterministically (including task-specific pause-preserving rules). |
| `voxneuro.features` | Define the ordered `voxneuro.voice.v3` contract and extract phonation/MFCC/spectral measurements. |
| `voxneuro.features.tasks` | Multi-task engines: `ddk` (syllable events, rates, drift), `connected_speech` (VAD, pauses, prosody), `vowel_space` (Burg LPC formants, VSA), `schema` (registries & fingerprints), `pipeline` (session orchestrator). |
| `voxneuro.dataset` | Load source records, validate manifest and feature provenance, summarize cohort integrity. |
| `voxneuro.modeling` | Participant-grouped folds, fold-local model pipelines, exploratory metrics, guarded research-only bundles. |
| `voxneuro.reporting` | Sanitize feature values, preserve schema/provenance, and render research disclosures (including multi-task HTML/JSON reports). |
| `voxneuro.visualization` | Prepare bounded waveform and STFT payloads for a local Three.js iframe and render 2D/research figures (including acoustic vowel triangles). |
| `app.py` | Streamlit navigation and user-facing acquisition, single/multi-task analysis, research, report, and privacy pages. |
| `scripts/` | Dataset inspection, manifest/audit, extraction, evaluation, training, verification, and source packaging. |

## Multi-task session orchestration and failure isolation

Milestone 3 introduces `voxneuro.features.tasks.pipeline.analyze_multitask_session`, which orchestrates multiple independent speech paradigms (sustained vowel `/a/`, DDK syllable repetition, connected speech, and multi-vowel formant analysis) into a unified `voxneuro.voice.v4` envelope:
- **Zero-Cascading Failure Policy:** If a recording for one task is corrupt, clipped, or rejected by quality validation, only that specific task receives `quality_failed` or `processing_failed`. Other valid tasks in the session process normally.
- **Envelope Status Synthesis:** If all tasks succeed, overall status is `complete`. If some tasks succeed and others fail, overall status is `partial`. If all fail, overall status is `quality_failed`.
- **Complete Feature Isolation:** Existing machine learning models (`voxneuro.voice.v3`) are decoupled from multi-task schemas (`voxneuro.task.ddk.v1`, `voxneuro.task.connected_speech.v1`, `voxneuro.task.vowel_space.v1`), preventing invalid dimension mismatches.
- Full architectural details are documented in [`docs/M3_MULTITASK_ARCHITECTURE.md`](M3_MULTITASK_ARCHITECTURE.md).

## Recording domain architecture, domain shift, and inference safety boundaries

Milestone 4 introduces an auditable governance framework for recording domains, domain-shift analysis, and fail-closed inference safety:
- **Separation of Concerns:** Strict architectural separation between Recording Domain ID, Acquisition Metadata (transducers, sample rates, acoustic environments), Capture Origin (research corpus vs. user upload vs. live microphone), and Model Compatibility Approval.
- **Canonical Recording Domain Registry:** Defined in `configs/recording_domain_registry.yaml` and managed via `voxneuro.modeling.domain_registry`. Tracks the reference development domain (`uams_telephone`) and candidate external domains (`neurovoz_studio`, `pc_gita_condenser`, `italian_parkinsons_headset`). `approved_domains: []` remains strictly empty.
- **Candidate Assessment Dossier (`voxneuro.domain_assessment.v1`):** Cryptographically versioned assessment structure capturing frozen model evaluation, quality attrition, and feature-level domain shift. Candidate dossiers are structurally prevented from being loaded as approved compatibility reports.
- **Domain Shift Engine (`voxneuro.modeling.domain_shift`):** Evaluates physical acquisition differences, Standardized Mean Differences (Cohen's $d$), two-sample Kolmogorov–Smirnov distribution tests, and multiple hypothesis testing corrections (Benjamini–Hochberg FDR and Bonferroni).
- **Frozen Model Evaluation (`voxneuro.modeling.domain_evaluation`):** Enforces zero retraining, fixed decision boundaries (threshold = 0.5), participant-level stratified bootstrap uncertainty ($B=1,000$), and small-cell suppression ($N < 10$).
- **Fail-Closed Inference Gate:** `predict_research()` strictly enforces an `InputCaptureContext` contract. User uploads, live browser/app microphones, and unknown capture origins are unconditionally rejected. `allow_user_microphone_inference` remains `false`, and `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` remains empty (`frozenset()`).
- Full architectural details are documented in [`docs/M4_DOMAIN_ARCHITECTURE.md`](M4_DOMAIN_ARCHITECTURE.md) and [`docs/M4_INFERENCE_SAFETY.md`](M4_INFERENCE_SAFETY.md).

## Research data flow

UAMS archive hashes and expected contents are checked before extraction to a staging directory. Workbook labels are mapped explicitly; unknown labels and unexpected folders fail. Manifest audit checks participant/label consistency and waveform hashes. Feature extraction validates the manifest and only permits the three named clipping exclusions when the explicit reviewed-exclusions option is supplied. Each step records content/configuration/code fingerprints. Grouped evaluation is required before model training. Model verification checks receipts and the model artifact checksum before deserialization.

UCI's repeated-record feature table is analyzed separately. All repeats remain grouped by participant, and a second duplicate-removal sensitivity analysis is reported. UCI does not exercise VoxNeuro's WAV decoding or feature extraction pipeline.

## Feature and model contract

The 39 measurements are versioned. Bundle provenance records the ordered feature schema fingerprint, feature and preprocessing configuration fingerprints, dataset version/checksum, current evaluation receipt, relevant software versions, and build time. `predict_research()` requires explicit matching schema/configuration and a domain-validation report whose hash has been reviewed and added to the source allowlist. It refuses microphone audio, enforces complete feature order, and permits only explicitly named undefined acoustic measurements. The distributed model metadata remains research-only and marks domain compatibility false; the approval allowlist is empty, so the research prediction helper cannot produce a class for any current domain.

## 3D visualizer boundary

`frontend/acoustic-visualizer` contains the local Three.js source and reproducible npm lockfile. The Python wrapper downsamples the processed waveform while preserving local extrema, computes a bounded Hann-window STFT surface, rejects non-finite or oversized payloads, and embeds the bundled JS in a local Streamlit iframe. WebGL context loss/unavailability falls back to a local 2D canvas. The home ribbon is decorative and explicitly labeled; only the Signal analysis view consumes a user's processed recording. No audio is uploaded to a visualization service.

## Data and security boundaries

- Source archive distributions exclude raw audio, participant-linked manifests/features, generated evaluations, model artifacts, caches, and virtual environments.
- Local raw data and generated research outputs are ignored by Git. A source-only archive retains placeholder README files to document those directories.
- The joblib loader accepts only internally generated, trusted artifacts and verifies an adjacent SHA-256 checksum first. The checksum detects accidental/tampered bytes; it is not a signature or proof of publisher identity.
- Dataset labels, participant identifiers, demographic columns, and recording paths are never model predictors.
- No diagnosis, disease probability, clinical threshold, or treatment recommendation is returned.

---

## Milestone 6 Platform Architecture (Product UX, Auth/RBAC, ML Registry & Fail-Closed Inference)

Milestone 6 transforms the Streamlit front-end (`app.py` + `src/voxneuro/ui/`) and backend operations into a role-separated research platform while preserving every M0–M5 scientific, privacy, and fail-closed safety invariant:

1. **Responsive Role-Separated Web Interface (`src/voxneuro/ui/` & `app.py`)**
   - `src/voxneuro/ui/theme.py`: Warm editorial palette, responsive CSS breakpoints, accessible keyboard focus rings, mandatory non-diagnostic banner (`render_medical_disclaimer()`), 6-step guided progress bar (`Prepare -> Consent -> Record -> Quality -> Features -> Result`), and plain-language `PredictionResult` cards.
   - `src/voxneuro/ui/consumer_pages.py`: Public landing hero, "How VoxNeuro Works", "Privacy & Safety", "Help & FAQ", opt-in consent step backed by SQLite, authenticated participant "My History", and "Account" registration/sign-in/password-reset/profile portal.
   - `src/voxneuro/ui/admin_portals.py`: Server-side RBAC-gated Researcher Portal, ML Model Registry & Governance Portal, and System Administration & Security Portal. Sidebar initializes collapsed (`initial_sidebar_state="collapsed"`) with synchronized compatibility controls (`voxneuro_nav` / `voxneuro_m6_view`).

2. **Database Schema v006 & Authentication / RBAC (`src/voxneuro/study/migrations/006_m6_platform_and_ml_registry.sql`, `src/voxneuro/study/auth.py`)**
   - Extends SQLite from 13 to 24 tables (`users`, `user_sessions`, `password_reset_tokens`, `training_datasets`, `training_runs`, `model_versions`, `model_evaluations`, `model_domain_approvals`, `prediction_records`, `abstention_events`, `model_lifecycle_events`).
   - Uses PBKDF2-HMAC-SHA256 (`200,000` iterations) per-user salts, stores only SHA-256 hashes of session and single-use reset tokens, assigns `'participant'` by default on public registration, and enforces timing-safe role checks server-side.
   - `src/voxneuro/study/withdrawal.py`: Participant withdrawal purges any retained `prediction_records` alongside `derived_features`.

3. **Leakage-Free ML Benchmarking, Calibration & Model Registry (`src/voxneuro/modeling/dataset_readiness.py`, `m6_experiment.py`, `m6_training_ops.py`, `model_registry.py`)**
   - Enforces participant-disjoint grouped CV (`verify_participant_split_integrity`), rejects target/identifier column leakage, runs Models A–D and multi-family benchmarks (`logistic_regression`, `linear_svm_calibrated`, `rbf_svm`, `random_forest`, `extra_trees`, `hist_gradient_boosting`, `dummy_prior`), computes Brier score / ECE reliability bins / threshold curves / `N >= 10` subgroup summaries, and enforces fail-closed lifecycle transitions (`RESEARCH_INFERENCE_APPROVED` requires `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` verification and exact bundle SHA-256 matching).

4. **Standalone Fail-Closed Prediction Service (`src/voxneuro/modeling/prediction_service.py`)**
   - Decoupled from Streamlit rendering (`run_prediction_service()` / `evaluate_audio_bytes_research()`). Enforces audio quality, disallowed capture origin, disabled microphone inference, feature schema matching, OOD z-score checks, consent/DUA verification, and bundle SHA-256 verification before returning scores—otherwise abstains cleanly with telemetry and never persists raw audio or predictions without explicit opt-in consent.
