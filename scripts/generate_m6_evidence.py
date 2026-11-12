"""Generate aggregate, privacy-sanitized M6 review evidence and manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voxneuro.config import PROJECT_ROOT, load_config
from voxneuro.features.schema import (
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
)
from voxneuro.features.schema import schema_fingerprint as v3_schema_fingerprint
from voxneuro.features.tasks.schema import (
    connected_speech_schema_fingerprint,
    ddk_schema_fingerprint,
    v4_envelope_schema_fingerprint,
    vowel_space_schema_fingerprint,
)
from voxneuro.modeling.dataset_readiness import build_dataset_readiness_report
from voxneuro.modeling.domains import TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
from voxneuro.modeling.m6_experiment import (
    generate_m6_model_card,
    render_model_card_html,
    run_m6_comparative_experiments,
)
from voxneuro.modeling.model_registry import LIFECYCLE_STATES
from voxneuro.modeling.prediction import InputCaptureContext
from voxneuro.modeling.prediction_service import M6_MEDICAL_DISCLAIMER, run_prediction_service
from voxneuro.provenance import project_code_fingerprint
from voxneuro.study.auth import VALID_ROLES, register_user
from voxneuro.study.database import check_schema_integrity, get_connection, run_migrations

PATH_LEAK_RE = re.compile(r"[A-Za-z]:(?:\\\\|\\|/(?!/))|/[Uu]sers/|/home/")


def _assert_clean_payload(name: str, payload: bytes) -> None:
    text = payload.decode("utf-8", errors="replace")
    if PATH_LEAK_RE.search(text):
        raise ValueError(f"Workstation path detected in generated evidence {name}")
    if re.search(rb"\buams-\d+\b", payload.lower()):
        raise ValueError(f"Participant identifier detected in generated evidence {name}")


def _write_json(path: Path, data: Any) -> bytes:
    encoded = (json.dumps(data, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
    _assert_clean_payload(path.name, encoded)
    path.write_bytes(encoded)
    return encoded


def _categorize_testcase(classname: str) -> str:
    if "test_m6_" in classname:
        if "integration" in classname:
            return "m6_ui_integration_tests"
        return "m6_ml_auth_prediction_tests"
    if "test_app" in classname or "test_multitask_app" in classname:
        return "ui_streamlit_tests"
    if "domain" in classname or "prediction" in classname or "external" in classname:
        return "m4_domain_validation_tests"
    if "study" in classname:
        return "m5_study_tests"
    return "m0_m3_core_tests"


def _run_pytest_summary() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="voxneuro-m6-junit-") as tmp_dir:
        xml_path = Path(tmp_dir) / "junit.xml"
        cmd = [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml_path}"]
        start = time.monotonic()
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
        elapsed = round(time.monotonic() - start, 2)
        if not xml_path.is_file():
            raise RuntimeError(
                f"pytest did not produce JUnit XML (exit={proc.returncode}): {proc.stdout}\n"
                f"{proc.stderr}"
            )
        root = ET.parse(xml_path).getroot()
        cases = []
        categories: dict[str, dict[str, int]] = {}
        passed = failed = skipped = errors = 0
        for tc in root.iter("testcase"):
            classname = tc.attrib.get("classname", "")
            name = tc.attrib.get("name", "")
            tsec = round(float(tc.attrib.get("time", "0.0")), 4)
            failure = tc.find("failure")
            err = tc.find("error")
            skip = tc.find("skipped")
            if failure is not None:
                status = "failed"
                failed += 1
            elif err is not None:
                status = "error"
                errors += 1
            elif skip is not None:
                status = "skipped"
                skipped += 1
            else:
                status = "passed"
                passed += 1
            cat = _categorize_testcase(classname)
            bucket = categories.setdefault(
                cat, {"passed": 0, "failed": 0, "skipped": 0, "total": 0}
            )
            bucket["total"] += 1
            if status == "passed":
                bucket["passed"] += 1
            elif status == "skipped":
                bucket["skipped"] += 1
            else:
                bucket["failed"] += 1
            cases.append(
                {
                    "category": cat,
                    "classname": classname,
                    "name": name,
                    "status": status,
                    "time_seconds": tsec,
                }
            )
        return {
            "milestone": "M6",
            "generated_utc": datetime.now(UTC).isoformat(),
            "execution_command": "uv run pytest -q --junitxml=<temporary-report-path>",
            "exit_code": proc.returncode,
            "all_passed": proc.returncode == 0 and failed == 0 and errors == 0 and skipped == 0,
            "passed_tests": passed,
            "failed_tests": failed,
            "skipped_tests": skipped,
            "error_tests": errors,
            "execution_time_seconds": elapsed,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "categories": categories,
            "test_cases": cases,
        }


def generate_m6_evidence(*, run_tests: bool = True) -> dict[str, Any]:
    """Generate all M6 evidence artifacts under review_evidence/ and verify manifest."""
    ev_dir = PROJECT_ROOT / "review_evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    eval_dir = PROJECT_ROOT / "artifacts" / "reports" / "model_evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # 1. Experiment benchmark, dataset readiness, and model card
    readiness = build_dataset_readiness_report()
    experiment = run_m6_comparative_experiments()
    model_card = generate_m6_model_card(experiment)
    card_html = render_model_card_html(model_card)

    _write_json(eval_dir / "m6_dataset_readiness.json", readiness)
    _write_json(eval_dir / "m6_experiment_summary.json", experiment)
    _write_json(eval_dir / "m6_model_card.json", model_card)
    (eval_dir / "m6_model_card.html").write_text(card_html, encoding="utf-8")

    # 2. Isolated Migration 006 + RBAC + fail-closed PredictionService verification
    with tempfile.TemporaryDirectory(prefix="voxneuro-m6-ev-") as tmp_dir:
        tmp_db = Path(tmp_dir) / "ev.db"
        applied = run_migrations(tmp_db)
        integrity = check_schema_integrity(tmp_db)
        conn = get_connection(tmp_db)
        try:
            tables = sorted(
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
                ).fetchall()
            )
            demo_user = register_user(
                conn,
                username="ev_participant",
                email="ev_part@example.org",
                password="EvidenceStrongPassword123!",
                role="participant",
            )
            abstain_res = run_prediction_service(
                features=None,
                quality_valid=False,
                capture_context=InputCaptureContext(
                    capture_origin="live_browser_mic", verified_origin=False
                ),
                input_domain="laptop_microphone",
                conn=conn,
                user_id=demo_user.user_id,
            )
            abstention_count = conn.execute(
                "SELECT COUNT(*) AS c FROM abstention_events;"
            ).fetchone()["c"]
        finally:
            conn.close()

    audio_cfg = load_config("audio_config.yaml")
    feature_cfg = load_config("feature_config.yaml")
    model_cfg = load_config("model_config.yaml")

    written: dict[str, bytes] = {}
    written["m6_dataset_readiness.json"] = _write_json(
        ev_dir / "m6_dataset_readiness.json", readiness
    )
    written["m6_experiment_summary.json"] = _write_json(
        ev_dir / "m6_experiment_summary.json", experiment
    )
    written["m6_model_card.json"] = _write_json(ev_dir / "m6_model_card.json", model_card)
    html_bytes = card_html.encode("utf-8")
    _assert_clean_payload("m6_model_card.html", html_bytes)
    (ev_dir / "m6_model_card.html").write_bytes(html_bytes)
    written["m6_model_card.html"] = html_bytes

    written["m6_database_and_auth_summary.json"] = _write_json(
        ev_dir / "m6_database_and_auth_summary.json",
        {
            "milestone": "M6",
            "generated_utc": datetime.now(UTC).isoformat(),
            "applied_migrations": applied,
            "schema_integrity": integrity,
            "table_count": len(tables),
            "tables": tables,
            "rbac_roles": sorted(VALID_ROLES),
            "model_lifecycle_states": sorted(LIFECYCLE_STATES),
            "password_hashing": "PBKDF2-HMAC-SHA256 (200000 iterations)",
            "session_token_storage": "SHA-256 hash only (raw token never stored)",
            "self_registration_default_role": "participant",
        },
    )

    written["m6_prediction_service_summary.json"] = _write_json(
        ev_dir / "m6_prediction_service_summary.json",
        {
            "milestone": "M6",
            "generated_utc": datetime.now(UTC).isoformat(),
            "allow_user_microphone_inference": bool(
                model_cfg.get("allow_user_microphone_inference", False)
            ),
            "trusted_domain_validation_report_hashes_count": len(
                TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
            ),
            "fail_closed_probe": {
                "abstained": abstain_res.abstained,
                "status": abstain_res.status,
                "abstention_reasons": abstain_res.abstention_reasons,
                "retention_persisted": abstain_res.retention_persisted,
                "abstention_events_recorded": abstention_count,
                "disclaimer_present": M6_MEDICAL_DISCLAIMER in abstain_res.research_only_disclaimer,
            },
            "medical_disclaimer": M6_MEDICAL_DISCLAIMER,
        },
    )

    written["m6_ui_architecture_summary.json"] = _write_json(
        ev_dir / "m6_ui_architecture_summary.json",
        {
            "milestone": "M6",
            "generated_utc": datetime.now(UTC).isoformat(),
            "initial_sidebar_state": "collapsed",
            "top_navigation_public_pages": [
                "Home",
                "Voice Check",
                "Results",
                "How It Works",
                "Privacy & Safety",
                "Help",
                "Account",
            ],
            "authenticated_user_pages": ["My History"],
            "role_gated_portals": ["Researcher", "Model Admin", "System Admin"],
            "guided_workflow_steps": [
                "Prepare",
                "Consent",
                "Record",
                "Quality",
                "Features",
                "Result",
            ],
            "legacy_compatibility_sidebar_preserved": True,
        },
    )

    written["m6_provenance_summary.json"] = _write_json(
        ev_dir / "m6_provenance_summary.json",
        {
            "milestone": "M6",
            "generated_utc": datetime.now(UTC).isoformat(),
            "application_version": "voxneuro-0.6.0-research",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "project_code_fingerprint": project_code_fingerprint(),
            "schema_version": SCHEMA_VERSION,
            "configuration_fingerprints": {
                "audio_config": configuration_fingerprint(audio_cfg),
                "feature_config": feature_config_fingerprint(feature_cfg),
            },
            "task_schema_fingerprints": {
                "voxneuro.voice.v3": v3_schema_fingerprint(),
                "voxneuro.task.ddk.v1": ddk_schema_fingerprint(),
                "voxneuro.task.connected_speech.v1": connected_speech_schema_fingerprint(),
                "voxneuro.task.vowel_space.v1": vowel_space_schema_fingerprint(),
                "voxneuro.voice.v4": v4_envelope_schema_fingerprint(),
            },
        },
    )

    if run_tests:
        test_summary = _run_pytest_summary()
        written["m6_test_summary.json"] = _write_json(ev_dir / "m6_test_summary.json", test_summary)
    elif (ev_dir / "m6_test_summary.json").is_file():
        written["m6_test_summary.json"] = (ev_dir / "m6_test_summary.json").read_bytes()

    manifest_files = {
        fname: {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for fname, payload in sorted(written.items())
    }
    manifest = {
        "milestone": "M6",
        "description": "Milestone 6 cryptographic review evidence manifest",
        "generated_utc": datetime.now(UTC).isoformat(),
        "total_files": len(manifest_files),
        "files": manifest_files,
    }
    _write_json(ev_dir / "m6_review_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate M6 cryptographic review evidence.")
    parser.add_argument("--skip-tests", action="store_true", help="Reuse existing m6_test_summary.")
    args = parser.parse_args(argv)
    manifest = generate_m6_evidence(run_tests=not args.skip_tests)
    print(f"PASS generated M6 evidence ({manifest['total_files']} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
