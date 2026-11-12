"""Versioned M6 ML Model Registry with immutable lifecycle governance and integrity checks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from voxneuro.features.schema import SCHEMA_VERSION
from voxneuro.modeling.domains import TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
from voxneuro.modeling.model_bundle import load_bundle
from voxneuro.study.audit import log_audit_event
from voxneuro.study.auth import UserAccount, require_role
from voxneuro.study.database import transaction
from voxneuro.study.schema import utc_now_iso

LIFECYCLE_STATES: tuple[str, ...] = (
    "TRAINING",
    "TRAINED",
    "RESEARCH_EVALUATED",
    "EXTERNAL_VALIDATION_PENDING",
    "RESEARCH_INFERENCE_APPROVED",
    "REJECTED",
    "RETIRED",
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "TRAINING": {"TRAINED", "REJECTED"},
    "TRAINED": {"RESEARCH_EVALUATED", "REJECTED", "RETIRED"},
    "RESEARCH_EVALUATED": {
        "EXTERNAL_VALIDATION_PENDING",
        "RESEARCH_INFERENCE_APPROVED",
        "REJECTED",
        "RETIRED",
    },
    "EXTERNAL_VALIDATION_PENDING": {"RESEARCH_INFERENCE_APPROVED", "REJECTED", "RETIRED"},
    "RESEARCH_INFERENCE_APPROVED": {"RETIRED", "REJECTED"},
    "REJECTED": {"RETIRED"},
    "RETIRED": set(),
}


@dataclass(frozen=True)
class RegisteredModel:
    """Metadata view of a registered versioned model."""

    model_id: str
    model_version: str
    model_family: str
    feature_schema_version: str
    feature_schema_fingerprint: str
    training_run_id: str | None
    artifact_path: str
    artifact_sha256: str
    lifecycle_state: str
    calibration_status: str
    clinical_claim_status: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _row_to_model(row: sqlite3.Row) -> RegisteredModel:
    return RegisteredModel(
        model_id=row["model_id"],
        model_version=row["model_version"],
        model_family=row["model_family"],
        feature_schema_version=row["feature_schema_version"],
        feature_schema_fingerprint=row["feature_schema_fingerprint"],
        training_run_id=row["training_run_id"],
        artifact_path=row["artifact_path"],
        artifact_sha256=row["artifact_sha256"],
        lifecycle_state=row["lifecycle_state"],
        calibration_status=row["calibration_status"],
        clinical_claim_status=row["clinical_claim_status"],
        metadata=json.loads(row["metadata_json"] or "{}"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def record_training_dataset(
    conn: sqlite3.Connection,
    *,
    dataset_name: str,
    dataset_version: str,
    dataset_sha256: str,
    schema_version: str,
    participant_count: int,
    recording_count: int,
    authorization_status: str,
    notes: str = "",
) -> str:
    """Register or retrieve a training dataset provenance record."""
    row = conn.execute(
        """
        SELECT dataset_record_id FROM training_datasets
        WHERE dataset_name = ? AND dataset_version = ? AND dataset_sha256 = ?;
        """,
        (dataset_name, dataset_version, dataset_sha256),
    ).fetchone()
    if row:
        return row["dataset_record_id"]

    rec_id = f"tds-{uuid.uuid4().hex[:12]}"
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO training_datasets (
                dataset_record_id, dataset_name, dataset_version, dataset_sha256,
                schema_version, participant_count, recording_count, authorization_status,
                notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                rec_id,
                dataset_name,
                dataset_version,
                dataset_sha256,
                schema_version,
                participant_count,
                recording_count,
                authorization_status,
                notes,
                utc_now_iso(),
            ),
        )
    return rec_id


def create_training_run(
    conn: sqlite3.Connection,
    *,
    run_name: str,
    project_code_fingerprint: str,
    dataset_ids: list[str],
    config: dict[str, Any],
    random_seed: int,
    actor: UserAccount | None = None,
) -> str:
    """Create a reproducible ML training run record."""
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    now_iso = utc_now_iso()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO training_runs (
                run_id, run_name, project_code_fingerprint, dataset_ids_json,
                config_json, random_seed, status, created_by_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'RUNNING', ?, ?);
            """,
            (
                run_id,
                run_name,
                project_code_fingerprint,
                json.dumps(dataset_ids),
                json.dumps(config, sort_keys=True),
                random_seed,
                actor.user_id if actor else None,
                now_iso,
            ),
        )
    return run_id


def complete_training_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str = "COMPLETED",
    receipt_sha256: str,
) -> None:
    """Mark a training run complete with its cryptographic receipt hash."""
    with transaction(conn):
        conn.execute(
            """
            UPDATE training_runs
            SET status = ?, completed_at = ?, receipt_sha256 = ?
            WHERE run_id = ?;
            """,
            (status, utc_now_iso(), receipt_sha256, run_id),
        )


def register_model_version(
    conn: sqlite3.Connection,
    *,
    model_version: str,
    model_family: str,
    feature_schema_version: str,
    feature_schema_fingerprint: str,
    training_run_id: str | None,
    artifact_path: Path,
    calibration_status: str = "UNCALIBRATED",
    metadata: dict[str, Any] | None = None,
    initial_state: str = "TRAINED",
    actor_role: str = "system_pipeline",
) -> RegisteredModel:
    """Register an immutable versioned model artifact in the SQLite registry."""
    if initial_state not in {"TRAINING", "TRAINED"}:
        raise ValueError("New model versions must enter the registry in TRAINING or TRAINED state.")
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Model artifact not found: {artifact_path}")
    actual_sha = compute_file_sha256(artifact_path)
    model_id = f"mdl-{uuid.uuid4().hex[:12]}"
    now_iso = utc_now_iso()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO model_versions (
                model_id, model_version, model_family, feature_schema_version,
                feature_schema_fingerprint, training_run_id, artifact_path, artifact_sha256,
                lifecycle_state, calibration_status, clinical_claim_status, metadata_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'UNAPPROVED_RESEARCH_ONLY', ?, ?, ?);
            """,
            (
                model_id,
                model_version,
                model_family,
                feature_schema_version,
                feature_schema_fingerprint,
                training_run_id,
                artifact_path.as_posix(),
                actual_sha,
                initial_state,
                calibration_status,
                json.dumps(metadata or {}, sort_keys=True),
                now_iso,
                now_iso,
            ),
        )
        conn.execute(
            """
            INSERT INTO model_lifecycle_events (
                event_id, model_id, from_state, to_state,
                actor_user_id, actor_role, reason, created_at
            ) VALUES (?, ?, NULL, ?, NULL, ?, ?, ?);
            """,
            (
                f"mle-{uuid.uuid4().hex[:12]}",
                model_id,
                initial_state,
                actor_role,
                f"Initial registration of {model_family} ({model_version})",
                now_iso,
            ),
        )
    return get_model_version(conn, model_id)


def get_model_version(conn: sqlite3.Connection, model_id: str) -> RegisteredModel:
    """Retrieve a registered model by ID."""
    row = conn.execute("SELECT * FROM model_versions WHERE model_id = ?;", (model_id,)).fetchone()
    if not row:
        raise KeyError(f"Registered model not found: {model_id!r}")
    return _row_to_model(row)


def list_model_versions(conn: sqlite3.Connection) -> list[RegisteredModel]:
    """List all registered models ordered newest first."""
    rows = conn.execute("SELECT * FROM model_versions ORDER BY created_at DESC;").fetchall()
    return [_row_to_model(r) for r in rows]


def record_model_evaluation(
    conn: sqlite3.Connection,
    *,
    model_id: str,
    evaluation_scope: str,
    dataset_name: str,
    n_participants: int,
    metrics: dict[str, Any],
) -> str:
    """Store an immutable evaluation snapshot for a registered model."""
    get_model_version(conn, model_id)
    eval_id = f"evl-{uuid.uuid4().hex[:12]}"
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO model_evaluations (
                evaluation_id, model_id, evaluation_scope, dataset_name, n_participants,
                roc_auc, pr_auc, balanced_accuracy, sensitivity, specificity,
                brier_score, ece, metrics_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                eval_id,
                model_id,
                evaluation_scope,
                dataset_name,
                n_participants,
                metrics.get("roc_auc"),
                metrics.get("pr_auc"),
                metrics.get("balanced_accuracy"),
                metrics.get("sensitivity"),
                metrics.get("specificity"),
                metrics.get("brier_score"),
                metrics.get("ece"),
                json.dumps(metrics, sort_keys=True),
                utc_now_iso(),
            ),
        )
    return eval_id


def set_model_domain_approval(
    conn: sqlite3.Connection,
    session_token: str | None,
    *,
    model_id: str,
    domain_id: str,
    approval_state: str,
    evidence_sha256: str = "",
    notes: str = "",
) -> None:
    """Record domain approval/rejection; APPROVED fails closed without trusted SHA-256."""
    actor = require_role(conn, session_token, {"ml_admin", "admin"})
    get_model_version(conn, model_id)
    if approval_state == "APPROVED":
        if not evidence_sha256 or evidence_sha256 not in TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256:
            raise ValueError(
                "Fail-closed governance block: cannot approve domain without a reviewed, "
                "trusted domain validation report hash in TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256."
            )
    now_iso = utc_now_iso()
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO model_domain_approvals (
                approval_id, model_id, domain_id, approval_state, evidence_sha256,
                approved_by_user_id, approved_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_id, domain_id) DO UPDATE SET
                approval_state = excluded.approval_state,
                evidence_sha256 = excluded.evidence_sha256,
                approved_by_user_id = excluded.approved_by_user_id,
                approved_at = excluded.approved_at,
                notes = excluded.notes;
            """,
            (
                f"mda-{uuid.uuid4().hex[:12]}",
                model_id,
                domain_id,
                approval_state,
                evidence_sha256,
                actor.user_id,
                now_iso,
                notes,
            ),
        )
        log_audit_event(
            conn,
            operation_type="MODEL_DOMAIN_APPROVAL_UPDATED",
            entity_type="model_version",
            entity_id=model_id,
            actor_role=actor.role,
            details={"domain_id": domain_id, "approval_state": approval_state},
        )


def transition_model_state(
    conn: sqlite3.Connection,
    *,
    model_id: str,
    to_state: str,
    reason: str,
    session_token: str | None = None,
    system_internal: bool = False,
) -> RegisteredModel:
    """Enforce allowed lifecycle transitions, RBAC, and fail-closed inference approval rules."""
    model = get_model_version(conn, model_id)
    if to_state not in LIFECYCLE_STATES:
        raise ValueError(f"Unknown lifecycle state: {to_state!r}")
    allowed = ALLOWED_TRANSITIONS.get(model.lifecycle_state, set())
    if to_state not in allowed:
        raise ValueError(
            f"Illegal model lifecycle transition {model.lifecycle_state!r} -> {to_state!r}."
        )

    actor_user_id: str | None = None
    actor_role = "system_pipeline"
    if not system_internal or to_state in {"RESEARCH_INFERENCE_APPROVED", "REJECTED", "RETIRED"}:
        actor = require_role(conn, session_token, {"ml_admin", "admin"})
        actor_user_id = actor.user_id
        actor_role = actor.role

    artifact_file = Path(model.artifact_path)
    if to_state in {
        "RESEARCH_EVALUATED",
        "EXTERNAL_VALIDATION_PENDING",
        "RESEARCH_INFERENCE_APPROVED",
    }:
        if not artifact_file.is_file():
            raise FileNotFoundError(f"Model artifact missing at {artifact_file}")
        actual_sha = compute_file_sha256(artifact_file)
        if actual_sha != model.artifact_sha256:
            raise ValueError("Model artifact checksum mismatch; transition blocked.")

    if to_state == "RESEARCH_INFERENCE_APPROVED":
        eval_cnt = conn.execute(
            "SELECT COUNT(*) AS cnt FROM model_evaluations WHERE model_id = ?;", (model_id,)
        ).fetchone()["cnt"]
        if int(eval_cnt) == 0:
            raise ValueError("Cannot approve model for inference without recorded evaluations.")
        approved_domains = conn.execute(
            """
            SELECT domain_id, evidence_sha256 FROM model_domain_approvals
            WHERE model_id = ? AND approval_state = 'APPROVED';
            """,
            (model_id,),
        ).fetchall()
        if not approved_domains or not any(
            row["evidence_sha256"] in TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
            for row in approved_domains
        ):
            raise ValueError(
                "Fail-closed governance block: RESEARCH_INFERENCE_APPROVED requires at least "
                "one domain with a verified report hash in TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256."
            )

    now_iso = utc_now_iso()
    with transaction(conn):
        conn.execute(
            "UPDATE model_versions SET lifecycle_state = ?, updated_at = ? WHERE model_id = ?;",
            (to_state, now_iso, model_id),
        )
        conn.execute(
            """
            INSERT INTO model_lifecycle_events (
                event_id, model_id, from_state, to_state,
                actor_user_id, actor_role, reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                f"mle-{uuid.uuid4().hex[:12]}",
                model_id,
                model.lifecycle_state,
                to_state,
                actor_user_id,
                actor_role,
                reason,
                now_iso,
            ),
        )
        log_audit_event(
            conn,
            operation_type="MODEL_LIFECYCLE_TRANSITION",
            entity_type="model_version",
            entity_id=model_id,
            actor_role=actor_role,
            details={"from_state": model.lifecycle_state, "to_state": to_state, "reason": reason},
        )
    return get_model_version(conn, model_id)


def verify_and_load_registered_bundle(
    conn: sqlite3.Connection,
    model_id: str,
    *,
    required_domain_id: str,
    expected_schema_version: str = SCHEMA_VERSION,
) -> tuple[RegisteredModel, dict[str, Any]]:
    """Verify approval state, schema, domain authorization, and SHA-256 checksum before loading."""
    model = get_model_version(conn, model_id)
    if model.lifecycle_state != "RESEARCH_INFERENCE_APPROVED":
        raise ValueError(
            f"Model {model_id!r} is in state {model.lifecycle_state!r}, "
            "not RESEARCH_INFERENCE_APPROVED."
        )
    if model.feature_schema_version != expected_schema_version:
        raise ValueError(
            f"Model schema {model.feature_schema_version!r} mismatches "
            f"expected {expected_schema_version!r}."
        )
    domain_row = conn.execute(
        """
        SELECT approval_state, evidence_sha256 FROM model_domain_approvals
        WHERE model_id = ? AND domain_id = ?;
        """,
        (model_id, required_domain_id),
    ).fetchone()
    if (
        not domain_row
        or domain_row["approval_state"] != "APPROVED"
        or domain_row["evidence_sha256"] not in TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
    ):
        raise ValueError(
            f"Model {model_id!r} is not approved for acquisition domain {required_domain_id!r}."
        )
    artifact_path = Path(model.artifact_path)
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Registered model artifact missing on disk: {artifact_path}")
    actual_sha = compute_file_sha256(artifact_path)
    if actual_sha != model.artifact_sha256:
        raise ValueError(
            f"Checksum tampering detected for model {model_id!r}: "
            f"{actual_sha} != {model.artifact_sha256}."
        )
    bundle = load_bundle(artifact_path)
    return model, bundle
