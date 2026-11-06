# Dataset card

VoxNeuro contains two separate research dataset workflows. They are not merged and answer different software questions.

## UAMS sustained-vowel WAV cohort

| Field | Observed value |
|---|---|
| Source/version | Figshare article 23849127; DOI `10.6084/m9.figshare.23849127.v1`; CC BY 4.0. |
| Source snapshot | UAMS archive MD5 values checked against the source record on 2026-11-06. |
| Participants / recordings | 81 participants, one recording each; 40 PD and 41 healthy control. |
| Recording task/domain | Sustained `/a/`, telephone-collected voice messages. Device models and network channel are not fully characterized. |
| Original format/rate | WAVEX/FLOAT, mono, 8,000 Hz; duration observed 1.516–7.208 s. |
| Metadata | Workbook `Parselmouth` sheet; Sample ID, diagnosis label, age, and sex mapped to audio stem. 81/81 metadata and diagnosis matches in current audit. |
| Quality outcomes | 78/81 accepted for features. Three PD recordings exceeded the configured clipping-fraction threshold; only these explicit, reviewed exclusions are allowed. |
| Demographic imbalance | Mean age HC 47.73 years, PD 67.04; Mann–Whitney p=1.75×10⁻⁸; standardized mean difference −1.61. |
| Integrity | Current audit found no corrupt WAVs or duplicate waveform hashes. Archive checksums and expected counts are verified before staged extraction. |
| Primary use here | Engineering and exploratory participant-grouped internal model comparisons. |
| Limitations | Small case-control cohort; strong age confounding; three class-specific quality failures; telephone domain; one recording per person; no external test set; no claim of disease-specific voice signal or local-population validity. |

## UCI Parkinson's Disease Classification feature table

| Field | Observed value |
|---|---|
| Source/version | UCI Machine Learning Repository dataset 470; DOI `10.24432/C5MS4X`; CC BY 4.0. |
| Source snapshot | Archive SHA-256 and extracted CSV SHA-256 recorded in the local extraction receipt. |
| Participants / rows | 252 participants, 756 repeated recordings; three rows per participant. |
| Classes | 564 PD recordings / 192 control recordings. |
| Table | 752 acoustic predictor columns plus participant ID, gender, and class; no missing values observed. |
| Duplicate review | One exact duplicate row within the same participant; primary analysis retains it, and a separate deduplicated sensitivity analysis is recorded. |
| Age | No row-level age field; a row-level age-only comparator is unavailable. |
| Primary use here | Separate participant-grouped feature-table benchmark. |
| Limitations | Does not exercise VoxNeuro WAV decoding, preprocessing, or feature extraction and cannot validate laptop/browser microphone performance. |

## Data governance

Voice is potentially identifying biometric information even when filenames are pseudonymous. Raw audio, workbooks, participant-linked manifests/features, and model artifacts remain local and are excluded from Git and the source audit ZIP. Follow each source license and institutional privacy/ethics requirements. See the detailed [UAMS report](dataset/UAMS_DATASET_REPORT.md), [UCI report](dataset/UCI_DATASET_REPORT.md), and [privacy notes](PRIVACY.md).
