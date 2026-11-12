# Inference Safety Architecture and Fail-Closed Safeguards

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Safety Protocol Identifier:** `VOXNEURO-M4-SAFE-INFERENCE-V1`  
**Status:** Authoritative Security Policy  
**Effective Date:** 2026-11-12  

---

## 1. Safety Architecture and Design Principles

VoxNeuro is designed under the **fail-closed** security principle: unless every condition for safe, verified inference is explicitly proven and cryptographically validated, the system must immediately reject prediction and withhold clinical outputs.

In bioacoustic clinical decision support, the most dangerous failure modes involve silent misclassification: a user uploading arbitrary low-quality microphone audio or compressed smartphone files that the model processes without warning, producing an erroneous prediction that is interpreted clinically.

To eliminate this vulnerability, VoxNeuro implements four multi-layered gates:

```
+-----------------------------------------------------------------------------------+
|                        INCOMING INFERENCE REQUEST                                 |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| GATE 1: Input Domain Verification                                                 |
| - Domain label must be non-empty and canonicalized.                               |
| - Domain must be declared in bundle["validated_input_domains"].                   |
| - Domain must NOT match any microphone or live-capture token.                     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| GATE 2: Cryptographic Evidence & Allowlist Verification                           |
| - Bundle must contain valid domain validation JSON payload.                       |
| - Stored evidence SHA-256 must match digest of JSON payload.                      |
| - Evidence digest must exist in source TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256.   |
|   (Currently frozenset() -> ALL candidate domains fail closed).                   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| GATE 3: Capture Origin & Provenance Contract                                      |
| - Capture context must indicate verified research acquisition.                    |
| - Capture origin must be 'pre_recorded_research' or 'controlled_research_session'.|
| - Origins 'user_upload', 'live_browser_mic', 'live_app_mic', 'unknown' -> REJECT. |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| GATE 4: Feature Schema & Preprocessing Integrity                                  |
| - Schema version must equal 'voxneuro.voice.v3'.                                  |
| - 39 features present in exact canonical order, all finite numeric values.        |
| - Schema fingerprint, feature config hash, and preprocessing hash must match.     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                       OUTPUT: EXPERIMENTAL RESEARCH CLASS                         |
| (clinical_probability is ALWAYS None; non-diagnostic experimental status)        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Invariant Policies

### 2.1 Live Microphone Prohibition
- `allow_user_microphone_inference` is hardcoded to `false` in `configs/model_config.yaml`.
- Any domain identifier or capture origin containing tokens such as `mic`, `microphone`, `smartphone`, `browser`, `live`, `mobile`, `webcam`, `laptop`, or `upload` is unconditionally rejected by `is_microphone_domain()`.

### 2.2 Empty Trusted Allowlist
- `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` in `src/voxneuro/modeling/domains.py` is initialized to `frozenset()`.
- Automated testing, benchmark scripts, and candidate dossier generators are strictly prohibited from mutating or appending to this set.
- Candidate dossiers conforming to `voxneuro.domain_assessment.v1` are rejected by `load_domain_validation_report()`.

### 2.3 Strict Origin Verification
- A valid domain identifier alone is insufficient to permit inference. The calling application must present an explicit `InputCaptureContext` certifying an authorized research provenance.
- Ad-hoc client uploads and unspecified origins fail closed.

---

## 3. Human Approval Workflow

To transition any candidate recording domain into an approved domain:

1. **Protocol Execution:** Complete the frozen validation protocol `VOXNEURO-M4-EXT-VAL-2026-V1` on an independent, IRB-approved cohort.
2. **Dossier Audit:** Review the generated candidate dossier (`voxneuro.domain_assessment.v1`), verifying that $N \ge 50$, $N_{\text{group}} \ge 20$, Balanced Accuracy lower CI bound $\ge 0.70$, and attrition rate $< 25\%$.
3. **Dual Maintainer Sign-Off:** Two authorized maintainers (one biostatistician, one clinical voice specialist) must sign an audit receipt.
4. **Source Code Commit:** The candidate report's SHA-256 digest is manually committed to `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` in `src/voxneuro/modeling/domains.py`, and the domain ID is added to `approved_domains` in `configs/recording_domain_registry.yaml`.
