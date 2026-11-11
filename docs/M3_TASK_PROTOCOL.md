# VoxNeuro Milestone 3: Standardized Multi-Task Speech Protocol

**Version:** 3.0.0  
**Status:** Research Specification  
**Classification:** Non-diagnostic exploratory research protocol  
**Enclosing Architecture:** `voxneuro.voice.v4`  

---

## 1. Executive Summary & Clinical Context

Speech impairment in Parkinson's disease (hypokinetic dysarthria) is multidimensional, affecting respiratory, phonatory, articulatory, and prosodic subsystems. While sustained vowel phonation (`/a/`) provides sensitive measures of laryngeal stability and vocal fold vibration (jitter, shimmer, harmonics-to-noise ratio), it does not assess:
- Rapid alternating speech motor control (articulatory diadochokinesis);
- Connected speech dynamics (speech pause architecture, prosodic modulation, intensity drift);
- Dynamic acoustic working range of oral articulators (vowel space area).

VoxNeuro Milestone 3 (M3) establishes standardized acquisition and processing protocols for a comprehensive 4-task speech battery, structured under the versioned multi-task envelope `voxneuro.voice.v4`.

---

## 2. Standardized Acoustic Environment & Instrumentation

To ensure reproducible acoustic extraction across clinical and home environments:

1. **Ambient Noise:** Background acoustic noise must not exceed 45 dBA SPL. Quiet room with minimal acoustic reflections (carpeting or curtains preferred; avoid tiled or bare glass rooms).
2. **Microphone Specifications:**
   - Directional polar pattern (cardioid or hypercardioid);
   - Flat frequency response across 50 Hz – 10,000 Hz (±2 dB);
   - Minimum 16-bit linear PCM sampling at 16,000 Hz or higher (up to 48,000 Hz).
3. **Microphone Positioning:**
   - Fixed distance of 5.0 to 8.0 cm from the corner of the mouth;
   - Off-axis angle of 45° to eliminate aerodynamic burst artifacts and plosive breath turbulence ("popping");
   - Use of a pop filter or foam windscreen is mandatory.
4. **Subject Positioning:**
   - Upright seated posture, back supported, feet flat on the floor;
   - Head in neutral, Frankfort horizontal position;
   - Resting pause of 60 seconds between tasks to prevent motor fatigue.

---

## 3. Speech Paradigm Protocols

### Paradigm 1: Sustained Vowel Phonation (`/a/`)
- **Schema Reference:** `voxneuro.voice.v3` (Core39)
- **Descriptive acoustic measurement construct:** Acoustic phonatory stability. The existing `voxneuro.voice.v3` measures acoustic phonatory characteristics such as fundamental frequency ($F_0$), jitter (period perturbation), shimmer (amplitude perturbation), and harmonics-to-noise ratio (HNR). The application measures acoustic audio properties; it does not directly measure laryngeal mucosal wave motion or vocal fold micro-tremor.
- **Verbal Instruction to Participant:**
  > *"Take a comfortable deep breath and hold the sound 'ah' (/a/) as steadily and evenly as possible at your normal, comfortable pitch and loudness until I signal you to stop. Hold for approximately 3 to 5 seconds."*
- **Target Duration:** 3.0 to 5.0 seconds.
- **Valid Limits:** Minimum 1.5 s, maximum 30.0 s.
- **Exclusion Criteria:** Glottal frying, excessive pitch glide (> 30 Hz drift), laughing, audible inhalation within the phonation segment.

---

### Paradigm 2: Diadochokinetic Syllable Repetition (DDK)
- **Schema Reference:** `voxneuro.task.ddk.v1`
- **Descriptive acoustic measurement construct:** Acoustic event timing and regularity. The implementation estimates acoustic burst event timing, including syllable event repetition rate, inter-event interval variability, and temporal rate drift across the recording. The application measures acoustic energy bursts; it does not directly measure motor planning, physical articulatory velocity, neurological fatigue, or phonetic correctness, and acoustic event timing is not equivalent to a validated clinical articulatory examination.
- **Stimulus Subtypes:**
  1. **AMR (Alternating Motion Rate):**
     - `/pa/` (bilabial closure, cranial nerve VII - facial);
     - `/ta/` (alveolar-lingual contact, cranial nerve XII - hypoglossal);
     - `/ka/` (velar-dorsal tongue contact, cranial nerve XII & X).
  2. **SMR (Sequential Motion Rate):**
     - `/pa-ta-ka/` (rapid front-to-back sequential motor sequencing).
- **Verbal Instruction to Participant:**
  > *"Take a deep breath and repeat the syllable '[pa / ta / ka / pa-ta-ka]' as rapidly, clearly, and evenly as possible on a single breath until I tell you to stop. Keep going steadily for about 5 to 7 seconds."*
- **Target Duration:** 4.0 to 8.0 seconds.
- **Valid Limits:** Minimum 2.0 s, maximum 20.0 s.
- **Acoustic Gate:** Minimum 4 distinct syllable events must be detected; otherwise classified as `insufficient_signal`.

---

### Paradigm 3: Connected Speech (Phonetically Balanced Passage)
- **Schema Reference:** `voxneuro.task.connected_speech.v1`
- **Descriptive acoustic measurement construct:** Estimated speech activity duration, pause distribution, and acoustic prosodic variability. The implementation extracts acoustic Voice Activity Detection (VAD) proxies, including estimated active speech bout duration, pause count and duration distribution, dynamic fundamental frequency range (semitones), and vocal intensity variation. The application measures acoustic audio dynamics; it does not directly measure respiratory coordination, lung capacity, breath-group physiology, true articulation rate without phonetic annotations, or clinically validated speech intelligibility.
- **Reading Stimulus (Bamboo Passage - 31 words):**
  > *"Cheaply made bamboo boats can be useful for light travel. They carry few people and float easily upon the smooth surface. Strong reeds and tall stalks bend in the quiet wind."*
- **Monologue Stimulus (Alternative for non-readers):**
  > 30–60 second spontaneous response to standard cognitive prompt: *"Describe what you typically do on a Sunday morning."*
- **Verbal Instruction to Participant:**
  > *"Please read this short paragraph aloud at your normal speaking speed and loudness, as if you were speaking to a companion across a table. Do not rush."*
- **Target Duration:** 10.0 to 30.0 seconds.
- **Valid Limits:** Minimum 5.0 s, maximum 180.0 s. Minimum active speech duration: 1.5 s.

---

### Paradigm 4: Corner Vowels & Vowel Space Area (VSA)
- **Schema Reference:** `voxneuro.task.vowel_space.v1`
- **Descriptive acoustic measurement construct:** Acoustic vowel-space geometry derived from formant estimates. VSA is computed using the Gauss shoelace formula from estimated $F_1$ and $F_2$ vowel formant coordinates of /a/, /i/, and /u/. The application computes acoustic resonance proxies; it does not directly measure physical articulatory movement or oral cavity range of motion. Lower VSA reflects acoustic formant proximity and does not prove Parkinsonian articulatory centralization.
- **Corner Vowel Targets:**
  - `/a/` (low, back/central vowel; open jaw, depressed tongue);
  - `/i/` (high, front vowel; elevated tongue dorsum, retracted lips);
  - `/u/` (high, back vowel; rounded lips, retracted tongue).
- **Trial Multiplicity:** 1 to 3 distinct repetitions per corner vowel. Median formant frequencies ($F_1$, $F_2$) across repetitions are aggregated to form final coordinates.
- **Verbal Instruction to Participant:**
  > *"Produce the vowel sound '[ah / ee / oo]' clearly and steadily at a comfortable speaking pitch and volume for about 2 to 3 seconds."*
- **Target Duration per Trial:** 2.0 to 3.0 seconds.
- **Valid Limits per Trial:** Minimum 1.0 s, maximum 15.0 s.
- **Acoustic Gate:** All three corner vowels (`/a/`, `/i/`, `/u/`) must be provided with valid formant estimates ($F_1, F_2$ within physiological limits) to compute Triangular VSA. If any corner vowel is missing or invalid, VSA is reported as `null` (`vsa_estimable: false`).

---

## 4. Rejection and Quality Control Criteria

| Quality Metric | Criterion | Action on Failure |
| :--- | :--- | :--- |
| **Sample Rate** | 8,000 Hz to 48,000 Hz | Hard rejection: `AudioValidationError` |
| **Channel Count** | 1 (mono) or 2 (stereo) | Rejection if > 2 channels |
| **Stereo Phase** | $r < -0.85$ between channels | Rejection (destructive phase cancellation) |
| **Peak Amplitude** | $\ge 0.999$ full scale | Clipping check triggered |
| **Clipping Fraction** | $> 1.0\%$ of samples | Hard rejection: `AudioValidationError` |
| **RMS Amplitude** | $< 0.002$ full scale | Hard rejection: `insufficient_signal` |
| **Active Duration** | Below task threshold | Hard rejection: `insufficient_signal` |
| **Missing Corner Vowel** | Missing `/a/`, `/i/`, or `/u/` | VSA marked not estimable; session partial |

---

## 5. Non-Diagnostic and Research Disclaimer

This protocol is strictly intended for scientific investigation, reproducibility auditing, and engineering verification. The multi-task metrics extracted by VoxNeuro have not been cleared or approved by the FDA or international regulatory bodies as diagnostic biomarkers for Parkinson's disease or any medical condition.
