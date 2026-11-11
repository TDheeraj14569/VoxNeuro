# VoxNeuro Milestone 3: Schema Versioning & Backwards Compatibility Architecture

**Version:** 3.0.0  
**Classification:** Software Architecture & Data Governance Specification  
**Canonical Baseline:** `voxneuro.voice.v3`  
**Multi-Task Release:** `voxneuro.voice.v4`  

---

## 1. Architectural Intent & Core Principles

VoxNeuro Milestone 3 expands the acoustic processing capabilities of the platform to multiple speech tasks while preserving absolute backwards compatibility with existing pipelines, baseline datasets, and trained models.

To achieve this, VoxNeuro adheres to three strict architectural rules:

1. **Strict Immutability of Canonical Core39 (`voxneuro.voice.v3`):**  
   The feature set, definitions, mathematical implementations, ordering, and schema fingerprint of `voxneuro.voice.v3` cannot be modified under any circumstances.
2. **Task-Specific Sub-Schemas:**  
   Each speech paradigm possesses its own independent, versioned sub-schema with a deterministic SHA-256 fingerprint.
3. **Multi-Task Envelope (`voxneuro.voice.v4`):**  
   The v4 envelope serves as a hierarchical container that packages the results of independent tasks without mutating the underlying task schemas.

---

## 2. Schema Hierarchy & Registry

The schema hierarchy for Milestone 3 is structured as follows:

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

### Authoritative Schema Registry

| Schema Name | Version | Feature Count | Deterministic SHA-256 Fingerprint |
| :--- | :--- | :---: | :--- |
| **Sustained Vowel (Canonical)** | `voxneuro.voice.v3` | 39 | `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` |
| **DDK Syllable Repetition** | `voxneuro.task.ddk.v1` | 11 | `b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b` |
| **Connected Speech** | `voxneuro.task.connected_speech.v1` | 20 | `7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1` |
| **Vowel Space Area** | `voxneuro.task.vowel_space.v1` | 16 | `e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993` |
| **Multi-Task Session Envelope** | `voxneuro.voice.v4` | Multi-Task Envelope | `cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429` |

---

## 3. Why Existing Machine Learning Models Cannot Consume v4 Features

A critical scientific boundary enforced in M3 is that **existing research models cannot and must not consume multi-task features directly**:

### 3.1 Feature Vector Dimensionality Mismatch
The verified UAMS research model (`logistic_regression_uams_model.joblib`) was trained on feature vectors of dimensionality $D = 39$, strictly defined by `voxneuro.voice.v3`. Attempting to pass a concatenated or altered feature vector (e.g., 86 features across all 4 tasks) directly violates the input shape expectations of the scikit-learn pipeline, triggering dimension mismatch errors.

### 3.2 Dataset Ground Truth Absence
The raw training cohorts available in the repository (UAMS and UCI) consist exclusively of sustained vowel recordings. **Neither UAMS nor UCI includes diadochokinetic audio, connected speech reading passages, or multi-vowel formant sets.** Therefore, there is zero empirical training data for these new speech paradigms in the current repository.

### 3.3 Protection Against Spurious Inference
Attempting to map multi-task features into a classifier trained on sustained vowels would represent severe clinical invalidity and pseudoscience. To prevent accidental misapplication:
- Model inference scripts reject any feature dictionary that does not strictly match `voxneuro.voice.v3`.
- The multi-task session orchestrator (`analyze_multitask_session`) produces task-isolated outputs without calling any predictive models.
- The Streamlit interface displays descriptive measurements and quality status for M3 tasks, maintaining the rule: `allow_user_microphone_inference: false`.

---

## 4. Encapsulation & Backward Compatibility Guarantees

1. **Legacy Pipeline Compatibility:**  
   Code calling `voxneuro.audio.validation.validate_audio`, `voxneuro.audio.preprocessing.preprocess_audio`, and `voxneuro.features.extractor.extract_features` continues to produce `voxneuro.voice.v3` outputs with unchanged behavior.
2. **Self-Contained Envelope:**  
   When a sustained vowel recording is provided to `analyze_multitask_session`, the resulting `sustained_vowel_a` entry inside `tasks` explicitly tags `task_schema_version: "voxneuro.voice.v3"` and `task_schema_fingerprint: "a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f"`.
3. **Future Extensibility:**  
   When prospective clinical data incorporating multi-task recordings are acquired under protocol `VN-M3-CLIN-001`, task-specific or multi-task models can be cleanly developed using the stable v1/v4 schema interfaces.
