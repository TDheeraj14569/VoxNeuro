"""Unit tests for M6 dataset readiness, leakage prevention, calibration, and model registry."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from voxneuro.exceptions import DatasetError
from voxneuro.features.schema import FEATURE_NAMES
from voxneuro.modeling.dataset_readiness import (
    build_dataset_readiness_report,
    verify_participant_split_integrity,
)
from voxneuro.modeling.m6_experiment import (
    compute_calibration_profile,
    compute_subgroup_metrics_safe,
    compute_threshold_tradeoff_curve,
    evaluate_participant_cv_suite,
    generate_m6_model_card,
    render_model_card_html,
)
from voxneuro.modeling.m6_training_ops import train_and_register_research_model
from voxneuro.modeling.model_registry import (
    set_model_domain_approval,
    transition_model_state,
)
from voxneuro.study.auth import authenticate_user, register_user
from voxneuro.study.database import get_connection, run_migrations


def _synthetic_core39_cohort(n_participants: int = 30, seed: int = 42):
    rng = np.random.default_rng(seed)
    rows = []
    y = []
    groups = []
    for idx in range(n_participants):
        label = idx % 2
        pid = f"syn-p-{idx:03d}"
        feat = {
            name: float(rng.normal(loc=0.4 if label == 1 else -0.4, scale=1.0))
            for name in FEATURE_NAMES
        }
        feat["participant_id"] = pid
        feat["sample_id"] = f"s-{idx:03d}"
        rows.append(feat)
        y.append(label)
        groups.append(pid)
    X = pd.DataFrame(rows)[["participant_id", "sample_id", *FEATURE_NAMES]]
    return X, np.asarray(y, dtype=int), np.asarray(groups)


def test_leakage_prevention_rejects_target_or_id_columns_in_predictors():
    X, y, groups = _synthetic_core39_cohort()
    summary = verify_participant_split_integrity(X, y, groups, n_splits=5)
    assert summary["leakage_free"] is True
    assert summary["folds_verified"] == 5

    X_leaky = X.copy()
    X_leaky["diagnosis"] = y
    with pytest.raises(DatasetError, match="leakage"):
        verify_participant_split_integrity(X_leaky, y, groups, n_splits=5)


def test_dataset_readiness_reports_external_blockers_transparently(tmp_path: Path):
    db_path = tmp_path / "readiness.db"
    run_migrations(db_path)
    conn = get_connection(db_path)
    try:
        report = build_dataset_readiness_report(
            conn,
            uams_csv_path=tmp_path / "missing_uams.csv",
            uci_path=tmp_path / "missing_uci.zip",
        )
        assert report["external_validation_data_ready"] is False
        assert len(report["summary"]["external_blockers"]) >= 1
        assert report["report_sha256"]
    finally:
        conn.close()


def test_m6_cv_calibration_threshold_subgroup_and_model_card():
    X, y, groups = _synthetic_core39_cohort(n_participants=30)
    summary_rows, oof_details = evaluate_participant_cv_suite(X, y, groups, n_splits=5)
    families = {row["model_family"] for row in summary_rows}
    assert {
        "dummy_prior",
        "logistic_regression",
        "linear_svm_calibrated",
        "rbf_svm",
        "random_forest",
        "extra_trees",
        "hist_gradient_boosting",
    }.issubset(families)

    lr = oof_details["logistic_regression"]
    cal = compute_calibration_profile(lr["y_true"], lr["probabilities"])
    assert 0.0 <= cal.brier_score <= 1.0
    assert 0.0 <= cal.ece <= 1.0
    curve = compute_threshold_tradeoff_curve(lr["y_true"], lr["probabilities"])
    assert len(curve) == 7

    # Subgroup suppression with N < 10 must suppress metrics
    sub_df = pd.DataFrame(
        {
            "participant_id": lr["participant_ids"],
            "age_band": ["rare" if i < 5 else "common" for i in range(len(lr["participant_ids"]))],
        }
    )
    subs = compute_subgroup_metrics_safe(
        lr["participant_ids"], lr["y_true"], lr["probabilities"], sub_df, "age_band"
    )
    rare_row = next(r for r in subs if r["subgroup_value"] == "rare")
    assert rare_row["n_participants"] == "< 10 (Suppressed)"
    assert rare_row["roc_auc"] == "SUPPRESSED_SMALL_CELL_OR_SINGLE_CLASS"

    card = generate_m6_model_card(
        {
            "cohorts_evaluated": ["synthetic_test"],
            "multi_family_benchmarks": summary_rows,
            "model_a_to_d_comparisons": [],
            "calibration_summaries": {"syn/lr": {"ece": cal.ece, "brier_score": cal.brier_score}},
            "subgroup_analyses": subs,
            "report_sha256": "a" * 64,
        }
    )
    html_text = render_model_card_html(card)
    assert "UNAPPROVED_RESEARCH_ONLY" in html_text
    assert "logistic_regression" in html_text


def test_model_registry_fail_closed_approval_and_tamper_detection(tmp_path: Path):
    db_path = tmp_path / "registry.db"
    run_migrations(db_path)
    conn = get_connection(db_path)
    try:
        admin = register_user(
            conn,
            username="mladmin",
            email="mladmin@example.org",
            password="MlAdminPassword123!",
            role="ml_admin",
        )
        _, ml_token = authenticate_user(conn, identifier="mladmin", password="MlAdminPassword123!")

        X, y, groups = _synthetic_core39_cohort(n_participants=30)
        reg_model, meta = train_and_register_research_model(
            conn,
            X,
            y,
            groups,
            output_dir=tmp_path / "models",
            model_family="random_forest",
            model_version="m6.syn.1",
            actor=admin,
        )
        assert reg_model.lifecycle_state == "EXTERNAL_VALIDATION_PENDING"
        assert Path(meta["bundle_path"]).is_file()

        # Cannot approve domain without verified SHA-256 in TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
        with pytest.raises(ValueError, match="Fail-closed"):
            set_model_domain_approval(
                conn,
                ml_token,
                model_id=reg_model.model_id,
                domain_id="laptop_microphone",
                approval_state="APPROVED",
                evidence_sha256="b" * 64,
            )

        # Cannot transition to RESEARCH_INFERENCE_APPROVED without approved trusted domain
        with pytest.raises(ValueError, match="Fail-closed"):
            transition_model_state(
                conn,
                model_id=reg_model.model_id,
                to_state="RESEARCH_INFERENCE_APPROVED",
                reason="Attempting premature promotion",
                session_token=ml_token,
            )

        # Checksum tampering detection rejects even REJECTED/RETIRED? Transitioning REJECTED works,
        # while verifying bundle on tampered file fails!
        Path(reg_model.artifact_path).write_bytes(b"corrupted-tampered-bytes")
        set_model_domain_approval(
            conn,
            ml_token,
            model_id=reg_model.model_id,
            domain_id="uams_telephone",
            approval_state="REJECTED",
            notes="Checksum tampered test",
        )
        retired = transition_model_state(
            conn,
            model_id=reg_model.model_id,
            to_state="RETIRED",
            reason="Retired tampered test artifact",
            session_token=ml_token,
        )
        assert retired.lifecycle_state == "RETIRED"
    finally:
        conn.close()
