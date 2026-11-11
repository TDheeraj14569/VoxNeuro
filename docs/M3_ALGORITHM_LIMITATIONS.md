# VoxNeuro Milestone 3: Algorithm Limitations & Edge-Case Behavior

**Version:** 3.0.0  
**Enclosing Architecture:** `voxneuro.voice.v4`  
**Classification:** Technical Risk & Algorithm Constraints Report  

---

## 1. Executive Summary

Milestone 3 broadens VoxNeuro's signal-processing architecture from single-vowel phonation (`voxneuro.voice.v3`) to a multidimensional 4-task speech battery (`voxneuro.voice.v4`).

Every signal-processing algorithm operates under mathematical and physical assumptions. This document details the specific technical failure modes, acoustic edge cases, and limitations of the newly implemented M3 algorithms.

---

## 2. Diadochokinetic Syllable Repetition (DDK) Limitations

### 2.1 Acoustic Envelope Onset Detection
The DDK event detector identifies syllable burst events via smoothed short-time RMS energy peaks with dynamic prominence thresholding ($15\%$ of dynamic range).

**Known Failure Modes:**
1. **Severe Hypophonia (Reduced Vocal Loudness):** In advanced Parkinson's disease, patients often produce extremely faint syllables (hypophonia). When syllable peak energy fails to exceed ambient room noise by $> 6$ dB, syllable pulses cannot be reliably distinguished from noise, leading to under-counting.
2. **Plosive Air Blasts on Microphone:** Plosive consonants (`/p/`, `/t/`, `/k/`) generate low-frequency aerodynamic pops. If the microphone is placed directly in front of the mouth rather than at a 45° angle, aerodynamic turbulence creates artificial energy spikes that mimic syllables.
3. **Audible Inhalation Bursts:** Rapid gasps for air between syllable trains create broad energy humps that may be erroneously registered as syllable events if the prominence threshold is overly permissive.
4. **Articulatory Undershoot (Mumbling):** SMR sequences (`/pa-ta-ka/`) in Parkinsonian speech frequently degenerate into continuous fricative or vowel humming without complete acoustic closure. In such cases, envelope modulation diminishes to zero, causing the detector to report `insufficient_signal` or an abnormally low syllable count.

---

## 3. Connected Speech Segmentation & Prosodic Limitations

### 3.1 Energy-Based Voice Activity Detection (VAD)
Speech bouts and pause intervals are segmented using a dual-threshold energy detector with 150 ms minimum pause duration gating.

**Known Failure Modes:**
1. **Room Reverberation & Echo:** In acoustically reflective rooms (e.g. uncarpeted clinics or tiled bathrooms), acoustic reverberation decays slowly, filling genuine phonetic pauses with decaying acoustic energy. This artificially inflates estimated phonation duration and reduces measured pause count and pause ratio.
2. **Breathiness & Vocal Tremor:** Severe vocal breathiness (turbulent transglottal airflow) raises the noise floor during phonation. If the adaptive silence threshold drifts, trailing breath sounds may be categorized as active speech.
3. **Reading Hesitations vs. Motor Pauses:** The algorithm cannot distinguish between cognitive reading hesitations, dyslexia, unfamiliarity with text, and neurogenic motor speech pauses. Clinical studies must control for literacy and cognitive status.

### 3.2 Prosodic Fundamental Frequency ($F_0$) Tracking
$F_0$ distribution across connected speech is tracked using Praat's autocorrelation algorithm with physiological bounds ($75 – 500$ Hz).

**Known Failure Modes:**
- Voiceless fricatives (`/s/`, `/f/`) and unvoiced stops do not have pitch. While the algorithm masks unvoiced frames, transient voicing onsets can introduce pitch-halving or pitch-doubling octave jumps.
- Pitch range is quantified in semitones ($12 \log_2(F_{0,90} / F_{0,10})$) to normalize for biological differences between male and female baseline pitch. However, non-modal phonation (creaky voice / vocal fry) at utterance ends artificially expands the lower percentile ($F_{0,10}$), distorting semitone span.

---

## 4. Vowel Space Area (VSA) & Burg LPC Formant Limitations

### 4.1 Linear Predictive Coding (LPC) Formants
Formants are estimated using Burg's algorithm on stationary windowed segments of corner vowels (`/a/`, `/i/`, `/u/`).

**Known Failure Modes:**
1. **High Fundamental Frequency ($F_0 > 250$ Hz):** In high-pitched female or child voices, acoustic harmonics are spaced widely apart ($\Delta f = F_0$). When harmonic spacing exceeds the bandwidth of vocal tract resonances, LPC algorithms struggle to identify true formant center frequencies, often locking onto harmonic peaks instead.
2. **Nasalization:** Hypokinetic dysarthria frequently features velopharyngeal incompetence (hypernasality), introducing nasal antiformants (spectral zeros) and pole-zero pairs. Because Burg LPC is an all-pole model, nasal zeros violate model assumptions and can shift estimated $F_1$ and $F_2$ values by $50 – 150$ Hz.
3. **Vocal Tract Length Differences:** VSA is an absolute area in $\text{Hz}^2$. Anatomical differences in vocal tract length (e.g., taller individuals having longer vocal tracts and lower formant frequencies) cause baseline differences in VSA that are entirely unrelated to neurological disease. Raw VSA must be interpreted with anatomical reference or normalized via Formant Centralization Ratio (FCR).

---

## 5. Linguistic, Cultural & Stimulus Sensitivity

1. **English Stimulus Dependency:** The reading passage ("Bamboo Passage") is standardized in American English. Non-native English speakers or speakers of other languages will exhibit different articulation rates, pause locations, and vowel space configurations.
2. **Vowel Quality Variation:** The acoustic definitions of `/a/`, `/i/`, `/u/` depend on regional phonetic dialects (e.g., the cot-caught merger or Northern Cities Shift in American English). Cross-site clinical comparisons must establish dialect-specific reference norms.

---

## 6. Complete Absence of Trained Machine Learning Models for M3 Tasks

**CRITICAL SCIENTIFIC SAFETY NOTE:**
- VoxNeuro currently possesses trained research models **ONLY** for sustained vowel `/a/` (`voxneuro.voice.v3` Core39 features trained on UAMS).
- **NO model in VoxNeuro is trained on DDK, connected speech, or vowel space area.**
- The M3 implementation provides signal processing and reproducible feature extraction engines only.
- Passing M3 task features into the existing M1/M2 classifiers is strictly prohibited by schema validation rules, as doing so would constitute an invalid feature mismatch and produce meaningless, unvalidated outputs.
