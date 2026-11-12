"""Integration test for Milestone 4 domain validation pipeline and CLI tools."""

import json
from pathlib import Path

from scripts.evaluate_external_domain import main as evaluate_main
from scripts.generate_domain_assessment import main as generate_main
from scripts.inspect_external_domain import inspect_domain

from voxneuro.modeling.domain_assessment import load_domain_assessment_dossier
from voxneuro.modeling.domain_registry import load_domain_registry

ROOT = Path(__file__).resolve().parents[2]


def test_domain_pipeline_end_to_end(tmp_path, monkeypatch):
    # 1. Registry validation
    registry = load_domain_registry()
    assert registry.is_registered("neurovoz_studio")
    assert registry.is_registered("uams_telephone")

    # 2. Inspect external domain CLI tool
    summary = inspect_domain("neurovoz_studio")
    assert summary["domain_id"] == "neurovoz_studio"
    assert summary["candidate_compatibility_status"] == "DOMAIN_VALIDATION_PENDING"
    assert summary["inference_eligible"] is False

    # 3. Generate candidate assessment dossier
    dossier_path = tmp_path / "m4_dossier.json"
    monkeypatch.setattr(
        "sys.argv",
        ["generate_domain_assessment.py", "--output", str(dossier_path)],
    )
    assert generate_main() == 0
    assert dossier_path.is_file()

    dossier = load_domain_assessment_dossier(dossier_path)
    assert dossier.schema_version == "voxneuro.domain_assessment.v1"
    assert dossier.status == "FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING"
    assert dossier.compatibility_approval["approved_for_inference"] is False

    # 4. Evaluate candidate domain with pending status
    eval_out = tmp_path / "domain_eval"
    monkeypatch.setattr(
        "sys.argv",
        [
            "evaluate_external_domain.py",
            "--domain",
            "neurovoz_studio",
            "--out-dir",
            str(eval_out),
            "--json",
        ],
    )
    assert evaluate_main() == 0
    eval_file = eval_out / "neurovoz_studio_evaluation_status.json"
    assert eval_file.is_file()
    eval_data = json.loads(eval_file.read_text(encoding="utf-8"))
    assert eval_data["status"] == "FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING"
    assert eval_data["inference_eligible"] is False
