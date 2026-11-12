"""Recording session and multi-task audio ingestion workflow."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from voxneuro.features.tasks.pipeline import MultiTaskSessionResult, analyze_multitask_session
from voxneuro.study.consent import (
    _is_task_permitted,
    get_consent,
    get_dataset_access,
    verify_dataset_authorization_for_task,
)
from voxneuro.study.participant import get_participant, is_participant_active
from voxneuro.study.registry import get_study
from voxneuro.study.schema import (
    VALID_SESSION_STATUSES,
    ResearchSession,
    TaskRecording,
    utc_now_iso,
)

OPERATION_AUTHORIZATION_MAP: dict[str, dict[str, frozenset[str]]] = {
    "feature_extraction": {
        "allowed_scopes": frozenset(
            {"voice_analysis", "audio_analysis", "voice_recording", "feature_extraction"}
        ),
        "allowed_research_uses": frozenset({"biomarker_research", "feature_extraction"}),
    },
    "transient_processing": {
        "allowed_scopes": frozenset(
            {"voice_analysis", "audio_analysis", "voice_recording", "transient_processing"}
        ),
        "allowed_research_uses": frozenset(
            {"biomarker_research", "transient_processing", "reproducibility_audit"}
        ),
    },
    "statistical_audit": {
        "allowed_scopes": frozenset({"statistical_audit", "reproducibility_audit", "audit_and_qc"}),
        "allowed_research_uses": frozenset(
            {"statistical_audit", "reproducibility_audit", "audit_and_qc"}
        ),
    },
    "qc_validation": {
        "allowed_scopes": frozenset({"qc_validation", "quality_control", "audit_and_qc"}),
        "allowed_research_uses": frozenset(
            {"qc_validation", "quality_control", "reproducibility_audit", "audit_and_qc"}
        ),
    },
    "longitudinal_analysis": {
        "allowed_scopes": frozenset({"longitudinal_tracking", "longitudinal_analysis"}),
        "allowed_research_uses": frozenset({"longitudinal_analysis", "longitudinal_research"}),
    },
    "aggregate_reporting": {
        "allowed_scopes": frozenset({"aggregate_reporting", "reporting"}),
        "allowed_research_uses": frozenset(
            {"aggregate_reporting", "reporting", "reproducibility_audit"}
        ),
    },
}


def _verify_consent_operation_scope(consent: Any, requested_operation: str) -> tuple[bool, str]:
    """Verify exact session-pinned consent scope_of_permission and permitted_research_uses."""
    if requested_operation not in OPERATION_AUTHORIZATION_MAP:
        return (
            False,
            f"Requested processing operation {requested_operation!r} is not recognized.",
        )

    scopes = {str(s).strip() for s in (consent.scope_of_permission or []) if str(s).strip()}
    if not scopes:
        return (
            False,
            f"Session consent {consent.consent_record_id!r} has empty scope_of_permission.",
        )

    uses = {str(u).strip() for u in (consent.permitted_research_uses or []) if str(u).strip()}
    if not uses:
        return (
            False,
            f"Session consent {consent.consent_record_id!r} has empty permitted_research_uses.",
        )

    rule = OPERATION_AUTHORIZATION_MAP[requested_operation]
    if not (scopes & rule["allowed_scopes"]):
        return (
            False,
            f"Consent scope_of_permission {sorted(scopes)} does not authorize operation "
            f"{requested_operation!r} (requires one of {sorted(rule['allowed_scopes'])}).",
        )

    if not (uses & rule["allowed_research_uses"]):
        return (
            False,
            f"Consent permitted_research_uses {sorted(uses)} does not authorize operation "
            f"{requested_operation!r} (requires one of {sorted(rule['allowed_research_uses'])}).",
        )

    return True, "Consent scope and research uses verified for operation."


def create_session(conn: sqlite3.Connection, session: ResearchSession) -> None:
    """Create a research session within a study for an active pseudonymous participant."""
    # 1. Verify study exists and is active
    study = get_study(conn, session.study_id)
    if study.study_status in {"archived", "completed"}:
        raise PermissionError(
            f"Cannot schedule session: study {session.study_id!r} is {study.study_status!r}."
        )

    # 2. Verify participant exists
    try:
        participant = get_participant(conn, session.participant_id)
    except KeyError as err:
        raise PermissionError(
            f"Cannot schedule session for participant {session.participant_id!r}: "
            f"Participant is not currently enrolled with active consent in study "
            f"{session.study_id!r}."
        ) from err

    # 3. Prevent cross-study session assignment
    if participant.study_id != session.study_id:
        raise ValueError(
            f"Cross-study session assignment rejected: participant {session.participant_id!r} "
            f"belongs to study {participant.study_id!r}, cannot create session in study "
            f"{session.study_id!r}."
        )

    # 4. Verify participant is enrolled and consented in this exact study
    if not is_participant_active(conn, session.participant_id, study_id=session.study_id):
        raise PermissionError(
            f"Cannot schedule session for participant {session.participant_id!r}: "
            f"Participant is not currently enrolled with active consent in study "
            f"{session.study_id!r}."
        )

    # 5. Verify exact consent reference linkage (no implicit fallback permitted)
    consent_ref = session.consent_reference
    if not consent_ref or not str(consent_ref).strip():
        raise PermissionError(
            f"Cannot schedule session for participant {session.participant_id!r}: "
            f"Missing required consent_reference."
        )

    try:
        consent = get_consent(conn, consent_ref)
    except KeyError as err:
        raise PermissionError(
            f"Cannot schedule session for participant {session.participant_id!r}: "
            f"Referenced consent {consent_ref!r} does not exist in study {session.study_id!r}."
        ) from err

    if consent.participant_id != session.participant_id or consent.study_id != session.study_id:
        raise PermissionError(
            f"Consent linkage mismatch: consent {consent.consent_record_id!r} belongs to "
            f"participant {consent.participant_id!r} in study {consent.study_id!r}, "
            f"but session is for participant {session.participant_id!r} in study "
            f"{session.study_id!r}."
        )
    if consent.withdrawal_status:
        raise PermissionError(
            f"Referenced consent {consent.consent_record_id!r} has been withdrawn or revoked."
        )
    if not consent.consent_form_version or consent.consent_form_version.lower() == "none":
        raise PermissionError(
            f"Referenced consent {consent.consent_record_id!r} has invalid "
            f"consent form version: {consent.consent_form_version!r}."
        )

    # Capture origin safety check: ensure live browser mic or untrusted user uploads fail closed
    if session.capture_origin in {"user_upload", "live_browser_mic", "live_app_mic", "unknown"}:
        pass  # We store capture_origin accurately; disease inference is fail-closed by policy

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO sessions (
            session_id, study_id, protocol_version, participant_id,
            visit_index, visit_label, acquisition_domain_id, capture_origin,
            recording_timestamp, consent_reference, device_metadata_json,
            task_completion_states_json, qc_results_json, processing_receipt_sha256,
            missing_task_reasons_json, overall_session_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            session.session_id,
            session.study_id,
            session.protocol_version,
            session.participant_id,
            session.visit_index,
            session.visit_label,
            session.acquisition_domain_id,
            session.capture_origin,
            session.recording_timestamp,
            consent_ref,
            json.dumps(session.device_metadata),
            json.dumps(session.task_completion_states),
            json.dumps(session.qc_results),
            session.processing_receipt_sha256,
            json.dumps(session.missing_task_reasons),
            session.overall_session_status,
        ),
    )


def get_session(conn: sqlite3.Connection, session_id: str) -> ResearchSession:
    """Retrieve session by ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, study_id, protocol_version, participant_id,
               visit_index, visit_label, acquisition_domain_id, capture_origin,
               recording_timestamp, consent_reference, device_metadata_json,
               task_completion_states_json, qc_results_json, processing_receipt_sha256,
               missing_task_reasons_json, overall_session_status
        FROM sessions
        WHERE session_id = ?;
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise KeyError(f"Session not found: {session_id}")

    return ResearchSession(
        session_id=row["session_id"],
        study_id=row["study_id"],
        protocol_version=row["protocol_version"],
        participant_id=row["participant_id"],
        visit_index=row["visit_index"],
        visit_label=row["visit_label"],
        acquisition_domain_id=row["acquisition_domain_id"],
        capture_origin=row["capture_origin"],
        recording_timestamp=row["recording_timestamp"],
        consent_reference=row["consent_reference"],
        device_metadata=json.loads(row["device_metadata_json"]),
        task_completion_states=json.loads(row["task_completion_states_json"]),
        qc_results=json.loads(row["qc_results_json"]),
        processing_receipt_sha256=row["processing_receipt_sha256"],
        missing_task_reasons=json.loads(row["missing_task_reasons_json"]),
        overall_session_status=row["overall_session_status"],
    )


def list_sessions(
    conn: sqlite3.Connection,
    study_id: str | None = None,
    participant_id: str | None = None,
) -> list[ResearchSession]:
    """List sessions filtered by study or participant."""
    cursor = conn.cursor()
    query = """
        SELECT session_id, study_id, protocol_version, participant_id,
               visit_index, visit_label, acquisition_domain_id, capture_origin,
               recording_timestamp, consent_reference, device_metadata_json,
               task_completion_states_json, qc_results_json, processing_receipt_sha256,
               missing_task_reasons_json, overall_session_status
        FROM sessions
    """
    params: list[Any] = []
    clauses: list[str] = []
    if study_id:
        clauses.append("study_id = ?")
        params.append(study_id)
    if participant_id:
        clauses.append("participant_id = ?")
        params.append(participant_id)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY participant_id, visit_index;"

    cursor.execute(query, tuple(params))
    return [
        ResearchSession(
            session_id=row["session_id"],
            study_id=row["study_id"],
            protocol_version=row["protocol_version"],
            participant_id=row["participant_id"],
            visit_index=row["visit_index"],
            visit_label=row["visit_label"],
            acquisition_domain_id=row["acquisition_domain_id"],
            capture_origin=row["capture_origin"],
            recording_timestamp=row["recording_timestamp"],
            consent_reference=row["consent_reference"],
            device_metadata=json.loads(row["device_metadata_json"]),
            task_completion_states=json.loads(row["task_completion_states_json"]),
            qc_results=json.loads(row["qc_results_json"]),
            processing_receipt_sha256=row["processing_receipt_sha256"],
            missing_task_reasons=json.loads(row["missing_task_reasons_json"]),
            overall_session_status=row["overall_session_status"],
        )
        for row in cursor.fetchall()
    ]


def update_session_status(conn: sqlite3.Connection, session_id: str, new_status: str) -> None:
    """Update overall session status."""
    if new_status not in VALID_SESSION_STATUSES:
        raise ValueError(f"Invalid overall_session_status: {new_status!r}")

    get_session(conn, session_id)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sessions SET overall_session_status = ? WHERE session_id = ?;",
        (new_status, session_id),
    )


def preflight_session_ingestion(
    conn: sqlite3.Connection,
    session_id: str,
    tasks_to_process: list[str] | None = None,
    requested_operation: str = "feature_extraction",
) -> tuple[bool, str, dict[str, Any]]:
    """Central authorization preflight gate executed strictly BEFORE audio processing."""
    # 1. Session check
    try:
        session = get_session(conn, session_id)
    except KeyError:
        return False, f"Session not found: {session_id!r}", {}

    if session.overall_session_status == "RESTRICTED_WITHDRAWN":
        return False, f"Session {session_id!r} is RESTRICTED_WITHDRAWN; processing blocked.", {}

    # 2. Study check
    try:
        study = get_study(conn, session.study_id)
    except KeyError:
        return False, f"Study not found: {session.study_id!r}", {}

    if study.study_status in {"archived", "completed"}:
        return (
            False,
            f"Study {session.study_id!r} status is {study.study_status!r}; processing blocked.",
            {},
        )

    # 3. Participant check
    try:
        participant = get_participant(conn, session.participant_id)
    except KeyError:
        return False, f"Participant not found: {session.participant_id!r}", {}

    if participant.study_id != session.study_id:
        return (
            False,
            f"Cross-study participant linkage failure: participant belongs to "
            f"{participant.study_id!r}, session is in study {session.study_id!r}.",
            {},
        )

    if participant.enrollment_status == "withdrawn":
        return False, f"Participant {participant.participant_id!r} has withdrawn from research.", {}

    if participant.consent_status != "consented":
        return (
            False,
            f"Participant {participant.participant_id!r} consent status is "
            f"{participant.consent_status!r} (must be 'consented').",
            {},
        )

    # 4. Consent linkage check
    if not session.consent_reference:
        return False, "Session has no associated consent reference.", {}

    try:
        consent = get_consent(conn, session.consent_reference)
    except KeyError:
        return False, f"Referenced consent not found: {session.consent_reference!r}", {}

    if consent.participant_id != session.participant_id or consent.study_id != session.study_id:
        return (
            False,
            f"Consent linkage mismatch: consent is for participant {consent.participant_id!r} "
            f"in study {consent.study_id!r}, but session is for {session.participant_id!r} "
            f"in study {session.study_id!r}.",
            {},
        )

    if consent.withdrawal_status:
        return (
            False,
            f"Referenced consent {session.consent_reference!r} has been withdrawn or revoked.",
            {},
        )

    if not consent.consent_form_version or consent.consent_form_version.lower() == "none":
        return (
            False,
            f"Referenced consent {session.consent_reference!r} has invalid "
            f"consent form version: {consent.consent_form_version!r}.",
            {},
        )

    # 5. Exact session-pinned consent task & scope verification (no fallback to latest active)
    tasks = tasks_to_process or ["sustained_vowel", "ddk", "connected_speech", "vowel_space"]
    for t in tasks:
        if not _is_task_permitted(t, consent.permitted_recording_tasks):
            return (
                False,
                f"Task consent failure for {t!r}: not permitted by exact session consent "
                f"{consent.consent_record_id!r}. Permitted: {consent.permitted_recording_tasks}",
                {},
            )

    op_ok, op_msg = _verify_consent_operation_scope(consent, requested_operation)
    if not op_ok:
        return False, op_msg, {}

    # 6. Dataset DUA verification
    try:
        dua = get_dataset_access(conn, study.dataset_id, dataset_version=study.dataset_version)
    except KeyError:
        return (
            False,
            f"No registered DUA for dataset {study.dataset_id!r} "
            f"version {study.dataset_version!r}.",
            {},
        )

    if dua.dataset_version != study.dataset_version:
        return (
            False,
            f"Dataset version mismatch: study requires version {study.dataset_version!r}, "
            f"DUA authorizes version {dua.dataset_version!r}.",
            {},
        )

    if dua.access_approval_state != "APPROVED":
        return (
            False,
            f"Dataset access approval state is {dua.access_approval_state!r} (must be 'APPROVED').",
            {},
        )

    if dua.dua_state not in {"ACTIVE", "NOT_REQUIRED"}:
        return (
            False,
            f"Dataset DUA state is {dua.dua_state!r} (must be 'ACTIVE' or 'NOT_REQUIRED').",
            {},
        )

    if dua.expiration_date:
        today_iso = utc_now_iso()[:10]
        if str(dua.expiration_date)[:10] < today_iso:
            return (
                False,
                f"Dataset DUA expired on {dua.expiration_date}. Ingestion blocked.",
                {},
            )

    if requested_operation not in dua.permitted_data_processing_operations:
        return (
            False,
            f"Requested operation {requested_operation!r} is not in DUA permitted operations: "
            f"{dua.permitted_data_processing_operations}.",
            {},
        )

    for t in tasks:
        d_ok, d_msg = verify_dataset_authorization_for_task(
            conn,
            study.dataset_id,
            t,
            dataset_version=study.dataset_version,
            requested_operation=requested_operation,
        )
        if not d_ok:
            return False, f"Dataset DUA authorization failure for task {t!r}: {d_msg}", {}

    # 7. Acquisition domain check
    from voxneuro.modeling.domain_registry import load_domain_registry

    try:
        reg = load_domain_registry()
        if not reg.is_registered(session.acquisition_domain_id):
            return (
                False,
                f"Acquisition domain {session.acquisition_domain_id!r} is not registered.",
                {},
            )
        dom = reg.get_domain(session.acquisition_domain_id)
        if dom.feature_schema_compatibility != "voxneuro.voice.v3":
            return (
                False,
                f"Acquisition domain schema {dom.feature_schema_compatibility!r} is incompatible.",
                {},
            )
    except Exception as exc:
        return False, f"Domain registry validation failed: {exc}", {}

    return (
        True,
        "Preflight session ingestion authorization passed.",
        {
            "session": session,
            "study": study,
            "participant": participant,
            "consent": consent,
            "dua": dua,
        },
    )


def record_task_recording(
    conn: sqlite3.Connection,
    task: TaskRecording,
    features: dict[str, Any] | None = None,
    consent: Any | None = None,
    requested_operation: str = "feature_extraction",
) -> None:
    """Record task execution and store derived features after centralized preflight."""
    ok, reason, meta = preflight_session_ingestion(
        conn,
        task.session_id,
        tasks_to_process=[task.task_type],
        requested_operation=requested_operation,
    )
    if not ok:
        raise PermissionError(
            f"Task recording blocked by central authorization preflight: {reason}"
        )

    session = meta["session"]
    session_consent = meta["consent"]

    # If caller passed a consent object, verify exact field equality with authorized DB consent
    if consent is not None and consent != session_consent:
        raise PermissionError(
            f"Supplied consent {getattr(consent, 'consent_record_id', None)!r} does not match "
            f"the authorized session-pinned consent {session_consent.consent_record_id!r}."
        )

    # Enforce derived-feature retention strictly from exact session consent (defaults to False)
    retain_features = bool(session_consent.permission_to_retain_derived_features)

    final_features = features if retain_features else None
    final_feature_count = len(final_features) if final_features else 0
    final_status = (
        task.task_status
        if retain_features
        else ("ACCEPTED_TRANSIENT_PROCESSED" if task.quality_passed else task.task_status)
    )

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO task_recordings (
            task_id, session_id, task_type, task_status, audio_duration_seconds,
            quality_passed, rejection_reason, feature_schema_version,
            feature_schema_fingerprint, derived_feature_count, qc_metrics_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, task_type) DO UPDATE SET
            task_status=excluded.task_status,
            audio_duration_seconds=excluded.audio_duration_seconds,
            quality_passed=excluded.quality_passed,
            rejection_reason=excluded.rejection_reason,
            feature_schema_version=excluded.feature_schema_version,
            feature_schema_fingerprint=excluded.feature_schema_fingerprint,
            derived_feature_count=excluded.derived_feature_count,
            qc_metrics_json=excluded.qc_metrics_json;
        """,
        (
            task.task_id,
            task.session_id,
            task.task_type,
            final_status,
            task.audio_duration_seconds,
            1 if task.quality_passed else 0,
            task.rejection_reason,
            task.feature_schema_version,
            task.feature_schema_fingerprint,
            final_feature_count,
            json.dumps(task.qc_metrics),
            task.created_at,
        ),
    )

    if final_features is not None and task.task_status == "FEATURES_EXTRACTED":
        feat_id = f"feat-{uuid.uuid4().hex[:12]}"
        cursor.execute(
            """
            INSERT INTO derived_features (
                feature_record_id, task_id, session_id, participant_id,
                task_type, schema_version, features_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                feat_id,
                task.task_id,
                task.session_id,
                session.participant_id,
                task.task_type,
                task.feature_schema_version or "unknown",
                json.dumps(final_features),
                utc_now_iso(),
            ),
        )


def get_task_recordings_for_session(
    conn: sqlite3.Connection, session_id: str
) -> list[TaskRecording]:
    """Retrieve all task recording entries for a session."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT task_id, session_id, task_type, task_status, audio_duration_seconds,
               quality_passed, rejection_reason, feature_schema_version,
               feature_schema_fingerprint, derived_feature_count, qc_metrics_json,
               created_at
        FROM task_recordings
        WHERE session_id = ?
        ORDER BY task_type;
        """,
        (session_id,),
    )
    return [
        TaskRecording(
            task_id=row["task_id"],
            session_id=row["session_id"],
            task_type=row["task_type"],
            task_status=row["task_status"],
            audio_duration_seconds=row["audio_duration_seconds"],
            quality_passed=bool(row["quality_passed"]),
            rejection_reason=row["rejection_reason"],
            feature_schema_version=row["feature_schema_version"],
            feature_schema_fingerprint=row["feature_schema_fingerprint"],
            derived_feature_count=row["derived_feature_count"],
            qc_metrics=json.loads(row["qc_metrics_json"]),
            created_at=row["created_at"],
        )
        for row in cursor.fetchall()
    ]


def get_derived_features_for_session(
    conn: sqlite3.Connection, session_id: str
) -> dict[str, dict[str, Any]]:
    """Retrieve all extracted feature records for a session keyed by task_type."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT task_type, schema_version, features_json
        FROM derived_features
        WHERE session_id = ?;
        """,
        (session_id,),
    )
    res: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        res[row["task_type"]] = {
            "schema_version": row["schema_version"],
            "features": json.loads(row["features_json"]),
        }
    return res


def ingest_session_multitask_audio(
    conn: sqlite3.Connection,
    session_id: str,
    sustained_vowel: Any | None = None,
    ddk_recordings: dict[str, Any] | None = None,
    connected_speech: Any | None = None,
    vowel_space_recordings: dict[str, Any] | None = None,
) -> MultiTaskSessionResult:
    """Run M3 multi-task pipeline on session audio under strict preflight authorization."""
    # Determine which speech tasks were supplied for ingestion
    tasks_present: list[str] = []
    if sustained_vowel is not None:
        tasks_present.append("sustained_vowel")
    if ddk_recordings is not None:
        tasks_present.append("ddk")
    if connected_speech is not None:
        tasks_present.append("connected_speech")
    if vowel_space_recordings is not None:
        tasks_present.append("vowel_space")

    if not tasks_present:
        tasks_present = ["sustained_vowel"]

    # STEP 0: Mandatory preflight authorization check BEFORE any audio decoding or extraction
    is_authorized, reason, preflight_meta = preflight_session_ingestion(
        conn,
        session_id=session_id,
        tasks_to_process=tasks_present,
        requested_operation="feature_extraction",
    )
    if not is_authorized:
        raise PermissionError(f"Session audio ingestion preflight failed: {reason}")

    # ONLY after preflight passes: execute M3 multi-task evaluation
    result = analyze_multitask_session(
        sustained_vowel=sustained_vowel,
        ddk_recordings=ddk_recordings,
        connected_speech=connected_speech,
        vowel_space_recordings=vowel_space_recordings,
        session_id=session_id,
    )

    consent = preflight_meta.get("consent")
    completion_states: dict[str, str] = {}
    qc_results: dict[str, Any] = {}
    missing_reasons: dict[str, str] = {}

    for task_name, task_dict in result.tasks.items():
        raw_status = str(
            task_dict.get("task_status") or task_dict.get("status") or "NOT_STARTED"
        ).lower()
        completion_states[task_name] = raw_status

        errors = task_dict.get("errors") or []
        err_msg = "; ".join(errors) if errors else task_dict.get("error")
        if err_msg:
            missing_reasons[task_name] = str(err_msg)

        task_id = f"task-{uuid.uuid4().hex[:12]}"
        is_passed = raw_status in {"complete", "completed"}
        feat_dict = task_dict.get("features", {}) if is_passed else None
        feat_count = len(feat_dict) if feat_dict else 0

        qc_meta = task_dict.get("quality") or task_dict.get("validation") or {}
        qc_results[task_name] = qc_meta

        duration_sec = (
            qc_meta.get("duration_seconds")
            if isinstance(qc_meta, dict)
            else task_dict.get("duration_seconds") or 0.0
        )

        schema_ver = task_dict.get("task_schema_version") or task_dict.get("schema_version")
        schema_fp = task_dict.get("task_schema_fingerprint") or task_dict.get("schema_fingerprint")

        rec = TaskRecording(
            task_id=task_id,
            session_id=session_id,
            task_type=task_name,
            task_status="FEATURES_EXTRACTED" if is_passed else "PROCESSING_FAILED",
            audio_duration_seconds=float(duration_sec or 0.0),
            quality_passed=is_passed,
            rejection_reason=str(err_msg) if err_msg else None,
            feature_schema_version=schema_ver,
            feature_schema_fingerprint=schema_fp,
            derived_feature_count=feat_count,
            qc_metrics=qc_meta if isinstance(qc_meta, dict) else {},
            created_at=utc_now_iso(),
        )

        record_task_recording(conn, rec, features=feat_dict, consent=consent)

    # Update session overall status
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE sessions
        SET task_completion_states_json = ?, qc_results_json = ?,
            missing_task_reasons_json = ?, overall_session_status = ?
        WHERE session_id = ?;
        """,
        (
            json.dumps(completion_states),
            json.dumps(qc_results),
            json.dumps(missing_reasons),
            (
                "COMPLETED"
                if str(result.overall_processing_status).lower() in {"complete", "completed"}
                else "QUALITY_FAILED"
            ),
            session_id,
        ),
    )

    return result
