# VoxNeuro defect repair and release verification

**Historical log:** most entries below describe snapshots from 2026-11-06 through 2026-11-08. Their test totals, coverage, CI status, and inference behavior are not the current release status. See [`docs/testing/VERIFICATION_REPORT.md`](docs/testing/VERIFICATION_REPORT.md) for the current checked snapshot.

**Date:** 2026-11-06 to 2026-11-08  
**Workspace:** Local project root

## Current GitHub-main follow-up — 2026-11-13

- Investigated the three supplied result screenshots against the local UAMS manifest. All are PD-labeled research recordings: two pass technical quality checks and one is rejected for clipping.
- Clarified the UI so an audio-quality pass is explicitly not a health or Parkinson's result, and changed the pass notice from success-green to neutral blue.
- Added an original-WAV SHA-256 overlap gate. An exact WAV already in the development manifest cannot receive an individual score from the full-refit model; it gets `KNOWN_TRAINING_RECORDING`. A missing fingerprint fails closed.
- Re-ran the UAMS archive verification, manifest build/audit, extraction, fixed grouped evaluation, three-repeat nested participant-grouped evaluation, model training, and model verification. All passed; 78/81 recordings were accepted under the reviewed exclusions.
- Nested L2 logistic evaluation had 27 true positives and 10 false negatives among 37 PD participants in each of three repeats. This does not support forcing a PD output for every PD-labeled WAV. The user's two usable screenshot WAVs are blocked from in-sample scoring; the clipped WAV is rejected before inference.
- Full CPython 3.12.14 suite: 611 passed, 0 failed; coverage 85.7% (7,108/8,294 statements). Ruff lint, Ruff format (303 files), and `verify_project.py` passed.
- The supplied browser screenshots establish that the user-visible page rendered before these last copy/safety edits. A new post-edit browser click-through and physical microphone permission check were not independently performed.
- Rebuilt source and production-named source archives: 351 files, 2,405,217 bytes, matching SHA-256 `0158e49781420b00d2f2713d54035ae6afb3db5e4efae171292f66a743f9bf6b`; ZIP CRC and exclusion checks passed. Raw WAVs, generated cohort tables, models, and environments remain excluded.

## External audit resolution & release hardening (2026-11-08)

- **Resampling Filter Overshoot & Amplitude Contract:** In `src/voxneuro/audio/preprocessing.py`, eliminated polyphase FIR filter overshoot (`samples = samples / peak if peak > 1.0`), preventing spurious amplitude violations on near-full-scale input audio. Enforced uniform normalized float and $[-1.0, 1.0]$ checks in `extract_praat_features` and `extract_spectral_features`.
- **SVM Decision Margin Tie-Breaking & Score-Kind Branching:** In `src/voxneuro/modeling/evaluation.py`, branched tie resolution (`y_pred == 0.5`) on model score-kind (`score >= 0.0` for `decision_function` margin scores vs `score >= 0.5` for `predict_proba` probabilities).
- **Positional Alignment Hardening:** In `_validate_additional_predictors`, rejected predictor tables on default `RangeIndex` lacking explicit `sample_id` or `participant_id` to prevent false positive matching on independently reordered DataFrames.
- **Dynamic Table Headers & Receipt Hardening:** In `app.py`, checked for `NaN` before string conversion in `_current_nested_evaluation_package()`, dynamically mapped glass table headers from `summary_cols`, set `toolbarMode = "minimal"` in `.streamlit/config.toml`, and gracefully handled unmeasured voiced fractions as `"Not measured"`.
- **Demographic Cohort & SD Discrepancy Reconciliation:** Clearly distinguished source manifest cohort (81 participants: 41 HC, 40 PD) from analyzed model cohort (78 participants: 41 HC, 37 PD), presenting both sample SD ($ddof=1$) and population SD ($ddof=0$).
- **Literature & Risk Documentation:** Corrected Atalar et al. (2023) citation, added 2025 Mizoram Indian feasibility study context and full PMC13652970 citation; clarified HAZ-07 accidental-tampering detection vs repository artifact security, and clarified why architectural controls reduce HAZ-01 severity from 4 to 3 supporting a hypothetical Class B profile.
- **3D Waveform Timeline Coordinates & Amplitude Depth:** Supported `start_seconds` in `waveform_payload` so detail slices display absolute timeline coordinates matching UI sliders; clarified ribbon depth varies with instantaneous absolute amplitude ($z \propto |amplitude|$); removed duplicated badge text in hero view.
- **Expanded Test Suite:** Expanded to **312 passed tests** (304 unit/pipeline + 8 UI AppTests) with 87%+ statement coverage across `src/voxneuro`. All 4 CI matrix jobs verified passing green on GitHub Actions.

- **UI & Hover Redesign:** Eliminated all white button hover and focus artifacts across the application using high-specificity CSS (`html body div.stApp button:hover:not(:disabled)`). Buttons now feature dark-glass gradients (`rgba(26, 82, 100, 0.98)`), glowing emerald borders (`#55D9C1`), crisp white text, and smooth elevation.
- **Dark Glass Tables:** Applied uniform glassmorphism (`backdrop-filter: blur(20px)`, dark-teal gradients, glowing borders, uppercase headers, zebra striping, and interactive row highlight) across all 7 sections (`Overview`, `Voice assessment`, `Signal analysis`, `Feature analysis`, `Research model`, `Reports`, `Method & privacy`).
- **Reports Overhaul:** Completely resolved report visibility issues by replacing raw JSON displays and canvas dataframes with executive telemetry cards, the full 39-feature glass table, recorded audio SHA-256 and schema/configuration fingerprints, and prominent download buttons (HTML, JSON, CSV).
- **Clipping Display Correction:** Replaced hardcoded "0% clipping" in the decision panel with actual measured clipping percentages (`{quality.clipping_fraction * 100:.4f}% clipping`).
- **Safety Terminology Alignment:** Replaced unsupported "AUDIT CERTIFICATE" and "cryptographic provenance verification" claims with accurate research wording: "VOICE SIGNAL ANALYSIS REPORT", "Audio quality checks passed", and "Schema and configuration fingerprints recorded".
- **Strict Predictor Identity Contracts:** Enforced 1-to-1 matching for `sample_id` and `participant_id` between $X$ and additional predictors in `evaluate_grouped()`, rejecting one-sided presence and sequence mismatches.
- **Audio Validation Hardening:** Rejected complex-valued, object, and boolean audio arrays with structured errors (`Audio samples must contain real numeric values.`). Validated sample rates independently in `AudioRecord.__post_init__()` and rejected 3-channel WAVs with `AudioReadError`.
- **Harmonic Screening Reframing:** Reframed synthetic generator checks as acoustic task screening criteria. Added configurable thresholds to `audio_config.yaml`.
- **Test Suite & Receipts:** Full suite expanded through intermediate checkpoints (247, 252, 265, 296, and 299 tests) to **310 passed tests** (302 unit/pipeline tests and 8 Streamlit AppTests) with 87.05% statement coverage across 2,232 statements. Regenerated model receipts, model bundle, and deterministic audit archives.

## Findings fixed

- Canonicalized recording domains and rejected microphone aliases before compatibility checks. Non-string domains now produce a controlled compatibility error.
- Stopped treating a domain-name list or a well-formed report as approval. A validation report must be structurally valid, its embedded hash must match, and a maintainer must explicitly allowlist that hash in source control. The current allowlist is empty.
- Rejected multichannel arrays at the mono feature-extraction boundary instead of flattening/interleaving channels.
- Made demographic summaries tolerate malformed values and count missing, malformed, and out-of-range ages separately. Dataset feature validation now rejects Python and NumPy Boolean values.
- Enforced the schema's three-voiced-frame minimum for all F0 summaries; documented MFCC SD frame requirements and fixed the extractor to 13 MFCCs.
- Corrected MFCC units/method descriptions and bumped the feature contract to `voxneuro.voice.v3`.
- Renamed the `average_precision_score` output from `pr_auc` to `average_precision` in code and reporting.
- Added schema/configuration provenance columns to exported feature CSVs.
- Counted only valid SHA-256 values in the dataset audit's duplicate-hash summary.
- Rejected Python/NumPy Boolean participant ages and made invalid demographic ages fail the dataset audit.
- Required JSON receipts to have object roots and return controlled validation errors for arrays/scalars/null.
- Centralized UCI feature-table validation: exact cohort/participant structure, three repeats, binary diagnosis/gender coding, consistent per-participant metadata, and complete finite numeric predictors.
- Expanded microphone-domain blocks to phone, smartphone, mobile, browser/web, laptop/computer, and live-device aliases while keeping the telephone-collected UAMS domain distinct.
- Enforced the configured feature schema version against the implementation schema.
- Made preprocessing revalidate the original audio instead of trusting an unbound `AudioQuality` object; malformed array dimensions or channel metadata now return structured invalid-audio results before signal analysis.
- Defined clipping fraction as an inclusive maximum: equality passes, zero permits only clean recordings, and only a fraction above the threshold fails. Added zero/equality/below/above regressions.
- Rejected standalone stereo spectral input and cutoff frequencies at or above the effective Nyquist; configuration now requires the v3 schema's exact 13 MFCCs and a cutoff below the configured target-rate Nyquist.
- Automated both source-archive inventory documents from the archive builder and added tests for per-folder and total counts.
- Explained that logistic regression is bundled as an interpretable research reference, not because it led the small internal cross-validation scores.
- Excluded local environment files, Streamlit secrets, private keys, and sensitive certificate formats from review archives; added matching Git ignore rules.
- Regenerated the source archive's included-file inventory and counts.
- Used the configured frame duration in silence trimming, corrected supported WAV/WAVEX instructions, and fixed the traceability test paths.
- Reconciled verification and test documentation with the current source snapshot; earlier pass reports are marked as historical.

## Historical verification completed — 2026-11-07 (310-test suite)

- **Test Suite & Coverage:** Expanded to **310 passed tests** (302 non-UI tests plus 8 Streamlit AppTests) with **87.05% statement coverage** across 2,232 statements in `src/voxneuro`.
- **Feature Extraction Array Validation:** Enforced strict non-boolean, non-complex, finite numeric array requirements, bounded extraction parameters, and integer sample rate validation (8–48 kHz) in standalone `extract_features()`. Added comprehensive regression tests.
- **Audio Validation Config & Early Exit:** Added `AudioValidationConfig.from_dict()` with strict non-coercing type validation, early-exit on invalid audio duration or silence before Praat/FFT execution, and configurable second harmonic overtone bounds.
- **Manifest Sample Hierarchy:** Added prioritized ID tier matching (`sample_id` > `participant_id` > `id`) and ambiguous key rejection in `build_manifest.py`.
- **Visualization Safety:** Hardened `waveform.py` and `spectrogram.py` with parameter validation (sample rate, n_fft, hop_length) and downmix/channel checks.
- **Model Tuning Alignment & Dynamic Findings:** Aligned reference model training in `train_model.py` to 3-fold inner cross-validation (`inner_cv_splits`). Dynamically derived Key Research Findings in `app.py` from nested evaluation outputs.
- **Dynamic Limitation Counts:** Derived participant cohort counts dynamically from dataset frames in `evaluate_nested_models.py` and synchronized random seed generation.
- **HTML Report Enhancements:** Displayed recorded audio SHA-256 fingerprint, outer-fold ROC-AUC and Average Precision, and migrated template substitution to safe `string.Template`.
- **Ruff & Quality Gates:** All 153 repository files formatted with Ruff; zero lint or style violations; all project and model verifiers passed green.
- **Deterministic Archives:** Rebuilt `VoxNeuro_source_audit.zip` (181 files) and `VoxNeuro_ai_review_bundle.zip` (192 files) with pre-replacement size validation and exact checksum verifications.
- **HNR Formula Correction:** Filtered out Praat's unvoiced/undefined frame marker (`-200 dB`) in `parselmouth_features.py` with `hnr > -199.0`, matching Praat's native `Get mean` harmonicity exactly.
- **Feature Schema & Provenance:** Updated `hnr_mean_db` definition in `schema.py` to "mean valid voiced frames". New schema fingerprint: `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f`.
- **Evaluation Hardening:** Replaced `groups[test]` indexing with `group_values[test]` in `evaluate_grouped()` to support lists and Series. Enforced strict `sample_id` uniqueness check in `_validate_additional_predictors()`.
- **Model Bundle TOCTOU Protection:** Closed TOCTOU gap in `model_bundle.load_bundle()` by hashing and deserializing from single-read in-memory bytes (`io.BytesIO(payload)`).
- **Matplotlib Memory Leak Elimination:** Converted all Matplotlib figure builders in `waveform.py`, `spectrogram.py`, `metrics.py`, and `app.py` to `Figure(figsize=...).subplots()`, preventing global pyplot figure dictionary accumulation.
- **Cross-Platform Line Ending Determinism:** Added `.gitattributes` (`* text=auto eol=lf`) and CRLF-to-LF normalization in `project_code_fingerprint()`.
- **Full Retraining & Artifact Re-Verification:** Successfully re-extracted 78 UAMS recordings, ran grouped and repeated nested CV (Extra Trees 0.762 ± 0.020 BA, age-only logistic 0.839 ± 0.007 BA), trained research logistic reference, and verified bundle reload and sidecar hashes.
- **Deterministic Release Bundles:** Rebuilt `VoxNeuro_source_audit.zip` (181 files) and `VoxNeuro_AI_review_bundle.zip` (192 files) with verified checksums.

### Historical verification snapshot (224-test suite)

- Locked environment: CPython 3.12.14; uv 0.12.5; `uv sync --all-extras --locked` checked 71 packages.
- Full suite: **224 passed** (218 non-UI tests plus six Streamlit AppTests); **87% coverage** across 1,934 statements.
- Ruff 0.17.3 lint passed; format check passed with 153 files already formatted. Project verification passed 11 imports and 8 required files.
- UAMS audit passed for 81 rows/81 participants with no label, duplicate-waveform, or demographic-age issues. Current Core39 extraction accepted 78/81 recordings under the reviewed policy; all three clipped exclusions are PD.
- Repeated nested UAMS model selection/evaluation completed with five outer folds, three inner folds, three seeds, and participant bootstrap intervals. Extra Trees had the highest mean voice-only BA at 0.766 ± 0.019; age-only logistic was 0.839 ± 0.007. The age imbalance and PD-only exclusions prevent disease-specific interpretation.
- The separate UCI grouped benchmark ran on 756 rows / 252 participants; its table is not raw-audio validation.
- Tuned L2 logistic research reference trained and verified against current code, data, schema, and standard/nested evaluation receipts. App microphone classification remains disabled.
- Regenerated the grouped UAMS and nested UAMS receipts, UCI grouped evaluation, and research model against the current source fingerprint; model verification passed.
- Generated a UAMS nested evaluation HTML report, aggregate-only dataset-audit HTML report, and an HTML Core39 smoke report from an actual UAMS development-cohort WAV. The aggregate audit omits sample IDs; the AI-bundle extraction receipt retains the exclusion count while redacting the ID list. No disease class was emitted for the WAV.
- Python suite includes six Streamlit AppTests. Frontend npm tests passed (3/3), build succeeded, and browser workflow passed for synthetic upload, analysis, 3D views, tab visibility resume, camera reset, and WebGL fallback.
- Opened the current app in Chrome at the local address. Physical microphone/OS permissions were not tested.
- Rebuilt the source archive and generated both inventories from the same inclusion rules. ZIP integrity passed: 180 source files. Review-only README/evidence files are explicitly excluded from source inventory calculations.
- Built and CRC-checked the AI review bundle: 191 files total (180 source files plus 11 review attachments); no audio, participant-level feature/prediction table, or model binary is included.
- Re-extracted the AI review ZIP and reran all 224 tests with its `src/` first on `PYTHONPATH`; all passed at 87% coverage.
- Current source/model provenance fingerprint: `e73319356c3512350d251de512393ccc95f034d49fee25e0043338a608167259`.

## Historical limits recorded on 2026-11-07

No physical microphone recording, browser/OS permission test, external clinical cohort, clinician or participant study, ethics approval, regulatory opinion, or clinical-use claim was represented as completed. The app extracted and reported acoustic features and did not classify new recordings in that historical snapshot. Current behavior and current verification evidence are in `docs/testing/VERIFICATION_REPORT.md`. The source ZIP excludes raw datasets, participant-linked processed files, and trained model artifacts.
