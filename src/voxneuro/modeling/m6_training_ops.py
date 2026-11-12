"""End-to-end M6 model fitting, versioned bundle serialization, and SQLite registry integration."""

from __future__ import annotations

import hashlib
import json
import platform
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn

from voxneuro.config import load_config
from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION
from voxneuro.modeling.m6_experiment import (
    build_m6_model_families,
    compute_calibration_profile,
    compute_training_feature_distribution,
    evaluate_participant_cv_suite,
)
from voxneuro.modeling.model_bundle import make_bundle, save_bundle
from voxneuro.modeling.model_registry import (
    RegisteredModel,
    complete_training_run,
    create_training_run,
    record_model_evaluation,
    record_training_dataset,
    register_model_version,
    transition_model_state,
)
from voxneuro.provenance import project_code_fingerprint
from voxneuro.study.auth import UserAccount

AUDIO_CONFIG = load_config("audio_config.yaml")
FEATURE_CONFIG = load_config("feature_config.yaml")


def train_and_register_research_model(
    conn: sqlite3.Connection,
    X: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    output_dir: Path,
    model_family: str = "random_forest",
    model_version: str = "m6.v1.0",
    dataset_name: str = "uams",
    dataset_version: str = "figshare-23849127.v1",
    dataset_sha256: str | None = None,
    random_seed: int = 2026,
    actor: UserAccount | None = None,
) -> tuple[RegisteredModel, dict[str, Any]]:
    """Train an M6 research model via grouped CV, save verified bundle, and register immutably."""
    families = build_m6_model_families(random_seed)
    if model_family not in families:
        raise ValueError(f"Unsupported M6 model family {model_family!r}.")

    feat_cols = [c for c in X.columns if c not in ("participant_id", "sample_id")]
    if list(feat_cols) != list(FEATURE_NAMES):
        raise ValueError("M6 Core39 model registration requires exact FEATURE_NAMES columns.")

    ds_sha = dataset_sha256 or hashlib.sha256(X.to_csv(index=False).encode("utf-8")).hexdigest()
    dataset_rec_id = record_training_dataset(
        conn,
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        dataset_sha256=ds_sha,
        schema_version=SCHEMA_VERSION,
        participant_count=int(len(np.unique(groups))),
        recording_count=int(len(X)),
        authorization_status="OPEN_CC_BY_4_0"
        if dataset_name == "uams"
        else "VERIFIED_TRAINING_COHORT",
    )

    run_id = create_training_run(
        conn,
        run_name=f"{dataset_name}_{model_family}_{model_version}",
        project_code_fingerprint=project_code_fingerprint(),
        dataset_ids=[dataset_rec_id],
        config={"model_family": model_family, "random_seed": random_seed, "n_splits": 5},
        random_seed=random_seed,
        actor=actor,
    )

    summary_rows, oof_details = evaluate_participant_cv_suite(
        X,
        y,
        groups,
        models={model_family: families[model_family]},
        n_splits=5,
        random_seed=random_seed,
        cohort_label=dataset_name,
    )
    metrics = next(r for r in summary_rows if r["model_family"] == model_family)
    oof = oof_details[model_family]
    cal = compute_calibration_profile(oof["y_true"], oof["probabilities"])
    eval_receipt_sha = hashlib.sha256(
        json.dumps(metrics, sort_keys=True).encode("utf-8")
    ).hexdigest()

    estimator = families[model_family]
    estimator.fit(X[feat_cols], y)
    dist_stats = compute_training_feature_distribution(X, FEATURE_NAMES)

    bundle = make_bundle(
        estimator,
        dataset_provenance=f"{dataset_name} ({len(np.unique(groups))} participants)",
        dataset_version=dataset_version,
        dataset_checksum_sha256=ds_sha,
        code_version=project_code_fingerprint(),
        training_evaluation_receipt_sha256=eval_receipt_sha,
        validation_method="5-fold participant-grouped CV",
        software_versions={
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
        },
        preprocessing_config=AUDIO_CONFIG,
        feature_config=FEATURE_CONFIG,
        allow_user_microphone_inference=False,
        validated_input_domains=[],
        domain_validation_report=None,
        training_details={
            "model_family": model_family,
            "model_version": model_version,
            "calibration_status": cal.calibration_status,
            "metrics": metrics,
        },
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = output_dir / f"{dataset_name}_{model_family}_{model_version}.joblib"
    save_bundle(bundle, bundle_path)

    reg_model = register_model_version(
        conn,
        model_version=model_version,
        model_family=model_family,
        feature_schema_version=SCHEMA_VERSION,
        feature_schema_fingerprint=bundle["feature_schema_fingerprint"],
        training_run_id=run_id,
        artifact_path=bundle_path,
        calibration_status=cal.calibration_status,
        metadata={
            "feature_distribution_stats": dist_stats,
            "calibration": {
                "brier_score": cal.brier_score,
                "ece": cal.ece,
                "bins": cal.bins,
            },
            "metrics": metrics,
        },
        initial_state="TRAINED",
    )
    record_model_evaluation(
        conn,
        model_id=reg_model.model_id,
        evaluation_scope="internal_grouped_cv",
        dataset_name=dataset_name,
        n_participants=int(len(np.unique(groups))),
        metrics=metrics,
    )
    reg_model = transition_model_state(
        conn,
        model_id=reg_model.model_id,
        to_state="RESEARCH_EVALUATED",
        reason="Automated grouped CV evaluation and calibration recorded.",
        system_internal=True,
    )
    reg_model = transition_model_state(
        conn,
        model_id=reg_model.model_id,
        to_state="EXTERNAL_VALIDATION_PENDING",
        reason="Awaiting authorized multi-domain external cohort validation.",
        system_internal=True,
    )
    complete_training_run(conn, run_id, receipt_sha256=eval_receipt_sha)
    return reg_model, {
        "metrics": metrics,
        "calibration": oof["calibration"],
        "bundle_path": str(bundle_path),
    }
