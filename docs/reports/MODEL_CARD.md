# VoxNeuro experimental model card

**Status: research only.** No clinical validation or authorization has occurred. VoxNeuro's application does not classify a new microphone recording. The numeric results below are measured internal cross-validation results, not diagnostic accuracy.

## Intended use and users

This model is for software and signal-processing researchers auditing sustained-vowel acoustic measurements from the UAMS development cohort. It is not for Parkinson screening, diagnosis, rule-out, monitoring, prognosis, treatment selection, or patient management.

## Data and input

- Source: UAMS voice samples, Figshare DOI [10.6084/m9.figshare.23849127.v1](https://doi.org/10.6084/m9.figshare.23849127.v1), CC BY 4.0; see [UAMS dataset report](../dataset/UAMS_DATASET_REPORT.md).
- Original cohort: 81 people (41 healthy controls, 40 PD), one sustained /a/ telephone recording each, reported at 8 kHz.
- Analysis cohort: 78 people (41 HC, 37 PD). Three clipped recordings, all from the PD group, were excluded under the documented reviewed policy. This class-specific missingness can bias the results.
- Voice input: 39 Core39 measurements in schema voxneuro.voice.v3, extracted with Praat/Parselmouth and Librosa. The feature schema and configuration fingerprints are stored with generated data and the model bundle. Age and sex are excluded from voice-only models.
- UCI #470 is a separate pre-extracted feature-table benchmark. Its features are not interchangeable with Core39 and are never fed from raw WAV recordings.

## UAMS validation design

The current model comparison uses repeated nested participant-grouped cross-validation: five outer folds, three inner folds, and three prespecified repeats (seeds 2026–2028). The inner folds choose hyperparameters by balanced accuracy. Imputation and scaling are fit only within the corresponding training folds. Outer-fold participants are not used for that fold's tuning.

The voice-only comparison includes L2 and elastic-net logistic regression, linear and RBF SVM, random forest, Extra Trees, and histogram gradient boosting. It also includes a prior dummy baseline and age-only / age-plus-voice logistic comparators. Voice-only models receive the 39 acoustic predictors only.

The table reports mean ± standard deviation across the three repeated participant-level out-of-fold estimates. The BA interval is a 95% class-stratified participant bootstrap over the primary-seed OOF predictions; it is conditional on the already fitted outer-fold models and is not an external-validity or clinical confidence interval. Sensitivity, specificity, precision, and the other measures use the default model decision rule. No clinical threshold was selected. Probability outputs, where available, are uncalibrated.

## Measured UAMS results

| Candidate | Accuracy | Precision | Sensitivity | Specificity | Balanced accuracy | Primary-seed BA bootstrap 95% interval | ROC-AUC | Trapezoidal PR-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Prior dummy | 0.526 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 1.000 ± 0.000 | 0.500 ± 0.000 | 0.500–0.500 | 0.474 ± 0.000 | 0.506 ± 0.000 | 0.461 ± 0.000 |
| L2 logistic | 0.739 ± 0.007 | 0.723 ± 0.011 | 0.730 ± 0.000 | 0.748 ± 0.014 | 0.739 ± 0.007 | 0.632–0.821 | 0.771 ± 0.006 | 0.707 ± 0.023 | 0.717 ± 0.022 |
| Elastic-net logistic | 0.735 ± 0.030 | 0.717 ± 0.035 | 0.730 ± 0.027 | 0.740 ± 0.037 | 0.735 ± 0.029 | 0.616–0.821 | 0.776 ± 0.018 | 0.747 ± 0.018 | 0.753 ± 0.017 |
| Linear SVM | 0.705 ± 0.022 | 0.682 ± 0.035 | 0.712 ± 0.016 | 0.699 ± 0.051 | 0.705 ± 0.021 | 0.591–0.793 | 0.756 ± 0.014 | 0.704 ± 0.019 | 0.715 ± 0.015 |
| RBF SVM | 0.739 ± 0.007 | 0.705 ± 0.014 | 0.775 ± 0.016 | 0.707 ± 0.024 | 0.741 ± 0.007 | 0.641–0.835 | 0.766 ± 0.014 | 0.695 ± 0.020 | 0.707 ± 0.021 |
| Random forest | 0.752 ± 0.015 | 0.709 ± 0.012 | 0.811 ± 0.027 | 0.699 ± 0.014 | 0.755 ± 0.015 | 0.671–0.862 | 0.786 ± 0.017 | 0.701 ± 0.062 | 0.715 ± 0.055 |
| Extra Trees | 0.761 ± 0.020 | 0.727 ± 0.017 | 0.793 ± 0.041 | 0.732 ± 0.024 | **0.762 ± 0.020** | 0.664–0.850 | 0.784 ± 0.014 | 0.713 ± 0.067 | 0.724 ± 0.060 |
| Histogram gradient boosting | 0.705 ± 0.013 | 0.667 ± 0.016 | 0.757 ± 0.000 | 0.659 ± 0.024 | 0.708 ± 0.012 | 0.606–0.812 | 0.739 ± 0.027 | 0.697 ± 0.069 | 0.705 ± 0.065 |
| Age-only logistic comparator | **0.838 ± 0.007** | **0.807 ± 0.012** | **0.865 ± 0.000** | **0.813 ± 0.014** | **0.839 ± 0.007** | 0.754–0.911 | **0.849 ± 0.013** | **0.793 ± 0.015** | **0.799 ± 0.014** |
| Age-plus-voice logistic comparator | 0.769 ± 0.013 | 0.736 ± 0.025 | 0.802 ± 0.016 | 0.740 ± 0.037 | 0.771 ± 0.012 | 0.658–0.851 | 0.817 ± 0.024 | 0.777 ± 0.021 | 0.782 ± 0.021 |

These are small-cohort internal estimates. Extra Trees had the highest mean balanced accuracy among voice-only candidates, but its primary-seed interval is wide. The age-only comparator was higher (0.839 versus 0.762 BA); age-plus-voice did not exceed age-only BA or ROC-AUC. This cohort cannot establish that voice contributes disease-specific information independently of age. Average precision is distinct from trapezoidal PR-AUC.

## Separate UCI feature-table benchmark

The current fixed-pipeline, five-fold participant-grouped UCI run used 756 rows, 252 participants, and 752 acoustic predictors. One exact duplicate row was assessed in a separate sensitivity run. These figures do not evaluate VoxNeuro's WAV preprocessing or microphone compatibility.

| Candidate | Balanced accuracy | Sensitivity | Specificity | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|
| Logistic regression | 0.766 ± 0.043 | 0.878 ± 0.014 | 0.655 ± 0.093 | 0.826 ± 0.036 | 0.924 ± 0.032 |
| Random forest | 0.727 ± 0.056 | 0.910 ± 0.031 | 0.545 ± 0.135 | 0.848 ± 0.043 | 0.942 ± 0.019 |
| RBF SVM | 0.715 ± 0.052 | 0.883 ± 0.015 | 0.547 ± 0.111 | 0.827 ± 0.039 | 0.929 ± 0.022 |

The class distribution is imbalanced and sensitivity is higher than specificity. These results are a separate benchmark and must not be combined with the UAMS results.

## Bundled reference model

The saved UAMS artifact is an L2 logistic regression reference whose regularization strength is tuned by participant-grouped cross-validation and then refit on all 78 development participants. It is retained for interpretability and reproducibility, not because it is the top-scoring voice model. Its performance estimate comes from the nested cross-validation table above, not from its final all-data fit.

The bundle records the data checksum, schema/configuration fingerprints, source fingerprint, software versions, nested evaluation receipt, training settings, and timestamp. Its SHA-256 sidecar detects artifact changes but is not a digital signature; only internally generated trusted bundles may be loaded.

## Limitations and safeguards

- The UAMS healthy-control mean age is 47.73 years (SD 14.33); the PD mean is 67.04 (SD 8.98), standardized mean difference -1.61, Mann–Whitney p=1.75e-8.
- All three quality exclusions are PD recordings. This class-dependent exclusion can bias the training cohort.
- The development dataset is small, retrospective, telephone-collected, and limited to sustained /a/. Language, device, channel, room, task, medication, fatigue, age, and other conditions can affect voice.
- Compatibility with laptop, smartphone, browser-microphone, or other recording domains is unverified. The application withholds disease classification for new recordings.
- No calibrated clinical probability, decision threshold, external test, prospective cohort, Indian-population evaluation, clinician feedback, ethics review, or regulatory authorization has been established.
- NeuroVoz was not used because its access process requires a Data Use Agreement and an access request that were not completed.
- Voice is potentially identifying biometric data. Recordings are held in application memory and are not saved by default.

Do not use this model to make or change clinical decisions. A generated nested-results report is available locally at artifacts/reports/model_evaluation/uams_nested.html; reproducibility details are in [model evaluation methodology](../methodology/model_evaluation.md).
