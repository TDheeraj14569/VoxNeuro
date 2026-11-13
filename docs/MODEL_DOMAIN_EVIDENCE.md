# Model recording-domain evidence gate

VoxNeuro does not expose an approved or clinically validated disease prediction for new microphone audio. Model bundles are research-only, `allow_user_microphone_inference` is disabled, and the source-controlled `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` allowlist is empty. A separate exploratory software path may show a research candidate from a local model only after current provenance, task, quality, schema, explicit user-declared device category, and training-derived out-of-distribution checks pass. That display does **not** verify the recording domain, populate the trusted allowlist, or change the approved-inference status.

## Requirements for a future review

`make_bundle()` will not infer compatibility from a list of domain names. A proposed report must be a JSON file with the following fields:

```json
{
  "report_version": "1.0",
  "validated_utc": "2026-11-06T00:00:00+00:00",
  "validation_protocol": "documented protocol identifier",
  "validation_dataset": "independent cohort identifier",
  "independent_validation": true,
  "validated_input_domains": ["uams_telephone"],
  "results": {
    "n_participants": 80,
    "balanced_accuracy": 0.75
  }
}
```

The report is parsed and structurally checked, its bytes are SHA-256 hashed into bundle version 4, and edits invalidate that digest. Before compatibility can be marked verified, a maintainer must review the report and deliberately add its SHA-256 to the source-controlled allowlist in `src/voxneuro/modeling/domains.py`. The current allowlist contains no approved hashes. All microphone names and aliases remain rejected even if a proposed report lists one.

The hash protects report integrity; it is not a digital signature and cannot prove that the report's claims are true. Human review must verify the cohort, protocol, results, and relevance to the intended input domain before adding any hash. Such a software gate does not establish clinical validity, authorization, or safe use.

Domain names are stripped, case-folded, and normalized before matching. Live-device aliases are blocked when a domain contains any of these tokens: `mic`, `microphone`, `smartphone`, `mobile`, `cellphone`, `phone`, `browser`, `web`, `laptop`, `computer`, `desktop`, `device`, `iphone`, `ipad`, `android`, `webcam`, `headset`, `streamlit`, `getusermedia`, or `live`. This also rejects names such as `phone_recording` and `web_audio`. The token `telephone` is intentionally distinct: a telephone-collected research corpus such as `uams_telephone` is not considered a live microphone domain. Model compatibility checks also require exact feature-schema and preprocessing fingerprints, complete ordered features, and the model's explicit missing-value policy.

## Milestone 4 Architecture and Candidate Dossiers

Milestone 4 introduces the candidate domain assessment schema (`voxneuro.domain_assessment.v1`) and the authoritative domain registry (`configs/recording_domain_registry.yaml`):

1. **Candidate Dossier vs. Approved Compatibility Report:** Candidate dossiers evaluate prospective external cohorts, recording quality attrition, and feature-level domain shift (SMD, KS tests, FDR/Bonferroni). Crucially, candidate dossiers are structurally and cryptographically rejected by `load_domain_validation_report()` and cannot be used by `make_bundle()` to mark a model compatible.
2. **Explicit Input Capture Context:** In addition to domain identifiers, `predict_research()` enforces an explicit acquisition context (`InputCaptureContext`). User uploads, live browser streams, and unknown origins fail closed, preventing neutral domain names from masking live microphone inputs.
3. **Current Evaluation Status:** Candidate external domains (`neurovoz_studio`, `pc_gita_condenser`, `italian_parkinsons_headset`) are awaiting licensed raw-audio access under institutional DUAs. The trusted allowlist remains strictly empty (`TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`), and approved prediction compatibility remains disabled. An exploratory candidate from a self-declared category is a separate unvalidated research display only.

For comprehensive architectural and safety specifications, see:
- [`docs/M4_DOMAIN_ARCHITECTURE.md`](M4_DOMAIN_ARCHITECTURE.md)
- [`docs/M4_INDEPENDENT_DOMAIN_VALIDATION_PROTOCOL.md`](M4_INDEPENDENT_DOMAIN_VALIDATION_PROTOCOL.md)
- [`docs/M4_DOMAIN_COMPATIBILITY_DECISION_FRAMEWORK.md`](M4_DOMAIN_COMPATIBILITY_DECISION_FRAMEWORK.md)
- [`docs/M4_INFERENCE_SAFETY.md`](M4_INFERENCE_SAFETY.md)

