# VoxNeuro Milestone 0: Baseline Integrity & Audit Report

**Date:** 2026-11-10  
**Milestone:** M0 – Baseline Integrity, Source Packaging & Documentation Repair  
**Auditor / Agent:** Antigravity (Gemini 3.8 Flash High)  
**Execution Environment:** Windows 11, PowerShell, CPython 3.12.16 via `uv`  

---

## 1. Current Git Branch and Working-Tree State

- **Branch:** `main`
- **Head Commit:** `27e6d8d Resolve audit defects: eliminate resampling filter overshoot, branch margin score tie-breaking, harden predictor positional contracts, support 3D timeline offsets, reconcile cohort demographics, and update literature citations`
- **Working-Tree Status (`git status --short`):**
  - `M docs/audit/PROJECT_FILE_INVENTORY.md` (Uncommitted user modifications; inventory count 183 reflecting local PDF)
  - `M docs/audit/PROJECT_FILE_INVENTORY_COUNTS.txt` (Uncommitted user modifications; inventory count 183)
  - `?? "Voice_Neuro_Detection_Need_Statement (1).pdf"` (Untracked 9-page PDF artifact)
  - `?? app.zip` (Untracked external distribution archive)
- **Repository Safety:** All existing user modifications and untracked files are preserved intact. No destructive Git commands (`clean`, `reset`, `checkout -f`) have been or will be executed. No automatic commits or pushes will be performed.

---

## 2. Python Environment and Dependency Management

- **System PATH Python:** Python 3.13.15
- **Project Virtual Environment:** CPython 3.12.16 (`<uv-managed-virtualenv>/python.exe`)
- **Package Manager:** `uv` 0.13.7
- **Specification:** `pyproject.toml` (`requires-python = ">=3.12,<3.13"`)
- **Lockfiles:**
  - `uv.lock` (150,073 bytes, locked)
  - `requirements-lock.txt` (41,112 bytes, locked)
- **Environment Verification:** `uv run python --version` correctly returns `Python 3.12.16`.

---

## 3. Repository Directory Structure

```text
VoxNeuro/
├── .github/workflows/          # CI workflows (ci.yml)
├── .streamlit/                 # Streamlit UI configuration (config.toml)
├── artifacts/                  # Local evaluation models and HTML reports (gitignored/placeholder)
├── configs/                    # YAML configuration files (audio_config.yaml, etc.)
├── data/                       # Datasets, manifests, extraction receipts (raw/interim/processed)
├── docs/                       # Project documentation, specifications, audits, and guides
│   ├── architecture/
│   ├── audit/
│   ├── biodesign/              # Biodesign need statements, protocols, scenarios
│   ├── clinical_validation/
│   ├── dataset/
│   ├── limitations/
│   ├── methodology/
│   ├── regulatory/
│   ├── reports/
│   ├── research/
│   └── testing/
├── frontend/                   # Local Three.js/WebGL visualizer bundle and manifests
│   └── acoustic-visualizer/
│       ├── dist/visualizer.bundle.js
│       ├── package.json
│       ├── package-lock.json
│       └── src/main.js
├── scripts/                    # Build, inspection, feature extraction, and verification scripts
├── src/voxneuro/               # Core Python package (audio, dataset, features, modeling, reporting)
├── tests/                      # Pytest suite (unit, integration, regression)
├── app.py                      # Main Streamlit application entrypoint
├── pyproject.toml              # Build system, dependencies, and tooling configuration
├── README.md                   # Project overview and instructions
├── requirements-lock.txt       # Frozen pip requirements
└── uv.lock                     # Locked uv dependency graph
```

---

## 4. Test Suite Baseline

- **Test Framework:** `pytest` 8.4.2 via `uv run python -m pytest -q`
- **Baseline Test Execution:** **316 passed in 74.72s** (0 failures, 0 errors)
- **Static Analysis (`ruff check .`):** Clean (All checks passed)
- **Code Formatting (`ruff format --check .`):** Clean (153 files already formatted)
- **Project Verification (`scripts/verify_project.py`):**
  - 11 required package module imports: PASS
  - 8 required files check: PASS
  - Release provenance calculation: PASS (`model_pipeline_fingerprint`: `6e238abd...`, `frontend_fingerprint`: `af9abde5...`)

---

## 5. Existing Packaging, Provenance, and Documentation Mechanisms

### A. Source Archive Generation (`scripts/build_source_archive.py`)
- Traverses repository files using `os.walk` while excluding standard build directories (`.git`, `.venv`, `.pytest_cache`, `__pycache__`, etc.), secrets, raw waveforms, models, and non-README data files.
- Enforces an arbitrary subset in `REQUIRED_FILES`:
  ```python
  REQUIRED_FILES = {
      "app.py",
      "README.md",
      "pyproject.toml",
      "requirements-lock.txt",
      "uv.lock",
      "src/voxneuro/__init__.py",
      "scripts/verify_project.py",
      "tests/__init__.py",
      "configs/audio_config.yaml",
      "docs/ARCHITECTURE.md",
  }
  ```
- Generates `VoxNeuro_source_audit.zip` with deterministic timestamps (1980-01-01 00:00:00).
- Automatically updates `docs/audit/PROJECT_FILE_INVENTORY.md` and `PROJECT_FILE_INVENTORY_COUNTS.txt`.

### B. Provenance Verification (`src/voxneuro/provenance.py`)
- Computes SHA-256 digests over:
  - Required root files: `app.py`, `pyproject.toml`, `requirements-lock.txt`, `uv.lock`, `.streamlit/config.toml`.
  - Python/YAML/JSON files in `src/`, `scripts/`, `configs/`.
  - Frontend visualizer bundle: `frontend/acoustic-visualizer/package.json`, `package-lock.json`, `src/main.js`, `dist/visualizer.bundle.js`.
- If any required file is missing, raises `FileNotFoundError`.

### C. PDF Generation Mechanism
- The untracked file `Voice_Neuro_Detection_Need_Statement (1).pdf` in the root is a 9-page, 12,288-byte PDF generated with ReportLab (ASCII85/Flate compressed streams).
- **No generator script exists in the repository.** No build command or editable source document is tracked.

---

## 6. Known Defects Reproduced During Inspection

1. **Packaging / Provenance Inconsistency (`.streamlit/config.toml`):**
   - `.streamlit/config.toml` exists in the local Git repository and working tree, and is strictly required by `src/voxneuro/provenance.py`.
   - However, `scripts/build_source_archive.py`'s `REQUIRED_FILES` list omitted `.streamlit/config.toml` as well as the frontend bundle files.
   - In third-party distributions (such as `app.zip` found in the root), `.streamlit/config.toml` was completely omitted, resulting in an immediate `FileNotFoundError` upon executing `project_code_fingerprint()`.
2. **Missing Automated Archive Integrity & Clean Extraction Tests:**
   - There are currently no automated unit/integration tests verifying that `build_source_archive.py` produces a valid, extractable archive containing all provenance dependencies, or that a clean extraction outside the repository root can compute the release fingerprint.
3. **Biodesign Narrative Contradiction in the Need-Statement PDF:**
   - In `Voice_Neuro_Detection_Need_Statement (1).pdf`, Page 2 cites "Primary research: clinicians, health workers and families in primary care, community camps and neurology clinics."
   - Page 3 is titled "Unmet Need Identification: Gaps Found from Primary Research Through Observation" and lists specific observational claims from primary care clinics, rural health camps, and tertiary neurology clinics.
   - However, `docs/biodesign/SIMULATED_CLINICAL_WORKFLOW_SCENARIOS.md` explicitly states:
     > "All clinical scenarios, patient descriptions, numerical examples, and clinician statements in this document are fictional illustrations... No real patient observations, human-subject fieldwork, or clinical stakeholder interviews have been collected."
   - This represents an unsupported claim of primary clinical fieldwork that must be corrected to adhere to academic research integrity.
4. **Lack of Reproducible Need-Statement PDF Source and Generation Pipeline:**
   - The repository lacks an editable source file and a deterministic script to generate the 9-page need-statement PDF.
5. **Need Statement Scope Alignment:**
   - Need statement narratives must clearly distinguish between the broad problem of neurological screening, the exploratory use-case of Parkinson's-associated voice analysis, and the actual technical boundaries of the current prototype (which processes sustained-vowel acoustic features, with microphone prediction explicitly disabled).
