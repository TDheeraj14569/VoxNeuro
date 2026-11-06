# Model validation protocol

This document summarizes the validation rules for VoxNeuro's research experiments. Detailed implementation and metrics are in [model evaluation methodology](methodology/model_evaluation.md).

## Separate experiments

1. **UAMS raw-audio Core39 experiment:** tests the project's own WAV preprocessing and acoustic features on one telephone-collected sustained-vowel recording per participant.
2. **UCI #470 pre-extracted feature experiment:** tests a separate table of existing acoustic predictors. It cannot test VoxNeuro's WAV-to-feature implementation.

No rows, predictions, or scores are combined across these experiments.

## Participant-level split and scoring

- Use participant ID as the grouping unit. Repetitions from one participant must never cross a train/test boundary.
- UAMS comparison: three repeated five-fold outer StratifiedGroupKFold evaluations. For each outer training partition, hyperparameters are selected by three-fold grouped inner validation using balanced accuracy.
- The six voice candidate families are L2 logistic regression, elastic-net logistic regression, linear SVM, RBF SVM, random forest, Extra Trees, and histogram gradient boosting.
- Age-only and age-plus-voice logistic comparators are separate analyses; age and sex are not inputs to voice-only models.
- All imputation and scaling are fit inside the corresponding training folds.
- Test metrics use participant-level out-of-fold scores. No threshold is tuned on outer test outcomes. The default model decision rule is exploratory only.

## Metrics and uncertainty

Report accuracy, precision, sensitivity, specificity, balanced accuracy, F1, ROC-AUC, trapezoidal PR-AUC, average precision, MCC, Brier score where probabilities are provided, and confusion counts.

Report repeat mean and standard deviation separately from the class-stratified participant bootstrap interval for the primary repeat. The bootstrap interval conditions on fitted outer-fold models; it is not a population or clinical confidence interval. Uncalibrated estimator probability outputs are not clinical risks.

## Interpretation gates

- The age imbalance and PD-only clipping exclusions must appear alongside any UAMS result.
- A higher score in internal CV cannot establish disease-specific voice information, a biomarker, or clinical benefit.
- External validation requires a compatible task and acquisition protocol, frozen features/model, participant-disjoint evaluation, and no tuning on external labels.
- The app must abstain from disease classification for new microphone audio until recording-domain compatibility has been supported by approved evidence and separately reviewed. A matching feature schema alone does not satisfy this gate.
- No diagnostic threshold, calibrated probability, prospective performance, or medical-device status is claimed.
