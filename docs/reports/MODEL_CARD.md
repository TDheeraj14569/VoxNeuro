# VoxNeuro UAMS research-model card

**Status: experimental research reference. Not clinically validated, not a medical device, and not approved for diagnosis, screening, rule-out, monitoring, prognosis, or treatment decisions.** Current UAMS metrics were generated locally from the licensed research data on 2026-11-13 and were not regenerated from this source-only release because participant data and model artifacts are excluded.

## Intended research use

The model is a reproducible software reference for exploring Core39 acoustic measurements from sustained `/a/` recordings. The app may show a clearly labeled exploratory candidate only when a locally generated artifact and current provenance/evaluation receipts pass all checks. This candidate is a classifier output, not an individual medical result. The validated-domain prediction gate remains disabled.

## Data and features

- Dataset: UAMS voice samples, Figshare DOI [10.6084/m9.figshare.23849127.v1](https://doi.org/10.6084/m9.figshare.23849127.v1), CC BY 4.0.
- Initial cohort: 81 people (41 HC, 40 PD), one telephone-collected sustained vowel each, reported at 8 kHz.
- Model cohort: 78 people (41 HC, 37 PD). Three PD recordings failed the reviewed clipping policy. This class-specific exclusion can bias results.
- Voice-only inputs: 39 ordered Core39 measurements in `voxneuro.voice.v3`. Age and sex are not voice-model inputs. The bundle pins feature schema/configuration and preprocessing fingerprints.
- UCI #470 is a separate pre-extracted feature benchmark. It is not used as raw audio, is not mixed with the UAMS data, and does not validate the WAV pipeline.

## Evaluation design

The current UAMS comparison used 5-fold participant-grouped outer cross-validation, 3-fold grouped inner tuning, and three prespecified repeats (seeds 2026–2028). All transforms and hyperparameter selection were restricted to the corresponding outer-training partitions. Reported values are means and standard deviations across three repeat-level out-of-fold estimates. These are internal estimates from a small retrospective cohort; they are not external-validation or clinical performance estimates. No clinical threshold was selected and no probability calibration is used for the app's exploratory candidate.

## Current locally measured UAMS results

| Candidate | Balanced accuracy (mean ± repeat SD) | Precision | Sensitivity | Specificity | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|
| Voice-only L2 logistic | 0.739 ± 0.007 | 0.723 | 0.730 | 0.748 | 0.770 | 0.717 |
| Voice-only Extra Trees | 0.766 ± 0.008 | 0.734 | 0.793 | 0.740 | 0.785 | 0.727 |
| Age-only logistic comparator | 0.839 ± 0.007 | 0.807 | 0.865 | 0.813 | 0.849 | 0.799 |
| Age + voice logistic comparator | 0.771 ± 0.012 | 0.736 | 0.802 | 0.740 | 0.814 | 0.784 |

The age-only comparator scores higher than the voice-only candidates. Adding voice to age did not improve this cohort's internal balanced accuracy over age alone. The marked age imbalance (HC mean 47.73 years; PD mean 67.04 years; SMD −1.61) and PD-only quality exclusions prevent a disease-specific interpretation. These results do not establish a useful voice biomarker or individual-level disease accuracy.

In the primary-seed paired analysis, adding voice to age changed balanced accuracy by -0.0758 (95% participant-bootstrap interval [-0.1842, +0.0284]); adding voice to age plus sex changed it by -0.0745 (95% interval [-0.1843, +0.0310]). Across the repeated nested evaluation, the corresponding mean differences were -0.0681 and -0.0762. Confidence intervals include zero and positive effects; the true incremental contribution remains uncertain, and this cohort does not establish a supported positive benefit from the voice features beyond demographic comparators.

The bundled local reference is an L2 logistic model retained for transparent, reproducible behavior, not because it was the highest-scoring candidate. Its default `decision_function` output is an **uncalibrated score** with a fixed research threshold of 0.0. It is not a probability. The final refit uses the development cohort, so its individual scores are not held-out estimates. The nested metrics above come from held-out participants within cross-validation, not from scoring the final all-data artifact.

## What the app displays

- Approved prediction: unavailable. `allow_user_microphone_inference` is false and the trusted domain-validation hash allowlist is empty.
- Exploratory candidate: a distinct unvalidated result is possible only from a local current bundle after data/evaluation/code/schema provenance, input quality/task, device category, completeness, and training-derived OOD checks pass. Capture origin is separate from the user-declared acquisition category. A self-report does not prove the actual hardware or domain.
- Abstention: if any required gate fails, the app gives a specific reason and retains available acoustic analysis and reports.

The OOD reference is derived only from the model's training feature table. It does not establish that a device domain is validated or that a score is clinically meaningful. The local source archive omits datasets, trained binaries, and generated receipts; a clean checkout therefore cannot produce an exploratory candidate until the documented local workflow has been completed.

## Separate UCI feature-table benchmark

The local UCI #470 grouped benchmark (252 participants, 756 repeated rows, 752 acoustic predictors) reported balanced accuracy of 0.766 ± 0.043 for logistic regression, 0.727 ± 0.056 for random forest, and 0.715 ± 0.052 for RBF SVM. It is a separate experiment using pre-extracted features and must not be presented as confirmation of the Core39 raw-audio workflow.

## Limitations and safeguards

- Small, retrospective UAMS cohort; no independent external cohort, prospective study, or representative clinical population.
- Strong age imbalance and three PD-only clipping exclusions may distort apparent performance.
- Telephone recording compatibility with browser, laptop, smartphone, headset, other rooms, languages, or tasks is not established.
- Sustained vowels do not represent connected speech or all clinically relevant speech behavior.
- Scores are uncalibrated and no clinical decision threshold, sensitivity target, or negative predictive value has been established.
- No clinical expert/user validation, ethics approval for a prospective study, Indian-population validation, or regulatory authorization is claimed.
- Voice is potentially identifying data. App audio stays in memory by default; users should handle downloaded reports carefully.

Do not use this model or an exploratory candidate to make or change clinical decisions. See [evaluation methodology](../methodology/model_evaluation.md), [validation protocol](../VALIDATION_PROTOCOL.md), and [known limitations](../KNOWN_LIMITATIONS.md).
