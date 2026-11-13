# Current verification report

**Checked:** 2026-11-13, Windows 11, CPython 3.12.14. Dependencies were synchronized from the checked-in lock with `uv sync --all-extras --locked`. Local datasets, participant-level tables, model binaries, and generated receipts are ignored and excluded from the source archive.

## Software checks

- Full Python suite: **611 passed, 0 failed**; statement coverage **85.7%** (7,108 of 8,294 statements) in `src/voxneuro`. The suite includes Streamlit AppTests and individual-result, training-audio-overlap, provenance, OOD, report, and abstention regressions.
- Ruff: lint passed; format check passed with 303 files already formatted.
- `scripts/verify_project.py`: 17 imports, 10 required files, project and frontend provenance passed.
- `scripts/verify_model.py --dataset uams`: local artifact checksum, deterministic bundle reload, current extraction/evaluation/nested-evaluation/code/config/schema provenance, and research-only/domain status passed.
- Frontend: `npm ci` reported zero vulnerabilities; three Node visualizer tests passed; `npm run build` succeeded; rebuilt 581.2 kB bundle matched the committed `dist/` output.
- Live Streamlit/browser verification is recorded below after it is completed. Physical microphone permission is a manual OS/browser check and is not claimed by these automated results.

## UAMS dataset and evaluation evidence

- The two downloaded UAMS archives matched the pinned Figshare hashes. Inspection found 81 mono WAVEX/FLOAT recordings at 8 kHz (41 HC, 40 PD), with no corrupt waveforms or duplicate audio hashes.
- Manifest construction matched all 81 workbook diagnosis labels and metadata records. The audit found no label, participant, age, or waveform-hash integrity issues.
- Feature extraction accepted 78/81 recordings. The only three exclusions are the documented clipped recordings, all from the PD group; that class-specific attrition can bias results.
- The UAMS age gap is large: HC mean 47.73 years (SD 14.33), PD mean 67.04 (SD 8.98), standardized mean difference -1.61, Mann–Whitney p=1.75e-8.
- Repeated nested evaluation used five participant-grouped outer folds, three grouped inner folds, and three prespecified repeats. Mean ± repeat SD balanced accuracy: age-only logistic 0.839 ± 0.007; voice-only Extra Trees 0.766 ± 0.008; voice-only L2 logistic 0.739 ± 0.007; age + voice logistic 0.771 ± 0.012. Results are internal estimates, not clinical accuracy.
- In the primary-seed paired analysis, adding voice to age changed balanced accuracy by -0.0758 (95% participant-bootstrap interval [-0.1842, +0.0284]); adding voice to age plus sex changed it by -0.0745 (95% interval [-0.1843, +0.0310]). Across repeated nested evaluation the corresponding mean differences were -0.0681 and -0.0762. Confidence intervals include zero and positive effects; the true incremental contribution remains uncertain.

## Individual result behavior and safety boundary

Capture origin (upload/live browser microphone) is tracked separately from the user-declared acquisition category. Upload type does not establish the hardware. The approved prediction path remains unavailable: `allow_user_microphone_inference` is false, the trusted domain-validation hash allowlist is empty, and the current local model remains research-only and domain-unverified.

When a trusted local research bundle and fresh receipts exist, a separate exploratory path may produce an **EXPLORATORY — NOT DOMAIN VALIDATED** candidate only after quality, task, complete ordered Core39 schema, provenance, declared-domain, and training-only out-of-distribution checks pass. It shows a raw uncalibrated score and fixed threshold, never a probability. Missing/stale evidence, unknown domain, invalid input, or severe/unmeasurable shift produces a specific abstention reason. The app also hashes the original uploaded WAV and withholds an exact recording already present in the development manifest as `KNOWN_TRAINING_RECORDING`; a full-refit in-sample score is not evidence of generalization. Acoustic measurements and reports remain available after abstention. A candidate is not a diagnosis, screening result, clinical accuracy estimate, or guide to care.

The 40 PD-labeled UAMS recordings were checked: all files are present, 37 pass the reviewed audio-quality policy, and 3 are excluded for clipping. In the three participant-grouped nested L2 logistic runs, each run had 27 true-positive and 10 false-negative PD participants among the 37 eligible participants. The user's two usable screenshot examples match exact development-cohort WAVs and are correctly blocked from individual scoring; the clipped example fails the quality gate. These reference labels and held-out model predictions are separate.

## Live browser verification

**Status: limited evidence.** User-provided screenshots show the localhost assessment page rendering its technical-quality pass, unknown-domain abstention, and clipping rejection states. The exact WAVs were checked against the local manifest and the current model/evaluation safeguards were exercised directly. A fresh post-change browser click-through, report download, and physical microphone/OS permission test were not independently performed.

## GitHub workflow status

Local verification does not establish GitHub Actions status. Check the repository's run for the pushed commit before calling CI green. External clinical validation, device compatibility, clinical need validation, ethics approval, and regulatory authorization have not been established.
