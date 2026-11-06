# Verification Pass 1 — Functional QA

**Historical snapshot note:** The test counts and schema version below describe the earlier v2 source snapshot. Later audits found additional defects. Current code, test, and data results are in `docs/testing/VERIFICATION_REPORT.md` and `docs/audit/VERIFICATION_PASS_3.md`.

**Reviewer role:** implementing engineer / senior functional QA. This pass checks real program behavior and explicit regression cases; it is not independent from implementation.

## Results (2026-11-06)

- Full CPython 3.12 locked development suite: `uv run --extra dev --locked python -m pytest -q` → **99 passed**.
- Coverage run: `python -m pytest -q --cov=src/voxneuro --cov-report=term-missing` → **99 passed, 88% statement coverage** (905 statements, 111 missed).
- `ruff check .` → **All checks passed**; `ruff format --check .` → **131 files already formatted**.
- `scripts/verify_project.py` → 10 imports and 7 required files passed.
- Dataset source inspection: UAMS 81/81 WAVEX/FLOAT mono at 8 kHz; official archive checksums matched; expected 40 PD/41 HC. UCI-only mode inspected 756×755, 252 participants, three recordings each, 1 exact duplicate row.
- Manifest rebuild and audit: 81/81 source label/metadata matches; no duplicate waveform hashes or integrity issues. Age means HC=47.73, PD=67.04; standardized mean difference −1.61.
- Feature extraction: 78/81 accepted only with the explicit reviewed-exclusion option; the three named PD clipping failures are present in the policy and extraction report.
- Regenerated participant-grouped experiments: UAMS age-only 0.825±0.074 BA; voice logistic 0.659±0.134; RF 0.758±0.094; RBF SVM 0.760±0.066. UCI separate feature benchmark: logistic 0.766±0.043; RF 0.727±0.056; SVM 0.715±0.052. UCI duplicate-removal sensitivity was also rerun.
- Model training only proceeded with current feature/evaluation receipts; `verify_model.py` checked checksum, current provenance, reload prediction consistency, research-only status, and unverified domain.
- Streamlit AppTest covered a synthetic upload through validation, extraction, display, report, and download control. No class prediction was returned. A live preview confirmed navigation/empty states and research plot rendering.

## Issues caught and corrected during QA/release

The functional suite caught a test-fixture update needed after making required source metadata explicit. The release lint pass caught import ordering, line-length, and a late-bound UI callback issue; these were fixed and rechecked. The independent reviewer then found two additional data-workflow issues; their correction and re-verification are in Pass 2. Coverage review also added direct tests for table/manifest helpers, calibration guards, the model-card template, and grouped metric plotting.

## Boundaries

This pass did not grant browser microphone permission or capture a physical voice. Synthetic audio and software rendering do not establish device behavior, clinical validity, or a clinical need.
