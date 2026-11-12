# Recording Domain Metadata Schema Specification

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Schema Identifier:** `voxneuro.domain_metadata.v1`  
**Status:** Frozen Specification  
**Version:** 1.0.0  

---

## 1. Overview

Acoustic feature extraction algorithms (e.g. pitch perturbation jitter, amplitude perturbation shimmer, harmonics-to-noise ratio, Mel-frequency cepstral coefficients, and formant trajectories) depend directly on the analog-to-digital transfer function of the audio capture system. Variations in transducer design, acoustic distance, room reverberation, ADC resolution, frequency bandwidth, and compression algorithms can alter extracted numerical values independently of the participant's vocal pathology.

To ensure reproducible domain identification, every candidate and approved recording domain must be described by a structured acquisition metadata profile.

---

## 2. Field Definitions

| Field Name | Type | Allowed Values / Constraint | Semantic Description |
|---|---|---|---|
| `domain_id` | `string` | Lowercase alphanumeric with underscores (`^[a-z0-9_]+$`) | Canonical unique identifier for the acoustic regime. |
| `domain_name` | `string` | Non-empty text | Human-readable title for documentation and reporting. |
| `domain_category` | `string` | `training_domain`, `candidate_external_domain`, `approved_compatible_domain` | Governance classification. |
| `dataset_id` | `string` | Non-empty text | Unique research repository or collection identifier. |
| `dataset_version` | `string` | Non-empty text | Release version of the underlying dataset. |
| `collection_site_id` | `string` | Non-empty text | Primary institutional or geographical collection site. |
| `country` | `string` | ISO 3166-1 alpha-3 code (e.g. `USA`, `ESP`, `COL`, `ITA`) | Country of data collection. |
| `region` | `string` | State, province, or autonomous community | Sub-national geographic provenance. |
| `collection_period` | `string` | Year range or `historical` | Temporal epoch of acoustic acquisition. |
| `device_category` | `string` | `telephone`, `studio_microphone`, `headset_microphone`, `dynamic_microphone`, `condenser_microphone`, `smartphone`, `laptop_microphone`, `webcam_microphone`, `unknown` | Transducer platform class. |
| `device_manufacturer` | `string` or `null` | E.g. `AKG`, `Shure`, `Apple`, or `null` | Hardware equipment manufacturer. |
| `device_model` | `string` or `null` | E.g. `C520`, `SM48`, `WH20`, or `null` | Specific hardware product model. |
| `microphone_type` | `string` | `electret_condenser`, `dynamic`, `mems`, `carbon_granule`, `unknown` | Physical acoustic transducer operating mechanism. |
| `recording_software` | `string` or `null` | E.g. `Pro Tools`, `Audacity`, or `null` | Software application used to capture digitised stream. |
| `audio_codec` | `string` | `pcm_s16le`, `alaw`, `mulaw`, `aac`, `opus`, `unknown` | Low-level digital audio encoding format. |
| `container_format` | `string` | `wav`, `flac`, `mp3`, `ogg`, `unknown` | File container format. |
| `original_sample_rate` | `integer` or `null` | Positive integer (e.g. `16000`, `44100`, `48000`) or `null` when unverified | Native hardware sampling rate prior to resampling. |
| `bit_depth` | `integer` or `null` | Positive integer (e.g. `16`, `24`) or `null` when unverified | Quantization resolution per audio sample. |
| `channel_count` | `integer` or `null` | Positive integer (typically `1` for mono, `2` for stereo) or `null` when unverified | Number of audio channels. |
| `microphone_distance_cm` | `float` or `null` | Positive float or `null` | Measured mouth-to-microphone distance in centimeters. |
| `microphone_angle_degrees` | `float` or `null` | E.g. `0.0` (on-axis), `45.0` (off-axis) | Geometric orientation relative to acoustic axis. |
| `automatic_gain_control` | `boolean` or `"unknown"` | `true`, `false`, or `"unknown"` | Dynamic range compression / gain normalization status. |
| `noise_suppression` | `boolean` or `"unknown"` | `true`, `false`, or `"unknown"` | Active digital noise cancellation filtering. |
| `compression_enabled` | `boolean` or `"unknown"` | `true`, `false`, or `"unknown"` | Lossy audio codec compression status. |
| `recording_environment` | `string` | `sound_treated_booth`, `clinical_quiet_room`, `domestic_room`, `telephone_network`, `unknown` | Acoustical boundary conditions and reverberation profile. |
| `estimated_background_noise_db` | `float` or `null` | Ambient SPL or SNR in decibels | Estimated noise floor during recording. |
| `protocol_id` | `string` | Non-empty text | Prespecified acoustic phonation protocol identifier. |
| `task_type` | `string` | `sustained_vowel`, `ddk`, `connected_speech`, `vowel_space` | Clinical phonation task class. |
| `language` | `string` | ISO 639-1 two-letter code (e.g. `en`, `es`, `it`) | Primary spoken language of participants. |
| `dialect_metadata` | `string` or `null` | E.g. `north_american`, `castilian`, `colombian` | Regional phonetic and prosodic dialect notes. |

---

## 3. Data Integrity & Privacy Safeguards

1. **Explicit Unknown States:** Fields whose exact physical parameters cannot be verified from authoritative documentation must be set to `null` or `"unknown"`. Fabricating hardware models or acoustic distances is prohibited.
2. **De-Identification:** Domain metadata describes the acoustic environment and recording equipment only. It must never contain patient medical record numbers (MRNs), names, addresses, or individual participant identifiers.
3. **Immutability:** Once registered in `configs/recording_domain_registry.yaml`, a domain profile is immutable unless updated via a version-controlled maintainer commit.
