# VoxNeuro defect repair and release verification

**Date:** 2026-11-06 to 2026-11-07  
**Workspace:** Local project root

## Audit findings & UI glassy redesign resolution (2026-11-07)

- **UI & Hover Redesign:** Eliminated all white button hover and focus artifacts across the application using high-specificity CSS (`html body div.stApp button:hover:not(:disabled)`). Buttons now feature dark-glass gradients (`rgba(26, 82, 100, 0.98)`), glowing emerald borders (`#55D9C1`), crisp white text, and smooth elevation.
- **Dark Glass Tables:** Applied uniform glassmorphism (`backdrop-filter: blur(20px)`, dark-teal gradients, glowing borders, uppercase headers, zebra striping, and interactive row highlight) across all 7 sections (`Overview`, `Voice assessment`, `Signal analysis`, `Feature analysis`, `Research model`, `Reports`, `Method & privacy`).
- **Reports Overhaul:** Completely resolved report visibility issues by replacing raw JSON displays and canvas dataframes with executive telemetry cards, the full 39-feature glass table, recorded audio SHA-256 and schema/configuration fingerprints, and prominent download buttons (HTML, JSON, CSV).
- **Clipping Display Correction:** Replaced hardcoded "0% clipping" in the decision panel with actual measured clipping percentages (`{quality.clipping_fraction * 100:.4f}% clipping`).
- **Safety Terminology Alignment:** Replaced unsupported "AUDIT CERTIFICATE" and "cryptographic provenance verification" claims with accurate research wording: "VOICE SIGNAL ANALYSIS REPORT", "Audio quality checks passed", and "Schema and configuration fingerprints recorded".
- **Strict Predictor Identity Contracts:** Enforced 1-to-1 matching for `sample_id` and `participant_id` between $X$ and additional predictors in `evaluate_grouped()`, rejecting one-sided presence and sequence mismatches.
- **Audio Validation Hardening:** Rejected complex-valued, object, and boolean audio arrays with structured errors (`Audio samples must contain real numeric values.`). Validated sample rates independently in `AudioRecord.__post_init__()` and rejected 3-channel WAVs with `AudioReadError`.
- **Harmonic Screening Reframing:** Reframed synthetic generator checks as acoustic task screening criteria. Added configurable thresholds to `audio_config.yaml`.
- **Test Suite & Receipts:** Full suite expanded through intermediate checkpoints (247, 252, and 265 tests) to **296 passed tests** (288 unit/pipeline tests and 8 Streamlit AppTests) with 86.81% statement coverage. Regenerated model receipts, model bundle, and deterministic audit archives.

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

## Latest verification completed — 2026-11-07 (296-test suite)

- **Test Suite & Coverage:** Expanded to **296 passed tests** (288 non-UI tests plus 8 Streamlit AppTests) with **86.81% statement coverage** in `src/voxneuro`.
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

## Limits retained

No physical microphone recording, browser/OS permission test, external clinical cohort, clinician or participant study, ethics approval, regulatory opinion, or clinical-use claim is represented as completed. The app extracts and reports acoustic features; it does not diagnose or classify new recordings. The source ZIP excludes raw datasets, participant-linked processed files, and trained model artifacts.
