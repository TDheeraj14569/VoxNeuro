# Recording-Domain Shift Methodology

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Methodology Identifier:** `VOXNEURO-M4-SHIFT-METHODOLOGY-V1`  
**Status:** Frozen Methodological Guide  
**Effective Date:** 2026-11-12  

---

## 1. Taxonomy of Domain Shift in Clinical Speech Processing

When a machine learning model trained on speech audio from domain $\mathcal{D}_{\text{ref}}$ is deployed on data from an external domain $\mathcal{D}_{\text{cand}}$, performance degradation can stem from four distinct, interacting types of distribution shift:

```
+-----------------------------------------------------------------------------------+
|                           DOMAIN SHIFT TAXONOMY                                   |
+-----------------------------------------------------------------------------------+
|  1. Covariate Shift          | P(X_cand) != P(X_ref) while P(Y|X) is constant.    |
|                              | Feature distribution alters due to acoustic filters|
+------------------------------+----------------------------------------------------+
|  2. Concept Shift            | P(Y|X_cand) != P(Y|X_ref).                         |
|                              | The physiological mapping between acoustic values  |
|                              | and disease status changes due to distortion.      |
+------------------------------+----------------------------------------------------+
|  3. Label (Prior) Shift      | P(Y_cand) != P(Y_ref).                             |
|                              | Proportion of PD vs. HC varies between cohorts.    |
+------------------------------+----------------------------------------------------+
|  4. Acquisition / Quality    | Differences in SNR, clipping, harmonic distortion, |
|     Shift                    | or codec compression masking vocal tremor.         |
+-----------------------------------------------------------------------------------+
```

---

## 2. Statistical Metrics and Shift Inference

### 2.1 Standardized Mean Difference (Cohen's $d$)
To quantify the magnitude of shift for continuous acoustic feature $j$ independent of measurement units, VoxNeuro computes Cohen's $d$ using the pooled sample standard deviation:

$$d_j = \frac{\bar{x}_{\text{cand}, j} - \bar{x}_{\text{ref}, j}}{s_{\text{pooled}, j}}$$

where:
$$s_{\text{pooled}, j} = \sqrt{\frac{(n_{\text{cand}} - 1)s_{\text{cand}, j}^2 + (n_{\text{ref}} - 1)s_{\text{ref}, j}^2}{n_{\text{cand}} + n_{\text{ref}} - 2}}$$

Standard heuristic effect-size interpretations:
- $|d| < 0.2$: Negligible shift.
- $0.2 \le |d| < 0.5$: Small domain shift.
- $0.5 \le |d| < 0.8$: Moderate domain shift.
- $|d| \ge 0.8$: Large domain shift (high risk of classification failure).

### 2.2 Distribution Divergence: Two-Sample Kolmogorov–Smirnov Test
To capture non-Gaussian distributional differences, skewness, and multimodality, the non-parametric two-sample Kolmogorov–Smirnov (KS) test is evaluated:

$$D_j = \sup_x |F_{\text{cand}, j}(x) - F_{\text{ref}, j}(x)|$$

where $F_{\text{cand}, j}$ and $F_{\text{ref}, j}$ are empirical cumulative distribution functions.

### 2.3 Multiple Comparison Control
Because 39 simultaneous statistical tests are performed (one for each Core39 feature), uncorrected hypothesis testing inflates the family-wise type I error rate:
$$\alpha_{\text{family}} = 1 - (1 - 0.05)^{39} \approx 86.5\%$$

VoxNeuro mandates two simultaneous multiple-testing adjustments:
1. **False Discovery Rate (FDR):** Calculated via the Benjamini–Hochberg step-up procedure at target FDR $q \le 0.05$.
2. **Bonferroni FWER Correction:** Adjusted threshold $\alpha_{\text{Bonf}} = \frac{0.05}{39} \approx 0.00128$.

---

## 3. Critical Methodological Invariant: The Non-Equivalence Fallacy

> [!WARNING]
> **Absence of Evidence is Not Evidence of Equivalence**  
> A failure to reject the null hypothesis of identical distributions ($p_{\text{FDR}} > 0.05$) must **never** be cited as scientific proof that two recording domains are equivalent or compatible. In statistical hypothesis testing, failure to reject $H_0$ can be caused by small sample sizes, high variance, or low statistical power. Equivalence requires prospective two one-sided tests (TOST) with prespecified clinical equivalence margins, combined with empirical out-of-domain classification accuracy.

---

## 4. Milestone 4 Current Empirical Status

> [!IMPORTANT]
> **Authoritative M4 Domain-Shift Status**  
> Domain-specific recording acquisition differences have been derived directly from each candidate domain's verified registry metadata (for example: `neurovoz_studio` AKG C420 headset in a quiet clinical room at 44.1 kHz / 16-bit vs. `pc_gita_condenser` Shure SM63L dynamic omnidirectional mic in a sound-treated booth at 44.1 kHz / 16-bit vs. `italian_parkinsons_headset` IPVS unverified hardware/rate/bit depth/environment marked `unknown`/`null`, each compared individually against `uams_telephone`). Empirical external feature-distribution comparison has not been performed because no eligible independent external feature dataset is available locally.
>
> Zero SMD or non-significant KS statistics must **never** be described as evidence of compatibility. A lack of observed statistical shift in pending or unmeasured data never establishes domain equivalence. All external candidate domains remain strictly unapproved for inference.

