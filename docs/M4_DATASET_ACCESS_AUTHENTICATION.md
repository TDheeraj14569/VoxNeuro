# VoxNeuro M4 Dataset Access Authentication

## 1. Objective

Milestone 4 external evaluation requires verifiable proof that every candidate cohort has an active, task- and operation-scoped Data Use Agreement (DUA) and governance approval recorded authoritatively before evaluation metrics can be marked provenance-verified.

---

## 2. Removal of Caller-Supplied Object Bypass

Previously, callers of `_verify_authoritative_dataset_access()`, `verify_evaluation_provenance_receipt()`, and `evaluate_external_domain_with_provenance()` could omit `study_conn` (the SQLite database connection) and pass an in-memory `DatasetAccessRecord` Python object (`dataset_access_record`), bypassing persistent governance storage.

That bypass has been **completely removed**:

- If `study_conn` is `None`, `_verify_authoritative_dataset_access()` fails closed immediately returning `(False, "DATASET_AUTHORIZATION_NOT_VERIFIED: authoritative study database connection is required; caller-supplied DatasetAccessRecord cannot bypass authority lookup.")`.
- Supplying a `dataset_access_record` object in memory does **not** satisfy dataset access verification: when `study_conn` is absent it is rejected, and when `study_conn` is present it must match the authoritative SQLite row (`passed_rec == db_rec`).

---

## 3. Authoritative SQLite Lookup, Signed Registry Cross-Binding & DUA Artifact Verification

`_verify_authoritative_dataset_access()` queries the SQLite `dataset_access` table (migrated through `004_dataset_access_dua_fingerprint.sql` and `005_dataset_access_registry_binding.sql`) by `(dataset_id, dataset_version)` using `get_dataset_access()` in `src/voxneuro/study/consent.py`.

A candidate evaluation fails closed (`DATASET_AUTHORIZATION_NOT_VERIFIED`) unless **all** of the following hold on the authoritative database row, signed registry, and on-disk DUA document artifact:

1. A matching row exists for `(dataset_id, dataset_version)` with `dua_verification_status == "DOCUMENT_AUTHENTICATED"` (`VALID_DUA_VERIFICATION_STATUSES = {"UNVERIFIED", "DOCUMENT_AUTHENTICATED", "REVOKED", "EXPIRED"}`).
2. `access_approval_state == "APPROVED"` and `dua_state in {"ACTIVE", "NOT_REQUIRED"}`.
3. `dataset_owner` is populated and not `"unknown"`, `"pending"`, `"none"`, or `"tbd"`.
4. `expiration_date` (and receipt `dua_expiration_date`) is not expired (`>= today UTC date`) and matches between the database row, receipt, and signed registry source `expiry_utc[:10]`.
5. `permitted_tasks` includes both the receipt `task_identifier` and `domain_entry.metadata.task_type`, and `permitted_data_processing_operations` includes `"frozen_model_evaluation"` or `"external_validation"` and covers receipt `permitted_operations`.
6. `storage_restrictions`, `publication_restrictions`, and `source_documentation` are present and valid (not `"DUA_PENDING_REVIEW"`, `"UNKNOWN"`, `"NONE"`, or `"PENDING"`), `dataset_source` is non-empty, and `dua_document_fingerprint` is a 64-character SHA-256 hex digest matching the receipt and the actual SHA-256 of the supplied DUA document file (`dua_document_path`).
7. When a `SignedAuthorizationRegistry` is supplied in `verify_evaluation_provenance_receipt()` / `evaluate_external_domain_with_provenance()`, the authoritative SQLite `dataset_access` row must pass **12-point cross-binding** against the Ed25519-signed `AuthorizedSourceRecord` (`dataset_id`, `dataset_version`, `source_id`, `authorization_ref`, `authorization_state == "APPROVED"`, `permitted_tasks` subset, `permitted_data_processing_operations` subset, `expiration_date == expiry_utc[:10]`, `dua_document_fingerprint`, `issuing_authority`, `authorization_registry_id` & `authorization_registry_version`, `dua_source_artifact_reference == retrieval_reference`), as well as matching attestation `candidate_roster_source` / `candidate_authorization_ref` and a valid source `artifact_sha256`.

---

## 4. Release Posture

Because the public/review release contains **no** external cohort data and **no** bundled operational study SQLite database with active DUAs:
- `review_evidence/m4_dataset_access_authentication_summary.json` records `"caller_supplied_dataset_access_record_bypass_rejected": true` from a live probe where calling `_verify_authoritative_dataset_access(..., study_conn=None, fallback_record=...)` raises `DATASET_AUTHORIZATION_NOT_VERIFIED`.
- `review_evidence/m5_dataset_access_summary.json` continues to report `RUNTIME_DATASET_AUTHORIZATION_NOT_INCLUDED_IN_RELEASE` with `registered_datasets: []`.
