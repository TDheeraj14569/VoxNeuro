# Historical software verification — superseded

This audit records an earlier source snapshot and is superseded by [`VERIFICATION_REPORT.md`](VERIFICATION_REPORT.md). Its test and formatter counts are historical, not current. It is an implementation verification record, not an independent clinical or regulatory review.

## Earlier snapshot evidence

- `uv sync --all-extras --locked`: 71 pinned packages checked.
- Pytest, Ruff lint, and Ruff formatting passed on that earlier snapshot. Current counts are recorded in `VERIFICATION_REPORT.md`.
- `scripts/verify_project.py`: 10 module imports and 7 required files passed.
- `scripts/verify_model.py`: current bundle checksum, dataset/evaluation/code provenance, schema, reload, and deterministic prediction checks passed.
- Streamlit AppTest completed synthetic WAV upload, quality validation, feature extraction, provenance-bearing CSV, report, and download-control flow. It returned no disease classification.
- The local server returned `ok` from `/_stcore/health` and HTTP 200 from `/`; no browser microphone permission was granted and no physical microphone was tested.

## Regression coverage added for reviewed defects

- Direct `BytesIO` decoding, WAVEX support, and corrected WAV/WAVEX wording.
- JSON report and feature CSV retain schema/config provenance.
- Unknown diagnosis labels, conflicting duplicate metadata, malformed/missing ages, and Boolean measurements are rejected or reported safely.
- ZIP checksum, path-safety, completeness, and partial-extraction safeguards.
- Dataset audit fails closed on label/data integrity failures and counts only valid duplicate hashes.
- Stereo feature input is rejected; all F0 summaries require three voiced frames; MFCC count is fixed at 13.
- Model-domain strings are canonicalized, microphone aliases are blocked, untrusted evidence cannot verify a domain, and malformed input-domain values raise controlled errors.
- Average Precision is named accurately; schema validity, MFCC units, export provenance, and test traceability were corrected.

## Limits

Synthetic audio verifies software flow only. It does not establish physical microphone behavior, external model performance, stakeholder need, clinical validity, or suitability for healthcare decisions.
