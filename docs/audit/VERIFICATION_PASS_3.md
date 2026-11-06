# Historical Verification Pass 3 — Clean source-ZIP release check

This is a historical release check for an earlier source snapshot and has been superseded by [`../testing/VERIFICATION_REPORT.md`](../testing/VERIFICATION_REPORT.md). Its test and formatter counts are not current. It verifies packaging and software setup only; it is not an independent code review or clinical validation.

## Distribution structure

| Check | Result |
|---|---|
| ZIP CRC and member readability | PASS |
| Required source, configuration, tests, lockfiles, and documentation | PASS |
| `.git`, virtual environments, Python caches, node_modules absent | PASS |
| Raw/interim/processed data, model binaries, and temporary caches excluded | PASS |
| Duplicate members, absolute paths, and parent traversal absent | PASS |

## Clean extracted environment

The ZIP was extracted to a new temporary directory containing no datasets or model artifacts. A fresh CPython 3.12.14 environment was created from the included lockfiles. `uv sync --all-extras --locked` installed 71 packages.

| Check | Result |
|---|---|
| `python -m pytest -q` | PASS on that earlier snapshot; current test count is in `VERIFICATION_REPORT.md`. |
| `ruff check --no-cache .` | PASS; all checks passed. |
| `ruff format --check .` | PASS on that earlier snapshot; current formatter result is in `VERIFICATION_REPORT.md`. |
| `python scripts/verify_project.py` | PASS; 10 imports and 7 required files. |
| Streamlit startup and `/_stcore/health` | PASS; `/` returned HTTP 200 and health returned `ok`. |
| Data/model commands without local datasets/artifacts | Correctly unavailable because the source ZIP omits these generated/private inputs. |

## Data-rich workspace checks

Separately, the current working tree passed UAMS archive checksum, manifest, audit, and v3 feature-extraction checks. The 78/81 extraction result uses only the three named reviewed PD clipping exclusions. Grouped UAMS and separate UCI evaluations were regenerated; the research-only model was retrained and `verify_model.py` passed against current receipts and code. These data and model artifacts are not included in the ZIP.

## Release limits

The clean-package tests used synthetic audio. No physical microphone, browser/OS permission, stakeholder or participant study, external clinical cohort, ethics approval, or regulatory review was performed. The application is an acoustic-analysis prototype and does not classify new recordings.
