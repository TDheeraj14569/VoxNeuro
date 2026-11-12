"""Study and protocol registry operations with protocol version immutability."""

from __future__ import annotations

import json
import sqlite3

from voxneuro.study.schema import (
    VALID_STUDY_STATUSES,
    ProtocolDefinition,
    Study,
    utc_now_iso,
)


def create_protocol(conn: sqlite3.Connection, protocol: ProtocolDefinition) -> None:
    """Register a new immutable protocol definition."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO protocols (
            protocol_id, protocol_version, tasks_json, visits_expected,
            minimum_interval_days, instructions, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (
            protocol.protocol_id,
            protocol.protocol_version,
            json.dumps(protocol.tasks),
            protocol.visits_expected,
            protocol.minimum_interval_days,
            protocol.instructions,
            protocol.created_at,
        ),
    )


def get_protocol(
    conn: sqlite3.Connection, protocol_id: str, protocol_version: str
) -> ProtocolDefinition:
    """Retrieve a protocol definition by ID and version."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT protocol_id, protocol_version, tasks_json, visits_expected,
               minimum_interval_days, instructions, created_at
        FROM protocols
        WHERE protocol_id = ? AND protocol_version = ?;
        """,
        (protocol_id, protocol_version),
    )
    row = cursor.fetchone()
    if not row:
        raise KeyError(f"Protocol not found: {protocol_id} (version {protocol_version})")

    return ProtocolDefinition(
        protocol_id=row["protocol_id"],
        protocol_version=row["protocol_version"],
        tasks=json.loads(row["tasks_json"]),
        visits_expected=row["visits_expected"],
        minimum_interval_days=row["minimum_interval_days"],
        instructions=row["instructions"],
        created_at=row["created_at"],
    )


def list_protocols(conn: sqlite3.Connection) -> list[ProtocolDefinition]:
    """List all registered protocol definitions."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT protocol_id, protocol_version, tasks_json, visits_expected,
               minimum_interval_days, instructions, created_at
        FROM protocols
        ORDER BY protocol_id, protocol_version;
        """
    )
    return [
        ProtocolDefinition(
            protocol_id=row["protocol_id"],
            protocol_version=row["protocol_version"],
            tasks=json.loads(row["tasks_json"]),
            visits_expected=row["visits_expected"],
            minimum_interval_days=row["minimum_interval_days"],
            instructions=row["instructions"],
            created_at=row["created_at"],
        )
        for row in cursor.fetchall()
    ]


def create_study(conn: sqlite3.Connection, study: Study) -> None:
    """Register a new research study tied to a valid protocol."""
    # Ensure referenced protocol exists
    get_protocol(conn, study.protocol_id, study.protocol_version)

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO studies (
            study_id, study_name, study_description, protocol_id, protocol_version,
            study_status, research_site_id, dataset_id, dataset_version,
            created_at, updated_at, study_owner_role, consent_requirements_json,
            data_retention_policy_id, analysis_configuration_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            study.study_id,
            study.study_name,
            study.study_description,
            study.protocol_id,
            study.protocol_version,
            study.study_status,
            study.research_site_id,
            study.dataset_id,
            study.dataset_version,
            study.created_at,
            study.updated_at,
            study.study_owner_role,
            json.dumps(study.consent_requirements),
            study.data_retention_policy_id,
            study.analysis_configuration_id,
        ),
    )


def get_study(conn: sqlite3.Connection, study_id: str) -> Study:
    """Retrieve a study record by study_id."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT study_id, study_name, study_description, protocol_id, protocol_version,
               study_status, research_site_id, dataset_id, dataset_version,
               created_at, updated_at, study_owner_role, consent_requirements_json,
               data_retention_policy_id, analysis_configuration_id
        FROM studies
        WHERE study_id = ?;
        """,
        (study_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise KeyError(f"Study not found: {study_id}")

    return Study(
        study_id=row["study_id"],
        study_name=row["study_name"],
        study_description=row["study_description"],
        protocol_id=row["protocol_id"],
        protocol_version=row["protocol_version"],
        study_status=row["study_status"],
        research_site_id=row["research_site_id"],
        dataset_id=row["dataset_id"],
        dataset_version=row["dataset_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        study_owner_role=row["study_owner_role"],
        consent_requirements=json.loads(row["consent_requirements_json"]),
        data_retention_policy_id=row["data_retention_policy_id"],
        analysis_configuration_id=row["analysis_configuration_id"],
    )


def list_studies(conn: sqlite3.Connection) -> list[Study]:
    """List all registered studies."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT study_id, study_name, study_description, protocol_id, protocol_version,
               study_status, research_site_id, dataset_id, dataset_version,
               created_at, updated_at, study_owner_role, consent_requirements_json,
               data_retention_policy_id, analysis_configuration_id
        FROM studies
        ORDER BY created_at DESC;
        """
    )
    return [
        Study(
            study_id=row["study_id"],
            study_name=row["study_name"],
            study_description=row["study_description"],
            protocol_id=row["protocol_id"],
            protocol_version=row["protocol_version"],
            study_status=row["study_status"],
            research_site_id=row["research_site_id"],
            dataset_id=row["dataset_id"],
            dataset_version=row["dataset_version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            study_owner_role=row["study_owner_role"],
            consent_requirements=json.loads(row["consent_requirements_json"]),
            data_retention_policy_id=row["data_retention_policy_id"],
            analysis_configuration_id=row["analysis_configuration_id"],
        )
        for row in cursor.fetchall()
    ]


def update_study_status(conn: sqlite3.Connection, study_id: str, new_status: str) -> None:
    """Transition a study's operational status."""
    if new_status not in VALID_STUDY_STATUSES:
        raise ValueError(f"Invalid study status: {new_status!r}")

    # Check existence
    get_study(conn, study_id)

    cursor = conn.cursor()
    cursor.execute(
        "UPDATE studies SET study_status = ?, updated_at = ? WHERE study_id = ?;",
        (new_status, utc_now_iso(), study_id),
    )


def update_study_protocol(
    conn: sqlite3.Connection,
    study_id: str,
    new_protocol_id: str,
    new_protocol_version: str,
) -> None:
    """Update a study to a new protocol version.

    Enforces protocol immutability: Rejects protocol modifications if research
    sessions have already been recorded under the current protocol.
    """
    study = get_study(conn, study_id)
    if study.protocol_id == new_protocol_id and study.protocol_version == new_protocol_version:
        return

    # Verify new protocol exists
    get_protocol(conn, new_protocol_id, new_protocol_version)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) as session_count FROM sessions
        WHERE study_id = ? AND protocol_version = ?;
        """,
        (study_id, study.protocol_version),
    )
    row = cursor.fetchone()
    count = row["session_count"] if row else 0
    if count > 0:
        raise ValueError(
            f"Cannot modify protocol for study {study_id!r}: {count} research session(s) "
            f"have already been recorded under protocol {study.protocol_id} "
            f"v{study.protocol_version}. Protocols are immutable once sessions exist. "
            "Create a new protocol version or new study."
        )

    cursor.execute(
        """
        UPDATE studies
        SET protocol_id = ?, protocol_version = ?, updated_at = ?
        WHERE study_id = ?;
        """,
        (new_protocol_id, new_protocol_version, utc_now_iso(), study_id),
    )
