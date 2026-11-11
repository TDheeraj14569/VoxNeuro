# VoxNeuro Milestone 3: Feature Schema & Mathematical Definitions

**Version:** 3.0.0  
**Enclosing Envelope:** `voxneuro.voice.v4`  
**Classification:** Research Acoustic Feature Specification  

---

## 1. Overview of Multi-Task Architecture

Milestone 3 defines three task-specific feature schemas alongside the legacy `voxneuro.voice.v3` sustained-vowel schema, packaged inside a unified `voxneuro.voice.v4` multi-task session envelope:

1. **`voxneuro.voice.v3`**: Canonical Core39 acoustic features (sustained vowel `/a/`). Preserved with zero modification.
2. **`voxneuro.task.ddk.v1`**: 11 temporal regularity, syllable rate, and rate-drift features.
3. **`voxneuro.task.connected_speech.v1`**: 20 speech segmentation, pause distribution, and prosodic dynamics features.
4. **`voxneuro.task.vowel_space.v1`**: 16 formant tracking and geometric vowel space area features.

---

## 2. Canonical Sustained Vowel Schema: `voxneuro.voice.v3`

- **Schema Version:** `voxneuro.voice.v3`
- **Schema Fingerprint:** `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f`
- **Feature Count:** Exactly 39 features in immutable deterministic sequence.
- **Constituent Groups:**
  - Fundamental frequency ($F_0$): `f0_mean_hz`, `f0_median_hz`, `f0_sd_hz`, `f0_min_hz`, `f0_max_hz`, `f0_range_hz`
  - Perturbation: `jitter_local` (fraction), `shimmer_local` (fraction)
  - Harmonics: `hnr_mean_db` (dB)
  - Mel-Frequency Cepstral Coefficients: `mfcc_00_mean` through `mfcc_12_mean` (13 means), `mfcc_00_sd` through `mfcc_12_sd` (13 standard deviations)
  - Spectral Descriptors: `spectral_centroid_mean_hz`, `spectral_rolloff_mean_hz`, `spectral_bandwidth_mean_hz`, `zero_crossing_rate_mean`

*Note: Models trained in M1 and validated in M2 consume exclusively `voxneuro.voice.v3`. They cannot consume v4 features directly.*

---

## 3. Diadochokinetic Syllable Repetition: `voxneuro.task.ddk.v1`

- **Schema Version:** `voxneuro.task.ddk.v1`
- **Schema Fingerprint:** `b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b`
- **Feature Count:** 11 features

### Mathematical Definitions

1. **`estimated_event_count`** ($N$):
   $$\text{Count of acoustic syllable peaks identified by smoothed energy envelope prominence.}$$
   - *Unit:* Count (integer represented as float) | *Range:* $[0, \infty)$

2. **`estimated_event_rate_per_s`** ($R_{\text{DDK}}$):
   $$R_{\text{DDK}} = \frac{N - 1}{t_{\text{last}} - t_{\text{first}}} = \frac{1}{\bar{\Delta t}_{\text{IEI}}}$$
   - *Unit:* $\text{s}^{-1}$ (events / s) | *Range:* $[0.5, 15.0]$ | *Null when:* $N < 3$

3. **`mean_inter_event_interval_s`** ($\bar{\Delta t}_{\text{IEI}}$):
   $$\bar{\Delta t}_{\text{IEI}} = \frac{1}{N - 1} \sum_{i=1}^{N-1} (t_{i+1} - t_i)$$
   - *Unit:* Seconds (s) | *Range:* $[0.05, 2.0]$ | *Null when:* $N < 2$

4. **`median_inter_event_interval_s`** ($\tilde{\Delta t}_{\text{IEI}}$):
   $$\tilde{\Delta t}_{\text{IEI}} = \text{median}(\{t_{i+1} - t_i\}_{i=1}^{N-1})$$
   - *Unit:* Seconds (s) | *Range:* $[0.05, 2.0]$ | *Null when:* $N < 2$

5. **`sd_inter_event_interval_s`** ($\sigma_{\text{IEI}}$):
   $$\sigma_{\text{IEI}} = \sqrt{\frac{1}{N - 2} \sum_{i=1}^{N-1} (\Delta t_i - \bar{\Delta t}_{\text{IEI}})^2}$$
   - *Unit:* Seconds (s) | *Range:* $[0.0, 1.0]$ | *Null when:* $N < 3$

6. **`cv_inter_event_interval`** ($\text{CV}_{\text{IEI}}$):
   $$\text{CV}_{\text{IEI}} = \frac{\sigma_{\text{IEI}}}{\bar{\Delta t}_{\text{IEI}}}$$
   - *Unit:* Dimensionless ratio | *Range:* $[0.0, 2.0]$ | *Null when:* $N < 3$ or $\bar{\Delta t} \le 0$

7. **`rmssd_inter_event_interval_s`** ($\text{RMSSD}_{\text{IEI}}$):
   $$\text{RMSSD}_{\text{IEI}} = \sqrt{\frac{1}{N - 2} \sum_{i=1}^{N-2} (\Delta t_{i+1} - \Delta t_i)^2}$$
   - *Unit:* Seconds (s) | *Range:* $[0.0, 1.0]$ | *Null when:* $N < 3$

8. **`inter_event_interval_slope_s_per_event`** ($\beta_{\text{IEI}}$):
   $$\text{Ordinary least-squares linear slope of } \Delta t_i \text{ as a function of event index } i.$$
   Measures the temporal change (rate drift) in detected inter-event intervals over time. A positive slope indicates progressive lengthening of inter-event intervals (slowing), while a negative slope indicates shortening (acceleration). This measures temporal change in detected intervals only and does not independently establish fatigue or neurological deterioration.
   - *Unit:* s / event | *Range:* $[-0.5, 0.5]$ | *Null when:* $N < 4$

9. **`valid_intervals_count`**:
   $$\text{Number of completed inter-event intervals } = N - 1.$$
   - *Unit:* Count | *Range:* $[0, \infty)$

10. **`active_speech_duration_s`**:
    $$T_{\text{active}} = t_{\text{last}} - t_{\text{first}}$$
    - *Unit:* Seconds (s) | *Range:* $[0.0, \text{duration}]$ | *Null when:* $N < 2$

11. **`task_duration_s`**:
    $$T_{\text{total}} = \text{Total retained recording duration after preprocessing.}$$
    - *Unit:* Seconds (s) | *Range:* $[2.0, 20.0]$

---

## 4. Connected Speech: `voxneuro.task.connected_speech.v1`

- **Schema Version:** `voxneuro.task.connected_speech.v1`
- **Schema Fingerprint:** `7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1`
- **Feature Count:** 20 features

### Mathematical Definitions

1. **`total_recording_duration_s`** ($T_{\text{rec}}$): Total audio duration in seconds.
2. **`estimated_active_speech_duration_s`** ($T_{\text{phon}}$): Total duration of detected speech bouts ($> 100$ ms).
3. **`estimated_silence_duration_s`** ($T_{\text{pause}}$): Total duration of detected pauses ($> 150$ ms).
4. **`pause_count`** ($N_{\text{pause}}$): Number of silent intervals exceeding the 150 ms acoustic pause threshold.
5. **`mean_pause_duration_s`**: Mean duration of individual pause intervals.
6. **`median_pause_duration_s`**: Median duration of individual pause intervals.
7. **`max_pause_duration_s`**: Longest single pause duration in seconds.
8. **`pause_duration_sd_s`**: Standard deviation of pause durations.
9. **`pause_fraction`** ($\Phi_{\text{pause}}$):
   $$\Phi_{\text{pause}} = \frac{T_{\text{pause}}}{T_{\text{rec}}}$$
10. **`speech_activity_fraction`** ($\Phi_{\text{speech}}$):
    $$\Phi_{\text{speech}} = \frac{T_{\text{phon}}}{T_{\text{rec}}}$$
11. **`speech_bout_count`**: Number of continuous active speech segments separated by pauses.
12. **`mean_speech_bout_duration_s`**: Mean duration of continuous vocal bouts.
13. **`median_speech_bout_duration_s`**: Median duration of continuous vocal bouts.
14. **`f0_median_hz`**: Median fundamental frequency across voiced frames in connected speech.
15. **`f0_sd_hz`**: Standard deviation of $F_0$ across voiced frames (prosodic pitch variation).
16. **`f0_q10_hz`**: 10th percentile of fundamental frequency.
17. **`f0_q90_hz`**: 90th percentile of fundamental frequency.
18. **`f0_range_semitones`** ($\text{ST}_{\text{range}}$):
    $$\text{ST}_{\text{range}} = 12 \cdot \log_2\left(\frac{F_{0, 90}}{F_{0, 10}}\right)$$
    Measures pitch dynamic range independent of baseline pitch (semitones). Monotone speech exhibits restricted semitone range.
19. **`intensity_median_dbfs`**: Median root-mean-square energy (dB relative to full scale) across active speech frames.
20. **`intensity_iqr_db`**: Interquartile range of vocal intensity across speech frames (measures dynamic loudness variation).

---

## 5. Vowel Space Area: `voxneuro.task.vowel_space.v1`

- **Schema Version:** `voxneuro.task.vowel_space.v1`
- **Schema Fingerprint:** `e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993`
- **Feature Count:** 16 features

### Formant Tracking Method
Formants ($F_1, F_2$) are extracted from stable central vowel segments using Burg's Linear Predictive Coding (LPC) algorithm with pre-emphasis ($0.97$), Hamming windowing (25 ms window, 10 ms step), and polynomial root extraction:
- Expected order: $p = 2 + \text{round}(f_s / 1000)$. At $f_s = 16,000$ Hz, $p = 18$ poles.
- Formant candidates filtered using engineering plausibility bounds (for candidate filtering only; these engineering limits do not constitute clinical reference intervals):
  - $F_1 \in [200, 1200]$ Hz
  - $F_2 \in [600, 3200]$ Hz
  - Bandwidth $B \le 400$ Hz

### Coordinate Definitions
For each corner vowel $v \in \{a, i, u\}$, the median formant frequency across all valid frames and trials is reported:
- `f1_a_median_hz`, `f2_a_median_hz`, `f1_a_sd_hz`, `f2_a_sd_hz`, `valid_frames_a_count`
- `f1_i_median_hz`, `f2_i_median_hz`, `f1_i_sd_hz`, `f2_i_sd_hz`, `valid_frames_i_count`
- `f1_u_median_hz`, `f2_u_median_hz`, `f1_u_sd_hz`, `f2_u_sd_hz`, `valid_frames_u_count`

### Vowel Space Area Calculation (Shoelace Formula)
$$\text{VSA}_{\text{triangle}} = \frac{1}{2} \left| F_1^{(i)} \cdot (F_2^{(a)} - F_2^{(u)}) + F_1^{(a)} \cdot (F_2^{(u)} - F_2^{(i)}) + F_1^{(u)} \cdot (F_2^{(i)} - F_2^{(a)}) \right|$$
- **Feature Name:** `vowel_space_area_hz2`
- **Unit:** $\text{Hz}^2$
- **Interpretation & Clinical Scope:** Vowel Space Area is a descriptive acoustic measure derived from estimated F1/F2 locations of /a/, /i/ and /u/. This implementation does not establish a normal reference interval, disease threshold, or Parkinson's diagnostic interpretation. Its clinical and population-specific meaning requires independent validation.
- Reduced vowel-space measures have been reported in some speech research involving neurological populations, including Parkinson's disease (e.g., Atalar et al., 2023; Ngo et al., 2022). Such associations are not universal, language-independent or diagnostic. VoxNeuro has not established this relationship in an independent clinical cohort.
- When any of the three corner vowels is missing or unvoiced, `vowel_space_area_hz2` is `null` and `vsa_estimable` is `false`.

---

## 6. Multi-Task Session Envelope: `voxneuro.voice.v4`

- **Schema Version:** `voxneuro.voice.v4`
- **Schema Fingerprint:** `cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429`

### Envelope Structure
```json
{
  "session_id": "4b7ef368-b53c-42bf-a358-8f09c9206ee3",
  "created_utc": "2026-11-11T20:54:24.123456+00:00",
  "schema_version": "voxneuro.voice.v4",
  "schema_fingerprint": "cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429",
  "overall_processing_status": "complete",
  "system_info": {
    "python_version": "3.12.16",
    "platform": "Windows-11-10.0.26100-SP0"
  },
  "tasks": {
    "sustained_vowel_a": { ... },
    "ddk_pa": { ... },
    "connected_speech_passage": { ... },
    "vowel_space_group": { ... }
  },
  "warnings": [],
  "errors": []
}
```

### Overall Processing Status Rules
- `complete`: Every registered task in the session completed successfully (`task_status == "complete"`).
- `partial`: At least one task completed successfully, but one or more tasks failed quality checks or processing.
- `quality_failed`: All registered tasks failed audio validation.
- `empty_session`: No tasks were evaluated.
