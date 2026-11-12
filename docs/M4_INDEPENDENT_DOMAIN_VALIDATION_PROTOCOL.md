# Independent External Recording-Domain Validation Protocol

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Protocol Document Identifier:** `VOXNEURO-M4-EXT-VAL-2026-V1`  
**Status:** Pre-Registered Frozen Protocol  
**Effective Date:** 2026-11-12  

---

## 1. Scientific Objective and Scope

This protocol establishes the prospective, reproducible methodology for evaluating the frozen VoxNeuro Core39 acoustic reference model on genuinely independent external cohorts collected under non-reference recording domains.

The central scientific question is whether the reference model—trained on telephone-collected sustained-vowel recordings—maintains discriminative utility and acceptable calibration when presented with acoustic recordings obtained via alternative transducers (e.g. acoustic studio microphones, clinic dynamic microphones, or digital audio interfaces) without model retraining or threshold adaptation.

---

## 2. Frozen Reference Model Specification

All external evaluations conducted under this protocol must apply the frozen reference model bundle without modification. The reference model parameters, preprocessing pipeline, and feature extraction definitions are cryptographically bound:

| Specification Attribute | Bound Parameter Value / Digest |
|---|---|
| Model Bundle Artifact | `artifacts/models/uams_logistic_research.joblib` |
| Model Artifact SHA-256 | `eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333` |
| Model Bundle Version | `4` |
| Model Architecture | L2-Regularized Logistic Regression ($C=0.01$) |
| Feature Schema Version | `voxneuro.voice.v3` |
| Feature Schema Fingerprint | `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` |
| Feature Configuration Fingerprint | `190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9` |
| Audio Preprocessing Fingerprint | `8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d` |
| Development Training Dataset SHA-256 | `d83d37e901ab2e5ec2499f070bd507b1c5c2b754dda36d115184f57a1383ab77` |
| Training Evaluation Combined SHA-256 | `c73146c1a94e235dc0262877dfa5e4a425fff0a3019ab76e38ea51c22cacba80` |

### Protocol Invariants:
1. **Zero Retraining:** The model weights, intercept, and hyperparameters are immutable. Retraining or fine-tuning on external data is strictly prohibited.
2. **Zero Threshold Optimization:** The decision boundary is fixed at posterior probability threshold $P(\text{PD}) \ge 0.5$. Post-hoc selection of an "optimal" operating point on external data is considered data dredging and is disallowed.
3. **Zero Feature Modification:** Features must be extracted using the canonical Core39 v3 algorithm. No feature substitution, transformation, or pruning is permitted.

---

## 3. Cohort Eligibility and Data Hygiene

External datasets must satisfy rigorous eligibility criteria before inclusion:

1. **Participant Disjointness:** No participant may have contributed data to the UAMS development dataset. Overlap checks must be executed using cryptographic hashes of standardized pseudonymous IDs.
2. **Clinical Reference Standard:** Idiopathic Parkinson's disease confirmed by a certified neurologist (UK Brain Bank or MDS criteria). Healthy controls must have no documented history of neurodegenerative disorder.
3. **Phonation Task:** Sustained phonation of the open vowel `/a/` produced at comfortable pitch and loudness for at least 1.0 second.
4. **Unit of Analysis:** Analysis is conducted strictly at the **participant level**. When multiple phonations exist per participant, a prespecified aggregation rule must be applied (averaging extracted feature vectors across valid phonations per participant), preserving exchangeability.
5. **Quality Attrition Tracking:** All phonation attempts must be audited. Audio failing quality gates (clipping $> 1\%$, RMS $< 0.003$, voiced fraction $< 15\%$, or duration $< 1.0\text{s}$) must be recorded in an attrition log with diagnostic group stratifications.

---

## 4. Prespecified Statistical Endpoints

### 4.1 Primary Endpoint
- **Balanced Accuracy (BACC):** Defined as the unweighted mean of sensitivity and specificity:
  $$\text{BACC} = \frac{\text{Sensitivity} + \text{Specificity}}{2}$$
  Prespecified to prevent inflation due to class imbalance.

### 4.2 Secondary Endpoints
- **Sensitivity (Recall / True Positive Rate):** $\frac{\text{TP}}{\text{TP} + \text{FN}}$
- **Specificity (True Negative Rate):** $\frac{\text{TN}}{\text{TN} + \text{FP}}$
- **Positive Predictive Value (Precision):** $\frac{\text{TP}}{\text{TP} + \text{FP}}$
- **F1-Score:** Harmonic mean of precision and recall.
- **Area Under the Receiver Operating Characteristic (ROC-AUC):** Rank-order discrimination metric across continuous model decision scores.
- **Average Precision (AP) / PR-AUC:** Precision-recall area, evaluated with AP clearly distinguished from trapezoidal PR-AUC.
- **Matthews Correlation Coefficient (MCC):** Balanced measure across all confusion matrix quadrants.

### 4.3 Statistical Uncertainty & Bootstrap Resampling
- Participant-level stratified bootstrap resampling with $B = 1,000$ iterations.
- Fixed random seed: $2026$.
- Two-sided 95% confidence intervals constructed using the empirical percentile method $[\alpha/2, 1 - \alpha/2] = [2.5\%, 97.5\%]$.
- If total participant sample size $N < 20$ or any diagnostic subgroup $N_c < 10$, confidence intervals must be flagged as `UNRELIABLE_SMALL_SAMPLE` or `NOT_ESTIMABLE`.

---

## 5. Domain Shift Analysis Methodology

To diagnose the etiology of potential performance degradation, domain shift must be evaluated along two axes:

1. **Acquisition-Level Divergence:** Comparison of physical and digital parameters (sampling rate, bit depth, SNR, frequency response cutoff, AGC presence, dynamic range).
2. **Feature-Level Distribution Shift:**
   - For all 39 features, calculate the Standardized Mean Difference (Cohen's $d$ or Hedges' $g$) between the reference UAMS domain and the candidate external domain:
     $$d = \frac{\bar{x}_{\text{cand}} - \bar{x}_{\text{ref}}}{s_{\text{pooled}}}$$
   - Non-parametric two-sample Kolmogorov–Smirnov (KS) test for distributional divergence.
   - Family-wise multiple hypothesis testing correction using False Discovery Rate (Benjamini–Hochberg $\alpha = 0.05$) and Bonferroni adjustment.
   - **Critical Rule:** Absence of statistically significant shift ($p > 0.05$) is **never** interpreted as evidence of domain equivalence.

---

## 6. Demographic Subgroup & Small-Cell Safeguards

1. Performance must be stratified by age groups ($<60$, $60\text{--}69$, $\ge 70$) and biological sex where recorded.
2. **Small-Cell Suppression:** Any subgroup cell with fewer than 10 participants ($N < 10$) must have its summary metrics suppressed in distributable reports to prevent re-identification and statistical distortion.
3. Differences across demographic strata must be reported descriptively with confidence bounds; claims of cross-demographic fairness cannot be based on underpowered subgroup observations.

---

## 7. Approval and Governance Workflow

Execution of this evaluation protocol generates a candidate assessment dossier conforming to `voxneuro.domain_assessment.v1`. Generating a dossier **does not** constitute domain compatibility approval.

To attain approved compatibility status:
1. The candidate assessment dossier must undergo independent review by at least two maintainers (one biostatistical, one bioacoustic/clinical).
2. Maintainers must verify that balanced accuracy and sensitivity exceed prespecified clinical thresholds with acceptable confidence bounds.
3. Upon unanimous maintainer approval, the candidate report's SHA-256 digest must be manually incorporated into `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` in `src/voxneuro/modeling/domains.py` via a signed source-code commit.
4. Until such human approval occurs, the candidate domain remains strictly `inference_eligible: false`.
