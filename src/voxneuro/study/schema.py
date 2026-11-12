"""Data structures and schemas for Milestone 5 research study operations."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

VALID_STUDY_STATUSES = frozenset({"draft", "active", "paused", "completed", "archived"})
VALID_ENROLLMENT_STATUSES = frozenset({"enrolled", "active", "withdrawn", "completed"})
VALID_CONSENT_STATUSES = frozenset({"consented", "withdrawn", "pending", "revoked"})
VALID_DUA_STATES = frozenset(
    {"ACTIVE", "PENDING", "NOT_REQUIRED", "RESTRICTED", "DENIED", "EXPIRED"}
)
VALID_DUA_APPROVAL_STATES = frozenset({"APPROVED", "PENDING", "DENIED", "EXPIRED"})
VALID_DUA_VERIFICATION_STATUSES = frozenset(
    {"UNVERIFIED", "DOCUMENT_AUTHENTICATED", "REVOKED", "EXPIRED"}
)
VALID_TASK_STATUSES = frozenset(
    {
        "NOT_STARTED",
        "RECEIVED",
        "QUALITY_CHECKED",
        "ACCEPTED",
        "ACCEPTED_TRANSIENT_PROCESSED",
        "REJECTED",
        "PROCESSING_FAILED",
        "FEATURES_EXTRACTED",
        "REQUIRES_REVIEW",
    }
)
VALID_SESSION_STATUSES = frozenset(
    {"SCHEDULED", "IN_PROGRESS", "COMPLETED", "QUALITY_FAILED", "RESTRICTED_WITHDRAWN"}
)


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


def generate_pseudonymous_id(prefix: str = "PT") -> str:
    """Generate a random pseudonymous identifier with zero PII."""
    random_token = uuid.uuid4().hex[:12].upper()
    return f"{prefix}-{random_token}"


@dataclass(frozen=True)
class ProtocolDefinition:
    """Immutable protocol specification defining visits and required speech tasks."""

    protocol_id: str
    protocol_version: str
    tasks: list[str] = field(
        default_factory=lambda: ["sustained_vowel", "ddk", "connected_speech", "vowel_space"]
    )
    visits_expected: int = 1
    minimum_interval_days: int = 0
    instructions: str = ""
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Study:
    """Research study entity governing participant cohorts, protocols, and data policies."""

    study_id: str
    study_name: str
    study_description: str
    protocol_id: str
    protocol_version: str
    study_status: str = "draft"
    research_site_id: str = "primary_site"
    dataset_id: str = "default_study_dataset"
    dataset_version: str = "v1"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    study_owner_role: str = "Principal Investigator"
    consent_requirements: list[str] = field(
        default_factory=lambda: ["voice_recording", "feature_retention"]
    )
    data_retention_policy_id: str = "standard_research_retention"
    analysis_configuration_id: str = "voxneuro_default_v4"

    def __post_init__(self) -> None:
        if self.study_status not in VALID_STUDY_STATUSES:
            valid_list = sorted(VALID_STUDY_STATUSES)
            raise ValueError(
                f"Invalid study_status {self.study_status!r}. Must be one of {valid_list}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Participant:
    """Pseudonymous research participant with zero direct personal identifiers."""

    participant_id: str
    study_id: str
    enrollment_status: str = "enrolled"
    consent_status: str = "pending"
    consent_version: str = "none"
    enrollment_timestamp: str = field(default_factory=utc_now_iso)
    withdrawal_timestamp: str | None = None
    site_id: str = "primary_site"
    allowed_research_scopes: list[str] = field(
        default_factory=lambda: ["voice_analysis", "longitudinal_monitoring"]
    )
    participant_metadata_status: str = "PSEUDONYMOUS_VERIFIED"

    def __post_init__(self) -> None:
        if self.enrollment_status not in VALID_ENROLLMENT_STATUSES:
            raise ValueError(f"Invalid enrollment_status {self.enrollment_status!r}")
        if self.consent_status not in VALID_CONSENT_STATUSES:
            raise ValueError(f"Invalid consent_status {self.consent_status!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConsentRecord:
    """Cryptographically trackable research consent state."""

    consent_record_id: str
    participant_id: str
    study_id: str
    consent_form_version: str
    consent_date: str
    scope_of_permission: list[str]
    permitted_recording_tasks: list[str] = field(
        default_factory=lambda: ["sustained_vowel", "ddk", "connected_speech", "vowel_space"]
    )
    permitted_research_uses: list[str] = field(
        default_factory=lambda: ["biomarker_research", "longitudinal_analysis"]
    )
    permission_to_retain_derived_features: bool = False
    permission_to_retain_audio: bool = False
    withdrawal_status: bool = False
    revocation_date: str | None = None
    source_document_reference: str = "IRB_APPROVED_CONSENT_DOCUMENT_ON_FILE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DatasetAccessRecord:
    """Dataset governance and Data Use Agreement (DUA) record."""

    dataset_id: str
    dataset_version: str
    dataset_owner: str
    license_type: str
    access_approval_state: str = "PENDING"
    dua_state: str = "PENDING"
    permitted_tasks: list[str] = field(default_factory=lambda: ["sustained_vowel"])
    permitted_data_processing_operations: list[str] = field(
        default_factory=lambda: ["feature_extraction", "statistical_audit"]
    )
    storage_restrictions: str = "local_ephemeral_processing_only"
    publication_restrictions: str = "aggregate_only_no_raw_audio"
    expiration_date: str | None = None
    source_documentation: str = "DUA_PENDING_REVIEW"
    dua_document_fingerprint: str = ""
    authorization_ref: str = ""
    source_id: str = ""
    authorization_registry_id: str = ""
    authorization_registry_version: str = ""
    issuing_authority: str = ""
    dua_source_artifact_reference: str = ""
    dua_verification_status: str = "UNVERIFIED"

    def __post_init__(self) -> None:
        if self.access_approval_state not in VALID_DUA_APPROVAL_STATES:
            raise ValueError(f"Invalid access_approval_state: {self.access_approval_state!r}")
        if self.dua_state not in VALID_DUA_STATES:
            raise ValueError(f"Invalid dua_state: {self.dua_state!r}")
        if self.dua_verification_status not in VALID_DUA_VERIFICATION_STATUSES:
            raise ValueError(f"Invalid dua_verification_status: {self.dua_verification_status!r}")

    def is_authorized(self) -> bool:
        return self.access_approval_state == "APPROVED" and self.dua_state in {
            "ACTIVE",
            "NOT_REQUIRED",
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskRecording:
    """Individual speech task recording within a session."""

    task_id: str
    session_id: str
    task_type: str
    task_status: str = "NOT_STARTED"
    audio_duration_seconds: float = 0.0
    quality_passed: bool = False
    rejection_reason: str | None = None
    feature_schema_version: str | None = None
    feature_schema_fingerprint: str | None = None
    derived_feature_count: int = 0
    qc_metrics: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if self.task_status not in VALID_TASK_STATUSES:
            raise ValueError(f"Invalid task_status: {self.task_status!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchSession:
    """A research visit containing multiple task recordings."""

    session_id: str
    study_id: str
    protocol_version: str
    participant_id: str
    visit_index: int = 1
    visit_label: str = "Baseline"
    acquisition_domain_id: str = "uams_telephone"
    capture_origin: str = "controlled_research_session"
    recording_timestamp: str = field(default_factory=utc_now_iso)
    consent_reference: str = "default_consent"
    device_metadata: dict[str, Any] = field(default_factory=dict)
    task_completion_states: dict[str, str] = field(default_factory=dict)
    qc_results: dict[str, Any] = field(default_factory=dict)
    processing_receipt_sha256: str | None = None
    missing_task_reasons: dict[str, str] = field(default_factory=dict)
    overall_session_status: str = "SCHEDULED"

    def __post_init__(self) -> None:
        if self.overall_session_status not in VALID_SESSION_STATUSES:
            raise ValueError(f"Invalid overall_session_status: {self.overall_session_status!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProcessingRunReceipt:
    """Immutable provenance receipt for reproducible research processing."""

    run_id: str
    study_id: str
    session_ids: list[str]
    processing_timestamp: str
    application_version: str
    project_code_fingerprint: str
    python_version: str
    dependency_lockfile_fingerprint: str
    task_schema_fingerprints: dict[str, str]
    audio_config_fingerprint: str
    feature_config_fingerprint: str
    domain_metadata_fingerprint: str
    input_file_checksum: str | None
    feature_table_checksum: str
    processing_status: str
    exclusion_summary: dict[str, int]
    error_summary: dict[str, int]
    output_artifact_checksums: dict[str, str]
    receipt_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compute_sha256(self) -> str:
        d = asdict(self)
        d["receipt_sha256"] = ""
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
