"""Participant withdrawal, data retention policy enforcement, and tombstone auditing."""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import uuid
from typing import Any

from voxneuro.study.audit import log_audit_event
from voxneuro.study.database import transaction
from voxneuro.study.participant import get_participant
from voxneuro.study.schema import utc_now_iso


def compute_withdrawal_tombstone_hash(
    participant_id: str,
    key: bytes | str | None = None,
    key_id: str = "voxneuro-key-v1",
) -> tuple[str, str]:
    """Compute privacy-preserving HMAC-SHA256 tombstone hash using external key material."""
    active_key = key or os.environ.get("VOXNEURO_HMAC_KEY")
    if not active_key:
        raise KeyError(
            "Cannot generate privacy-preserving withdrawal tombstone: external HMAC key material "
            "is unavailable. Provide key parameter or configure VOXNEURO_HMAC_KEY."
        )
    key_bytes = active_key.encode("utf-8") if isinstance(active_key, str) else bytes(active_key)
    norm_id = participant_id.strip().casefold()
    tombstone_hash = hmac.new(key_bytes, norm_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return tombstone_hash, key_id


def withdraw_participant(
    conn: sqlite3.Connection,
    participant_id: str,
    key: bytes | str | None = None,
    key_id: str = "voxneuro-key-v1",
    deletion_reason: str = "Participant requested withdrawal of consent",
    policy_reference: str = "IRB_STANDARD_DATA_DELETION_POLICY",
    actor_role: str = "data_protection_officer",
    actor_session_token: str | None = None,
) -> dict[str, Any]:
    """Execute complete atomic participant withdrawal workflow and purge features.

    STRICT GOVERNANCE INVARIANT:
    - Blocks all future processing for the participant immediately.
    - Atomically updates participant enrollment and consent statuses to 'withdrawn'.
    - Restricts existing sessions to 'RESTRICTED_WITHDRAWN'.
    - Deletes all derived features and prediction records for the participant.
    - Deactivates linked user accounts and revokes active sessions.
    - Generates an irreversible keyed HMAC-SHA256 tombstone with external key material.
    - Logs a privacy-safe audit event without exposing participant personal identity.
    - Rolls back entire transaction on any failure.
    """
    if actor_session_token:
        from voxneuro.study.auth import require_role

        actor = require_role(
            conn, actor_session_token, {"admin", "researcher", "data_protection_officer"}
        )
        actor_role = actor.role

    participant = get_participant(conn, participant_id)
    if participant.enrollment_status == "withdrawn":
        return {
            "status": "ALREADY_WITHDRAWN",
            "participant_id": participant_id,
            "message": "Participant has already been withdrawn and records removed.",
        }

    # Verify key material is available BEFORE starting database transaction
    tombstone_hash, used_key_id = compute_withdrawal_tombstone_hash(
        participant_id, key=key, key_id=key_id
    )

    now_iso = utc_now_iso()
    tombstone_id = f"tomb-{uuid.uuid4().hex[:12]}"

    # Transactional execution: all database changes are committed atomically
    with transaction(conn):
        cursor = conn.cursor()

        # 1. Count and delete derived features and any retained prediction records
        cursor.execute(
            "SELECT COUNT(*) as feat_count FROM derived_features WHERE participant_id = ?;",
            (participant_id,),
        )
        feat_count = cursor.fetchone()["feat_count"]
        cursor.execute("DELETE FROM derived_features WHERE participant_id = ?;", (participant_id,))

        pred_count = 0
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prediction_records';"
        )
        if cursor.fetchone():
            cursor.execute(
                "SELECT COUNT(*) as pred_count FROM prediction_records WHERE participant_id = ?;",
                (participant_id,),
            )
            pred_count = cursor.fetchone()["pred_count"]
            cursor.execute(
                "DELETE FROM prediction_records WHERE participant_id = ?;",
                (participant_id,),
            )

        # 2. Mark sessions as RESTRICTED_WITHDRAWN
        cursor.execute(
            """
            UPDATE sessions
            SET overall_session_status = 'RESTRICTED_WITHDRAWN'
            WHERE participant_id = ?;
            """,
            (participant_id,),
        )
        cursor.execute(
            "SELECT COUNT(*) as session_count FROM sessions WHERE participant_id = ?;",
            (participant_id,),
        )
        session_count = cursor.fetchone()["session_count"]

        # 3. Update participant enrollment and consent statuses to withdrawn
        cursor.execute(
            """
            UPDATE participants
            SET enrollment_status = 'withdrawn', consent_status = 'withdrawn',
                withdrawal_timestamp = ?, participant_metadata_status = 'WITHDRAWN_AND_RESTRICTED'
            WHERE participant_id = ?;
            """,
            (now_iso, participant_id),
        )

        # 4. Mark all consent records for this participant as withdrawn
        cursor.execute(
            """
            UPDATE consents
            SET withdrawal_status = 1, revocation_date = ?
            WHERE participant_id = ?;
            """,
            (now_iso, participant_id),
        )

        # 5. Deactivate linked user accounts and revoke all active sessions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if cursor.fetchone():
            cursor.execute(
                "SELECT user_id FROM users WHERE participant_id = ?;",
                (participant_id,),
            )
            linked_uids = [r["user_id"] for r in cursor.fetchall()]
            for uid in linked_uids:
                cursor.execute(
                    "UPDATE users SET is_active = 0, updated_at = ? WHERE user_id = ?;",
                    (now_iso, uid),
                )
                cursor.execute(
                    "UPDATE user_sessions SET revoked_at = ? "
                    "WHERE user_id = ? AND revoked_at IS NULL;",
                    (now_iso, uid),
                )

        # 6. Insert irreversible cryptographic tombstone with non-secret key_id
        cursor.execute(
            """
            INSERT INTO tombstones (
                tombstone_id, timestamp_utc, participant_pseudonym_hash,
                study_id, deletion_reason, records_deleted_count, policy_reference, key_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                tombstone_id,
                now_iso,
                tombstone_hash,
                participant.study_id,
                deletion_reason,
                feat_count,
                policy_reference,
                used_key_id,
            ),
        )

        # 7. Record privacy-safe audit event
        log_audit_event(
            conn,
            operation_type="PARTICIPANT_WITHDRAWAL_EXECUTED",
            entity_type="participant",
            entity_id=tombstone_id,
            actor_role=actor_role,
            details={
                "tombstone_id": tombstone_id,
                "study_id": participant.study_id,
                "derived_features_deleted": feat_count,
                "prediction_records_deleted": pred_count,
                "sessions_restricted": session_count,
                "key_id": used_key_id,
                "policy_reference": policy_reference,
            },
        )

    return {
        "status": "WITHDRAWAL_COMPLETED",
        "tombstone_id": tombstone_id,
        "study_id": participant.study_id,
        "derived_features_deleted": feat_count,
        "prediction_records_deleted": pred_count,
        "sessions_restricted": session_count,
        "key_id": used_key_id,
        "timestamp_utc": now_iso,
        "policy_reference": policy_reference,
    }


def list_tombstones(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Query tombstone records for compliance verification."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tombstone_id, timestamp_utc, participant_pseudonym_hash,
               study_id, deletion_reason, records_deleted_count, policy_reference, key_id
        FROM tombstones
        ORDER BY timestamp_utc DESC;
        """
    )
    return [
        {
            "tombstone_id": row["tombstone_id"],
            "timestamp_utc": row["timestamp_utc"],
            "participant_pseudonym_hash": row["participant_pseudonym_hash"],
            "study_id": row["study_id"],
            "deletion_reason": row["deletion_reason"],
            "records_deleted_count": row["records_deleted_count"],
            "policy_reference": row["policy_reference"],
            "key_id": row["key_id"],
        }
        for row in cursor.fetchall()
    ]
