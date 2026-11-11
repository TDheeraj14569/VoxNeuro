# VoxNeuro External Validation Cohort Protocol (Phase 8 Specification)

**Document ID:** `VN-PROT-M2-EXT-001`  
**Version:** `1.1.0`  
**Status:** Draft prospective external-validation study protocol – requires clinical, statistical, ethics and institutional review  
**Date:** November 2026  
**Focus:** Demographic Balancing, Standardized Acoustic Recording, and Statistical Power Plan for External Independent Cohorts  

> [!IMPORTANT]
> **Regulatory Notice:** This document is a prospective engineering study protocol specification drafted for future academic and clinical trial planning. It does NOT represent an active clinical trial registration, approved Institutional Review Board (IRB) submission, or cleared medical device protocol. Prior to patient recruitment, this protocol requires formal ethical approval, multi-site institutional authorization, and prospective registration on clinical registry platforms.

---

## 1. Executive Summary & Clinical Rationale

Milestone 2 of VoxNeuro identified critical scientific limitations in historical research cohorts (UAMS, Figshare DOI 10.6084/m9.figshare.23849127.v1):
1. **Severe Age Confounding:** A 19.31-year age disparity between Healthy Controls (mean $47.73 \pm 14.33$ years) and Parkinson's Disease participants (mean $67.04 \pm 8.98$ years; SMD = -1.61, $p = 1.75 \times 10^{-8}$).
2. **No Supported Incremental Voice Benefit Beyond Demographics:** The retrospective cohort did not establish supported incremental predictive benefit from adding the current voice features beyond demographic comparators. A simple age-only logistic model achieves $83.89\%$ balanced accuracy ($84.90\%$ ROC-AUC), whereas the primary linear acoustic model achieves only $70.54\%$ ($75.59\%$ ROC-AUC). Combining voice features with demographic variables yields $\Delta\text{BA} = -0.0758$ [95% bootstrap CI: $-0.1842, +0.0284$] (repeated-CV $\Delta = -0.0681$, supplementary McNemar $p = 0.2632$).
3. **Class-Dependent Attrition:** Quality exclusions (acoustic clipping) occurred exclusively in the Parkinson cohort ($7.5\%$ excluded vs $0\%$ HC).
4. **Sample Size Exhaustion on Caliper Matching:** Enforcing a standard epidemiological caliper ($0.2$ pooled SD $= 2.44$ years) with exact sex matching leaves only 5 pairs (10 participants), rendering matched modeling formally not estimable.

To rigorously test whether sustained-vowel phonation ($/a/$) carries genuine Parkinsonian acoustic markers or merely mirrors demographic senescence and unstandardized recording artifacts, an **independent prospective validation cohort** is mandatory. This protocol governs the design, sample size, acquisition, and ethical oversight of that future study.

---

## 2. Study Objectives & Hypotheses

### 2.1 Primary Objective
To determine whether sustained-vowel acoustic features (schema `voxneuro.voice.v3`, Core39) provide statistically significant incremental predictive accuracy beyond chronological age and biological sex in a prospective, demographically frequency-matched clinical cohort.

### 2.2 Primary Statistical Hypothesis
- **Null Hypothesis ($H_0$):** In a demographically balanced cohort (SMD $< 0.10$ for age; exact $1:1$ sex matching), the addition of Core39 acoustic features to a demographic baseline model yields no increase in cross-validated balanced accuracy ($\Delta \text{BA} \le 0$).
- **Alternative Hypothesis ($H_1$):** Core39 acoustic features provide a clinically meaningful incremental increase in balanced accuracy ($\Delta \text{BA} \ge 0.08$ [8 percentage points], two-sided $\alpha = 0.05$).

### 2.3 Secondary Objectives
1. Quantify test-retest acoustic feature variance across multiple recording trials per participant within the same visit.
2. Evaluate acoustic stability across controlled microphone transducers (studio condenser vs calibrated smartphone internal MEMS microphone).
3. Test correlation between specific acoustic dysphonic clusters (jitter/shimmer vs MFCC spectral envelopes) and motor symptom severity (MDS-UPDRS Part III motor score and Hoehn & Yahr staging).

---

## 3. Study Population & Eligibility Criteria

The study will recruit prospective participants from tertiary movement disorder clinics and matched community controls.

### 3.1 Parkinson's Disease (PD) Cohort
- **Diagnostic Criteria:** Clinically established or clinically probable Parkinson's disease diagnosed by a board-certified movement disorder specialist according to the **Movement Disorder Society (MDS) Clinical Diagnostic Criteria**.
- **Age Window:** 50 to 80 years at enrollment.
- **Stage:** Hoehn & Yahr stages 1 to 3 in the defined medication state ("ON" state, 1–2 hours post-levodopa dose, or "OFF" state explicitly documented).
- **Inclusion Criteria:**
  - Capable of providing voluntary informed consent.
  - Native or fluent speaker capable of following sustained phonation instructions.
  - Documented clinical history, including disease duration, current dopaminergic regimen (Levodopa Equivalent Daily Dose, LEDD), and recent MDS-UPDRS III score.

### 3.2 Healthy Control (HC) Cohort
- **Matching Scheme:** Frequency-matched to the PD cohort within 5-year age strata (50–54, 55–59, 60–64, 65–69, 70–74, 75–80) and exact $1:1$ biological sex matching.
- **Inclusion Criteria:**
  - Age 50 to 80 years.
  - No personal or first-degree family history of neurodegenerative disease (Parkinson's, Alzheimer's, ALS, Huntington's).
  - No active neurological, movement, or cognitive impairment (Montreal Cognitive Assessment [MoCA] $\ge 26$).

### 3.3 Universal Exclusion Criteria (Both Groups)
1. Acute or chronic structural laryngeal disease, vocal cord nodules/polyps, history of laryngeal surgery, or head/neck radiation.
2. Active acute upper respiratory tract infection or acute allergic rhinitis/laryngitis within 3 weeks prior to recording.
3. Severe chronic pulmonary disease (e.g., severe COPD or asthma requiring home oxygen therapy) compromising sustained phonation duration ($< 3.0$ seconds).
4. History of stroke, traumatic brain injury with lasting neurological deficit, or other neurological movement disorders (e.g., essential tremor, multiple system atrophy, progressive supranuclear palsy).
5. Active tracheostomy or indwelling vocal prosthesis.

---

## 4. Standardized Acoustic Acquisition Protocol

To prevent the recording-quality and gain-calibration asymmetries observed in telephone-collected datasets, all recordings must comply with strict acoustic engineering standards.

### 4.1 Acoustic Environment
- **Setting:** Dedicated sound-attenuated acoustic booth or quiet clinical examination room certified to ambient noise $< 35\text{ dBA}$ (Type 1 sound level meter).
- **Background Noise Measurement:** 10-second ambient baseline recording captured immediately prior to participant testing; ambient SNR must exceed $30\text{ dB}$.

### 4.2 Hardware & Transducer Specifications
- **Primary Microphone:** Calibrated, large-diaphragm studio condenser microphone with a cardioid polar pattern (e.g., AKG C414 XLS or Shure KSM32).
- **Secondary Transducer (Exploratory):** Standardized, uncompressed mobile test device (e.g., Apple iPhone 15 internal bottom MEMS microphone) placed adjacent to the primary microphone.
- **Positioning:** Fixed microphone stand with pop filter; microphone capsule placed at exactly **$15.0\text{ cm}$** from the oral aperture, oriented at a **$45^\circ$ angle** off-axis to avoid direct aerodynamic plosive air blast.
- **Audio Interface:** 24-bit discrete analog-to-digital converter (e.g., Focusrite Scarlett 2i2 or Motu M2) operating at **$44,100\text{ Hz}$** or **$48,000\text{ Hz}$** uncompressed linear PCM WAV.

### 4.3 Gain Staging & Calibration
- **Calibration Tone:** Pre-session 1 kHz calibration tone at 94 dB SPL using an acoustic calibrator to establish absolute SPL reference.
- **Dynamic Headroom:** Analog input gain set such that comfortable loud phonation peaks at **$-12\text{ dBFS}$**, leaving at least $10\text{ dB}$ of headroom to prevent acoustic clipping. Any recording with sample clipping ($> 0.0\%$ samples at $\pm 1.0$) is immediately flagged and re-recorded.

### 4.4 Voice Recording Tasks
Each participant performs the following sequence with 30-second rests between trials:
1. **Task 1 (Primary):** Three (3) successive trials of sustained vowel $/a/$ at comfortable pitch and loudness, held for at least 5 seconds per trial on a single breath.
2. **Task 2 (Supplementary):** Three (3) successive trials of sustained vowel $/i/$ (high-front vowel).
3. **Task 3 (Exploratory):** Standardized phonetically balanced reading passage (e.g., "The Rainbow Passage", first paragraph, or "Grandfather Passage").

---

## 5. Sample Size Determination & Statistical Power Plan

### 5.1 Power Calculation Parameters & Methodological Clarification
- **Primary Metric:** Increment in cross-validated Balanced Accuracy ($\Delta \text{BA} = \text{BA}_{\text{Age+Sex+Voice}} - \text{BA}_{\text{Age+Sex}}$).
- **Type I Error ($\alpha$):** 0.05 (two-sided).
- **Statistical Power ($1 - \beta$):** 0.80 ($80\%$).
- **Minimum Clinically Meaningful Effect Size:** $\Delta \text{BA} \ge 0.08$ (8.0 percentage points improvement over demographic baseline).
- **Assumed Standard Deviation of Paired Differences:** $\sigma_{\Delta} = 0.22$ (Provisional Planning Assumption).

> [!WARNING]
> **Methodological Clarification on Planning Standard Deviation ($\sigma_{\Delta} = 0.22$):**
> The value $\sigma_{\Delta} = 0.22$ is an exploratory planning assumption derived from resampling variability across cross-validation folds in a single historical cohort (UAMS), NOT an independently established prospective participant-level paired standard deviation.
> Cross-validation fold variability reflects internal fold partition variance and is not automatically equivalent to an independent prospective participant-level paired standard deviation across distinct individuals. True paired variance on an independent test cohort will depend on prospective multi-site acoustic calibration, test-retest variance across repeated trials, device variation, and participant clinical heterogeneity.

### 5.2 Sensitivity Scenarios Across Plausible Paired Standard Deviations
Because the prospective paired-difference standard deviation cannot be known with certainty prior to pilot multi-site data collection, sample size requirements are evaluated across a spectrum of plausible standard deviations $\sigma_{\Delta} \in \{0.15, 0.20, 0.22, 0.25, 0.30\}$ for detecting $\Delta\text{BA} \ge 0.08$ at two-sided $\alpha = 0.05$ with $80\%$ statistical power:

$$N_{\text{pairs}} = \left( \frac{(Z_{\alpha/2} + Z_{\beta}) \cdot \sigma_{\Delta}}{\Delta} \right)^2 = \left( \frac{(1.960 + 0.842) \cdot \sigma_{\Delta}}{0.08} \right)^2 \approx (35.025 \cdot \sigma_{\Delta})^2$$

| Plausible Paired SD ($\sigma_{\Delta}$) | Targeted Effect ($\Delta\text{BA}$) | Nominal Pairs ($N_{\text{pairs}}$) | Nominal Participants ($1:1$) | Attrition-Adjusted Pairs ($+10\%$) | Attrition-Adjusted Participants | Illustrative Subgroup / Multi-Site Buffer Scenario |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **$0.15$** | $0.08$ | $28$ | $56$ | $31$ | $62$ | $120$ |
| **$0.20$** | $0.08$ | $50$ | $100$ | $55$ | $110$ | $200$ |
| **$0.22$ (Provisional Baseline)** | $0.08$ | $60$ | $120$ | $67$ | $134$ | **$240$ (Planning Target)** |
| **$0.25$** | $0.08$ | $77$ | $154$ | $86$ | $172$ | $300$ |
| **$0.30$** | $0.08$ | $111$ | $222$ | $124$ | $248$ | $450$ |

### 5.3 Recruitment Planning Target vs. Statistical Guarantees
The total study enrollment target of **$N = 240$ participants** ($120$ idiopathic PD, $120$ healthy controls) is an **illustrative recruitment planning scenario**, not a validated or statistically guaranteed sample size.

The eventual prospective trial design must formally account for:
1. **Independent Test-Set Size:** Allocating sufficient sample size for completely held-out prospective evaluation distinct from any fine-tuning or threshold calibration partitions.
2. **Participant-Level Clustering & Repetitions:** Accounting for intra-subject correlation across repeated phonation trials (Tasks 1–3) using hierarchical mixed-effects models or Generalized Estimating Equations (GEE).
3. **Multi-Site & Transducer Variance:** Accounting for site-to-site ambient variation, acoustic booth differences, and inter-microphone differences (studio condenser vs smartphone MEMS).
4. **Test-Retest Reliability:** Estimating intraclass correlation coefficients (ICC) across repeated trials within and between visits.
5. **Participant Attrition & Quality Exclusions:** Providing adequate buffer for acoustic clipping or failure to complete sustained phonation ($> 3.0$ seconds).
6. **Precision of Secondary Diagnostic Metrics:** Providing sufficient power for sensitivity, specificity, and ROC-AUC confidence interval width.
7. **Incremental Model Comparison Methodology:** Pre-registering exact paired bootstrap or permutation test specifications.

> [!IMPORTANT]
> **Biostatistician Review Requirement:** Prior to protocol freeze, ethics committee submission, or patient recruitment, a qualified biostatistician must conduct a formal power simulation, establish prospective design effects, and sign off on the definitive sample size calculation and prospective Statistical Analysis Plan (SAP).

---

## 6. Ethics, Governance, Biometric Privacy, and Data Access Register

| Requirement | Specification | Regulatory / Compliance Anchor |
|:---|:---|:---|
| **Institutional Review Board (IRB / IEC)** | Prospective review and approval required from Institutional Review Boards / Institutional Ethics Committees (IEC) at each clinical trial site prior to enrollment. | 45 CFR 46 / Declaration of Helsinki / ICMR Guidelines 2017 |
| **Informed Consent** | Written informed consent with explicit clauses permitting secondary, pseudonymized research use, biometric data handling, and scientific dissemination. | HIPAA Authorization / GDPR Article 9 / DPDP Act 2023 |
| **Biometric Audio Identifiability Notice** | Voice recordings constitute biometric data containing unique acoustic, physiological, and anatomical vocal-tract characteristics. Removal of direct identifiers (Name, MRN, DOB) does NOT render voice audio completely anonymized. Audio recordings are classified as sensitive personal health data with inherent re-identification risks. | ISO/IEC 19794-13 / HIPAA Safe Harbor & Expert Determination / GDPR Recital 51 |
| **Pseudonymization & Security** | Immediate replacement of patient identifiers with cryptographic pseudonyms (`EXT-SITE01-P001`). Age recorded in integer years; sex recorded as biological sex (M/F). Data encrypted at rest (AES-256) and in transit (TLS 1.3). | Digital Personal Data Protection Act, 2023 (DPDP Act) / HIPAA Security Rule |
| **Data Repository Registration** | Prospective registration on ClinicalTrials.gov and Open Science Framework (OSF) with frozen, pre-registered statistical analysis plan prior to participant enrollment. | ICMJE / STARD-AI Guidelines |
| **Controlled Data Access Architecture** | Processed feature matrices and pseudonymized audio deposited in controlled-access scientific repositories (e.g., PhysioNet, Zenodo restricted access) governed by strict Data Transfer Agreements (DTA). | FAIR Data Principles / ICMR Data Sharing Guidelines |

---

## 7. Success, Stopping Criteria, and Balanced Inference Framework

The external validation cohort study will be evaluated under the following balanced scientific framework:

### 7.1 Prespecified Quality and Balance Criteria
1. **Demographic Balance Achieved:** Age standardized mean difference satisfies $|\text{SMD}| \le 0.10$ and biological sex absolute proportion difference satisfies $|\Delta_{\text{prop}}| \le 0.05$ (5 percentage points).
2. **Quality Attrition Controlled:** Overall recording attrition is $< 3.0\%$ with no statistically significant class asymmetry ($p > 0.20$ via Fisher's exact test).

### 7.2 Formal 5-Point Balanced Statistical Inference Framework
The primary outcome ($\Delta\text{BA} = \text{BA}_{\text{Age+Sex+Voice}} - \text{BA}_{\text{Age+Sex}}$) shall be interpreted strictly according to the following decision framework:
1. **Evidence of Positive Incremental Predictive Performance:** If the 95% paired confidence interval is entirely above zero ($\text{CI}_{\text{low}} > 0$), there is statistically supported evidence of positive incremental predictive performance under the prespecified statistical design.
2. **Evidence Exceeding Clinically Meaningful Threshold:** If the 95% confidence interval is entirely above a separately prespecified clinically meaningful threshold $\Delta_{\text{crit}}$ ($\text{CI}_{\text{low}} \ge \Delta_{\text{crit}}$, e.g. $\Delta \ge 0.08$), there is statistically supported evidence of an incremental effect exceeding that clinically meaningful threshold.
3. **Inconclusive Incremental Effect:** If the 95% confidence interval crosses zero ($\text{CI}_{\text{low}} \le 0 \le \text{CI}_{\text{high}}$), the trial is inconclusive regarding a positive incremental effect.
4. **Ruling Out Clinically Meaningful Incremental Effect:** If the upper bound of the 95% confidence interval is below the prespecified clinically meaningful threshold ($\text{CI}_{\text{high}} < \Delta_{\text{crit}}$), the data rule out an incremental effect as large as that threshold under the study's design assumptions.
5. **No Evidence of Absence from High p-Value:** A non-significant p-value alone ($p \ge 0.05$) does NOT establish equivalence or prove the complete absence of clinical utility ("absence of evidence is not evidence of absence").

### 7.3 Methodological Distinctions
- **Statistical Superiority:** Testing whether voice features add incremental predictive performance ($\Delta > 0$).
- **Clinical Meaningfulness:** Testing whether the point estimate and confidence interval satisfy $\Delta \ge \Delta_{\text{crit}}$ to justify clinical adoption.
- **Statistical Equivalence:** Testing whether the incremental difference lies strictly within an a priori defined equivalence margin $[-\delta, +\delta]$ using two one-sided tests (TOST).
- **Non-Inferiority:** Testing whether performance is not unacceptably worse than a reference standard by more than a predefined non-inferiority margin.

> [!IMPORTANT]
> **Pre-registration Requirement:** All clinically meaningful thresholds ($\Delta_{\text{crit}}$), equivalence margins ($\delta$), and decision boundaries must be prespecified a priori in the approved Statistical Analysis Plan prior to participant enrollment and NEVER selected post-hoc after inspecting study data.

---

*VoxNeuro Research Prototype &bull; Phase 8 External Validation Protocol &bull; Biodesign Engineering Specification*
