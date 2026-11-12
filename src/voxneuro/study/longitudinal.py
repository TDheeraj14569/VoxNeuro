"""Descriptive longitudinal acoustic feature tracking and interval statistics."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

import numpy as np

from voxneuro.study.qc import apply_small_cell_suppression


def calculate_longitudinal_feature_changes(
    conn: sqlite3.Connection,
    study_id: str | None = None,
    task_type: str = "sustained_vowel",
    feature_names: list[str] | None = None,
    min_visits: int = 2,
    suppress_small_cells: bool = True,
) -> dict[str, Any]:
    """Compute per-participant and group-level descriptive feature changes across repeated visits.

    STRICT SCIENTIFIC INVARIANT: Results are strictly descriptive longitudinal observations.
    They must never be used or presented as evidence of disease progression, clinical worsening,
    or therapeutic efficacy.
    """
    cursor = conn.cursor()
    task_filter = (
        "(df.task_type = ? OR df.task_type LIKE 'sustained_vowel%')"
        if task_type.startswith("sustained_vowel")
        else "df.task_type = ?"
    )
    query = f"""
        SELECT df.participant_id, s.visit_index, s.recording_timestamp, df.features_json
        FROM derived_features df
        JOIN sessions s ON df.session_id = s.session_id
        JOIN participants p ON s.participant_id = p.participant_id
        WHERE {task_filter}
          AND p.enrollment_status IN ('enrolled', 'active')
          AND p.consent_status = 'consented'
          AND s.overall_session_status = 'COMPLETED'
    """
    params: list[Any] = [task_type]
    if study_id:
        query += " AND s.study_id = ?"
        params.append(study_id)
    query += " ORDER BY df.participant_id, s.visit_index ASC;"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()

    # Organize features by participant -> visit_index
    participant_data: dict[str, dict[int, tuple[str, dict[str, float]]]] = {}
    for r in rows:
        pid = r["participant_id"]
        vidx = r["visit_index"]
        ts = r["recording_timestamp"]
        feats = json.loads(r["features_json"])
        if pid not in participant_data:
            participant_data[pid] = {}
        participant_data[pid][vidx] = (ts, feats)

    # Filter to participants with at least min_visits
    eligible_pids = [pid for pid, visits in participant_data.items() if len(visits) >= min_visits]
    n_eligible = len(eligible_pids)

    # Determine features to analyze
    target_features = feature_names or [
        "f0_mean_hz",
        "jitter_local_percent",
        "shimmer_local_percent",
    ]

    # Compute deltas (Visit_k - Visit_1) for each participant
    feature_deltas: dict[str, list[float]] = {f: [] for f in target_features}
    intervals_days: list[float] = []

    for pid in eligible_pids:
        visits = participant_data[pid]
        v_indices = sorted(visits.keys())
        baseline_v = v_indices[0]
        followup_v = v_indices[1]  # Compare baseline to first follow-up

        t0_str, f0_dict = visits[baseline_v]
        t1_str, f1_dict = visits[followup_v]

        try:
            d0 = datetime.fromisoformat(t0_str.replace("Z", "+00:00"))
            d1 = datetime.fromisoformat(t1_str.replace("Z", "+00:00"))
            intervals_days.append(abs((d1 - d0).total_seconds()) / 86400.0)
        except Exception:
            pass

        for fn in target_features:
            val0 = f0_dict.get(fn)
            val1 = f1_dict.get(fn)
            if val0 is not None and val1 is not None and np.isfinite(val0) and np.isfinite(val1):
                feature_deltas[fn].append(float(val1 - val0))

    # Compute descriptive summaries (mean, std, median, IQR)
    group_summaries: dict[str, Any] = {}
    for fn, deltas in feature_deltas.items():
        if len(deltas) >= 5:
            arr = np.array(deltas)
            group_summaries[fn] = {
                "n_observations": len(deltas),
                "mean_change": round(float(np.mean(arr)), 4),
                "std_change": round(float(np.std(arr, ddof=1)), 4) if len(arr) > 1 else 0.0,
                "median_change": round(float(np.median(arr)), 4),
                "iqr_change": round(float(np.percentile(arr, 75) - np.percentile(arr, 25)), 4),
            }
        else:
            group_summaries[fn] = {
                "n_observations": len(deltas),
                "status": "INSUFFICIENT_OBSERVATIONS_FOR_SUMMARY",
            }

    interval_summary: dict[str, Any] = {}
    if intervals_days:
        i_arr = np.array(intervals_days)
        interval_summary = {
            "mean_days": round(float(np.mean(i_arr)), 2),
            "std_days": round(float(np.std(i_arr, ddof=1)), 2) if len(i_arr) > 1 else 0.0,
            "min_days": round(float(np.min(i_arr)), 2),
            "max_days": round(float(np.max(i_arr)), 2),
            "median_days": round(float(np.median(i_arr)), 2),
        }

    return {
        "study_id": study_id or "ALL_STUDIES",
        "task_type": task_type,
        "participants_evaluated": (
            apply_small_cell_suppression(n_eligible) if suppress_small_cells else n_eligible
        ),
        "total_cohort_participants": (
            apply_small_cell_suppression(len(participant_data))
            if suppress_small_cells
            else len(participant_data)
        ),
        "visit_interval_summary": interval_summary,
        "feature_change_summaries": group_summaries,
        "scientific_disclaimer": (
            "Descriptive acoustic tracking only. Changes in voice measurements over time "
            "do not establish neurodegenerative progression, symptom worsening, "
            "or therapeutic response."
        ),
    }
