# M4 External Dataset Eligibility Register

**Milestone:** 4 (Independent Recording-Domain Validation, Domain-Shift Analysis, Cryptographic Evidence and Safe Inference)  
**Status:** Complete  
**Generated UTC:** 2026-11-12T03:16:00Z  
**Authoritative Register:** Candidate Cohort Eligibility and Access Auditing

---

## 1. Objective and Eligibility Framework

The VoxNeuro reference model was trained and evaluated on telephone-collected sustained-vowel recordings from the University of Arkansas for Medical Sciences (UAMS) cohort. To assess whether the frozen Core39 feature extraction and classification pipeline generalizes across acoustic recording domains, candidate external datasets must satisfy five prerequisite scientific criteria:

1. **Participant Independence:** No participant overlap with the UAMS training or development cohort.
2. **Clinical Reference Standard:** Clinically verified neurological diagnosis (e.g. UK Parkinson's Disease Society Brain Bank or MDS clinical diagnostic criteria) by a movement disorder specialist; well-characterized control cohort.
3. **Task Compatibility:** Direct phonation of sustained vowel `/a/` for at least 1.0 second. Datasets containing only connected speech, reading, DDK, or other vowels cannot validate the Core39 sustained-vowel feature pipeline.
4. **Acquisition Metadata Documentation:** Documented transducer category, acoustic environment, sampling rate, bit depth, and compression settings.
5. **Legal and Ethical Access:** Permissive research license or executed Data Use Agreement (DUA) authorizing local acoustic feature extraction.

---

## 2. Candidate Dataset Evaluation Register

| Candidate Dataset | Audio Task | Participant Cohort | Acquisition Metadata | Clinical Reference Standard | Cohort Origin | Participant Overlap Status | License & Access Model | Formal Decision |
|---|---|---|---|---|---|---|---|---|
| **UAMS Figshare Corpus** (Little et al.) | Sustained `/a/` | $N=81$ ($40\text{ PD}, 41\text{ HC}$) | Telephone network (landline/cellular), 8 kHz / 16 kHz resampled, PCM | Clinically confirmed idiopathic PD, documented UPDRS | Development reference (UAMS, USA) | `NOT_APPLICABLE` (Training reference) | CC BY 4.0 (Open Access) | `INELIGIBLE` (Training reference) |
| **UCI ML Repository #470** (Sakar et al., 2019) | Sustained `/a/` (3 repetitions) | $N=252$ ($188\text{ PD}, 64\text{ HC}$) | Microphones recorded at Istanbul Cerrahpasa; **raw audio withheld** | Neurologist confirmed, Hoehn & Yahr staging | Turkish cohort (Istanbul, TUR) | `NOT_ASSESSED` (Disjoint geographic origin inferred; unverified) | CC BY 4.0 / Open Access | `INELIGIBLE` (Audio pipeline validation) |
| **NeuroVoz Corpus** (UPM / HGUGM, Madrid) | Sustained vowels (`/a/`, `/e/`, `/i/`, `/o/`, `/u/`), DDK, text | $N=112$ ($54\text{ PD}, 58\text{ HC}$) | Quiet clinical room (not sound-treated, mean SNR 24.3 dB), AKG C420 electret headset mic, SoundBlaster Live, 44.1 kHz, 16-bit PCM | In-person neurologist diagnosis, MDS-UPDRS, H&Y | Spanish cohort (Madrid, ESP) | `NOT_ASSESSED` (Cross-cohort overlap verification pending) | Controlled institutional DUA; ethics committee approval required (Nature Sci Data 2024, PMC11655668) | `ACCESS_PENDING` (Local raw audio withheld) |
| **PC-GITA** (Univ. of Antioquia, Colombia) | Sustained vowels, DDK, monologue, read text | $N=100$ ($50\text{ PD}, 50\text{ HC}$, matched) | Sound-treated booth, Shure SM63L dynamic omnidirectional mic, M-Audio C400, 44.1 kHz, 16-bit PCM | Neurologist confirmed, UPDRS III, H&Y | Colombian cohort (Medellín, COL) | `NOT_ASSESSED` (Cross-cohort overlap verification pending) | Academic research agreement required; direct PI approval (CSL 2014, PMC10017962, PMC12565443) | `ACCESS_PENDING` (Local raw audio withheld) |
| **Italian Parkinson's Voice and Speech (IPVS)** (Univ. of Bari) | Vowel phonations, reading text, syllables `/pa/`, `/ta/` (full `/pa-ta-ka/` DDK unverified) | $N=65$ ($28\text{ PD}, 22\text{ elderly HC}, 15\text{ young HC}$) | Device manufacturer, device model, microphone type, sample rate, bit depth, channels, codec, and room environment **unknown / null** in verified open metadata | Neurologist confirmed idiopathic PD | Italian cohort (Bari, ITA) | `NOT_ASSESSED` (Cross-cohort overlap verification pending) | IEEE DataPort access / DUA required (DOI: 10.21227/m293-hp19); separated from unrelated Samson Meteor / Rome/Turin Shure WH20 studies (PMC8886162) | `CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED` (Local raw audio withheld; eligible: false) |
| **mPower Smartphone Study** (Sage Bionetworks) | Phonation `/a/` via iOS mobile app | $N>1,000$ self-enrolled | Uncontrolled iPhone built-in MEMS microphone, mobile app | **Self-reported survey** (unverified by clinician) | US self-enrolled cohort (USA) | `NOT_ASSESSED` (Overlap verification not performed) | Synapse Qualified Researcher DUA | `INELIGIBLE` (Self-report invalid; mic unapproved) |
| **Synthetic / Corrupted Audio** | Algorithmic test fixtures | Non-human | Synthetic signals | N/A | N/A | Internal | `INELIGIBLE` (Scientific validation prohibited) |

---

## 3. Detailed Decision Rationales

### 3.1 UAMS Reference Cohort
- **Decision:** `INELIGIBLE` for external validation.
- **Rationale:** UAMS is the reference development cohort utilized in M1, M2, and M3. Testing the frozen reference model against participants used during its derivation violates the fundamental requirement of out-of-sample external validity.

### 3.2 UCI Parkinson's Dataset #470
- **Decision:** `INELIGIBLE` for raw audio pipeline validation.
- **Rationale:** The UCI 470 repository distributes a pre-computed matrix of 754 engineered acoustic features. Raw waveform files (`.wav`) are not distributed. Consequently, UCI 470 cannot evaluate raw audio ingestion, Praat/Parselmouth acoustic extraction, or Core39 schema alignment. Using UCI 470 as a proxy for raw audio domain validation would represent scientific misrepresentation.

### 3.3 NeuroVoz & PC-GITA Corpora
- **Decision:** `ACCESS_PENDING`.
- **Rationale:** Both corpora feature high-quality clinical documentation and uncompressed 44.1 kHz, 16-bit PCM recordings of sustained `/a/` under distinct acquisition setups (`neurovoz_studio`: AKG C420 headset in a quiet clinical room, mean SNR 24.3 dB; `pc_gita_condenser`: Shure SM63L dynamic omnidirectional mic in a sound-treated booth). Neither dataset is pre-packaged within the local workspace, and both require credentialed Data Use Agreements (DUAs) with institutional review boards. Bypassing access controls or importing unverified external files without executed institutional agreements is strictly forbidden.

### 3.4 Italian Parkinson's Voice and Speech (IPVS) Corpus (Univ. of Bari)
- **Decision:** `CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED` (`research_evaluation_eligible: false`).
- **Rationale:** The Dimauro & Girardi IPVS corpus (IEEE DataPort `DOI: 10.21227/m293-hp19`, 65 speakers: 28 PD, 22 elderly HC, 15 young HC) is strictly separated from unrelated studies: hardware transducer, device model, microphone type, sample rate, bit depth, channel count, audio codec, and room environment are all `unknown` / `null` in verified open metadata. Samson Meteor microphone specifications from an unrelated study in Studi AISV 2023 and Shure WH20 headset specifications from Rome/Turin studies (`PMC8886162`) do not apply to IPVS. Verified IPVS tasks cover vowel phonations, text reading, and isolated syllables `/pa/` and `/ta/`; full `/pa-ta-ka/` DDK compatibility with Core39 sustained `/a/` is unverified.

### 3.5 mPower Smartphone Study
- **Decision:** `INELIGIBLE`.
- **Rationale:** Diagnostic labels in mPower are self-reported via a mobile application survey without clinical examination. Furthermore, live or uncalibrated smartphone microphone capture is strictly prohibited from inference eligibility under the VoxNeuro safety policy.

---

## 4. Formal Milestone 4 Execution Decision

Because no independent raw-audio dataset is currently licensed and stored within the local private workspace:

1. **Zero Data Fabrication:** No synthetic cohorts, simulated clinical outcomes, or unverified external files will be fabricated or claimed as genuine external clinical evidence.
2. **Framework Implementation:** The entire software domain validation framework (registry, metadata schemas, domain shift analyzers, participant-level bootstrap evaluators, and fail-closed inference gates) will be fully implemented and comprehensively tested.
3. **Authoritative Status Designation:** The scientific evaluation status for Milestone 4 is formally recorded as:
   $$\mathbf{FRAMEWORK\_VERIFIED\_DOMAIN\_VALIDATION\_PENDING}$$
4. **Model Safety:** All candidate external domains remain strictly `inference_eligible: false`. The cryptographic trusted domain allowlist remains strictly empty (`TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()`).
