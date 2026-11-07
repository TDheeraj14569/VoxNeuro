# Reproducibility record

## Environment used for the latest model run

- Windows 11, CPython 3.12.14, uv 0.12.5.
- Locked dependencies include NumPy 2.5.4, pandas 3.1.1, SciPy 1.18.1, scikit-learn 1.9.1, Librosa 0.11.0, praat-parselmouth 0.4.7, SoundFile 0.14.0, Streamlit 1.66.1, and joblib 1.6.0.
- The project lock is in uv.lock and requirements-lock.txt. These results were generated in the workspace with the locked environment; bit-for-bit identity across hardware/library versions is not asserted.

## UAMS nested run provenance

- Source fingerprint: 65942228163857cf526d5881703a668717981347f6a6a90932ff489f339687c5.
- Feature schema: voxneuro.voice.v3; schema fingerprint bd4a145f09ada55b519fae1f06bf4383a1921ff9a2421c7562ddead672eb48f2.
- Feature configuration fingerprint: 190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9.
- Preprocessing configuration fingerprint: 1db0448d55ee8d02cbbe28691a9e1471cfd678e23ef302c09d632ed42147ed6a.
- Manifest SHA-256: 697e422f2631ded7be3b6ac737ce2655747340491ab8a49ab5ba40ed0454264e.
- Extracted feature-table SHA-256: 9037167ccb69c98e3926573a0de3ec1e922595557c77aaa16617bfd4a1f0b2a6.
- Outer/inner splits: 5/3; repeats: seeds 2026, 2027, 2028; 1,000 participant bootstrap iterations for the primary repeat.
- Selection metric: inner-fold balanced accuracy. No outer-fold threshold selection; probability calibration was not fitted.
- Current results and artifact checksums: data/processed/nested_uams_evaluation_receipt.json. The human-readable report is artifacts/reports/model_evaluation/uams_nested.html.
- Nested metrics CSV SHA-256: 7e75d9ad7ecf08a3e5dff080725d2de40c1f4c2cae73c893dfd4160742f7c0f4.
- Participant-level out-of-fold predictions SHA-256: 2bedcc5b7d13dab9cc4316827b2ed0311db63a54d7772bfc7e06b9bef611aac1.
- Summary CSV SHA-256: e02b75ff85f51002fa87abd980be0a91dd00b68f3411ebf37289a7c3651516ec.

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
