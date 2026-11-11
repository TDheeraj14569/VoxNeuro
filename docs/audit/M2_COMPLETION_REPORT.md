# VoxNeuro Milestone 2 Completion Report
## Scientific Bias Audit, Demographic Confounding, Age/Sex Matching, Statistical Robustness, and M2 Verified Archive

**Document ID:** `VN-REP-M2-COMPLETION-001`  
**Milestone:** M2 (Scientific Bias Audit & Statistical Robustness)  
**Date:** 2026-11-11  
**Author:** Antigravity (Senior Software Architect & Verification Engineer)  
**Status:** Complete & Independently Verified  
**Baseline Starting Archive:** `VoxNeuro_M1_VERIFIED.zip`  
**Final Output Archive:** `VoxNeuro_M2_VERIFIED.zip`  
**External Sidecar Checksum:** `VoxNeuro_M2_VERIFIED.zip.sha256`  
**Archive Size:** ~2.18 MB (231 files: 206 source, 24 review attachments, 1 bundle README)  
**Pipeline Code Fingerprint:** `c595e14ef181902c35cbcbffa285fcf1aa1e10b5b57a338c781776ed73f47db3`  
**Frontend Fingerprint:** `af9abde5877765614b0ac60d32bf7cbc3a37bf4ec2506562ed21467d1be8e62a`  

---

## 1. Executive Summary

Milestone 2 of VoxNeuro has been successfully completed and repaired in full accordance with all critical execution rules, research integrity standards, and pre-registered statistical decision protocols.

M2 conducted an exhaustive empirical audit of the UAMS telephone sustained-vowel (`/a/`) dataset to establish whether acoustic feature modeling (schema `voxneuro.voice.v3`, Core39) isolates a genuine Parkinsonian neurodegenerative signature or merely reflects demographic senescence and recording-quality attrition.

### Principal Findings:
1. **Severe Demographic Confounding:** Healthy Controls are on average **19.31 years younger** than Parkinson's participants ($47.73 \pm 14.33$ vs $67.04 \pm 8.98$ years; Standardized Mean Difference [SMD] $= -1.61$; Rank-Biserial Correlation $r_{\text{rb}} = -0.728$; Mann-Whitney $U = 223.0$, $p = 1.75 \times 10^{-8}$).
2. **No Supported Incremental Voice Benefit Beyond Demographics:** The retrospective cohort did not establish supported incremental predictive benefit from adding the current voice features beyond demographic comparators. A simple age-only logistic classifier achieves **$83.89\%$** balanced accuracy ($0.8490$ ROC-AUC), substantially outperforming the primary linear voice-only model (**$70.54\%$** balanced accuracy, $0.7559$ ROC-AUC) and L2-regularized logistic voice model (**$73.88\%$** balanced accuracy, $0.7697$ ROC-AUC).
3. **Absence of Supported Positive Incremental Voice Diagnostic Value:** In repeated $5 \times 3$ nested cross-validation on identical participant holdouts:
   - Comparing Age + Voice to Age Only yields a primary-seed $\Delta\text{BA} = -0.0758$ ($-7.58\%$) with a 95% bootstrap CI of [$-0.1842, +0.0284$] (secondary repeated-CV $\Delta\text{BA} = -0.0681$; supplementary McNemar exact $p = 0.2632$).
   - Comparing Age + Sex + Voice to Age + Sex yields a primary-seed $\Delta\text{BA} = -0.0745$ ($-7.45\%$) with a 95% bootstrap CI of [$-0.1843, +0.0310$] (secondary repeated-CV $\Delta\text{BA} = -0.0762$; supplementary McNemar exact $p = 0.2632$).
   - Under the pre-registered SAP decision rule (requiring the 95% bootstrap CI lower bound to strictly exceed zero), no statistically supported positive incremental voice contribution was established.
4. **Balanced Scientific Inference:** No statistically supported positive incremental voice contribution was established in the current UAMS cohort. However, the available confidence intervals do not establish that the true incremental contribution is zero or that a clinically meaningful contribution is impossible in a larger, demographically balanced prospective cohort.
5. **Sample Size Exhaustion on Caliper Matching:** Enforcing a standard epidemiological caliper ($0.2$ pooled SD $= 2.44$ years) with exact sex matching retains only **5 pairs (10 participants)** &mdash; an $87.2\%$ cohort attrition rate. In accordance with pre-registered SAP Rule 5, cross-validation modeling on the matched subset is formally documented as **NOT ESTIMABLE**.
6. **Small-Cell Suppression in Age Strata:** In accordance with `docs/methodology/M2_METHODOLOGY_ADDENDUM.md`, age strata (<50, 50–59, 60–69, 70+) suffer from severe class depletion ($< 10$ participants per class in every stratum) and are formally designated as **NOT ESTIMABLE** per pre-registered SAP Rule 6.
7. **Exploratory Feature Multiplicity Control:** Multivariable logistic associations adjusted for age and sex across all 39 Core39 features evaluated partial disease signal via Likelihood Ratio Tests and Benjamini–Hochberg False Discovery Rate control ($q < 0.05$).
8. **Class-Dependent Quality Attrition:** Quality exclusions occurred exclusively in the Parkinson's cohort ($3/40$ PD excluded [$7.5\%$] vs $0/41$ HC [$0.0\%$]; Fisher exact $p = 0.1158$), all driven by acoustic clipping ($>0.5\%$ samples at peak rail).
9. **Draft Prospective Phase 8 Validation Protocol:** Authored `docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md` specifying an illustrative prospective $N=240$ multi-center study draft with 1:1 age- and sex-matching ($|\text{SMD}| \le 0.10, |\Delta_{\text{prop}}| \le 0.05$), sound-booth acoustics ($<35\text{ dBA}$), calibrated studio condenser transducers, sensitivity power scenarios across plausible paired-difference variances ($\sigma_\Delta \in [0.15, 0.30]$), biostatistician sign-off mandate, biometric voice identifiability notices, and Indian privacy compliance (DPDP Act 2023, ICMR 2017).

---

## 2. Phase-by-Phase Verification Record

| Phase | Title | Artifact / Implementation Deliverable | Verification Status |
|:---|:---|:---|:---:|
| **Phase 0** | Baseline Verification & Integrity | `docs/audit/M2_BASELINE_REPORT.md` (Checked 71 locked packages, passing tests, clean tree) | **PASS** |
| **Phase 1** | Pre-registered Statistical Analysis Plan | `docs/methodology/M2_STATISTICAL_ANALYSIS_PLAN.md` and `docs/methodology/M2_METHODOLOGY_ADDENDUM.md` | **PASS** |
| **Phase 2** | Demographic Confounding Audit | `src/voxneuro/dataset/bias_audit.py`, `data/processed/m2_demographic_summary.json` (Exact Student's t CIs, Mann-Whitney U, SMD, rank-biserial -0.728, scientific p-values) | **PASS** |
| **Phase 3** | Attrition & Missingness Audit | `audit_quality_attrition()`, `data/processed/m2_attrition_summary.json` (3 PD clipping exclusions, 0 HC; Fisher exact p=0.116) | **PASS** |
| **Phase 4** | Matching Sensitivity Analysis | `src/voxneuro/dataset/matching.py`, `data/processed/m2_matching_sensitivity.csv` (Hungarian bipartite matching across 0.1, 0.2, 0.3 SD, uncalipered) | **PASS** |
| **Phase 5** | Matched Modeling Feasibility | SAP Rule 5 determination: 5 pairs at 0.2 SD caliper exhausts fold capacity; formally reported as **NOT ESTIMABLE** | **PASS** |
| **Phase 6** | Comparator Hierarchy & Incremental Voice | `src/voxneuro/modeling/demographic_sensitivity.py`, `data/processed/m2_comparator_metrics.csv`, `data/processed/m2_paired_incremental_voice.csv` | **PASS** |
| **Phase 7** | Subgroup Analyses & Small-Cell Rules | `data/processed/m2_sex_subgroup_summary.csv` and `data/processed/m2_age_subgroup_summary.csv` | **PASS** |
| **Phase 8** | Prospective External Cohort Protocol | `docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md` (N=240, 1:1 frequency matched, studio condenser, booth acoustics) | **PASS** |
| **Phase 9** | Automated Testing Suite | `tests/unit/test_bias_audit.py`, `tests/unit/test_matching.py`, `tests/unit/test_demographic_sensitivity.py`, `tests/unit/test_m2_report_consistency.py`, `tests/integration/test_m2_bias_pipeline.py` (357 tests passed) | **PASS** |
| **Phase 10** | Scientific Bias Audit Report | `docs/reports/M2_BIAS_AUDIT_REPORT.md` (14 comprehensive sections), HTML dashboards in `artifacts/reports/scientific_audit/` | **PASS** |
| **Phase 11** | Review Bundle & Packaging | `scripts/build_ai_review_bundle.py --milestone m2`, `VoxNeuro_M2_VERIFIED.zip`, `VoxNeuro_M2_VERIFIED.zip.sha256` | **PASS** |
| **Phase 12** | Clean-Room Extraction Verification | Extracted to clean temporary directory; verified CRC, tests pass/skip cleanly, `verify_project.py` passes, zero private IDs/audio | **PASS** |
| **Phase 13** | Receipt Refresh Sequence | Executed exact 13-step pipeline sequence; all receipts cryptographically aligned to frozen code fingerprint `c595e14ef181902c35cbcbffa285fcf1aa1e10b5b57a338c781776ed73f47db3` | **PASS** |

---

## 3. Prespecified Comparator Model Evaluation Hierarchy

Evaluated across identical $5 \times 3$ repeated nested cross-validation folds (seeds 2026, 2027, 2028; $N = 78$ accepted UAMS participants):

| Model Name | Description | Status | Balanced Accuracy [95% CI] | ROC-AUC | Sensitivity | Specificity | F1 Score | Accuracy |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `age_only_logistic` | Demographic Age only | ESTIMATED | **$83.89\%$** [$74.68\%, 91.07\%$] | **$0.8490$** | $86.49\%$ | $81.30\%$ | $0.8348$ | $83.76\%$ |
| `age_plus_sex_logistic` | Age + Biological Sex | ESTIMATED | **$83.81\%$** [$74.56\%, 91.20\%$] | **$0.8493$** | $84.68\%$ | $82.93\%$ | $0.8318$ | $83.76\%$ |
| `age_plus_voice_logistic` | Age + Core39 Voice | ESTIMATED | **$77.08\%$** [$65.89\%, 84.71\%$] | **$0.8141$** | $80.18\%$ | $73.98\%$ | $0.7674$ | $76.92\%$ |
| `age_plus_sex_plus_voice` | Age + Sex + Voice | ESTIMATED | **$76.18\%$** [$65.89\%, 84.84\%$] | **$0.8132$** | $78.38\%$ | $73.98\%$ | $0.7567$ | $76.07\%$ |
| `voice_only_logistic` | Core39 Voice (L2) | ESTIMATED | **$73.88\%$** [$62.79\%, 82.27\%$] | **$0.7697$** | $72.97\%$ | $74.80\%$ | $0.7265$ | $73.93\%$ |
| `voice_only_svm` | Core39 Voice (Linear SVM)| ESTIMATED | **$70.54\%$** [$59.13\%, 79.43\%$] | **$0.7559$** | $71.17\%$ | $69.92\%$ | $0.6963$ | $70.51\%$ |
| `sex_only_logistic` | Biological Sex only | ESTIMATED | **$56.16\%$** [$44.79\%, 67.67\%$] | **$0.4971$** | $51.35\%$ | $60.98\%$ | $0.5278$ | $56.41\%$ |
| `majority_classifier` | Majority Class Baseline | ESTIMATED | **$50.00\%$** [$50.00\%, 50.00\%$] | **$0.5000$** | $0.00\%$ | $100.0\%$ | $0.0000$ | $52.56\%$ |
| `matched_voice_svm` | Matched Voice SVM | **NOT ESTIMABLE** | N/A | N/A | N/A | N/A | N/A | N/A |

### Paired Incremental Contrast Tests:
- **Age + Voice vs Age Only:** Primary seed 2026 $\Delta \text{BA} = -0.0758$ ($-7.58\%$), $95\%$ CI [$-0.1842, +0.0284$], secondary repeated-CV $\Delta \text{BA} = -0.0681$, supplementary McNemar exact $p = 0.2632$.
- **Age + Sex + Voice vs Age + Sex:** Primary seed 2026 $\Delta \text{BA} = -0.0745$ ($-7.45\%$), $95\%$ CI [$-0.1843, +0.0310$], secondary repeated-CV $\Delta \text{BA} = -0.0762$, supplementary McNemar exact $p = 0.2632$.
- **Inference:** Sustained-vowel acoustic metrics do not establish a statistically supported positive incremental contribution beyond basic demographics in this cohort.

---

## 4. Final Verification Metrics & Test Suite

- **Total Python Tests:** **357 passed** (0 failed, 0 skipped) in pytest suite.
  - Non-UI tests: 349.
  - Streamlit AppTests: 8.
- **Report-Data Consistency Tests:** **10 passed** (0 failed) in `tests/unit/test_m2_report_consistency.py` (verifying age strata, FDR Core39 names, q-values, prospective protocol assumptions, and negative failure assertions).
- **Test Coverage:** **$87.5\%$** across statements in `src/voxneuro`.
- **Ruff Lint:** Clean (zero errors, zero warnings).
- **Ruff Format:** All files formatted cleanly.
- **Git Status:** All working tree files preserved; no automatic commits or destructive commands executed.

---

## 5. Milestone Completion Sign-Off

Milestone 2 objectives are completely fulfilled. In accordance with critical execution rules, feature development remained strictly out of scope, live microphone prediction remains disabled (`allow_user_microphone_inference: false`), and no M3 tasks were undertaken.

*VoxNeuro Research Prototype &bull; Milestone 2 Verified Completion Report &bull; 2026-11-11*
