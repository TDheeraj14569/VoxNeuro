# Milestone 5 Data Governance, Consent Tracking and DUA Policy

**Framework:** VoxNeuro Research Compliance and Data Lifecycle Governance  
**Audience:** Principal Investigators, Institutional Review Boards (IRB), Compliance Auditors  
**Status:** Implemented & Verified  

---

## 1. Governance Principles

VoxNeuro adheres to strict research data governance, complying with privacy-by-design principles, HIPAA de-identification standards, and GDPR Article 89 safeguards for scientific research:

1. **Strict Pseudonymity:** No direct personal identifiers (PII) or protected health information (PHI) are ingested, displayed, or stored.
2. **Explicit Consent Scoping:** Processing operations and acoustic feature extraction are permitted only when explicitly authorized by an unrevoked informed consent record.
3. **Institutional DUA Alignment:** Ingestion of external or multi-center speech corpora requires verified Data Use Agreements with active approval states.
4. **Zero Persistent Raw Audio:** Audio waveforms are analyzed ephemerally in transient memory. Only derived numerical features are persisted to storage.
5. **Irreversible Right to Erasure:** Withdrawal of participant consent triggers immediate feature deletion, session restriction, and cryptographic tombstoning.

---

## 2. Informed Consent State Machine

Consent records are tracked cryptographically in the relational database.

```
       [ENROLLED] 
            |
            v
       [CONSENTED]  <================+
            |                        | (Re-consent)
            +------------------------+
            | (Consent Withdrawn)
            v
       [WITHDRAWN]  (Features Deleted, Sessions Restricted, Tombstone Created)
```

### 2.1 Consent Record Attributes
- `consent_record_id`: Unique tracking token.
- `consent_form_version`: Version of the IRB-approved document signed by participant.
- `permitted_recording_tasks`: Explicit task list (`sustained_vowel`, `ddk`, `connected_speech`, `vowel_space`).
- `permitted_research_uses`: Permitted analysis types (e.g. `biomarker_research`, `reproducibility_audit`).
- `permission_to_retain_derived_features`: Authorization to retain non-identifying tabular acoustic measurements (defaults to `False`; requires affirmative opt-in; when `False`, processing remains ephemeral with 0 persisted rows).
- `permission_to_retain_audio`: Fixed to `False` in VoxNeuro research prototype.
- `withdrawal_status`: Boolean indicator of consent revocation.

### 2.2 Exact Pinned Consent Reference
Sessions must explicitly pin an immutable `consent_reference` at creation time. The operational architecture strictly rejects implicit fallbacks to latest active consents or assumed defaults:
- If `consent_reference` is missing, whitespace, or nonexistent, session creation raises `PermissionError`.
- Sessions are cryptographically pinned to the exact consent under which they were scheduled; subsequent re-consenting or modifications do not retroactively alter the rules governing historical sessions.
- Ingestion checks tasks and scopes strictly against the pinned consent.

### 2.3 Operation Scope Mapping & Centralized Preflight
- `OPERATION_AUTHORIZATION_MAP` (`src/voxneuro/study/session.py`) explicitly maps permitted operations (`feature_extraction`, `transient_processing`, `statistical_audit`, `qc_validation`, `longitudinal_analysis`, `aggregate_reporting`) to required `scope_of_permission` and `permitted_research_uses` entries; unrecognized or unmatched operations fail closed.
- Both `ingest_session_multitask_audio()` and direct calls to `record_task_recording()` invoke centralized `preflight_session_ingestion()` before persisting any task or derived feature row, and validate exact equality of any supplied `ConsentRecord`.

---

## 3. Data Use Agreement (DUA) Enforcement

Data Use Agreements govern the operational boundary between external institutions and the VoxNeuro processing pipeline.

| Attribute | Field | Governance Constraint |
|---|---|---|
| Access Approval State | `access_approval_state` | Must be `APPROVED`. `PENDING`, `REJECTED`, or `EXPIRED` blocks ingestion. |
| DUA Agreement State | `dua_state` | Must be `ACTIVE` or `NOT_REQUIRED`. `TERMINATED` blocks ingestion. |
| Dataset Version | `dataset_version` | Must strictly match the study's registered dataset version. |
| Expiration Date | `expiration_date` | Ingestion is blocked if `expiration_date < today`. |
| Permitted Tasks | `permitted_tasks` | Must contain the specific speech task being processed. |
| Storage Restrictions | `storage_restrictions` | Enforces ephemeral analysis only; prohibits unencrypted archiving. |
| Publication Rules | `publication_restrictions` | Requires small-cell suppression ($N < 10$) on all public summaries. |

---

## 4. Participant Withdrawal Protocol

When a participant exercises their right to withdraw consent:
1. **Processing Lockout:** Future session scheduling is immediately rejected (`PermissionError`).
2. **State Transition:** Participant `enrollment_status` and `consent_status` transition to `withdrawn`.
3. **Session Restriction:** Associated sessions transition to `RESTRICTED_WITHDRAWN`.
4. **Data Purge:** All extracted records in `derived_features` matching `participant_id` are permanently deleted.
5. **Cryptographic Tombstone:** A tombstone record is created in `tombstones`:
   - `tombstone_id`: Unique identifier (`tomb-XXXXXXXXXXXX`).
   - `participant_pseudonym_hash`: Salted SHA-256 digest of participant pseudonym (irreversible).
   - `records_deleted_count`: Count of derived feature records purged.
   - `policy_reference`: IRB data retention policy citation.
