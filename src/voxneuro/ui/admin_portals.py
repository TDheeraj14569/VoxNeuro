"""Server-side RBAC-gated Researcher, ML Model Admin, and System Admin portals."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from voxneuro.config import PROJECT_ROOT, load_config
from voxneuro.modeling.dataset_readiness import build_dataset_readiness_report
from voxneuro.modeling.domain_registry import load_domain_registry
from voxneuro.modeling.domains import TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
from voxneuro.modeling.m6_experiment import (
    render_model_card_html,
    run_m6_comparative_experiments,
)
from voxneuro.modeling.m6_training_ops import train_and_register_research_model
from voxneuro.modeling.model_registry import list_model_versions, transition_model_state
from voxneuro.study.audit import list_audit_events
from voxneuro.study.auth import (
    AuthorizationError,
    list_users_admin,
    require_role,
    update_user_role_or_status,
)
from voxneuro.study.database import check_schema_integrity

MODEL_CONFIG = load_config("model_config.yaml")


def show_researcher_portal(conn: sqlite3.Connection | None, session_token: str | None) -> None:
    """Researcher dashboard gated server-side to researcher/admin roles."""
    st.title("Researcher Portal")
    if not session_token:
        st.warning("Access Restricted: Sign in on the Account page as a Researcher or Admin.")
        return
    if conn is None:
        st.warning("Access Restricted: Research database is not initialized.")
        return
    try:
        actor = require_role(conn, session_token, {"researcher", "admin"})
    except AuthorizationError as exc:
        st.warning(
            f"Access Restricted: {exc} Sign in on the Account page as a Researcher or Admin."
        )
        return

    st.caption(f"Authenticated researcher session: {actor.display_name} ({actor.role})")
    tab_ready, tab_exp, tab_card = st.tabs(
        ["Dataset Readiness & Blockers", "Models A–D & Family Benchmarks", "Model Card"]
    )
    with tab_ready:
        report = build_dataset_readiness_report(conn)
        st.json(report["summary"])
        st.dataframe(pd.DataFrame(report["cohorts"]), use_container_width=True)

    with tab_exp:
        summary_path = (
            PROJECT_ROOT
            / "artifacts"
            / "reports"
            / "model_evaluation"
            / "m6_experiment_summary.json"
        )
        if st.button("Re-run M6 Comparative Benchmark Suite", key="m6_rerun_exp_btn"):
            with st.spinner("Running participant-grouped CV comparisons…"):
                res = run_m6_comparative_experiments()
                summary_path.parent.mkdir(parents=True, exist_ok=True)
                summary_path.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
                st.success("Experiment benchmark refreshed.")
        if summary_path.is_file():
            exp = json.loads(summary_path.read_text(encoding="utf-8"))
            st.subheader("Confounding & Incremental Value (Models A–D)")
            st.dataframe(
                pd.DataFrame(exp.get("model_a_to_d_comparisons", [])), use_container_width=True
            )
            st.subheader("Multi-Family Voice Benchmarks")
            st.dataframe(
                pd.DataFrame(exp.get("multi_family_benchmarks", [])), use_container_width=True
            )
            for item in exp.get("scientific_conclusions", []):
                st.info(item)
        else:
            st.info(
                "Click 'Re-run M6 Comparative Benchmark Suite' to compute benchmarks on "
                "local cohorts."
            )

    with tab_card:
        card_path = (
            PROJECT_ROOT / "artifacts" / "reports" / "model_evaluation" / "m6_model_card.json"
        )
        if card_path.is_file():
            card = json.loads(card_path.read_text(encoding="utf-8"))
            st.download_button(
                "Download M6 Model Card (HTML)",
                render_model_card_html(card),
                "voxneuro_m6_model_card.html",
                "text/html",
            )
            st.json(card)
        else:
            st.info(
                "Run the experiment suite or `scripts/run_m6_training.py` to generate the "
                "model card."
            )


def show_ml_admin_portal(conn: sqlite3.Connection | None, session_token: str | None) -> None:
    """ML Model Admin portal gated server-side to ml_admin/admin roles."""
    st.title("ML Model Registry & Governance")
    if not session_token:
        st.warning("Access Restricted: Sign in on the Account page as ML Admin or Admin.")
        return
    if conn is None:
        st.warning("Access Restricted: Model registry database is not initialized.")
        return
    try:
        actor = require_role(conn, session_token, {"ml_admin", "admin"})
    except AuthorizationError as exc:
        st.warning(f"Access Restricted: {exc} Sign in on the Account page as ML Admin or Admin.")
        return

    st.caption(f"Authenticated ML governance operator: {actor.display_name} ({actor.role})")
    with st.expander("Train & Register Research Model (UAMS Core39)", expanded=False):
        fam = st.selectbox(
            "Model family",
            [
                "logistic_regression",
                "linear_svm_calibrated",
                "rbf_svm",
                "random_forest",
                "extra_trees",
                "hist_gradient_boosting",
            ],
            key="m6_train_fam",
        )
        ver = st.text_input("Semantic version tag", value="m6.v1.0", key="m6_train_ver")
        if st.button("Train & Register Model Version", key="m6_train_submit"):
            try:
                from voxneuro.modeling.dataset_readiness import load_uams_cohort

                X, y, g, _ = load_uams_cohort()
                reg_model, meta = train_and_register_research_model(
                    conn,
                    X,
                    y,
                    g,
                    output_dir=PROJECT_ROOT / "artifacts" / "models",
                    model_family=fam,
                    model_version=ver,
                    actor=actor,
                )
                st.success(
                    f"Registered model {reg_model.model_id} in state {reg_model.lifecycle_state}."
                )
                st.json(meta["metrics"])
            except Exception as exc:
                st.error(f"Training/registration failed: {exc}")

    models = list_model_versions(conn)
    if not models:
        st.info("No M6 model versions are currently registered in SQLite.")
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "model_id": m.model_id,
                        "version": m.model_version,
                        "family": m.model_family,
                        "state": m.lifecycle_state,
                        "calibration": m.calibration_status,
                        "sha256_prefix": m.artifact_sha256[:12],
                        "updated_at": m.updated_at,
                    }
                    for m in models
                ]
            ),
            use_container_width=True,
        )
        selected_id = st.selectbox("Inspect / manage model", [m.model_id for m in models])
        target_state = st.selectbox(
            "Requested lifecycle transition",
            ["RESEARCH_INFERENCE_APPROVED", "REJECTED", "RETIRED"],
        )
        reason = st.text_input("Transition justification", value="ML governance review")
        if st.button("Apply State Transition", key="m6_transition_btn"):
            try:
                updated = transition_model_state(
                    conn,
                    model_id=selected_id,
                    to_state=target_state,
                    reason=reason,
                    session_token=session_token,
                )
                st.success(f"Model {updated.model_id} transitioned to {updated.lifecycle_state}.")
            except Exception as exc:
                st.error(f"Transition blocked fail-closed: {exc}")

    abs_rows = conn.execute(
        "SELECT abstention_id, reason_code, acquisition_domain_id, capture_origin, created_at "
        "FROM abstention_events ORDER BY created_at DESC LIMIT 50;"
    ).fetchall()
    st.subheader("Recent Fail-Closed Abstention Telemetry")
    st.dataframe(pd.DataFrame([dict(r) for r in abs_rows]), use_container_width=True)


def show_system_admin_portal(
    conn: sqlite3.Connection | None,
    session_token: str | None,
    db_path: Path,
) -> None:
    """System Admin portal for user RBAC, audit logs, and fail-closed system invariants."""
    st.title("System Administration & Security")
    if not session_token:
        st.warning("Access Restricted: Sign in on the Account page as System Admin.")
        return
    if conn is None:
        st.warning("Access Restricted: System database is not initialized.")
        return
    try:
        actor = require_role(conn, session_token, {"admin"})
    except AuthorizationError as exc:
        st.warning(f"Access Restricted: {exc} Sign in on the Account page as System Admin.")
        return

    st.caption(f"Authenticated Administrator: {actor.display_name}")
    tab_users, tab_sec, tab_audit = st.tabs(
        ["User Roles & Accounts", "Safety Invariants & DB", "Audit Trail"]
    )
    with tab_users:
        users = list_users_admin(conn, session_token)
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "user_id": u.user_id,
                        "username": u.username,
                        "role": u.role,
                        "active": u.is_active,
                        "last_login": u.last_login_at,
                    }
                    for u in users
                ]
            ),
            use_container_width=True,
        )
        if users:
            uid = st.selectbox("Select user", [u.user_id for u in users], key="m6_adm_uid")
            new_role = st.selectbox(
                "Assign role", ["participant", "researcher", "ml_admin", "admin"], key="m6_adm_role"
            )
            active_flag = st.checkbox("Account active", value=True, key="m6_adm_act")
            if st.button("Update User RBAC", key="m6_adm_upd"):
                update_user_role_or_status(
                    conn,
                    session_token,
                    target_user_id=uid,
                    new_role=new_role,
                    is_active=active_flag,
                )
                st.success("User permissions updated.")
                st.rerun()

    with tab_sec:
        reg = load_domain_registry()
        st.json(
            {
                "allow_user_microphone_inference": bool(
                    MODEL_CONFIG.get("allow_user_microphone_inference", False)
                ),
                "approved_domains": list(reg.approved_domains),
                "trusted_domain_report_hashes_count": len(TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256),
                "schema_integrity": check_schema_integrity(db_path),
            }
        )

    with tab_audit:
        events = list_audit_events(conn, limit=100)
        st.dataframe(pd.DataFrame(events), use_container_width=True)
