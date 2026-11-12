# Milestone 5 Longitudinal Analysis Methodology

**Methodological Specification:** Intra-Individual Speech Acoustic Tracking  
**Audience:** Biostatisticians, Speech Scientists, Clinical Research Investigators  
**Status:** Implemented & Verified  

---

## 1. Strict Scientific Integrity Notice

> [!IMPORTANT]
> **NON-DIAGNOSTIC & NON-PROGRESSION NOTICE**  
> Longitudinal voice measurements calculated by VoxNeuro are strictly descriptive intra-individual acoustic observations ($\Delta = \text{Visit}_k - \text{Visit}_1$). 
> 
> They MUST NOT be interpreted, published, or represented as:
> - Direct evidence of neurodegenerative disease progression.
> - Measurement of Parkinson's disease motor symptom worsening.
> - Assessment of pharmacological or therapeutic treatment response.
> - A surrogate clinical endpoint or clinical trial outcome measure.

Acoustic variation across recording visits is subject to normal diurnal fluctuations, hydration changes, respiratory state, vocal fatigue, and ambient acoustic variability. Without extensive prospective multi-center validation against validated clinical scales (e.g. MDS-UPDRS Part III), voice delta scores remain exploratory physical measurements.

---

## 2. Longitudinal Metrics Framework

### 2.1 Intra-Individual Deltas
For each eligible participant present in both baseline ($\text{Visit}_1$) and follow-up ($\text{Visit}_k$):

$$\Delta f_{i} = f_{i}(\text{Visit}_k) - f_{i}(\text{Visit}_1)$$

where $f_{i}$ is any defined acoustic feature (e.g. `f0_mean_hz`, `jitter_local_percent`, `shimmer_local_percent`, `estimated_event_rate_per_s`).

### 2.2 Visit Interval Characterization
Because speech visits rarely occur at exact calendar intervals, VoxNeuro computes explicit distribution statistics for visit spacing:
- Mean interval in days
- Standard deviation of interval
- Median and Interquartile Range (IQR) of interval
- Minimum and maximum observed intervals

### 2.3 Group-Level Descriptive Summaries
For cohorts with at least $N = 5$ observations for a given feature:
- Parametric summary: Mean change ($\bar{\Delta}$) and sample standard deviation ($s_{\Delta}$).
- Non-parametric summary: Median change ($\tilde{\Delta}$) and Interquartile Range ($\text{IQR}_{\Delta}$).
- For features with $N < 5$, summaries are marked `INSUFFICIENT_OBSERVATIONS_FOR_SUMMARY` to prevent misleading small-sample statistics.

---

## 3. Small-Cell Suppression Threshold ($N < 10$)

To safeguard participant anonymity and comply with statistical reporting guidelines:
- Any participant count or session count where $1 \le N \le 9$ is automatically suppressed as `< 10 (Suppressed)` in all generated aggregate reports and CSV exports.
- Zero counts ($N = 0$) are preserved as exact values to indicate complete absence of events.
- Counts of $N \ge 10$ are reported as exact numbers.

---

## 4. Operational Cohort Attrition Tracking

Retention rate ($R_k$) and attrition rate ($A_k$) at visit $k$ are defined relative to the baseline cohort ($N_1$):

$$R_k = \frac{N_k}{N_1}$$

$$A_k = 1.0 - R_k$$

Attrition metrics serve exclusively as operational study monitoring indicators (evaluating study retention efficiency) and do not reflect patient prognosis.
