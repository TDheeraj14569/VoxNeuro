# Reproducibility record

## Environment used for the latest model run

- Windows 11, CPython 3.12.16, uv 0.13.7.
- Locked dependencies include NumPy 2.5.4, pandas 3.1.1, SciPy 1.18.1, scikit-learn 1.9.1, Librosa 0.11.0, praat-parselmouth 0.4.7, SoundFile 0.14.0, Streamlit 1.66.1, and joblib 1.6.0.
- The project lock is in `uv.lock` and `requirements-lock.txt`. These results were generated in the workspace with the locked environment; bit-for-bit identity across hardware/library versions is not asserted.

## UAMS nested run provenance

- Source fingerprint: `3a9349043062cfebc0f8cdead7511422fd437eeac4d960bd247a278bcf17f0fa`.
- Feature schema: `voxneuro.voice.v3`; schema fingerprint `a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f`.
- Feature configuration fingerprint: `190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9`.
- Preprocessing configuration fingerprint: `8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d`.
- Manifest SHA-256: `f4c5c0325ad6c2ce629dead6f91fa1ab5f9888b45bd4c19d96786f2853206e92`.
- Extracted feature-table SHA-256: `ec406fe8f1630a1ccadae3f547af252cc2fa460cddeb06a516b4f21bd7b4bc4c`.
- Outer/inner splits: 5/3; repeats: seeds 2026, 2027, 2028; 1,000 participant bootstrap iterations for the primary repeat.
- Selection metric: inner-fold balanced accuracy. No outer-fold threshold selection; probability calibration was not fitted.
- Current results and artifact checksums: `data/processed/nested_uams_evaluation_receipt.json`. The human-readable report is `artifacts/reports/model_evaluation/uams_nested.html`.

## Milestone 2: Scientific Bias Audit and Demographic Confounding Provenance

- Pre-registered Statistical Analysis Plan: `docs/methodology/M2_STATISTICAL_ANALYSIS_PLAN.md`.
- Scientific Bias Audit Report: `docs/reports/M2_BIAS_AUDIT_REPORT.md`.
- External Prospective Validation Protocol: `docs/clinical_validation/M2_EXTERNAL_COHORT_PROTOCOL.md`.
- Analysis receipt: `data/processed/m2_analysis_receipt.json` (SHA-256 `4ff66f6f7ddcc3e988f991114269b33831991ddd97088cfe075bd7242386ba51`).
- Demographic summary: `data/processed/m2_demographic_summary.json`.
- Attrition summary: `data/processed/m2_attrition_summary.json`.
- Matching sensitivity: `data/processed/m2_matching_sensitivity.csv`.
- Comparator metrics: `data/processed/m2_comparator_metrics.csv`.
- Paired incremental voice: `data/processed/m2_paired_incremental_voice.csv`.
- Sex subgroups: `data/processed/m2_sex_subgroup_summary.csv`.
- Self-contained HTML dashboards: `artifacts/reports/scientific_audit/m2_bias_audit.html` and `artifacts/reports/scientific_audit/m2_model_comparison.html`.

### Key Milestone 2 Empirical Findings
- **Demographic Disparity:** HC mean age $47.73 \pm 14.33$ vs PD $67.04 \pm 8.98$ years (SMD $= -1.61$, Mann-Whitney $p = 1.75 \times 10^{-8}$).
- **Caliper Matching Non-Feasibility:** 0.2 SD caliper matching ($2.44$ years) retains only 5 pairs (10 participants, $87.2\%$ attrition). Matched model cross-validation is formally **NOT ESTIMABLE** per SAP Rule 5.
- **Model Hierarchy:** Age-only logistic balanced accuracy is **$83.89\%$**, outperforming voice-only linear SVM (**$70.54\%$**) and voice-only logistic (**$73.88\%$**).
- **Incremental Value:** In paired testing on the primary seed, adding voice to age yields $\Delta\text{BA} = -0.0758$ (95% CI [$-0.1842, +0.0284$], supplementary McNemar exact $p = 0.2632$; repeated-CV $\Delta = -0.0681$); adding voice to age and sex yields $\Delta\text{BA} = -0.0745$ (95% CI [$-0.1843, +0.0310$], supplementary McNemar exact $p = 0.2632$; repeated-CV $\Delta = -0.0762$). The retrospective cohort did not establish statistically supported positive incremental predictive benefit from the voice features beyond demographic comparators. The confidence intervals include zero and positive effects; therefore, the true incremental contribution remains uncertain.

## Complete Reproduction Sequence

Run from the repository root with the checked-out UAMS and UCI source data present:

```powershell
uv sync --all-extras --locked
uv run python scripts/inspect_dataset.py --dataset uams
uv run python scripts/build_manifest.py --dataset uams
uv run python scripts/audit_dataset.py --dataset uams
uv run python scripts/extract_features.py --allow-reviewed-exclusions
uv run python scripts/evaluate_model.py --dataset uams
uv run python scripts/evaluate_nested_models.py --dataset uams
uv run python scripts/train_model.py --dataset uams
uv run python scripts/verify_model.py
uv run python scripts/inspect_dataset.py --dataset uci
uv run python scripts/evaluate_model.py --dataset uci
uv run python scripts/analyze_scientific_bias.py
uv run python scripts/evaluate_demographic_sensitivity.py
uv run python scripts/verify_project.py
```

The extraction option accepts only the three reviewed PD clipping exclusions listed in project configuration. Without those exact exclusions, partial extraction is rejected. Training is blocked when the extraction/evaluation receipts do not match current files, settings, schema, and code.

The trained artifact is written to `artifacts/models/uams_logistic_research.joblib` with a SHA-256 sidecar. It is a local research reference, not an approved predictor. If it and current matching evaluation receipts exist, the app may display a separately labeled, unvalidated exploratory candidate after task, quality, schema, declared-device, and training-only OOD checks pass. The approved user-microphone inference gate remains disabled because input-domain compatibility is unverified.

## Packaging Verification

To generate the verified Milestone 2 distribution package:

```powershell
uv run python scripts/build_source_archive.py
uv run python -m scripts.build_ai_review_bundle --milestone m2 --output VoxNeuro_M2_VERIFIED.zip
```
