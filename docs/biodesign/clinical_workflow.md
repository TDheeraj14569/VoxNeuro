# Clinical Workflow Hypothesis & Pathway Exploration

**Course / Project:** Biodesign Concept & Practice — Clinical Workflow Mapping
**Working Concept:** VoxNeuro Early Neurological Triage Prototype
**Evidence Framework & Status:**
- **Evidence Tier:** **Design Assumption & Simulated Workflow Scenario.**
- **Primary Research Status:** **Primary Research Pending.** No live clinical workflows, consultation observations, or hospital handoffs have been observed or collected. Prospective field observations require prior IEC/IRB ethical clearance and authorized clinical site agreements.

---

## 1. Hypothesized Clinical Referral Pathway (Design Assumption)

```text
Person / Family notices speech/motor change (Simulated Symptom Presentation)
        ↓
First-contact primary care physician gathers history & performs routine examination (Simulated PHC / OPD)
        ↓
Clinician considers differential etiology and specialist referral requirement (Hypothesized Triage Point)
        ↓
Neurology / movement-disorder specialist assessment & reference diagnosis (Tertiary Setting)
        ↓
Speech-language pathologist (SLP) phonatory/articulatory evaluation if indicated
        ↓
Longitudinal clinical follow-up with standardized motor and functional measures
```

---

## 2. Research Scope & Current Operational Boundary

* **VoxNeuro is Currently Outside the Clinical Care Pathway:** The current software prototype is strictly a local research tool for acoustic signal quality verification and isolated sustained-vowel (`/a/`) acoustic feature extraction.
* **No Diagnostic Insertion:** The experimental software must not be inserted into clinical referral, triage, or diagnostic pathways.
* **Microphone Inference Gated:** Live recording predictions are disabled until multi-device calibration, domain shift adaptation, and prospective clinical validation studies are completed.

---

## 3. Fieldwork Discovery Requirements (Primary Research Pending)

When institutional ethics approvals are secured, prospective primary research will map:
1. **Responsible Roles:** Primary care physicians, community health workers (ASHAs), SLPs, and neurologists.
2. **Clinical Handoffs:** Referral documentation formats, turnaround times, and drop-out rates.
3. **Workflow Barriers:** Consultation time constraints (<4 minutes in high-volume OPDs), linguistic diversity, and rural specialist scarcity.
4. **Failure Modes:** Diagnostic misattribution (e.g., confusing hypokinetic dysarthria with benign presbyphonia or respiratory fatigue).
