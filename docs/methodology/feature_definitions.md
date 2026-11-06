# Feature schema `voxneuro.voice.v3`

Feature order and units are defined in `src/voxneuro/features/schema.py`; `schema_document()` returns the machine-readable contract. All measurements describe the supplied sustained vowel. None is asserted to be a Parkinson's biomarker.

| Family | Measures | Method and units |
|---|---|---|
| F0 | mean, median, sample SD, min, max, range | Praat autocorrelation pitch; Hz; 75 Hz floor, 500 Hz ceiling, 10 ms step; voiced frames only |
| Perturbation | local jitter, local shimmer | Praat periodic point process; dimensionless ratios; missing if undefined |
| Noise | mean HNR | Praat cross-correlation harmonicity; dB; finite frames only |
| Cepstral/spectral | 13 MFCC means and SDs | Dimensionless DCT coefficients derived from log-Mel power; Librosa indices 0–12 (zero-based); 40 Mel bands, 1,024-sample FFT, 160-sample hop |
| Spectral shape | centroid, 85% rolloff, bandwidth, zero-crossing rate | Librosa frame summaries; Hz for frequency values, fraction for ZCR |

The 39 measurements use a shared spectral upper band of 3,800 Hz, with a 50 Hz lower Mel bound. The source telephone recordings are 8 kHz, so their Nyquist frequency is 4,000 Hz. Before spectral summaries, signals are low-pass filtered at 3,800 Hz; this prevents higher-frequency content in 16 kHz browser recordings from changing the feature band. Resampling alone does not make recording devices equivalent. The shared band reduces one settings difference, while microphone and telephone domain compatibility remains unvalidated.

The configured 1,024-sample window is 64 ms at the 16 kHz processing rate, with a 10 ms hop. Feature names `mfcc_00_*` through `mfcc_12_*` correspond to Librosa coefficient indices 0 through 12. MFCC standard deviations require at least two frames, and all F0 summaries require at least three voiced frames. The current extractor rejects any MFCC count other than 13. Any change to this feature contract requires a schema version update. Undefined jitter and shimmer remain missing; model imputation, when used, occurs inside training folds only. No CPP implementation is included. Sustained vowels do not measure speech rhythm, articulation, intelligibility, calibrated sound pressure, or connected-speech prosody.
