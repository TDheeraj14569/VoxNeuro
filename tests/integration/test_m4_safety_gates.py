"""Integration test verifying absolute invariants of Milestone 4 safety gates."""

from pathlib import Path

import yaml

from voxneuro.config import load_config
from voxneuro.modeling import domains as domain_safety
from voxneuro.modeling.domain_registry import load_domain_registry
from voxneuro.modeling.model_bundle import load_bundle

ROOT = Path(__file__).resolve().parents[2]


def test_safety_gate_trusted_allowlist_is_strictly_empty():
    """Safety rule: TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 must remain strictly empty."""
    assert len(domain_safety.TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256) == 0
    assert domain_safety.TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 == frozenset()


def test_safety_gate_microphone_inference_is_strictly_disabled():
    """Safety rule: allow_user_microphone_inference must be false in configuration and loader."""
    model_config = load_config("model_config.yaml")
    assert model_config["allow_user_microphone_inference"] is False

    raw_yaml = yaml.safe_load((ROOT / "configs" / "model_config.yaml").read_text(encoding="utf-8"))
    assert raw_yaml.get("allow_user_microphone_inference") is False


def test_safety_gate_registry_approved_domains_is_strictly_empty():
    """Safety rule: approved_domains in registry must remain strictly empty."""
    registry = load_domain_registry()
    assert registry.approved_domains == []
    for _d, entry in registry.domains.items():
        assert entry.inference_eligible is False


def test_safety_gate_reference_model_bundle_safety_flags():
    """Safety rule: reference model bundle must enforce research_only and unverified domain."""
    bundle_path = ROOT / "artifacts" / "models" / "uams_logistic_research.joblib"
    if bundle_path.is_file():
        bundle = load_bundle(bundle_path)
        assert bundle["research_only"] is True
        assert bundle["domain_compatibility_verified"] is False
        assert bundle["validated_input_domains"] == []
        assert bundle["allow_user_microphone_inference"] is False
