# VoxNeuro Milestone 2: Scientific Bias Audit, Demographic Confounding, Age/Sex Matching, and Statistical Robustness Report

**Document ID:** `VN-REP-M2-001`  
**Milestone:** M2 (Scientific Bias & Confounding Audit)  
**Version:** `1.1.0`  
**Release Date:** November 2026  
**Status:** Pre-registered Empirical Scientific Audit Completed  
**Author:** Antigravity (Senior Software Architect & Verification Engineer)  
**Study Design:** Pre-registered Statistical Analysis Plan (`docs/methodology/M2_STATISTICAL_ANALYSIS_PLAN.md`) and Methodology Addendum (`docs/methodology/M2_METHODOLOGY_ADDENDUM.md`)  
**Investigated Cohort:** UAMS Sustained-Vowel (/a/) Dataset (Figshare DOI `10.6084/m9.figshare.23849127.v1`)  

---

## 1. Executive Summary & Pre-registered Objectives

Milestone 2 evaluates a foundational scientific question regarding the VoxNeuro acoustic analysis prototype:  
> **Does sustained-vowel (/a/) acoustic feature analysis (schema `voxneuro.voice.v3`, Core39) provide incremental diagnostic value beyond demographic variables (age and biological sex), or is apparent classifier accuracy primarily attributable to demographic confounding and quality-related cohort attrition?**

### Core Findings Summary
1. **Severe Age Confounding:** Healthy Controls (HC) are on average **19.31 years younger** than Parkinson's Disease (PD) participants ($47.73 \pm 14.33$ vs $67.04 \pm 8.98$ years; Standardized Mean Difference [SMD] $= -1.61$; Rank-Biserial Correlation $r_{\text{rb}} = -0.728$; Mann-Whitney $U = 223.0$, $p = 1.75 \times 10^{-8}$).
2. **No Supported Incremental Voice Benefit Beyond Demographics:** The retrospective cohort did not establish supported incremental predictive benefit from adding the current voice features beyond demographic comparators. A simple age-only logistic model achieves **$83.89\%$** balanced accuracy ($84.90\%$ ROC-AUC), substantially outperforming the primary linear voice-only model (**$70.54\%$** balanced accuracy, $75.59\%$ ROC-AUC) and L2-regularized logistic voice model (**$73.88\%$** balanced accuracy, $76.97\%$ ROC-AUC).
3. **Absence of Supported Positive Incremental Voice Contribution:** 
   - Comparing Age + Voice to Age Only on identical out-of-fold participant holdouts (primary seed 2026) yields $\Delta\text{BA} = -0.0758$ ($-7.58\%$) with a 95% bootstrap CI of [$-0.1842, +0.0284$] (secondary repeated-CV $\Delta\text{BA} = -0.0681$; supplementary McNemar exact $p = 0.2632$).
   - Comparing Age + Sex + Voice to Age + Sex yields $\Delta\text{BA} = -0.0745$ ($-7.45\%$) with a 95% bootstrap CI of [$-0.1843, +0.0310$] (secondary repeated-CV $\Delta\text{BA} = -0.0762$; supplementary McNemar exact $p = 0.2632$).
   - Under the pre-registered SAP decision rule (requiring the 95% bootstrap CI lower bound to strictly exceed zero), no statistically supported positive incremental voice contribution was established.
4. **Balanced Scientific Inference:** The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain. In this cohort, available confidence intervals do not establish that the true incremental contribution is zero or that a clinically meaningful contribution is impossible in a larger, demographically balanced prospective cohort.
5. **Class-Dependent Quality Attrition:** Quality exclusions occurred exclusively in the Parkinson's cohort ($3/40$ PD excluded [$7.5\%$] vs $0/41$ HC [$0.0\%$]; Fisher exact $p = 0.1158$). All exclusions were caused by acoustic clipping ($> 0.5\%$ samples at full-scale), underscoring recording quality and gain calibration considerations for remote audio collection.
6. **Sample Size Exhaustion on Caliper Matching:** Enforcing a standard epidemiological caliper ($0.2$ pooled SD $= 2.44$ years) with exact biological sex matching leaves only **5 pairs (10 participants)** &mdash; an $87.2\%$ participant attrition rate. Per pre-registered SAP Rule 5, cross-validation modeling on the matched subset is formally designated as **NOT ESTIMABLE**.
7. **Small-Cell Suppression in Age Strata:** Post-hoc age strata (<50, 50–59, 60–69, 70+) suffer from severe class depletion ($< 10$ participants per class in every stratum) and are formally designated as **NOT ESTIMABLE** per pre-registered SAP Rule 6.
8. **Exploratory Feature Multiplicity Control:** Multivariable logistic associations adjusted for age and sex across all 39 Core39 features identified exploratory associations under Benjamini–Hochberg False Discovery Rate ($q < 0.05$), serving as candidate hypothesis targets for prospective validation rather than validated biomarkers.

---

## 2. Population Definitions

Two distinct cohorts are formally tracked to ensure transparency regarding attrition:

| Population Parameter | Population 1: Source Manifest Cohort | Population 2: Accepted Core39 Cohort |
|:---|:---|:---|
| **Definition** | All raw research participants with valid demographics in source workbook | High-quality recordings successfully passing Core39 extraction without excessive clipping |
| **Total Participants** | 81 | 78 |
| **Healthy Controls (HC)** | 41 ($50.6\%$) | 41 ($52.6\%$) |
| **Parkinson's Disease (PD)**| 40 ($49.4\%$) | 37 ($47.4\%$) |
| **Acoustic Exclusions** | None (unfiltered source) | 3 ($7.5\%$ of PD cohort; 0 HC) |
| **Exclusion Mechanism** | N/A | Excessive acoustic clipping ($>0.5\%$ samples at peak rail) |

---

## 3. Demographic Confounding Audit

### 3.1 Chronological Age Distribution

| Metric | Healthy Controls (HC) | Parkinson's Disease (PD) | Effect Size (HC minus PD) | Statistical Test |
|:---|:---|:---|:---|:---|
| **Pop 1 Mean &plusmn; SD** | $47.73 \pm 14.33$ yrs<br>[95% CI: $43.21, 52.25$] | $67.04 \pm 8.98$ yrs<br>[95% CI: $64.16, 69.91$] | Mean Diff: $-19.31$ yrs [$95\%$ CI: $-24.58, -13.91$] | MW $U = 223.0$, $p = 1.75 \times 10^{-8}$ |
| **Pop 1 Median (IQR)** | $45.00$ ($22.00$) yrs | $67.90$ ($12.00$) yrs | Median Diff: $-22.90$ yrs | Rank-biserial $r_{\text{rb}} = -0.728$ |
| **Pop 1 SMD (Cohen's $d$)**| &mdash; | &mdash; | SMD: $-1.61$ [$95\%$ CI: $-2.11, -1.13$] | Massive demographic shift |
| **Pop 2 Mean &plusmn; SD** | $47.73 \pm 14.33$ yrs<br>[95% CI: $43.21, 52.25$] | $66.91 \pm 9.47$ yrs<br>[95% CI: $63.75, 70.07$] | Mean Diff: $-19.17$ yrs [$95\%$ CI: $-24.49, -13.73$] | MW $U = 208.5$, $p = 2.45 \times 10^{-8}$ |
| **Pop 2 SMD** | &mdash; | &mdash; | SMD: $-1.56$ [$95\%$ CI: $-2.07, -1.08$] | Rank-biserial $r_{\text{rb}} = -0.728$ |

### 3.2 Biological Sex Representation

Cramér's V is computed using standard Pearson chi-square without Yates' continuity correction:

| Cohort | Female Count (%) | Male Count (%) | Odds Ratio (95% CI) | Fisher's Exact p | Cramér's V (Pearson $\chi^2$) |
|:---|:---|:---|:---|:---|:---|
| **Pop 1 HC** | 25 ($61.0\%$) | 16 ($39.0\%$) | $1.73$ [$0.70, 4.28$] | $p = 0.268$ | $0.123$ ($\chi^2 = 1.228$) |
| **Pop 1 PD** | 19 ($47.5\%$) | 21 ($52.5\%$) | Reference | &mdash; | &mdash; |
| **Pop 2 HC** | 25 ($61.0\%$) | 16 ($39.0\%$) | $1.52$ [$0.61, 3.81$] | $p = 0.364$ | $0.122$ ($\chi^2 = 1.154$) |
| **Pop 2 PD** | 18 ($48.6\%$) | 19 ($51.4\%$) | Reference | &mdash; | &mdash; |

---

## 4. Joint Demographic Support & Strata Overlap

Evaluating age distributions within biological sex strata reveals severe demographic disjointness:

| Stratum | Cohort | N (Pop 1 / Pop 2) | Age Mean &plusmn; SD | Age Range (Min &ndash; Max) | Common Support Window | Mann-Whitney p |
|:---|:---|:---|:---|:---|:---|:---|
| **Female (F)** | HC | 25 / 25 | $45.20 \pm 12.90$ yrs | $22.0 - 74.0$ yrs | **$43.1 - 74.0$ yrs** | $p = 1.05 \times 10^{-4}$ |
|  | PD | 19 / 18 | $66.95 \pm 10.22$ yrs | $43.1 - 81.3$ yrs | (Only 3 HC $\ge 65$; 2 PD $< 55$) |  |
| **Male (M)** | HC | 16 / 16 | $51.69 \pm 15.93$ yrs | $18.0 - 79.0$ yrs | **$51.0 - 79.0$ yrs** | $p = 1.83 \times 10^{-4}$ |
|  | PD | 21 / 19 | $66.86 \pm 8.70$ yrs | $51.0 - 85.3$ yrs | (Only 2 HC $\ge 65$; 1 PD $< 55$) |  |

---

## 5. Recording Quality & Attrition Asymmetry

All raw audio files were evaluated for acoustic validity. Attrition by diagnostic class:

| Diagnostic Cohort | Eligible Source Audio | Accepted Core39 Audio | Excluded Audio | Acceptance Rate (95% CI) | Exclusion Reason |
|:---|:---|:---|:---|:---|:---|
| **Healthy Control (HC)** | 41 | 41 | 0 ($0.0\%$) | $100.0\%$ [$91.4\%, 100.0\%$] | None (all compliant) |
| **Parkinson's Disease (PD)** | 40 | 37 | 3 ($7.5\%$) | $92.5\%$ [$79.6\%, 98.4\%$] | Acoustic clipping ($>0.5\%$) |
| **Difference / Test** | &mdash; | &mdash; | 3 vs 0 | Diff: $7.5\%$ | Fisher exact $p = 0.1158$ |

All three excluded recordings exhibited severe input clipping across more than $0.5\%$ of audio samples, preventing accurate pitch tracking and spectral feature extraction. While the difference in attrition rate ($7.5\%$ vs $0.0\%$) does not attain statistical significance at $\alpha=0.05$ ($p = 0.1158$), the class asymmetry highlights that remote, unsupervised recording quality and gain calibration must be rigorously monitored in prospective studies.

---

## 6. Demographic Matching Sensitivity Analysis

To investigate whether a valid age- and sex-balanced subcohort could be constructed, optimal 1:1 bipartite matching without replacement was performed using the Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) with exact sex matching across multiple caliper thresholds:

| Caliper Specification | Caliper Threshold (Years) | Matched Pairs Retained | Retained Participants | Discarded Participants | Post-Match Mean Age Gap | Post-Match SMD |
|:---|:---|:---|:---|:---|:---|:---|
| **0.1 SD** | $1.22$ yrs | 3 | 6 ($7.7\%$) | 72 ($92.3\%$) | $0.86$ yrs | $-0.110$ |
| **0.2 SD (Primary)** | $2.44$ yrs | **5** | **10** ($12.8\%$) | **68** ($87.2\%$) | **$1.08$ yrs** | **$-0.066$** |
| **0.3 SD** | $3.67$ yrs | 7 | 14 ($17.9\%$) | 64 ($82.1\%$) | $1.68$ yrs | $-0.099$ |
| **Uncalipered** | None ($\infty$) | 34 | 68 ($87.2\%$) | 10 ($12.8\%$) | $14.90$ yrs | $-1.327$ |

### Matching Sensitivity Interpretation
1. Tight calipers ($0.1 - 0.3$ SD) eliminate demographic confounding (SMD $< 0.10$), but discard **$82\% - 92\%$ of the cohort**, leaving only 3 to 7 matched pairs.
2. Uncalipered matching retains 34 pairs but fails completely to achieve balance (post-match mean age gap $= 14.90$ years, $\text{SMD} = -1.327$).
3. Common demographic support in UAMS is insufficient to support matched statistical modeling.

---

## 7. Matched Modeling Feasibility & Non-Estimability

Pre-registered Statistical Analysis Plan Decision Rule 5 states:
> *"If caliper matching yields fewer than 10 pairs (sample size exhaustion), cross-validation fold construction on the matched cohort is formally documented as NOT ESTIMABLE rather than forced through uncalipered matching."*

At the primary $0.2$ SD caliper, only 5 pairs (5 HC, 5 PD; 10 participants) exist. Stratified 5-fold cross-validation requires at least 5 participants per class, placing exactly 1 participant per class in each outer test fold and leaving only 4 participants per class for training. A 3-fold inner cross-validation cannot be partitioned across 4 training samples without producing singleton or degenerate folds.

Therefore, matched acoustic model performance is formally documented as **NOT ESTIMABLE**.

---

## 8. Prespecified Comparator Model Performance Hierarchy

All 8 prespecified models were evaluated across identical participant holdouts using repeated nested cross-validation ($5 \times 3$ outer/inner folds; seeds 2026, 2027, 2028; $N = 78$ accepted participants):

| Model Rank | Model Identifier | Model Description | Status | Balanced Accuracy [95% CI] | ROC-AUC | Sensitivity | Specificity | F1 Score | Accuracy |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| 1 | `age_only_logistic` | Demographic Age only | ESTIMATED | **$83.89\%$** [$74.68\%, 91.07\%$] | **$0.8490$** | $86.49\%$ | $81.30\%$ | $0.8348$ | $83.76\%$ |
| 2 | `age_plus_sex_logistic` | Age + Biological Sex | ESTIMATED | **$83.81\%$** [$74.56\%, 91.20\%$] | **$0.8493$** | $84.68\%$ | $82.93\%$ | $0.8318$ | $83.76\%$ |
| 3 | `age_plus_voice_logistic` | Age + Core39 Voice | ESTIMATED | **$77.08\%$** [$65.89\%, 84.71\%$] | **$0.8141$** | $80.18\%$ | $73.98\%$ | $0.7674$ | $76.92\%$ |
| 4 | `age_plus_sex_plus_voice` | Age + Sex + Voice | ESTIMATED | **$76.18\%$** [$65.89\%, 84.84\%$] | **$0.8132$** | $78.38\%$ | $73.98\%$ | $0.7567$ | $76.07\%$ |
| 5 | `voice_only_logistic` | Core39 Voice (L2) | ESTIMATED | **$73.88\%$** [$62.79\%, 82.27\%$] | **$0.7697$** | $72.97\%$ | $74.80\%$ | $0.7265$ | $73.93\%$ |
| 6 | `voice_only_svm` | Core39 Voice (Linear SVM)| ESTIMATED | **$70.54\%$** [$59.13\%, 79.43\%$] | **$0.7559$** | $71.17\%$ | $69.92\%$ | $0.6963$ | $70.51\%$ |
| 7 | `sex_only_logistic` | Biological Sex only | ESTIMATED | **$56.16\%$** [$44.79\%, 67.67\%$] | **$0.4971$** | $51.35\%$ | $60.98\%$ | $0.5278$ | $56.41\%$ |
| 8 | `majority_classifier` | Majority Class Baseline | ESTIMATED | **$50.00\%$** [$50.00\%, 50.00\%$] | **$0.5000$** | $0.00\%$ | $100.0\%$ | $0.0000$ | $52.56\%$ |
| &mdash; | `matched_voice_svm` | Matched Voice SVM | **NOT ESTIMABLE** | N/A | N/A | N/A | N/A | N/A | N/A |

---

## 9. Paired Incremental Voice Value Analysis

Paired differences were calculated across identical out-of-fold participant test sets on the primary seed ($2026$) matching the paired bootstrap CI estimator, with $1,000$ participant bootstrap iterations, secondary repeated-CV cross-seed comparisons, and supplementary McNemar exact binomial tests:

| Comparison | Contrast Tested | Baseline Model | Primary Seed $\Delta\text{BA}$ [95% CI] | Repeated-CV $\Delta\text{BA}$ | Discordance ($b, c$) | Supplementary McNemar p | SAP Decision Rule |
|:---|:---|:---|:---|:---|:---|:---|:---|
| **Comparison 1** | Age + Voice | Age Only | **$-0.0758$** [$-0.1842, +0.0284$] | $-0.0681$ | $b=7, c=13$ | $p = 0.2632$ | **Not Supported** ($\text{CI}_{\text{low}} \le 0$) |
| **Comparison 2** | Age + Sex + Voice | Age + Sex | **$-0.0745$** [$-0.1843, +0.0310$] | $-0.0762$ | $b=7, c=13$ | $p = 0.2632$ | **Not Supported** ($\text{CI}_{\text{low}} \le 0$) |

### Balanced Scientific Inference
- **Decision Rule Determination:** Under pre-registered SAP Decision Rule 4, positive incremental voice diagnostic value is supported if and only if the 95% paired bootstrap confidence interval strictly excludes zero on the positive side ($\text{CI}_{\text{low}} > 0$). Because the confidence intervals extend deeply into negative territory (spanning from approx. $-18.4\%$ to $+3.1\%$), the hypothesis of positive incremental diagnostic value is not supported in this cohort.
- **Scientific Interpretation:** The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain. Available confidence intervals do not establish that the true incremental contribution is zero or that a clinically meaningful contribution is impossible in a sufficiently powered, demographically balanced cohort.
- **Estimation Variance:** Adding 39 acoustic features to demographic baselines increases parameter estimation variance in modest sample sizes ($N=78$), which penalizes out-of-fold generalization.

### Conceptual Distinctions in Scientific Interpretation
To prevent overstatement or misinterpretation, four distinct scientific concepts are formally distinguished:
1. **Statistical Association:** Whether an acoustic feature correlates with disease status after adjusting for age and biological sex in a parametric regression model (e.g., multivariable likelihood-ratio test with Benjamini–Hochberg FDR control). Significant association indicates a covariate-adjusted statistical relationship within this historical sample, but does not prove predictive classification utility or clinical diagnostic value.
2. **Predictive Performance:** Standalone capacity of acoustic features or models to discriminate between diagnostic classes in cross-validation (e.g., balanced accuracy of $70.54\%$ for linear SVM, $73.88\%$ for L2 logistic). High standalone predictive performance can arise entirely from demographic confounding when classes differ systematically in age.
3. **Incremental Predictive Contribution:** The paired improvement ($\Delta\text{BA}$) achieved by adding acoustic features to a demographic baseline model evaluated on identical out-of-fold participant test sets. In this cohort, adding Core39 voice features to age and sex baselines resulted in negative point estimates ($\Delta\text{BA} \approx -7.5\%$) whose 95% bootstrap confidence intervals span zero (spanning $-18.4\%$ to $+3.1\%$), establishing no supported incremental predictive contribution.
4. **External Clinical Validity:** The generalizability of acoustic classification to an independent, prospectively recruited, and demographically balanced patient population under standardized acoustic recording conditions. This cannot be established from historical, retrospectively confounded cohorts and requires prospective multi-center trial verification.

---

## 10. Exploratory Age Strata Subgroup Analysis

In accordance with `docs/methodology/M2_METHODOLOGY_ADDENDUM.md`, exploratory age-stratified subgroup analyses were audited with small-cell suppression rules ($N_{\text{min}} = 10$ per class):

| Age Band | Range (Years) | N (HC) | N (PD) | Total N | HC Mean Age | PD Mean Age | Common Support | Subgroup Status | Reason |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|:---:|:---|
| **Under 50** | $[0, 50)$ | 23 | 3 | 26 | $37.74$ | $47.01$ | $[43.1, 47.0]$ | **NOT ESTIMABLE** | Small-cell suppression: < 10 participants in at least one class (HC=23, PD=3) |
| **50–59** | $[50, 60)$ | 11 | 6 | 17 | $53.73$ | $57.88$ | $[56.5, 57.0]$ | **NOT ESTIMABLE** | Small-cell suppression: < 10 participants in at least one class (HC=11, PD=6) |
| **60–69** | $[60, 70)$ | 3 | 12 | 15 | $66.00$ | $65.58$ | $[61.0, 69.0]$ | **NOT ESTIMABLE** | Small-cell suppression: < 10 participants in at least one class (HC=3, PD=12) |
| **70 and above** | $\ge 70$ | 4 | 16 | 20 | $75.00$ | $75.01$ | $[71.0, 79.0]$ | **NOT ESTIMABLE** | Small-cell suppression: < 10 participants in at least one class (HC=4, PD=16) |

Because every age stratum violates the minimum cell size constraint in at least one diagnostic arm, cross-validated classification performance within age bands is formally **NOT ESTIMABLE**. Complete summary saved to `data/processed/m2_age_subgroup_summary.csv`.

---

## 11. Exploratory Feature-Level Multivariable Associations (BH-FDR)

In accordance with `docs/methodology/M2_METHODOLOGY_ADDENDUM.md`, multivariable logistic regression models were fitted for each of the 39 Core39 features (`voxneuro.features.schema.FEATURE_NAMES`) adjusted for age and biological sex, with Likelihood Ratio Tests (LRT) and Benjamini–Hochberg False Discovery Rate control ($q < 0.05$). The top five features by likelihood ratio test statistic are shown below:

| Feature Name | Standardized $\beta$ | Odds Ratio | LRT $\chi^2$ (df=1) | p (Unadjusted) | FDR q-value | Significant ($q < 0.05$)? |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `mfcc_10_sd` | $2.1997$ | $9.0222$ | $21.3094$ | $3.9081 \times 10^{-6}$ | $0.0001524$ | **Yes (Exploratory)** |
| `f0_median_hz` | $2.3034$ | $10.0080$ | $16.3545$ | $5.2532 \times 10^{-5}$ | $0.0010244$ | **Yes (Exploratory)** |
| `f0_mean_hz` | $2.1229$ | $8.3555$ | $15.4360$ | $8.5348 \times 10^{-5}$ | $0.0011095$ | **Yes (Exploratory)** |
| `mfcc_07_sd` | $1.1177$ | $3.0578$ | $10.9893$ | $9.1641 \times 10^{-4}$ | $0.0089001$ | **Yes (Exploratory)** |
| `mfcc_06_sd` | $1.1133$ | $3.0444$ | $10.5835$ | $1.1410 \times 10^{-3}$ | $0.0089001$ | **Yes (Exploratory)** |

*Note: All 39 evaluated features strictly belong to the authoritative `voxneuro.features.schema.FEATURE_NAMES` schema. Outdated feature designations from prior exploratory drafts have been completely removed. These feature-level associations represent exploratory within-cohort statistical associations adjusted for age and sex, and do NOT constitute validated Parkinson's biomarkers or establish standalone clinical diagnostic utility. Complete 39-feature summary saved to `data/processed/m2_feature_fdr_summary.csv`.*

---

## 12. Biological Sex Subgroup Stratification

Performance across biological sex strata on the primary seed ($2026$):

| Subgroup | Model Specification | Sample N (HC / PD) | Balanced Accuracy | ROC-AUC | Sensitivity | Specificity | Cell Support |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Female (F)** | `age_only_logistic` | $43$ ($25$ HC / $18$ PD) | **$86.00\%$** | $0.8711$ | $83.33\%$ | $88.00\%$ | Sufficient ($N \ge 10$) |
|  | `age_plus_sex_logistic` | $43$ ($25$ HC / $18$ PD) | **$86.00\%$** | $0.8711$ | $83.33\%$ | $88.00\%$ | Sufficient ($N \ge 10$) |
|  | `voice_only_svm` | $43$ ($25$ HC / $18$ PD) | **$73.56\%$** | $0.7844$ | $66.67\%$ | $80.44\%$ | Sufficient ($N \ge 10$) |
|  | `age_plus_sex_plus_voice`| $43$ ($25$ HC / $18$ PD) | **$79.56\%$** | $0.8356$ | $77.78\%$ | $81.33\%$ | Sufficient ($N \ge 10$) |
| **Male (M)** | `age_only_logistic` | $35$ ($16$ HC / $19$ PD) | **$80.92\%$** | $0.8224$ | $84.21\%$ | $77.63\%$ | Sufficient ($N \ge 10$) |
|  | `age_plus_sex_logistic` | $35$ ($16$ HC / $19$ PD) | **$80.92\%$** | $0.8224$ | $84.21\%$ | $77.63\%$ | Sufficient ($N \ge 10$) |
|  | `voice_only_svm` | $35$ ($16$ HC / $19$ PD) | **$66.78\%$** | $0.7138$ | $63.16\%$ | $70.39\%$ | Sufficient ($N \ge 10$) |
|  | `age_plus_sex_plus_voice`| $35$ ($16$ HC / $19$ PD) | **$71.88\%$** | $0.7862$ | $68.42\%$ | $75.33\%$ | Sufficient ($N \ge 10$) |

---

## 13. Prospective External Validation Protocol Summary

To overcome the demographic confounding and attrition limitations of historical data, Phase 8 specifies a formal prospective study protocol (`docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md`):
- **Protocol Status:** Draft prospective external-validation study protocol &mdash; requires formal clinical, statistical, ethics, and institutional review prior to study initiation.
- **Cohort Size:** $N = 240$ participants ($120$ clinically confirmed idiopathic PD, $120$ healthy controls).
- **Matching Criteria:** Frequency-matched on 5-year age bands (50–54, 55–59, 60–64, 65–69, 70–74, 75–80) and 1:1 biological sex matching ($60\text{ M} / 60\text{ F}$ per group).
- **Target Balance:** Standardized Mean Difference $|\text{SMD}| \le 0.10$ for age; biological sex absolute proportion difference $|\Delta_{\text{prop}}| \le 0.05$ (5 percentage points).
- **Acoustic Standards:** Sound-attenuated booth ($< 35\text{ dBA}$ ambient noise); calibrated studio condenser microphone at $15\text{ cm}$, $45^\circ$ off-axis; $44.1\text{ kHz}$ uncompressed 24-bit PCM; gain staged at $-12\text{ dBFS}$ to eliminate clipping.
- **Statistical Power:** $80\%$ power at two-sided $\alpha = 0.05$ to detect $\Delta \text{BA} \ge 0.08$ over demographic baseline assuming $\sigma_{\Delta} = 0.22$ planning standard deviation.

---

## 14. Reproducibility & Cryptographic Provenance Receipt Register

All data, figures, and models were generated using the locked environment (`pyproject.toml`, `requirements-lock.txt`, `uv.lock`) under CPython 3.12:

| Artifact Name | Relative Path | Purpose |
|:---|:---|:---|
| **Demographic Summary** | `data/processed/m2_demographic_summary.json` | Complete parametric & non-parametric audit statistics |
| **Attrition Summary** | `data/processed/m2_attrition_summary.json` | Exclusion counts, exact Clopper-Pearson CIs, Fisher test |
| **Matching Sensitivity** | `data/processed/m2_matching_sensitivity.csv` | Caliper threshold sensitivity across 0.1, 0.2, 0.3 SD |
| **Age Subgroup Summary** | `data/processed/m2_age_subgroup_summary.csv` | Age strata counts, common support, and suppression |
| **Feature FDR Summary** | `data/processed/m2_feature_fdr_summary.csv` | Multivariable LRT and Benjamini-Hochberg FDR results |
| **Comparator Metrics** | `data/processed/m2_comparator_metrics.csv` | Cross-validated metrics across all 8 models |
| **Paired Incremental** | `data/processed/m2_paired_incremental_voice.csv` | Paired $\Delta$ metrics, bootstrap CIs, McNemar p-values |
| **Sex Subgroups** | `data/processed/m2_sex_subgroup_summary.csv` | Male/female stratified performance breakdown |
| **Analysis Receipt** | `data/processed/m2_analysis_receipt.json` | Execution metadata, hashes, seeds, and findings |
| **HTML Master Dashboard** | `artifacts/reports/scientific_audit/m2_bias_audit.html` | Self-contained visual audit dashboard |
| **HTML Model Comparison**| `artifacts/reports/scientific_audit/m2_model_comparison.html`| Model performance hierarchy & paired comparisons |
| **Methodology Addendum** | `docs/methodology/M2_METHODOLOGY_ADDENDUM.md` | Strata & FDR specification |
| **External Protocol** | `docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md`| Prospective Phase 8 validation protocol |

---

*VoxNeuro Research Prototype &bull; Milestone 2 Verified Scientific Audit &bull; November 2026*
