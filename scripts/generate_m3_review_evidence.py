"""Generate Milestone 3 review evidence files for VoxNeuro audit.

Produces:
  - review_evidence/m3_task_schema_registry.json
  - review_evidence/m3_synthetic_fixture_verification.json
  - review_evidence/m3_implementation_test_summary.json
  - review_evidence/m3_provenance_summary.json
"""

from __future__ import annotations

import json
import platform
import posixpath
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

import numpy as np
from tests.fixtures.synthetic_connected_speech import synthetic_connected_speech
from tests.fixtures.synthetic_ddk_audio import synthetic_ddk_train
from tests.fixtures.synthetic_vowels import synthetic_formant_vowel

from voxneuro.audio.task_preprocessing import TaskPreprocessingResult
from voxneuro.features.schema import schema_fingerprint as v3_schema_fingerprint
from voxneuro.features.tasks.connected_speech import extract_connected_speech_features
from voxneuro.features.tasks.ddk import extract_ddk_features
from voxneuro.features.tasks.schema import (
    connected_speech_schema_fingerprint,
    ddk_schema_fingerprint,
    generate_task_schema_registry_document,
    get_task_schema_registry,
    v4_envelope_schema_fingerprint,
    vowel_space_schema_fingerprint,
)
from voxneuro.features.tasks.vowel_space import extract_vowel_space_features
from voxneuro.provenance import project_code_fingerprint

M3_TARGET_TEST_FILES: list[str] = [
    "tests/unit/test_task_audio.py",
    "tests/unit/test_ddk_features.py",
    "tests/unit/test_connected_speech_features.py",
    "tests/unit/test_vowel_space_features.py",
    "tests/unit/test_multitask_orchestration.py",
    "tests/unit/test_multitask_failures.py",
    "tests/unit/test_schema_registry.py",
    "tests/unit/test_evidence_generator.py",
    "tests/unit/test_features.py",
    "tests/integration/test_multitask_app.py",
    "tests/integration/test_app.py",
]


def _make_prep(samples: np.ndarray, sr: int = 16000) -> TaskPreprocessingResult:
    return TaskPreprocessingResult(
        samples=samples.astype(np.float64),
        sample_rate=sr,
        original_sample_rate=sr,
        original_channels=1,
        dc_offset_removed=0.0,
        trim_start_seconds=0.0,
        trimmed_tail_seconds=0.0,
        retained_duration_seconds=float(len(samples) / sr),
        resampled=False,
        preprocessing_fingerprint="synthetic_fixture_test",
    )


def verify_synthetic_fixtures() -> dict[str, object]:
    """Execute synthetic audio fixture tests and output verification metrics."""
    results: dict[str, object] = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "disclaimer": (
            "These synthetic audio fixtures verify software implementation correctness and "
            "signal-processing edge cases only. Passing a synthetic fixture bound (e.g., VSA "
            "bounds, DDK rates, or pause counts) does not establish a healthy reference range, "
            "validate physiological maximum performance, diagnose clinical dysarthria, "
            "or establish population-level formant accuracy."
        ),
        "ddk_fixtures": {},
        "connected_speech_fixture": {},
        "vowel_space_fixture": {},
        "overall_verification": "PASS",
    }

    # 1. DDK Fixtures
    ddk_dict: dict[str, object] = {}
    for target_rate in (3.0, 5.0, 7.0):
        audio = synthetic_ddk_train(sample_rate=16000, duration=4.0, target_rate_hz=target_rate)
        prep = _make_prep(audio)
        ddk_res = extract_ddk_features(prep)
        measured_rate = ddk_res.features.get("estimated_event_rate_per_s")
        rate_error = abs(measured_rate - target_rate) if measured_rate is not None else 999.0
        passed = rate_error <= 0.45
        ddk_dict[f"rate_{target_rate}hz"] = {
            "target_rate_hz": target_rate,
            "measured_rate_hz": measured_rate,
            "error_hz": round(rate_error, 4),
            "events_detected": int(ddk_res.features.get("estimated_event_count") or 0),
            "status": "PASS" if passed else "FAIL",
        }
        if not passed:
            results["overall_verification"] = "FAIL"

    # DDK Jitter vs Uniform
    uniform = _make_prep(synthetic_ddk_train(duration=4.0, target_rate_hz=5.0, jitter_sd_s=0.0))
    jittered = _make_prep(synthetic_ddk_train(duration=4.0, target_rate_hz=5.0, jitter_sd_s=0.04))
    res_u = extract_ddk_features(uniform)
    res_j = extract_ddk_features(jittered)
    cv_u = res_u.features.get("cv_inter_event_interval")
    cv_j = res_j.features.get("cv_inter_event_interval")
    jitter_passed = cv_j is not None and cv_u is not None and cv_j > cv_u
    ddk_dict["timing_variability_jitter_test"] = {
        "uniform_cv_iei": round(cv_u, 4) if cv_u is not None else None,
        "jittered_cv_iei": round(cv_j, 4) if cv_j is not None else None,
        "status": "PASS" if jitter_passed else "FAIL",
    }
    if not jitter_passed:
        results["overall_verification"] = "FAIL"

    # DDK Rate Drift Acceleration
    accel = _make_prep(
        synthetic_ddk_train(duration=5.0, target_rate_hz=4.0, acceleration_slope_s=-0.005)
    )
    res_acc = extract_ddk_features(accel)
    slope = res_acc.features.get("inter_event_interval_slope_s_per_event")
    slope_passed = slope is not None and slope < 0.0
    ddk_dict["rate_drift_acceleration_test"] = {
        "drift_slope_s_per_event": round(slope, 6) if slope is not None else None,
        "status": "PASS" if slope_passed else "FAIL",
    }
    if not slope_passed:
        results["overall_verification"] = "FAIL"

    results["ddk_fixtures"] = ddk_dict

    # 2. Connected Speech Fixture
    cs_audio = synthetic_connected_speech(sample_rate=16000)
    prep_cs = _make_prep(cs_audio)
    res_cs = extract_connected_speech_features(prep_cs)
    cs_feats = res_cs.features
    pause_count = int(cs_feats.get("pause_count") or 0)
    tot_dur = cs_feats.get("total_recording_duration_s") or 0.0
    pause_frac = cs_feats.get("pause_fraction") or 0.0
    st_range = cs_feats.get("f0_range_semitones") or 0.0

    cs_passed = pause_count == 2 and abs(tot_dur - 6.5) <= 0.3 and pause_frac > 0.10
    results["connected_speech_fixture"] = {
        "total_duration_s": round(tot_dur, 2),
        "pause_count": pause_count,
        "pause_fraction": round(pause_frac, 3),
        "f0_median_hz": cs_feats.get("f0_median_hz"),
        "f0_range_semitones": round(st_range, 2),
        "status": "PASS" if cs_passed else "FAIL",
    }
    if not cs_passed:
        results["overall_verification"] = "FAIL"

    # 3. Vowel Space Area Fixture
    v_a = _make_prep(synthetic_formant_vowel("a", duration=2.0))
    v_i = _make_prep(synthetic_formant_vowel("i", duration=2.0))
    v_u = _make_prep(synthetic_formant_vowel("u", duration=2.0))
    vs_res = extract_vowel_space_features({"a": [v_a], "i": [v_i], "u": [v_u]})
    vsa_val = vs_res.features.get("vowel_space_area_hz2")
    f1_a = vs_res.features.get("f1_a_median_hz")
    f2_a = vs_res.features.get("f2_a_median_hz")
    f1_i = vs_res.features.get("f1_i_median_hz")
    f2_i = vs_res.features.get("f2_i_median_hz")
    f1_u = vs_res.features.get("f1_u_median_hz")
    f2_u = vs_res.features.get("f2_u_median_hz")

    vs_passed = (
        vsa_val is not None and 100000 <= vsa_val <= 300000 and vs_res.task_status == "complete"
    )
    results["vowel_space_fixture"] = {
        "vowel_a_formants_hz": {"f1": f1_a, "f2": f2_a},
        "vowel_i_formants_hz": {"f1": f1_i, "f2": f2_i},
        "vowel_u_formants_hz": {"f1": f1_u, "f2": f2_u},
        "vowel_space_area_hz2": round(vsa_val, 1) if vsa_val is not None else None,
        "status": "PASS" if vs_passed else "FAIL",
    }
    if not vs_passed:
        results["overall_verification"] = "FAIL"

    return results


def sanitize_target_path(target: str, repo_root: Path | str | None = None) -> str:
    """Sanitize a test target path cross-platform without leaking user directories or host paths."""
    target_str = str(target).strip()
    if not target_str:
        return ""

    # 1. UNC network paths (e.g. \\server\share\... or //server/share/...)
    # Must never expose server or share identifiers
    if (
        target_str.startswith(r"\\\\")
        or target_str.startswith("//")
        or bool(re.match(r"^[\\/]{2}", target_str))
    ):
        clean_back = target_str.replace("/", "\\")
        pw = PureWindowsPath(clean_back)
        fn = pw.name or "test_file.py"
        return f"<temporary-dir>/{fn}"

    # 2. Tilde paths (~/...)
    if target_str.startswith("~"):
        fn = posixpath.basename(target_str.replace("\\", "/").rstrip("/")) or "test_file.py"
        return f"<temporary-dir>/{fn}"

    # Detect Windows drive letter (e.g. C:\ or C:/)
    has_win_drive = bool(re.match(r"^[A-Za-z]:[\\/]", target_str))

    # Detect POSIX absolute path
    is_posix_abs = target_str.startswith("/") and not target_str.startswith("//")

    root_val = repo_root or Path(__file__).resolve().parents[1]
    root_str = str(root_val)
    root_is_win = bool(re.match(r"^[A-Za-z]:[\\/]", root_str))
    root_is_posix = root_str.startswith("/") and not root_str.startswith("//")

    # 3. Relative path handling (neither Windows drive nor POSIX absolute)
    if not has_win_drive and not is_posix_abs:
        normalized_slash = target_str.replace("\\", "/")
        norm = posixpath.normpath(normalized_slash)
        if norm in (".", ""):
            return ""
        if norm.startswith("../") or norm == "..":
            fn = posixpath.basename(norm) or "test_file.py"
            return f"<temporary-dir>/{fn}"
        return norm

    # 4. Windows absolute path
    if has_win_drive:
        if root_is_win:
            pw_target = PureWindowsPath(target_str)
            pw_root = PureWindowsPath(root_str)
            try:
                rel = pw_target.relative_to(pw_root)
                norm_rel = posixpath.normpath(rel.as_posix())
                if not norm_rel.startswith("../") and norm_rel != "..":
                    return norm_rel
            except ValueError:
                pass
        # Foreign flavor or external path
        pw = PureWindowsPath(target_str)
        fn = pw.name or "test_file.py"
        return f"<temporary-dir>/{fn}"

    # 5. POSIX absolute path
    if is_posix_abs:
        if root_is_posix:
            pp_target = PurePosixPath(target_str)
            pp_root = PurePosixPath(root_str)
            try:
                rel = pp_target.relative_to(pp_root)
                norm_rel = posixpath.normpath(rel.as_posix())
                if not norm_rel.startswith("../") and norm_rel != "..":
                    return norm_rel
            except ValueError:
                pass
        # Foreign flavor or external path
        pp = PurePosixPath(target_str)
        fn = pp.name or "test_file.py"
        return f"<temporary-dir>/{fn}"

    # Fallback
    fn = posixpath.basename(target_str.replace("\\", "/").rstrip("/")) or "test_file.py"
    return f"<temporary-dir>/{fn}"


def build_portable_pytest_command(targets: list[str]) -> str:
    """Construct a clean, portable command string for review evidence without path leaks."""
    sanitized = [sanitize_target_path(t) for t in targets]
    return f"python -m pytest {' '.join(sanitized)} --junitxml=<temporary-file> -q"


def run_actual_tests_and_summarize(test_targets: list[str]) -> dict[str, object]:
    """Execute pytest with JUnit XML reporting and derive real test execution statistics."""
    # Check if streamlit is available
    streamlit_available = True
    try:
        import streamlit  # noqa: F401
    except ImportError:
        streamlit_available = False

    active_targets = list(test_targets)
    blocked_targets = []
    if not streamlit_available:
        active_targets = [t for t in test_targets if "app" not in t]
        blocked_targets = [t for t in test_targets if "app" in t]

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tf:
        xml_path = Path(tf.name)

    actual_cmd = [sys.executable, "-m", "pytest", *active_targets, f"--junitxml={xml_path}", "-q"]

    proc = subprocess.run(actual_cmd, capture_output=True, text=True)

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is not None:
            total_tests = int(suite.attrib.get("tests", 0))
            failures = int(suite.attrib.get("failures", 0))
            errors = int(suite.attrib.get("errors", 0))
            skipped = int(suite.attrib.get("skipped", 0))
            passed = total_tests - (failures + errors + skipped)
            duration_s = round(float(suite.attrib.get("time", 0.0)), 3)
        else:
            total_tests = failures = errors = skipped = passed = 0
            duration_s = 0.0
    except Exception as exc:
        total_tests = failures = skipped = passed = 0
        errors = 1
        duration_s = 0.0
        print(f"Error parsing JUnit XML report: {exc}")
    finally:
        xml_path.unlink(missing_ok=True)

    pass_rate = round((passed / total_tests * 100.0), 2) if total_tests > 0 else 0.0
    execution_status = (
        "PASS" if (failures == 0 and errors == 0 and proc.returncode == 0) else "FAIL"
    )

    sanitized_executed = [sanitize_target_path(t) for t in active_targets]
    sanitized_all = [sanitize_target_path(t) for t in test_targets]
    sanitized_blocked = [sanitize_target_path(t) for t in blocked_targets]
    portable_cmd = build_portable_pytest_command(active_targets)

    summary: dict[str, object] = {
        "milestone": "M3",
        "execution_timestamp_utc": datetime.now(UTC).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "command": portable_cmd,
        "test_targets": sanitized_all,
        "executed_targets": sanitized_executed,
        "blocked_targets": sanitized_blocked,
        "total": total_tests,
        "passed": passed,
        "failed": failures,
        "errors": errors,
        "skipped": skipped,
        "pass_rate_percentage": pass_rate,
        "duration_seconds": duration_s,
        "exit_code": proc.returncode,
        "execution_status": execution_status,
    }

    # Verify no local filesystem leakage in output
    raw_str = json.dumps(summary)
    assert sys.executable not in raw_str, "sys.executable leaked into test summary"
    assert str(xml_path) not in raw_str, "temporary xml_path leaked into test summary"

    return summary


def main() -> None:
    review_dir = Path("review_evidence")
    review_dir.mkdir(parents=True, exist_ok=True)

    # 1. Authoritative Schema Registry
    schema_registry_doc = generate_task_schema_registry_document()
    with open(review_dir / "m3_task_schema_registry.json", "w", encoding="utf-8") as f:
        json.dump(schema_registry_doc, f, indent=2)
    print("Wrote review_evidence/m3_task_schema_registry.json")

    # 2. Synthetic Fixture Verification
    fixture_evidence = verify_synthetic_fixtures()
    with open(review_dir / "m3_synthetic_fixture_verification.json", "w", encoding="utf-8") as f:
        json.dump(fixture_evidence, f, indent=2)
    print("Wrote review_evidence/m3_synthetic_fixture_verification.json")

    # 3. Dynamic Test Execution Summary from JUnit XML
    test_summary = run_actual_tests_and_summarize(M3_TARGET_TEST_FILES)
    with open(review_dir / "m3_implementation_test_summary.json", "w", encoding="utf-8") as f:
        json.dump(test_summary, f, indent=2)
    print("Wrote review_evidence/m3_implementation_test_summary.json (derived from real pytest)")

    # 4. Provenance Summary
    prov_summary = {
        "milestone": "M3",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "project_code_fingerprint": project_code_fingerprint(),
        "canonical_v3_schema_fingerprint": v3_schema_fingerprint(),
        "ddk_v1_schema_fingerprint": ddk_schema_fingerprint(),
        "connected_speech_v1_schema_fingerprint": connected_speech_schema_fingerprint(),
        "vowel_space_v1_schema_fingerprint": vowel_space_schema_fingerprint(),
        "v4_envelope_schema_fingerprint": v4_envelope_schema_fingerprint(),
        "schema_registry_count": len(get_task_schema_registry()),
        "microphone_inference_policy": "allow_user_microphone_inference: false (locked)",
    }
    with open(review_dir / "m3_provenance_summary.json", "w", encoding="utf-8") as f:
        json.dump(prov_summary, f, indent=2)
    print("Wrote review_evidence/m3_provenance_summary.json")


if __name__ == "__main__":
    main()
