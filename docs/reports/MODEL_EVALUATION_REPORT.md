# VoxNeuro Model Evaluation Report
## Multi-Family Benchmark, Demographic Baseline Comparisons, and Scientific Evidence

**Document Version:** 1.0.0-production  
**Date:** 2026-11-12  
**Status:** **RESEARCH BENCHMARK ONLY — NOT FOR CLINICAL DIAGNOSIS**  
**Evidence Level:** Internal Participant-Grouped Cross-Validation (UAMS N=78, UCI #470 N=252)

---

## 1. Executive Summary

This report presents the rigorous empirical evaluation of multiple classification model families on the **UAMS** (University of Arkansas for Medical Sciences) voice dataset and the **UCI #470** Parkinson's dataset.

### Key Findings
1. **Voice-Only Models (UAMS Development Cohort, N=78):**
   - **Extra Trees** achieved the highest mean balanced accuracy among voice-only candidates: **0.7821** (ROC-AUC: 0.7831, Brier score: 0.1888, ECE: 0.1354).
   - **Random Forest** achieved balanced accuracy of **0.7726** (ROC-AUC: 0.7877, Brier score: 0.1844, ECE: 0.0969).
   - **RBF SVM** achieved balanced accuracy of **0.7442** (ROC-AUC: 0.7732, Brier score: 0.1996, ECE: 0.1338).
   - **Logistic Regression (L2)** achieved balanced accuracy of **0.6549** (ROC-AUC: 0.7198, Brier score: 0.2452, ECE: 0.1759).
   - **Linear SVM (Calibrated)** achieved balanced accuracy of **0.6200** (ROC-AUC: 0.6664, Brier score: 0.2292, ECE: 0.0375).
   - **Dummy Prior Baseline:** Balanced accuracy **0.5000** (ROC-AUC: 0.4743, Brier: 0.2497, ECE: 0.0001).

2. **The Demographic Confounding Challenge:**
   - In the UAMS cohort, the **Age-Only Logistic Regression** achieved balanced accuracy of **0.8389** (ROC-AUC: 0.8490).
   - The healthy control cohort mean age is 47.7 years (SD 14.3) while the Parkinson's cohort mean age is 67.0 years (SD 9.0), a standardized mean difference (SMD) of -1.61 ($p = 1.75 \times 10^{-8}$).
   - In paired statistical testing, adding voice features to age (Age + Voice) yielded $\Delta\text{BA} = -0.0758$ (95% CI [$-0.1842, +0.0284$], McNemar $p = 0.2632$).
   - **Conclusion:** Voice features did not provide a statistically significant positive incremental predictive benefit over demographic age alone in this small cohort.

3. **UCI #470 Benchmark (N=252 participants, 752 predictors):**
   - Extra Trees: ROC-AUC 0.8494, BA 0.7236, Brier 0.1273.
   - Random Forest: ROC-AUC 0.8479, BA 0.7282, Brier 0.1314.
   - Calibrated Linear SVM: ROC-AUC 0.8423, BA 0.5781, Brier 0.1439.
   - Logistic Regression: ROC-AUC 0.8308, BA 0.7330, Brier 0.1427.

---

## 2. Experimental Methodology

### 2.1 Validation Design
- **Participant-Grouped Cross-Validation:** 5-fold outer `StratifiedGroupKFold` split strictly by `participant_id`. No participant's audio appears in both training and test folds.
- **Nested Tuning:** 3-fold inner cross-validation for hyperparameter tuning. Imputation and standard scaling fit strictly within each training fold.
- **Metrics Evaluated:** Balanced Accuracy (BA), Sensitivity (Recall), Specificity, ROC-AUC, Precision, F1-score, Brier Score, and Expected Calibration Error (ECE).

### 2.2 Feature Representation (Core39)
The primary feature extraction pipeline computes 39 schema-aligned acoustic features (`voxneuro.voice.v3`):
- **Pitch/F0:** `f0_mean_hz`, `f0_median_hz`, `f0_sd_hz`, `f0_min_hz`, `f0_max_hz`, `f0_range_hz`.
- **Perturbation:** `jitter_local` (relative pitch variability), `shimmer_local` (amplitude variability).
- **Harmonicity:** `hnr_mean_db` (Harmonics-to-Noise Ratio).
- **Spectral Envelope:** 13 MFCC coefficients (means and standard deviations: 26 features).
- **Spectral Shape:** `spectral_centroid_mean_hz`, `spectral_rolloff_mean_hz`, `spectral_bandwidth_mean_hz`, `zero_crossing_rate_mean`.

---

## 3. UAMS Benchmark Results

| Model Family | ROC-AUC | PR-AUC | Balanced Acc | Sensitivity | Specificity | F1 Score | Brier Score | ECE | Calibration Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Dummy Prior** | 0.4743 | 0.4606 | 0.5000 | 0.0000 | 1.0000 | 0.0000 | 0.2497 | 0.0001 | Internally Calibrated |
| **Linear SVM (Calibrated)** | 0.6664 | 0.6469 | 0.6200 | 0.4595 | 0.7805 | 0.5397 | 0.2292 | **0.0375** | Well Calibrated |
| **Logistic Regression (L2)** | 0.7198 | 0.7288 | 0.6549 | 0.6757 | 0.6341 | 0.6494 | 0.2452 | 0.1759 | Moderate ECE |
| **HistGradientBoosting** | 0.7126 | 0.6872 | 0.6427 | 0.6757 | 0.6098 | 0.6410 | 0.3051 | 0.2994 | Overconfident |
| **RBF SVM** | 0.7732 | 0.7235 | 0.7442 | 0.7568 | 0.7317 | 0.7368 | 0.1996 | 0.1338 | Uncalibrated Margin |
| **Random Forest** | **0.7877** | 0.7143 | 0.7726 | **0.8108** | 0.7317 | 0.7692 | **0.1844** | 0.0969 | Bagged Ensembles |
| **Extra Trees** | 0.7831 | **0.7321** | **0.7821** | 0.8108 | **0.7561** | **0.7792** | 0.1888 | 0.1354 | Bagged Ensembles |

---

## 4. Subgroup Analysis: Sex and Age

Performance was evaluated across demographic subgroups:
- **Female Participants (N=36, 17 PD, 19 HC):**
  - Random Forest BA: 0.7415, ROC-AUC: 0.7647.
  - Extra Trees BA: 0.7632, ROC-AUC: 0.7709.
- **Male Participants (N=42, 20 PD, 22 HC):**
  - Random Forest BA: 0.7955, ROC-AUC: 0.8068.
  - Extra Trees BA: 0.7977, ROC-AUC: 0.7932.

---

## 5. Scientific Limitations & Safe Use Policy

1. **Telephone Channel vs Consumer Audio:** The UAMS dataset was captured over landline telephone audio (8 kHz sampling). Consumer microphones (smartphones, laptops) introduce acoustic differences (different frequency response, environmental room reverberation, noise suppression algorithms).
2. **Quality Exclusions:** 3 files were excluded due to digital clipping; all 3 belonged to PD participants. This asymmetric exclusion is documented and tracked.
3. **No Clinical Use:** These results establish internal benchmark feasibility, NOT clinical efficacy. The application withholds disease probabilities from consumer microphone audio.
