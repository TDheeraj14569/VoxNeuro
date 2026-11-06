# Known limitations and blockers

## Clinical and scientific

- VoxNeuro is not a disease detector, diagnostic device, screening instrument, or clinical decision-support product. It returns audio quality and technical features only.
- The clinical need remains a hypothesis. No stakeholder interview, observation, clinician endorsement, or patient feedback is claimed.
- The UAMS cohort has 81 source participants and 78 accepted feature rows. HC mean age is 47.73 and PD 67.04 years (standardized difference −1.61); the age-only baseline exceeds all tested voice-only balanced-accuracy means. An age-plus-voice comparison is also run on identical participant folds, but cannot establish an independent voice effect.
- All three quality exclusions are PD recordings. The class-dependent missingness may bias results.
- UAMS is telephone-collected; laptop/smartphone acquisition equivalence has not been established. Matching feature names or resampling rates do not prove domain compatibility.
- UCI is a separate pre-extracted feature-table benchmark. It is not external validation of the raw-audio extractor.
- The task is a sustained vowel; connected speech, language, articulation, intelligibility, prosody, longitudinal progression, and representative primary-care populations are untested.
- There is no external cohort, calibrated clinical probability, intended-use threshold, prospective study, Indian-population validation, clinical expert review, or regulatory opinion/authorization.

## Software and environment

- Python 3.12 is required by `pyproject.toml`; dependencies are locked. The source ZIP omits datasets and model/evaluation artifacts, so data-specific scripts require separately obtained licensed local data.
- The browser microphone control was rendered and tested in Streamlit AppTest, but real browser/OS permission and physical microphone capture have not been verified.
- UCI archive extraction relies on Windows `tar` support for RAR. An installation without that support must use a suitable extraction environment.
- The model checksum detects byte changes but does not authenticate the signer or make arbitrary joblib files safe.
- `.git` and trained artifacts are local only; there is no remote, release tag, or signed release in this package.

## Data and evidence

- The ZIP alone cannot reproduce reported cohort metrics because local datasets and generated outputs are omitted.
- The source cohort's capture hardware/channel details, task adherence, and clinical context are incompletely characterized.
- A technical signal-quality pass does not imply normal health, and extraction failure does not imply disease.
