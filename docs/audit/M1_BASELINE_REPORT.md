# VoxNeuro Milestone 1: Baseline Environment Verification Report

**Date:** 2026-11-11  
**Milestone:** M1 – Dataset Acquisition, Reproducible Processing, Model Evaluation, Training and M1 Verified Archive  
**Agent:** Antigravity (Gemini 3.8 Flash High)  
**Target Environment:** CPython 3.12.16, Windows 11 via `uv` 0.13.7  

---

## 1. Executive Summary

Prior to initiating data acquisition, feature extraction, or model training for Milestone 1 (M1), this baseline audit verifies that the development environment, package manager, compiler, test suite, and archive tools are fully functional, deterministic, and compliant with all project safety constraints.

---

## 2. Baseline Status Matrix

| Component | Target Requirement | Measured Baseline | Status |
|---|---|---|---|
| **Python Version** | `>=3.12,<3.13` | CPython 3.12.16 | **PASS** |
| **Dependency Lock** | Exact lockfile resolution | 71 locked packages resolved via `uv sync --all-extras --locked` | **PASS** |
| **Code Linting** | Ruff compliance | `ruff check .` passed (0 errors) | **PASS** |
| **Code Formatting** | Ruff formatting | `ruff format --check .` passed (156 files formatted) | **PASS** |
| **Project Imports** | All 11 modules & 10 required files | `python scripts/verify_project.py` passed | **PASS** |
| **Test Suite** | Full regression suite | **318 passed** in 24.76s (0 failures, 0 errors) | **PASS** |
| **M0 Archive Checksum** | SHA-256 integrity | `d53d6c0bd9eea41bc3f078f477812525cc6d74e77e71954eb56bd476fd3d0d51` (1,073,387 bytes) | **PASS** |
| **M0 Code Fingerprint** | Deterministic pipeline hash | `750b857cab42a93b920f914780c0bc019e70a97dcfec96432de2e89da74c110a` | **PASS** |
| **M0 Frontend Fingerprint** | Deterministic bundle hash | `af9abde5877765614b0ac60d32bf7cbc3a37bf4ec2506562ed21467d1be8e62a` | **PASS** |
| **Disk Space** | Sufficient for audio & features | **254.68 GB free** (552.83 GB total) | **PASS** |
| **Network Access** | Figshare & UCI endpoints reachable | Confirmed via `Invoke-WebRequest` | **PASS** |
| **RAR Archive Tool** | RAR-capable extractor | `C:\WINDOWS\system32\tar.EXE` (bsdtar 3.8.4, libarchive 3.8.4) | **PASS** |

---

## 3. Git Working-Tree State

- **Branch:** `main`
- **Head Commit:** `27e6d8d` (*Resolve audit defects: eliminate resampling filter overshoot, branch margin score tie-breaking...*)
- **Modified Tracked Files:** 8 files (M0 documentation, inventory, archive, and provenance exports)
- **Untracked Artifacts:** M0 delivery files (`VoxNeuro_M0_VERIFIED.zip`, need-statement PDF, baseline and completion reports)
- **Preservation Policy:** Working tree uncommitted; zero destructive commands executed.

---

## 4. Directory State Inspection

The following directories are initially empty of raw research recordings, processed feature datasets, and model binaries (containing only placeholder files or directory structures):

- `data/raw/` (unpopulated)
- `data/interim/` (unpopulated)
- `data/processed/` (unpopulated)
- `artifacts/models/` (unpopulated)
- `artifacts/reports/` (unpopulated)

---

## 5. Phase 0 Conclusion

All prerequisites for Milestone 1 are satisfied. Data acquisition may proceed under strict local-retention and privacy policies.
