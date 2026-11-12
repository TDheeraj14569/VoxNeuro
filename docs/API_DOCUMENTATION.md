# VoxNeuro API Reference Manual
## Python Architecture, REST Services, and Clinical Verification Interfaces

**Version:** 1.0.0-production  
**Module Prefix:** `voxneuro.*`  
**License:** Research & Evaluation Prototype

---

## 1. Architecture Overview

VoxNeuro is designed as a modular, fail-closed platform separating ordinary user voice assessment from clinical research, study governance, and acoustic modeling.

```
voxneuro/
├── audio/            # WAV I/O, validation, spectral gating, preprocessing
├── features/         # Core39 schema (voxneuro.voice.v3), Praat/Parselmouth, Librosa
├── dataset/          # UAMS and UCI #470 ingestion, audit, demographic matching
├── modeling/         # Bundling, domain registry, prediction service, M6 benchmarks
├── study/            # SQLite database (006), consent, participants, sessions, auth
├── ui/               # Streamlit theme, design tokens, consumer pages, reports
└── reporting/        # HTML/JSON audit evidence generators
```

---

## 2. Core Audio & Feature Extraction APIs

### `voxneuro.audio.io.decode_audio(file_or_bytes: str | bytes | Path) -> tuple[np.ndarray, int]`
Decodes standard PCM or compressed audio formats into a 1D float32 array normalized to $[-1.0, 1.0]$ and native sample rate.

### `voxneuro.audio.validation.validate_audio(signal: np.ndarray, sample_rate: int, config: AudioValidationConfig) -> ValidationResult`
Evaluates audio signal against prespecified quality thresholds:
- Minimum duration (1.0s) and maximum duration (30.0s).
- RMS level ($\ge 0.003$) and peak clipping limit ($< 0.01$).
- Silence fraction ($< 0.35$).
- Voicing fraction ($\ge 0.15$) and harmonic overtone structure.

### `voxneuro.features.extractor.extract_features(signal: np.ndarray, sample_rate: int, config: FeatureConfig) -> dict[str, float]`
Extracts the 39 Core39 acoustic features conforming to schema `voxneuro.voice.v3`. Returns pitch, perturbation (jitter, shimmer), harmonicity (HNR), and 13 MFCC means and standard deviations.

---

## 3. Modeling & Prediction Service APIs

### `voxneuro.modeling.prediction_service.evaluate_prediction(features: dict[str, float], domain_id: str, context: CaptureContext) -> PredictionResult`
Executes the fail-closed 4-Case Decision Engine:
- **Returns `PredictionResult` with fields:**
  - `case_category`: `"CASE_A"`, `"CASE_B"`, `"CASE_C"`, or `"CASE_D"`.
  - `calibrated_probability`: Float or `None`.
  - `confidence_interval`: Tuple `(lower, upper)` or `None`.
  - `similarity_index`: Float or `None`.
  - `plain_language_summary`: Clinically neutral summary string.
  - `recommended_next_steps`: List of consumer-facing action items.
  - `acoustic_highlights`: Plain-language metrics for pitch, steadiness, and clarity.

---

## 4. Study & Participant Governance APIs

### `voxneuro.study.auth.authenticate_user(conn: sqlite3.Connection, email: str, password: str) -> AuthToken | None`
Authenticates user with PBKDF2-HMAC-SHA256 password hashing. Issues cryptographically signed session token.

### `voxneuro.study.consent.record_consent(conn: sqlite3.Connection, participant_id: str, study_id: str, scopes: list[str]) -> ConsentRecord`
Stores explicit versioned consent for voice recording, feature analysis, research retention, or withdrawal.
