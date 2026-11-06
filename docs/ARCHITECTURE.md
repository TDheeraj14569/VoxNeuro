# Architecture and release boundaries

## Application data flow

```text
Browser microphone or WAV upload
  → soundfile decodes bytes and reads source metadata
  → audio quality gate (duration, finite samples, level, clipping, voicing)
  → mono conversion, DC correction, silence trim, resampling
  → downsampled local Three.js waveform/STFT surfaces, plus 2D fallback plots
  → versioned Praat/Parselmouth and Librosa measurements
  → schema validation and local JSON/CSV report
```

The browser sends an audio object to the local Streamlit process. Processing is in memory; audio and reports are not persisted by default. The default server binds to `127.0.0.1`. The app reports signal quality and measurements only. It does not invoke the research model for a user's recording.

## Package responsibilities

| Package | Responsibility |
|---|---|
| `voxneuro.audio` | Decode WAV/WAVEX, inspect and validate signals, preprocess deterministically. |
| `voxneuro.features` | Define the ordered `voxneuro.voice.v3` contract and extract phonation/MFCC/spectral measurements. |
| `voxneuro.dataset` | Load source records, validate manifest and feature provenance, summarize cohort integrity. |
| `voxneuro.modeling` | Participant-grouped folds, fold-local model pipelines, exploratory metrics, guarded research-only bundles. |
| `voxneuro.reporting` | Sanitize feature values, preserve schema/provenance, and render research disclosures. |
| `voxneuro.visualization` | Prepare bounded waveform and STFT payloads for a local Three.js iframe and render 2D/research figures. |
| `app.py` | Streamlit navigation and user-facing acquisition, analysis, research, report, and privacy pages. |
| `scripts/` | Dataset inspection, manifest/audit, extraction, evaluation, training, verification, and source packaging. |

## Research data flow

UAMS archive hashes and expected contents are checked before extraction to a staging directory. Workbook labels are mapped explicitly; unknown labels and unexpected folders fail. Manifest audit checks participant/label consistency and waveform hashes. Feature extraction validates the manifest and only permits the three named clipping exclusions when the explicit reviewed-exclusions option is supplied. Each step records content/configuration/code fingerprints. Grouped evaluation is required before model training. Model verification checks receipts and the model artifact checksum before deserialization.

UCI's repeated-record feature table is analyzed separately. All repeats remain grouped by participant, and a second duplicate-removal sensitivity analysis is reported. UCI does not exercise VoxNeuro's WAV decoding or feature extraction pipeline.

## Feature and model contract

The 39 measurements are versioned. Bundle provenance records the ordered feature schema fingerprint, feature and preprocessing configuration fingerprints, dataset version/checksum, current evaluation receipt, relevant software versions, and build time. `predict_research()` requires explicit matching schema/configuration and a domain-validation report whose hash has been reviewed and added to the source allowlist. It refuses microphone audio, enforces complete feature order, and permits only explicitly named undefined acoustic measurements. The distributed model metadata remains research-only and marks domain compatibility false; the approval allowlist is empty, so the research prediction helper cannot produce a class for any current domain.

## 3D visualizer boundary

`frontend/acoustic-visualizer` contains the local Three.js source and reproducible npm lockfile. The Python wrapper downsamples the processed waveform while preserving local extrema, computes a bounded Hann-window STFT surface, rejects non-finite or oversized payloads, and embeds the bundled JS in a local Streamlit iframe. WebGL context loss/unavailability falls back to a local 2D canvas. The home ribbon is decorative and explicitly labeled; only the Signal analysis view consumes a user's processed recording. No audio is uploaded to a visualization service.

## Data and security boundaries

- Source archive distributions exclude raw audio, participant-linked manifests/features, generated evaluations, model artifacts, caches, and virtual environments.
- Local raw data and generated research outputs are ignored by Git. A source-only archive retains placeholder README files to document those directories.
- The joblib loader accepts only internally generated, trusted artifacts and verifies an adjacent SHA-256 checksum first. The checksum detects accidental/tampered bytes; it is not a signature or proof of publisher identity.
- Dataset labels, participant identifiers, demographic columns, and recording paths are never model predictors.
- No diagnosis, disease probability, clinical threshold, or treatment recommendation is returned.
