# Current test and verification results

Verified on 2026-11-07 in the locked Windows/Python 3.12 environment. Full details and scientific limits are in [the verification report](testing/VERIFICATION_REPORT.md).

| Check | Result |
|---|---|
| Environment | Windows 11, CPython 3.12.14; uv 0.12.5; 71 locked Python packages checked. |
| Python tests | **216 passed**: 210 non-UI tests and all 6 Streamlit AppTests. |
| Source coverage | **87%** across 1,791 statements in `src/voxneuro`. |
| Ruff | Lint passed; formatter check passed with 153 files already formatted. |
| Project verification | 11 required imports and 8 required files passed. |
| Dataset audit | UAMS: 81 records (41 HC/40 PD), 81 participants, zero label, waveform-hash, demographic, or age-integrity issues. |
| UAMS feature extraction | 78/81 accepted under the exact reviewed exclusion policy; all three clipped exclusions are PD. |
| Nested UAMS modeling | Repeated 5-outer/3-inner participant-grouped evaluation with three seeds and 1,000 primary-seed participant bootstrap resamples; report and receipts regenerated. Age-only BA was 0.839 ± 0.007; the highest voice-only mean BA was Extra Trees at 0.766 ± 0.019. |
| UCI benchmark | Separate grouped evaluation passed for 756 rows / 252 participants / 752 predictors, with one exact duplicate row handled in a separate sensitivity run. |
| Model bundle | Tuned logistic reference trained; current dataset/code/evaluation/schema provenance and deterministic reload verification passed. Microphone inference remains disabled. |
| Frontend | npm ci succeeded with zero reported vulnerabilities; three JavaScript tests passed; local visualizer bundle built successfully. |
| Browser | Chrome workflow passed with synthetic WAV upload, analysis, 3D waveform/spectrogram, camera reset, hidden-tab resume, and WebGL-disabled responsive fallback; no page errors. |
| WAV report | Actual UAMS training-cohort WAV passed decoding, quality validation and Core39 feature extraction; a local self-contained HTML smoke report was generated. No disease classification was made. |
| Source archive | `VoxNeuro_source_audit.zip` rebuilt and CRC/inventory validated: 180 files. |
| AI review bundle | 191 files: the same 180 source files plus 11 hashed aggregate-evidence attachments; CRC and inventory checks passed. |
| Extracted bundle tests | The full 216-test suite passed from a clean extraction with the extracted `src/` explicitly first on `PYTHONPATH`; coverage rounded to 87%. |

The browser upload used generated synthetic audio. The separate WAV smoke test used a development-cohort UAMS recording and is not independent validation. Physical microphone/OS permissions, external-cohort performance, clinical validity, and regulatory status remain unverified.
