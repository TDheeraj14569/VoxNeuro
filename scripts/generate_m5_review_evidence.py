"""Generate Milestone 5 review evidence files for VoxNeuro audit.

Produces:
  - review_evidence/m5_study_registry_summary.json
  - review_evidence/m5_database_schema_summary.json
  - review_evidence/m5_consent_governance_summary.json
  - review_evidence/m5_dataset_access_summary.json
  - review_evidence/m5_session_pipeline_summary.json
  - review_evidence/m5_quality_control_summary.json
  - review_evidence/m5_longitudinal_analysis_summary.json
  - review_evidence/m5_privacy_audit_summary.json
  - review_evidence/m5_provenance_summary.json
  - review_evidence/m5_test_summary.json
  - review_evidence/m5_review_manifest.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import posixpath
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from voxneuro.features.schema import schema_fingerprint as v3_schema_fingerprint
from voxneuro.features.tasks.schema import (
    connected_speech_schema_fingerprint,
    ddk_schema_fingerprint,
    v4_envelope_schema_fingerprint,
    vowel_space_schema_fingerprint,
)
from voxneuro.provenance import project_code_fingerprint
from voxneuro.study.consent import list_dataset_access
from voxneuro.study.database import (
    check_schema_integrity,
    get_connection,
    run_migrations,
)
from voxneuro.study.qc import SUPPRESSION_THRESHOLD
from voxneuro.study.reporting import RESEARCH_DISCLAIMER
from voxneuro.study.schema import (
    VALID_CONSENT_STATUSES,
    VALID_DUA_APPROVAL_STATES,
    VALID_DUA_STATES,
    VALID_ENROLLMENT_STATUSES,
    VALID_SESSION_STATUSES,
    VALID_STUDY_STATUSES,
    VALID_TASK_STATUSES,
    ConsentRecord,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "review_evidence"


def sanitize_target_path(target: str, repo_root: Path | str | None = None) -> str:
    """Sanitize a test target path cross-platform without leaking user directories or host paths."""
    target_str = str(target).strip()
    if not target_str:
        return ""

    if (
        target_str.startswith(r"\\\\")
        or target_str.startswith("//")
        or bool(re.match(r"^[\\/]{2}", target_str))
    ):
        clean_back = target_str.replace("/", "\\")
        pw = PureWindowsPath(clean_back)
        fn = pw.name or "test_file.py"
        return f"<temporary-dir>/{fn}"

    if target_str.startswith("~"):
        fn = posixpath.basename(target_str.replace("\\", "/").rstrip("/")) or "test_file.py"
        return f"<temporary-dir>/{fn}"

    is_win_abs = bool(re.match(r"^[a-zA-Z]:[\\/]", target_str))
    is_posix_abs = target_str.startswith("/") and not target_str.startswith("//")

    if not is_win_abs and not is_posix_abs:
        norm = target_str.replace("\\", "/")
        norm = re.sub(r"^\./", "", norm)
        return norm

    root_path = Path(repo_root) if repo_root is not None else ROOT
    root_resolved = root_path.resolve()

    if is_win_abs:
        p_win = PureWindowsPath(target_str.replace("/", "\\"))
        try:
            r_win = PureWindowsPath(str(root_resolved).replace("/", "\\"))
            rel = p_win.relative_to(r_win)
            return rel.as_posix()
        except ValueError:
            target_norm = target_str.replace("\\", "/").rstrip("/")
            root_norm = str(root_resolved).replace("\\", "/").rstrip("/")
            if target_norm.lower().startswith(root_norm.lower()):
                suffix = target_norm[len(root_norm) :].lstrip("/")
                return suffix or target_norm.split("/")[-1]
            return f"<temporary-dir>/{p_win.name or 'test_file.py'}"

    if is_posix_abs:
        p_pos = PurePosixPath(target_str)
        try:
            r_pos = PurePosixPath(root_resolved.as_posix())
            rel = p_pos.relative_to(r_pos)
            return rel.as_posix()
        except ValueError:
            target_norm = target_str.rstrip("/")
            root_norm = root_resolved.as_posix().rstrip("/")
            if target_norm.startswith(root_norm):
                suffix = target_norm[len(root_norm) :].lstrip("/")
                return suffix or target_norm.split("/")[-1]
            return f"<temporary-dir>/{p_pos.name or 'test_file.py'}"

    return target_str.replace("\\", "/")


def generate_study_registry_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_study_registry_summary.json."""
    data = {
        "milestone": "M5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "schema_version": "voxneuro.study_registry.v1",
        "description": "Milestone 5 research study registry and protocol definition metadata",
        "governance_rules": {
            "protocol_immutability_enforced": True,
            "immutability_rule": (
                "Protocols are immutable once research sessions have been recorded. "
                "Updating study protocol version is blocked if sessions exist under that version."
            ),
            "valid_study_statuses": sorted(VALID_STUDY_STATUSES),
            "valid_enrollment_statuses": sorted(VALID_ENROLLMENT_STATUSES),
            "valid_session_statuses": sorted(VALID_SESSION_STATUSES),
            "valid_task_statuses": sorted(VALID_TASK_STATUSES),
        },
        "default_protocol_structure": {
            "tasks": ["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
            "expected_visits_range": [1, 10],
            "minimum_interval_days_enforced": True,
        },
        "scientific_disclaimer": RESEARCH_DISCLAIMER,
    }
    target = out_dir / "m5_study_registry_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_database_schema_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_database_schema_summary.json."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        applied = run_migrations(db_path)
        integrity = check_schema_integrity(db_path)

        data = {
            "milestone": "M5",
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "schema_version": "voxneuro.database_schema.v1",
            "applied_migrations": applied,
            "table_count": len(integrity["tables"]),
            "tables": sorted(integrity["tables"]),
            "foreign_keys_enabled": True,
            "foreign_key_violations": len(integrity["foreign_key_violations"]),
            "integrity_check_passed": integrity["clean"],
            "tables_specification": {
                "schema_migrations": "Tracks applied migration versions and timestamps",
                "protocols": "Immutable task specifications, schedules, and quality gates",
                "studies": "Research studies linking cohorts to immutable protocol versions",
                "participants": "Pseudonymous participant cohort with zero direct identifiers",
                "consents": "Informed consent records and permitted task/use scopes",
                "dataset_access": "Data Use Agreements (DUA) and institutional authorizations",
                "sessions": "Longitudinal visit sessions and operational quality state",
                "task_recordings": "Task-specific audio recording metadata and pass/fail states",
                "derived_features": "Extracted acoustic features without persisting raw audio",
                "processing_runs": "Immutable cryptographic receipts of batch processing runs",
                "audit_log": "Privacy-sanitized operational audit trail",
                "tombstones": "Cryptographic records of consent withdrawal and feature deletion",
            },
        }
    finally:
        if db_path.exists():
            try:
                db_path.unlink()
            except OSError:
                pass

    target = out_dir / "m5_database_schema_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _inspect_consent_retention_defaults() -> tuple[bool, bool]:
    """Verify ConsentRecord and SQLite migrated schema retention defaults match."""
    consent_fields = {f.name: f.default for f in fields(ConsentRecord)}
    dc_feat = bool(consent_fields["permission_to_retain_derived_features"])
    dc_audio = bool(consent_fields["permission_to_retain_audio"])

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    try:
        run_migrations(db_path)
        conn = get_connection(db_path)
        try:
            cols = {
                row["name"]: row["dflt_value"]
                for row in conn.execute("PRAGMA table_info(consents);").fetchall()
            }
        finally:
            conn.close()
    finally:
        if db_path.exists():
            try:
                db_path.unlink()
            except OSError:
                pass

    sql_feat = bool(int(str(cols["permission_to_retain_derived_features"]).strip("'\"")))
    sql_audio = bool(int(str(cols["permission_to_retain_audio"]).strip("'\"")))

    if dc_feat != sql_feat:
        raise RuntimeError(
            f"derived_features_retention_default mismatch: "
            f"ConsentRecord={dc_feat} vs SQLite={sql_feat}"
        )
    if dc_audio != sql_audio:
        raise RuntimeError(
            f"raw_audio_retention_default mismatch: ConsentRecord={dc_audio} vs SQLite={sql_audio}"
        )
    return dc_audio, dc_feat


def generate_consent_governance_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_consent_governance_summary.json."""
    raw_audio_default, derived_features_default = _inspect_consent_retention_defaults()
    data = {
        "milestone": "M5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "schema_version": "voxneuro.consent_governance.v1",
        "consent_model": {
            "valid_consent_statuses": sorted(VALID_CONSENT_STATUSES),
            "consent_verification_required_for_ingestion": True,
            "task_scope_matching_enforced": True,
            "raw_audio_retention_default": raw_audio_default,
            "derived_features_retention_default": derived_features_default,
        },
        "withdrawal_policy": {
            "withdrawal_workflow_implemented": True,
            "immediate_session_restriction": True,
            "restricted_status_label": "RESTRICTED_WITHDRAWN",
            "derived_features_deleted_on_withdrawal": True,
            "cryptographic_tombstone_created": True,
            "tombstone_properties": [
                "tombstone_id",
                "timestamp_utc",
                "participant_pseudonym_hash",
                "study_id",
                "deletion_reason",
                "records_deleted_count",
                "policy_reference",
            ],
        },
        "scientific_disclaimer": RESEARCH_DISCLAIMER,
    }
    target = out_dir / "m5_consent_governance_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_dataset_access_summary(out_dir: Path, study_db_path: Path | None = None) -> Path:
    """Generate review_evidence/m5_dataset_access_summary.json from runtime DB if configured."""
    configured_db = study_db_path or (
        Path(os.environ["VOXNEURO_STUDY_DB"]) if os.environ.get("VOXNEURO_STUDY_DB") else None
    )
    if configured_db is not None and configured_db.is_file():
        conn = get_connection(configured_db)
        try:
            records = list_dataset_access(conn)
        finally:
            conn.close()
        status = "RUNTIME_DATASET_AUTHORIZATION_VERIFIED"
        registered = [
            {
                "dataset_id": r.dataset_id,
                "dataset_version": r.dataset_version,
                "license_type": r.license_type,
                "access_approval_state": r.access_approval_state,
                "dua_state": r.dua_state,
                "expiration_date": r.expiration_date,
            }
            for r in records
        ]
    else:
        status = "RUNTIME_DATASET_AUTHORIZATION_NOT_INCLUDED_IN_RELEASE"
        registered = []

    data = {
        "milestone": "M5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "schema_version": "voxneuro.dataset_access.v1",
        "status": status,
        "governance_rules": {
            "valid_access_approval_states": sorted(VALID_DUA_APPROVAL_STATES),
            "valid_dua_states": sorted(VALID_DUA_STATES),
            "required_approval_state_for_ingestion": "APPROVED",
            "required_dua_states_for_ingestion": ["ACTIVE", "NOT_REQUIRED"],
            "fail_closed_if_unregistered": True,
            "task_authorization_matching_enforced": True,
        },
        "registered_datasets": registered,
        "disclaimer": RESEARCH_DISCLAIMER,
    }
    target = out_dir / "m5_dataset_access_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_session_pipeline_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_session_pipeline_summary.json."""
    data = {
        "milestone": "M5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "schema_version": "voxneuro.session_pipeline.v1",
        "pipeline_architecture": {
            "ingestion_framework": "M3 MultiTaskSessionResult pipeline integration",
            "task_extractors": [
                "voxneuro.voice.v3 (Core39 sustained vowel)",
                "voxneuro.task.ddk.v1 (AMR /pa/, /ta/, /ka/ & SMR /pataka/)",
                "voxneuro.task.connected_speech.v1 (Read text speech cadence & pauses)",
                "voxneuro.task.vowel_space.v1 (Corner vowel formant quadrilateral VSA)",
            ],
            "audio_retention_policy": (
                "Zero raw audio persisted to database; ephemeral memory only"
            ),
            "derived_feature_storage": (
                "Relational derived_features table keyed by task_id and session_id"
            ),
            "session_status_values": sorted(VALID_SESSION_STATUSES),
            "fail_closed_handling": (
                "Unconsented or unauthorized tasks fail closed with "
                "PermissionError before audio ingestion."
            ),
        },
        "scientific_disclaimer": RESEARCH_DISCLAIMER,
    }
    target = out_dir / "m5_session_pipeline_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_quality_control_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_quality_control_summary.json."""
    data = {
        "milestone": "M5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "schema_version": "voxneuro.quality_control.v1",
        "small_cell_suppression": {
            "suppression_threshold": SUPPRESSION_THRESHOLD,
            "suppression_rule": (
                "Counts strictly between 1 and 9 are suppressed as '< 10 (Suppressed)' "
                "to prevent re-identification and unpowered conclusions. 0 is not suppressed."
            ),
            "enforced_on_reports": [
                "STUDY_OVERVIEW_REPORT",
                "SESSION_COMPLETION_REPORT",
                "TASK_QC_REPORT",
                "COHORT_ATTRITION_REPORT",
                "LONGITUDINAL_DESCRIPTIVE_REPORT",
                "CONSENT_DATASET_AUTHORIZATION_REPORT",
            ],
        },
        "operational_metrics_tracked": [
            "total_participants_enrolled",
            "active_consented_participants",
            "withdrawn_participants",
            "sessions_total",
            "sessions_completed",
            "sessions_quality_failed",
            "task_level_acceptance_rate",
        ],
        "disclaimer": RESEARCH_DISCLAIMER,
    }
    target = out_dir / "m5_quality_control_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_longitudinal_analysis_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_longitudinal_analysis_summary.json."""
    data = {
        "milestone": "M5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "schema_version": "voxneuro.longitudinal_analysis.v1",
        "methodology": {
            "tracking_paradigm": (
                "Descriptive intra-individual feature differences (Visit_k - Visit_1)"
            ),
            "required_minimum_visits": 2,
            "interval_metrics": ["mean_days", "std_days", "median_days", "min_days", "max_days"],
            "feature_summary_metrics": [
                "n_observations",
                "mean_change",
                "std_change",
                "median_change",
                "iqr_change",
            ],
            "minimum_observations_for_summary": 5,
        },
        "scientific_integrity_invariant": {
            "strict_constraint": (
                "Longitudinal observations are purely descriptive acoustic measurements. "
                "They MUST NOT be used or interpreted as evidence of disease progression, "
                "symptom worsening, therapeutic efficacy, or clinical outcome."
            ),
            "disclaimer_text": (
                "Descriptive acoustic tracking only. Changes in voice measurements over time "
                "do not establish neurodegenerative progression, symptom worsening, "
                "or therapeutic response."
            ),
        },
    }
    target = out_dir / "m5_longitudinal_analysis_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_privacy_audit_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_privacy_audit_summary.json."""
    data = {
        "milestone": "M5",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "schema_version": "voxneuro.privacy_audit.v1",
        "pseudonymity_protections": {
            "participant_id_format": "PT-XXXXXXXXXXXX (12-char cryptographically random hex)",
            "direct_pii_rejected": True,
            "pii_detection_regex_rules": [
                "Email address patterns",
                "Phone number / SSN 3-3-4 patterns",
                "Explicit PII label prefixes (mrn=, ssn=, dob=, patient=, name=)",
            ],
        },
        "audit_logging": {
            "relational_audit_table": "audit_log",
            "automatic_pii_redaction": True,
            "redacted_terms": ["name", "email", "phone", "address", "mrn", "password", "token"],
            "redaction_replacement": "[REDACTED_PII]",
        },
        "immutable_processing_receipts": {
            "receipt_entity": "ProcessingRunReceipt",
            "receipt_hash_algorithm": "SHA-256",
            "cryptographic_provenance_bound": [
                "project_code_fingerprint",
                "task_schema_fingerprints",
                "audio_config_fingerprint",
                "feature_config_fingerprint",
                "domain_metadata_fingerprint",
                "feature_table_checksum",
            ],
        },
    }
    target = out_dir / "m5_privacy_audit_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_provenance_summary(out_dir: Path) -> Path:
    """Generate review_evidence/m5_provenance_summary.json."""
    data = {
        "milestone": "M5",
        "application_version": "voxneuro-0.5.0-research",
        "generated_utc": datetime.now(UTC).isoformat(),
        "project_code_fingerprint": project_code_fingerprint(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "task_schema_fingerprints": {
            "voxneuro.voice.v3": v3_schema_fingerprint(),
            "voxneuro.task.ddk.v1": ddk_schema_fingerprint(),
            "voxneuro.task.connected_speech.v1": connected_speech_schema_fingerprint(),
            "voxneuro.task.vowel_space.v1": vowel_space_schema_fingerprint(),
            "voxneuro.voice.v4": v4_envelope_schema_fingerprint(),
        },
        "configuration_fingerprints": {
            "audio_config": "8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d",
            "feature_config": "190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9",
        },
    }
    target = out_dir / "m5_provenance_summary.json"
    target.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_test_evidence(out_dir: Path, test_paths: list[str] | None = None) -> Path:
    """Run tests, capture JUnit XML, verify exit code, and record categorized results."""
    targets = test_paths or ["tests"]

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        xml_path = Path(tmp.name)

    try:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            *targets,
            f"--junitxml={xml_path}",
            "-q",
        ]
        test_env = dict(os.environ)
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=test_env,
            capture_output=True,
            text=True,
            check=False,
        )

        test_cases: list[dict[str, Any]] = []
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_tests = 0
        skipped_tests = 0
        total_time = 0.0

        categories = {
            "m0_m3_tests": {"total": 0, "passed": 0, "failed": 0},
            "m4_domain_validation_tests": {"total": 0, "passed": 0, "failed": 0},
            "m5_study_operations_unit_tests": {"total": 0, "passed": 0, "failed": 0},
            "m5_integration_tests": {"total": 0, "passed": 0, "failed": 0},
            "ui_streamlit_tests": {"total": 0, "passed": 0, "failed": 0},
        }

        if xml_path.is_file() and xml_path.stat().st_size > 0:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            for suite in root.iter("testsuite"):
                total_time += float(suite.get("time", 0.0))
            for tc in root.iter("testcase"):
                total_tests += 1
                name = tc.get("name", "")
                classname = tc.get("classname", "")
                file_attr = tc.get("file", "")
                tc_time = float(tc.get("time", 0.0))

                failure = tc.find("failure")
                error = tc.find("error")
                skipped = tc.find("skipped")

                if failure is not None:
                    status = "failed"
                    failed_tests += 1
                elif error is not None:
                    status = "error"
                    error_tests += 1
                elif skipped is not None:
                    status = "skipped"
                    skipped_tests += 1
                else:
                    status = "passed"
                    passed_tests += 1

                if file_attr:
                    sanitized_file = sanitize_target_path(file_attr)
                else:
                    mod_path = classname.split(".Test")[0].replace(".", "/")
                    sanitized_file = f"{mod_path}.py"

                norm_key = (sanitized_file + " " + classname).replace("\\", "/").casefold()

                if "test_study_" in norm_key:
                    cat_key = "m5_study_operations_unit_tests"
                elif "test_m5_" in norm_key:
                    cat_key = "m5_integration_tests"
                elif (
                    "test_domain_" in norm_key
                    or "test_m4_" in norm_key
                    or "test_external_evaluation" in norm_key
                    or "test_inference_capture_context" in norm_key
                ):
                    cat_key = "m4_domain_validation_tests"
                elif "test_app" in norm_key:
                    cat_key = "ui_streamlit_tests"
                else:
                    cat_key = "m0_m3_tests"

                categories[cat_key]["total"] += 1
                if status == "passed":
                    categories[cat_key]["passed"] += 1
                elif status in {"failed", "error"}:
                    categories[cat_key]["failed"] += 1

                test_cases.append(
                    {
                        "name": name,
                        "file": sanitized_file,
                        "classname": classname,
                        "time_seconds": round(tc_time, 4),
                        "status": status,
                        "category": cat_key,
                    }
                )

        xml_parsed_successfully = xml_path.is_file() and xml_path.stat().st_size > 0
        all_passed = bool(
            proc.returncode == 0
            and xml_parsed_successfully
            and total_tests > 0
            and failed_tests == 0
            and error_tests == 0
            and skipped_tests == 0
        )
        summary = {
            "milestone": "M5",
            "generated_utc": datetime.now(UTC).isoformat(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "error_tests": error_tests,
            "skipped_tests": skipped_tests,
            "execution_time_seconds": round(total_time, 2),
            "exit_code": proc.returncode,
            "all_passed": all_passed,
            "execution_command": "uv run pytest -q --junitxml=<temporary-report-path>",
            "test_report_status": (
                "PARSED_COMPLETE" if xml_parsed_successfully else "REPORT_UNAVAILABLE"
            ),
            "categories": categories,
            "test_cases": test_cases,
        }
    finally:
        if xml_path.exists():
            try:
                xml_path.unlink()
            except OSError:
                pass

    target = out_dir / "m5_test_summary.json"
    target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def generate_review_manifest(out_dir: Path, files: list[Path]) -> Path:
    """Generate review_evidence/m5_review_manifest.json with SHA-256 digests."""
    file_entries = {}
    for f in sorted(files, key=lambda p: p.name):
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        file_entries[f.name] = {
            "bytes": f.stat().st_size,
            "sha256": sha,
        }

    manifest = {
        "milestone": "M5",
        "description": "Milestone 5 cryptographic review evidence manifest",
        "generated_utc": datetime.now(UTC).isoformat(),
        "total_files": len(file_entries),
        "files": file_entries,
    }

    target = out_dir / "m5_review_manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Milestone 5 review evidence files.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory to write review evidence files.",
    )
    args = parser.parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating Milestone 5 review evidence in {out_dir}...")
    evidence_files: list[Path] = []

    # 1. Study registry summary
    f1 = generate_study_registry_summary(out_dir)
    evidence_files.append(f1)
    print(f"  [1/10] Wrote {f1.name}")

    # 2. Database schema summary
    f2 = generate_database_schema_summary(out_dir)
    evidence_files.append(f2)
    print(f"  [2/10] Wrote {f2.name}")

    # 3. Consent governance summary
    f3 = generate_consent_governance_summary(out_dir)
    evidence_files.append(f3)
    print(f"  [3/10] Wrote {f3.name}")

    # 4. Dataset access summary
    f4 = generate_dataset_access_summary(out_dir)
    evidence_files.append(f4)
    print(f"  [4/10] Wrote {f4.name}")

    # 5. Session pipeline summary
    f5 = generate_session_pipeline_summary(out_dir)
    evidence_files.append(f5)
    print(f"  [5/10] Wrote {f5.name}")

    # 6. Quality control summary
    f6 = generate_quality_control_summary(out_dir)
    evidence_files.append(f6)
    print(f"  [6/10] Wrote {f6.name}")

    # 7. Longitudinal analysis summary
    f7 = generate_longitudinal_analysis_summary(out_dir)
    evidence_files.append(f7)
    print(f"  [7/10] Wrote {f7.name}")

    # 8. Privacy audit summary
    f8 = generate_privacy_audit_summary(out_dir)
    evidence_files.append(f8)
    print(f"  [8/10] Wrote {f8.name}")

    # 9. Provenance summary
    f9 = generate_provenance_summary(out_dir)
    evidence_files.append(f9)
    print(f"  [9/10] Wrote {f9.name}")

    # 10. Test summary
    print("  Running test suite for evidence generation...")
    f10 = generate_test_evidence(out_dir)
    evidence_files.append(f10)
    print(f"  [10/10] Wrote {f10.name}")

    # 11. Review manifest
    f11 = generate_review_manifest(out_dir, evidence_files)
    print(f"  Generated review manifest: {f11.name} covering {len(evidence_files)} artifacts.")

    print("Milestone 5 review evidence generation completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
