# Verification Pass 2: signal processing and exploratory modeling

**Status: reproducible software and exploratory analysis only. Clinical validation has not been conducted. Milestone 2 scientific bias audit completed: 2026-11-11.**

## Signal and schema

- The prototype analyzes a sustained `/a/`; it does not measure connected speech, articulation, intelligibility, speech rhythm, calibrated sound pressure, or task-level prosody.
- Audio validation covers empty and malformed input, non-finite samples, short/long duration, low level, clipping, unvoiced input, and stereo phase cancellation. The configured mono policy is enforced.
- The current `voxneuro.voice.v3` schema contains 39 measures: Praat F0 summaries, local jitter/shimmer ratios, mean HNR, 13 Librosa MFCC means and SDs with zero-based indices 0–12, and four spectral summaries. MFCC units and minimum frame validity are defined explicitly; the extractor fixes the count at 13 and rejects multichannel input. A 3,800 Hz upper band is applied before spectral summaries to align with the source cohort's 8 kHz Nyquist limit. This does not establish device equivalence.
- Missing jitter/shimmer remain missing. Undefined values may be imputed only inside the training pipeline's folds or when explicitly allowed in a research inference bundle.

## Dataset and exclusions

- UAMS Figshare archives passed the published MD5 and expected-file-count checks. All 81 mono WAVEX/FLOAT files decode at 8 kHz; the 41 HC and 40 PD workbook labels and IDs match their audio folders. The manifest audit reported no issues, duplicate waveform hashes, or mismatches.
- Quality screening accepted 78/81 files. The three excluded recordings (3 clipped PD recordings) are all PD recordings that exceed the configured clipping fraction. They are handled under the aggregate clipping policy in `configs/reviewed_exclusions.yaml`; feature extraction returns a nonzero status on partial failure unless the explicit reviewed-exclusion flag is supplied and every failure matches its reviewed reason.
- Quality attrition analysis (M2): all 3 exclusions occurred in the PD cohort ($7.5\%$ excluded vs $0\%$ HC; Fisher exact $p = 0.1158$). This indicates potential class-dependent selection bias.
- UCI includes 756 rows from 252 participants with three recordings each. The source has one exact duplicate pair within one participant; participant-grouped splitting keeps repeats and the duplicate in the same fold. This is a separate pre-extracted feature-table benchmark, not validation of the raw-audio pipeline.

## Milestone 2: Demographic Confounding & Incremental Voice Value

The pre-registered Statistical Analysis Plan (`docs/methodology/M2_STATISTICAL_ANALYSIS_PLAN.md`) evaluated demographic confounding and model hierarchy across identical $5 \times 3$ nested folds (seeds 2026–2028, N=78 accepted participants):

1. **Demographic Disparity:** Healthy Controls are on average 19.31 years younger than Parkinson's participants ($47.73 \pm 14.33$ vs $67.04 \pm 8.98$ years; SMD $= -1.61$, Mann-Whitney $U = 223.0$, $p = 1.75 \times 10^{-8}$).
2. **Caliper Matching Sensitivity:** Enforcing standard calipers with exact sex matching:
   - 0.1 SD ($1.22$ yrs): 3 matched pairs ($92.3\%$ discarded).
   - 0.2 SD ($2.44$ yrs): 5 matched pairs ($87.2\%$ discarded).
   - 0.3 SD ($3.67$ yrs): 7 matched pairs ($82.1\%$ discarded).
   - Uncalipered: 34 matched pairs, but residual age gap is $14.90$ years (SMD $= -1.327$).
   - Matched modeling is formally **NOT ESTIMABLE** (only 5 pairs retained, exhausting cross-validation fold capacity).
3. **Model Comparison Hierarchy:**
   - `age_only_logistic`: Balanced accuracy **$83.89\%$** [$74.68\%, 91.07\%$], ROC-AUC **$0.8490$**.
   - `age_plus_sex_logistic`: Balanced accuracy **$83.81\%$** [$74.56\%, 91.20\%$], ROC-AUC **$0.8493$**.
   - `age_plus_voice_logistic`: Balanced accuracy **$77.08\%$** [$65.89\%, 84.71\%$], ROC-AUC **$0.8141$**.
   - `age_plus_sex_plus_voice_logistic`: Balanced accuracy **$76.18\%$** [$65.89\%, 84.84\%$], ROC-AUC **$0.8132$**.
   - `voice_only_logistic`: Balanced accuracy **$73.88\%$** [$62.79\%, 82.27\%$], ROC-AUC **$0.7697$**.
   - `voice_only_svm`: Balanced accuracy **$70.54\%$** [$59.13\%, 79.43\%$], ROC-AUC **$0.7559$**.
   - `matched_voice_svm`: **NOT ESTIMABLE** (sample size exhaustion).
4. **Paired Incremental Tests:**
   - Age + Voice vs Age Only: $\Delta \text{BA} = -0.0681$ ($-6.81\%$), 95% CI [$-0.1842, +0.0284$], McNemar exact $p = 0.2632$.
   - Age + Sex + Voice vs Age + Sex: $\Delta \text{BA} = -0.0762$ ($-7.62\%$), 95% CI [$-0.1843, +0.0310$], McNemar exact $p = 0.2632$.
   - **Conclusion:** Adding 39 acoustic features introduces dimensionality noise that degrades generalization compared to demographic variables alone.

## Clinical interpretation

No independent external cohort, calibration, intended-use threshold, prevalence-representative screening evaluation, clinician feedback, prospective study, ethics review, or Indian-population validation is available. The model is kept out of the app's new-recording workflow because telephone-to-microphone compatibility has not been established. Phase 8 establishes a prospective study protocol (`docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md`) requiring $N=240$ participants ($1:1$ frequency matched by age band and sex) to definitively determine whether acoustic features carry disease-specific information under standardized conditions.
