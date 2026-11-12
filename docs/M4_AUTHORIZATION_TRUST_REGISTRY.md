# VoxNeuro M4 Authorization Trust Registry

## 1. Purpose and Threat Model

Prior to this hardening repair, the M4 evaluation flow accepted caller-supplied reviewer allowlists and caller-supplied source metadata (for example CLI flags `--authorized-reviewers` and `--authorized-sources-json`, or direct keyword allowlists). Allowing a caller or local operator to supply both the policy allowlist and the attested artifacts meant an unauthenticated caller could self-authorize reviewers or dataset sources.

VoxNeuro Milestone 4 now requires an **external Ed25519-signed Authorization Trust Registry** verified against **pinned public verification keys** compiled and cross-checked in the release before any reviewer or dataset source authorization check can succeed.

---

## 2. Pinned Trust Anchors and Cryptography

- **Module:** `src/voxneuro/modeling/trust_registry.py`
- **Pinned Anchor Config:** `configs/m4_trust_anchors.yaml` (`schema_version: voxneuro.m4_trust_anchors.v1`, `signature_algorithm: Ed25519`)
- **Pinned Key ID:** `voxneuro-m4-authority-ed25519-v1` (public verification key `f0161e1dcd64c2b464d5c1344de1554886780a1fbd3c6efeecff2046aaed44db`)
- **Implementation:** Pure-Python RFC 8032 Ed25519 implementation (`ed25519_public_key_from_seed`, `ed25519_sign`, `ed25519_verify`) requiring no additional packages beyond `uv.lock`, verified against RFC 8032 Section 7.1 Test Vectors 1, 2, and 3.
- **No Signing Secrets in Release:** Only public verification keys exist in the repository and ZIP archive. No private Ed25519 seed, private key file (`.pem`, `.key`, `id_ed25519`), or default HMAC secret is bundled.

### Strict Pinning & Anti-Self-Signing Invariants

`get_pinned_trust_anchors()` enforces:
1. `configs/m4_trust_anchors.yaml` must exist, declare `schema_version: voxneuro.m4_trust_anchors.v1`, declare `signature_algorithm: Ed25519`, and match the compiled `_PINNED_ED25519_PUBLIC_KEYS` mapping exactly. Any tampering fails closed with `AuthorizationTrustRootError("AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED: ...")`.
2. Signed registry bundles must not verify against caller-supplied public keys or embedded public keys inside the JSON envelope. Any unrecognized `key_id`, malformed hex/point, or embedded key mismatch fails closed with `AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED`.

---

## 3. Signed Registry Envelope and Data Model

`SignedAuthorizationRegistry` pairs:
- `registry`: `AuthorizationTrustRegistry` (`registry_id`, `registry_version`, `issuing_authority`, `created_utc`, `expires_utc`, `review_date_utc`, `key_id`, `signature_algorithm`, `authorized_sources`, `authorized_reviewers`, `registry_fingerprint`)
- `signature_algorithm`: `"Ed25519"`
- `key_id`: must resolve via `get_pinned_public_key(key_id)`
- `signature_hex`: 64-byte Ed25519 signature (128 hex characters) over `VOXNEURO-M4-AUTHORIZATION-REGISTRY-V1\x00{registry_fingerprint}`, where `registry_fingerprint` is the SHA-256 hex digest of the canonical unsigned JSON (`json.dumps(..., sort_keys=True, separators=(",", ":"))`).

### Record Schemas

- `AuthorizedSourceRecord`: `dataset_id`, `dataset_version`, `source_id`, `role` (`"reference"` or `"candidate"`), `artifact_sha256`, `retrieval_reference`, `authorization_ref`, `authorization_state` (`"APPROVED"`), `permitted_tasks`, `permitted_operations`, `expiry_utc`, `issuing_authority`, `registry_version`.
- `AuthorizedReviewerRecord`: `reviewer_id`, `role`, `approval_status` (`"APPROVED"`), `permitted_evaluation_tasks`, `permitted_operations`, `expiry_utc`.

---

## 4. Verification Checks and Fail-Closed Rules

`verify_signed_authorization_registry(signed_registry, now_utc=...)` rejects with `AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED` if:
- `signed_registry` is missing (`None`), not a `SignedAuthorizationRegistry`, or lacks an external Ed25519 signature;
- `key_id` is absent or not in `get_pinned_trust_anchors()`;
- an embedded public key disagrees with the pinned key or signature verification fails on the domain-separated `signing_message()`;
- `expires_utc <= now_utc` (expired registry) or `created_utc > expires_utc` or malformed `review_date_utc`;
- `issuing_authority` is missing or empty, or `registry_version` disagrees across records.

### CLI Enforcement

In `scripts/evaluate_external_domain.py`:
- Supported inputs are `--authorization-registry` and `--authorization-registry-signature` paired with `--reviewer-id`.
- Supplying removed flags `--authorized-reviewers` or `--authorized-sources-json` exits non-zero immediately with `AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED`.
- When `--features-path` is omitted (pending status mode) and no signed external registry is supplied, the output explicitly reports `"authorization_trust_root_status": "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED"`.

---

## 5. Separation of Guarantees

1. **Ed25519 Trust Registry Signature Verification** proves the authorization allowlist was issued by a pinned authority key and was not modified locally.
2. **Source Authorization (`authorize_source_from_registry`)** proves the roster artifact SHA-256, `source_id`, `dataset_id`, `dataset_version`, `authorization_ref`, task/operation scope, and expiry are authorized in the signed registry.
3. **Reviewer Authorization (`authorize_reviewer_from_registry`)** proves the reviewer's identity, role, approval status, task/operation permissions, and expiry are authorized in the signed registry.
4. **Scientific Clinical Validation** remains strictly separate: even a cryptographically verified trust registry and external evaluation run do **not** approve clinical or microphone inference (`allow_user_microphone_inference: false`, `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`, `approved_domains: []` remain locked).
