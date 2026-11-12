# Milestone 5 Completion Report
## Privacy-Preserving Longitudinal Cohort Management, Research Study Operations and Verified Release

**Milestone:** 5  
**Project:** VoxNeuro Research Prototype  
**Date of Completion:** 2026-11-12  
**Starting Archive Baseline:** `VoxNeuro_M5_VERIFIED(2).zip`  
**Starting Archive SHA-256:** `19b49228fccb33f52d89ddacb3dc77fad00f5597e5895ce02f70ceaafbab8a61`  
**M4 Baseline Archive SHA-256:** `bc53fdea2efe4262f15d2c32288d08dbda0dfeef2b201e586a4badbd41f29167`  
**Target Release Archive:** `VoxNeuro_M5_VERIFIED.zip`  
**Archive Checksum Sidecar:** `VoxNeuro_M5_VERIFIED.zip.sha256`  
**Execution Environment:** Python 3.12.16 (Windows-11-10.0.26200-SP0, AMD64), `uv` package manager  

---

## 1. Executive Summary

Milestone 5 establishes an enterprise-grade, privacy-preserving research-study operations and longitudinal cohort-management platform within the VoxNeuro speech analysis ecosystem.

While prior milestones developed feature extraction pipelines (M1), demographic robustness analyses (M2), multi-task speech analysis with schema v4 (M3), and recording-domain validation with fail-closed safety restrictions (M4), Milestone 5 provides the operational, governance, and data-lifecycle infrastructure necessary to conduct real-world observational speech biomarker studies.

### Authoritative Milestone Statement
> "Milestone 5 research study operations, longitudinal tracking, protocol immutability, consent governance, and privacy auditing architectures are fully implemented and verified. All acoustic changes over time are strictly descriptive intra-individual measurements. VoxNeuro remains a non-diagnostic research prototype. No disease progression or therapeutic efficacy claims are supported."

---

## 2. Key Deliverables & Implementation Highlights

### 2.1 Relational Study Architecture (`voxneuro.study`)
- Implemented a 12-table relational schema under SQLite with enforced foreign key constraints (`PRAGMA foreign_keys = ON;`) and versioned SQL migration runners.
- Tables implemented:
  1. `schema_migrations`: Versioned migration execution tracker.
  2. `protocols`: Immutable scientific protocol specifications.
  3. `studies`: Research study entities governing cohorts and data policies.
  4. `participants`: Pseudonymous participant records with zero PII.
  5. `consents`: Cryptographically traceable informed consent records.
  6. `dataset_access`: Data Use Agreements (DUA) and dataset authorizations.
  7. `sessions`: Longitudinal research visit sessions.
  8. `task_recordings`: Task-specific execution and screening records.
  9. `derived_features`: Extracted acoustic feature vectors (zero raw audio).
  10. `processing_runs`: Immutable `ProcessingRunReceipt` cryptographic provenance.
  11. `audit_log`: Privacy-sanitized relational event trail.
  12. `tombstones`: Cryptographic records of consent withdrawal and feature erasure.

### 2.2 Protocol Immutability & Safety
- Protocols specify permitted speech tasks (`sustained_vowel`, `ddk`, `connected_speech`, `vowel_space`), visit schedule constraints, and operational instructions.
- Immutability Enforcement: If research sessions exist under a study's protocol version, updating the protocol version on that study is strictly prohibited (`ValueError`), preventing protocol drift in longitudinal cohorts.

### 2.3 Informed Consent & DUA Dual-Gate Authorization
- Ingestion of speech task recordings is fail-closed: it requires both active participant consent for the specific task and approved institutional DUA authorization.
- Consent revocation workflow immediately halts processing, marks existing sessions `RESTRICTED_WITHDRAWN`, purges derived features, and creates an irreversible tombstone record.

### 2.4 Longitudinal Tracking & Operational QC
- Computes intra-individual acoustic deltas ($\Delta = \text{Visit}_k - \text{Visit}_1$) alongside empirical visit interval statistics.
- Strict Small-Cell Suppression ($N < 10$): Frequencies between 1 and 9 are suppressed as `< 10 (Suppressed)` across all reports and CSV exports.
- Non-progression guarantee: Acoustic changes are explicitly marked as exploratory physical measurements, barring clinical worsening inferences.

### 2.5 Seven Structured Research Reports
- Comprehensive reporting module generating both JSON and CSV exports:
  1. Study Overview Report
  2. Session Completion Report
  3. Task-Level QC Report
  4. Cohort Attrition Report
  5. Longitudinal Descriptive Report
  6. Data Provenance & Processing Run Report
  7. Consent & Dataset Authorization Status Report

---

## 3. Cryptographic Provenance & Schema Fingerprints

| Component / Artifact | Identifier / Value |
|---|---|
| M4 Starting Baseline Checksum (SHA-256) | `bc53fdea2efe4262f15d2c32288d08dbda0dfeef2b201e586a4badbd41f29167` |
| M5(4) Input Baseline Checksum (SHA-256) | `ac000a446470e0568f49059138d4df2fefec76016afd02b63c84839cbcfffa08` |
| Project Code Fingerprint | `c112d43bcb519790c25934c0b2e56216013a0999c7004f293d5d52f3ea546416` |
| Dependency Lockfile Fingerprint (`uv.lock`) | `bfe40d59826377274e4bb7ebf19c3d37363f707a0042d1254fcec7f4ede0b5a0` |
| Reference Model Artifact (`uams_logistic_research.joblib`) | `eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333` |
| Sustained Vowel Core39 Schema Fingerprint (`voxneuro.voice.v3`) | `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f` |
| DDK Feature Schema Fingerprint (`voxneuro.task.ddk.v1`) | `b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b` |
| Connected Speech Schema Fingerprint (`voxneuro.task.connected_speech.v1`) | `7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1` |
| Vowel Space Area Schema Fingerprint (`voxneuro.task.vowel_space.v1`) | `e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993` |
| Multi-Task Envelope Schema Fingerprint (`voxneuro.voice.v4`) | `cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429` |
| Audio Preprocessing Configuration Fingerprint (`audio_config.yaml`) | `8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d` |
| Feature Extraction Configuration Fingerprint (`feature_config.yaml`) | `190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9` |
| Migration `001_initial_study_schema.sql` (SHA-256) | `0ea66b31eb6b7c2f98fafea552b26b3db681411b9f5682e362f98da1d0470b7e` |
| Migration `002_participant_study_constraints.sql` (SHA-256) | `8d6fdf8562edc8d95ca454eae39f21195bef8b633bfc8c523efcde2790a0ab6b` |
| Migration `003_composite_foreign_keys_and_retention_defaults.sql` (SHA-256) | `d6de922504e4183a9e7b7ccd037e0b197fced8818447ed7377fc2080bf23092f` |
| Migration `004_dataset_access_dua_fingerprint.sql` (SHA-256) | `7caf2b6d9decb7937cdcfc717ef26d2704ae71e9eeb9070e9167829709693451` |
| Migration `005_dataset_access_registry_binding.sql` (SHA-256) | `7de84098bef1eca67a79228242ceac22400868b3dc3b064c1adba64f2e781cef` |

---

## 4. Verification Summary

- **Automated Test Suite:** 577 passed, 0 failed, 0 skipped across M0–M5 test modules matching `review_evidence/m5_test_summary.json` (execution duration 84.64s, portable command string `"uv run pytest -q --junitxml=<temporary-report-path>"`).
- **Evidence Consistency:** `m5_consent_governance_summary.json` dynamically derives `derived_features_retention_default: false` from `ConsentRecord` and migrated SQLite `PRAGMA table_info(consents)`; `m5_dataset_access_summary.json` reports `status: "RUNTIME_DATASET_AUTHORIZATION_NOT_INCLUDED_IN_RELEASE"` and `registered_datasets: []` when no runtime study DB is configured rather than hardcoding dataset approvals.
- **Consent Operation Mapping & Central Preflight:** `OPERATION_AUTHORIZATION_MAP` maps all 6 operations (`feature_extraction`, `transient_processing`, `statistical_audit`, `qc_validation`, `longitudinal_analysis`, `aggregate_reporting`) to required `scope_of_permission` and `permitted_research_uses`, and `record_task_recording()` invokes `preflight_session_ingestion()` before any write.
- **Code Quality:** Clean `ruff check` (0 errors), clean `ruff format --check` (270 files formatted).
- **Security & Privacy:** Prohibited raw audio (`.wav`), SQLite databases (`.db`), unverified model artifacts, and workstation filesystem paths are completely absent from release bundles and `review_evidence/`.
- **Participant Privacy Sanitization:** Individual participant exclusion identifiers (the three clipped PD sample IDs) completely purged from repository configurations, documentation, and tests into aggregate reviewed clipping policies (`exclusion_group_clipping`).
- **Verified Safety Invariants:**
  - `allow_user_microphone_inference = false`
  - `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`
  - `approved_domains = []`
  - `clinical_diagnostic_use = false`
  - `external_domain_validation_status = DOMAIN_VALIDATION_PENDING`

---

## 5. Summary of Verified Defect Repairs (M4 & M5)

1. **IPVS Equipment Attribution Correction:** Removed unsupported Samson Meteor microphone attribution from Italian Parkinson's Voice and Speech (IPVS) domain metadata. Set device model, sample rate, bit depth, channel count, and codec to null/unknown with literature citation to Studi AISV 2023 (vol. 11, pp. 249-268), noting Samson Meteor specifications from an unrelated study do not apply.
2. **Participant Independence Attestation Binding:** Bound `IndependenceAttestation` to participant roster SHA-256 digests and cryptographic HMAC-SHA256 signatures, requiring a recognized common identity basis or crosswalk.
3. **External Evaluation Receipt Integrity:** Upgraded `verify_evaluation_provenance_receipt` to dynamically recompute and validate all canonical schema, config, preprocessing, code, and frozen model SHA-256 fingerprints, along with checking candidate CSV features for numerical validity and non-NaN values.
4. **Exact Pinned Consent Reference Enforcement:** Eliminated implicit fallback to latest active consent in `create_session()` and `preflight_session_ingestion()`. Sessions must explicitly pin a valid consent reference in the same study and participant; changing consent after session creation cannot alter pinned session rules.
5. **Default Non-Retention Invariant:** Configured `permission_to_retain_derived_features = False` as default across Python dataclasses and SQLite migration schemas. Non-retained audio is processed ephemerally with zero derived feature rows persisted.
6. **SQLite Composite Foreign Key Constraints:** Added composite foreign keys `FOREIGN KEY (participant_id, study_id) REFERENCES participants(participant_id, study_id)` and `FOREIGN KEY (consent_reference, participant_id, study_id) REFERENCES consents(consent_record_id, participant_id, study_id)` to prevent cross-study and cross-participant SQL bypass.
7. **Atomic SQLite Migration Runner:** Wrapped migration script execution in `BEGIN IMMEDIATE` and `ROLLBACK` on error, eliminating partial migration state risks.
8. **HMAC Key Hard-Code Removal:** Removed all hardcoded fallback secrets from evidence generation scripts and withdrawal modules, enforcing cryptographic fail-closed behavior when external key material is unavailable.
9. **Release Privacy & Exclusion ID Purge:** Replaced individual participant IDs (the three clipped PD sample IDs) in `configs/reviewed_exclusions.yaml` and documentation with aggregate group policies (`exclusion_group_clipping`), ensuring zero participant-level identifiers leak into release artifacts.
10. **Evidence & Documentation Synchronization:** Regenerated all M4 and M5 review evidence artifacts, updated manifests, and reconciled completion reports and defect logs.
