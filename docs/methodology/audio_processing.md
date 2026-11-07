# Audio processing methodology

**Implemented prototype settings** are in `configs/audio_config.yaml` and `src/voxneuro/audio/`.

1. Decode with libsndfile and retain sample rate, channels, format, and subtype from the WAV header.
2. Require one or two channels, finite non-empty samples, supported original sample rate (8,000 to 48,000 Hz), duration (1–30 s), linear RMS, limited clipping (≤ 1.00%), pitch-voiced frame fraction (≥ 15%), and vocal overtone/even-harmonic structure (rejecting synthetic single-frequency tones, rail waveforms, and non-vocal audio). Environmental noise, background speech, and room reverberation are not currently estimated or filtered, avoiding destructive alteration of perturbation measures like jitter and shimmer. Praat autocorrelation pitch uses the shared 75–500 Hz floor/ceiling from `feature_config.yaml`; energy-active frame fraction is reported separately.
3. Apply the configured `average_with_phase_check` mono policy: detect strongly out-of-phase stereo and reject when averaging risks cancellation; otherwise average stereo channels. Unsupported policy values fail closed.
4. Estimate and subtract DC offset. Do not loudness-normalize or denoise by default.
5. Trim leading/trailing low-energy frames relative to the signal peak while leaving a 50 ms margin.
6. Use deterministic polyphase resampling to the configured 16 kHz feature-processing rate after preserving source samples in session memory.
7. Record original and processed sample rates, channel count, removed offset, leading trim, trailing trim, and resampling status.

The `voxneuro.voice.v3` spectral features use a shared upper band of 3,800 Hz, below the 4,000 Hz Nyquist limit of the 8 kHz telephone cohort. The signal is low-pass filtered before MFCC and spectral summaries; the feature schema and model must be versioned if this band or the MFCC indexing changes. This harmonizes a frequency limit but does not establish equivalence between telephone and consumer microphone recordings.

Quality checks use PCM floating-point full-scale amplitude, not calibrated SPL. Sample peak/clipping rules are not a microphone calibration. Current thresholds are engineering defaults and require technical validation against device/task failure modes. The processed signal is rejected if malformed or empty. Not all valid files will support reliable pitch, jitter, or shimmer; undefined acoustic measures remain missing rather than zero.

