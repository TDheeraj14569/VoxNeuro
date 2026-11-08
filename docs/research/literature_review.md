# Literature review: Parkinson's voice and speech

**Scope and status:** secondary research snapshot assembled 2026-11-06. It supports a research rationale, not an intended clinical claim. Dataset-specific performance below is published performance, not a VoxNeuro result.

## Findings

- PD-associated hypokinetic dysarthria can include reduced loudness/stress, monopitch, breathiness or hoarseness, imprecise articulation, altered rate, and short utterances. These patterns are neither unique to PD nor all measurable from a sustained vowel. [Atalar et al., 2023](https://doi.org/10.1007/s00415-023-11750-8)
- A systematic review of 147 suitable studies found substantial heterogeneity in datasets, tasks, features, and analytic methods; it describes promise while identifying barriers to comparable and clinically interpretable systems. [Ngo et al., 2022](https://doi.org/10.1016/j.cmpb.2022.107133)
- Jitter measures local period variability; shimmer measures pulse-amplitude variability; HNR represents periodic-to-noise energy. They depend on task, signal quality, settings, and algorithm, and cannot be interpreted as disease-specific tests. Praat documents measurement definitions and settings. [Praat jitter manual](https://praat.org/manual/PointProcess__Get_jitter__local____.html), [Praat harmonicity manual](https://praat.org/manual/Harmonicity.html)
- Sustained-vowel data are useful for phonation research but omit articulation, rhythm, intelligibility, language, and connected speech. MFCCs summarize short-time spectral envelope and are not direct anatomical biomarkers.
- A large longitudinal telemonitoring study related speech measures to UPDRS progression using roughly 6,000 recordings from 42 participants over six months. This addresses repeat monitoring in established PD, not screening accuracy in a primary-care population. [Tsanas et al., 2010](https://doi.org/10.1109/TBME.2009.2036000)
- The peer-reviewed UAMS voice sample study used 81 telephone-collected `/a/` recordings (40 PD, 41 controls). It reported high AUCs for a pretrained CNN on spectrograms, while conventional feature baselines were lower and varied; its small single-cohort results are not external validation and are not VoxNeuro results. Any use of these data must keep the participant as the split unit. [Rahmatallah et al., Scientific Reports (published 1 March 2025), DOI 10.1038/s41598-025-92105-6](https://doi.org/10.1038/s41598-025-92105-6)
- Cross-population feasibility in India: A 2025 pilot study conducted in Mizoram evaluated acoustic phonation measures in 15 native speakers (5 PD, 10 HC) using smartphone-collected vowels. While demonstrating preliminary feasibility of non-invasive acoustic capture in non-Western populations, its small sample size serves solely as supplementary research context and is not part of VoxNeuro model training or benchmark validation.
- Device and environment differences are material. A recent review of remote speech technologies discusses variable microphone frequency response and mixed reliability by feature; its findings do not justify treating a laptop microphone as equivalent to a telephone or a calibrated clinical microphone. [Gomez et al., 2026, Remote Speech and Swallowing Assessment Technologies, PubMed Central PMC13652970](https://pmc.ncbi.nlm.nih.gov/articles/PMC13652970/)
- A review of commercially available PD voice-analysis technologies identified 12 products and concluded that real-world suitability remains uncertain. PubMed lists the article date as 11 July 2025; its issue/collection record is January 2026. This review does not establish clinical validity for VoxNeuro. [PubMed record](https://pubmed.ncbi.nlm.nih.gov/40643097/), [DOI 10.1002/mdc3.70214](https://doi.org/10.1002/mdc3.70214)

## Evidence table

See [`clinical_evidence_table.csv`](clinical_evidence_table.csv) for design, cohort, task, features, evaluation, performance context, and limitations. Different studies and datasets are not directly pooled here.

