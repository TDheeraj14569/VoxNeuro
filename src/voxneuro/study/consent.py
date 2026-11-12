"""Consent tracking and Data Use Agreement (DUA) authorization enforcement."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from voxneuro.study.participant import get_participant, update_participant_consent_status
from voxneuro.study.schema import (
    ConsentRecord,
    DatasetAccessRecord,
)


def record_consent(conn: sqlite3.Connection, consent: ConsentRecord) -> None:
    """Record an informed consent submission for a participant."""
    # Ensure participant exists and belongs to the exact study
    participant = get_participant(conn, consent.participant_id)
    if participant.study_id != consent.study_id:
        raise ValueError(
            f"Cross-study consent prohibited: participant {consent.participant_id} belongs to "
            f"study {participant.study_id!r}, cannot record consent for study {consent.study_id!r}."
        )

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO consents (
            consent_record_id, participant_id, study_id, consent_form_version,
            consent_date, scope_of_permission_json, permitted_recording_tasks_json,
            permitted_research_uses_json, permission_to_retain_derived_features,
            permission_to_retain_audio, withdrawal_status, revocation_date,
            source_document_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            consent.consent_record_id,
            consent.participant_id,
            consent.study_id,
            consent.consent_form_version,
            consent.consent_date,
            json.dumps(consent.scope_of_permission),
            json.dumps(consent.permitted_recording_tasks),
            json.dumps(consent.permitted_research_uses),
            1 if consent.permission_to_retain_derived_features else 0,
            1 if consent.permission_to_retain_audio else 0,
            1 if consent.withdrawal_status else 0,
            consent.revocation_date,
            consent.source_document_reference,
        ),
    )
    # Update participant consent status
    if not consent.withdrawal_status:
        update_participant_consent_status(
            conn,
            consent.participant_id,
            consent_status="consented",
            consent_version=consent.consent_form_version,
        )


def get_consent(conn: sqlite3.Connection, consent_record_id: str) -> ConsentRecord:
    """Retrieve consent record by ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT consent_record_id, participant_id, study_id, consent_form_version,
               consent_date, scope_of_permission_json, permitted_recording_tasks_json,
               permitted_research_uses_json, permission_to_retain_derived_features,
               permission_to_retain_audio, withdrawal_status, revocation_date,
               source_document_reference
        FROM consents
        WHERE consent_record_id = ?;
        """,
        (consent_record_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise KeyError(f"Consent record not found: {consent_record_id}")

    return ConsentRecord(
        consent_record_id=row["consent_record_id"],
        participant_id=row["participant_id"],
        study_id=row["study_id"],
        consent_form_version=row["consent_form_version"],
        consent_date=row["consent_date"],
        scope_of_permission=json.loads(row["scope_of_permission_json"]),
        permitted_recording_tasks=json.loads(row["permitted_recording_tasks_json"]),
        permitted_research_uses=json.loads(row["permitted_research_uses_json"]),
        permission_to_retain_derived_features=bool(row["permission_to_retain_derived_features"]),
        permission_to_retain_audio=bool(row["permission_to_retain_audio"]),
        withdrawal_status=bool(row["withdrawal_status"]),
        revocation_date=row["revocation_date"],
        source_document_reference=row["source_document_reference"],
    )


def get_active_consent_for_participant(
    conn: sqlite3.Connection, participant_id: str, study_id: str | None = None
) -> ConsentRecord | None:
    """Retrieve most recent non-revoked consent record for participant in study."""
    target_study = study_id
    if target_study is None:
        try:
            part = get_participant(conn, participant_id)
            target_study = part.study_id
        except KeyError:
            pass

    cursor = conn.cursor()
    if target_study:
        cursor.execute(
            """
            SELECT consent_record_id, participant_id, study_id, consent_form_version,
                   consent_date, scope_of_permission_json, permitted_recording_tasks_json,
                   permitted_research_uses_json, permission_to_retain_derived_features,
                   permission_to_retain_audio, withdrawal_status, revocation_date,
                   source_document_reference
            FROM consents
            WHERE participant_id = ? AND study_id = ? AND withdrawal_status = 0
            ORDER BY consent_date DESC
            LIMIT 1;
            """,
            (participant_id, target_study),
        )
    else:
        cursor.execute(
            """
            SELECT consent_record_id, participant_id, study_id, consent_form_version,
                   consent_date, scope_of_permission_json, permitted_recording_tasks_json,
                   permitted_research_uses_json, permission_to_retain_derived_features,
                   permission_to_retain_audio, withdrawal_status, revocation_date,
                   source_document_reference
            FROM consents
            WHERE participant_id = ? AND withdrawal_status = 0
            ORDER BY consent_date DESC
            LIMIT 1;
            """,
            (participant_id,),
        )
    row = cursor.fetchone()
    if not row:
        return None

    return ConsentRecord(
        consent_record_id=row["consent_record_id"],
        participant_id=row["participant_id"],
        study_id=row["study_id"],
        consent_form_version=row["consent_form_version"],
        consent_date=row["consent_date"],
        scope_of_permission=json.loads(row["scope_of_permission_json"]),
        permitted_recording_tasks=json.loads(row["permitted_recording_tasks_json"]),
        permitted_research_uses=json.loads(row["permitted_research_uses_json"]),
        permission_to_retain_derived_features=bool(row["permission_to_retain_derived_features"]),
        permission_to_retain_audio=bool(row["permission_to_retain_audio"]),
        withdrawal_status=bool(row["withdrawal_status"]),
        revocation_date=row["revocation_date"],
        source_document_reference=row["source_document_reference"],
    )


def _is_task_permitted(task_type: str, permitted_tasks: list[str]) -> bool:
    """Check if task_type matches permitted tasks, allowing sustained_vowel variants."""
    if task_type in permitted_tasks:
        return True
    if task_type.startswith("sustained_vowel") and any(
        t.startswith("sustained_vowel") for t in permitted_tasks
    ):
        return True
    return False


def verify_participant_consent_for_task(
    conn: sqlite3.Connection,
    participant_id: str,
    task_type: str,
    study_id: str | None = None,
) -> tuple[bool, str]:
    """Verify that a participant has active, unwithdrawn consent for a given task in the study."""
    consent = get_active_consent_for_participant(conn, participant_id, study_id=study_id)
    if not consent:
        st_info = f" in study {study_id!r}" if study_id else ""
        return False, f"Participant {participant_id!r} has no active consent on file{st_info}."

    if consent.withdrawal_status:
        return False, f"Consent for participant {participant_id!r} has been withdrawn."

    if not _is_task_permitted(task_type, consent.permitted_recording_tasks):
        return False, (
            f"Task {task_type!r} is not within consented recording tasks "
            f"for participant {participant_id!r}."
        )

    return True, "Consent verified."


def register_dataset_access(conn: sqlite3.Connection, record: DatasetAccessRecord) -> None:
    """Register or update a dataset access and DUA governance record."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO dataset_access (
            dataset_id, dataset_version, dataset_owner, license_type,
            access_approval_state, dua_state, permitted_tasks_json,
            permitted_data_processing_operations_json, storage_restrictions,
            publication_restrictions, expiration_date, source_documentation,
            dua_document_fingerprint, authorization_ref, source_id,
            authorization_registry_id, authorization_registry_version,
            issuing_authority, dua_source_artifact_reference, dua_verification_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(dataset_id) DO UPDATE SET
            dataset_version=excluded.dataset_version,
            dataset_owner=excluded.dataset_owner,
            license_type=excluded.license_type,
            access_approval_state=excluded.access_approval_state,
            dua_state=excluded.dua_state,
            permitted_tasks_json=excluded.permitted_tasks_json,
            permitted_data_processing_operations_json=excluded.permitted_data_processing_operations_json,
            storage_restrictions=excluded.storage_restrictions,
            publication_restrictions=excluded.publication_restrictions,
            expiration_date=excluded.expiration_date,
            source_documentation=excluded.source_documentation,
            dua_document_fingerprint=excluded.dua_document_fingerprint,
            authorization_ref=excluded.authorization_ref,
            source_id=excluded.source_id,
            authorization_registry_id=excluded.authorization_registry_id,
            authorization_registry_version=excluded.authorization_registry_version,
            issuing_authority=excluded.issuing_authority,
            dua_source_artifact_reference=excluded.dua_source_artifact_reference,
            dua_verification_status=excluded.dua_verification_status;
        """,
        (
            record.dataset_id,
            record.dataset_version,
            record.dataset_owner,
            record.license_type,
            record.access_approval_state,
            record.dua_state,
            json.dumps(record.permitted_tasks),
            json.dumps(record.permitted_data_processing_operations),
            record.storage_restrictions,
            record.publication_restrictions,
            record.expiration_date,
            record.source_documentation,
            record.dua_document_fingerprint,
            record.authorization_ref,
            record.source_id,
            record.authorization_registry_id,
            record.authorization_registry_version,
            record.issuing_authority,
            record.dua_source_artifact_reference,
            record.dua_verification_status,
        ),
    )


def get_dataset_access(
    conn: sqlite3.Connection, dataset_id: str, dataset_version: str | None = None
) -> DatasetAccessRecord:
    """Retrieve DUA record by dataset_id, optionally verifying exact dataset_version."""
    cursor = conn.cursor()
    if dataset_version is not None:
        cursor.execute(
            """
            SELECT dataset_id, dataset_version, dataset_owner, license_type,
                   access_approval_state, dua_state, permitted_tasks_json,
                   permitted_data_processing_operations_json, storage_restrictions,
                   publication_restrictions, expiration_date, source_documentation,
                   dua_document_fingerprint, authorization_ref, source_id,
                   authorization_registry_id, authorization_registry_version,
                   issuing_authority, dua_source_artifact_reference, dua_verification_status
            FROM dataset_access
            WHERE dataset_id = ? AND dataset_version = ?;
            """,
            (dataset_id, dataset_version),
        )
        row = cursor.fetchone()
        if not row:
            raise KeyError(
                f"Dataset access record not found for dataset {dataset_id!r} "
                f"version {dataset_version!r}"
            )
    else:
        cursor.execute(
            """
            SELECT dataset_id, dataset_version, dataset_owner, license_type,
                   access_approval_state, dua_state, permitted_tasks_json,
                   permitted_data_processing_operations_json, storage_restrictions,
                   publication_restrictions, expiration_date, source_documentation,
                   dua_document_fingerprint, authorization_ref, source_id,
                   authorization_registry_id, authorization_registry_version,
                   issuing_authority, dua_source_artifact_reference, dua_verification_status
            FROM dataset_access
            WHERE dataset_id = ?;
            """,
            (dataset_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise KeyError(f"Dataset access record not found: {dataset_id}")

    return DatasetAccessRecord(
        dataset_id=row["dataset_id"],
        dataset_version=row["dataset_version"],
        dataset_owner=row["dataset_owner"],
        license_type=row["license_type"],
        access_approval_state=row["access_approval_state"],
        dua_state=row["dua_state"],
        permitted_tasks=json.loads(row["permitted_tasks_json"]),
        permitted_data_processing_operations=json.loads(
            row["permitted_data_processing_operations_json"]
        ),
        storage_restrictions=row["storage_restrictions"],
        publication_restrictions=row["publication_restrictions"],
        expiration_date=row["expiration_date"],
        source_documentation=row["source_documentation"],
        dua_document_fingerprint=row["dua_document_fingerprint"],
        authorization_ref=row["authorization_ref"],
        source_id=row["source_id"],
        authorization_registry_id=row["authorization_registry_id"],
        authorization_registry_version=row["authorization_registry_version"],
        issuing_authority=row["issuing_authority"],
        dua_source_artifact_reference=row["dua_source_artifact_reference"],
        dua_verification_status=row["dua_verification_status"],
    )


def list_dataset_access(conn: sqlite3.Connection) -> list[DatasetAccessRecord]:
    """List all registered dataset access / DUA records."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT dataset_id, dataset_version, dataset_owner, license_type,
               access_approval_state, dua_state, permitted_tasks_json,
               permitted_data_processing_operations_json, storage_restrictions,
               publication_restrictions, expiration_date, source_documentation,
               dua_document_fingerprint, authorization_ref, source_id,
               authorization_registry_id, authorization_registry_version,
               issuing_authority, dua_source_artifact_reference, dua_verification_status
        FROM dataset_access
        ORDER BY dataset_id;
        """
    )
    return [
        DatasetAccessRecord(
            dataset_id=row["dataset_id"],
            dataset_version=row["dataset_version"],
            dataset_owner=row["dataset_owner"],
            license_type=row["license_type"],
            access_approval_state=row["access_approval_state"],
            dua_state=row["dua_state"],
            permitted_tasks=json.loads(row["permitted_tasks_json"]),
            permitted_data_processing_operations=json.loads(
                row["permitted_data_processing_operations_json"]
            ),
            storage_restrictions=row["storage_restrictions"],
            publication_restrictions=row["publication_restrictions"],
            expiration_date=row["expiration_date"],
            source_documentation=row["source_documentation"],
            dua_document_fingerprint=row["dua_document_fingerprint"],
            authorization_ref=row["authorization_ref"],
            source_id=row["source_id"],
            authorization_registry_id=row["authorization_registry_id"],
            authorization_registry_version=row["authorization_registry_version"],
            issuing_authority=row["issuing_authority"],
            dua_source_artifact_reference=row["dua_source_artifact_reference"],
            dua_verification_status=row["dua_verification_status"],
        )
        for row in cursor.fetchall()
    ]


def verify_dataset_authorization_for_task(
    conn: sqlite3.Connection,
    dataset_id: str,
    task_type: str,
    dataset_version: str | None = None,
    requested_operation: str = "feature_extraction",
) -> tuple[bool, str]:
    """Verify dataset has approved access and DUA permitting requested task and operation."""
    try:
        dua = get_dataset_access(conn, dataset_id)
    except KeyError:
        return (
            False,
            f"Dataset {dataset_id!r} has no registered access/DUA record. Ingestion blocked.",
        )

    # Exact dataset version check: version 1.0 does not authorize 2.0
    if dataset_version is not None and dua.dataset_version != dataset_version:
        return (
            False,
            f"Dataset version mismatch: study requires {dataset_version!r}, "
            f"but registered DUA authorizes version {dua.dataset_version!r}.",
        )

    if dua.access_approval_state != "APPROVED":
        return (
            False,
            f"Dataset {dataset_id!r} access approval state is {dua.access_approval_state!r}. "
            "Must be 'APPROVED' to ingest data.",
        )

    if dua.dua_state not in {"ACTIVE", "NOT_REQUIRED"}:
        return (
            False,
            f"Dataset {dataset_id!r} DUA state is {dua.dua_state!r}. "
            "Must be 'ACTIVE' or 'NOT_REQUIRED'.",
        )

    # Expiration date check: expired DUA blocks processing
    if dua.expiration_date:
        today_iso = datetime.now(UTC).date().isoformat()
        if str(dua.expiration_date)[:10] < today_iso:
            return (
                False,
                f"Dataset {dataset_id!r} DUA expired on {dua.expiration_date}. Processing blocked.",
            )

    # Requested operation authorization check
    if requested_operation not in dua.permitted_data_processing_operations:
        return (
            False,
            f"Operation {requested_operation!r} is not authorized in dataset {dataset_id!r} DUA "
            f"permitted operations: {dua.permitted_data_processing_operations}.",
        )

    if not _is_task_permitted(task_type, dua.permitted_tasks):
        return (
            False,
            f"Task {task_type!r} is not authorized in dataset {dataset_id!r} DUA permitted tasks.",
        )

    return True, "Dataset DUA authorization verified."
