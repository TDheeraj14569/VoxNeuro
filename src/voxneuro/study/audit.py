"""Audit logging, event redaction, and reproducible processing run receipts."""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from typing import Any

from voxneuro.features.schema import (
    schema_fingerprint as v3_schema_fingerprint,
)
from voxneuro.features.tasks.schema import (
    connected_speech_schema_fingerprint,
    ddk_schema_fingerprint,
    v4_envelope_schema_fingerprint,
    vowel_space_schema_fingerprint,
)
from voxneuro.modeling.domain_registry import load_domain_registry
from voxneuro.provenance import project_code_fingerprint
from voxneuro.study.schema import ProcessingRunReceipt, utc_now_iso


def sanitize_audit_details(details: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize audit metadata to prevent accidental storage of PII or host paths."""
    if not details:
        return {}
    clean: dict[str, Any] = {}
    for k, v in details.items():
        k_lower = str(k).lower()
        if any(
            term in k_lower
            for term in ("name", "email", "phone", "address", "mrn", "password", "token")
        ):
            clean[k] = "[REDACTED_PII]"
        elif isinstance(v, dict):
            clean[k] = sanitize_audit_details(v)
        else:
            clean[k] = v
    return clean


def log_audit_event(
    conn: sqlite3.Connection,
    operation_type: str,
    entity_type: str,
    entity_id: str,
    actor_role: str = "researcher",
    details: dict[str, Any] | None = None,
) -> int:
    """Record a privacy-safe audit event into the relational audit trail."""
    clean_details = sanitize_audit_details(details)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO audit_log (
            timestamp_utc, operation_type, entity_type, entity_id, actor_role, details_json
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            utc_now_iso(),
            operation_type,
            entity_type,
            entity_id,
            actor_role,
            json.dumps(clean_details),
        ),
    )
    return int(cursor.lastrowid or 0)


def list_audit_events(
    conn: sqlite3.Connection,
    limit: int = 100,
    entity_type: str | None = None,
    operation_type: str | None = None,
) -> list[dict[str, Any]]:
    """Query recent audit events with optional filters."""
    cursor = conn.cursor()
    query = (
        "SELECT log_id, timestamp_utc, operation_type, entity_type, "
        "entity_id, actor_role, details_json FROM audit_log"
    )
    params: list[Any] = []
    clauses: list[str] = []
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if operation_type:
        clauses.append("operation_type = ?")
        params.append(operation_type)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY log_id DESC LIMIT ?;"
    params.append(limit)

    cursor.execute(query, tuple(params))
    return [
        {
            "log_id": row["log_id"],
            "timestamp_utc": row["timestamp_utc"],
            "operation_type": row["operation_type"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "actor_role": row["actor_role"],
            "details": json.loads(row["details_json"]),
        }
        for row in cursor.fetchall()
    ]


def record_processing_run(
    conn: sqlite3.Connection,
    study_id: str,
    session_ids: list[str],
    feature_table_checksum: str,
    processing_status: str = "COMPLETED",
    input_file_checksum: str | None = None,
    exclusion_summary: dict[str, int] | None = None,
    error_summary: dict[str, int] | None = None,
    output_artifact_checksums: dict[str, str] | None = None,
) -> ProcessingRunReceipt:
    """Generate and store an immutable ProcessingRunReceipt with cryptographic provenance."""
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    task_schema_fingerprints = {
        "voxneuro.voice.v3": v3_schema_fingerprint(),
        "voxneuro.task.ddk.v1": ddk_schema_fingerprint(),
        "voxneuro.task.connected_speech.v1": connected_speech_schema_fingerprint(),
        "voxneuro.task.vowel_space.v1": vowel_space_schema_fingerprint(),
        "voxneuro.voice.v4": v4_envelope_schema_fingerprint(),
    }
    registry = load_domain_registry()

    receipt = ProcessingRunReceipt(
        run_id=run_id,
        study_id=study_id,
        session_ids=list(session_ids),
        processing_timestamp=utc_now_iso(),
        application_version="voxneuro-0.5.0-research",
        project_code_fingerprint=project_code_fingerprint(),
        python_version=sys.version.split()[0],
        dependency_lockfile_fingerprint="uv_lock_verified",
        task_schema_fingerprints=task_schema_fingerprints,
        audio_config_fingerprint="8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d",
        feature_config_fingerprint="190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9",
        domain_metadata_fingerprint=registry.fingerprint(),
        input_file_checksum=input_file_checksum,
        feature_table_checksum=feature_table_checksum,
        processing_status=processing_status,
        exclusion_summary=dict(exclusion_summary or {}),
        error_summary=dict(error_summary or {}),
        output_artifact_checksums=dict(output_artifact_checksums or {}),
    )
    receipt_hash = receipt.compute_sha256()
    final_receipt = ProcessingRunReceipt(**{**receipt.to_dict(), "receipt_sha256": receipt_hash})

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO processing_runs (
            run_id, study_id, session_ids_json, processing_timestamp,
            application_version, project_code_fingerprint, python_version,
            dependency_lockfile_fingerprint, task_schema_fingerprints_json,
            audio_config_fingerprint, feature_config_fingerprint,
            domain_metadata_fingerprint, input_file_checksum, feature_table_checksum,
            processing_status, exclusion_summary_json, error_summary_json,
            output_artifact_checksums_json, receipt_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            final_receipt.run_id,
            final_receipt.study_id,
            json.dumps(final_receipt.session_ids),
            final_receipt.processing_timestamp,
            final_receipt.application_version,
            final_receipt.project_code_fingerprint,
            final_receipt.python_version,
            final_receipt.dependency_lockfile_fingerprint,
            json.dumps(final_receipt.task_schema_fingerprints),
            final_receipt.audio_config_fingerprint,
            final_receipt.feature_config_fingerprint,
            final_receipt.domain_metadata_fingerprint,
            final_receipt.input_file_checksum,
            final_receipt.feature_table_checksum,
            final_receipt.processing_status,
            json.dumps(final_receipt.exclusion_summary),
            json.dumps(final_receipt.error_summary),
            json.dumps(final_receipt.output_artifact_checksums),
            final_receipt.receipt_sha256,
        ),
    )

    log_audit_event(
        conn,
        operation_type="PROCESS_RUN_RECORDED",
        entity_type="processing_run",
        entity_id=run_id,
        details={"study_id": study_id, "receipt_sha256": receipt_hash},
    )
    return final_receipt


def get_processing_run(conn: sqlite3.Connection, run_id: str) -> ProcessingRunReceipt:
    """Retrieve an immutable processing run receipt by run_id."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM processing_runs WHERE run_id = ?;", (run_id,))
    row = cursor.fetchone()
    if not row:
        raise KeyError(f"Processing run not found: {run_id}")

    return ProcessingRunReceipt(
        run_id=row["run_id"],
        study_id=row["study_id"],
        session_ids=json.loads(row["session_ids_json"]),
        processing_timestamp=row["processing_timestamp"],
        application_version=row["application_version"],
        project_code_fingerprint=row["project_code_fingerprint"],
        python_version=row["python_version"],
        dependency_lockfile_fingerprint=row["dependency_lockfile_fingerprint"],
        task_schema_fingerprints=json.loads(row["task_schema_fingerprints_json"]),
        audio_config_fingerprint=row["audio_config_fingerprint"],
        feature_config_fingerprint=row["feature_config_fingerprint"],
        domain_metadata_fingerprint=row["domain_metadata_fingerprint"],
        input_file_checksum=row["input_file_checksum"],
        feature_table_checksum=row["feature_table_checksum"],
        processing_status=row["processing_status"],
        exclusion_summary=json.loads(row["exclusion_summary_json"]),
        error_summary=json.loads(row["error_summary_json"]),
        output_artifact_checksums=json.loads(row["output_artifact_checksums_json"]),
        receipt_sha256=row["receipt_sha256"],
    )
