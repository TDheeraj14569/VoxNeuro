# VoxNeuro Milestone 2: Baseline Environment Verification Report

**Date:** 2026-11-11  
**Milestone:** M2 – Scientific Bias Audit, Demographic Confounding, Age/Sex Matching, Statistical Robustness and M2 Verified Archive  
**Agent:** Antigravity (Gemini 3.8 Flash High)  
**Target Environment:** CPython 3.12.16, Windows 11 via `uv` 0.13.7  

---

## 1. Executive Summary

Milestone 2 (M2) investigates the extent to which VoxNeuro's apparent voice-analysis performance on the UAMS cohort may be explained by demographic confounding (especially severe age disparity and potential sex imbalance) and class-dependent recording-quality exclusions (clipping).

This report verifies that the starting state for M2 is fully established, with valid local datasets, cryptographic receipts, trained research model artifacts, and test baselines matching the deliverables of Milestone 1.

---

## 2. Baseline Verification Matrix

| Component | Target Requirement | Measured Value | Status |
|---|---|---|---|
| **M1 Verified Archive** | SHA-256 integrity | `ab452d4d5b02cfd4a3aefe3c1f2b74a8d99e1fe43b10b9b640a8143db71d7238` (1,112,149 bytes) | **PASS** |
| **Pipeline Code Fingerprint** | Deterministic source hash | `b30f309161eb1804e528d7a4c02f3424e41af138fa39f1684b78c68afa7f68d1` | **PASS** |
| **Frontend Bundle Fingerprint** | Deterministic visualizer hash | `af9abde5877765614b0ac60d32bf7cbc3a37bf4ec2506562ed21467d1be8e62a` | **PASS** |
| **Python Runtime** | `>=3.12,<3.13` | CPython 3.12.16 | **PASS** |
| **Package Environment** | Locked resolution | 71 packages verified via `uv sync --all-extras --locked` | **PASS** |
| **UAMS PD Archive** | Built-in MD5 match | `2e525e419abdad509e5cbf201e30ef36` (2,247,417 bytes) | **PASS** |
| **UAMS HC Archive** | Built-in MD5 match | `55fd33d365380372dcfbae4f7f520246` (2,007,786 bytes) | **PASS** |
| **Demographics Workbook** | SHA-256 match | `af622ccbd8b8051f19326688ad4138c4c72983f4b21aaae3ca58f6e1566a7305` (122,854 bytes) | **PASS** |
| **UCI Feature Table** | SHA-256 match | `9495d1100beaa24005ea951d4b6588186091de4c21cc45009b027f38f699b8ab` (5,308,926 bytes) | **PASS** |
| **Feature Manifest** | SHA-256 match | `f4c5c0325ad6c2ce629dead6f91fa1ab5f9888b45bd4c19d96786f2853206e92` (81 participants) | **PASS** |
| **Core39 Voice Features** | SHA-256 match | `ec406fe8f1630a1ccadae3f547af252cc2fa460cddeb06a516b4f21bd7b4bc4c` (78 participants) | **PASS** |
| **Model Artifact** | SHA-256 sidecar match | `a3ae33ea638e9953ea61dac7174fe6da7da559bb572c532d40cea4084cbf5ee0` (7,374 bytes) | **PASS** |
| **Project Imports & Files** | `verify_project.py` | 11 modules and 10 required files verified | **PASS** |
| **Model Bundle Validation** | `verify_model.py` | Bundle reload, deterministic prediction, research-only status passed | **PASS** |
| **Test Suite** | Full pytest regression | **318 passed** in 27.40s (0 failures, 0 errors) | **PASS** |

---

## 3. Data Availability & Scenario Confirmation

**Operating Scenario:** Scenario A (Local research datasets and artifacts are present in the workspace).

All research data files are retained strictly in local uncommitted directories (`data/raw/`, `data/interim/`, `data/processed/`, and `artifacts/models/`). Privacy policies remain in effect: no participant recordings or row-level demographic identities will enter version control or review archives.

---

## 4. Phase 0 Conclusion

All prerequisites for Milestone 2 execution are satisfied. The statistical analysis plan may now be formally pre-registered prior to running comparative modeling.
