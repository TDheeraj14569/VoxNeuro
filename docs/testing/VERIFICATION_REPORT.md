# Current verification report

**Checked:** 2026-11-11, Windows 11, CPython 3.12.16, locked project environment. The source-review ZIP excludes the local research datasets, processed participant-level feature tables, trained model artifacts, reports generated from participant recordings, environments, and caches. Dataset/model verification was run separately in the local data-bearing workspace.

## Software and application checks

- uv 0.13.7; uv sync --all-extras --locked checked 71 locked Python packages.
- Full Python suite: **338 passed** (330 non-UI tests plus eight Streamlit AppTests). Coverage is **87.2%** across statements in `src/voxneuro`.
- Ruff lint passed. Ruff format --check passed with all files formatted.
- Project verification passed: 11 required imports and required files.
- Model verification passed: bundle sidecar, current data/evaluation/code/config receipts, feature schema, deterministic reload prediction, and research-only/domain-incompatible metadata.
- Frontend: npm ci completed with zero reported vulnerabilities; all three JavaScript unit tests passed; the bundled 3D visualizer rebuilt successfully at 575.9 kB.
- Streamlit AppTests cover all seven sections, valid WAV analysis and HTML report controls, malformed WAV handling, empty research/report states, and the 3D signal views. No classification was emitted.
- All 13 steps of the mandatory receipt refresh sequence completed with exit code 0.

## Milestone 2: Scientific Bias & Demographic Confounding Audit

Milestone 2 completed an in-depth empirical investigation into demographic confounding, recording quality attrition, matching feasibility, and incremental voice diagnostic value:

1. **Demographic Disparity:**
   - Source cohort (Pop 1, N=81): Healthy Controls mean age $47.73 \pm 14.33$ years vs Parkinson's Disease $67.04 \pm 8.98$ years. Standardized Mean Difference (SMD) $= -1.61$, Mann-Whitney $U = 223.0$, $p = 1.75 \times 10^{-8}$.
   - Accepted Core39 cohort (Pop 2, N=78): HC mean $47.73 \pm 14.33$ vs PD $66.92 \pm 9.27$ years (SMD $= -1.56$, $p = 3.64 \times 10^{-8}$).
   - Biological Sex: Pop 1 HC 25F/16M ($61.0\%$ F) vs PD 19F/21M ($47.5\%$ F); Fisher's exact $p = 0.268$, OR $= 1.73$, Cramér's $V = 0.111$. Pop 2: Fisher's exact $p = 0.364$.
2. **Quality Attrition Asymmetry:**
   - Quality exclusions occurred exclusively in the Parkinson cohort: $3/40$ PD excluded ($7.5\%$) vs $0/41$ HC ($0.0\%$), Fisher exact $p = 0.1158$. All 3 exclusions resulted from acoustic clipping ($>0.5\%$ samples at peak rail).
3. **Caliper Matching Sensitivity & Sample Size Exhaustion:**
   - Applying standard epidemiological calipers with exact sex matching:
     - 0.1 SD ($1.22$ yrs): 3 pairs (6 participants, $92.3\%$ discarded).
     - 0.2 SD ($2.44$ yrs): **5 pairs (10 participants, $87.2\%$ discarded)**.
     - 0.3 SD ($3.67$ yrs): 7 pairs (14 participants, $82.1\%$ discarded).
     - Uncalipered: 34 pairs ($12.8\%$ discarded), but residual age gap is $14.90$ years (SMD $= -1.327$).
   - Per pre-registered SAP Rule 5, cross-validation modeling on the matched subset is formally **NOT ESTIMABLE** (only 5 pairs retained, violating 5-outer $\times$ 3-inner fold partition requirements).
4. **Model Comparison Hierarchy & Incremental Value:**
   - All 8 models evaluated across identical $5 \times 3$ nested folds (seeds 2026, 2027, 2028; N=78 participants):
     - `age_only_logistic`: Balanced Accuracy **$83.89\%$** [$74.68\%, 91.07\%$], ROC-AUC **$0.8490$**.
     - `age_plus_sex_logistic`: Balanced Accuracy **$83.81\%$** [$74.56\%, 91.20\%$], ROC-AUC **$0.8493$**.
     - `voice_only_logistic`: Balanced Accuracy **$73.88\%$** [$62.79\%, 82.27\%$], ROC-AUC **$0.7697$**.
     - `voice_only_svm`: Balanced Accuracy **$70.54\%$** [$59.13\%, 79.43\%$], ROC-AUC **$0.7559$**.
     - `age_plus_voice_logistic`: Balanced Accuracy **$77.08\%$** [$65.89\%, 84.71\%$], ROC-AUC **$0.8141$**.
     - `age_plus_sex_plus_voice_logistic`: Balanced Accuracy **$76.18\%$** [$65.89\%, 84.84\%$], ROC-AUC **$0.8132$**.
     - `matched_voice_svm`: **NOT ESTIMABLE** (Sample size exhaustion).
   - Paired incremental voice test:
     - Primary seed (2026):
       - Age + Voice vs Age Only: $\Delta \text{BA} = -0.0758$ ($-7.58\%$), 95% bootstrap CI [$-0.1842, +0.0284$], supplementary McNemar exact $p = 0.2632$ (discordance $b=7, c=13$).
       - Age + Sex + Voice vs Age + Sex: $\Delta \text{BA} = -0.0745$ ($-7.45\%$), 95% bootstrap CI [$-0.1843, +0.0310$], supplementary McNemar exact $p = 0.2632$ (discordance $b=7, c=13$).
     - Secondary repeated cross-validation ($5 \times 3$ nested CV):
       - Age + Voice vs Age Only: $\Delta \text{BA} = -0.0681$ ($-6.81\%$).
       - Age + Sex + Voice vs Age + Sex: $\Delta \text{BA} = -0.0762$ ($-7.62\%$).
   - **Conclusion:** The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain.
5. **Phase 8 External Validation Protocol:**
   - Established prospective multi-center protocol (`docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md`) specifying $N=240$ participants ($120$ PD, $120$ HC) frequency-matched by 5-year age band and sex, sound-booth acoustics ($<35\text{ dBA}$), and calibrated studio condenser transducers.

## Safety and domain boundary

- The UAMS training audio is telephone-collected. Compatibility with laptop, browser, smartphone, other languages, other tasks, or other recording conditions is unverified.
- Live-microphone and unknown device domains remain blocked (`allow_user_microphone_inference: false`).
- No clinical threshold, calibrated disease probability, independent external test, prospective cohort, Indian-population performance, clinician study, ethics approval, or regulatory authorization has been established.
