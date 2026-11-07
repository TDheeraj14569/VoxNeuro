# Reproducibility record

## Environment used for the latest model run

- Windows 11, CPython 3.12.14, uv 0.12.5.
- Locked dependencies include NumPy 2.5.4, pandas 3.1.1, SciPy 1.18.1, scikit-learn 1.9.1, Librosa 0.11.0, praat-parselmouth 0.4.7, SoundFile 0.14.0, Streamlit 1.66.1, and joblib 1.6.0.
- The project lock is in uv.lock and requirements-lock.txt. These results were generated in the workspace with the locked environment; bit-for-bit identity across hardware/library versions is not asserted.

## UAMS nested run provenance

- Source fingerprint: 1cedbb32605d6ffc3868efa499208d3248895b2e11ee757356972e795c17c53d.
- Feature schema: voxneuro.voice.v3; schema fingerprint a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f.
- Feature configuration fingerprint: 190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9.
- Preprocessing configuration fingerprint: 8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d.
- Manifest SHA-256: 697e422f2631ded7be3b6ac737ce2655747340491ab8a49ab5ba40ed0454264e.
- Extracted feature-table SHA-256: 732202ca2de13e54c7049f4b15775b964265f13931b93c0fb574f6cf9cd43fc0.
- Outer/inner splits: 5/3; repeats: seeds 2026, 2027, 2028; 1,000 participant bootstrap iterations for the primary repeat.
- Selection metric: inner-fold balanced accuracy. No outer-fold threshold selection; probability calibration was not fitted.
- Current results and artifact checksums: data/processed/nested_uams_evaluation_receipt.json. The human-readable report is artifacts/reports/model_evaluation/uams_nested.html.
- Nested metrics CSV SHA-256: 31a73576ce85080554da86b1d55fafca132a8fce7246e8bb9e6f583022ed4ae8.
- Participant-level out-of-fold predictions SHA-256: 915f2621b9fa93864b88e9198dd51f7e0ba3568755bab5459679df709ae1463a.
- Fold metrics CSV SHA-256: c8e0726d4a2ff3b3e5c1af5d4b993a5d2c6881845ad6bd490b213f8b1233993d.
- Summary CSV SHA-256: ba6bcda4d9459e2fc046cc093e5a297e50539c5205d8fd797e09326bd56efa67.

## Reproduction commands

Run from the repository root with the checked-out UAMS and UCI source data present:

    uv sync --all-extras --locked
    uv run python scripts/audit_dataset.py
    uv run python scripts/extract_features.py --allow-reviewed-exclusions
    uv run python scripts/evaluate_model.py --dataset uams
    uv run python scripts/evaluate_nested_models.py --dataset uams
    uv run python scripts/evaluate_model.py --dataset uci
    uv run python scripts/train_model.py --dataset uams
    uv run python scripts/verify_model.py

The extraction option accepts only the three reviewed PD clipping exclusions listed in project configuration. Without those exact exclusions, partial extraction is rejected. Training is blocked when the extraction/evaluation receipts do not match current files, settings, schema, and code.

The trained artifact is written to artifacts/models/uams_logistic_research.joblib with a SHA-256 sidecar. It is an offline research reference and is not enabled for user microphone inference. The app abstains because input-domain compatibility is unverified.

## WAV smoke report

A real WAV from the UAMS development cohort was processed as a software smoke test and written to artifacts/reports/individual/uams_training_recording_smoke_test.html. It verifies decoding, validation, Core39 feature extraction, and HTML report generation only. The recording belongs to the development cohort, so this is not independent prediction or validation.

The source-audit ZIP excludes all data, trained models, and generated evaluation outputs; obtain the datasets separately under their stated terms before reproducing these results.
