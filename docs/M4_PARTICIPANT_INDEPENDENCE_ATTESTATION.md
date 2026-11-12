# VoxNeuro M4 Participant Independence Attestation

## 1. Overview

External evaluation of VoxNeuro's frozen reference acoustic model requires verifiable participant independence between the UAMS reference cohort and any candidate external recording-domain cohort (`NeuroVoz`, `PC-GITA`, `Italian IPVS`).

This document describes the hardened construction and verification of `IndependenceAttestation` in `src/voxneuro/modeling/domain_evaluation.py`.

---

## 2. Cryptographic & Trust-Root Binding

Neither `create_participant_independence_attestation()` nor `verify_participant_independence_attestation()` accepts caller-supplied `authorized_reviewers` or `authorized_sources` dictionaries, nor unauthenticated source strings. Both require a `SignedAuthorizationRegistry` verified against pinned Ed25519 trust anchors (`verify_signed_authorization_registry`).

### Attested & Verified Fields on `IndependenceAttestation`

In addition to cohort overlap fields (`reference_participant_count`, `candidate_participant_count`, `overlapping_participants_count`, `duplicate_reference_count`, `duplicate_candidate_count`, `overlap_status`, `identity_basis_type`, `normalization_protocol`), each attestation binds:

- **Trust-Registry Binding:** `registry_id`, `registry_version`, `registry_fingerprint`
- **Authoritative Source Binding (Reference & Candidate):**
  - `reference_dataset_id`, `reference_dataset_version`, `reference_roster_source`, `reference_roster_sha256`, `reference_authorization_ref`, `reference_source_expiry_utc`
  - `candidate_dataset_id`, `candidate_dataset_version`, `candidate_roster_source`, `candidate_roster_sha256`, `candidate_authorization_ref`, `candidate_source_expiry_utc`
- **Authoritative Reviewer Binding:** `reviewer_identity`, `reviewer_role`, `timestamp_utc`
- **Cryptographic Integrity:** `roster_fingerprint` (SHA-256 over canonical source + normalized roster digests), `key_id`, and `attestation_hmac` (HMAC-SHA256 using an explicit runtime `key`, verified with `hmac.compare_digest`).

---

## 3. Verification Sequence (`verify_participant_independence_attestation`)

1. **Ed25519 Trust Root First:** Verify `signed_registry` against pinned public keys (`configs/m4_trust_anchors.yaml`). Fails closed with `AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED` if missing, unsigned, tampered, expired, or signed by an unpinned key.
2. **Schema & Positive Counts:** Verify `schema_version`, `reference_participant_count > 0`, `candidate_participant_count > 0`, `overlapping_participants_count == 0`, `overlap_status == "INDEPENDENT_VERIFIED"`, `normalization_protocol == "casefold_strip_prefix_v1"`, and explicit `identity_basis_type` (`"authorized_crosswalk"` or `"common_identity_basis"`).
3. **HMAC Integrity Verification & Trust-Registry Binding:** Verify `attestation_hmac` using an explicit non-empty `key` via `hmac.compare_digest`, and confirm `registry_id`, `registry_version`, and `registry_fingerprint` match the verified `AuthorizationTrustRegistry`.
4. **Reviewer Authorization:** Confirm `reviewer_identity` matches `expected_reviewer_id` and is `"APPROVED"`, non-expired, permitted for the target evaluation task and operation, and matches `reviewer_role` in the signed registry.
5. **Source Authorization & Live Roster Re-Verification:** Authorize both `"reference"` and `"candidate"` `AuthorizedSourceRecord` entries from the signed registry, verify `dataset_id`/`dataset_version`/`authorization_ref`/`expiry_utc`, verify live roster file byte SHA-256 digests match both the attestation and the signed registry's `artifact_sha256`, re-parse participant IDs from disk with normalization (`casefold_strip_prefix_v1`), and recompute `overlapping_participants_count == 0` and `roster_fingerprint`. Even a valid HMAC over a tampered or unauthorized reviewer/source fails because HMAC alone does not establish authority.

---

## 4. Boundary Between Proof Layers

| Mechanism | What It Guarantees | What It Does **Not** Guarantee |
|---|---|---|
| Ed25519 Trust Registry Signature | Pinned authority approved the reviewer & source roster hashes | Does not compute participant overlap on disk |
| Live Roster File Re-Parse & SHA-256 | Current files on disk match signed source hashes and have zero normalized participant overlap | Does not itself grant DUA database access |
| HMAC-SHA256 (`signing_key`) | Binds runtime attestation & provenance receipt end-to-end against caller mutation | Cannot override an unauthorized source, unapproved reviewer, or unverified trust root |
