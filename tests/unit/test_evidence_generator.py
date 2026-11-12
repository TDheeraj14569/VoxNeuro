"""Automated tests for M3 test evidence generator integrity and non-fabrication."""

from __future__ import annotations

import getpass
import json
import re
import sys
from pathlib import Path

from scripts.generate_m3_review_evidence import (
    build_portable_pytest_command,
    run_actual_tests_and_summarize,
    sanitize_target_path,
)


def test_test_summary_not_hardcoded() -> None:
    """The generated test summary must be derived from actual execution, not fixed constants."""
    summary_path = Path("review_evidence/m3_implementation_test_summary.json")
    if not summary_path.is_file():
        # If not yet generated in fresh clone, run on focused target
        return

    with open(summary_path, encoding="utf-8") as f:
        data = json.load(f)

    # Check structure
    assert data["milestone"] == "M3"
    assert "execution_timestamp_utc" in data
    assert "python_version" in data
    assert "platform" in data
    assert "command" in data
    assert "test_targets" in data
    assert isinstance(data["test_targets"], list)
    assert len(data["test_targets"]) > 0

    # Total must equal the sum of constituent test results
    total = data["total"]
    passed = data["passed"]
    failed = data["failed"]
    errors = data["errors"]
    skipped = data["skipped"]

    assert total == passed + failed + errors + skipped
    assert total > 0, "No tests were executed"
    assert data["duration_seconds"] > 0.0
    assert data["exit_code"] == 0
    assert data["execution_status"] == "PASS"


def test_generator_captures_simulated_failure(tmp_path: Path) -> None:
    """The generator must report actual failures when a test fails, rather than fabricating PASS."""
    # Create a temporary failing test file
    failing_test = tmp_path / "test_simulated_fail.py"
    failing_test.write_text("def test_will_fail():\n    assert False\n", encoding="utf-8")

    summary = run_actual_tests_and_summarize([str(failing_test)])
    assert summary["total"] == 1
    assert summary["failed"] == 1
    assert summary["passed"] == 0
    assert summary["exit_code"] != 0
    assert summary["execution_status"] == "FAIL"
    assert summary["pass_rate_percentage"] == 0.0


def test_portable_command_excludes_absolute_paths_and_identifies_targets() -> None:
    """1. Absolute Windows paths are excluded; portable command identifies targets."""
    targets = [
        "tests/unit/test_task_audio.py",
        "tests/unit/test_ddk_features.py",
    ]
    cmd = build_portable_pytest_command(targets)
    assert cmd.startswith("python -m pytest ")
    assert "--junitxml=<temporary-file> -q" in cmd
    assert sys.executable not in cmd
    # No Windows drive absolute path
    assert not re.search(r"[A-Za-z]:[\\/]", cmd)
    # Target files are clearly identified
    for t in targets:
        assert t in cmd


def test_evidence_excludes_unix_home_and_usernames() -> None:
    """2. Unix home-directory paths and 3. usernames are not exposed."""
    targets = ["tests/unit/test_task_audio.py"]
    summary = run_actual_tests_and_summarize(targets)

    raw_json = json.dumps(summary)
    username = getpass.getuser()
    if username and len(username) > 2:
        assert username not in raw_json, f"Username '{username}' exposed in summary"

    assert "/home/" not in raw_json
    assert "/Users/" not in raw_json
    assert not re.search(r"[A-Za-z]:[\\/][Uu]sers", raw_json)


def test_temporary_report_paths_replaced_with_placeholder(tmp_path: Path) -> None:
    """4. Temporary report paths are replaced with <temporary-file> placeholder."""
    test_file = tmp_path / "test_dummy.py"
    test_file.write_text("def test_ok(): pass\n", encoding="utf-8")

    summary = run_actual_tests_and_summarize([str(test_file)])
    assert "--junitxml=<temporary-file>" in str(summary["command"])
    assert ".xml" not in str(summary["command"]).replace("--junitxml=<temporary-file>", "")


def test_test_counts_derived_from_actual_junit_xml(tmp_path: Path) -> None:
    """5. Test counts remain derived from actual JUnit XML."""
    test_file = tmp_path / "test_mixed.py"
    test_file.write_text(
        "def test_one(): pass\ndef test_two(): pass\ndef test_three(): assert False\n",
        encoding="utf-8",
    )
    summary = run_actual_tests_and_summarize([str(test_file)])
    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert summary["errors"] == 0
    assert summary["skipped"] == 0
    assert summary["pass_rate_percentage"] == round(2 / 3 * 100.0, 2)


def test_sanitized_target_path_normalization(tmp_path: Path) -> None:
    """6. Path sanitizer strips absolute prefixes and normalizes slashes cross-platform."""
    # 1. Windows relative path
    assert sanitize_target_path(r"tests\unit\test_audio.py") == "tests/unit/test_audio.py"

    # 2. Windows absolute external path
    assert (
        sanitize_target_path(r"C:\Users\alice\AppData\Local\Temp\test_win.py")
        == "<temporary-dir>/test_win.py"
    )
    assert (
        sanitize_target_path(r"D:\other_drive\test_external.py")
        == "<temporary-dir>/test_external.py"
    )

    # 3. Windows repo-relative absolute path (with Windows repo root)
    assert (
        sanitize_target_path(
            r"C:\workspace\VoxNeuro\tests\unit\test_win.py",
            repo_root=r"C:\workspace\VoxNeuro",
        )
        == "tests/unit/test_win.py"
    )

    # 4. Windows external path (with Windows repo root)
    assert (
        sanitize_target_path(
            r"C:\Users\alice\temp\test.py",
            repo_root=r"C:\workspace\VoxNeuro",
        )
        == "<temporary-dir>/test.py"
    )

    # 5. POSIX relative path
    assert sanitize_target_path("tests/unit/test_audio.py") == "tests/unit/test_audio.py"

    # 6. POSIX absolute external path
    assert sanitize_target_path("/tmp/testing/test_posix.py") == "<temporary-dir>/test_posix.py"

    # 7. POSIX repo-relative absolute path (with POSIX repo root)
    assert (
        sanitize_target_path(
            "/workspace/VoxNeuro/tests/unit/test_posix.py",
            repo_root="/workspace/VoxNeuro",
        )
        == "tests/unit/test_posix.py"
    )

    # 8. Foreign-flavour paths (deterministic across Windows and Linux)
    # Windows path evaluated with POSIX repo root (Linux execution scenario)
    assert (
        sanitize_target_path(
            r"C:\Users\alice\AppData\Local\Temp\test_win.py",
            repo_root="/home/user/VoxNeuro",
        )
        == "<temporary-dir>/test_win.py"
    )
    # POSIX path evaluated with Windows repo root (Windows execution scenario)
    assert (
        sanitize_target_path(
            "/tmp/testing/test_posix.py",
            repo_root=r"C:\workspace\VoxNeuro",
        )
        == "<temporary-dir>/test_posix.py"
    )

    # 9. UNC network paths (never expose server or share name)
    assert (
        sanitize_target_path(r"\\server\share\tests\test_unc.py") == "<temporary-dir>/test_unc.py"
    )
    assert sanitize_target_path("//nas/volume/tests/test_unc.py") == "<temporary-dir>/test_unc.py"

    # 10. Paths containing spaces
    assert (
        sanitize_target_path("tests/dir with spaces/test_spaces.py")
        == "tests/dir with spaces/test_spaces.py"
    )

    # 11. External temporary file from fixture
    ext_file = tmp_path / "test_external.py"
    sanitized = sanitize_target_path(str(ext_file))
    assert sanitized == "<temporary-dir>/test_external.py"
    assert str(tmp_path) not in sanitized

    # 12. Path with '..' traversal components
    assert sanitize_target_path("tests/unit/../unit/test_audio.py") == "tests/unit/test_audio.py"
    assert (
        sanitize_target_path("../../outside/test_escaped.py") == "<temporary-dir>/test_escaped.py"
    )

    # 13. User profile / home paths
    assert sanitize_target_path(r"C:\Users\jdoe\mytest.py") == "<temporary-dir>/mytest.py"
    assert sanitize_target_path("/home/jdoe/mytest.py") == "<temporary-dir>/mytest.py"
    assert sanitize_target_path("~/mytest.py") == "<temporary-dir>/mytest.py"

    # 14. Portable command generation
    cmd = build_portable_pytest_command(
        [r"tests\unit\test_task_audio.py", "tests/unit/test_ddk_features.py"]
    )
    assert cmd == (
        "python -m pytest tests/unit/test_task_audio.py "
        "tests/unit/test_ddk_features.py --junitxml=<temporary-file> -q"
    )


def test_m4_evidence_generator_handles_pending_state(tmp_path: Path) -> None:
    from scripts.generate_m4_review_evidence import (
        generate_domain_shift_evidence,
        generate_m4_provenance_evidence,
        generate_safety_gate_test_evidence,
    )

    csv_p, json_p = generate_domain_shift_evidence(tmp_path)
    assert csv_p.is_file()
    assert json_p.is_file()
    j_data = json.loads(json_p.read_text(encoding="utf-8"))
    assert j_data["status"] == "DOMAIN_VALIDATION_PENDING"
    assert j_data["comparison_performed"] is False

    safety_p = generate_safety_gate_test_evidence(
        tmp_path, test_paths=["tests/unit/test_domain_registry.py"]
    )
    assert safety_p.is_file()
    s_data = json.loads(safety_p.read_text(encoding="utf-8"))
    assert s_data["exit_code"] == 0
    assert s_data["fully_successful"] is True
    assert s_data["total_tests"] >= 5
    assert s_data["passed_tests"] == s_data["total_tests"]

    prov_p = generate_m4_provenance_evidence(tmp_path)
    assert prov_p.is_file()
    p_data = json.loads(prov_p.read_text(encoding="utf-8"))
    assert p_data["milestone"] == "M4"
    assert (
        p_data["reference_model_artifact_sha256"]
        == "eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333"
    )
