# Milestone 5 Privacy and Security Audit

**Audit Scope:** Data Privacy Controls, PII Elimination, Relational Audit Trail, and Security Protections  
**Evaluation Standard:** HIPAA Security & Privacy Rules, GDPR Article 89, OWASP Secure Coding Practices  
**Status:** Implemented & Verified  

---

## 1. Executive Summary

Milestone 5 implements comprehensive technical safeguards ensuring that personal identifiable information (PII) cannot be stored, leaked, or exposed in audit trails, research reports, or release packages.

---

## 2. Technical Safeguards & Implementation

### 2.1 Pseudonymity and Rejection of Direct Identifiers
- Participants are issued a random 12-character token: `PT-[0-9A-F]{12}`.
- Pre-ingestion validation inspects candidate identifiers against three regular expression pattern families:
  1. Email addresses (`[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`)
  2. Phone numbers & Social Security Numbers (`\b\d{3}[-.\s]?\d{2,3}[-.\s]?\d{4}\b`)
  3. Direct clinical PII labels (`\b(?:mrn|ssn|dob|patient|name)[=:\s]`)
- Detection immediately raises `ValueError`, aborting registration before any database transaction.

### 2.2 Relational Audit Trail & PII Redaction
- All operational actions (`PARTICIPANT_REGISTERED`, `CONSENT_RECORDED`, `SESSION_CREATED`, `WITHDRAWAL_COMPLETED`, `PROCESS_RUN_RECORDED`) are logged in the `audit_log` table.
- Every audit entry details dictionary is filtered through `sanitize_audit_details()`.
- Any dictionary key containing `name`, `email`, `phone`, `address`, `mrn`, `password`, or `token` has its value irreversibly replaced with `"[REDACTED_PII]"`.

### 2.3 Ephemeral Audio Processing (Zero Storage Invariant)
- VoxNeuro does not write, cache, or persist raw recorded audio bytes (`.wav`) to disk or database.
- Audio is decoded in memory, evaluated against quality screening gates, and feature-extracted immediately.
- Only non-identifying derived acoustic feature tables are saved.

### 2.4 Cryptographic Processing Run Receipts
- Every batch analytical processing run produces an immutable `ProcessingRunReceipt`.
- The receipt binds:
  - Project code SHA-256 fingerprint (`project_code_fingerprint()`)
  - Python runtime version
  - Task schema fingerprints (`voxneuro.voice.v3`, `ddk.v1`, `connected_speech.v1`, `vowel_space.v1`, `v4_envelope`)
  - Audio and feature configuration fingerprints
  - Domain metadata registry fingerprint
  - Feature table output SHA-256 checksum
- The overall receipt hash is computed via deterministic canonical JSON serialization (`receipt_sha256`), providing tamper-evident verification.

### 2.5 Release Packaging Security
- SQLite database files (`.db`, `.sqlite`, `.sqlite3`) are explicitly excluded from the Git repository and distribution ZIP bundles.
- No real participant voice recordings or clinical audio files are bundled into releases.
- Synthetic fixtures used for automated verification are purely synthetic, mathematically synthesized sine/harmonic audio arrays.

### 2.6 Cryptographic Tombstone Key Management & Fail-Closed Enforcement
- Participant withdrawal generates a privacy-preserving HMAC-SHA256 tombstone digest.
- Requires external cryptographic key material (`VOXNEURO_HMAC_KEY` or caller-provided key) with an explicit `key_id` (e.g. `voxneuro-key-v1`).
- All hardcoded fallback secrets have been completely purged from the codebase; if key material is unavailable, withdrawal operations fail closed immediately (`KeyError`), preventing insecure or unkeyed tombstone creation.
- Operations execute inside an atomic database transaction (`transaction(conn)`), ensuring complete rollback if any step fails.

### 2.7 Cross-Study Isolation & Composite Integrity
- Composite foreign key constraints at the SQLite engine level enforce relational boundaries across studies.
- Sessions cannot reference participants or consents belonging to other studies (`FOREIGN KEY (participant_id, study_id)` and `FOREIGN KEY (consent_reference, participant_id, study_id)`).
- SQL injection or application-layer bypass attempts are blocked at the relational engine level with foreign key constraint failures.

### 2.8 Release Privacy & Participant ID Purging
- Individual participant identifiers associated with pre-reviewed clipping exclusions (the three clipped PD recordings) have been purged from all configuration files (`configs/reviewed_exclusions.yaml`), test fixtures, and documentation.
- Quality exclusions are managed via aggregate policy identifiers (`exclusion_group_clipping`), ensuring that zero individual participant-level identifiers are present in public release packages.

### 2.9 Evidence Sanitization & Authoritative DUA Provenance
- Evidence generators (`scripts/generate_m4_review_evidence.py`, `scripts/generate_m5_review_evidence.py`) record only portable execution commands (`uv run pytest -q --junitxml=<temporary-report-path>`) and cross-platform sanitized file references, verified both in unit tests and by `scripts/build_ai_review_bundle.py`.
- Consent retention evidence (`m5_consent_governance_summary.json`) inspects live `ConsentRecord` defaults and SQLite `PRAGMA table_info(consents)`, confirming `derived_features_retention_default: false`.
- Dataset access evidence (`m5_dataset_access_summary.json`) never hardcodes dataset approvals; when no runtime study DB is configured it emits `RUNTIME_DATASET_AUTHORIZATION_NOT_INCLUDED_IN_RELEASE` with `registered_datasets: []`.
