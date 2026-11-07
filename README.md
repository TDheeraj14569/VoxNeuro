# VoxNeuro

> [!NOTE]
> **Academic Research Software & Independence Notice:**  
> VoxNeuro Research Prototype is an independent academic research project developed for Biodesign Concept & Practice coursework (Voice Signal Analysis). It is not affiliated with, sponsored by, or related to VoxNeuro Inc. (makers of EEG cognitive assessments). VoxNeuro does not claim medical device status, regulatory authorization, or clinical diagnostic utility.

VoxNeuro is a private, local voice-signal quality control and 39-parameter acoustic measurement research prototype. It analyzes a sustained vowel recording (`/a/`), inspects signal quality, renders interactive 3D acoustic views, and exports self-contained HTML/JSON technical reports. It does **not** diagnose or rule out Parkinson's disease. The experimental cohort model is intentionally not exposed to new user microphone recordings because cross-domain compatibility between telephone-collected research datasets and arbitrary laptop/mobile microphones has not been clinically established.

---

## Quick Start (Analyze a WAV in 2 minutes)

```powershell
# 1. Install dependencies
uv sync --all-extras --locked

# 2. Run analysis on a supported WAV/WAVEX recording (8–48 kHz, mono/stereo, sustained vowel /a/)
.\.venv\Scripts\python.exe scripts\analyze_voice.py --audio path\to\vowel.wav

# 3. Or launch the interactive Streamlit workspace
.\.venv\Scripts\streamlit.exe run app.py --server.address 127.0.0.1
```

*(On macOS/Linux, substitute `.venv/bin/python` and `.venv/bin/streamlit`)*.

---

## Versioning Architecture

| Component | Version | Scope & Role |
| :--- | :--- | :--- |
| **Python Package** | `0.1.0` | Core `voxneuro` library, preprocessing, and validation pipelines (`pyproject.toml`). |
| **Acoustic Feature Schema** | `voxneuro.voice.v3` | 39 versioned, deterministic Praat and Librosa measurement definitions. |
| **Session Technical Report** | `0.3.0` | Individual session acoustic quality, waveform, and measurement HTML report. |
| **Research Model Bundle** | `0.4.0-research` | Internal UAMS cross-validation cohort baseline (domain-restricted; research only). |

---

## Environment

The implementation targets 64-bit Windows, Linux, and macOS running CPython 3.12. The checked-in `uv.lock` and `requirements-lock.txt` record exact resolved dependencies. A local managed Python can be installed with `uv python install 3.12`; no global Python install is needed.

## Setup

### Windows (PowerShell)
```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv sync --all-extras --locked
```

### macOS / Linux (Bash)
```bash
uv python install 3.12
uv venv --python 3.12 .venv
uv sync --all-extras --locked
```

Activation is optional; exact commands below use `.venv\Scripts\python.exe` and `.venv\Scripts\streamlit.exe` (or `.venv/bin/python` on POSIX) so they do not depend on shell execution policy. Streamlit is restricted to loopback by `.streamlit/config.toml`.

## Verify and launch

```powershell
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe scripts\verify_project.py
.\.venv\Scripts\streamlit.exe run app.py --server.address 127.0.0.1
```

The project verification command checks required files and imports. Dataset commands require the corresponding local data.

## Local 3D signal views

The Overview page uses a decorative acoustic ribbon; the Signal analysis page renders the processed waveform and configured STFT spectrogram from the recording in the current local session. The Three.js bundle is included locally, so the viewer makes no CDN or third-party asset requests. The Three.js MIT license is included beside the frontend package. If you edit the frontend source, rebuild it with Node.js 20, 22, or 24 (Node.js 24 recommended):

```powershell
Set-Location frontend\acoustic-visualizer
npm ci
npm run build
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$env:VOXNEURO_URL = "http://127.0.0.1:8501"
npm run smoke
Set-Location ..\..
```

Run the smoke command after launching Streamlit. It uses a local Chrome/Edge installation, uploads a generated synthetic WAV, checks WebGL2 waveform and spectrogram rendering, moves the waveform detail window, tests the camera reset, and launches a WebGL-disabled browser to verify the 2D fallback. Optional screenshot output paths are `VOXNEURO_HOME_SCREENSHOT_PATH`, `VOXNEURO_SCREENSHOT_PATH`, and `VOXNEURO_SPECTROGRAM_SCREENSHOT_PATH`.

The viewer sends only bounded, downsampled numeric arrays into its local iframe. Its WebGL scene has an on-device 2D canvas fallback. The spectrogram's vertical surface axis is frequency and its depth axis is magnitude in dB relative to amplitude 1.0; it is not calibrated sound pressure level. The waveform detail window shows actual samples, preserves local extrema when downsampling, and moves over the full recording. Rendering data is not used for feature extraction or classification.

## Datasets

Dataset downloads are separate from software installation. These commands download CC BY 4.0 sources from the official records. Keep them local; do not commit raw audio, spreadsheets with participant metadata, model files, or generated tables. Figshare article 23849127 provides the UAMS files below; the UCI ZIP contains the RAR used by the inspection script.

```powershell
New-Item -ItemType Directory -Force data\raw\uams | Out-Null
New-Item -ItemType Directory -Force data\raw\uci\download | Out-Null
Invoke-WebRequest -Uri "https://ndownloader.figshare.com/files/41836707" -OutFile data\raw\uams\Demographics_age_sex.xlsx
Invoke-WebRequest -Uri "https://ndownloader.figshare.com/files/41836710" -OutFile data\raw\uams\PD_AH.zip
Invoke-WebRequest -Uri "https://ndownloader.figshare.com/files/41836713" -OutFile data\raw\uams\HC_AH.zip
Get-FileHash data\raw\uams\PD_AH.zip -Algorithm MD5
Get-FileHash data\raw\uams\HC_AH.zip -Algorithm MD5
Invoke-WebRequest -Uri "https://archive.ics.uci.edu/static/public/470/parkinson%2Bs%2Bdisease%2Bclassification.zip" -OutFile data\raw\uci\uci-470.zip
Expand-Archive -LiteralPath data\raw\uci\uci-470.zip -DestinationPath data\raw\uci\download -Force
tar -tf data\raw\uci\download\pd_speech_features.rar
.\.venv\Scripts\python.exe scripts\inspect_dataset.py --dataset uams
.\.venv\Scripts\python.exe scripts\build_manifest.py
.\.venv\Scripts\python.exe scripts\audit_dataset.py
.\.venv\Scripts\python.exe scripts\extract_features.py --allow-reviewed-exclusions
.\.venv\Scripts\python.exe scripts\evaluate_model.py --dataset uams
.\.venv\Scripts\python.exe scripts\evaluate_nested_models.py --dataset uams
.\.venv\Scripts\python.exe scripts\train_model.py --dataset uams
.\.venv\Scripts\python.exe scripts\verify_model.py
.\.venv\Scripts\python.exe scripts\analyze_voice.py --audio .\path\to\recording.wav
.\.venv\Scripts\python.exe scripts\inspect_dataset.py --dataset uci
.\.venv\Scripts\python.exe scripts\evaluate_model.py --dataset uci
```

The UAMS ZIP hashes and expected WAV counts are checked before extraction. Extraction occurs in a temporary staging directory, validates safe paths and WAV headers, and replaces prior output only after the complete archive passes. `extract_features.py` fails closed on partial extraction; the three documented clipped UAMS samples are accepted only with the explicit flag above and the reviewed sample-specific policy in `configs/reviewed_exclusions.yaml`. The nested UAMS run tunes each candidate only inside participant-grouped inner folds, then scores held-out participants in repeated outer folds. It saves a detailed self-contained HTML comparison at `artifacts/reports/model_evaluation/uams_nested.html`. The research logistic bundle is fit only after the current extraction, fixed grouped evaluation, and nested-evaluation receipts pass provenance checks. UCI extraction invokes the system `tar` command and requires RAR support.

The `--dataset uams` and `--dataset uci` inspection modes are independent: UCI-only inspection does not require UAMS archives. UCI inspection requires a RAR-capable `tar` command (for example, bsdtar/libarchive) on `PATH`; the command above checks that it can list the archive before inspection. Windows' `tar.exe` may not support RAR, so use a RAR-capable bsdtar build if that check fails. The pinned ordered header manifest is `configs/uci470_schema.json`. The UCI record does not publish an archive SHA-256; locally recorded hashes detect accidental changes but do not authenticate the downloaded archive. The UCI file contains a separate pre-extracted feature benchmark and does not share the UAMS WAV feature schema. Do not concatenate those columns or use UCI validation to claim microphone-model performance.

Research model files are generated locally under `artifacts/models/` and are omitted from the source archive. The loader checks a SHA-256 sidecar before joblib deserialization; this detects file changes but is not a digital signature. Only trusted, internally generated model files may be loaded. Never accept user-uploaded joblib/pickle artifacts. The app does not load a model for new microphone recordings. Each successful session can download a self-contained HTML report with actual audio quality, processed waveform, STFT spectrogram, all 39 measurements and extraction definitions. JSON remains available as a machine-readable export.

## Recording and privacy

The assessment page requests a sustained `/a/` for about 3 to 5 seconds, sitting comfortably in a quiet room, with the built-in microphone about 15 cm away and at a steady distance. It accepts WAV uploads and uses the Streamlit browser microphone widget. The browser must be allowed microphone access; browsers generally treat `localhost` as a secure context. The checked-in server configuration binds to `127.0.0.1`, so the prototype is reachable only on the same computer by default. A remote LAN host would require an explicitly configured secure deployment and HTTPS. Verify target-browser/device behavior before a study. Audio processing is local to the app process, and the prototype does not save recordings or reports by default. A voice may itself be identifying.

Streamlit microphone input is a browser recording convenience, not a validated acquisition instrument. The app displays actual WAV metadata and re-samples after decoding when needed. New microphone audio is never sent to the cohort classifier.

## Known status

See `docs/testing/VERIFICATION_REPORT.md`, the dataset reports, model card, and limitations document. Dataset-derived internal cross-validation is experimental and does not establish clinical validity, local-population validity, calibrated risk, or regulatory authorization. Real microphone permission, browser/device variability, clinical expert feedback, prospective clinical data, ethics review, external validation, and regulatory advice require separate work.

See also [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md), [`docs/DATASET_CARD.md`](docs/DATASET_CARD.md), [`docs/FEATURE_SCHEMA.md`](docs/FEATURE_SCHEMA.md), [`docs/PRIVACY.md`](docs/PRIVACY.md), and [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) for detailed workflow, dataset, feature, privacy, and limitation documentation.

For model and dataset details, see [`docs/reports/MODEL_CARD.md`](docs/reports/MODEL_CARD.md), [`docs/DATASET_CATALOG.md`](docs/DATASET_CATALOG.md), [`docs/VALIDATION_PROTOCOL.md`](docs/VALIDATION_PROTOCOL.md), and [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md). The model evaluation methodology records participant-level scoring, nested group splits, fold-local preprocessing, demographic comparators, and why internal metrics are not clinical performance.

For a local WAV feature-analysis report, see [`docs/INFERENCE_GUIDE.md`](docs/INFERENCE_GUIDE.md). It explains why new microphone recordings currently receive an unavailable model assessment instead of a Parkinson's classification.

## Review archives

To create the small source-only archive, run `uv run python scripts/build_source_archive.py`. To create the AI review ZIP with the source package plus hashed aggregate evaluation evidence, run `uv run python -m scripts.build_ai_review_bundle`. The latter uses local dataset-derived outputs but excludes recordings, participant-level feature/prediction tables, and trained model binaries. Both builders verify ZIP integrity and the source inventory; the AI review README explains the included evidence and its limits.
