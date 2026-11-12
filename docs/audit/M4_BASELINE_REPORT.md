# M4 Baseline Verification Report

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Baseline Archive Checksum (SHA-256):** `95d260cf69d62f6f36c2782c974d164437b422277ef329d8d8a7f6da091b6ef9`  
**Starting Archive Reference:** `VoxNeuro_M3_VERIFIED(5).zip`  
**Generated UTC:** 2026-11-12T03:15:00Z  
**Verification Environment:** Python 3.12.16 (Windows-11-10.0.26200-SP0, AMD64), `uv` package manager  

---

## 1. Executive Baseline Summary

This baseline audit documents the starting state of the VoxNeuro repository prior to the execution of Milestone 4. Milestone 3 introduced multi-task acoustic analysis (`voxneuro.voice.v4` envelope covering sustained vowel, DDK, connected speech, and vowel space area) and established reproducible provenance. Milestone 4 focuses on independent recording-domain validation, domain-shift characterization, cryptographic evidence verification, and fail-closed inference safety.

All baseline integrity, schema fingerprint, provenance, model, and test verification checks passed with zero errors.

---

## 2. Baseline Environment & Integrity Checksums

| Component | Identifier / Value |
|---|---|
| Python Runtime | `3.12.16` |
| Operating System | Windows 11 (AMD64) |
| Starting Archive SHA-256 | `95d260cf69d62f6f36c2782c974d164437b422277ef329d8d8a7f6da091b6ef9` |
| Project Source Fingerprint (`code_version`) | `f9cced52e226e87d386e1b1523883d004ea006ca8bf63a42d178c81e054ab3e3` |
| Frontend Code Fingerprint | `af9abde5877765614b0ac60d32bf7cbc3a37bf4ec2506562ed21467d1be8e62a` |
| Reference Model Artifact (`uams_logistic_research.joblib`) SHA-256 | `d6eb5bcd7f616c71f69cc6cd2f944e7f475ecc0774e7dc8afe51b64dd061787f` |
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

- **Trusted Domain Allowlist (`TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256`):** `frozenset()` (strictly empty, length 0).
- **User Microphone Inference Policy (`allow_user_microphone_inference`):** `false` in `configs/model_config.yaml`.
- **Model Bundle Domain Status:**
  - `research_only`: `true`
  - `domain_compatibility_verified`: `false`
  - `validated_input_domains`: `[]`
  - `allow_user_microphone_inference`: `false`
- **Inference Protection:** Fail-closed on missing, unapproved, or microphone-derived domains.

---

## 5. Baseline Test Execution Results

- **Command:** `uv run pytest`
- **Total Test Items:** 433
- **Passed:** 433
- **Failed:** 0
- **Errors:** 0
- **Duration:** ~77 seconds
- **Verification Scripts:**
  - `uv run python scripts/verify_project.py` -> PASS (10 required files, provenance match)
  - `uv run python scripts/verify_model.py` -> PASS (bundle reload, prediction consistency, artifact checksum, research-only status)

All baseline verification requirements are confirmed. Baseline is frozen and ready for Milestone 4.
