"""Pseudonymous research participant management with zero direct personal identifiers."""

from __future__ import annotations

import json
import re
import sqlite3

from voxneuro.study.schema import (
    VALID_CONSENT_STATUSES,
    Participant,
)

# Explicit rejection regex for apparent email addresses, phone numbers, or SSN/MRN patterns
PII_DETECTION_PATTERNS = [
    re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),  # Email
    re.compile(r"\b\d{3}[-.\s]?\d{2,3}[-.\s]?\d{4}\b"),  # Phone or SSN
    re.compile(r"\b(?:mrn|ssn|dob|patient|name)[=:\s]", re.IGNORECASE),  # PII labels
]


def validate_pseudonym_safety(identifier: str) -> None:
    """Ensure a proposed participant identifier contains no detectable personal identifiers."""
    for pattern in PII_DETECTION_PATTERNS:
        if pattern.search(identifier):
            raise ValueError(
                f"Proposed participant identifier {identifier!r} contains potential PII "
                "or direct identity markers. Only pseudonymous identifiers are permitted."
            )


def register_participant(conn: sqlite3.Connection, participant: Participant) -> None:
    """Enroll a new pseudonymous participant in a study."""
    validate_pseudonym_safety(participant.participant_id)

    # Verify study exists
    cursor = conn.cursor()
    cursor.execute("SELECT study_id FROM studies WHERE study_id = ?;", (participant.study_id,))
    if not cursor.fetchone():
        raise KeyError(f"Referenced study does not exist: {participant.study_id}")

    # Registration establishes enrollment with pending consent;
    # creating a participant must not create or imply consent.
    cursor.execute(
        """
        SELECT consent_form_version FROM consents
        WHERE participant_id = ? AND study_id = ? AND withdrawal_status = 0;
        """,
        (participant.participant_id, participant.study_id),
    )
    c_row = cursor.fetchone()
    if c_row:
        actual_consent_status = "consented"
        actual_consent_version = c_row["consent_form_version"]
    else:
        actual_consent_status = "pending"
        actual_consent_version = "none"

    cursor.execute(
        """
        INSERT INTO participants (
            participant_id, study_id, enrollment_status, consent_status,
            consent_version, enrollment_timestamp, withdrawal_timestamp,
            site_id, allowed_research_scopes_json, participant_metadata_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            participant.participant_id,
            participant.study_id,
            participant.enrollment_status,
            actual_consent_status,
            actual_consent_version,
            participant.enrollment_timestamp,
            participant.withdrawal_timestamp,
            participant.site_id,
            json.dumps(participant.allowed_research_scopes),
            participant.participant_metadata_status,
        ),
    )


def get_participant(conn: sqlite3.Connection, participant_id: str) -> Participant:
    """Retrieve participant record by pseudonymous ID."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT participant_id, study_id, enrollment_status, consent_status,
               consent_version, enrollment_timestamp, withdrawal_timestamp,
               site_id, allowed_research_scopes_json, participant_metadata_status
        FROM participants
        WHERE participant_id = ?;
        """,
        (participant_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise KeyError(f"Participant not found: {participant_id}")

    return Participant(
        participant_id=row["participant_id"],
        study_id=row["study_id"],
        enrollment_status=row["enrollment_status"],
        consent_status=row["consent_status"],
        consent_version=row["consent_version"],
        enrollment_timestamp=row["enrollment_timestamp"],
        withdrawal_timestamp=row["withdrawal_timestamp"],
        site_id=row["site_id"],
        allowed_research_scopes=json.loads(row["allowed_research_scopes_json"]),
        participant_metadata_status=row["participant_metadata_status"],
    )


def list_participants(conn: sqlite3.Connection, study_id: str | None = None) -> list[Participant]:
    """List participants optionally filtered by study_id."""
    cursor = conn.cursor()
    if study_id:
        cursor.execute(
            """
            SELECT participant_id, study_id, enrollment_status, consent_status,
                   consent_version, enrollment_timestamp, withdrawal_timestamp,
                   site_id, allowed_research_scopes_json, participant_metadata_status
            FROM participants
            WHERE study_id = ?
            ORDER BY enrollment_timestamp;
            """,
            (study_id,),
        )
    else:
        cursor.execute(
            """
            SELECT participant_id, study_id, enrollment_status, consent_status,
                   consent_version, enrollment_timestamp, withdrawal_timestamp,
                   site_id, allowed_research_scopes_json, participant_metadata_status
            FROM participants
            ORDER BY enrollment_timestamp;
            """
        )

    return [
        Participant(
            participant_id=row["participant_id"],
            study_id=row["study_id"],
            enrollment_status=row["enrollment_status"],
            consent_status=row["consent_status"],
            consent_version=row["consent_version"],
            enrollment_timestamp=row["enrollment_timestamp"],
            withdrawal_timestamp=row["withdrawal_timestamp"],
            site_id=row["site_id"],
            allowed_research_scopes=json.loads(row["allowed_research_scopes_json"]),
            participant_metadata_status=row["participant_metadata_status"],
        )
        for row in cursor.fetchall()
    ]


def update_participant_consent_status(
    conn: sqlite3.Connection,
    participant_id: str,
    consent_status: str,
    consent_version: str,
) -> None:
    """Update a participant's consent status and version."""
    if consent_status not in VALID_CONSENT_STATUSES:
        raise ValueError(f"Invalid consent_status: {consent_status!r}")

    # Check existence
    get_participant(conn, participant_id)

    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE participants
        SET consent_status = ?, consent_version = ?
        WHERE participant_id = ?;
        """,
        (consent_status, consent_version, participant_id),
    )


def is_participant_active(
    conn: sqlite3.Connection, participant_id: str, study_id: str | None = None
) -> bool:
    """Check if a participant is currently enrolled and has active consent in the study."""
    try:
        p = get_participant(conn, participant_id)
        if study_id is not None and p.study_id != study_id:
            return False
        return p.enrollment_status in {"enrolled", "active"} and p.consent_status == "consented"
    except KeyError:
        return False
