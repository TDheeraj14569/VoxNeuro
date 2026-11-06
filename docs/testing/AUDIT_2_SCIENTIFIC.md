# Verification Pass 2: signal processing and exploratory modeling

**Status: reproducible software and exploratory analysis only. Clinical validation has not been conducted. Current local rerun: 2026-11-06.**

## Signal and schema

- The prototype analyzes a sustained `/a/`; it does not measure connected speech, articulation, intelligibility, speech rhythm, calibrated sound pressure, or task-level prosody.
- Audio validation covers empty and malformed input, non-finite samples, short/long duration, low level, clipping, unvoiced input, and stereo phase cancellation. The configured mono policy is enforced.
- The current `voxneuro.voice.v3` schema contains 39 measures: Praat F0 summaries, local jitter/shimmer ratios, mean HNR, 13 Librosa MFCC means and SDs with zero-based indices 0–12, and four spectral summaries. MFCC units and minimum frame validity are defined explicitly; the extractor fixes the count at 13 and rejects multichannel input. A 3,800 Hz upper band is applied before spectral summaries to align with the source cohort's 8 kHz Nyquist limit. This does not establish device equivalence.
- Missing jitter/shimmer remain missing. Undefined values may be imputed only inside the training pipeline's folds or when explicitly allowed in a research inference bundle.

## Dataset and exclusions

- UAMS Figshare archives passed the published MD5 and expected-file-count checks. All 81 mono WAVEX/FLOAT files decode at 8 kHz; the 41 HC and 40 PD workbook labels and IDs match their audio folders. The manifest audit reported no issues, duplicate waveform hashes, or mismatches.
- Quality screening accepted 78/81 files. The three excluded recordings (`uams-045` to `uams-047`) are all PD recordings that exceed the configured clipping fraction. They are named in `configs/reviewed_exclusions.yaml`; feature extraction returns a nonzero status on partial failure unless the explicit reviewed-exclusion flag is supplied and every failure matches its reviewed reason.
- UCI includes 756 rows from 252 participants with three recordings each. The source has one exact duplicate pair within one participant; participant-grouped splitting keeps repeats and the duplicate in the same fold. This is a separate pre-extracted feature-table benchmark, not validation of the raw-audio pipeline.

## Exploratory grouped metrics

Five-fold participant-wise UAMS balanced accuracy (mean ± fold SD): age-only logistic 0.825 ± 0.074; age-plus-voice logistic 0.784 ± 0.145; voice logistic 0.659 ± 0.134; random forest 0.758 ± 0.094; RBF SVM 0.760 ± 0.066; dummy 0.500 ± 0.000. The age-plus-voice baseline did not exceed age-only balanced accuracy or ROC-AUC; this comparison is exploratory and cannot establish an incremental voice effect. Corresponding voice ROC-AUC values are 0.723, 0.793, and 0.784. These are internal small-cohort estimates, not clinical performance claims.

HC age averaged 47.73 ± 14.33 years versus 67.04 ± 8.98 for PD (Mann–Whitney p=1.75×10⁻⁸; standardized difference −1.61). The age-only comparator outperformed all voice-only candidates. Class-dependent clipping exclusions may also bias these results. Voice-only metrics do not establish a disease-specific signal.

Descriptive sex-stratified balanced accuracy was 0.681/0.633 for logistic (F/M), 0.717/0.832 for random forest, and 0.729/0.801 for SVM. These small subgroups do not support fairness conclusions.

UCI grouped participant-level balanced accuracy was 0.766 ± 0.043 for logistic, 0.727 ± 0.056 for random forest, 0.715 ± 0.052 for SVM, and 0.500 for dummy. After removal of its one within-participant exact duplicate, the respective means were 0.749, 0.725, and 0.723. Age is not available for a row-level comparator in that feature table; UCI results must remain separate from UAMS.

The largest held-out random-forest permutation importance was `mfcc_10_sd`, with mean balanced-accuracy decrease 0.045 (fold SD 0.046; positive in 4/5 folds). This is an unstable model association, not a biomarker or causal explanation.

## Clinical interpretation

No independent external cohort, calibration, intended-use threshold, prevalence-representative screening evaluation, clinician feedback, prospective study, ethics review, or Indian-population validation is available. The model is kept out of the app's new-recording workflow because telephone-to-microphone compatibility has not been established. No diagnosis, prognosis, monitoring, or treatment claim is supported.
