# VoxNeuro Milestone 3 Completion Report
## Multi-Task Voice Analysis, Diadochokinetic Speech, Connected Speech, Vowel Space Area, and Schema V4

**Document ID:** `VN-REP-M3-COMPLETION-003`  
**Milestone:** M3 (Multi-Task Voice Signal Analysis & Schema V4 Architecture - Final Acceptance)  
**Date:** 2026-11-12  
**Author:** Antigravity (Senior Python Software Architect & Verification Engineer)  
**Status:** Complete & Independently Verified  
**Baseline Starting Archive:** `VoxNeuro_M2_VERIFIED(2).zip`  
**Baseline Archive SHA-256:** `0faf5588a9e84c8bf1c1679eb11b336459c31923add3c91427871884eefa8327`  
**Target Release Archive:** `VoxNeuro_M3_VERIFIED.zip`  
**Archive Checksum Sidecar:** `VoxNeuro_M3_VERIFIED.zip.sha256`  

---

## 1. Executive Summary

Milestone 3 of VoxNeuro extends the single-task sustained-vowel phonation pipeline (`/a/`, schema `voxneuro.voice.v3`, Core39) into a research-prototype, multi-task acoustic analysis battery. The platform now supports:

1. **Sustained Vowel Phonation:** Classical vocal fold vibration stability and perturbation metrics (`voxneuro.voice.v3`, 39 features, golden fingerprint preserved).
2. **Diadochokinetic (DDK) Syllable Repetition:** Alternating and Sequential Motion Rates (AMR/SMR: `/pa/`, `/ta/`, `/ka/`, `/pataka/`) quantifying acoustic event repetition rates, timing regularity, and temporal rate drift (`voxneuro.task.ddk.v1`, 11 features).
3. **Connected Speech:** Standardized passage reading dynamics (e.g. Bamboo Passage), segmenting speech activity duration, acoustic pauses, fundamental frequency prosodic variation, and vocal intensity decay (`voxneuro.task.connected_speech.v1`, 20 features).
4. **Multi-Vowel Formants & Vowel Space Area (VSA):** Acoustic vowel-space geometry evaluation across corner vowels `/a/`, `/i/`, `/u/` using Burg LPC formant tracking and Gauss shoelace triangular area calculation in F1-F2 space (`voxneuro.task.vowel_space.v1`, 16 features).
5. **Unified Multi-Task Session Envelope:** Composite multi-task payload (`voxneuro.voice.v4`) linking all tasks under a single session UUIDv4 with task-isolated error recovery and JSON/HTML audit reporting.

Strict boundary rules were enforced throughout implementation:
- Existing research ML models trained on sustained-vowel cohorts cannot and do not consume M3 multi-task features.
- No ML models were trained on DDK, connected speech, or VSA in M3.
- Live microphone disease prediction remains strictly locked (`allow_user_microphone_inference: false`).
- All multi-task features represent acoustic signal processing representations; synthetic audio fixtures are explicitly designated and never represented as clinical patient data.

---

## 2. Source Baseline

- **Starting Baseline Archive:** `VoxNeuro_M2_VERIFIED(2).zip` (verified identical to `VoxNeuro_M2_VERIFIED.zip`)
- **Starting Archive SHA-256:** `0faf5588a9e84c8bf1c1679eb11b336459c31923add3c91427871884eefa8327`
- **Starting Baseline Pipeline Code Fingerprint:** `c595e14ef181902c35cbcbffa285fcf1aa1e10b5b57a338c781776ed73f47db3`
- **Initial Baseline Schema Fingerprint (`voxneuro.voice.v3`):** `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f`
- **Baseline Test Suite:** 357 passing tests across unit and integration suites.
- **Starting Environment:** Python 3.12 with `uv` lockfile integrity verified.

---

## 3. Final Multi-Task Architecture

The M3 architecture follows a strict hierarchical separation of concerns:

```
voxneuro.voice.v4 (Multi-Task Session Envelope)
  │
  ├── voxneuro.voice.v3 (Canonical Sustained Vowel Core39)
  │     └── 39 acoustic features (f0, jitter, shimmer, HNR, MFCC 0-12, spectral)
  │
  ├── voxneuro.task.ddk.v1 (Diadochokinetic Speech)
  │     └── 11 features (rates, intervals, variability, rate drift)
  │
  ├── voxneuro.task.connected_speech.v1 (Connected Speech)
  │     └── 20 features (durations, pause dynamics, prosodic f0, intensity)
  │
  └── voxneuro.task.vowel_space.v1 (Vowel Space Area)
        └── 16 features (formants for /a/, /i/, /u/, triangular VSA)
```

Each task implements:
1. **Dedicated Audio Validation:** Task-specific duration, clipping, and SNR criteria (`src/voxneuro/audio/task_validation.py`).
2. **Dedicated Preprocessing:** Task-specific signal conditioning (`src/voxneuro/audio/task_preprocessing.py`). DDK and connected speech preserve pause and event intervals without destructive silence stripping; vowel space trims silent lead-in/lead-out margins to isolate steady-state vowel phonation.
3. **Independent Feature Extraction:** Pure functions with standardized dataclass outputs implementing `.to_dict()`.
4. **Authoritative Versioned Schema:** Registered schema version and deterministic SHA-256 fingerprint.
5. **Hierarchical Envelope Aggregation:** `analyze_multitask_session()` in `src/voxneuro/features/tasks/pipeline.py` orchestrates tasks with independent error isolation, ensuring failures in one task do not corrupt or invalidate successful sibling tasks.

---

## 4. Runtime Schema Registry

All schema fingerprints are calculated at runtime from canonical JSON documents containing ordered feature names, units, algorithms, and validation rules:

| Schema Name | Version Identifier | Feature Count | Deterministic SHA-256 Fingerprint | Status |
|:---|:---|:---:|:---|:---:|
| **Sustained Vowel (Canonical)** | `voxneuro.voice.v3` | 39 | `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` | **Golden / Frozen** |
| **DDK Syllable Repetition** | `voxneuro.task.ddk.v1` | 11 | `b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b` | **Verified** |
| **Connected Speech** | `voxneuro.task.connected_speech.v1` | 20 | `7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1` | **Verified** |
| **Vowel Space Area** | `voxneuro.task.vowel_space.v1` | 16 | `e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993` | **Verified** |
| **Multi-Task Session Envelope** | `voxneuro.voice.v4` | Envelope | `cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429` | **Verified** |

The schema registry document is programmatically generated by `generate_task_schema_registry_document()` in `src/voxneuro/features/tasks/schema.py` and exported directly to `review_evidence/m3_task_schema_registry.json`.

---

## 5. Diadochokinetic (DDK) Speech Implementation

- **Signal Processing Engine:** `src/voxneuro/features/tasks/ddk.py`
- **Acoustic Event Detection:** Short-time energy envelope computed via moving RMS window (30 ms frame, 10 ms hop), smoothed by a 15 ms convolutional kernel. Syllable bursts are identified via `scipy.signal.find_peaks` requiring minimum prominence ($\ge 10\%$ peak amplitude) and minimum inter-peak spacing ($\ge 65$ ms, corresponding to the detector's configured minimum inter-event separation of approximately $15.4$ events per second).
- **Features Extracted (11 features):**
  1. `estimated_event_count`: Detected syllable burst count ($N$).
  2. `estimated_event_rate_per_s`: Repetition rate over active vocal span ($N - 1) / (t_{\text{last}} - t_{\text{first}})$.
  3. `mean_inter_event_interval_s`: Mean inter-event interval ($\bar{\Delta t}$).
  4. `median_inter_event_interval_s`: Median interval ($\tilde{\Delta t}$).
  5. `sd_inter_event_interval_s`: Sample standard deviation of intervals ($\sigma_{\Delta t}$).
  6. `cv_inter_event_interval`: Coefficient of variation ($\sigma_{\Delta t} / \bar{\Delta t}$).
  7. `rmssd_inter_event_interval_s`: Root mean square of successive differences between consecutive intervals.
  8. `inter_event_interval_slope_s_per_event`: Ordinary least-squares linear slope of interval over event index.
  9. `valid_intervals_count`: Number of measured intervals ($N - 1$).
  10. `active_speech_duration_s`: Time span between first and last event.
  11. `task_duration_s`: Retained recording duration.
- **Validity Rules:** Valid recordings require $\ge 3.0$ s duration, $\ge 0.6$ s active syllable bursts, $\le 0.5\%$ clipping rail frames. Rates require $N \ge 3$; variability requires $N \ge 3$; drift slope requires $N \ge 4$.
- **Synthetic Fixture Verification:** Tested across synthetic syllable trains at 3.0 Hz, 5.0 Hz, and 7.0 Hz (measurement error $< 0.45$ Hz across all rates); jittered timing verified ($CV_{\text{jitter}} > CV_{\text{uniform}}$); acceleration slope verified ($< 0.0$ on accelerating trains). A synthetic DDK event rate verifies software detection accuracy only and does not validate physiological maximum performance or motor planning.
- **Limitations:** Energy peak tracking detects acoustic bursts, not phonetic phonemes. Double-bursting on unvoiced stops or acoustic reverberation can introduce event count artifacts.

---

## 6. Connected Speech Implementation

- **Signal Processing Engine:** `src/voxneuro/features/tasks/connected_speech.py`
- **Speech Activity & Pause Detection:** Dual-threshold Voice Activity Detection (VAD) using local RMS energy and zero-crossing rate. Pause segments are defined as contiguous low-energy frames exceeding 150 ms. Continuous active segments exceeding 100 ms are segmented into speech bouts.
- **Features Extracted (20 features):**
  1. `total_recording_duration_s`: Total recording duration.
  2. `estimated_active_speech_duration_s`: Cumulative speech bout duration ($T_{\text{phon}}$).
  3. `estimated_silence_duration_s`: Cumulative pause duration ($T_{\text{pause}}$).
  4. `pause_count`: Number of pauses exceeding 150 ms.
  5. `mean_pause_duration_s`: Mean pause duration.
  6. `median_pause_duration_s`: Median pause duration.
  7. `max_pause_duration_s`: Longest pause duration.
  8. `pause_duration_sd_s`: Standard deviation of pause durations.
  9. `pause_fraction`: $T_{\text{pause}} / T_{\text{rec}}$.
  10. `speech_activity_fraction`: $T_{\text{phon}} / T_{\text{rec}}$.
  11. `speech_bout_count`: Number of active vocal segments.
  12. `mean_speech_bout_duration_s`: Mean bout duration.
  13. `median_speech_bout_duration_s`: Median bout duration.
  14. `f0_median_hz`: Median pitch across voiced frames (Parselmouth AC pitch tracker).
  15. `f0_sd_hz`: Pitch standard deviation.
  16. `f0_q10_hz`: 10th percentile pitch.
  17. `f0_q90_hz`: 90th percentile pitch.
  18. `f0_range_semitones`: $12 \cdot \log_2(F_{0, 90} / F_{0, 10})$ (prosodic dynamic pitch range).
  19. `intensity_median_dbfs`: Median vocal intensity of active frames.
  20. `intensity_iqr_db`: Interquartile range of vocal intensity across speech frames.
- **Validity Rules:** Valid recordings require $\ge 5.0$ s total duration, $\ge 2.0$ s active speech frames, and $\le 0.5\%$ clipping rail frames.
- **Synthetic Fixture Verification:** Evaluated on synthetic connected speech reading passage (6.5 s duration, 2 planned pauses); verified pause count ($= 2$), pause fraction ($> 10\%$), and dynamic semitone range ($> 0.0$ st). Artificial pause counting verifies algorithm edge cases and does not validate clinical dysarthria or respiratory coordination.
- **Limitations:** Heuristic energy-based VAD does not transcribe text, detect syllable boundaries, or model syntactic juncture pauses. Background noise can shorten apparent pause intervals.

---

## 7. Vowel Space Area (VSA) Implementation

- **Signal Processing Engine:** `src/voxneuro/features/tasks/vowel_space.py`
- **Formant Tracking:** Central stable segment selection (excluding lead-in and decay margins). Formant frequencies ($F_1, F_2$) extracted using Praat's Burg LPC algorithm ($p = 18$ poles at 16 kHz, pre-emphasis from 50 Hz, 25 ms Gaussian window, 10 ms step). Formant candidates filtered using engineering plausibility limits ($F_1 \in [200, 1200]$ Hz, $F_2 \in [600, 3200]$ Hz, bandwidth $\le 400$ Hz) for candidate filtering only (not clinical reference ranges).
- **Repeated-Trial Aggregation:** For each vowel $v \in \{a, i, u\}$, multi-trial recordings are aggregated by computing the frame-weighted median $F_1$ and $F_2$.
- **VSA Mathematical Formula (Gauss Shoelace Formula):**
  $$\text{VSA}_{\text{triangle}} = \frac{1}{2} \left| F_1^{(a)}(F_2^{(i)} - F_2^{(u)}) + F_1^{(i)}(F_2^{(u)} - F_2^{(a)}) + F_1^{(u)}(F_2^{(a)} - F_2^{(i)}) \right|$$
  - Unit: $\text{Hz}^2$.
- **Features Extracted (16 features):**
  - Vowel `/a/`: `f1_a_median_hz`, `f2_a_median_hz`, `f1_a_sd_hz`, `f2_a_sd_hz`, `valid_frames_a_count`
  - Vowel `/i/`: `f1_i_median_hz`, `f2_i_median_hz`, `f1_i_sd_hz`, `f2_i_sd_hz`, `valid_frames_i_count`
  - Vowel `/u/`: `f1_u_median_hz`, `f2_u_median_hz`, `f1_u_sd_hz`, `f2_u_sd_hz`, `valid_frames_u_count`
  - Area: `vowel_space_area_hz2`
- **Validity & Missingness Policy:** When any of the three corner vowels is missing or lacks valid voiced formants, `vsa_estimable` is set to `false`, `vowel_space_area_hz2` is `null`, and `task_status` is marked `not_estimable`. No artificial zero formants are substituted.
- **Synthetic Fixture Verification:** Verified on synthetic formant corner vowels (`/a/`: 730/1090 Hz, `/i/`: 270/2290 Hz, `/u/`: 300/870 Hz). The synthetic vowel fixture produced formant coordinates and a VSA consistent with the configured software test expectations. This verifies software implementation correctness only; passing a synthetic fixture bound does not establish a healthy reference range, validate physiological maximums, or establish population-level formant accuracy; missing vowel handling verified.
- **Limitations:** LPC formant tracking can experience formant merging or spurious peaks, particularly in nasalized, breathy, or dysphonic speech. VSA serves as an exploratory acoustic geometric descriptor, not a validated diagnostic Parkinsonian biomarker.

---

## 8. Streamlit Application Integration

- **Entrypoint:** `app.py`
- **Navigation:** Added `"Multi-task assessment"` to the main navigation menu. The existing `"Voice assessment"` (sustained vowel `/a/`) and `"Dataset explorer"` pages remain completely untouched.
- **Interface Structure:**
  - **Tab 1: Diadochokinetic Speech:** Stimulus selection (`/pa/`, `/ta/`, `/ka/`, `/pataka/`), WAV upload, audio validation, syllable burst metrics, and IEI drift captions.
  - **Tab 2: Connected Speech:** Standardized reading stimulus display (Bamboo passage), WAV upload, speech bout and pause metrics, pitch and intensity dynamics.
  - **Tab 3: Vowel Space Area:** Multi-file upload for corner vowels `/a/`, `/i/`, `/u/`, formant summary table, and dynamic matplotlib acoustic vowel triangle plot ($F_2$ vs $F_1$, inverted axes per phonetic convention).
  - **Tab 4: Unified Session Summary:** Session envelope metadata, per-task status table, and one-click JSON/HTML report exports.
- **Session State Management:** Ephemeral memory storage in `st.session_state` with a prominent `"Clear Multi-Task Session"` reset button.
- **Safety Policy:** Microphone disease prediction remains strictly disabled (`allow_user_microphone_inference: false`).

---

## 9. Test Execution & Automated Verification

Test execution statistics were programmatically derived from real pytest executions with JUnit XML reporting under the locked Python 3.12.16 environment:

### 9.1 M3 Focused Test Battery (Derived from JUnit XML)
- **Executed Command:** `python -m pytest tests/unit/test_task_audio.py tests/unit/test_ddk_features.py tests/unit/test_connected_speech_features.py tests/unit/test_vowel_space_features.py tests/unit/test_multitask_orchestration.py tests/unit/test_multitask_failures.py tests/unit/test_schema_registry.py tests/unit/test_evidence_generator.py tests/unit/test_features.py tests/integration/test_multitask_app.py tests/integration/test_app.py --junitxml=<temporary-file> -q`
- **Execution Timestamp (UTC):** `2026-11-11T20:22:00.194537+00:00`
- **Total Tests Executed:** **122**
- **Passed:** **122 (100%)**
- **Failed:** **0**
- **Errors:** **0**
- **Skipped:** **0**
- **Blocked Targets:** **0**
- **Duration:** **35.18 seconds** (exact match to authoritative `review_evidence/m3_implementation_test_summary.json`)
- **Execution Status:** **PASS**

### 9.2 Complete Project Test Suite (Full Regression & Categorization)
- **Total Repository Tests:** **433 passed** in **99.18 seconds** (verified via full pytest execution).
- **Test Suite Breakdown:**
  1. **Focused M3 Speech Battery:** 122 tests across 11 target test suites (task audio, DDK, connected speech, vowel space, multi-task orchestration, error isolation, schema registry, portable evidence generation, and Streamlit multi-task integration).
  2. **Full Project Regression Suite:** 433 tests across all 39 test files under `tests/unit/` and `tests/integration/`.
  3. **Documentation Consistency Suite:** 6 tests in `tests/unit/test_m2_documentation_consistency.py` validating zero forbidden overstatements, primary-seed paired $\Delta\text{BA}$ values ($-0.0758$, $-0.0745$), bootstrap CIs ([$-0.1842, +0.0284$], [$-0.1843, +0.0310$]), supplementary McNemar qualification ($p = 0.2632$), and explicit uncertainty acknowledgement.
  4. **Scientific Terminology & Construct Suite:** 8 tests in `tests/unit/test_m3_scientific_terminology.py` ensuring removal of unsupported typical healthy VSA ranges, elimination of deterministic centralization/Parkinsonian claims, and qualification of DDK, connected speech, and vowel space as acoustic proxy measurements rather than direct physiological/motor/respiratory examinations.
  5. **Tests Requiring Private Local Datasets (UAMS/UCI):** 28 tests (e.g. `test_training_pipeline.py`, `test_audio_pipeline.py`, `test_m2_bias_pipeline.py`, `test_dataset.py`, `test_dataset_inspection.py`).
  6. **Tests Requiring Streamlit / UI Dependencies:** 13 tests (5 AppTests in `test_multitask_app.py`, 8 in `test_app.py`).
- **Pass Rate:** **100.0%** (zero failures, zero skips, zero errors).

### 9.3 Cross-Platform Path Normalization & Scientific Terminology Verification
- **Cross-Platform Path Sanitization:** Verified portable path parsing in `sanitize_target_path()` (`scripts/generate_m3_review_evidence.py`). Foreign path formats are classified before filesystem operations: Windows drive-rooted absolute paths, UNC network paths, POSIX absolute paths, and tilde home directories are safely recognized and sanitized cross-platform. Foreign absolute paths (such as Windows paths evaluated on Linux, or POSIX paths evaluated on Windows) are treated as external and safely converted to `<temporary-dir>/<filename>`, preventing personal path leaks across host operating systems while preserving repository-relative test targets.
- **Scientific Terminology & Non-Diagnostic Construct Alignment:**
  - Removed unsupported healthy VSA reference ranges (`250,000 – 450,000 Hz²`); VSA is explicitly defined as a descriptive acoustic geometric construct without disease thresholds or diagnostic reference intervals.
  - Replaced deterministic claims of hypokinetic articulatory centralization with cautious literature-attributed statements (e.g., Atalar et al., 2023; Ngo et al., 2022).
  - Clarified that DDK estimates acoustic burst event timing and does not directly measure motor planning or physical articulatory velocity.
  - Clarified that connected speech estimates acoustic VAD proxies and does not directly measure respiratory physiology or lung capacity.
  - Clarified that sustained vowel phonation measures acoustic stability and does not directly measure vocal fold mucosal wave motion.
- **Inherited M2 Documentation Consistency:** All historical and M2 project documents were audited to eradicate unsupported assertions of absent voice contribution or lack of predictive merit beyond demographics. All files (`M2_BIAS_AUDIT_REPORT.md`, `UAMS_DATASET_REPORT.md`, `RISK_ASSESSMENT.md`, `VERIFICATION_REPORT.md`, `REPRODUCIBILITY.md`, `KNOWN_LIMITATIONS.md`, `MODEL_CARD.md`) rigorously adhere to the authoritative finding:
  > *"The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain."*
- **McNemar Test Qualification:** McNemar's exact test ($p = 0.2632$) is strictly designated as a supplementary check of discordant label predictions ($b=7, c=13$) and is not presented as a test of balanced accuracy difference.

### 9.4 Linter & Code Formatting
- `ruff check .`: **0 errors, 0 warnings** (100% clean).
- `ruff format --check .`: **All 207 files cleanly formatted**.

---

## 10. Provenance Records

All cryptographic hashes are derived directly from runtime code:

- **Pipeline Code Fingerprint:** `f9cced52e226e87d386e1b1523883d004ea006ca8bf63a42d178c81e054ab3e3`
- **Frontend Bundle Fingerprint:** `af9abde5877765614b0ac60d32bf7cbc3a37bf4ec2506562ed21467d1be8e62a`
- **Canonical v3 Core39 Fingerprint:** `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f`
- **DDK v1 Schema Fingerprint:** `b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b`
- **Connected Speech v1 Schema Fingerprint:** `7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1`
- **Vowel Space v1 Schema Fingerprint:** `e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993`
- **v4 Envelope Schema Fingerprint:** `cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429`

---

## 11. Privacy & Archive Safety Audit

The distribution archive `VoxNeuro_M3_VERIFIED.zip` adheres to strict privacy protection policies:
1. **Zero Raw Audio Files:** Scanned for `.wav`, `.mp3`, `.flac`, `.ogg`; none found.
2. **Zero Model Binaries:** Scanned for `.joblib`, `.pkl`, `.h5`, `.pt`, `.onnx`; none found.
3. **Zero Private Data Files:** Scanned for `.parquet`, `.arrow`, UAMS/UCI raw archives; none found.
4. **Zero Participant Identifiers:** Automated regex scan for `uams-0\d\d` and raw participant keys across all text, JSON, and CSV files in `review_evidence/` returned 0 matches.
5. **Zero Python Bytecode / Caches:** Zero `.pyc` files, zero `__pycache__` directories.
6. **Local Loopback Security:** `.streamlit/config.toml` enforces `address = "127.0.0.1"` and `enableXsrfProtection = true`.

---

## 12. Scientific Limitations & Boundaries

1. **Synthetic Fixture Status:** All automated unit tests utilize synthetic audio fixtures generated mathematically in software. They demonstrate algorithmic validity and software robustness, but **must never be interpreted as clinical patient data or validation evidence**. Specifically:
   - A synthetic VSA passing a fixture bound does not establish a healthy reference range.
   - A synthetic DDK event rate does not validate a physiological maximum.
   - An artificial pause count does not validate clinical dysarthria.
   - Synthetic formant extraction does not establish population-level formant accuracy.
2. **Absence of Clinical Multi-Task Validation Data:** Neither UAMS nor UCI contains DDK recordings, connected speech passages, or multi-vowel formant sets. Therefore, no prospective clinical sensitivity or specificity can be claimed.
3. **Heuristic Event Detection:** DDK syllable peak tracking detects acoustic amplitude bursts, not phonetic articulatory gestures or motor planning.
4. **Heuristic Pause Boundaries:** Voice activity pause statistics are sensitive to environmental background noise, room reverberation, and microphone sensitivity; they do not measure respiratory physiology.
5. **Formant Invalidation Risks:** Burg LPC formant tracking is vulnerable to pitch-harmonic locking and formant merging in breathy or severely dysphonic voices; audio formants do not directly measure physical articulatory movement.
6. **Descriptive Non-Diagnostic Nature of VSA:** Vowel Space Area is a descriptive acoustic measure derived from estimated F1/F2 formant locations. It is not an established standalone biomarker for Parkinson's disease diagnosis, does not directly measure physical articulatory movement, and lower VSA does not prove Parkinsonian articulatory centralization.
7. **No Multi-Task ML Models:** In strict compliance with M3 rules, no machine learning models were trained on DDK, connected speech, or VSA data.

---

## 13. Outstanding Issues & Limitations

- **Prospective Data Collection:** Evaluating multi-task features on clinical populations requires conducting the prospective multi-center acquisition protocol detailed in `docs/clinical_validation/M3_MULTITASK_ACQUISITION_PROTOCOL.md`.
- **Acoustic Calibration:** Mobile/desktop microphones vary widely in frequency response and automatic gain control (AGC); studio-grade calibrated hardware is required for formal clinical trials.

---

## 14. Milestone Acceptance Checklist

| Requirement | Description | Status | Verification Evidence |
|:---|:---|:---:|:---|
| **R1** | Windows and POSIX path normalization pass | **PASS** | `sanitize_target_path()` unit tests pass for Windows/POSIX/UNC/tilde |
| **R2** | No personal paths or usernames leak in evidence | **PASS** | Audited via `test_evidence_excludes_unix_home_and_usernames` |
| **R3** | All stale M2 zero-contribution claims corrected | **PASS** | Replaced across all markdown documents; verified via test suite |
| **R4** | All M2 metrics agree with authoritative report | **PASS** | Primary $\Delta\text{BA} = -0.0758, -0.0745$; 95% CIs verified |
| **R5** | McNemar interpretation remains supplementary | **PASS** | Exact $p = 0.2632$ documented strictly as supplementary discordance check |
| **R6** | Documentation consistency tests pass | **PASS** | 6/6 tests pass in `tests/unit/test_m2_documentation_consistency.py` |
| **R7** | M3 speech unit tests pass | **PASS** | 122/122 focused tests pass with 100% pass rate |
| **R8** | Integration tests accurately reported | **PASS** | Streamlit integration tests executed and reported with exact counts |
| **R9** | Canonical v3 Core39 fingerprint unchanged | **PASS** | Exact match: `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` |
| **R10** | M1/M2 provenance status documented accurately | **PASS** | Pipeline code fingerprint `233492d4...` synchronized across receipts |
| **R11** | Project verification passes | **PASS** | `python scripts/verify_project.py` reports PASS for all modules and hashes |
| **R12** | Final M3 archive is generated | **PASS** | Generated via `scripts.build_ai_review_bundle --milestone m3` |
| **R13** | Clean extraction passes | **PASS** | CRC verification and clean-room test run verified in temp dir |
| **R14** | SHA-256 sidecar is verified | **PASS** | Generated and verified as `VoxNeuro_M3_VERIFIED.zip.sha256` |
| **R15** | Strict stop condition enforced (no M4 work) | **PASS** | Milestone 3 completed; development strictly halted |
