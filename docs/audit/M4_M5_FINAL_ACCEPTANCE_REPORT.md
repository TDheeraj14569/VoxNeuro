# VoxNeuro M4/M5 Final Acceptance Report

**Report Scope:** Final M4/M5 Scientific Metadata and Authorization Binding Repair, Regression Verification, and Verified Release  
**Baseline Input Archive:** `VoxNeuro_M5_VERIFIED(4).zip` (`SHA-256: ac000a446470e0568f49059138d4df2fefec76016afd02b63c84839cbcfffa08`)  
**Target Deliverable:** `VoxNeuro_M5_VERIFIED.zip` + `VoxNeuro_M5_VERIFIED.zip.sha256`  
**Project Code Fingerprint:** `c112d43bcb519790c25934c0b2e56216013a0999c7004f293d5d52f3ea546416`  
**Pinned Authority Key ID:** `voxneuro-m4-authority-ed25519-v1` (`configs/m4_trust_anchors.yaml`, `SHA-256: 303d290e894c30dca34b73f3af77d9de212049cd2cd1d12b7526b6378ddaa907`)  
**Execution Environment:** Python 3.12.16 (`uv sync --frozen --all-extras`), Windows 11

---

## 1. Evidence Classification Matrix

| Capability / Claim | Status | Basis & Scope |
|---|---|---|
| Ed25519 Authorization Trust Registry & Pinned Trust Anchors (`trust_registry.py`, `configs/m4_trust_anchors.yaml`) | **Implemented, Unit-tested, Runtime-verified** | Pure-Python RFC 8032 Ed25519 verified against official Test Vectors 1–3 (`tests/unit/test_m4_trust_registry.py`). Rejects missing, unsigned, tampered, expired, or unpinned registries with `AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED`. |
| Removal of caller-supplied `--authorized-reviewers` / `--authorized-sources-json` & in-memory allowlists (`domain_evaluation.py`, `evaluate_external_domain.py`) | **Implemented, Unit-tested, CLI-probed** | Legacy insecure flags exit `1` (`AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED`); deprecated `_validate_source_authority` removed; pending CLI reports `"authorization_trust_root_status": "AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED"`. |
| Trust-root-bound `IndependenceAttestation` & evaluation provenance receipt verification (`domain_evaluation.py`) | **Implemented, Unit-tested** | Verifies Ed25519 trust registry first, enforces reviewer role/status/task/operation/expiry and live roster file SHA-256 + overlap recomputation; HMAC alone cannot override unauthorized sources or reviewers (`test_m4_trust_registry.py`, `test_m4_provenance_and_roster_binding.py`). |
| Authoritative SQLite `dataset_access` 12-point cross-binding & DUA artifact SHA-256 verification (`005_dataset_access_registry_binding.sql`, `domain_evaluation.py`) | **Implemented, Unit-tested, Runtime-probed** | `_verify_authoritative_dataset_access()` fails closed with `DATASET_AUTHORIZATION_NOT_VERIFIED` whenever `study_conn` is `None`, `dua_verification_status != "DOCUMENT_AUTHENTICATED"`, on-disk `--dua-document` artifact is missing/mismatched, or any of the 12 cross-binding fields (`authorization_ref`, `source_id`, `authorization_registry_id`, `authorization_registry_version`, `issuing_authority`, `dua_source_artifact_reference`, `dua_document_fingerprint`, tasks, operations, expiry, state, dataset identity) diverges from the Ed25519-signed `AuthorizedSourceRecord` (`test_dua_to_signed_registry_cross_binding_enforcement`). |
| Domain metadata & acquisition consistency (`recording_domain_registry.yaml`, `domain_assessment.py`, `M4_EXTERNAL_DATASET_REGISTER.md`) | **Implemented, Unit-tested** | IPVS metadata keeps hardware, sample rate, bit depth, channels, codec, and environment as `null`/`unknown` with Samson Meteor & WH20 studies separated and full `/pa-ta-ka/` DDK unverified; `M4_EXTERNAL_DATASET_REGISTER.md` & `M4_COMPLETION_REPORT.md` separate Cohort Origin from Participant Overlap (`NOT_ASSESSED`); assessment dossier computes domain-specific acquisition differences per candidate without booth conflation (`test_ipvs_metadata_and_register_scientific_consistency`, `test_pending_dossier_acquisition_differences_are_domain_specific`). |
| M5 study operations, consent governance (`OPERATION_AUTHORIZATION_MAP`, `derived_features_retention_default: false`), and privacy/audit redaction | **Implemented, Unit-tested, Integration-tested, Runtime-verified** | Verified across `m5_study_operations_unit_tests` (49/49) and `m5_integration_tests` (18/18), plus `m5_consent_governance_summary.json` and `m5_dataset_access_summary.json`. |
| M4/M5 review evidence manifests & new trust-root summaries (`review_evidence/`) | **Generated, Runtime-verified** | Preserves exact 6-entry `m4_review_manifest.json` and 10-entry `m5_review_manifest.json`, plus 4 new M4 trust-root summaries bundled via `scripts/build_ai_review_bundle.py`; zero workstation paths or private signing keys. |
| Automated M0–M5 local test suite & static checks | **Runtime-verified** | `uv run ruff check .` & `ruff format --check .` passed; full suite passed 577/577 tests (`m4_safety_gate_test_summary.json`: 128.124s; `m5_test_summary.json`: 84.64s). |
| Frontend JS checks (`npm test` / `npm run build` / `npm run smoke`) | **Blocked on Host Toolchain** | `node`/`npm` are not installed on this Windows host; pre-built `frontend/acoustic-visualizer/dist/visualizer.bundle.js` (595,161 bytes) preserved unmodified and included in `frontend_code_fingerprint()`. |
| Clean-room ZIP verification (`VoxNeuro_M5_VERIFIED.zip`) | **Executed via Release Pipeline** | Verified against freshly extracted archive (CRC, manifests, SHA-256 sidecar, zero secrets/path leaks, `uv sync --frozen --all-extras`, `ruff`, `pytest`, `verify_project.py`, and trust-root/DB bypass probes). |
| Independent external recording-domain clinical validation (`NeuroVoz`, `PC-GITA`, `Italian IPVS`) | **Blocked** | Licensed external audio/features, executed DUAs, and signed external trust registry are absent from the release (`FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING`, `AUTHORIZATION_TRUST_ROOT_NOT_VERIFIED`). |
| Live user microphone diagnostic inference | **Blocked (Intentionally Disabled / N/A)** | Locked fail-closed (`allow_user_microphone_inference: false`, `approved_domains: []`, `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`). |

---

## 2. Cryptographic Separation & Documentation References

- `docs/M4_AUTHORIZATION_TRUST_REGISTRY.md` — Pinned Ed25519 trust anchors, signing envelope, anti-self-signing rules, and CLI behavior.
- `docs/M4_PARTICIPANT_INDEPENDENCE_ATTESTATION.md` — Separation between Ed25519 trust-registry verification, live roster hashing/overlap computation, and runtime HMAC binding.
- `docs/M4_DATASET_ACCESS_AUTHENTICATION.md` — Authoritative SQLite `dataset_access` DUA verification and removal of `DatasetAccessRecord` bypass.

---

## 3. Fail-Closed Safety Invariants

All mandatory safety invariants remain locked:
- `configs/model_config.yaml`: `allow_user_microphone_inference: false`, `clinical_diagnostic_use: false`
- `src/voxneuro/modeling/domains.py`: `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`, `external_domain_validation_status = "DOMAIN_VALIDATION_PENDING"`
- `configs/recording_domain_registry.yaml`: `approved_domains: []`, every candidate domain has `inference_eligible: false`
- `configs/m4_trust_anchors.yaml`: public verification key only (`voxneuro-m4-authority-ed25519-v1`); zero private keys or HMAC secrets in repository or release archive
- `ConsentRecord` and migrated SQLite `consents`: `permission_to_retain_derived_features = False` (`0`), `permission_to_retain_audio = False` (`0`)
- No M6 modules, migrations, schemas, tests, documentation, or release hooks exist anywhere in the repository.
