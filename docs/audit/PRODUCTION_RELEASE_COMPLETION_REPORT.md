# Release engineering verification — research prototype

**Snapshot:** 2026-11-13
**Repository baseline:** GitHub `main` at `dd80ffda11ddd1b0a0c0b6b32d2df4bff0b8c045` before this follow-up.
**Status:** Local engineering checks passed for this snapshot. VoxNeuro is not a production or clinically validated disease detector.

## Scope and safety status

VoxNeuro performs recording-quality checks, audio preprocessing, acoustic feature extraction, visualization, and reporting. The approved disease-prediction path remains disabled. A separate local research workflow can emit only an explicitly unvalidated exploratory candidate when its model, current evaluation receipts, source context, quality, schema, and out-of-distribution checks pass. Exact WAV files present in the model-development manifest are now blocked from individual scoring because a full-refit model would be evaluated in-sample.

A technical audio-quality pass means only that the signal can proceed to acoustic measurement. It does not imply a healthy voice or a Parkinson's diagnosis. No clinical validation, external prospective performance, microphone-domain validation, regulatory authorization, or treatment utility is established.

## UAMS data and model evidence

- Archive checksums matched the pinned Figshare records. The cohort contains 81 WAVs (41 healthy-control labels, 40 PD labels), all at 8 kHz.
- Manifest audit found no label, metadata, participant, or waveform-hash mismatches.
- Feature extraction accepted 78/81. Three PD-labeled recordings were excluded under the documented clipping policy.
- Three-repeat participant-grouped nested cross-validation with grouped inner tuning reported mean balanced accuracy: age-only logistic 0.839 ± 0.007; voice-only Extra Trees 0.766 ± 0.008; voice-only L2 logistic 0.739 ± 0.007; age-plus-voice logistic 0.771 ± 0.012.
- The L2 reference had sensitivity 0.730 and precision 0.723. In each reported repeat it produced 27 true-positive and 10 false-negative PD participants among the 37 quality-accepted PD recordings. It does not correctly identify every PD-labeled recording.
- Age imbalance is substantial (HC mean 47.73 years; PD mean 67.04; SMD -1.61). The age-only comparator exceeds the voice-only logistic reference, so voice-specific contribution remains uncertain.
- One supplied usable PD WAV was classified PD-like in all three held-out folds; a second was classified HC-like in two of three folds. Both exact source files are in the development dataset and are blocked from full-refit individual scoring. A third PD-labeled example fails clipping checks and is excluded.

These are internal research estimates from a small retrospective cohort, not diagnostic accuracy or evidence of clinical effectiveness.

## Local verification

| Check | Result |
|---|---|
| Python environment | CPython 3.12.14; locked dependencies |
| Full test suite | 610 passed, 0 failed |
| Coverage | 85.7% (7,108 of 8,294 source statements) |
| Ruff lint and format | Passed; 303 files formatted |
| Project verifier | 17 imports, 10 required files, provenance passed |
| UAMS model verifier | Bundle reload, checksum, current data/code/config/schema/evaluation provenance passed |
| Frontend checks | 3 tests passed; build succeeded; checked-in bundle matched build |
| Browser evidence | User-supplied screenshots show the app rendering quality-pass, unknown-domain abstention, and clipping-rejection states. No independent post-change browser click-through or physical microphone permission check is claimed. |
| GitHub Actions | Must be checked after the changes are pushed; local passes do not establish CI status. |

## Distribution contents

The source archive contains source code, configuration, tests, and documentation. It excludes raw participant audio, locally generated feature/prediction tables, trained model binaries, environments, and caches. The archive checksum and inventory are maintained separately in the root release manifest and checksum sidecar.

## Appropriate description

Use: **VoxNeuro — a Parkinson's-focused voice acoustic analysis research prototype.** Do not describe this release as a working diagnostic system or a clinically accurate detector.
