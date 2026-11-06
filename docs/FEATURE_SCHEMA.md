# Feature schema: `voxneuro.voice.v3`

The versioned schema contains 39 ordered technical measurements from a sustained `/a/`. Definitions are in `src/voxneuro/features/schema.py`; settings are in `configs/feature_config.yaml`. Extraction records the schema, schema fingerprint, feature-config fingerprint, and preprocessing-config fingerprint.

## Measurement definitions

| # | Feature name | Units | Method / validity |
|---:|---|---|---|
| 1 | `f0_mean_hz` | Hz | Praat autocorrelation; mean voiced F0; at least 3 valid voiced frames. |
| 2 | `f0_median_hz` | Hz | Median voiced F0; at least 3 valid voiced frames. |
| 3 | `f0_sd_hz` | Hz | Sample standard deviation of voiced F0; at least 3 valid voiced frames. |
| 4 | `f0_min_hz` | Hz | Minimum valid voiced F0; at least 3 valid voiced frames. |
| 5 | `f0_max_hz` | Hz | Maximum valid voiced F0; at least 3 valid voiced frames. |
| 6 | `f0_range_hz` | Hz | Maximum minus minimum voiced F0; at least 3 valid voiced frames. |
| 7 | `jitter_local` | Ratio | Praat local jitter: mean absolute consecutive period difference divided by mean period; undefined when periodic pulses are insufficient. |
| 8 | `shimmer_local` | Ratio | Praat local shimmer: mean absolute consecutive pulse-amplitude difference divided by mean amplitude; may be undefined. |
| 9 | `hnr_mean_db` | dB | Mean finite Praat cross-correlation harmonicity; requires at least one finite frame. |
| 10–35 | `mfcc_00_mean`, `mfcc_00_sd` through `mfcc_12_mean`, `mfcc_12_sd` | Dimensionless numerical coefficient | DCT coefficients derived from the log-Mel power spectrum; indices 0–12 (zero-based); means require one frame and SDs require two; 13×2 measures. |
| 36 | `spectral_centroid_mean_hz` | Hz | Mean Librosa spectral centroid over frames, within the common 50–3,800 Hz feature band. |
| 37 | `spectral_rolloff_mean_hz` | Hz | Mean 85% spectral rolloff over frames, with shared 3,800 Hz cap. |
| 38 | `spectral_bandwidth_mean_hz` | Hz | Mean Librosa spectral bandwidth over frames, with shared 3,800 Hz cap. |
| 39 | `zero_crossing_rate_mean` | Fraction | Mean Librosa zero-crossing rate over frames. |

The MFCC row covers 26 ordered feature names: `mfcc_00_mean`, `mfcc_00_sd`, `mfcc_01_mean`, `mfcc_01_sd`, …, `mfcc_12_mean`, `mfcc_12_sd`.

## Configuration and missing values

- Output sample rate after preprocessing: 16 kHz.
- Pitch range: 75–500 Hz; pitch step 0.01 s.
- MFCC count: 13; mel bands: 40; FFT window: 1,024 samples; hop: 160 samples; mel range 50–3,800 Hz.
- Spectral rolloff fraction: 0.85; feature upper limit: 3,800 Hz, below the source cohort's 4 kHz Nyquist frequency.
- Undefined jitter/shimmer and other valid undefined measurements remain native missing values. They are never converted to zero. The guarded research model's named missing-value policy and fold-local imputation do not accept omitted or malformed inputs.
- All six F0 summaries are undefined unless at least three voiced pitch frames are available. The current schema fixes the MFCC count at 13; changing it requires a schema revision.
- Text values such as `"NaN"`, `"null"`, or `"several"` are malformed in feature tables; only native missing values represent legitimate undefined measurements.

## Interpretation boundary

These acoustic summaries describe a short phonation task. They do not capture connected speech, articulation, speech rate, intelligibility, or conversational prosody. No healthy range, disease threshold, or validated biomarker interpretation is assigned.
