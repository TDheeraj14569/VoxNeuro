# Model evaluation methodology

## Scope

VoxNeuro has two separate experiments:

- **UAMS raw audio:** the primary experiment for the project's own 39-feature signal-processing pipeline.
- **UCI #470 pre-extracted feature table:** a separate benchmark that cannot be used as a raw-WAV model or as validation of VoxNeuro's audio processing.

Neither experiment establishes a clinical diagnosis or performance in a screening population. The approved prediction path abstains for new microphone recordings because recording-domain compatibility and clinical validity have not been established. Separately, when fresh local research artifacts pass provenance and input checks, the application may display an explicitly unvalidated exploratory candidate. That candidate does not change the approved-domain status and is not a clinical result.

## Cohorts and evaluation unit

- UAMS began with 81 participants (40 PD, 41 HC), one sustained /a/ telephone recording each. The documented quality policy excludes three clipped PD recordings; the processed table therefore contains 78 people (37 PD, 41 HC). Class-specific exclusion can bias results.
- UCI #470 contains 756 pre-extracted feature rows from 252 participants, three repetitions each, with 752 predictors after its metadata columns are removed. It remains a distinct feature-table experiment.
- Participant ID is the grouping unit. When a participant has repeated recordings, their rows are kept together in every train/test split. At scoring time, repeated-row decisions are averaged to one participant decision; the exploratory majority rule uses a 0.5 cutoff.

## UAMS repeated nested grouped cross-validation

The current UAMS model comparison uses three deterministic repetitions of five-fold outer StratifiedGroupKFold (seeds 2026, 2027, and 2028), with three-fold grouped inner cross-validation in each outer training set. Hyperparameters are selected only from inner-fold balanced accuracy. No outer-test labels or scores are used to tune a model or threshold.

The inner search compares:

- L2 logistic regression and elastic-net logistic regression.
- Linear and RBF support-vector machines.
- Random forest, Extra Trees, and histogram gradient boosting.
- An age-only logistic comparator and an age-plus-voice logistic comparator, when age is available.
- A prior dummy baseline.

The six voice-only candidates receive only the 39 acoustic features. Age and sex are excluded from voice-only inputs. Median imputation and standard scaling, where needed, are pipeline steps and are fitted only on the current training fold. The fixed logistic/forest/SVM grouped-CV run is retained as a historical descriptive baseline; the nested run is the current comparison for the tuned candidate families.

Out-of-fold scores are calculated at the participant level. The report gives the mean and standard deviation across the three repeat-level pooled estimates. It also gives a class-stratified bootstrap interval from the prespecified first-seed out-of-fold participants. That interval is conditional on the already-fitted outer-fold models and does not include model-fitting, cohort-selection, or external-validity uncertainty. It is not a clinical confidence interval.

## UCI benchmark

The UCI #470 workflow remains a separate deterministic five-fold participant-grouped evaluation of fixed model pipelines, with imputation/scaling contained in each fold. The duplicate-row sensitivity analysis is reported separately. The table does not supply participant-level age for an age-only comparator. These results cannot validate the UAMS raw-audio pipeline or ordinary microphone recordings.

## Metrics, thresholds, and probability outputs

The HTML report includes accuracy, precision, sensitivity, specificity, balanced accuracy, F1, ROC-AUC, trapezoidal PR-AUC, average precision, Matthews correlation coefficient, Brier score when a model exposes predict_proba, and TN/FP/FN/TP counts.

Scikit-learn average precision is not trapezoidal PR-AUC; both are reported under distinct names. Model predict_proba outputs are uncalibrated scores and must not be read as clinical probabilities. No calibration procedure or clinical operating threshold has been established. The default classifier decision rule is used; outer-fold threshold tuning is prohibited.

## Interpretation and limits

The UAMS cohort is small and shows a large age difference: HC mean age 47.73 (SD 14.33), PD 67.04 (SD 8.98), standardized mean difference -1.61, Mann-Whitney p=1.75e-8. Age-only performance is therefore an essential confounding comparator. Age-plus-voice results do not isolate a causal or independent voice contribution. The three PD-only quality exclusions add class-dependent missingness.

The highest internal voice-model score is not evidence of a biomarker, diagnostic accuracy, or a reason to choose that model for deployment. Logistic regression is retained as an interpretable research reference, not because it wins the nested comparison. There is no independent external test, prospective cohort, Indian-population evaluation, clinician feedback study, or clinically selected threshold.

NeuroVoz was not added: its repository requires a Data Use Agreement and an access request, which were not completed. No external result is claimed.

Full measured results and the distinction between model development and clinical use are in [MODEL_CARD.md](../reports/MODEL_CARD.md), [VERIFICATION_REPORT.md](../testing/VERIFICATION_REPORT.md), and the local generated HTML under artifacts/reports/model_evaluation/uams_nested.html.

Any future validated predictive claim requires a predefined intended use and analysis plan, independent participant cohorts recorded with a compatible protocol, transparent class-specific missingness, and independent clinical/statistical review. The distinct exploratory path is a software research output only; a user-declared device category does not prove acquisition compatibility, and an exploratory score must not be interpreted as an individual disease result.
