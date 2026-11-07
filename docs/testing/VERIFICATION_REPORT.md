# Current verification report

**Checked:** 2026-11-07, Windows 11, CPython 3.12.14, locked project environment. The source-review ZIP excludes the local research datasets, processed participant-level feature tables, trained model artifacts, reports generated from participant recordings, environments, and caches. Dataset/model verification was run separately in the local data-bearing workspace.

## Software and application checks

- uv 0.12.5; uv sync --all-extras --locked checked 71 locked Python packages.
- Full Python suite: **265 passed** (257 non-UI tests plus eight Streamlit AppTests). Coverage is **86.81% across 2,085 statements** in `src/voxneuro`.
- Ruff lint passed. Ruff format --check passed with 153 files already formatted.
- Project verification passed: 11 required imports and 8 required files.
- Model verification passed: bundle sidecar, current data/evaluation/code/config receipts, feature schema, deterministic reload prediction, and research-only/domain-incompatible metadata.
- Frontend: npm ci completed with zero reported vulnerabilities; all three JavaScript unit tests passed; the bundled 3D visualizer rebuilt successfully at 575.2 kB.
- A fresh local Streamlit server was opened at http://127.0.0.1:8512. The Chrome workflow used a generated synthetic WAV and checked upload, audio analysis, waveform, spectrogram, camera reset, hidden-tab animation resumption, and the WebGL-disabled responsive 2D fallback. It reported no browser page errors.
- Streamlit AppTests cover all seven sections, valid WAV analysis and HTML report controls, malformed WAV handling, empty research/report states, and the 3D signal views. No classification was emitted.
- A real UAMS development-cohort WAV was passed through the CLI analysis path; decoding, technical validation, Core39 extraction, and the local HTML report succeeded. This is a software smoke test on training-cohort data, not independent inference or validation.
- The dataset audit, nested UAMS comparison, and individual WAV HTML reports are local artifacts under artifacts/reports. They are not bundled into the source-only review ZIP.

## Dataset integrity and provenance

- UAMS manifest: 81 records (41 HC, 40 PD), 81 unique participants, no label mismatches, duplicate waveform hashes, or malformed/missing/out-of-range age values.
- Feature extraction: 78/81 recordings accepted under the explicit reviewed exclusion policy. The three excluded recordings are clipped PD samples. Class-specific missingness can bias model estimates.
- Current Core39 feature table: 78 participants (37 PD, 41 HC), one recording per participant. Feature schema is voxneuro.voice.v3.
- UCI #470: strict validation passed for 756 source rows, 252 participants, three repeats per participant, binary and participant-consistent metadata, and finite predictors. There is one exact duplicate row for one participant; a separate deduplication sensitivity analysis was run.
- Source/model provenance fingerprint: a4ea2987db07b813e5f7f1c98c7748c52a5fb4835f4bcdfba07bd564ae323390.
- UAMS feature schema fingerprint: a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f.
- UAMS manifest SHA-256: 697e422f2631ded7be3b6ac737ce2655747340491ab8a49ab5ba40ed0454264e.
- UAMS extracted feature-table SHA-256: 732202ca2de13e54c7049f4b15775b964265f13931b93c0fb574f6cf9cd43fc0.

## UAMS nested model evaluation

The current model-family comparison uses repeated nested participant-grouped evaluation: five outer folds, three inner grouped folds, seeds 2026–2028, and 1,000 class-stratified participant bootstrap resamples for the primary seed. Inner hyperparameter selection uses balanced accuracy. Preprocessing is contained in each model pipeline and fit only on training participants. No outer-fold threshold tuning or probability calibration is performed.

Across the three pooled repeat estimates:

- Age-only logistic comparator: balanced accuracy **0.839 ± 0.007**, precision **0.807 ± 0.012**, sensitivity **0.865**, specificity **0.813 ± 0.014**, ROC-AUC **0.849 ± 0.013**.
- Highest mean voice-only candidate, Extra Trees: balanced accuracy **0.762 ± 0.020**, precision **0.727 ± 0.023**, sensitivity **0.793 ± 0.027**, specificity **0.732 ± 0.038**, ROC-AUC **0.784 ± 0.016**.
- Age-plus-voice logistic: balanced accuracy **0.771 ± 0.012**, ROC-AUC **0.817 ± 0.018**.
- Extra Trees primary-seed participant-bootstrap 95% interval for balanced accuracy: **0.678–0.861**. Age-only comparator interval: **0.754–0.911**. These intervals condition on the fitted outer-fold models and do not represent external or clinical uncertainty.

The cohort has a large age imbalance: HC mean age 47.73 (SD 14.33), PD 67.04 (SD 8.98), standardized mean difference -1.61, Mann–Whitney p=1.75e-8. Age-only exceeds every voice-only candidate. Age-plus-voice does not exceed age-only balanced accuracy or ROC-AUC. This cohort therefore cannot establish that the model has isolated a Parkinson-specific acoustic signal. The three PD-only clipping exclusions are another limitation.

Full accuracy, precision, sensitivity, specificity, balanced accuracy, F1, ROC-AUC, trapezoidal PR-AUC, average precision, MCC, Brier score where available, confusion counts, intervals, and per-fold selected parameters are in docs/reports/MODEL_CARD.md and artifacts/reports/model_evaluation/uams_nested.html. Brier scores and estimator predict_proba outputs are uncalibrated; average precision is not trapezoidal PR-AUC.

The bundled L2 logistic model is an interpretable research reference whose regularization was selected by participant-grouped cross-validation and then refit on all 78 UAMS participants. It is not selected because it has the top voice-only CV score. It is not used by the application for new microphone audio.

## Separate UCI feature-table results

The fixed-pipeline, five-fold participant-grouped benchmark produced:

- Logistic regression: BA 0.766 ± 0.043; sensitivity 0.878 ± 0.014; specificity 0.655 ± 0.093; ROC-AUC 0.826 ± 0.036; average precision 0.924 ± 0.032.
- Random forest: BA 0.727 ± 0.056; sensitivity 0.910 ± 0.031; specificity 0.545 ± 0.135; ROC-AUC 0.848 ± 0.043; average precision 0.942 ± 0.019.
- RBF SVM: BA 0.715 ± 0.052; sensitivity 0.883 ± 0.015; specificity 0.547 ± 0.111; ROC-AUC 0.827 ± 0.039; average precision 0.929 ± 0.022.

These are results on the UCI pre-extracted table, not VoxNeuro raw WAV features. The feature table has more PD than HC examples and no row-level age comparator.

## Safety and domain boundary

- The UAMS training audio is telephone-collected. Compatibility with laptop, browser, smartphone, other languages, other tasks, or other recording conditions is unverified.
- Live-microphone and unknown device domains remain blocked. A matching feature-name list or schema does not prove acoustic-domain compatibility.
- No clinical threshold, calibrated disease probability, independent external test, prospective cohort, Indian-population performance, clinician study, ethics approval, or regulatory authorization has been established.
- The app analyzes signal quality and acoustic measurements. It deliberately withholds PD/HC classification on new recordings.
- NeuroVoz was not downloaded or used: its repository requires an access request and Data Use Agreement, neither of which was completed. No external performance is claimed.

## Source archive

`VoxNeuro_source_audit.zip` was rebuilt using the repository inclusion rules and passed ZIP integrity and inventory checks. It contains 181 source, configuration, test, and documentation files, including the bundled local visualizer and synthetic-only browser smoke test assets. It excludes `.venv`, `.git`, caches, `node_modules`, raw/processed datasets, trained model artifacts, generated reports, and AI-review-only attachments.

`VoxNeuro_AI_review_bundle.zip` contains those same 181 source files plus 11 review attachments (192 members total). The evidence includes aggregate fold metrics, result summaries, provenance receipts, and a dataset audit with counts only; the feature-extraction receipt replaces its sample-ID list with an exclusion count. It excludes recordings, participant-level prediction rows, participant-level feature tables, and trained model binaries. Its README lists SHA-256 hashes for every evidence attachment.

The entire 252-test suite was also run from a clean extraction of the AI review ZIP with the extracted `src/` forced to the front of `PYTHONPATH`; all tests passed and coverage reached 87%. This confirms the fixed source-inventory test and the package contents rather than relying only on a test run in the development workspace.

Reproducing the cohort results requires separately obtaining and verifying the source datasets. Passing software tests and internal cross-validation do not establish clinical effectiveness.
