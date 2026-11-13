# VoxNeuro model evaluation report

**Status: research benchmark only. Not clinical validation.** This document summarizes the latest locally generated evaluation snapshot (2026-11-13). Raw datasets, participant-level tables, trained artifacts, and receipts are excluded from the source ZIP, so this release alone cannot reproduce the reported scores.

## UAMS raw-audio Core39 experiment

The development cohort contains 81 participants (41 healthy controls, 40 PD) with one sustained-vowel telephone recording each. Three PD recordings failed the reviewed clipping policy, leaving 78 participants for modeling (41 HC/37 PD). The complete repeated nested run used participant-grouped outer folds, grouped inner-fold tuning, and three prespecified repeats. Preprocessing and tuning were fit only inside each outer training set.

| Candidate | Balanced accuracy, mean ± repeat SD | Precision | Sensitivity | Specificity | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|
| Dummy baseline | 0.500 ± 0.000 | 0.000 | 0.000 | 1.000 | 0.474 | 0.461 |
| Voice-only L2 logistic | 0.739 ± 0.007 | 0.723 | 0.730 | 0.748 | 0.770 | 0.717 |
| Voice-only Extra Trees | 0.766 ± 0.008 | 0.734 | 0.793 | 0.740 | 0.785 | 0.727 |
| Age-only logistic comparator | **0.839 ± 0.007** | 0.807 | 0.865 | 0.813 | **0.849** | 0.799 |
| Age + voice logistic comparator | 0.771 ± 0.012 | 0.736 | 0.802 | 0.740 | 0.814 | 0.784 |

The compact table includes only candidates for which all displayed metrics were read from the current generated summary. The full comparison is available in the locally generated nested report and CSV receipt, not in the source-only archive.

The strongest current voice-only mean BA is Extra Trees (0.766), while the age-only comparator is higher (0.839). Age plus voice does not improve on age alone in this cohort. The cohort is strongly age-confounded (SMD −1.61) and all three quality exclusions are PD recordings. These results do not establish a disease-specific voice signal. Model-selection and interpretation limits are detailed in the [model card](MODEL_CARD.md).

The app's local L2 logistic research reference is selected for interpretability and reproducibility, not because it has the highest observed voice-only score. Its final artifact uses a decision score and fixed 0.0 threshold, without calibration. That app score is not a probability, and final-refit predictions are not held-out performance.

## UCI #470 feature-table benchmark

The separate participant-grouped UCI experiment uses 252 participants with three repeated pre-extracted-feature records each. It does not validate VoxNeuro's WAV preprocessing, Core39 extraction, or microphone/device compatibility. Its latest local benchmark is summarized in the model card. Never merge these features or scores with the UAMS raw-audio experiment.

## Interpretation

- Internal cross-validation is not external, prospective, or clinical validation.
- No clinically selected threshold, calibrated disease probability, population representative performance, or treatment utility has been established.
- Device categories in an app session are user-declared only. The exploratory result path is kept separate from the approved inference gate, which remains disabled.
- The source-only archive excludes the data, evaluation receipts, and model. The reported local metrics should be treated as documented local-run evidence until another reviewer independently reproduces them from authorized data.

See [model evaluation methodology](../methodology/model_evaluation.md), [validation protocol](../VALIDATION_PROTOCOL.md), and [known limitations](../KNOWN_LIMITATIONS.md).
