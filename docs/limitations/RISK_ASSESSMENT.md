# Preliminary Risk Assessment & Medical Device Software Safety Analysis

**Regulatory & Quality Standards Reference:** ISO 14971:2019 (Application of risk management to medical devices) & IEC 62304:2006/AMD 1:2015 (Medical device software — Software life cycle processes).  
**Context:** VoxNeuro Software-Only Voice Acoustic Analysis Prototype.

**Current implementation note (2026-11-13):** A separate exploratory path can display an unvalidated model candidate for a new recording when a current, locally generated research artifact and all specified evidence/input checks pass. This path is not approved inference, is not clinically validated, and must not be used in care. The previous absolute statement that all user-microphone model outputs are blocked is superseded. The hazard ratings below are an educational discussion, not a reassessed clinical risk file or a claim of acceptable patient-care risk.

---

## 1. IEC 62304 Software Safety Classification

Under IEC 62304 clause 4.3, medical device software is categorized into three safety classes based on the severity of potential injury resulting from a software failure or hazard:
- **Class A:** No injury or damage to health is possible.
- **Class B:** Non-serious injury is possible.
- **Class C:** Death or serious injury is possible.

### Hypothetical Educational Lifecycle Classification Discussion:
- **Hypothetical Software Safety Profile: Class B (Educational Discussion)**
- **Educational Context & Regulatory Status:** This analysis is an educational exploration under IEC 62304 and ISO 14971 principles, not a formal or legally binding regulatory assignment. VoxNeuro is an academic research prototype for voice acoustic analysis. It does not claim medical-device clearance, CE mark, FDA 510(k)/De Novo status, or CDSCO authorization. It does not perform clinical diagnosis, screening, or medical risk scoring.
- **Rationale:** If evaluated within a medical device software lifecycle framework, acoustic analysis and any model-derived candidate could be misconstrued without clinician oversight. The approved clinical prediction gate is blocked for user microphone inputs. The separate research candidate path uses explicit exploratory/non-domain-validated labeling, a raw uncalibrated score (not probability), provenance and OOD checks, abstention, and non-diagnostic notices. These reduce silent or unqualified output; they do not establish safety for clinical use.

---

## 2. ISO 14971 Risk Analysis Matrix (FMEA)

*(Note: The FMEA scoring methodology below is an educational engineering risk-ranking framework adapted from ISO 14971 principles for this academic software prototype. It establishes research risk-benefit trade-offs but does not replace formal notified-body clinical evaluation).*

### Scoring Criteria:
- **Severity (S):** 1 = Negligible, 2 = Minor, 3 = Moderate (temporary impairment or diagnostic delay requiring clinical follow-up), 4 = Critical (serious injury or neurodegenerative progression without intervention), 5 = Catastrophic.
- **Probability of Occurrence (P):** 1 = Improbable (<1 in 10,000), 2 = Remote, 3 = Occasional, 4 = Probable, 5 = Frequent.
- **Risk Priority Number (RPN) = S × P:**
  - **1 – 6:** Broadly Acceptable (Green)
  - **7 – 12:** As Low As Reasonably Practicable (ALARP / Yellow)
  - **14 – 25:** Unacceptable (Red; mandatory risk reduction controls required)

| Hazard ID | Hazard / Hazardous Situation | Potential Clinical Harm | Pre S | Pre P | Pre RPN | Risk Control Measures (Safety by Design & Information) | Post S | Post P | Post RPN | Residual Acceptability |
|:---:|---|---|:---:|:---:|:---:|---|:---:|:---:|:---:|:---:|
| **HAZ-01** | False reassurance from unvalidated acoustic feature summary or exploratory candidate | Delayed neurological referral; untreated neurodegenerative progression | 4 | 3 | **12** | The approved prediction gate rejects unverified domains. If a separate exploratory candidate is emitted, it is prominently labeled `EXPLORATORY — NOT DOMAIN VALIDATED`, shows an uncalibrated score and fixed research threshold rather than probability, presents its evidence limits and a non-diagnostic warning, and abstains on failed input/provenance/OOD checks. These controls reduce risk of silent/ambiguous output but cannot establish clinical safety or prevent misinterpretation. | 3 | 2 | **6** | Research use only; not assessed for care |
| **HAZ-02** | False positive flag or misinterpretation of pitch/jitter values | Patient anxiety; unnecessary costly neuroimaging (e.g. DaTscan) | 3 | 3 | **9** | Information for Safety: Clear notation that acoustic measurements have no standalone normal/abnormal cutoff; training materials emphasize values are adjunct research metrics only. | 2 | 2 | **4** | Acceptable for research |
| **HAZ-03** | Clipped, silent, or noisy audio accepted for feature extraction | Artifactual acoustic distortion misinterpreted as vocal tremor/dysarthria | 3 | 4 | **12** | Inherent Safety: Automated multi-stage signal gatekeeper rejects clipped signals (>1% threshold), silence, RMS amplitude below threshold, and audio with <15% voiced frames. Insufficient voiced pitch frames result in NaN summary features rather than corrupted numeric outputs. | 2 | 1 | **2** | Acceptable for research |
| **HAZ-04** | Demographic/Age confounding over-interpreted as disease pathology | Clinical misclassification driven by normal aging vocal changes | 4 | 4 | **16** | Protective Measure: Milestone 2 pre-registered empirical audit (`docs/reports/M2_BIAS_AUDIT_REPORT.md`) formally quantified age confounding (HC vs PD mean gap 19.31 yrs, SMD -1.61). The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators (primary-seed paired $\Delta\text{BA} = -0.0758$, 95% CI [$-0.1842, +0.0284$], supplementary McNemar exact $p = 0.2632$; repeated-CV $\Delta = -0.0681$). Caliper matching at 0.2 SD exhausted sample size (5 pairs), proving non-estimability. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain. Model card and reports prominently display comparator hierarchy and abstain from claiming acoustic disease markers. | 3 | 1 | **3** | Acceptable for research |
| **HAZ-05** | Cross-domain acoustic shift (telephone-trained model applied to a consumer device) | Incorrect exploratory candidate due to frequency response, compression, room, or task shift | 4 | 4 | **16** | Approved inference remains disabled and the trusted validation allowlist is empty. Exploratory scoring requires an explicit self-declared category and applies training-derived OOD checks, but these do not verify the hardware or prove compatibility. Candidate UI/report explicitly mark domain and clinical validation as unverified and allow abstention. | 3 | 2 | **6** | Research use only; not assessed for care |
| **HAZ-06** | Biometric re-identification from sustained voice recording | Patient confidentiality breach under India DPDP Act 2023 | 3 | 3 | **9** | Protective Measure: Local-only processing on loopback (`127.0.0.1`); audio held only in transient memory; zero cloud uploads; no audio or patient identifiers persisted by default. | 2 | 1 | **2** | Acceptable for research |
| **HAZ-07** | Incompatible model artifact or corrupted pickle bundle loaded | Arbitrary code execution or erroneous computation | 4 | 2 | **8** | Protective Measure: SHA-256 sidecar checksum verification detects accidental file modification or transfer corruption before joblib deserialization; digital security is strictly enforced by deserializing only trusted repository-internal artifacts and rejecting untrusted third-party files. | 3 | 1 | **3** | Acceptable for research |
| **HAZ-08** | Code drift between signal extraction and validation receipt | Unreproducible clinical feature definitions across versions | 3 | 3 | **9** | Protective Measure: Automated cryptographic code fingerprinting (`project_code_fingerprint`) enforced by CI/CD and verification scripts before release. | 2 | 1 | **2** | Acceptable for research |
| **HAZ-09** | User interprets a research candidate/raw score as a diagnosis or probability | Anxiety, false reassurance, or inappropriate self-management | 4 | 3 | **12** | Use explicit exploratory/non-domain-validated language, avoid risk/probability terminology, show model/evaluation context and non-diagnostic notice, preserve clinician referral guidance, and keep approved prediction disabled. These are communication controls only; user understanding has not been evaluated. | 3 | 2 | **6** | Research use only; not assessed for care |

---

## 3. Risk Management Conclusion

Within the scope of an academic research software prototype, identified hazards have been mitigated through architectural controls, automated input gatekeeping, transient in-memory processing, and explicit domain boundaries preventing diagnostic claims on microphone audio. Clinical residual risks cannot be deemed acceptable for clinical patient care without prospective multi-site clinical trials, institutional ethics approval, and formal regulatory clearance.
