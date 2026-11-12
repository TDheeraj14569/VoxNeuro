# Known limitations and blockers

## Clinical and scientific

- **Non-Diagnostic Nature:** VoxNeuro is an academic research prototype. It is not a disease detector, diagnostic device, screening instrument, or clinical decision-support product. It returns audio quality and technical acoustic measurements only.
- **Unvalidated Need Statement:** The clinical need remains a research hypothesis. No stakeholder interview, observation, clinician endorsement, or patient feedback is claimed.
- **Severe Demographic Confounding (M2 Finding):** The UAMS cohort exhibits an extreme age disparity between Healthy Controls ($47.73 \pm 14.33$ years) and Parkinson's Disease participants ($67.04 \pm 8.98$ years; SMD $= -1.61$, $p = 1.75 \times 10^{-8}$). An age-only logistic classifier achieves **83.89%** balanced accuracy, exceeding all tested voice-only models (best linear SVM: 70.54%, logistic: 73.88%).
- **Absence of Supported Incremental Voice Diagnostic Benefit (M2 Finding):** In paired out-of-fold testing on the primary seed, adding 39 acoustic features to demographic age yields $\Delta\text{BA} = -0.0758$ (95% CI [$-0.1842, +0.0284$], supplementary McNemar exact $p = 0.2632$; repeated-CV $\Delta = -0.0681$). Adding voice to age and sex combined yields $\Delta\text{BA} = -0.0745$ (95% CI [$-0.1843, +0.0310$], supplementary McNemar exact $p = 0.2632$; repeated-CV $\Delta = -0.0762$). The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain.
- **Sample Size Exhaustion on Caliper Matching (M2 Finding):** Constructing a defensible age- and sex-matched subcohort with standard epidemiological calipers ($0.2$ pooled SD $= 2.44$ years) retains only **5 pairs (10 participants)** &mdash; an $87.2\%$ participant attrition rate. Consequently, cross-validation modeling on a matched cohort is formally **NOT ESTIMABLE** due to minimal class partition constraints.
- **Class-Dependent Recording Attrition:** Quality exclusions (excessive acoustic clipping $>0.5\%$ samples) occurred exclusively in the Parkinson's cohort ($3/40$ PD excluded [$7.5\%$] vs $0/41$ HC [$0.0\%$]; Fisher exact $p = 0.1158$). All three reviewed clipping exclusions occurred in the PD group. The available data do not establish the cause of this class-dependent acquisition failure.
- **Unverified Device Compatibility:** UAMS is telephone-collected; laptop/smartphone acquisition equivalence has not been established. Matching feature names or resampling rates do not prove domain compatibility.
- **Benchmark Separation:** UCI #470 is a separate pre-extracted feature-table benchmark. It is not external validation of the raw-audio extractor.
- **Absence of Trained Multi-Task Models (M3 Boundary):** Milestone 3 introduces diadochokinetic syllable repetition (`voxneuro.task.ddk.v1`), connected speech segmentation (`voxneuro.task.connected_speech.v1`), and vowel space area (`voxneuro.task.vowel_space.v1`) under envelope `voxneuro.voice.v4`. **No machine learning model is trained on these new tasks.** Existing research models were trained exclusively on sustained vowels (`voxneuro.voice.v3`). Passing M3 features to existing models is mathematically invalid and blocked by schema validation.
- **Multi-Task Signal Processing Limitations (M3 Boundary):**
  - DDK onset detection degrades under severe hypophonia (insufficient dynamic range) and plosive air blast.
  - Connected speech energy-based VAD is sensitive to room reverberation and cannot separate cognitive reading hesitations from motor speech pauses.
  - Burg LPC formant tracking for VSA degrades at high fundamental frequencies ($F_0 > 250$ Hz), under hypernasality, and reflects anatomical vocal tract length differences.
  - Complete algorithm limitations are detailed in [`docs/M3_ALGORITHM_LIMITATIONS.md`](M3_ALGORITHM_LIMITATIONS.md).
- **Prospective Protocol Mandate:** There is no currently available independent external validation cohort for multi-task voice. Milestone 3 establishes a formal prospective protocol ([`docs/clinical_validation/M3_MULTITASK_ACQUISITION_PROTOCOL.md`](clinical_validation/M3_MULTITASK_ACQUISITION_PROTOCOL.md)) to evaluate multi-task diagnostic superiority under standardized clinical trial conditions.
- **Independent External Raw-Audio Domain Validation Status (M4 Boundary):** Milestone 4 establishes the formal recording domain validation architecture, candidate dossier schema (`voxneuro.domain_assessment.v1`), domain shift analyzer, and frozen-model participant bootstrap evaluator. Candidate external cohorts (NeuroVoz, PC-GITA, Italian Parkinson's) require credentialed institutional Data Use Agreements (DUAs) and are not pre-packaged in the local workspace. Authoritative milestone status is formally `FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING`. No candidate domain has been approved for inference compatibility.
- **Fail-Closed Inference Protection (M4 Boundary):** The trusted report allowlist (`TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256`) remains strictly empty (`frozenset()`). User microphone inference remains disabled (`allow_user_microphone_inference: false`). Live microphones, browser audio streams, and user uploads unconditionally fail closed under the `InputCaptureContext` contract. Candidate dossiers cannot be loaded as approved prediction compatibility reports.

## Software and environment

- Python 3.12 is required by `pyproject.toml`; dependencies are locked. The source ZIP omits datasets and model/evaluation artifacts, so data-specific scripts require separately obtained licensed local data.
- The browser microphone control was rendered and tested in Streamlit AppTest, but real browser/OS permission and physical microphone capture have not been verified. Microphone prediction is locked by safety configuration (`allow_user_microphone_inference: false`).
- UCI archive extraction relies on Windows `tar` support for RAR. An installation without that support must use a suitable extraction environment.
- The model checksum detects byte changes but does not authenticate the signer or make arbitrary joblib files safe.
- `.git` and trained artifacts are local only; there is no remote, release tag, or signed release in this package.

## Data and evidence

- The ZIP alone cannot reproduce reported cohort metrics because local datasets and generated outputs are omitted.
- The source cohort's capture hardware/channel details, task adherence, and clinical context are incompletely characterized.
- A technical signal-quality pass does not imply normal health, and extraction failure does not imply disease.
