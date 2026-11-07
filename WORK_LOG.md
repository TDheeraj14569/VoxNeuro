# VoxNeuro defect repair and release verification

**Date:** 2026-11-06 to 2026-11-07  
**Workspace:** Local project root

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

## Latest verification completed — 2026-11-07

- Locked environment: CPython 3.12.14; uv 0.12.5; `uv sync --all-extras --locked` checked 71 packages.
- Full suite: **216 passed** (210 non-UI tests plus six Streamlit AppTests); **87% coverage** across 1,791 statements.
- Ruff 0.17.3 lint passed; format check passed with 153 files already formatted. Project verification passed 11 imports and 8 required files.
- UAMS audit passed for 81 rows/81 participants with no label, duplicate-waveform, or demographic-age issues. Current Core39 extraction accepted 78/81 recordings under the reviewed policy; all three clipped exclusions are PD.
- Repeated nested UAMS model selection/evaluation completed with five outer folds, three inner folds, three seeds, and participant bootstrap intervals. Extra Trees had the highest mean voice-only BA at 0.766 ± 0.019; age-only logistic was 0.839 ± 0.007. The age imbalance and PD-only exclusions prevent disease-specific interpretation.
- The separate UCI grouped benchmark ran on 756 rows / 252 participants; its table is not raw-audio validation.
- Tuned L2 logistic research reference trained and verified against current code, data, schema, and standard/nested evaluation receipts. App microphone classification remains disabled.
- Regenerated the grouped UAMS and nested UAMS receipts, UCI grouped evaluation, and research model against the current source fingerprint; model verification passed.
- Generated a UAMS nested evaluation HTML report, aggregate-only dataset-audit HTML report, and an HTML Core39 smoke report from an actual UAMS development-cohort WAV. The aggregate audit omits sample IDs; the AI-bundle extraction receipt retains the exclusion count while redacting the ID list. No disease class was emitted for the WAV.
- Python suite includes five Streamlit AppTests. Frontend npm tests passed (3/3), build succeeded, and browser workflow passed for synthetic upload, analysis, 3D views, tab visibility resume, camera reset, and WebGL fallback.
- Opened the current app in Chrome at the local address. Physical microphone/OS permissions were not tested.
- Rebuilt the source archive and generated both inventories from the same inclusion rules. ZIP integrity passed: 180 source files. Review-only README/evidence files are explicitly excluded from source inventory calculations.
- Built and CRC-checked the AI review bundle: 191 files total (180 source files plus 11 review attachments); no audio, participant-level feature/prediction table, or model binary is included.
- Re-extracted the AI review ZIP and reran all 216 tests with its `src/` first on `PYTHONPATH`; all passed at 87% coverage.
- Current source/model provenance fingerprint: `65942228163857cf526d5881703a668717981347f6a6a90932ff489f339687c5`.

## Limits retained

No physical microphone recording, browser/OS permission test, external clinical cohort, clinician or participant study, ethics approval, regulatory opinion, or clinical-use claim is represented as completed. The app extracts and reports acoustic features; it does not diagnose or classify new recordings. The source ZIP excludes raw datasets, participant-linked processed files, and trained model artifacts.
