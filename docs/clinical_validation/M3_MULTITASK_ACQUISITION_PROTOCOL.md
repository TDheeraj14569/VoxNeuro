# Clinical Investigation Protocol: Multi-Task Voice Assessment in Parkinson's Disease

**Protocol Identifier:** VN-M3-CLIN-001  
**Study Title:** Prospective Multi-Task Acoustic Battery for Speech Biomarker Characterization in Parkinson's Disease  
**Sponsor/Academic Center:** VoxNeuro Research Consortium  
**Phase:** Exploratory Technology Characterization / Observational Biomarker Validation  
**Target Release:** Milestone 3 Baseline  

---

## 1. Background & Scientific Rationale

Parkinson's disease (PD) impairs speech motor function in up to 90% of individuals across disease progression. However, single sustained-vowel phonation captures only phonatory stability. The multi-task speech battery defined in VoxNeuro Milestone 3 introduces Diadochokinetic Syllable Repetition (AMR/SMR), Connected Speech (standard reading passage), and Vowel Space Area (formant working range).

This prospective protocol establishes the methodology required to acquire paired multi-task audio across rigorously matched PD and Healthy Control (HC) cohorts to evaluate clinical validity.

---

## 2. Study Objectives & Primary Hypotheses

### Primary Objective
To prospectively evaluate the diagnostic discriminatory ability of a multi-task speech battery compared to sustained vowel phonation alone in age- and sex-matched cohorts.

### Primary Hypotheses
1. **$H_1$ (Multidimensional Superiority):** Combining phonatory (Core39), diadochokinetic (rate/variability), and prosodic (connected speech) features will yield significantly higher cross-validated balanced accuracy than sustained vowels alone.
2. **$H_2$ (Articulatory Sensitivity):** Vowel Space Area (VSA) and Formant Centralization Ratio (FCR) will exhibit negative correlation with clinical motor severity (MDS-UPDRS Part III speech item 3.1).
3. **$H_3$ (Dopaminergic Responsiveness):** DDK rate and pause fraction will demonstrate measurable sensitivity between ON-medication and OFF-medication states in individuals with motor fluctuations.

---

## 3. Patient Cohort & Eligibility Criteria

### 3.1 Parkinson's Disease Cohort ($N = 100$)
**Inclusion Criteria:**
- Clinically diagnosed idiopathic Parkinson's disease according to UK Parkinson's Disease Society Brain Bank criteria or Movement Disorder Society (MDS) clinical diagnostic criteria.
- Age between 50 and 80 years.
- Hoehn and Yahr stage I–III in the ON-medication state.
- Stable dopaminergic medication regimen for at least 4 weeks prior to enrollment.
- Native or fluent speaker of the protocol test language.

**Exclusion Criteria:**
- Atypical or secondary parkinsonism (e.g., PSP, MSA, vascular parkinsonism).
- Prior history of neurosurgical intervention (Deep Brain Stimulation - DBS, focused ultrasound).
- Co-morbid neurological conditions (stroke, traumatic brain injury, dementia - MoCA $< 22$).
- Primary laryngeal pathology (vocal cord nodules, polyps, vocal fold paralysis) or active upper respiratory infection within 2 weeks of recording.
- Severe hearing impairment preventing comprehension of spoken instructions.

### 3.2 Healthy Control Cohort ($N = 100$)
**Inclusion Criteria:**
- Age and biological sex frequency-matched to the PD cohort (within 3-year age bins and equal sex ratios).
- No personal history of neurodegenerative disease, movement disorder, or chronic neurological illness.
- Normal cognitive screening (MoCA $\ge 26$).
- Native or fluent speaker of the protocol test language.

---

## 4. Medication State Standardization

Because dopaminergic therapy influences speech motor performance:
1. **Standard Assessment (ON State):** Assessments are conducted during the patient's defined clinical "ON" state, approximately 60 to 90 minutes following their usual morning levodopa dose.
2. **Optional Fluctuation Sub-study (OFF vs. ON):** In a designated sub-cohort ($N = 30$), recordings are obtained:
   - **Practically Defined OFF:** Following a minimum 12-hour overnight withdrawal of dopaminergic medication.
   - **Defined ON:** 60 minutes post-administration of standard dispersible levodopa challenge.

---

## 5. Standardized Acquisition Environment & Setup

- **Acoustic Environment:** Sound-attenuated booth or quiet private examination room ($\le 40$ dBA ambient sound pressure level).
- **Instrumentation:**
  - Headset-mounted condenser microphone with fixed cardioid pickup pattern (e.g., AKG C520 or Shure SM35).
  - Microphone placed 5 cm from the mouth corner at a 45° angle to minimize plosive pop artifacts.
  - Dedicated USB audio interface with 24-bit linear PCM conversion at 44.1 kHz or 48 kHz.
- **Physical Position:** Patient seated upright in a straight-backed chair with feet flat on the floor.

---

## 6. Multi-Task Execution Sequence

The complete assessment takes approximately 12–15 minutes, following this exact sequence:

```
[Orientation & Microphone Check] (2 min)
  │
  ├── [Task 1: Sustained Phonation] ── 3 trials of /a/ (5 s each)
  │     (30 s rest)
  │
  ├── [Task 2: Diadochokinesis (DDK)]
  │     ├── AMR /pa/ ── 2 trials (5-7 s each)
  │     ├── AMR /ta/ ── 2 trials (5-7 s each)
  │     ├── AMR /ka/ ── 2 trials (5-7 s each)
  │     └── SMR /pa-ta-ka/ ── 2 trials (5-7 s each)
  │     (60 s rest)
  │
  ├── [Task 3: Connected Speech] ── Standardized Passage Reading (Bamboo / Grandfather)
  │     (30 s rest)
  │
  └── [Task 4: Corner Vowels for VSA]
        ├── /a/ ── 2 trials (3 s each)
        ├── /i/ ── 2 trials (3 s each)
        └── /u/ ── 2 trials (3 s each)
```

---

## 7. Data Management, Privacy & Regulatory Compliance

1. **De-Identification & Provenance:** Audio files are assigned a cryptographically random UUID4. No protected health information (PHI) or participant names are included in filenames or metadata.
2. **No Real-Time Cloud Upload:** Recordings are processed locally in volatile session memory.
3. **Institutional Review Board (IRB) / Ethics:** Protocol must receive prior approval from the Institutional Review Board (IRB) or Independent Ethics Committee (IEC). Written informed consent is obtained from all participants prior to study procedures.
4. **FDA Regulatory Status:** This protocol is an exploratory non-significant risk (NSR) research investigation under 21 CFR 812.2(b). VoxNeuro software is not cleared as a medical device.
