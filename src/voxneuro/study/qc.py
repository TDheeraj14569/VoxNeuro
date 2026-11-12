"""Operational quality control metrics, cohort attrition tracking, and small-cell suppression."""

from __future__ import annotations

import sqlite3
from typing import Any

SUPPRESSION_THRESHOLD = 10


def apply_small_cell_suppression(count: int, threshold: int = SUPPRESSION_THRESHOLD) -> str | int:
    """Apply privacy-preserving small-cell suppression to low frequency counts.

    Counts strictly greater than 0 and less than `threshold` are suppressed as '< 10'
    to prevent re-identification and unpowered conclusions. Zero is not suppressed.
    """
    if 0 < count < threshold:
        return f"< {threshold} (Suppressed)"
    return count


def calculate_cohort_qc_metrics(
    conn: sqlite3.Connection,
    study_id: str | None = None,
    site_id: str | None = None,
    suppress_small_cells: bool = True,
) -> dict[str, Any]:
    """Calculate operational participant- and session-level QC metrics."""
    cursor = conn.cursor()

    # Participant counts
    p_query = "SELECT enrollment_status, consent_status, COUNT(*) as count FROM participants"
    params: list[Any] = []
    clauses: list[str] = []
    if study_id:
        clauses.append("study_id = ?")
        params.append(study_id)
    if site_id:
        clauses.append("site_id = ?")
        params.append(site_id)
    if clauses:
        p_query += " WHERE " + " AND ".join(clauses)
    p_query += " GROUP BY enrollment_status, consent_status;"

    cursor.execute(p_query, tuple(params))
    rows = cursor.fetchall()

    total_enrolled = 0
    active_consented = 0
    withdrawn = 0

    for r in rows:
        cnt = r["count"]
        total_enrolled += cnt
        if r["enrollment_status"] == "withdrawn" or r["consent_status"] == "withdrawn":
            withdrawn += cnt
        elif r["consent_status"] == "consented":
            active_consented += cnt

    # Session counts
    s_query = "SELECT overall_session_status, COUNT(*) as count FROM sessions"
    s_params: list[Any] = []
    if study_id:
        s_query += " WHERE study_id = ?"
        s_params.append(study_id)
    s_query += " GROUP BY overall_session_status;"

    cursor.execute(s_query, tuple(s_params))
    s_rows = cursor.fetchall()

    sessions_total = 0
    sessions_completed = 0
    sessions_failed = 0
    sessions_scheduled = 0

    for r in s_rows:
        cnt = r["count"]
        sessions_total += cnt
        st = r["overall_session_status"]
        if st == "COMPLETED":
            sessions_completed += cnt
        elif st == "QUALITY_FAILED":
            sessions_failed += cnt
        elif st == "SCHEDULED":
            sessions_scheduled += cnt

    # Task recordings counts
    t_query = """
        SELECT t.task_type, t.task_status, COUNT(*) as count
        FROM task_recordings t
        JOIN sessions s ON t.session_id = s.session_id
    """
    t_params: list[Any] = []
    if study_id:
        t_query += " WHERE s.study_id = ?"
        t_params.append(study_id)
    t_query += " GROUP BY t.task_type, t.task_status;"

    cursor.execute(t_query, tuple(t_params))
    t_rows = cursor.fetchall()

    tasks_by_type: dict[str, dict[str, int]] = {}
    for r in t_rows:
        ttype = r["task_type"]
        status = r["task_status"]
        cnt = r["count"]
        if ttype not in tasks_by_type:
            tasks_by_type[ttype] = {"accepted": 0, "failed": 0, "total": 0}
        tasks_by_type[ttype]["total"] += cnt
        if status == "FEATURES_EXTRACTED":
            tasks_by_type[ttype]["accepted"] += cnt
        else:
            tasks_by_type[ttype]["failed"] += cnt

    def _maybe_suppress(v: int) -> str | int:
        return apply_small_cell_suppression(v) if suppress_small_cells else v

    return {
        "study_id": study_id or "ALL_STUDIES",
        "site_id": site_id or "ALL_SITES",
        "cohort_metrics": {
            "total_enrolled": _maybe_suppress(total_enrolled),
            "active_consented": _maybe_suppress(active_consented),
            "withdrawn": _maybe_suppress(withdrawn),
        },
        "session_metrics": {
            "sessions_total": _maybe_suppress(sessions_total),
            "sessions_completed": _maybe_suppress(sessions_completed),
            "sessions_failed": _maybe_suppress(sessions_failed),
            "sessions_scheduled": _maybe_suppress(sessions_scheduled),
        },
        "task_breakdown": {
            k: {
                "accepted": _maybe_suppress(v["accepted"]),
                "failed": _maybe_suppress(v["failed"]),
                "total": _maybe_suppress(v["total"]),
            }
            for k, v in tasks_by_type.items()
        },
        "privacy_policy": "Small-cell suppression threshold N=10 enforced.",
    }


def calculate_cohort_attrition(
    conn: sqlite3.Connection,
    study_id: str | None = None,
    suppress_small_cells: bool = True,
) -> dict[str, Any]:
    """Calculate visit-to-visit cohort attrition and completion retention rates."""
    cursor = conn.cursor()
    query = """
        SELECT visit_index, COUNT(DISTINCT participant_id) as participant_count,
               COUNT(*) as total_sessions,
               SUM(CASE WHEN overall_session_status = 'COMPLETED' THEN 1 ELSE 0 END)
                   as completed_sessions
        FROM sessions
    """
    params: list[Any] = []
    if study_id:
        query += " WHERE study_id = ?"
        params.append(study_id)
    query += " GROUP BY visit_index ORDER BY visit_index;"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    visits: list[dict[str, Any]] = []
    baseline_participants = None

    for r in rows:
        v_idx = r["visit_index"]
        p_cnt = r["participant_count"]
        comp = r["completed_sessions"]

        if baseline_participants is None and v_idx == 1:
            baseline_participants = p_cnt

        retention_rate = (
            float(p_cnt / baseline_participants)
            if (baseline_participants and baseline_participants > 0)
            else 1.0
        )
        attrition_rate = 1.0 - retention_rate

        p_display = apply_small_cell_suppression(p_cnt) if suppress_small_cells else p_cnt
        comp_display = apply_small_cell_suppression(comp) if suppress_small_cells else comp

        visits.append(
            {
                "visit_index": v_idx,
                "participants_present": p_display,
                "sessions_completed": comp_display,
                "retention_rate": round(retention_rate, 4),
                "attrition_rate": round(attrition_rate, 4),
            }
        )

    return {
        "study_id": study_id or "ALL_STUDIES",
        "baseline_participants": (
            apply_small_cell_suppression(baseline_participants or 0)
            if suppress_small_cells
            else baseline_participants
        ),
        "visits": visits,
        "disclaimer": (
            "Cohort attrition is an operational monitoring metric and does not represent "
            "clinical prognosis."
        ),
    }
