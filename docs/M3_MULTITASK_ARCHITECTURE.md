# VoxNeuro Milestone 3: Versioned Multi-Task Speech Analysis Architecture

**Document ID:** `VN-ARCH-M3-001`  
**Version:** `1.0.0`  
**Status:** Architecture Specification Locked  
**Target Schema:** `voxneuro.voice.v4` (Multi-Task Session Envelope)  
**Task Schemas:** `voxneuro.voice.v3`, `voxneuro.task.ddk.v1`, `voxneuro.task.connected_speech.v1`, `voxneuro.task.vowel_space.v1`  
**Author:** Antigravity (Senior Software Architect & Verification Engineer)  

---

## 1. Architectural Principles & Non-Diagnostic Boundary

Milestone 3 (M3) transitions VoxNeuro from a single-task sustained-vowel (`/a/`) prototype into a modular, multi-task acoustic signal processing framework capable of orchestrating four independent speech assessment paradigms:
1. **Sustained Vowel Phonation:** Phonatory stability, micro-perturbation (jitter/shimmer), harmonics-to-noise ratio, and spectral envelopes (legacy Core39 schema `voxneuro.voice.v3`).
2. **Diadochokinetic (DDK) Syllable Repetition:** Alternating Motion Rate (`/pa/`, `/ta/`, `/ka/`) and Sequential Motion Rate (`/pa-ta-ka/`) syllable event rates, rhythm regularity, inter-event interval variability, and rate acceleration/drift (`voxneuro.task.ddk.v1`).
3. **Connected Speech:** Continuous speech segmentation, Voice Activity Detection (VAD), pause timing, speech-to-pause ratios, and pitch/intensity variation over a standardized reading stimulus (`voxneuro.task.connected_speech.v1`).
4. **Multi-Vowel Formant & Vowel Space Area (VSA):** Multi-trial acoustic formant estimation ($F_1, F_2$) across corner vowels (`/a/`, `/i/`, `/u/`) and geometric triangle VSA calculation (`voxneuro.task.vowel_space.v1`).

### Non-Diagnostic Boundary & Scientific Restrictions
- **No Diagnostic Claims:** M3 provides engineering implementations and acoustic feature extraction tools. These features do NOT establish clinical validity, Parkinson's diagnostic classification, or validated dysarthria severity scores.
- **No Classifiers on M3 Tasks:** No machine learning model is trained on DDK, connected speech, or VSA features in M3. The legacy UAMS Parkinson's research model continues to evaluate strictly on Core39 sustained `/a/` features.
- **Independent Task Isolation:** Each task is processed independently with task-specific validation rules. Failure or low signal in one task (e.g. invalid DDK rhythm) never invalidates valid measurements in another task (e.g. sustained vowel).
- **Missing Value Integrity:** Features that fail signal or quality gates are encoded as explicit `null` (Python `None`, serialized as JSON `null`), accompanied by explicit status strings (e.g. `quality_failed`, `insufficient_signal`, `not_estimable`). Under no circumstances are missing values substituted with `0.0`.
- **Zero Data Persistence:** All audio and task features reside exclusively in volatile session memory. No local database, cloud upload, user accounts, or persistent recording retention is permitted.

---

## 2. Session Envelope Schema: `voxneuro.voice.v4`

The multi-task session envelope acts as a top-level container for all executed speech tasks in an evaluation session:

```json
{
  "schema_version": "voxneuro.voice.v4",
  "schema_fingerprint": "<sha256-hex>",
  "session_id": "c1f7b82e-9d84-4e2b-a19f-854728fbe902",
  "created_utc": "2026-11-11T15:20:00Z",
  "overall_processing_status": "complete",
  "tasks": {
    "sustained_vowel_a": { ... },
    "ddk_pa": { ... },
    "connected_speech_passage": { ... },
    "vowel_space_group": { ... }
  },
  "task_registry": {
    "voxneuro.voice.v3": "<sha256-hex>",
    "voxneuro.task.ddk.v1": "<sha256-hex>",
    "voxneuro.task.connected_speech.v1": "<sha256-hex>",
    "voxneuro.task.vowel_space.v1": "<sha256-hex>"
  },
  "processing_metadata": {
    "pipeline_code_fingerprint": "<sha256-hex>",
    "environment": {
      "python_version": "3.12.16",
      "librosa_version": "0.10.2.post1",
      "parselmouth_version": "0.4.5"
    }
  }
}
```

### Overall Processing Status Enumeration
- `complete`: All attempted tasks executed and successfully yielded valid feature vectors.
- `partial`: At least one task succeeded with valid features, but one or more attempted tasks failed quality/signal checks or were not estimable.
- `quality_failed`: All attempted tasks failed audio quality validation checks.
- `insufficient_signal`: Tasks contained insufficient voiced frames or speech activity.
- `not_estimable`: Preconditions for derived composite calculations (e.g., missing one corner vowel in VSA) were not satisfied.
- `processing_failed`: Unhandled exception or fatal error during processing.

---

## 3. Task Result Block Schema

Every task executed within the `v4` session returns a standardized dictionary:

| Field Name | Type | Description |
|:---|:---|:---|
| `task_id` | `str` | Unique session identifier for this task instance (e.g. `ddk_pa_trial_01`) |
| `task_type` | `str` | Enumeration: `sustained_vowel`, `ddk`, `connected_speech`, `vowel_space` |
| `task_schema_version` | `str` | Exact schema string (e.g. `voxneuro.task.ddk.v1`) |
| `task_schema_fingerprint`| `str` | Canonical SHA-256 fingerprint of the task schema definition |
| `task_status` | `str` | Status: `complete`, `quality_failed`, `insufficient_signal`, `not_estimable`, `processing_failed` |
| `features` | `dict[str, float | None]` | Extracted feature dictionary (null for failed/missing features) |
| `quality` | `dict[str, Any]` | Audio quality metrics (sample rate, RMS, peak, clipping, SNR) |
| `configuration_fingerprint` | `str` | SHA-256 of configuration dictionary controlling this extractor |
| `preprocessing_fingerprint` | `str` | SHA-256 of preprocessing parameters (filter bands, resampling) |
| `source_audio_metadata` | `dict[str, Any]` | Duration, original channels, original sample rate, encoding |
| `warnings` | `list[str]` | Non-fatal validity caveats or quality notices |
| `errors` | `list[str]` | Fatal error messages triggering non-estimability |

---

## 4. Task-Specific Schemas & Feature Contracts

### 4.1 Sustained Vowel Phonation (`voxneuro.voice.v3`)
- **Preservation Contract:** The legacy schema `voxneuro.voice.v3` is completely preserved.
- **Fingerprint:** `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f`.
- **Feature Count:** Exactly 39 features in identical order (6 pitch, 3 voice perturbation/harmonicity, 26 MFCC mean/sd, 4 spectral).

### 4.2 Diadochokinetic Speech (`voxneuro.task.ddk.v1`)
- **Stimuli Supported:**
  - `AMR_PA`: Alternating Motion Rate `/pa-pa-pa.../` (bilabial plosive).
  - `AMR_TA`: Alternating Motion Rate `/ta-ta-ta.../` (alveolar plosive).
  - `AMR_KA`: Alternating Motion Rate `/ka-ka-ka.../` (velar plosive).
  - `SMR_PATAKA`: Sequential Motion Rate `/pa-ta-ka-pa-ta-ka.../` (tri-syllable sequence).
- **Features Extracted:**
  1. `estimated_event_count` (`count`): Total valid syllable acoustic events detected.
  2. `estimated_event_rate_per_s` (`events/s`): Event count divided by active speech duration.
  3. `mean_inter_event_interval_s` (`s`): Arithmetic mean of inter-event intervals (IEI).
  4. `median_inter_event_interval_s` (`s`): Median of IEIs.
  5. `sd_inter_event_interval_s` (`s`): Sample standard deviation of IEIs.
  6. `cv_inter_event_interval` (`ratio`): Coefficient of variation ($\text{SD} / \text{Mean}$).
  7. `rmssd_inter_event_interval_s` (`s`): Root mean square of successive differences between consecutive IEIs.
  8. `inter_event_interval_slope_s_per_event` (`s/event`): Linear regression slope of IEI over time (rate drift/acceleration).
  9. `valid_intervals_count` (`count`): Number of valid measured intervals.
  10. `active_speech_duration_s` (`s`): Duration from first to last detected syllable event.
  11. `task_duration_s` (`s`): Total analyzed recording duration.
- **Validity Gate:** Requires $\ge 3$ detected events for rate and $\ge 4$ intervals for RMSSD and slope; otherwise status is `insufficient_signal` or `not_estimable`.

### 4.3 Connected Speech (`voxneuro.task.connected_speech.v1`)
- **Stimulus:** Standardized reading passage ("The North Wind and the Sun" or custom VoxNeuro English acoustic passage, versioned with language code `en-US`).
- **Features Extracted:**
  1. `total_recording_duration_s` (`s`): Total analyzed recording duration.
  2. `estimated_active_speech_duration_s` (`s`): Cumulative duration of speech-active bouts.
  3. `estimated_silence_duration_s` (`s`): Cumulative duration of pause/silence bouts.
  4. `pause_count` (`count`): Number of silent intervals exceeding minimum pause threshold ($>200\text{ ms}$).
  5. `mean_pause_duration_s` (`s`): Mean duration of pauses.
  6. `median_pause_duration_s` (`s`): Median duration of pauses.
  7. `max_pause_duration_s` (`s`): Duration of longest pause.
  8. `pause_duration_sd_s` (`s`): Standard deviation of pause durations.
  9. `pause_fraction` (`ratio`): Silence duration / total recording duration.
  10. `speech_activity_fraction` (`ratio`): Active speech duration / total recording duration.
  11. `speech_bout_count` (`count`): Number of continuous speech segments between pauses.
  12. `mean_speech_bout_duration_s` (`s`): Mean duration of speech bouts.
  13. `median_speech_bout_duration_s` (`s`): Median duration of speech bouts.
  14. `f0_median_hz` (`Hz`): Median fundamental frequency across voiced frames.
  15. `f0_sd_hz` (`Hz`): Standard deviation of $F_0$ across voiced frames.
  16. `f0_q10_hz` (`Hz`): 10th percentile of $F_0$.
  17. `f0_q90_hz` (`Hz`): 90th percentile of $F_0$.
  18. `f0_range_semitones` (`semitones`): $12 \times \log_2(F_{0,\text{q90}} / F_{0,\text{q10}})$.
  19. `intensity_median_dbfs` (`dBFS`): Median frame RMS level in dBFS.
  20. `intensity_iqr_db` (`dB`): Interquartile range of frame intensity.
- **Validity Gate:** Requires $\ge 5.0\text{ s}$ duration, $\ge 1.0\text{ s}$ speech activity, and $\ge 20$ voiced frames.

### 4.4 Multi-Vowel Formants & VSA (`voxneuro.task.vowel_space.v1`)
- **Corner Vowels Evaluated:** `/a/` (low back/central), `/i/` (high front), `/u/` (high back).
- **Formant Extraction Engine:** Parselmouth Burg Linear Predictive Coding (LPC) with 5 formants up to $5000\text{ Hz}$ (or $5500\text{ Hz}$ for female voices, default $5000\text{ Hz}$), $25\text{ ms}$ window, $10\text{ ms}$ step, pre-emphasis $>50\text{ Hz}$.
- **Analysis Segment:** Central $50\%$ stable segment ($25\%$ to $75\%$ duration window) to exclude onset/offset coarticulatory transitions.
- **Features Extracted:**
  - Per-Vowel Formants: $F_{1,\text{median}}$, $F_{2,\text{median}}$, $F_{1,\text{sd}}$, $F_{2,\text{sd}}$, valid frame count, valid frame fraction for `/a/`, `/i/`, `/u/`.
  - Composite Metric:
    $$\text{VSA} = 0.5 \times |F_{1,a}(F_{2,i} - F_{2,u}) + F_{1,i}(F_{2,u} - F_{2,a}) + F_{1,u}(F_{2,a} - F_{2,i})| \quad (\text{Hz}^2)$$
- **Validity Gate:** All three corner vowels (`/a/`, `/i/`, `/u/`) must be present with valid formant estimates. If any vowel is missing or invalid, $\text{VSA}$ is formally designated as `null` and status is marked `NOT ESTIMABLE`.

---

## 5. Module Hierarchy & File Organization

```text
src/voxneuro/
├── audio/
│   ├── io.py                    # Audio reading & decoding (shared)
│   ├── validation.py            # Legacy v3 sustained-vowel audio validator (PRESERVED)
│   ├── preprocessing.py         # Legacy v3 sustained-vowel preprocessor (PRESERVED)
│   ├── task_validation.py       # Task-agnostic audio integrity & task-specific validation gates
│   └── task_preprocessing.py    # Pause-preserving task preprocessor (DC offset, resample)
│
├── features/
│   ├── schema.py                # Legacy v3 Core39 schema (PRESERVED)
│   ├── extractor.py             # Legacy v3 Core39 extractor (PRESERVED)
│   │
│   └── tasks/
│       ├── __init__.py          # Task feature package entrypoint
│       ├── schema.py            # v4 session envelope, DDK, Connected Speech, Vowel Space schemas
│       ├── ddk.py               # DDK event detector & temporal feature extractor
│       ├── connected_speech.py  # VAD speech segmentation, pause, & prosodic feature extractor
│       ├── vowel_space.py       # Burg LPC formant estimation & triangle VSA calculator
│       └── pipeline.py          # Unified analyze_multitask_session() orchestrator
│
└── reporting/
    ├── report.py                # Legacy v3 report builder (PRESERVED)
    ├── html_report.py           # Legacy v3 HTML report (PRESERVED)
    └── multitask_report.py      # M3 Multi-task JSON & HTML visual dashboard builder
```

---

*VoxNeuro Research Prototype &bull; M3 Multi-Task Architecture Specification &bull; 2026-11-11*
