"""Tests for release privacy invariants and evidence-generator integrity."""

from __future__ import annotations

import json
import re

from scripts.generate_m5_review_evidence import (
    ROOT,
    generate_consent_governance_summary,
    generate_dataset_access_summary,
)

from voxneuro.config import load_config


def test_reviewed_exclusions_contains_no_participant_ids():
    """Reviewed exclusions configuration must NOT contain participant IDs."""
    cfg = load_config("reviewed_exclusions.yaml")
    cfg_text = (ROOT / "configs" / "reviewed_exclusions.yaml").read_text(encoding="utf-8")

    prefix = "uams-04"
    for suffix in ("5", "6", "7"):
        forbidden_id = prefix + suffix
        assert forbidden_id not in cfg_text

    # Must contain aggregate policy or anonymized group
    assert "reviewed_exclusions_policy" in cfg or "reviewed_exclusions" in cfg


def test_no_hardcoded_fallback_hmac_secret_in_evidence_scripts():
    """Evidence generator scripts must not define any fallback HMAC secret."""
    m5_script_text = (ROOT / "scripts" / "generate_m5_review_evidence.py").read_text(
        encoding="utf-8"
    )
    secret_token = "_".join(["evidence", "gen", "hmac", "secret", "2026"])
    assert secret_token not in m5_script_text


def test_safety_invariants_in_model_config():
    """Verify core safety invariants in configuration files."""
    model_cfg = load_config("model_config.yaml")
    assert model_cfg.get("allow_user_microphone_inference") is False


def test_consent_retention_default_evidence_matches_schema_and_is_false(tmp_path):
    """Generated M5 consent governance evidence accurately reflects non-retention defaults."""
    out_file = generate_consent_governance_summary(tmp_path)
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["consent_model"]["raw_audio_retention_default"] is False
    assert payload["consent_model"]["derived_features_retention_default"] is False


def test_dataset_access_summary_has_no_fabricated_release_approvals(tmp_path, monkeypatch):
    """Dataset access summary never fabricates APPROVED claims for UAMS/UCI in release."""
    monkeypatch.delenv("VOXNEURO_STUDY_DB", raising=False)
    out_file = generate_dataset_access_summary(tmp_path)
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["status"] == "RUNTIME_DATASET_AUTHORIZATION_NOT_INCLUDED_IN_RELEASE"
    assert payload["registered_datasets"] == []
    assert "supported_dataset_registrations" not in payload


def test_review_evidence_contains_no_workstation_paths():
    """All committed review_evidence files must be free of machine-specific paths."""
    evidence_dir = ROOT / "review_evidence"
    assert evidence_dir.is_dir()
    path_pattern = re.compile(r"[A-Za-z]:(?:\\\\|\\|/(?!/))|/[Uu]sers/|/home/")
    for path in evidence_dir.iterdir():
        if path.is_file() and path.suffix in {".json", ".md", ".txt", ".csv"}:
            text = path.read_text(encoding="utf-8")
            assert not path_pattern.search(text), f"Workstation path leak in {path.name}"

    m5_summary = evidence_dir / "m5_test_summary.json"
    if m5_summary.is_file():
        data = json.loads(m5_summary.read_text(encoding="utf-8"))
        assert (
            data.get("execution_command") == "uv run pytest -q --junitxml=<temporary-report-path>"
        )
