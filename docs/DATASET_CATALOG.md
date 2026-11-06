# VoxNeuro dataset catalog

## UAMS sustained-vowel recordings — raw audio

- Source: Figshare DOI [10.6084/m9.figshare.23849127.v1](https://doi.org/10.6084/m9.figshare.23849127.v1).
- License recorded by the project: CC BY 4.0. Cite the source and retain attribution when reusing it.
- Structure in this workspace: 81 mono WAVE extensible recordings in the HC_AH and PD_AH archives plus an age/sex workbook.
- Cohort: 41 healthy-control and 40 Parkinson's disease participants; one sustained /a/ recording per participant; reported telephone collection and 8 kHz sampling.
- Processing result: 78 recordings retained under the explicit, reviewed clipping policy; 37 PD and 41 HC. Three excluded recordings are all from the PD group.
- Use in VoxNeuro: raw-audio Core39 extraction and the primary nested grouped model comparison. This cohort is small, age-confounded, telephone-domain, and not independent external validation.
- Local data location: data/raw/uams and data/interim/uams. These participant recordings are excluded from source-review ZIPs.

See [the UAMS inspection report](dataset/UAMS_DATASET_REPORT.md) for the file-level audit and [the model card](reports/MODEL_CARD.md) for current measured model results.

## UCI Parkinson's speech feature table — pre-extracted predictors

- Source: UCI Machine Learning Repository, Parkinson's Disease Classification dataset #470. See [the UCI dataset report](dataset/UCI_DATASET_REPORT.md) for its exact source citation and schema.
- Local analysis: 756 recording rows, 252 participants, three repetitions per participant, 752 numeric predictors after metadata removal. One exact duplicate row was identified and evaluated separately in the recorded sensitivity analysis.
- Use in VoxNeuro: a separate participant-grouped feature-table benchmark.
- This is not raw audio. Its predictors are not mapped to the Core39 schema and are not used to infer from a WAV recording.
- Local data location: data/raw/uci and data/interim/uci. Dataset inputs and derived participant-level tables are excluded from source-review ZIPs.

## NeuroVoz — reviewed but not used

NeuroVoz is a Castilian Spanish speech corpus with an access process requiring a Data Use Agreement and a request. The project did not submit or obtain that access, so it was not downloaded or used and no external result is reported. See the [Scientific Data corpus paper](https://www.nature.com/articles/s41597-024-04186-z) and its stated access conditions.

## Synthetic quality-assurance audio

Generated synthetic signals are used only for software tests and browser demonstrations. They are never labeled as PD or HC, included in model fitting, or counted as clinical data.

## Source package boundary

The small source-audit ZIP contains code, tests, configuration, lockfiles, and documentation. It omits raw recordings, feature tables, trained joblib models, and experiment outputs. Reproducing numerical cohort results requires separately obtaining and verifying the licensed data.
