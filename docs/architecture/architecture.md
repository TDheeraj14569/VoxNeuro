# System architecture

The local Streamlit app is a thin UI over a reusable Python package:

```text
Browser mic / WAV upload
  → soundfile decode and actual WAV metadata
  → configurable quality gate (fail closed)
  → mono conversion, DC offset removal, silence trim, polyphase resampling
  → waveform / spectrogram views
  → Praat/Parselmouth phonation + Librosa MFCC/spectral features
  → schema validation and local report
  → (research-only grouped ML tools; no new-microphone classification)
```

The browser sends audio to the local Streamlit process; the application does not save raw audio or reports by default. There is no cloud service, external paid API, custom hardware, or hardware-specific model assumption. Filesystem paths, model artifacts, and datasets are kept outside UI state except for transient session data.

## Module responsibilities

- `audio`: decoding, quality checks, frame RMS, deterministic preprocessing.
- `features`: versioned feature order, Praat/Parselmouth and Librosa extraction.
- `dataset`: manifest, loading, integrity and demographic audits.
- `modeling`: participant-grouped splits, fold-safe pipelines, metrics, research model bundle and schema-checked inference.
- `reporting`: JSON data export, self-contained HTML audio report, model card, and nested-CV report.
- `visualization`: waveform, spectrogram, and fold metric plots.
- `app.py`: navigation, acquisition, displays, and report download.

## Data boundaries

Identity columns remain in the manifest only; they are excluded from the predictor list. Dataset source and label fields never enter the feature schema. UCI feature-only data remain a separate benchmark. Bundle metadata identifies the schema, source, evaluation design, software versions, and research-only status.

