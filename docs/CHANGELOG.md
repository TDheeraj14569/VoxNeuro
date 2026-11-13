# Changelog

## 2026-11-13 — Individual exploratory-result and provenance-gate repair

- Separated recording capture origin (upload/live browser microphone) from the acquisition-device category declared by the user; uploads no longer masquerade as a known hardware domain.
- Preserved the approved inference gate: `allow_user_microphone_inference` remains false, the trusted domain-validation allowlist is empty, and no clinical prediction is authorized.
- Added a separate exploratory candidate path that requires a locally generated trusted model, current extraction/evaluation/nested-evaluation receipts, current code/data/schema/configuration provenance, valid quality/task, exact complete Core39 features, explicit domain declaration, and training-only OOD checks. Severe or unevaluable OOD, missing or stale evidence, invalid inputs, or an unknown domain yield a specific abstention.
- Exploratory output is labeled **EXPLORATORY — NOT DOMAIN VALIDATED** and shows a raw uncalibrated decision score with a fixed research threshold, not a probability. Reports retain the outcome and reason, and acoustic findings remain available on abstention.
- Fixed the blank result panel by rendering the result card as a single HTML block. Updated current guides, model card, reports, risk note, and verification evidence to match actual behavior and current measured metrics.
- Generated and verified the research model only from the locally available authorized UAMS dataset; raw audio, participant-level records, model binaries, and receipts remain excluded from the GitHub source release.

## 2026-11-07 — Nested research-model evaluation and provenance verification

- Added repeated nested participant-grouped evaluation for seven voice-only model families, with grouped inner tuning, participant-level out-of-fold metrics, bootstrap intervals, and selected-parameter reporting.
- Added same-split age-only and age-plus-voice comparators to make the cohort's age confounding visible.
- Retrained the L2 logistic research reference only after current extraction and nested-evaluation receipts passed validation.
- Fixed model verification to validate and hash both the standard and nested evaluation receipts; added regression coverage for ordered multi-file provenance hashes.
- Generated a standalone UAMS nested-model comparison report, a dataset-audit HTML report, and an actual UAMS WAV feature-analysis smoke report. The WAV report makes no disease classification.
- Re-ran the separate UCI grouped benchmark; kept the feature-table scores isolated from raw-audio results.
- Added dataset catalog, validation protocol, inference guide, and reproducibility record. No new microphone inference or clinical claim was enabled.

## 2026-11-06 — Source audit and research-prototype hardening

- Fixed direct `BytesIO` WAV decoding, report schema metadata preservation, explicit diagnosis normalization, and malformed feature-table value rejection.
- Added fail-closed manifest validation that recomputes diagnosis agreement from source labels and `PD_AH` / `HC_AH` audio folders, validates audio-derived sample IDs against participant metadata, and checks required source metadata.
- Added independent `--dataset uams|uci|all` archive-inspection modes so UCI review does not require UAMS files.
- Strengthened archive checksum/path checks, staged extraction, manifest/hash validation, explicit reviewed feature exclusions, and content/config/code/evaluation receipts.
- Added model-domain, feature-schema, missing-input, and artifact-integrity safeguards. The app still withholds microphone classification.
- Added UCI exact-duplicate sensitivity analysis.
- Refined Streamlit navigation, research charts, and explicit empty/error states; added regression tests and standalone project guides/cards.
- Rebuilt the source-only ZIP after final review. See `docs/testing/VERIFICATION_REPORT.md` for the archive's final content and hash.
