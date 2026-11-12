# M5 Baseline Verification Report

**Milestone:** 5 (Privacy-Preserving Longitudinal Cohort Management and Research Study Operations)  
**Baseline Archive Checksum (SHA-256):** `d17629352da2303e6de8716bf2a6675aa3b6ba19c6586e0a08012e3c279b5c22`  
**Starting Archive Reference:** `VoxNeuro_M4_VERIFIED(1).zip`  
**Generated UTC:** 2026-11-12T08:00:00Z  
**Verification Environment:** Python 3.12.16 (Windows-11-10.0.26200-SP0, AMD64), `uv` package manager  

---

## 1. Executive Baseline Summary

This baseline audit documents the starting state of the VoxNeuro repository prior to the execution of Milestone 5. 

Milestone 4 established independent recording-domain validation, candidate assessment dossiers, domain-shift analysis, and fail-closed inference protection. Milestone 5 extends VoxNeuro into an enterprise-grade, privacy-preserving research-study operations platform supporting longitudinal cohort management, Data Use Agreements (DUA), informed consent state machines, protocol version immutability, operational QC tracking, small-cell suppression ($N < 10$), and cryptographic processing run receipts.

Prior to implementing Milestone 5, all Part B prerequisite repairs on Milestone 4 metadata were executed and verified:
1. **NeuroVoz Hardware & Environment Reconciliation:** Transducer corrected to AKG C420 electret condenser headset mic; environment documented as quiet clinical examination room (Nature *Scientific Data* 2024, DOI: 10.1038/s41597-024-04186-z, PMCID: PMC11655668).
2. **PC-GITA Transducer & Environment Reconciliation:** Transducer corrected to Shure SM63L dynamic omnidirectional mic; soundproof booth with M-Audio C400 audio interface documented (Orozco-Arroyave et al., CSL 2014, PMCID: PMC10017962, PMC12565443).
3. **Italian Dataset De-conflation:** Clarified identity of 65-speaker IPVS dataset (Dimauro & Girardi, Univ. of Bari, IEEE DataPort DOI: 10.21227/m293-hp19), separated from unrelated Rome/Turin Shure WH20 studies (Suppa et al., PMC8886162), and set `candidate_compatibility_status: "CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED"`.
4. **Structured Provenance References:** Implemented `DomainSourceReference` dataclass in domain registry.
5. **Fail-Closed Evaluation Gate:** Enforced cryptographic `EvaluationProvenanceReceipt` and pseudonymous salted participant independence verification.
6. **Model Provenance Reconciliation:** Reconciled reference model checksum `eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333` across all audit dossiers and completion reports.

---

## 2. Baseline Environment & Integrity Checksums

| Component | Identifier / Value |
|---|---|
| Python Runtime | `3.12.16` |
| Operating System | Windows 11 (AMD64) |
| Starting Archive SHA-256 | `d17629352da2303e6de8716bf2a6675aa3b6ba19c6586e0a08012e3c279b5c22` |
| Reference Model Artifact (`uams_logistic_research.joblib`) SHA-256 | `eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333` |
| Training Dataset Checksum SHA-256 | `d83d37e901ab2e5ec2499f070bd507b1c5c2b754dda36d115184f57a1383ab77` |
| Training Evaluation Receipt Combined SHA-256 | `c73146c1a94e235dc0262877dfa5e4a425fff0a3019ab76e38ea51c22cacba80` |

---

## 3. Schema & Configuration Fingerprints

| Schema / Configuration | Version / Name | Deterministic Fingerprint (SHA-256) |
|---|---|---|
| Core39 Sustained Vowel Schema | `voxneuro.voice.v3` | `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` |
| DDK Feature Schema | `voxneuro.task.ddk.v1` | `b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b` |
| Connected Speech Feature Schema | `voxneuro.task.connected_speech.v1` | `7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1` |
| Vowel Space Area Feature Schema | `voxneuro.task.vowel_space.v1` | `e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993` |
| Multi-Task Envelope Schema | `voxneuro.voice.v4` | `cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429` |
| Audio Preprocessing Configuration | `audio_config.yaml` | `8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d` |
| Feature Extraction Configuration | `feature_config.yaml` | `190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9` |
| Model Training Configuration | `model_config.yaml` | `069ce3100bf04d4588f29673791b4a12f073fc5d824ced3bdb8c31141dccc3c3` |
| Application Configuration | `application_config.yaml` | `6abd65929340529b8ae271687a3cdccf6d895d519f9f02419555c96e87d4195f` |

---

## 4. Current Domain Safety & Policy State

- `allow_user_microphone_inference: false` strictly enforced.
- `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()` strictly empty.
- `approved_domains: []` strictly empty in configuration.
- Reference model prediction is restricted exclusively to validated UAMS research cohort participants.
- External validation candidate dossiers remain in pending status (`FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING`).
