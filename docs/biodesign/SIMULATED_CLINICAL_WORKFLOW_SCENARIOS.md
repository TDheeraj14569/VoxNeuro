# Simulated Clinical Workflow Scenarios & Synthetic Stakeholder Synthesis

> [!IMPORTANT]
> **Fictional Simulation & Academic Integrity Notice:**
> All clinical scenarios, patient descriptions, numerical examples, and clinician statements in this document are fictional illustrations developed exclusively for academic Biodesign Concept & Practice coursework. No real patient observations, human-subject fieldwork, or clinical stakeholder interviews have been collected. Authorized human-subject clinical research requires formal Institutional Ethics Committee (IEC) / Institutional Review Board (IRB) approval, written informed consent, and adherence to GCP/ICH guidelines.

**Course Reference:** Biodesign Concept & Practice — Clinical Need Identification & Workflow Discovery.  
**Context:** Multi-stakeholder qualitative exploration for vocal biomarker screening in Parkinson's Disease (Simulated Primary Care & Movement Disorder Neurology Pathways, India).

---

## 1. Structured Clinical Observation Scenarios (Illustrative Walkthroughs)

### Scenario OBS-001: General Medicine Outpatient Department (OPD)
* **Setting:** Taluk Hospital / Sub-District Hospital OPD, Maharashtra, India.
* **Context:** Morning general clinic session; high patient volume (~90 patients per 4-hour OPD).
* **Observed Process:** 
  - Patient (Male, 64 years) presents with generalized fatigue, slow gait, and low vocal loudness ("voice getting softer and muffled" noticed by daughter).
  - First-contact medical officer performs basic physical exam (blood pressure, pulse, cranial nerve screening).
  - Voice symptom is recorded in handwritten notes as "general weakness / hoarseness due to chronic cough".
  - Patient is prescribed multivitamins and referred to ENT for laryngoscopy. No neurology referral initiated.
* **Failure Mode / Clinical Need:** 
  Early hypokinetic dysarthria (hypophonia and monotonic pitch) is easily confounded with normal aging or non-neurological laryngeal conditions. Primary care doctors lack a rapid, objective screening tool to quantify phonatory stability during short consultation times (<4 minutes per patient).

### Scenario OBS-002: Movement Disorder Specialty Clinic
* **Setting:** Tertiary Teaching Hospital Neurology OPD, New Delhi, India.
* **Observed Process:** 
  - Neurologist evaluates confirmed Parkinson's patient (Female, 58 years, Hoehn & Yahr Stage II).
  - Assessment relies on Movement Disorder Society Unified Parkinson's Disease Rating Scale (MDS-UPDRS Part III). Item 3.1 (Speech) is scored on a subjective 0–4 scale based on conversational clarity.
  - Neurologist notes difficulty tracking day-to-day voice fluctuations between medication "ON" and "OFF" states.
* **Clinician Feedback (Illustrative Scenario):**
  - *"If a software tool can record a 4-second sustained vowel, check signal quality, and provide standardized acoustic metrics (jitter, shimmer, fundamental frequency variability), it would give us an objective longitudinal trendline rather than relying solely on subjective 0–4 scoring."*

---

## 2. Simulated Stakeholder Needs Matrix

| Stakeholder Role | Key Clinical Insights & Unmet Needs | Design Requirements for Software |
|---|---|---|
| **Movement Disorder Neurologist** | Most patients present late (Hoehn & Yahr Stage II/III) when motor symptoms (resting tremor, rigidity) are obvious. Voice changes often precede motor signs by 2–5 years, but are missed. | • Must not claim diagnostic certainty.<br>• Must provide transparent, versioned acoustic metrics (F0, HNR, Jitter).<br>• Must exclude non-conforming or clipped audio. |
| **Primary Care Physician (MBBS)** | Consultation times are constrained (3–5 minutes). Referral pathways to government neurologists have 4–6 month waiting lists; cannot refer everyone without objective rationale. | • Zero-setup software running on standard browser.<br>• Instant feedback on recording quality.<br>• Simple 1-page printable/downloadable summary for referral attachment. |
| **Speech-Language Pathologist (SLP)** | Sustained vowel `/a/` is the ideal task because it minimizes language/dialect confounding across diverse linguistic populations in India, isolating phonatory mechanics from lexical processing. | • Strictly standardize microphone distance (~15 cm).<br>• Explicitly reject background ambient noise and reverberant recordings. |
| **Patient & Caregiver** | Early changes in voice (loss of projection, monotony, frequent requests by family to repeat words) caused social withdrawal and anxiety before diagnosis. | • Non-intimidating test (3–5 seconds breathing and phonation).<br>• Privacy guarantee: voice recordings must not be uploaded to unverified third-party cloud servers. |

---

## 3. Needs Statement Refinement

From this qualitative synthesis, the Biodesign Need Statement is refined from preliminary assumption to structured specification:

> **"A standardized, privacy-preserving acoustic analysis software for primary care and community clinicians to objectively measure sustained phonatory stability in adults with suspected early vocal changes, to support timely, evidence-backed neurological referrals while preventing false reassurance and avoiding uncalibrated automated diagnoses."**
