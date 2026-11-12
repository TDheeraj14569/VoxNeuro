# Domain Compatibility Decision Framework

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Document Identifier:** `VOXNEURO-M4-DECISION-FRAMEWORK-V1`  
**Status:** Authoritative Governance Policy  
**Effective Date:** 2026-11-12  

---

## 1. Purpose and Philosophy

In clinical bioacoustics and healthcare artificial intelligence, performance in cross-validation within a single development cohort frequently overstates real-world generalizability. Acoustic domain shifts—arising from microphone transducer frequency response, anti-aliasing filters, room reverberation, codec quantization, and automatic gain control—can catastrophically degrade machine learning models.

This framework defines the five mutually exclusive governance statuses for recording domains in VoxNeuro. It specifies the necessary and sufficient criteria for transitioning between states and establishes that **no automated process may ever transition a domain to approved status**.

```
                           +------------------------------------------------------+
                           |   CANDIDATE DOMAIN IDENTIFIED & REGISTERED           |
                           +------------------------------------------------------+
                                                     |
                                                     v
                           +------------------------------------------------------+
                           | Are independent raw audio & DUA available locally?   |
                           +------------------------------------------------------+
                                          /                          \
                                         / NO                         \ YES
                                        v                              v
           +---------------------------------------------+   +---------------------------------------------+
           | FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING |   | CANDIDATE_DOMAIN_EVALUATED_PENDING_REVIEW   |
           +---------------------------------------------+   +---------------------------------------------+
                                                                            |
                                                                            v
                                                             +-----------------------------+
                                                             | Independent Maintainer      |
                                                             | Clinical & Biostat Review   |
                                                             +-----------------------------+
                                                              /              |             \
                                                             / FAIL          | REJECT       \ PASS
                                                            v                v               v
                                            +--------------------+ +--------------------+ +-------------------------------+
                                            | DOMAIN_VALIDATION_ | | DOMAIN_VALIDATION_ | | DOMAIN_COMPATIBILITY_APPROVED |
                                            | BLOCKED            | | REJECTED           | | (Manual git commit only)      |
                                            +--------------------+ +--------------------+ +-------------------------------+
```

---

## 2. Categorical Decision States

### 2.1 State A: `FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING`
- **Application Condition:** Assigned when the software domain validation architecture, data structures, metadata schemas, and statistical evaluation engines are implemented and fully verified via automated tests, but no independent raw-audio clinical cohort is licensed and stored locally.
- **Criteria:**
  1. Registry configuration (`recording_domain_registry.yaml`) is valid.
  2. Candidate domain metadata is fully documented without fabricating missing fields.
  3. No unverified external audio files are imported.
  4. Empirical evaluation has not been executed.
- **Inference Eligibility:** Strictly `false`.
- **Maintainer Approval:** Strictly `UNREVIEWED`.

### 2.2 State B: `CANDIDATE_DOMAIN_EVALUATED_PENDING_REVIEW`
- **Application Condition:** Assigned when an independent, clinically diagnosed raw-audio cohort has been processed under the frozen protocol, producing complete performance and domain-shift dossiers.
- **Criteria:**
  1. Participant disjointness with development data is verified.
  2. Protocol `VOXNEURO-M4-EXT-VAL-2026-V1` was followed without post-hoc threshold selection or retraining.
  3. Participant-level stratified bootstrap ($B=1,000$) confidence intervals are computed.
  4. Acquisition and feature-level domain shift (SMD, KS test, FDR correction) is documented.
  5. Dossier conforms to `voxneuro.domain_assessment.v1`.
- **Inference Eligibility:** Strictly `false`.
- **Maintainer Approval:** Strictly `UNDER_REVIEW`.

### 2.3 State C: `DOMAIN_VALIDATION_BLOCKED`
- **Application Condition:** Assigned when an external evaluation cannot proceed or is halted due to insurmountable data governance, ethical, or technical obstacles.
- **Criteria (any of the following):**
  1. Failure to obtain executed Data Use Agreement (DUA) or institutional review board clearance.
  2. Identification of participant overlap with the UAMS development cohort.
  3. Severe task incompatibility (e.g. absence of sustained vowel phonation).
  4. Audio quality failure rate exceeding 40% of attempted recordings.
- **Inference Eligibility:** Strictly `false`.
- **Maintainer Approval:** Strictly `BLOCKED`.

### 2.4 State D: `DOMAIN_VALIDATION_REJECTED`
- **Application Condition:** Assigned when an external evaluation was completed, but empirical findings demonstrate that the frozen reference model cannot be safely applied to the candidate domain.
- **Criteria (any of the following):**
  1. Lower bound of 95% confidence interval for Balanced Accuracy falls below 0.60.
  2. Specificity or Sensitivity lower bound falls below 0.50 (worse than or equal to chance).
  3. Severe feature-level shift where $>50\%$ of Core39 features exhibit statistically significant divergence post-FDR ($p_{\text{FDR}} < 0.05$) with mean $|d| > 1.0$.
  4. Evidence of severe acquisition artifact (e.g. non-linear codec clipping, extreme aggressive AGC suppression) distorting pitch or spectral harmonics.
- **Inference Eligibility:** Strictly `false`.
- **Maintainer Approval:** Strictly `REJECTED`.

### 2.5 State E: `DOMAIN_COMPATIBILITY_APPROVED`
- **Application Condition:** Reserved exclusively for domains that have undergone rigorous independent scientific evaluation, clinical peer review, and formal maintainer sign-off.
- **Strict Non-Automated Approval Invariant:**
  1. Approval requires unanimous sign-off by at least two maintainers (one biostatistical, one clinical).
  2. The candidate assessment dossier's exact SHA-256 digest is manually committed to `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256` in `src/voxneuro/modeling/domains.py`.
  3. The domain ID is explicitly appended to `approved_domains` in `configs/recording_domain_registry.yaml`.
  4. The domain must never involve live microphone or mobile browser audio capture (`allow_user_microphone_inference` remains `false`).
- **Inference Eligibility:** `true` (restricted strictly to the validated input domain and validated research capture origins).

---

## 3. Authoritative Decision for Milestone 4

Under the criteria established above:
- Software domain-validation framework: **VERIFIED**.
- Local independent raw-audio access under DUA: **ACCESS_PENDING**.
- Formal Milestone 4 Status:
  $$\mathbf{FRAMEWORK\_VERIFIED\_DOMAIN\_VALIDATION\_PENDING}$$
- Model Inference Policy: **FAIL-CLOSED** (`allow_user_microphone_inference: false`, `approved_domains: []`, `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256: frozenset()`).
