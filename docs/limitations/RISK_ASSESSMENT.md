# Preliminary Risk Assessment & Medical Device Software Safety Analysis

**Regulatory & Quality Standards Reference:** ISO 14971:2019 (Application of risk management to medical devices) & IEC 62304:2006/AMD 1:2015 (Medical device software — Software life cycle processes).  
**Context:** VoxNeuro Software-Only Voice Acoustic Analysis Prototype.

---

## 1. IEC 62304 Software Safety Classification

Under IEC 62304 clause 4.3, medical device software is categorized into three safety classes based on the severity of potential injury resulting from a software failure or hazard:
- **Class A:** No injury or damage to health is possible.
- **Class B:** Non-serious injury is possible.
- **Class C:** Death or serious injury is possible.

### Hypothetical Educational Lifecycle Classification Discussion:
- **Hypothetical Software Safety Profile: Class B (Educational Discussion)**
- **Educational Context & Regulatory Status:** This analysis is an educational exploration under IEC 62304 and ISO 14971 principles, not a formal or legally binding regulatory assignment. VoxNeuro is an academic research prototype for voice acoustic analysis. It does not claim medical-device clearance, CE mark, FDA 510(k)/De Novo status, or CDSCO authorization. It does not perform clinical diagnosis, screening, or medical risk scoring.
- **Rationale:** If evaluated within a medical device software lifecycle framework, acoustic analysis of voice signals as an adjunct decision-support tool would correspond to non-serious indirect harm potential if misconstrued without clinician oversight. Inherent architectural controls (blocking automated disease classification on user microphone audio, prominent non-diagnostic notices, and explicit domain restrictions) mitigate these risks within the research environment.

---

## 2. ISO 14971 Risk Analysis Matrix (FMEA)

### Scoring Criteria:
- **Severity (S):** 1 = Negligible, 2 = Minor, 3 = Moderate (temporary impairment), 4 = Critical (serious injury/progression), 5 = Catastrophic.
- **Probability of Occurrence (P):** 1 = Improbable (<1 in 10,000), 2 = Remote, 3 = Occasional, 4 = Probable, 5 = Frequent.
- **Risk Priority Number (RPN) = S × P:**
  - **1 – 6:** Broadly Acceptable (Green)
  - **7 – 12:** As Low As Reasonably Practicable (ALARP / Yellow)
  - **14 – 25:** Unacceptable (Red; mandatory risk reduction controls required)

| Hazard ID | Hazard / Hazardous Situation | Potential Clinical Harm | Pre S | Pre P | Pre RPN | Risk Control Measures (Safety by Design & Information) | Post S | Post P | Post RPN | Residual Acceptability |
|:---:|---|---|:---:|:---:|:---:|---|:---:|:---:|:---:|:---:|
| **HAZ-01** | False reassurance from unvalidated acoustic feature summary | Delayed neurological referral; untreated neurodegenerative progression | 4 | 3 | **12** | Inherent Safety: Application completely blocks automated disease classification on user microphone audio; explicit non-diagnostic notice displayed prominently on all UI pages and reports. | 3 | 1 | **3** | Acceptable for research |
| **HAZ-02** | False positive flag or misinterpretation of pitch/jitter values | Patient anxiety; unnecessary costly neuroimaging (e.g. DaTscan) | 3 | 3 | **9** | Information for Safety: Clear notation that acoustic measurements have no standalone normal/abnormal cutoff; training materials emphasize values are adjunct research metrics only. | 2 | 2 | **4** | Acceptable for research |
| **HAZ-03** | Clipped, silent, or noisy audio accepted for feature extraction | Artifactual acoustic distortion misinterpreted as vocal tremor/dysarthria | 3 | 4 | **12** | Inherent Safety: Automated multi-stage signal gatekeeper rejects clipped signals (>1% threshold), silence, RMS amplitude below threshold, and audio with <15% voiced frames. Insufficient voiced pitch frames result in NaN summary features rather than corrupted numeric outputs. | 2 | 1 | **2** | Acceptable for research |
| **HAZ-04** | Demographic/Age confounding over-interpreted as disease pathology | Clinical misclassification driven by normal aging vocal changes | 4 | 4 | **16** | Protective Measure: Age-only and age+voice baseline comparators documented in model card; voice-only models strictly exclude age/sex predictors; model card warns clinicians of UAMS age imbalance. | 3 | 2 | **6** | Acceptable for research |
| **HAZ-05** | Cross-domain acoustic shift (Telephone model applied to smartphone mic) | Diagnostic failure due to mismatched frequency response and compression | 4 | 4 | **16** | Inherent Safety: `can_predict_recording_domain()` hard-coded to reject live microphone and browser audio domains until empirical equivalence is demonstrated. | 3 | 1 | **3** | Acceptable for research |
| **HAZ-06** | Biometric re-identification from sustained voice recording | Patient confidentiality breach under India DPDP Act 2023 | 3 | 3 | **9** | Protective Measure: Local-only processing on loopback (`127.0.0.1`); audio held only in transient memory; zero cloud uploads; no audio or patient identifiers persisted by default. | 2 | 1 | **2** | Acceptable for research |
| **HAZ-07** | Incompatible model artifact or corrupted pickle bundle loaded | Arbitrary code execution or erroneous computation | 4 | 2 | **8** | Protective Measure: SHA-256 sidecar checksum verification detects accidental file modification before joblib deserialization, while trust is strictly enforced by repository artifact isolation and rejection of untrusted third-party bundle files. | 3 | 1 | **3** | Acceptable for research |
| **HAZ-08** | Code drift between signal extraction and validation receipt | Unreproducible clinical feature definitions across versions | 3 | 3 | **9** | Protective Measure: Automated cryptographic code fingerprinting (`project_code_fingerprint`) enforced by CI/CD and verification scripts before release. | 2 | 1 | **2** | Acceptable for research |

---

## 3. Risk Management Conclusion

Within the scope of an academic research software prototype, identified hazards have been mitigated through architectural controls, automated input gatekeeping, transient in-memory processing, and explicit domain boundaries preventing diagnostic claims on microphone audio. Clinical residual risks cannot be deemed acceptable for clinical patient care without prospective multi-site clinical trials, institutional ethics approval, and formal regulatory clearance.
