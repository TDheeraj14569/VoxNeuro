# VoxNeuro project report

**Project status: complete software prototype; research-only evidence.** This report summarizes the implementation and observed verification. It does not claim clinical validity, medical-device status, or regulatory authorization.

## Objective and boundary

VoxNeuro is a local Python/Streamlit prototype for sustained `/a/` WAV quality assessment, visualization, acoustic feature extraction, and reporting. It supports Parkinson voice research only. It does not diagnose, screen, rule out disease, or recommend treatment. With a fresh locally generated model and matching evaluation/provenance receipts, it can display a separately labeled exploratory candidate after input checks pass. This candidate is unvalidated, is not a clinical result, and must not guide care. The approved prediction path remains disabled.

## Project structure

```text
VoxNeuro/
  app.py, pyproject.toml, uv.lock, requirements-lock.txt, README.md
  configs/ and .streamlit/
  data/raw, data/interim, data/processed/ (ignored local data)
  docs/architecture, biodesign, clinical_validation, dataset, limitations,
       methodology, regulatory, reports, research, testing
  scripts/ (inspection, manifest, audit, extraction, train, evaluate, verify)
  src/voxneuro/ (audio, features, dataset, modeling, reporting, visualization)
  tests/fixtures, tests/unit, tests/integration
```

## Implementation

- Dependency-locked Python 3.12 project using `uv`; Windows x64 was the observed environment. Exact dependency versions are in `uv.lock` and the local `requirements-lock.txt`.
- Modular audio decoding, WAV/WAVEX validation, digital quality checks, deterministic DC correction/trim/resampling, signal plots, versioned 39-feature Praat/Librosa schema, report generation, data manifest/audit, grouped models, and serialized research bundle. The current source feature contract is `voxneuro.voice.v3`; its MFCC indices are zero-based and its spectral band is capped at 3,800 Hz. The current UAMS and UCI grouped metrics and model bundle were regenerated under this v3 feature contract and current source/configuration fingerprints.
- Seven Streamlit sections cover overview, voice assessment, signal analysis, features, grouped research results, reports, and method/privacy. Browser microphone control uses the built-in browser input. The server binds only to `127.0.0.1` by default. All YAML configuration files are checked for required/unknown keys, types, and supported ranges at app startup. Audio/reports are not saved by default. Capture origin and user-declared acquisition category are distinct; a user-declared device does not verify the hardware or domain. The result panel distinguishes an approved result (currently unavailable), an unvalidated exploratory candidate, and abstention with a specific reason.
- The Overview page contains a clearly marked decorative local Three.js acoustic ribbon. Signal analysis renders the actual processed waveform and a bounded STFT surface in a self-contained local WebGL iframe, with orbit, zoom, reset, reduced-motion handling, WebGL-loss fallback and 2D plots. The waveform display preserves local extrema while downsampling; the spectrogram exposes time, frequency and dB re 1.0 axes. No CDN or remote visualization service is used, and visual payloads do not enter the feature/model pipeline.
- Clinical development deliverables include the Biodesign need statement and observation/interview templates, literature and solution review, clinical workflow, risk/privacy plan, clinical data dictionary, validation/expert-feedback plans, and an India regulatory source review.

## Dataset findings

- UAMS Figshare article 23849127, DOI `10.6084/m9.figshare.23849127.v1`, CC BY 4.0. Downloaded ZIP hashes matched source API. Inspection found 81 mono WAVEX/FLOAT samples at 8 kHz, 41 HC/40 PD, one recording per participant. All workbook IDs and labels matched; no corrupt samples or duplicate waveforms. Three PD recordings failed the clipping threshold, leaving 78 for modeling.
- The UAMS age imbalance is large: HC mean 47.73 (SD 14.33), PD mean 67.04 (SD 8.98); standardized mean difference −1.61; Mann–Whitney p=1.75×10⁻⁸.
- UCI dataset 470 is licensed CC BY 4.0 and has 756 repeated rows, 252 participants, three recordings each, 752 acoustic columns plus ID/gender/class, 564 PD and 192 control recordings, no missing values, and one exact duplicate pair within one participant. A checked-in contract pins the ordered 755-column header and dataset metadata; inspection and evaluation fail on header drift. The UCI record does not publish an archive SHA-256, so local hashes are documented only as integrity fingerprints. The participant grouping keeps repeats and that duplicate pair in a single fold. It remains an independent feature-table experiment.

## Audio and features

Input quality checks use source header values and linear full-scale amplitude. Stereo cancellation, clipping, low RMS, duration, finite signal, and Praat voiced-frame occupancy are checked. The configured `average_with_phase_check` mono policy is enforced; accepted signals are DC-corrected, silence-trimmed, and resampled to 16 kHz. No denoising, SPL calibration, or arbitrary loudness normalization is applied. Spectral summaries are limited to a shared 3,800 Hz band, below the source cohort's 4,000 Hz Nyquist frequency. Undefined jitter/shimmer remain missing, and the JSON report preserves the feature schema version.

## Model evaluation

The principal UAMS comparison is repeated nested participant-grouped cross-validation: five outer folds, three inner folds, and three prespecified repeats (seeds 2026–2028). Participants are the scoring and split unit; hyperparameters are selected only inside each outer training fold, and imputation/scaling are fit within training folds. The table summarizes the current nested results (mean ± standard deviation across the three repeat-level participant OOF estimates).

| Candidate | Balanced accuracy | ROC-AUC |
|---|---:|---:|
| Age-only logistic comparator | 0.839 ± 0.007 | 0.849 ± 0.013 |
| Age-plus-voice logistic comparator | 0.771 ± 0.012 | 0.814 ± 0.029 |
| Voice-only Extra Trees | 0.766 ± 0.008 | 0.785 ± 0.015 |
| Voice-only random forest | 0.746 ± 0.026 | 0.787 ± 0.016 |
| Voice-only L2 logistic | 0.739 ± 0.007 | 0.770 ± 0.008 |

The age-only baseline exceeds the voice-only results, and age-plus-voice does not improve on age-only. This small, age-confounded cohort does not establish a disease-specific voice contribution. For the primary-seed nested evaluation, internal class-stratified participant-bootstrap intervals are available; for example, Extra Trees balanced accuracy is 0.664–0.850. These intervals are conditional on already-fitted outer-fold models and are not external or clinical confidence intervals. No clinical threshold was selected, and probability outputs are uncalibrated.

The earlier fixed-pipeline grouped results are retained as a **historical descriptive baseline** only: age-only logistic 0.825 (0.074), age-plus-voice logistic 0.784 (0.145), voice logistic 0.659 (0.134), random forest 0.758 (0.094), RBF SVM 0.760 (0.066), and dummy 0.500. They are a separate earlier analysis and should not be combined with or substituted for the nested results above. The current local nested results show the same main limitation: the age-only comparator exceeds voice-only models, and the cohort does not demonstrate a disease-specific voice contribution.

The UCI #470 feature-table benchmark remains separate: logistic 0.766 (0.043), random forest 0.727 (0.056), RBF SVM 0.715 (0.052), and dummy 0.500 balanced accuracy. UCI features are not Core39 WAV measurements. See [`../methodology/model_evaluation.md`](../methodology/model_evaluation.md) for evaluation details and interpretation limits.

Grouped random-forest permutation importance and final logistic coefficients are exploratory; rankings are not biomarkers or causal explanations. No external test cohort, calibrated probability, clinically chosen threshold, prevalence-representative evaluation, or longitudinal model exists.

## Verification results

- The project's locked environment was checked with `uv sync --extra dev --locked`; 71 packages were verified.
- Unit/integration test counts, statement coverage, Ruff version and formatter file count are recorded in `docs/TEST_RESULTS.md` and `docs/testing/VERIFICATION_REPORT.md` for this source snapshot.
- Current grouped evaluation, feature extraction receipt, model training, artifact checksum, provenance checks, and model reload verification passed.
- Streamlit AppTest uploaded a generated synthetic WAV through the UI, completed analysis, and confirmed the schema version in features and reports. Regression tests cover all seven sections, malformed WAV handling, empty research/report states, result-card rendering, current model evidence, OOD abstention, and 3D signal navigation. Live browser smoke evidence and results are recorded in the current verification report; physical microphone/OS permission remains a manual check.
- Chrome 156 headless browser smoke test completed the synthetic WAV upload/analyze flow, rendered the decorative overview and real processed waveform with WebGL2, moved the waveform-detail slider, rendered the configured spectrogram surface, reset the camera, and confirmed the 2D canvas fallback with WebGL disabled. No browser page errors occurred. Synthetic-only screenshots are in `docs/testing/screenshots/`.
- Physical microphone permission and speech capture remain REQUIRES MANUAL VERIFICATION.
- Three sequential passes document software coverage, exploratory model limits, and release/data integrity. Pass 2 was a separate read-only review by an agent that did not implement the changes; Pass 3 exercised a fresh extraction/environment. These are not independent clinical reviews or validations.

See `docs/testing/VERIFICATION_REPORT.md` and `AUDIT_1_SOFTWARE.md` through `AUDIT_3_END_TO_END.md` for evidence and status.

## Privacy, clinical, and regulatory status

Raw recordings and participant-linked generated tables are excluded from Git. Voice can remain identifying. The configured default is loopback-only and the app does not persist user audio or reports. Clinical validation is blocked: no hospital/site, IEC approval, participants, clinician interviews, independent cohort, or prospective outcome evidence were available. Regulatory status was not determined and CDSCO authorization was not sought or obtained.

## Development pathway

1. Technical validation: repeatability, Praat reference comparison, distance/device/noise/browser robustness, and invalid-input failure analysis.
2. Clinical need refinement: obtain workflow observations and neurologist/SLP feedback using the provided non-leading interview guides; document real feedback only.
3. Prospective protocol: define intended population, primary endpoint and sample size with clinicians/statistician; obtain institutional ethics, hospital, consent, and privacy approval before data collection.
4. Model validation: lock participant-level development/test cohorts, include age/sex and voice-affecting covariates, calibrate only on development data, evaluate external sites, devices, languages, failure rates, subgroup sensitivity/specificity, calibration, and uncertainty.
5. Regulatory and deployment: obtain qualified Indian regulatory advice on intended use/classification, applicable QMS/software lifecycle/risk/cybersecurity requirements, and any licensing/clinical-investigation steps before clinical use.

## Reproduction commands

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv sync --all-extras --locked
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe scripts\verify_project.py
.\.venv\Scripts\streamlit.exe run app.py --server.address 127.0.0.1
```

Dataset download and analysis commands are in `README.md`. Keep downloaded UAMS voice files private and local.
