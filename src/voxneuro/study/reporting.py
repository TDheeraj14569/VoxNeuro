"""Generation of 7 structured Milestone 5 research reports with aggregate privacy protections."""

from __future__ import annotations

import csv
import io
import sqlite3
from typing import Any

from voxneuro.study.consent import list_dataset_access
from voxneuro.study.longitudinal import calculate_longitudinal_feature_changes
from voxneuro.study.qc import (
    apply_small_cell_suppression,
    calculate_cohort_attrition,
    calculate_cohort_qc_metrics,
)
from voxneuro.study.registry import get_study, list_studies
from voxneuro.study.schema import utc_now_iso

RESEARCH_DISCLAIMER = (
    "RESEARCH PROTOTYPE NOTICE: VoxNeuro is an investigational software platform for speech "
    "acoustics research. It does NOT provide clinical diagnostic decisions, "
    "rule-out determinations, or diagnostic disease probabilities. "
    "All metrics are descriptive and exploratory."
)


def generate_study_overview_report(
    conn: sqlite3.Connection, study_id: str | None = None
) -> dict[str, Any]:
    """Report 1: Study Overview Report."""
    studies = [get_study(conn, study_id)] if study_id else list_studies(conn)
    qc_metrics = calculate_cohort_qc_metrics(conn, study_id=study_id, suppress_small_cells=True)

    study_summaries = []
    for s in studies:
        study_summaries.append(
            {
                "study_id": s.study_id,
                "study_name": s.study_name,
                "protocol_id": s.protocol_id,
                "protocol_version": s.protocol_version,
                "study_status": s.study_status,
                "dataset_id": s.dataset_id,
                "dataset_version": s.dataset_version,
                "created_at": s.created_at,
            }
        )

    return {
        "report_type": "STUDY_OVERVIEW_REPORT",
        "generated_utc": utc_now_iso(),
        "studies": study_summaries,
        "aggregate_qc": qc_metrics,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def generate_session_completion_report(
    conn: sqlite3.Connection, study_id: str | None = None
) -> dict[str, Any]:
    """Report 2: Session Completion Report."""
    cursor = conn.cursor()
    query = """
        SELECT visit_index, visit_label, overall_session_status, COUNT(*) as count
        FROM sessions
    """
    params: list[Any] = []
    if study_id:
        query += " WHERE study_id = ?"
        params.append(study_id)
    query += " GROUP BY visit_index, visit_label, overall_session_status ORDER BY visit_index;"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    breakdown: list[dict[str, Any]] = []
    for r in rows:
        breakdown.append(
            {
                "visit_index": r["visit_index"],
                "visit_label": r["visit_label"],
                "status": r["overall_session_status"],
                "session_count": apply_small_cell_suppression(r["count"]),
            }
        )

    return {
        "report_type": "SESSION_COMPLETION_REPORT",
        "generated_utc": utc_now_iso(),
        "study_id": study_id or "ALL_STUDIES",
        "session_breakdown": breakdown,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def generate_task_qc_report(
    conn: sqlite3.Connection, study_id: str | None = None
) -> dict[str, Any]:
    """Report 3: Task-Level QC Report."""
    cursor = conn.cursor()
    query = """
        SELECT t.task_type, t.task_status, t.rejection_reason, COUNT(*) as count
        FROM task_recordings t
        JOIN sessions s ON t.session_id = s.session_id
    """
    params: list[Any] = []
    if study_id:
        query += " WHERE s.study_id = ?"
        params.append(study_id)
    query += " GROUP BY t.task_type, t.task_status, t.rejection_reason ORDER BY t.task_type;"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    tasks: list[dict[str, Any]] = []
    for r in rows:
        tasks.append(
            {
                "task_type": r["task_type"],
                "task_status": r["task_status"],
                "rejection_reason": r["rejection_reason"] or "NONE",
                "count": apply_small_cell_suppression(r["count"]),
            }
        )

    return {
        "report_type": "TASK_QC_REPORT",
        "generated_utc": utc_now_iso(),
        "study_id": study_id or "ALL_STUDIES",
        "tasks": tasks,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def generate_cohort_attrition_report(
    conn: sqlite3.Connection, study_id: str | None = None
) -> dict[str, Any]:
    """Report 4: Cohort Attrition Report."""
    attrition = calculate_cohort_attrition(conn, study_id=study_id, suppress_small_cells=True)
    return {
        "report_type": "COHORT_ATTRITION_REPORT",
        "generated_utc": utc_now_iso(),
        **attrition,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def generate_longitudinal_descriptive_report(
    conn: sqlite3.Connection, study_id: str | None = None, task_type: str = "sustained_vowel"
) -> dict[str, Any]:
    """Report 5: Longitudinal Descriptive Report."""
    long_res = calculate_longitudinal_feature_changes(
        conn, study_id=study_id, task_type=task_type, suppress_small_cells=True
    )
    return {
        "report_type": "LONGITUDINAL_DESCRIPTIVE_REPORT",
        "generated_utc": utc_now_iso(),
        **long_res,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def generate_data_provenance_run_report(
    conn: sqlite3.Connection, study_id: str | None = None
) -> dict[str, Any]:
    """Report 6: Data Provenance and Processing Run Report."""
    cursor = conn.cursor()
    query = """
        SELECT run_id, study_id, processing_timestamp, application_version,
               project_code_fingerprint, processing_status, feature_table_checksum,
               receipt_sha256
        FROM processing_runs
    """
    params: list[Any] = []
    if study_id:
        query += " WHERE study_id = ?"
        params.append(study_id)
    query += " ORDER BY processing_timestamp DESC LIMIT 50;"

    cursor.execute(query, tuple(params))
    runs = [dict(r) for r in cursor.fetchall()]

    return {
        "report_type": "DATA_PROVENANCE_RUN_REPORT",
        "generated_utc": utc_now_iso(),
        "study_id": study_id or "ALL_STUDIES",
        "processing_runs": runs,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def generate_consent_and_dua_report(
    conn: sqlite3.Connection, study_id: str | None = None
) -> dict[str, Any]:
    """Report 7: Consent and Dataset Authorization Status Report."""
    cursor = conn.cursor()
    # Participant consent breakdown
    p_query = """
        SELECT consent_status, COUNT(*) as count
        FROM participants
    """
    params: list[Any] = []
    if study_id:
        p_query += " WHERE study_id = ?"
        params.append(study_id)
    p_query += " GROUP BY consent_status;"
    cursor.execute(p_query, tuple(params))
    consent_counts = {
        r["consent_status"]: apply_small_cell_suppression(r["count"]) for r in cursor.fetchall()
    }

    # DUA access records
    dua_records = [d.to_dict() for d in list_dataset_access(conn)]

    return {
        "report_type": "CONSENT_DATASET_AUTHORIZATION_REPORT",
        "generated_utc": utc_now_iso(),
        "study_id": study_id or "ALL_STUDIES",
        "consent_status_counts": consent_counts,
        "dataset_dua_records": dua_records,
        "disclaimer": RESEARCH_DISCLAIMER,
    }


def export_report_to_csv(report_data: dict[str, Any], root_key: str) -> str:
    """Flatten an aggregate report list to a CSV string."""
    items = report_data.get(root_key, [])
    if not items or not isinstance(items, list):
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(items[0].keys()))
    writer.writeheader()
    for row in items:
        writer.writerow(row)
    return output.getvalue()
