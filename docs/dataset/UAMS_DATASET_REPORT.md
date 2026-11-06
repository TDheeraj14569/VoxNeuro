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

## Mandatory bias and integrity checks

The cohort may have demographic imbalance; published reports describe age differences across PD/control groups. `audit_dataset.py` summarizes observed age/sex by label and computes a Mann–Whitney comparison and standardized mean difference when data are present. `evaluate_model.py` compares age-only, voice-only, and age-plus-voice logistic baselines on the same participant folds. The combined model is exploratory and does not estimate a causal or disease-specific voice contribution. Sex subgroup metrics require enough participants and must remain descriptive. Device/environment confounding cannot be separated when those fields were not recorded. These comparisons do not establish disease-specific biomarkers.

## Modeling boundary

The internal cohort experiment uses a participant-wise StratifiedGroupKFold and pipelines that fit imputation and scaling within folds. No independent external test cohort is available in this dataset. These small-sample internal results are exploratory. Telephone-collected audio is not assumed equivalent to new browser or laptop recordings; the Streamlit application withholds classification for user audio. No generalization to Indian populations is claimed.

## Local files

Place source files under `data/raw/uams/`. The inspection script expands WAV archives under `data/interim/uams/` and writes a privacy-safe metadata summary under this directory. Generated paths and participant IDs remain local in the manifest and are not committed.

