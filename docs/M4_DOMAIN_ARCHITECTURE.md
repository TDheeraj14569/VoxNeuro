# Recording-Domain Architecture Specification

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Status:** Frozen Specification  
**Version:** 1.0.0  
**Scope:** Architecture for recording domain registry, acquisition metadata, capture origins, and model compatibility governance.

---

## 1. Architectural Principles

In bioacoustic machine learning, acoustic features derived from voice recordings are sensitive not only to physiological characteristics of phonation, but also to the physics of sound capture and processing. Variation in recording equipment, acoustic transducer design, spatial distance, room acoustics, anti-aliasing filters, automatic gain control (AGC), audio compression codecs, and analog-to-digital converters can induce severe covariate and concept shifts.

To prevent invalid cross-domain application, VoxNeuro enforces an architectural separation between four independent concepts:

1. **Recording Domain Identifier:** A standardized canonical identifier denoting a distinct, homogeneous acoustic acquisition regime.
2. **Acquisition Metadata:** A structured schema characterizing the physical, environmental, electrical, and digital properties of the recording pipeline.
3. **Capture Origin:** The provenance of the audio input buffer or file presented to the system (e.g. pre-recorded research corpus vs. user upload vs. live client microphone).
4. **Model Compatibility Approval:** An auditable, non-automated governance state establishing whether a frozen model bundle is authorized to evaluate inputs from a given domain.

```
+-----------------------------------------------------------------------------------+
|                              INPUT ACOUSTIC RECORD                                |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+------------------------+  +------------------------+  +---------------------------+
|   RECORDING DOMAIN     |  |   ACQUISITION          |  |   CAPTURE ORIGIN          |
|   IDENTIFIER           |  |   METADATA             |  |                           |
|   (e.g.,               |  |   (Transducer, room,   |  |   (Research file vs.      |
|    uams_telephone)     |  |    codec, rate, AGC)   |  |    user upload vs. mic)   |
+------------------------+  +------------------------+  +---------------------------+
             \                          |                          /
              \                         |                         /
               v                        v                        v
+-----------------------------------------------------------------------------------+
|                        FAIL-CLOSED INFERENCE SAFETY GATE                          |
|  - Is domain in approved registry?                                                |
|  - Does cryptographic validation report SHA-256 match trusted maintainer allowlist|
|  - Is capture origin eligible for inference? (Mic / unknown = REJECT)             |
|  - Are schema fingerprints and preprocessing configurations identical?            |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
                         [ PERMIT / REJECT INFERENCE ]
```

---

## 2. Component Specifications

### 2.1 Recording-Domain Identifier

- **Format:** Canonical identifiers must consist of lowercase alphanumeric ASCII words separated strictly by single underscores (`^[a-z0-9]+(_[a-z0-9]+)*$`).
- **Normalization:** Evaluated using `canonicalize_domain()`. Trailing, leading, or consecutive non-alphanumeric characters are stripped and collapsed.
- **Independence from Personal Data:** Domain identifiers must never incorporate participant names, medical record numbers (MRNs), hospital visit codes, or direct personal identifiers.
- **Reference Domains:**
  - `uams_telephone`: Reference development cohort (UAMS Figshare 10.6084/m9.figshare.23849127.v1).
  - `neurovoz_studio`: Candidate studio acoustic recording domain (NeuroVoz corpus).
  - `pc_gita_condenser`: Candidate controlled clinic condenser microphone domain (PC-GITA corpus).
  - `italian_parkinsons_headset`: Candidate Italian headset acoustic domain.

### 2.2 Acquisition Metadata Schema

Every recording domain is defined by an acquisition metadata profile adhering to standard engineering classifications:

```yaml
domain_id: string
dataset_id: string
dataset_version: string
collection_site_id: string
country: string
region: string
collection_period: string

device_manufacturer: string | null
device_model: string | null
device_category: "telephone" | "studio_microphone" | "headset_microphone" | "smartphone" | "laptop_microphone" | "unknown"
microphone_type: "dynamic" | "electret_condenser" | "mems" | "carbon_granule" | "unknown"
recording_software: string | null
recording_software_version: string | null

audio_codec: "pcm_s16le" | "alaw" | "mulaw" | "aac" | "opus" | "unknown"
container_format: "wav" | "flac" | "mp3" | "ogg" | "unknown"
original_sample_rate: integer
bit_depth: integer
channel_count: integer

microphone_distance_cm: float | null
microphone_angle_degrees: float | null
automatic_gain_control: boolean | "unknown"
noise_suppression: boolean | "unknown"
compression_enabled: boolean | "unknown"

recording_environment: "sound_treated_booth" | "clinical_quiet_room" | "domestic_room" | "telephone_network" | "unknown"
estimated_background_noise_db: float | null
protocol_id: string
task_type: "sustained_vowel" | "ddk" | "connected_speech" | "vowel_space"
language: string
dialect_metadata: string | null
```

All missing or unverified fields must be populated with explicit `null` or `"unknown"` values. Device specifications must never be fabricated.

### 2.3 Input Capture Origin

The physical provenance of an audio buffer cannot be inferred from a file container extension alone. An uploaded `.wav` file might represent a digitised 1990s telephone recording, an uncompressed laboratory DAT recording, or a smartphone voice memo recorded in a reverberant kitchen.

VoxNeuro distinguishes six explicit capture origins:

| Capture Origin Enum | Description | Default Inference Eligibility |
|---|---|---|
| `pre_recorded_research` | Authentic pre-recorded audio from an identified, licensed research repository. | Dependent on domain approval |
| `controlled_research_session` | Prospective recording collected under an IRB-approved research protocol with calibrated hardware. | Dependent on domain approval |
| `user_upload` | Ad-hoc audio file provided by an interactive user via file upload. | **INELIGIBLE** (`false`) |
| `live_browser_mic` | Audio stream captured in real time via WebRTC `getUserMedia()` or browser audio API. | **INELIGIBLE** (`false`) |
| `live_app_mic` | Audio stream captured via native operating system audio capture interface (e.g. PyAudio, sounddevice). | **INELIGIBLE** (`false`) |
| `unknown` | Audio with unspecified or missing capture provenance. | **INELIGIBLE** (`false`) |

**Fail-Closed Rule:** If an input's capture origin is `unknown`, `user_upload`, `live_browser_mic`, or `live_app_mic`, model inference is rejected immediately, even if the user specifies a valid domain identifier.

### 2.4 Governance & Prediction Eligibility

Model compatibility requires human maintainer review and explicit cryptographic authorization. The system tracks four independent status fields for each domain:

1. `research_evaluation_eligible`: Indicates whether offline research evaluation can be conducted on local research audio files.
2. `candidate_compatibility_status`: The scientific evaluation status of the domain (e.g. `PENDING`, `EVALUATED`, `INCOMPATIBLE`).
3. `inference_eligible`: A strict runtime boolean. For any newly assessed or candidate external domain in M4, `inference_eligible` is strictly `false`.
4. `human_review_status`: The maintainer sign-off state (e.g. `UNREVIEWED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`).

---

## 3. Cryptographic Evidence Separation

To avoid privilege escalation:

- Candidate assessment dossiers conform to the `voxneuro.domain_assessment.v1` schema.
- Approved prediction compatibility reports conform to the `load_domain_validation_report` parser specification.
- The two schemas are cryptographically and syntactically distinct. Passing a candidate assessment dossier to `load_domain_validation_report()` or `make_bundle()` will trigger a validation exception and fail closed.
- The trusted domain allowlist (`TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256`) in `src/voxneuro/modeling/domains.py` remains empty (`frozenset()`). No automation, script, or test is permitted to add a hash to this set.
