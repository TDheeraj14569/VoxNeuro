# Milestone 4 Final Acceptance Repair Report
## Domain Metadata Correction, Metadata Provenance, External Evaluation Gating, and Model Provenance Reconciliation

**Milestone:** M4 Final Acceptance Repair  
**Date:** 2026-11-12  
**Baseline Archive Checksum:** `d17629352da2303e6de8716bf2a6675aa3b6ba19c6586e0a08012e3c279b5c22`  
**Status:** **ACCEPTANCE PREREQUISITE COMPLETED**  

---

## 1. Executive Summary

Prior to initiating Milestone 5, a comprehensive audit and repair of the Milestone 4 baseline was executed in accordance with Part B of the project specification:
1. **NeuroVoz Metadata & Provenance:** Corrected microphone model from AKG C520 to AKG C420 electret condenser headset; corrected acoustic environment to quiet clinical room (not sound-treated booth, mean SNR 24.3 dB); added complete literature references (Nature Scientific Data 2024, DOI: 10.1038/s41597-024-04186-z, PMCID: PMC11655668).
2. **PC-GITA Metadata & Provenance:** Corrected microphone from Shure SM48 to Shure SM63L dynamic omnidirectional microphone; documented M-Audio Fast Track C400 interface and sound-treated booth conditions; added authoritative literature citations (Orozco-Arroyave et al., CSL 2014, PMCID: PMC10017962, PMC12565443).
3. **Italian Dataset Identity & Task Compatibility:** Resolved historical conflation between the 65-speaker Italian Parkinson's Voice and Speech (IPVS) dataset by Dimauro & Girardi (University of Bari, IEEE DataPort DOI: 10.21227/m293-hp19) and unrelated Rome/Turin studies (Suppa et al., PMC8886162) utilizing a Shure WH20 headset. Because hardware specifications and task compatibility with sustained `/a/` Core39 are unverified in published open metadata, the domain was accurately set to `CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED` and `research_evaluation_eligible: false`.
4. **Structured Metadata Provenance:** Implemented `DomainSourceReference` dataclass and integrated structured provenance sources across all registered domains in `configs/recording_domain_registry.yaml`.
5. **Fail-Closed External Evaluation Provenance Gate:** Implemented `EvaluationProvenanceReceipt`, `verify_evaluation_provenance_receipt()`, and privacy-preserving pseudonymous participant independence verification `verify_participant_independence()`. Enforced `--receipt-path` in `scripts/evaluate_external_domain.py`.
6. **Frozen Reference Model Reconciliation:** Fully reconciled the model artifact SHA-256 (`eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333`), documenting the historical transition from the initial pre-refit checksum (`d6eb5bcd...`) to the verified 78-participant L2-regularized logistic regression refit.

---

## 2. Detailed Audit and Repair Log

### 2.1 NeuroVoz Metadata Correction
- **Previous Specification:** AKG C520 headset mic in sound-treated booth.
- **Corrected Specification:** AKG C420 electret condenser headset mic, phantom-powered preamplifier, Creative SoundBlaster Live soundcard, 44.1 kHz, 16-bit PCM. Recorded in quiet clinical room (Hospital General Universitario Gregorio Marañón, Madrid), not acoustically isolated.
- **Authoritative Citation:**
  - *NeuroVoz: a Castillian Spanish corpus of parkinsonian speech*, Scientific Data (Nature), December 2024.
  - DOI: `10.1038/s41597-024-04186-z`
  - PMCID: `PMC11655668`
  - Cohort: 112 native Spanish speakers (54 PD, 58 HC).

### 2.2 PC-GITA Metadata Correction
- **Previous Specification:** Shure SM48 dynamic mic in quiet room.
- **Corrected Specification:** Shure SM63L dynamic omnidirectional mic, M-Audio Fast Track C400 audio interface, 44.1 kHz, 16-bit PCM. Recorded in sound-treated booth under controlled acoustic conditions.
- **Authoritative Citations:**
  - *PC-GITA: A Spanish speech database for the automatic analysis of Parkinson's disease*, Computer Speech & Language, 2014.
  - DOI: `10.1016/j.csl.2014.07.003`
  - PMCID: `PMC10017962`, `PMC12565443`
  - Cohort: 100 native Colombian Spanish speakers (50 PD, 50 HC; 25M/25F in each group, age-matched).

### 2.3 Italian Parkinson's Voice Corpus De-Conflation
- **Previous Specification:** Claimed 50 participants (28 PD, 22 HC), Turin collection site, Shure WH20 headset, sustained vowel task.
- **Investigation Finding:** Two distinct Italian research lines were previously conflated:
  1. *IPVS Dataset:* Giovanni Dimauro & Francesco Girardi, University of Bari (IEEE DataPort DOI: 10.21227/m293-hp19). 65 native Italian speakers (28 PD, 22 elderly HC, 15 young HC). Transducer and acoustic room specifications are not conclusively documented in published open metadata.
  2. *Rome/Turin Studies:* Antonio Suppa, Giovanni Costantini, PoliTO / Sapienza University of Rome / Tor Vergata (Frontiers in Neurology 2022, PMC8886162). Used Shure WH20 headset in private clinical studies.
- **Corrected Status:**
  - Registered as `italian_parkinsons_headset`: Italian Parkinson's Voice and Speech (IPVS) Domain.
  - Collection Site: `uniba_bari` (University of Bari, Apulia, Italy).
  - Hardware & Audio Parameters: Set to `device_manufacturer: null`, `device_model: null`, `device_category: "unknown"`, `microphone_type: "unknown"`, `original_sample_rate: null`, `bit_depth: null`, `channel_count: null`, `audio_codec: "unknown"`, and `recording_environment: "unknown"` (strictly separated from unrelated Samson Meteor Studi AISV 2023 and Rome/Turin Shure WH20 studies).
  - Task Compatibility: Published documentation describes vowel phonations, text reading, and isolated syllables `/pa/`, `/ta/`; full `/pa-ta-ka/` DDK and Core39 sustained `/a/` compatibility remain unverified.
  - Status: `CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED`.
  - Eligibility: `research_evaluation_eligible: false`.

### 2.4 Provenance Gate & Participant Independence Verification
- **Receipt Specification:** `EvaluationProvenanceReceipt` dataclass requires:
  - Candidate domain ID and dataset ID/version.
  - Dataset authorization status (`AUTHORIZED_DUA`, `AUTHORIZED_OPEN_DATA`).
  - Feature schema version and fingerprint.
  - Reference and candidate feature table SHA-256 digests.
  - Participant-level overlap status (`VERIFIED_DISJOINT`).
  - Zero duplicate recordings and zero duplicate participants.
- **Independence Check:** `verify_participant_independence()` implements privacy-preserving salted pseudonymous hashing (HMAC/SHA-256 with salt) to verify disjoint participant cohorts without exposing PII.
- **CLI Gate:** `scripts/evaluate_external_domain.py` unconditionally requires `--receipt-path` when `--features-path` is passed, failing closed if the receipt is missing, tampered, or indicates unverified independence.

### 2.5 Model Provenance Reconciliation
- **Artifact:** `artifacts/models/uams_logistic_research.joblib`
- **Verified SHA-256:** `eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333`
- **Historical Transition:** The earlier hash `d6eb5bcd...` was recorded during initial baseline derivation prior to refitting on all 78 valid development participants ($C=0.01$, balanced accuracy inner CV 75.96%, dataset checksum `d83d37e9...`, training receipt `6e82cf4d...`). The artifact checksum is now authoritatively bound in code (`FROZEN_REFERENCE_MODEL_SHA256`) and verified across all reports.

---

## 3. Safety Invariants Confirmed

- `allow_user_microphone_inference`: `false` (Strictly enforced)
- `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256`: `frozenset()` (Strictly empty)
- `approved_domains`: `[]` (Strictly empty)
- Candidate domains: `inference_eligible: false` (All candidate domains locked)
- External validation status: `FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING`
