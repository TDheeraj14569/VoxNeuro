# VoxNeuro Milestone 2: Statistical Analysis Plan (SAP)
## Pre-Registered Protocol for Demographic Confounding, Matching & Incremental Voice Analysis

**Document Version:** 1.0  
**Registration Date:** 2026-11-11  
**Status:** Pre-registered Prior to M2 Comparative Evaluation Execution  
**Project:** VoxNeuro – Parkinson's Voice Analysis Research Prototype  

---

## 1. Primary Scientific Question

Does sustained-vowel (`/a/`) acoustic feature analysis (Core39, schema `voxneuro.voice.v3`) provide statistically significant, incremental discriminatory power for Parkinson's disease beyond demographic variables (age and biological sex) in the UAMS telephone-recorded dataset, or is observed voice-model performance primarily an artifact of demographic confounding and class-dependent recording attrition?

---

## 2. Target Population & Cohort Context

The development cohort consists of retrospective telephone recordings collected from participants in Arkansas, USA (Figshare DOI `10.6084/m9.figshare.23849127.v1`). The cohort comprises healthy community controls and patients diagnosed with idiopathic Parkinson's disease. Findings are exploratory and specific to this development cohort; no claim of generalization to Indian clinics, prospective community screening, or smartphone/browser microphones is asserted.

---

## 3. Analysis Populations

Two distinct populations are formally prespecified to prevent attrition bias:

### Population 1: Original Source Cohort (N = 81)
- **Composition:** All 81 unique participants with audio recordings and linked demographic records in the UAMS source archive (41 Healthy Controls, 40 Parkinson's Disease).
- **Primary Analytic Purpose:** Baseline demographic distribution characterization, age and sex imbalance assessment, and class-dependent recording quality attrition analysis.

### Population 2: Accepted Feature Cohort (N = 78)
- **Composition:** 78 unique participants whose recordings satisfied technical audio validation under the prespecified reviewed clipping exclusion policy (`configs/reviewed_exclusions.yaml`): 41 Healthy Controls, 37 Parkinson's Disease.
- **Primary Analytic Purpose:** Core39 acoustic feature modeling, demographic-adjusted comparative evaluation, age/sex matching sensitivity analysis, and incremental voice estimation.

---

## 4. Participant-Level Unit of Analysis

The participant is the definitive unit of analysis. Each participant has exactly one primary sustained vowel recording. No duplicate or repeated participant records exist. Cross-validation fold splitting is strictly grouped by `participant_id` (`StratifiedGroupKFold`) to eliminate data leakage.

---

## 5. Demographic Variables & Coding

1. **Age:** Continuous variable in years, recorded to two decimal places in the source workbook. Modeled using fold-local `StandardScaler` (mean = 0, variance = 1 fit strictly on outer training participants).
2. **Biological Sex:** Binary category (`F` = Female, `M` = Male). Modeled using fold-local `OneHotEncoder(drop=None, handle_unknown="ignore")`. Arbitrary numeric hardcoding (e.g. 0/1) before cross-validation is strictly prohibited to guarantee encapsulation within pipelines.

---

## 6. Missing-Data & Quality Failure Strategy

- **Demographics:** The UAMS demographics workbook contains zero missing age or sex values (verified in manifest audit). If any unexpected missing demographic value is encountered, it must be flagged; row deletion or ad-hoc imputation without documented review is prohibited.
- **Waveform Clipping:** Waveforms exceeding the prespecified clipping fraction (0.5% maximum allowable clipped samples) are excluded per `configs/reviewed_exclusions.yaml`. No imputation of acoustic features for clipped recordings is permitted.

---

## 7. Model Comparators & Hierarchy

All models will be evaluated using identical 5-fold participant-grouped outer splits repeated across three fixed random seeds (2026, 2027, 2028), matching Milestone 1 specifications:

| Model Identifier | Predictor Inputs | Pipeline Specification | Scientific Role |
|---|---|---|---|
| **`dummy`** | None | Most frequent class prior | Null baseline |
| **`sex_only_logistic`** | Biological sex (`F`/`M`) | `OneHotEncoder` -> `LogisticRegression(penalty='l2')` | Sex alone |
| **`age_only_logistic`** | Age (years) | `StandardScaler` -> `LogisticRegression(penalty='l2')` | Age alone |
| **`age_plus_sex_logistic`** | Age + Sex | `ColumnTransformer` -> `LogisticRegression(penalty='l2')` | Complete demographic baseline |
| **`voice_only_logistic`** | Core39 (39 acoustic features) | `StandardScaler` -> `LogisticRegression(penalty='l2')` | Linear acoustic reference |
| **`voice_only_extra_trees`** | Core39 (39 acoustic features) | `StandardScaler` -> `ExtraTreesClassifier` | Non-linear acoustic reference |
| **`age_plus_voice_logistic`** | Age + Core39 | `ColumnTransformer` -> `LogisticRegression(penalty='l2')` | Age-adjusted voice |
| **`age_plus_sex_plus_voice`** | Age + Sex + Core39 | `ColumnTransformer` -> `LogisticRegression(penalty='l2')` | Fully adjusted acoustic model |

---

## 8. Age- and Sex-Matching Methodology

To evaluate acoustic separation independent of demographic confounding, one-to-one (1:1) matching without replacement will be performed on Population 2:

1. **Matching Strata:** Exact matching on biological sex (`F` matched to `F`, `M` matched to `M`).
2. **Distance Metric:** Absolute age difference $| \text{age}_{\text{PD}} - \text{age}_{\text{HC}} |$.
3. **Assignment Algorithm:** Optimal bipartite assignment via Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) minimizing total absolute age distance within each sex stratum.
4. **Primary Caliper:** $0.2 \times \text{SD}_{\text{pooled}}(\text{age})$ in Population 2.
5. **Sensitivity Calipers:** $0.1 \times \text{SD}_{\text{pooled}}$, $0.3 \times \text{SD}_{\text{pooled}}$, and uncalipered maximum assignment.
6. **Balance Metrics:** Post-match standardized mean difference ($\text{SMD} = (\bar{x}_{\text{HC}} - \bar{x}_{\text{PD}}) / \text{SD}_{\text{pooled}}$), maximum pairwise age difference, mean/median absolute age difference.
7. **Modeling Feasibility Rule:** If the matched cohort contains sufficient participants ($N \ge 30$) and admits valid 5-fold participant-grouped splits with both classes present in every fold, evaluate matched models; otherwise, record matched model performance as `NOT ESTIMABLE` and document sample-size exhaustion.

---

## 9. Primary & Secondary Comparisons

### Primary Comparison: Fully Adjusted Incremental Voice
$$\Delta_{\text{full}} = \text{Balanced Accuracy}(\text{age\_plus\_sex\_plus\_voice}) - \text{Balanced Accuracy}(\text{age\_plus\_sex\_logistic})$$

### Secondary Comparison 1: Age-Adjusted Incremental Voice
$$\Delta_{\text{age}} = \text{Balanced Accuracy}(\text{age\_plus\_voice\_logistic}) - \text{Balanced Accuracy}(\text{age\_only\_logistic})$$

### Secondary Comparison 2: Unadjusted Acoustic vs Demographic Baseline
$$\Delta_{\text{unadjusted}} = \text{Balanced Accuracy}(\text{voice\_only\_extra\_trees}) - \text{Balanced Accuracy}(\text{age\_plus\_sex\_logistic})$$

---

## 10. Performance Metrics & Decision Rules

- **Primary Metric:** Balanced Accuracy across pooled outer out-of-fold predictions.
- **Secondary Metrics:** Sensitivity (recall for PD), Specificity (true negative rate for HC), Precision (PPV), F1-score, Area Under ROC Curve (ROC-AUC), Average Precision (PR-AUC), Matthews Correlation Coefficient (MCC), and Brier Score.
- **Decision Rule:** An incremental contribution of voice is statistically supported only if the 95% participant-bootstrap confidence interval of $\Delta_{\text{full}}$ strictly excludes zero ($\text{CI}_{\text{lower}} > 0$). If the interval crosses or falls below zero, the null hypothesis—that acoustic features do not provide incremental predictive value beyond demographics—cannot be rejected.

---

## 11. Uncertainty Estimation & Multiplicity

- **Bootstrap Protocol:** 1,000 class-stratified participant-level bootstrap resamples on the primary-seed outer out-of-fold predictions (random seed: 2026).
- **Multiplicity:** Feature-level associations across 39 Core39 acoustic features will be adjusted using Benjamini–Hochberg False Discovery Rate (FDR $q < 0.05$).

---

## 12. Class-Dependent Attrition Analysis

Recording rejection rates will be compared between PD and HC using Fisher's exact test (two-sided) with exact 95% Clopper–Pearson binomial confidence intervals.

---

## 13. External Validation & Generalization Boundary

No secondary external test set exists in this repository. All performance metrics are internal out-of-fold cross-validation estimates. Voice probability outputs are uncalibrated; no clinical threshold or diagnostic claim is authorized.
