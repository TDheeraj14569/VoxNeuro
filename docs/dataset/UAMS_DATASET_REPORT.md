# UAMS Parkinson's Voice dataset report

**Source rechecked 2026-11-06:** Figshare article 23849127, DOI `10.6084/m9.figshare.23849127.v1`. The Figshare API record identifies CC BY 4.0 and lists `Demographics_age_sex.xlsx`, `PD_AH.zip`, and `HC_AH.zip`. [Dataset record](https://figshare.com/articles/dataset/Voice_Samples_for_Patients_with_Parkinson_s_Disease_and_Healthy_Controls/23849127), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The dataset description states that recordings are WAV files of prolonged vowel `/a/` collected using participants' telephones, and that the workbook Sample ID links to the WAVs. The downloaded files were locally inspected and excluded from Git. Actual findings:

- Both ZIP MD5 checksums match the Figshare API values; archives contain 40 PD and 41 HC WAVs.
- All 81 WAV headers decode: WAVEX/FLOAT, mono, 8,000 Hz. Duration is 1.516–7.208 seconds (median 3.102 seconds). No corrupt WAVs or duplicate waveform hashes were found.
- The workbook's `Parselmouth` sheet has 81 unique Sample IDs, and every Sample ID matched exactly one WAV after removing the UUID from each WAV filename. There are 81 unique participants and one recording each. Workbook labels match the archive class folders.
- Actual age: HC n=41, mean 47.73, SD 14.33, median 45, range 18–79; PD n=40, mean 67.04, SD 8.98, median 67.895, range 43.12–85.31. Mann–Whitney U=223, two-sided p=1.75×10⁻⁸; standardized mean difference (HC−PD) = −1.61. This is a major age confound, not a small baseline difference.
- Sex counts: HC 25 F / 16 M; PD 19 F / 21 M.
- Feature extraction passed quality checks for 78/81 recordings. Three PD recordings exceeded the current clipping-fraction threshold and were excluded before feature extraction; this class-specific failure can bias the already small cohort. See `data/processed/feature_extraction_report.csv` locally. Feature-extraction status is not the same as audio corruption.
- The workbook has other feature sheets (LPC/LAR/Cep/MFCC means and variances); they are not used in the primary WAV-derived model.

Generated `uams_inspection.json` records archive checksums, WAV counts, headers, durations, and sheet names. The local manifest verifies IDs and diagnosis labels before modeling.

## Provenance and permissions

The record license allows reuse with attribution. The voice recordings remain potentially identifiable biometric data: a UAMS publication notes that derived spectrograms were treated by institutional review/regulatory offices as voiceprints/PHI and not publicly shareable. Do not redistribute derived voiceprints or recordings, commit raw audio, publish voice clips, or assume anonymized filenames eliminate voice re-identification risk. Follow the source license and the project's privacy plan.

## Cohort and collection

- Intended sample count: 81; expected label counts: 40 PD and 41 control. These are source expectations, not a substitute for local inspection.
- Task: sustained/prolonged `/a/`.
- Device: participant telephone; exact telephone model, network path, microphone position, duration protocol, and environment may be absent.
- Demographic workbook: source indicates age, sex, and diagnosis label; exact values and column mapping must be taken from the local workbook and generated manifest/audit. Do not infer age, sex, or disease labels from file names.
- Participants and recordings: verify ID-to-WAV mapping and repeats before treating every WAV as one independent participant.

## Mandatory bias and integrity checks (Milestone 2 Completed Findings)

The cohort has severe demographic imbalance: HC mean age 47.73 ± 14.33 years vs PD 67.04 ± 8.98 years (standardized mean difference -1.61, Mann–Whitney p=1.75×10⁻⁸). Milestone 2 completed a rigorous empirical bias audit (`docs/reports/M2_BIAS_AUDIT_REPORT.md`):
1. **Age-Only Superiority:** Age-only logistic regression achieves **83.89%** balanced accuracy, exceeding all voice-only models (linear SVM: 70.54%, logistic: 73.88%).
2. **Uncertain Incremental Value:** In paired testing on the primary seed, adding voice to age yields $\Delta\text{BA} = -0.0758$ (95% CI [$-0.1842, +0.0284$], supplementary McNemar exact $p = 0.2632$; repeated-CV $\Delta = -0.0681$); adding voice to age and sex yields $\Delta\text{BA} = -0.0745$ (95% CI [$-0.1843, +0.0310$], supplementary McNemar exact $p = 0.2632$; repeated-CV $\Delta = -0.0762$). The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain.
3. **Caliper Matching Exhaustion:** Enforcing a standard 0.2 SD age caliper (2.44 years) with exact sex matching retains only **5 pairs (10 participants)** &mdash; an 87.2% participant attrition rate. Cross-validation modeling on the matched subcohort is formally **NOT ESTIMABLE** per SAP Rule 5.
4. **Asymmetric Attrition:** Quality exclusions (excessive clipping >0.5%) occurred exclusively in the PD cohort (3/40 [7.5%] vs 0/41 HC; Fisher exact p = 0.1158).
5. **Prospective Protocol:** Phase 8 establishes a formal prospective validation protocol (`docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md`) requiring N=240 participants (1:1 age- and sex-matched) under calibrated sound-booth conditions.

## Modeling boundary

The internal cohort experiment uses participant-wise StratifiedGroupKFold evaluation and pipelines that fit imputation/scaling within folds. No independent external test cohort is available in this dataset. These small-sample internal results are exploratory. Telephone-collected audio is not assumed equivalent to new browser or laptop recordings. The approved inference path remains disabled; a separate app path may display only an explicitly unvalidated research candidate when fresh local provenance and input/OOD checks pass. A user-declared device category is not evidence of domain compatibility. No generalization to Indian populations is claimed.

## Local files

Place source files under `data/raw/uams/`. The inspection script expands WAV archives under `data/interim/uams/` and writes a privacy-safe metadata summary under this directory. Generated paths and participant IDs remain local in the manifest and are not committed.

