# Historical end-to-end verification — superseded

This audit records an earlier source snapshot and is superseded by [`VERIFICATION_REPORT.md`](VERIFICATION_REPORT.md). The reported test counts and workflow checks below do not describe the current snapshot. Physical microphone and clinical validation were not claimed.

## Reproduced workflow

- `uv sync --all-extras --locked` checked 71 pinned packages under CPython 3.12.14.
- Pytest and coverage passed on that earlier snapshot; current counts are recorded in `VERIFICATION_REPORT.md`.
- Ruff lint and formatting checks passed; `scripts/verify_project.py` passed 10 imports and 7 required files.
- UAMS archive checks, manifest build, and dataset audit passed. Feature extraction accepted 78/81 recordings under the exact reviewed-exclusion policy. Grouped UAMS metrics and the model bundle were regenerated, and `verify_model.py` passed against current receipts and code provenance.
- UCI inspection and grouped feature-table evaluation completed separately. The duplicate-row sensitivity output was regenerated and is not treated as raw-audio or microphone validation.
- Streamlit AppTest completed a synthetic WAV upload through quality validation, feature extraction, CSV provenance, report generation, and download controls. The app returned no disease classification. The local server health endpoint returned `ok` and the homepage returned HTTP 200.
- The compact source archive builder checks required source/config/tests/docs, excludes private data/environments/caches/model binaries, and validates ZIP CRC.

## Regression coverage

| Area | Covered failure cases |
|---|---|
| Audio and decoding | Empty/malformed WAV, direct `BytesIO`, WAVEX, low/long/short/unvoiced/clipped signals, non-finite samples, stereo phase cancellation, configured trim frames |
| Feature extraction | Stereo arrays rejected, all six F0 summaries withheld below three voiced frames, MFCC count fixed at 13, dimensions/validity described correctly |
| Dataset integrity | Unknown labels, inconsistent duplicate metadata, missing/false manifest matches, malformed/missing age, Boolean acoustic values, invalid/duplicate hashes, audit nonzero status, unsafe/partial archive extraction |
| Model and reporting | Domain alias/type checks, name-list-only compatibility claims rejected, evidence report integrity and source allowlist required, missing/invalid feature values, schema mismatch, Average Precision naming, report/CSV provenance |
| App workflow | Synthetic WAV upload → validation → feature extraction → feature analysis → provenance-bearing CSV → report/download controls; no disease classification |

## Not reproduced

- Physical microphone capture and browser/OS permission on a target device.
- External clinical performance, clinician feedback, patient/stakeholder workflow, ethics approval, or regulatory authorization.
- Cohort metric regeneration from the source ZIP alone; raw datasets and generated tables/models are intentionally excluded.
