# Milestone 4 Completion Report
## Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference

**Milestone:** 4  
**Project:** VoxNeuro Research Prototype  
**Date of Completion:** 2026-11-12  
**Starting Archive Baseline:** `VoxNeuro_M4_VERIFIED.zip` (repaired from `VoxNeuro_M3_VERIFIED(5).zip`)  
**Starting Archive SHA-256:** `bc53fdea2efe4262f15d2c32288d08dbda0dfeef2b201e586a4badbd41f29167`  
**Target Release Archive:** `VoxNeuro_M4_VERIFIED.zip`  
**Archive Checksum Sidecar:** `VoxNeuro_M4_VERIFIED.zip.sha256`  
**Execution Environment:** Python 3.12.16 (Windows-11-10.0.26200-SP0, AMD64), `uv` package manager  

---

## 1. Executive Summary

Milestone 4 establishes an auditable, fail-closed software architecture for recording-domain validation, quantitative domain-shift analysis, and input capture origin governance in VoxNeuro. While prior milestones established reproducible feature extraction (M1), demographic robustness and bias auditing (M2), and multi-task speech evaluation (M3), Milestone 4 addresses the critical problem of **cross-domain generalization** across divergent recording hardware, transducers, and acoustic environments.

### Authoritative Milestone Statement
> "M4 domain-validation framework implementation and software verification are complete. Independent external recording-domain validation has not been performed. No candidate domain has been approved. Prediction compatibility remains disabled."

No candidate domain is approved, no external cohort has been fabricated, and the system enforces a strict fail-closed safety policy prohibiting live microphone inference or unvetted cross-domain predictions.

---

## 2. Provenance & Cryptographic Fingerprints

| Provenance Component | Value / Checksum (SHA-256) |
|---|---|
| M3 Baseline Archive Checksum | `95d260cf69d62f6f36c2782c974d164437b422277ef329d8d8a7f6da091b6ef9` |
| M4 Prior Archive Checksum | `bc53fdea2efe4262f15d2c32288d08dbda0dfeef2b201e586a4badbd41f29167` |
| Baseline Pipeline Code Fingerprint | `f9cced52e226e87d386e1b1523883d004ea006ca8bf63a42d178c81e054ab3e3` |
| Final M4 Pipeline Code Fingerprint | `72fc3f555729791e95e556627621be595af68d2fe1dada09cb4f340e5c21920e` |
| Frontend Code Fingerprint | `af9abde5877765614b0ac60d32bf7cbc3a37bf4ec2506562ed21467d1be8e62a` |
| Reference Model Artifact (`uams_logistic_research.joblib`) | `eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333` |
| Core39 Sustained Vowel Schema Fingerprint (`voxneuro.voice.v3`) | `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` |
| DDK Schema Fingerprint (`voxneuro.task.ddk.v1`) | `b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b` |
| Connected Speech Schema Fingerprint (`voxneuro.task.connected_speech.v1`) | `7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1` |
| Vowel Space Schema Fingerprint (`voxneuro.task.vowel_space.v1`) | `e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993` |
| Multi-Task Envelope Schema Fingerprint (`voxneuro.voice.v4`) | `cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429` |
| Feature Configuration Fingerprint (`feature_config.yaml`) | `190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9` |
| Audio Preprocessing Fingerprint (`audio_config.yaml`) | `8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d` |
| Domain Registry Document Fingerprint | `82dfd06e97e493aded40b9eccb62d81c3ae64880b52beb365c7416c3a9c6438a` |
| Candidate Assessment Dossier Fingerprint | `ffe46760b1869783dd4aa68f618d8f065348b629f7f8766b9c97b608bf01bb54` |

---

## 3. Four-Tier Recording Domain Architecture

VoxNeuro strictly separates four orthogonal concepts to prevent unsafe cross-domain generalization:

1. **Recording Domain Identifier:** A normalized canonical identifier (`^[a-z0-9_]+$`) denoting a homogeneous acoustic acquisition setup.
2. **Acquisition Metadata Profile:** Detailed physical, electrical, and digital characteristics of the recording chain (transducer type, sample rate, bit depth, codec, gain control, environment).
3. **Input Capture Origin:** The physical origin of an audio buffer presented to the system (`pre_recorded_research`, `controlled_research_session`, `user_upload`, `live_browser_mic`, `live_app_mic`, or `unknown`).
4. **Model Compatibility Approval:** An auditable, human-governed approval state requiring manual cryptographic commitment by maintainers into `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256`.

---

## 4. Recording Domain Registry

The authoritative registry is defined in `configs/recording_domain_registry.yaml` and loaded via `voxneuro.modeling.domain_registry`:

- **Training Domain:** `uams_telephone` (reference telephone-collected development cohort).
- **Candidate External Domains:**
  - `neurovoz_studio`: AKG C420 electret condenser headset in a quiet clinical room (Madrid; Nature Sci Data 2024, PMC11655668).
  - `pc_gita_condenser`: Shure SM63L dynamic omnidirectional microphone in a soundproof booth (Medellin; Orozco-Arroyave et al., PMC10017962, PMC12565443).
  - `italian_parkinsons_headset`: Italian Parkinson's Voice and Speech (IPVS) / Dimauro-Girardi cohort at Univ. of Bari (Studi AISV 2023, vol. 11, pp. 249-268). Device model, sample rate, bit depth, channel count, and audio codec are unknown/null; Samson Meteor specifications from the preceding unrelated study in that volume do not apply to IPVS; task compatibility with sustained `/a/` unverified (`research_evaluation_eligible: false`).
- **Approved Domains:** `[]` (**Strictly Empty**).
- **Inference Eligibility:** Every candidate domain is explicitly marked `inference_eligible: false`.

---

## 5. Candidate External Dataset Eligibility Decisions

Evaluated in `docs/audit/M4_EXTERNAL_DATASET_REGISTER.md`:

| Dataset | Candidate Task | Participants | Clinical Reference | Cohort Origin | Overlap Status | License / Access | Decision |
|---|---|---:|---|---|---|---|---|
| **UAMS Figshare** | Sustained `/a/` | 81 | Confirmed PD | Development reference (USA) | `NOT_APPLICABLE` (Training cohort) | CC BY 4.0 | `INELIGIBLE` (Training reference) |
| **UCI ML #470** | Sustained `/a/` | 252 | Confirmed PD | Turkish cohort (Istanbul) | `NOT_ASSESSED` (Audio withheld) | CC BY 4.0 | `INELIGIBLE` (Audio pipeline; table only) |
| **NeuroVoz** | Sustained vowels, DDK, text | 112 (54 PD, 58 HC) | In-person neurologist | Spanish cohort (Madrid) | `NOT_ASSESSED` (Verification pending) | Controlled DUA required | `ACCESS_PENDING` (Local raw audio withheld) |
| **PC-GITA** | Sustained vowels, DDK, text | 100 | Confirmed PD | Colombian cohort (Medellín) | `NOT_ASSESSED` (Verification pending) | Research agreement required | `ACCESS_PENDING` (Local raw audio withheld) |
| **Italian IPVS** | Vowel phonations, text, `/pa/`, `/ta/` (full DDK unverified) | 65 | Confirmed PD | Italian cohort (Bari) | `NOT_ASSESSED` (Verification pending) | IEEE DataPort access / DUA | `CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED` (Local raw audio withheld; eligible: false) |
| **mPower** | Phone app `/a/` | >1,000 | Self-reported survey | US self-enrolled cohort | `NOT_ASSESSED` | Synapse DUA | `INELIGIBLE` (Self-report invalid; mic unapproved) |

---

## 6. Frozen Reference Model & Validation Protocol

- **Protocol Document:** `docs/M4_INDEPENDENT_DOMAIN_VALIDATION_PROTOCOL.md` (`VOXNEURO-M4-EXT-VAL-2026-V1`).
- **Frozen Reference Model:** L2-regularized logistic regression ($C=0.01$) refit on all 78 valid development participants, bound cryptographically by training receipt SHA-256 and artifact checksum `eaa27193...`.
- **Invariants:** Zero retraining, zero post-hoc threshold selection (threshold fixed at 0.5), zero feature modification.
- **Statistical Methodology:**
  - Participant-level stratified bootstrap ($B=1,000$ iterations, random seed $2026$).
  - 95% empirical percentile confidence intervals.
  - Small-cell suppression ($N < 10$ in any diagnostic subgroup flagged as `UNRELIABLE_SMALL_SAMPLE` to prevent re-identification and unpowered conclusions).

---

## 7. Domain Shift Analysis Engine

Implemented in `src/voxneuro/modeling/domain_shift.py`:
- **Acquisition Comparison:** Structural comparison of transducers, sampling rates, codecs, and acoustic environments.
- **Feature-Level Shift:**
  - Standardized Mean Difference (Cohen's $d$) with pooled variance.
  - Two-sample Kolmogorov–Smirnov (KS) distributional divergence tests.
  - Dual multiplicity corrections: Benjamini–Hochberg False Discovery Rate ($q \le 0.05$) and Bonferroni FWER adjustment.
- **Methodological Invariant:** Non-significant distribution shift tests ($p > 0.05$) are **never** interpreted as proof of domain equivalence.
- **Empirical Evaluation Status:** Recording acquisition differences have been characterized from available dataset documentation. Empirical external feature-distribution comparison has not been performed because no eligible independent external feature dataset is available locally. Zero SMD or KS statistics are not described as evidence of compatibility, and a lack of observed statistical shift never establishes domain equivalence.

---

## 8. Inference Safety & Fail-Closed Protection

Implemented in `src/voxneuro/modeling/prediction.py`:
- **Input Capture Context:** All inference requests require an explicit `InputCaptureContext`.
- **Fail-Closed Origins:** Capture origins `user_upload`, `live_browser_mic`, `live_app_mic`, and `unknown` are unconditionally rejected.
- **Microphone Policy:** `allow_user_microphone_inference` remains `false` in `configs/model_config.yaml`.
- **Trusted Allowlist:** `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` remains `frozenset()`.
- **Separation of Evidence:** Candidate assessment dossiers (`voxneuro.domain_assessment.v1`) are structurally rejected by `load_domain_validation_report()` and cannot approve a bundle.

---

## 9. Verification & Automated Test Summary

All repository tests pass without failure in the local verification run (`review_evidence/m4_safety_gate_test_summary.json`):
- **Prior Tests (M0–M3):** 402 passed
- **Milestone 4 & Acceptance Unit Tests:** 70 passed (`test_domain_registry.py`, `test_domain_assessment.py`, `test_domain_shift.py`, `test_external_evaluation.py`, `test_inference_capture_context.py`, `test_m4_provenance_and_roster_binding.py`, `test_m4_trust_registry.py`)
- **Milestone 4 Integration Tests:** 5 passed
- **Private Dataset Dependent Tests:** 55 passed (run locally; excluded tests skip/adapt when private datasets are omitted from source-only clean-room packages)
- **Private Model Dependent Tests:** 31 passed (fail closed to `MODEL_ARTIFACT_NOT_VERIFIED` if private model binary is absent)
- **Streamlit Frontend Tests:** 14 passed
- **Total Local Test Count:** **577 passed in 128.12s** (0 failed, 0 errors, 0 skipped).
- **Source Provenance & DUA Gate Hardening:** `create_participant_independence_attestation()` and `verify_participant_independence_attestation()` bind directly to signed `AuthorizationTrustRegistry` sources/reviewers and live source roster files (SHA-256 byte check, normalized ID recomputation); `verify_evaluation_provenance_receipt()` enforces authoritative SQLite `dataset_access` verification (`DATASET_AUTHORIZATION_NOT_VERIFIED`), 12-point cross-binding against signed `AuthorizedSourceRecord` entries, `dua_verification_status == "DOCUMENT_AUTHENTICATED"`, and actual DUA document artifact SHA-256 verification.
- **Linting & Formatting:** 100% clean (`ruff check .`, `ruff format --check .`).

---

## 10. Privacy Audit

- **Zero PII Exposure:** No participant names, MRNs, or raw audio waveforms are stored in review evidence or git-tracked directories.
- **Cross-Platform Sanitization:** `scripts/generate_m4_review_evidence.py` sanitizes host paths cross-platform (`sanitize_target_path`), preventing leakage of absolute local paths.
- **Clean Inclusions:** Generated evidence files contain only aggregate metadata, schema fingerprints, and test execution summaries.

---

## 11. Final Acceptance Checklist

### Architecture
- [x] Explicit domain registry implemented (`configs/recording_domain_registry.yaml`, `src/voxneuro/modeling/domain_registry.py`).
- [x] Structured acquisition metadata schema (`voxneuro.domain_metadata.v1`).
- [x] Recording origin separated from domain ID (`InputCaptureContext`).
- [x] Candidate and approved domains strictly separated.
- [x] Versioned candidate assessment dossier schema (`voxneuro.domain_assessment.v1`).

### Dataset & Evaluation
- [x] Candidate dataset eligibility evaluated in `docs/audit/M4_EXTERNAL_DATASET_REGISTER.md`.
- [x] DUA and licensing requirements strictly respected; zero data fabrication.
- [x] Pre-registered frozen evaluation protocol (`VOXNEURO-M4-EXT-VAL-2026-V1`).
- [x] Participant-level bootstrap ($B=1,000$) uncertainty and small-cell suppression implemented.
- [x] Domain-shift engine with Cohen's $d$, KS tests, and FDR/Bonferroni corrections implemented.

### Safety & Governance
- [x] `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` remains strictly empty (`frozenset()`).
- [x] `allow_user_microphone_inference` remains `false`.
- [x] Live microphone, browser audio, and user uploads fail closed.
- [x] Candidate dossiers cannot approve prediction compatibility.
- [x] No automated tool can transition a domain to approved status.

### Distribution
- [x] M1, M2, and M3 evidence preserved.
- [x] M4 review evidence generated and hashed.
- [x] Review bundle builder extended to support `--milestone m4`.
- [x] Clean-room verification protocol ready.

---

## 12. Final Milestone 4 Verified Release Deliverables

| Deliverable Artifact | Description | Target Path |
|---|---|---|
| **Release Archive** | Clean-room reproducible source + review evidence bundle | `VoxNeuro_M4_VERIFIED.zip` |
| **Checksum Sidecar** | SHA-256 cryptographic digest | `VoxNeuro_M4_VERIFIED.zip.sha256` |
| **Audit Dossier** | Independent domain assessment dossier (`voxneuro.domain_assessment.v1`) | `review_evidence/m4_domain_assessment.json` |
| **Domain Registry** | Recording domain registry (`voxneuro.domain_metadata.v1`) | `configs/recording_domain_registry.yaml` |
| **Domain Registry Snapshot** | JSON snapshot of parsed recording domain registry | `review_evidence/m4_domain_registry.json` |
| **Shift Summary (CSV)** | Structural acquisition comparison and pending shift metrics | `review_evidence/m4_domain_shift_summary.csv` |
| **Shift Summary (JSON)** | Domain-shift status and candidate comparison metadata | `review_evidence/m4_domain_shift_summary.json` |
| **Safety Test Summary** | Automated safety-gate unit & integration test run results | `review_evidence/m4_safety_gate_test_summary.json` |
| **Provenance Summary** | Cryptographic fingerprints of code, schemas, and models | `review_evidence/m4_provenance_summary.json` |
| **Review Manifest** | Complete cryptographic manifest of review evidence | `review_evidence/m4_review_manifest.json` |

