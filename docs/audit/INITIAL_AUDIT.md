# Initial Audit

Date: 2026-11-06
Workspace: VoxNeuro/ (Windows workspace)
Branch: main (local repository initialized; no commit or remote)

## Baseline evidence

- Python: CPython 3.12.14 from .venv
- Runtime suite: uv run --locked python -m pytest -q — 74 passed
- Lint: uv run --locked ruff check . — passed
- Formatting: uv run --locked ruff format --check . — 110 files already formatted
- Import/file check: uv run --locked python scripts/verify_project.py — 10 imports and 7 required files passed
- Model check: uv run --locked python scripts/verify_model.py — artifact checksum, current provenance, reload, prediction consistency, and research/domain flags passed

## Repository state

The code is separated into src/voxneuro modules for audio, features, datasets, modeling, reporting, and visualization, with top-level scripts, configuration, tests, and Biodesign/research documentation. Local raw/interim data and model artifacts are present for verification but excluded from the audit ZIP. The inventory is in PROJECT_FILE_INVENTORY.md.

## Initial issues accepted for repair

The supplied audit identifies additional defects beyond the already repaired baseline: manifest and feature-table validation gaps; incomplete prediction safeguards; archive extraction and checksum handling; stale evaluation display; UI state ambiguity; missing UCI evaluation directory creation; and a duplicate UCI row requiring sensitivity analysis. These are treated as hypotheses until reproduced against the current checkout and documented in the repair log.

## Verification limits at baseline

- No physical microphone test or clinician/stakeholder validation is represented by these software checks.
- Dataset/model evaluation artifacts are local to this workstation and are omitted from the audit ZIP.
- Initial test results demonstrate the current state before the new edits, not the final release state.
