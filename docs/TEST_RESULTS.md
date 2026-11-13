# Current test and verification results

**Snapshot:** 2026-11-13, Windows 11, CPython 3.12.14, project dependencies synced with `uv sync --all-extras --locked`. See the [verification report](testing/VERIFICATION_REPORT.md) for execution scope and scientific limits.

| Check | Result |
|---|---|
| Python suite | **611 passed, 0 failed**; includes the Streamlit AppTests and regressions for result/provenance/abstention states. |
| Source coverage | **85.7%** across 8,294 statements in `src/voxneuro` (7,108 covered; above the CI 85% threshold). |
| Ruff | `ruff check .` passed; `ruff format --check .` passed with 303 files formatted. |
| Project verifier | 17 module imports, 10 required files, source and frontend provenance passed. |
| Model verifier | Fresh local model checksum, grouped evaluation receipts, current code/data/config/schema provenance, and deterministic reload passed. |
| UAMS audit and extraction | 81 recordings / 81 participants; 0 label mismatches, 0 duplicate waveform hashes; 78 accepted, with the three documented PD clipping exclusions. |
| Nested UAMS evaluation | Three repeated participant-grouped outer evaluations with grouped inner tuning. Age-only logistic BA 0.839 ± 0.007; voice-only Extra Trees 0.766 ± 0.008; voice-only L2 logistic 0.739 ± 0.007; age + voice 0.771 ± 0.012. Internal estimates only. |
| Frontend | `npm ci` reported 0 vulnerabilities; all 3 visualizer tests passed; build succeeded at 581.2 kB; committed bundle matched the build. |
| Local Streamlit browser | User-provided screenshots show the assessment page rendering the technical-quality pass, unknown-domain abstention, and clipped-recording rejection. The exact sample files were checked against the manifest and current inference safeguards. No independent post-change browser interaction or physical microphone/OS permission test is claimed. |
| Source archive | `VoxNeuro_source_audit.zip` and `VoxNeuro_PRODUCTION_RELEASE.zip` rebuilt; 351 files, 2,405,217 bytes; CRC, required inventory, and excluded-data rules passed. SHA-256 sidecars were regenerated. |
| GitHub Actions | Check the repository's latest `main` workflow run. This document does not substitute a local result for CI status. |

The UAMS means, age gap, and class-specific clipping exclusions limit interpretation. The age-only baseline is stronger than voice-only results. Neither internal cross-validation nor a local exploratory candidate establishes clinical accuracy, device compatibility, disease specificity, or a useful treatment decision. No model, cohort audio, participant-level feature table, or generated receipt is included in the source ZIP.

Earlier audit/test counts are historical and are not substitutes for the current snapshot above.
