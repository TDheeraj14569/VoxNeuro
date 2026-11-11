# Biodesign Need Statement Development: Voice-Based Early Neurological Screening

**Course / Project:** Biodesign Concept & Practice — Early Neurological Screening
**Working Hypothesis:** Voice-Based Early Neurological Disease Detection (VoxNeuro)
**Document Status:** Academic Research Preparation & Baseline Specification
**Evidence Framework:** All clinical and technical statements in this document are strictly classified into four evidential tiers:
1. **Published Literature Evidence** — Findings supported by documented peer-reviewed literature or official epidemiological registries.
2. **Design Assumptions** — Preliminary working hypotheses established for prototype exploration, pending independent clinical validation.
3. **Simulated Workflow Scenarios** — Illustrative academic walkthroughs developed to test operational constraints without human-subject claims.
4. **Primary Research Pending** — Formal prospective clinician interviews, clinic observations, and stakeholder feedback awaiting institutional ethics approval.

---

## 1. Strategic Focus Area & Passion

### Identification
* **Academic Interest & Passion (Design Assumption):** Computational speech signal processing, acoustic phonetics, and machine learning applied to early digital biomarkers for healthcare.
* **Secondary Literature Evidence:** Neurological disorders are a leading cause of global disability-adjusted life years (DALYs) (GBD 2021). Speech and phonatory irregularities (hypokinetic dysarthria) frequently accompany neurodegenerative conditions such as Parkinson's disease (Atalar et al., 2023; Ngo et al., 2022).
* **Primary Research Status:** *Primary research pending.* Prospective field observations of patient families, frontline health workers, and specialist clinics have not yet been executed.

### Strategic Selection Criteria
* **Clinical Need Alignment:** High unmet burden in low-resource and rural settings where access to specialist neurology is constrained.
* **Economic & Manufacturing Advantage:** Software-only algorithmic approach; eliminates specialized medical device manufacturing costs by operating on ubiquitous consumer mobile hardware.
* **Technological Readiness:** Mobile audio capture hardware and statistical acoustic feature extractors (e.g., Praat, digital signal processing algorithms) are mature.
* **National Healthcare Priorities:** Aligns with Indian Council of Medical Research (ICMR) and National Mental Health Program priorities for non-communicable neurological disorders and aging populations.

---

## 2. Unmet Need Identification & Clinical Contexts

### Clinical Gaps Identified via Literature and Simulated Walkthroughs
* **Simulated Workflow Observation:** In rural community camps and busy primary health centre (PHC) outpatient clinics, older adults presenting with non-specific fatigue, subtle movement slowness, or mild vocal dampening are rarely screened with objective tools. Initial signs are evaluated subjectively by ear or described by family members, frequently leading to misattribution (e.g., normal aging, chronic laryngitis) and delayed referral.
* **Three Recurring Bottlenecks (Design Assumptions):**
  1. *Absence of objective screening tools* suitable for high-throughput, short-consultation primary care (<4 minutes per patient).
  2. *Severe concentration of neurological expertise* and diagnostic equipment (MRI, DaTscan) in metropolitan tertiary centers.
  3. *Lack of structured longitudinal trend tracking* for subtle motor/phonatory decline prior to overt physical disability.
* **Impact on Clinical Outcome:** Unnecessary diagnostic delay (often 1–3 years from symptom onset), resulting in missed windows for early pharmacological or therapeutic intervention.
* **Volume and Frequency:** *Primary research pending.* Exact incidence and referral conversion rates are to be quantified through formal primary care observational audits.

### Hypothesized & Simulated Care Contexts
1. **Primary Care Outpatient Clinic (Simulated Scenario):** Constrained consultation times prevent thorough cranial nerve and speech examination. Frontline doctors require rapid objective triage guidance.
2. **Rural Health Camp (Simulated Scenario):** Complete absence of specialist diagnostic infrastructure; screening relies entirely on portable, robust software capable of offline operation.
3. **Tertiary Movement Disorder Clinic (Simulated Scenario):** High patient backlogs where neurologists need pre-screened, objectively triaged referrals with standardized acoustic baselines.

---

## 3. Need Statement Formulation

### Core Structural Elements
* **WHO (Target Population):** Adults presenting with subtle, early suspected neurological symptoms outside specialist centers.
* **WHERE (Care Context):** Primary care and community health settings with limited specialist neurological access.
* **WHY (Clinical Outcome):** To reduce diagnostic delay, eliminate subjective referral bottlenecks, and enable timely, appropriate specialist consultation.

### Formal Solution-Independent Need Statement
> **“A way to detect early neurological disease in adults with subtle symptoms in primary care and community settings with limited specialist access, to reduce diagnostic delay and enable timely referral.”**

### Decomposition
* **Problem:** Early neurological conditions are recognized late, inconsistently, and through subjective, uncalibrated observation.
* **Population:** Adult patients in primary care and community networks before specialist evaluation.
* **Outcome:** Quantifiable reduction in time from first presentation to appropriate neurological referral.
* **Solution Independence:** The statement does not embed voice analysis, machine learning, mobile apps, or specific sensors, preserving all potential solution pathways.

---

## 4. Need Statement Validation Against Common Pitfalls

| Pitfall | Status | Evaluation & Mitigation |
|---|---|---|
| **Too General** | Avoided | Specifically defines the population (adults with subtle early symptoms) and clinical setting (primary care with limited specialist access). |
| **Too Specific** | Avoided | Encompasses early neurological disease broadly rather than restricting to a single disease subtype (e.g., only Parkinson's) or single acoustic metric. |
| **Stuck in Current Practice** | Avoided | Focuses strictly on desired diagnostic timeliness and objectivity, not on mimicking current paper-based or subjective bedside scoring. |
| **Embedded Solution** | Avoided | Mentions no hardware, software, voice tasks, or AI algorithms; technical pathways remain entirely open. |
| **Built on a Negative** | Avoided | Framed positively around enabling timely detection and actionable referral rather than merely lamenting specialist scarcity. |

---

## 5. Multi-Dimensional Need Scoping

### a. Clinical Relevance (Published Literature Evidence)
* Neurological conditions represent a major and expanding contributor to global mortality and disability (GBD 2021).
* In Parkinson's disease, subclinical vocal changes (hypophonia, pitch monopitch, tremor) often develop years before classical resting tremor or postural instability become debilitating (Atalar et al., 2023; Tsanas et al., 2010).
* Timely clinical triage directly improves patient management and therapeutic optimization.

### b. Stakeholder Perspectives (Design Assumptions — Primary Research Pending)
* **Patients & Families:** Earlier objective validation of subtle symptoms with reduced travel burden, waiting times, and financial stress.
* **Primary Care Physicians:** An intuitive, rapid (under 1 minute), objective decision-support aid that substantiates specialist referral decisions without adding clinical overhead.
* **Movement Disorder Neurologists:** Higher-quality, triaged referrals accompanied by objective quantitative metrics rather than vague subjective notes.
* **Health Systems & Public Payers:** Cost-effective disease screening that mitigates downstream disability expenditure through earlier intervention.

### c. Market & Clinical Potential
* **Adjacent Domains:** Digital health diagnostics, remote patient monitoring (RPM), tele-neurology, and vocal biomarker screening.
* **Target Segment:** Point-of-care mobile screening applications for neurodegenerative conditions; commercial adoption requires formal prospective clinical evidence.

### d. Technical Feasibility & Engineering Challenges
* **Exploratory Approach:** Standardized sustained vowel phonation (`/a/`), automated signal quality assurance, acoustic feature extraction (F0, jitter, shimmer, HNR, MFCCs), and statistical classification.
* **Engineering Bottlenecks:** Variable smartphone microphone frequency response, ambient acoustic noise, acoustic clipping, participant dialect/accent variations, dataset domain shift, and model explainability.

### e. Regulatory & Quality Considerations
* **Software as a Medical Device (SaMD):** Likely classified as Class B or Class C SaMD under CDSCO Medical Device Rules 2017 (India) and US FDA SaMD guidelines.
* **Clinical Evaluation Requirements:** Formal prospective clinical investigation, analytical validation, software life-cycle compliance (IEC 62304), and clinical risk management (ISO 14971).

### f. Competitive Landscape & Gaps
* **Current Alternatives:** Subjective clinical history taking, MDS-UPDRS scoring, brain imaging (MRI, SPECT), and commercial speech research tools (e.g., Sonde Health, Canary Speech).
* **Unmet Gaps:** Commercial solutions are predominantly proprietary, cloud-dependent, calibrated on high-resource English datasets, and unvalidated for frontline public healthcare delivery in India.

---

## 6. Need Categorization & Strategic Positioning

* **Need Type:** **Mixed Need** — Leverages established acoustic analysis principles and machine learning algorithms, but addresses major unsolved challenges in low-resource multi-device calibration, clinical workflow integration, and cross-population generalizability.
* **Physiological Level:** **Intermediate (Branch) Level**
  * *Downstream (Leaves):* Managing advanced physical disability after late clinical diagnosis (palliative / symptomatic).
  * *Intermediate (Branch):* **Detecting early functional impairment to accelerate referral and treatment initiation (Target Need).**
  * *Upstream (Trunk):* Primary prevention of underlying neurodegenerative pathology (unsolved biological frontier).

---

## 7. Refined Need Statement & Technical Boundary

### Refined Need Statement
> **“A low-cost, accessible way to detect early neurological disease in adults with subtle symptoms in primary care and community settings, giving an objective result and referral guidance without specialist equipment.”**

### Exploration Pathways Evaluated
1. **Voice and Acoustic Analysis Software (Selected Pathway):** Rapid, non-invasive, hardware-agnostic, low implementation cost.
2. **Digital Cognitive Screening App:** Mobile tablet assessments for memory and processing speed; higher linguistic and educational bias.
3. **Camera-Based Movement Analysis:** Video capture of gait and tremor; constrained by room lighting, privacy concerns, and camera positioning.

### Explicit Technical Scope of the VoxNeuro Prototype
* **Exploratory Academic Scope:** VoxNeuro investigates whether standardized sustained-vowel phonation (`/a/`) recorded via web browser interfaces yields stable acoustic feature representations (Core39: F0, jitter, shimmer, HNR, spectral dynamics).
* **Definite Clinical Boundaries:**
  * **Not a Diagnostic Tool:** VoxNeuro is an academic research prototype and does not provide diagnostic classifications or clinical determinations.
  * **Not Comprehensive Speech Assessment:** The prototype evaluates isolated sustained-vowel phonatory stability only; it does not analyze articulation, prosody, fluency, lexical complexity, or connected speech.
  * **Microphone Prediction Disabled:** Live microphone inference is programmatically locked out until multi-device acoustic calibration, domain adaptation, and prospective ethics-approved clinical trials are completed.

---

## 8. Associated Artifacts and Generator

* **Need Statement PDF Document:** `docs/biodesign/Voice_Neuro_Detection_Need_Statement.pdf`
* **Reproducible PDF Generator:** `docs/biodesign/generate_need_statement_pdf.py`
* **Execution Command:** `uv run --with reportlab python docs/biodesign/generate_need_statement_pdf.py`
