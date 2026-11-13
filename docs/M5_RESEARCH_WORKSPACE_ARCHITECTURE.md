# Milestone 5 Research Workspace Architecture

**Architecture Specification:** VoxNeuro Privacy-Preserving Research Operations  
**Release Target:** Milestone 5 (`VoxNeuro_M5_VERIFIED.zip`)  
**Status:** Implemented & Verified  

---

## 1. Architectural Vision & Scope

Milestone 5 elevates VoxNeuro from a feature-extraction and domain-validation engine into a fully compliant, privacy-preserving research-study operations platform. 

VoxNeuro operates as an investigational software prototype designed for speech acoustics research and longitudinal observational tracking. Its approved clinical prediction gate remains closed for unverified microphone data and it does not output diagnostic probabilities or claim to track neurodegenerative clinical progression. The current UI may separately show a local research model's explicitly unvalidated candidate only after its evidence and input checks pass; this is not a validated disease result and must not guide care.

```
+-----------------------------------------------------------------------------------+
|                        Streamlit Research Workspace UI                            |
|   +-------------------+  +-------------------+  +-------------------------------+ |
|   | Studies/Protocols |  | Cohort & Consent  |  | QC & Longitudinal Tracking    | |
|   +-------------------+  +-------------------+  +-------------------------------+ |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                          voxneuro.study Application Layer                         |
|   +-----------------+  +-------------------+  +---------------------------------+ |
|   | Study Registry  |  | Consent / DUA     |  | Operational QC & Longitudinal   | |
|   +-----------------+  +-------------------+  +---------------------------------+ |
|   +-----------------+  +-------------------+  +---------------------------------+ |
|   | Ingestion Pipe  |  | Audit Trail       |  | Withdrawal & Tombstones         | |
|   +-----------------+  +-------------------+  +---------------------------------+ |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                            Relational SQLite Store                                |
|   (12 tables: foreign keys ON, migrations, ACID transactions, zero raw audio)     |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Subsystems

### 2.1 Protocol Immutability & Study Management (`voxneuro.study.registry`)
- Protocols define rigid scientific specifications: required speech tasks (`sustained_vowel`, `ddk`, `connected_speech`, `vowel_space`), expected visit counts, and minimum interval constraints between visits.
- **Protocol Immutability Guarantee:** A protocol version cannot be updated on a study if sessions have already been recorded under that protocol. Once sessions exist, any protocol alteration requires registering a new protocol version or initiating a distinct study entity.

### 2.2 Pseudonymous Participant Management (`voxneuro.study.participant`)
- Participants are identified exclusively by 12-character cryptographically random pseudonymous tokens (`PT-XXXXXXXXXXXX`).
- Proactive PII Rejection: Strict regular-expression screening blocks email addresses, telephone numbers, Social Security Numbers, Medical Record Numbers, and explicit name identifiers from ever entering the database.

### 2.3 Informed Consent & DUA Governance (`voxneuro.study.consent`)
- Task recording ingestion is strictly gated by two independent checks:
  1. Participant active consent covering the specific task requested.
  2. Institutional Data Use Agreement (DUA) state (`ACTIVE` or `NOT_REQUIRED`) and access approval (`APPROVED`) covering the specific task.
- Fail-Closed Gate: Any missing consent or unapproved DUA terminates processing immediately with `PermissionError`.

### 2.4 Longitudinal Multi-Task Audio Ingestion (`voxneuro.study.session`)
- Ingests audio records across multiple speech tasks into discrete research visits (`Visit 1 Baseline`, `Visit 2 Follow-up`, etc.).
- Integrates seamlessly with Milestone 3 multi-task extractors (`voxneuro.voice.v4` envelope).
- **Zero Raw Audio Retention Invariant:** Raw acoustic audio bytes are processed in ephemeral memory and discarded immediately following feature extraction and quality screening. Only derived tabular numbers are persisted.

### 2.5 Operational QC & Longitudinal Tracking (`voxneuro.study.qc`, `voxneuro.study.longitudinal`)
- Operational monitoring of cohort attrition, completion rates, and screening pass/fail statistics.
- **Small-Cell Suppression ($N < 10$):** All low-frequency participant and session counts between 1 and 9 are suppressed as `< 10 (Suppressed)` to eliminate re-identification risk and prevent statistically unpowered conclusions.
- Intra-individual descriptive deltas ($\Delta = \text{Visit}_k - \text{Visit}_1$) track acoustic feature variance over time with explicit scientific notices barring clinical progression inferences.

### 2.6 Cryptographic Audit Trail & Participant Withdrawal (`voxneuro.study.audit`, `voxneuro.study.withdrawal`)
- Relational audit logging with automatic regex-based PII redaction (`[REDACTED_PII]`).
- Comprehensive participant withdrawal workflow:
  1. Immediate state transition to `withdrawn`.
  2. Existing sessions marked `RESTRICTED_WITHDRAWN`.
  3. Complete deletion of derived acoustic features from `derived_features`.
  4. Generation of an irreversible, non-identifying cryptographic tombstone record with salted hash verification.
- Immutable `ProcessingRunReceipt` cryptographic provenance binding application version, code hash, task schema hashes, and output table checksums.
