# Current Test and Verification Results

**Authoritative Production Verification Run:** Verified on 2026-11-13 in the locked Windows/Python 3.12 environment (`CPython 3.12.14`). Full methodology, clinical disclaimers, and scientific limitations are in [the verification report](testing/VERIFICATION_REPORT.md).

| Check | Result |
|---|---|
| Environment | Windows 11, CPython 3.12.14; uv-managed virtualenv; 71 locked Python packages checked. |
| Python tests | **600 passed** (583 non-UI tests and 17 Streamlit UI tests; 0 failed, 0 skipped). |
| Source coverage | **86.03%** statement coverage across 7,869 statements in `src/voxneuro` (exceeds required 85.0% threshold). |
| Ruff | Lint passed (`0 errors` across 300 files); formatter check passed across all repository files. |
| Project verification | 17 required module imports, 10 required files, and release provenance verified (`scripts/verify_project.py`). |
| Model verification | Research model bundle reload, checksums, and safety gates verified (`scripts/verify_model.py`). |
| Dataset audit | UAMS: 81 records (41 HC / 40 PD), 81 participants, zero label, waveform-hash, demographic, or age-integrity issues. |
| UAMS feature extraction | 78/81 accepted under the exact reviewed exclusion policy; all three clipped exclusions are PD. |
| Nested UAMS modeling | Repeated 5-outer/3-inner participant-grouped evaluation with three seeds and 1,000 primary-seed participant bootstrap resamples; report and receipts current. Age-only BA is 0.8389 ± 0.007; the highest voice-only mean BA is Extra Trees at 0.7663 ± 0.008 (ROC-AUC 0.7851). |
| Fixed benchmark (M6) | Protocol B fixed-seed benchmark yields Extra Trees BA 0.7821, Random Forest BA 0.7726. |
| UCI benchmark | Separate grouped evaluation passed for 756 rows / 252 participants / 752 predictors. |
| Model bundle | Tuned logistic reference trained; current dataset/code/evaluation/schema provenance and deterministic reload verification passed. Microphone disease inference remains strictly disabled fail-closed. |
| Frontend visualizer | Three.js visualizer bundle built and verified against git tree; vitest tests passing. |
| Release archive | `VoxNeuro_PRODUCTION_RELEASE.zip` rebuilt and verified with detached `.sha256` checksum sidecar. |

---

## Historical Milestones (Historical Context Only)

- **Milestone 1 Checkpoint (2026-11-07):** 310 tests passed (302 non-UI, 8 AppTests), 87.05% coverage across 2,232 statements.
- **Milestone 5 Checkpoint (2026-11-10):** 566 tests passed.
- **Milestone 6 Checkpoint (2026-11-12):** 590 tests passed.
- **Production Release Final (2026-11-13):** 600 tests passed, 86.03% coverage across 7,869 statements.

> [!IMPORTANT]
> The browser upload demonstration uses generated synthetic audio or local research audio. Physical microphone/OS permissions, external-cohort performance, clinical validity, and regulatory status remain unverified. VoxNeuro is an academic research software prototype and does not provide clinical diagnostic utility.
