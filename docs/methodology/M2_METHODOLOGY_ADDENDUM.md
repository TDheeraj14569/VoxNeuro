# VoxNeuro Milestone 2 Methodology Addendum
## Exploratory Subgroup Stratification & Feature Multiplicity Protocol

**Document ID:** `VN-METH-M2-ADD-001`  
**Version:** `1.0.0`  
**Status:** Pre-registered Exploratory Analysis Specification  
**Date:** November 2026  
**Relation to SAP:** Addendum to `docs/methodology/M2_STATISTICAL_ANALYSIS_PLAN.md`  

---

## 1. Scope & Scientific Intent

This Addendum supplements the primary VoxNeuro Milestone 2 Statistical Analysis Plan (`M2_STATISTICAL_ANALYSIS_PLAN.md`). 

> [!IMPORTANT]
> **Exploratory Status Notice:** The analyses specified herein are secondary and exploratory. They do NOT replace, modify, or override the pre-registered primary hypothesis testing, comparator hierarchy, paired bootstrap confidence intervals, or pre-registered SAP decision rules governing the incremental value of acoustic features beyond demographic baselines.

The purpose of this Addendum is twofold:
1. Provide a rigorous, pre-specified protocol for evaluating model performance within **age-stratified subgroups**, enforcing small-cell suppression to guard against mathematically unstable partitions.
2. Provide a standardized multiplicity control protocol for **feature-level multivariable associations**, adjusting for age and biological sex while bounding the False Discovery Rate (FDR).

---

## 2. Age-Stratified Subgroup Analysis Protocol

### 2.1 Fixed Age Strata Definitions
To explore whether predictive performance or demographic confounding varies across stages of the lifespan, the cohort is partitioned into four standard age intervals:
- **Stratum 1 (Under 50):** Chronological age $< 50.0$ years.
- **Stratum 2 (50–59):** Chronological age $\ge 50.0$ and $< 60.0$ years.
- **Stratum 3 (60–69):** Chronological age $\ge 60.0$ and $< 70.0$ years.
- **Stratum 4 (70 and above):** Chronological age $\ge 70.0$ years.

### 2.2 Small-Cell Suppression Rule
Cross-validated classification metrics (Balanced Accuracy, Sensitivity, Specificity, ROC-AUC) require adequate representation across both diagnostic classes to produce mathematically stable out-of-fold estimates.

- **Threshold:** Each age stratum must contain at least **$N_{\text{min}} = 10$ participants per diagnostic arm** (HC $\ge 10$ and PD $\ge 10$).
- **Rule Enforcement:** If either diagnostic arm within a stratum has fewer than 10 participants:
  - Quantitative classification metrics are designated as **`NOT ESTIMABLE`**.
  - A formal suppression justification is logged: `Small-cell suppression: < 10 participants in at least one class`.
  - Raw demographic counts ($N_{\text{HC}}$, $N_{\text{PD}}$, $N_{\text{Total}}$, mean ages, and common support ranges) are preserved and reported for epidemiological transparency.
- **Implementation:** Governed by `voxneuro.dataset.bias_audit.audit_age_strata()`. Output artifact: `data/processed/m2_age_subgroup_summary.csv`.

---

## 3. Feature-Level Multivariable Association Protocol

### 3.1 Model Formulation
To identify which specific acoustic features exhibit residual Parkinsonian associations after controlling for demographic confounding, each feature $j \in \{1, \dots, 39\}$ in the Core39 suite (`voxneuro.features.schema.FEATURE_NAMES`) is evaluated via nested multivariable logistic regression models:

- **Null Model ($\mathcal{M}_0$, Demographics Only):**
  $$\text{logit}(P(Y=1 \mid \text{age}, \text{sex})) = \beta_0 + \beta_{\text{age}} \cdot z(\text{age}) + \beta_{\text{sex}} \cdot \text{sex}$$
- **Full Model ($\mathcal{M}_{1,j}$, Demographics + Feature $j$):**
  $$\text{logit}(P(Y=1 \mid \text{age}, \text{sex}, f_j)) = \beta_0 + \beta_{\text{age}} \cdot z(\text{age}) + \beta_{\text{sex}} \cdot \text{sex} + \beta_j \cdot z(f_j)$$

where $z(\cdot)$ denotes sample z-score standardization ($\mu=0, \sigma=1$) across the evaluated cohort, and $\text{sex}$ is binary-coded ($0 = \text{Female}, 1 = \text{Male}$).

### 3.2 Likelihood Ratio Test (LRT)
The partial contribution of acoustic feature $j$ beyond age and sex is evaluated using the Likelihood Ratio Test:
$$\Lambda_j = 2 \cdot (\ell(\mathcal{M}_{1,j}) - \ell(\mathcal{M}_0))$$
where $\ell(\cdot)$ denotes the log-likelihood of the fitted model. Under the null hypothesis that $\beta_j = 0$, $\Lambda_j$ is asymptotically distributed as $\chi^2$ with 1 degree of freedom ($\text{df} = 1$):
$$p_j = P(\chi^2_1 \ge \Lambda_j)$$

### 3.3 Multiplicity Control: Benjamini–Hochberg False Discovery Rate
Because 39 simultaneous hypothesis tests are conducted across the Core39 feature suite, unadjusted p-values are susceptible to substantial Type I error inflation. Multiplicity is controlled using the **Benjamini–Hochberg (BH) procedure**:

1. Sort unadjusted LRT p-values in ascending order: $p_{(1)} \le p_{(2)} \le \dots \le p_{(m)}$, where $m = 39$.
2. For each rank $k \in \{1, \dots, m\}$, compute the raw adjusted value:
   $$q_{(k)} = \min\left(1.0, \frac{m}{k} \cdot p_{(k)}\right)$$
3. Enforce monotonicity via cumulative minimum from highest rank to lowest:
   $$q_{(k)}^* = \min_{i \ge k} q_{(i)}$$
4. Features satisfying $q_{(k)}^* < 0.05$ are identified as exhibiting exploratory within-cohort statistical associations at an FDR threshold of $5\%$.

- **Implementation:** Governed by `voxneuro.dataset.bias_audit.audit_feature_level_associations()`. Output artifact: `data/processed/m2_feature_fdr_summary.csv`.

---

## 4. Preservation of Primary SAP Conclusions

1. **Exploratory Status:** Finding that an individual acoustic feature has an exploratory association ($q < 0.05$) does not contradict the primary finding that multivariable voice classifiers fail to provide statistically supported incremental out-of-fold generalization beyond age and sex.
2. **Estimation Variance:** In high-dimensional acoustic models with small sample sizes, estimating 39 coefficients alongside regularization penalties introduces variance that offsets marginal single-feature signal.
3. **Clinical Interpretation:** These exploratory associations provide candidate hypothesis targets for the prospective external cohort (`docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md`), but do not establish clinical diagnostic utility in isolation.

---

*VoxNeuro Research Prototype &bull; Milestone 2 Methodology Addendum &bull; Pre-registered Statistical Standards*
