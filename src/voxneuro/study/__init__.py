"""VoxNeuro Milestone 5:
Research Study Operations, Data Governance, and Longitudinal Cohort Management.
"""

from __future__ import annotations

from voxneuro.study.audit import list_audit_events, log_audit_event, record_processing_run
from voxneuro.study.consent import (
    get_active_consent_for_participant,
    get_consent,
    get_dataset_access,
    list_dataset_access,
    record_consent,
    register_dataset_access,
    verify_dataset_authorization_for_task,
    verify_participant_consent_for_task,
)
from voxneuro.study.database import (
    check_schema_integrity,
    get_connection,
    run_migrations,
    transaction,
)
from voxneuro.study.longitudinal import calculate_longitudinal_feature_changes
from voxneuro.study.participant import (
    get_participant,
    is_participant_active,
    list_participants,
    register_participant,
    update_participant_consent_status,
)
from voxneuro.study.qc import (
    apply_small_cell_suppression,
    calculate_cohort_attrition,
    calculate_cohort_qc_metrics,
)
from voxneuro.study.registry import (
    create_protocol,
    create_study,
    get_protocol,
    get_study,
    list_protocols,
    list_studies,
    update_study_protocol,
    update_study_status,
)
from voxneuro.study.reporting import (
    export_report_to_csv,
    generate_cohort_attrition_report,
    generate_consent_and_dua_report,
    generate_data_provenance_run_report,
    generate_longitudinal_descriptive_report,
    generate_session_completion_report,
    generate_study_overview_report,
    generate_task_qc_report,
)
from voxneuro.study.schema import (
    ConsentRecord,
    DatasetAccessRecord,
    Participant,
    ProcessingRunReceipt,
    ProtocolDefinition,
    ResearchSession,
    Study,
    TaskRecording,
    generate_pseudonymous_id,
)
from voxneuro.study.session import (
    create_session,
    get_derived_features_for_session,
    get_session,
    get_task_recordings_for_session,
    ingest_session_multitask_audio,
    list_sessions,
    record_task_recording,
    update_session_status,
)
from voxneuro.study.withdrawal import list_tombstones, withdraw_participant

__all__ = [
    "ConsentRecord",
    "DatasetAccessRecord",
    "Participant",
    "ProcessingRunReceipt",
    "ProtocolDefinition",
    "ResearchSession",
    "Study",
    "TaskRecording",
    "apply_small_cell_suppression",
    "calculate_cohort_attrition",
    "calculate_cohort_qc_metrics",
    "calculate_longitudinal_feature_changes",
    "check_schema_integrity",
    "create_protocol",
    "create_session",
    "create_study",
    "export_report_to_csv",
    "generate_cohort_attrition_report",
    "generate_consent_and_dua_report",
    "generate_data_provenance_run_report",
    "generate_longitudinal_descriptive_report",
    "generate_pseudonymous_id",
    "generate_session_completion_report",
    "generate_study_overview_report",
    "generate_task_qc_report",
    "get_active_consent_for_participant",
    "get_connection",
    "get_consent",
    "get_dataset_access",
    "get_derived_features_for_session",
    "get_participant",
    "get_protocol",
    "get_session",
    "get_study",
    "get_task_recordings_for_session",
    "ingest_session_multitask_audio",
    "is_participant_active",
    "list_audit_events",
    "list_dataset_access",
    "list_participants",
    "list_protocols",
    "list_sessions",
    "list_studies",
    "list_tombstones",
    "log_audit_event",
    "record_consent",
    "record_processing_run",
    "record_task_recording",
    "register_dataset_access",
    "register_participant",
    "run_migrations",
    "transaction",
    "update_participant_consent_status",
    "update_study_protocol",
    "update_study_status",
    "update_session_status",
    "verify_dataset_authorization_for_task",
    "verify_participant_consent_for_task",
    "withdraw_participant",
]
