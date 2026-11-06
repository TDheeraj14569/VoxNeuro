# UCI Parkinson's Disease Classification report

**Official source:** UCI Machine Learning Repository dataset 470, DOI `10.24432/C5MS4X`, licensed CC BY 4.0. The repository describes 756 rows and 754 features. It reports data from 188 PD participants (107 men, 81 women; ages 33–87, mean 65.1 ± 10.9) and 64 controls (23 men, 41 women; ages 41–82, mean 61.1 ± 8.9). The task is sustained `/a/` recorded three times per subject with a 44.1 kHz microphone. [UCI dataset record](https://archive.ics.uci.edu/dataset/470/parkinson%2Bs%2Bdisease%2Bclassification).

The local source RAR archive is available from the official UCI ZIP download. The archive CSV starts with a feature-family description row, then a true header; inspection used that second row. Actual contents: 756 rows and 755 columns (`id`, `gender`, 752 acoustic feature columns, `class`); 252 participant IDs with exactly three rows each; 564 class-1 (PD) and 192 class-0 (healthy control) rows; zero missing values; one pair of exact duplicate rows within the same participant; no participant label or gender inconsistencies. The duplicate repeat is retained and all three repeats remain in the participant group. The 752 acoustic columns are the predictors; participant ID, gender, and class are excluded. `uci_inspection.json` stores the complete column list and structural summary.

The public CSV has per-row sex/gender coding but no per-participant age values, so the UCI experiment cannot calculate an age-only baseline or participant age subgroup performance. The repository's aggregate cohort age description is not suitable as a row-level predictor.

## Input contract and provenance

`configs/uci470_schema.json` pins the official dataset ID, DOI, source and download URLs, archive member, CSV header row, exact 755 ordered column names, and the ordered-header SHA-256 (`55311b3a9f947d378df1a92b83dd322aff98553c951048cba127dc55cb0a647b`). Inspection and evaluation reject changes to the header order or names, participant/repeat structure, class/gender encoding, and non-finite/non-numeric predictors. The schema manifest's own SHA-256 is recorded in the extraction and evaluation receipts.

The UCI dataset record does not publish an archive SHA-256. Therefore, a locally computed archive hash is only a fingerprint for detecting changes after download; it does not authenticate that archive as publisher-supplied. The exact code and source metadata are pinned, but no publisher checksum is claimed. The archive contains a RAR, so extraction needs a RAR-capable `tar` implementation (such as bsdtar/libarchive); `README.md` gives a preflight listing command and expected download location.

The UCI data are an independent *feature-based benchmark experiment only*. Its feature columns and collection protocol differ from the UAMS WAV pipeline, so it must not be joined to UAMS or used as a direct test of VoxNeuro's microphone feature extractor. Before reporting scores, identify the exact ID/label columns from the archive, verify all 252 participant IDs, check all repetitions and group overlap, and use participant-wise grouped evaluation. No clinical or Indian-population generalization is claimed.

