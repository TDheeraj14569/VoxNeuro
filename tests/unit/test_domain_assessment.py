"""Unit tests for domain assessment dossier schema, validation, and safety separation."""

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION
from voxneuro.modeling.domain_assessment import (
    create_pending_framework_assessment_dossier,
    validate_domain_assessment_dict,
)
from voxneuro.modeling.domain_evaluation import FROZEN_REFERENCE_MODEL_SHA256
from voxneuro.modeling.domains import load_domain_validation_report
from voxneuro.modeling.model_bundle import make_bundle


def test_create_and_validate_pending_dossier():
    dossier = create_pending_framework_assessment_dossier()
    assert dossier.schema_version == "voxneuro.domain_assessment.v1"
    assert dossier.status == "FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING"
    assert dossier.compatibility_approval["approved_for_inference"] is False
    assert dossier.fingerprint()

    # Reconciled model checksum
    assert dossier.source_model.model_artifact_sha256 == FROZEN_REFERENCE_MODEL_SHA256

    # Semantics of pending state: unmeasured values are null or false
    assert dossier.independence["independent_validation"] is False
    assert dossier.independence["participant_overlap_checked"] is False
    assert dossier.independence["overlapping_participants_count"] is None
    assert dossier.independence["overlap_status"] == "NOT_ASSESSED"

    assert dossier.evaluation_design["frozen_model_applied"] is False
    assert dossier.evaluation_design["threshold_fixed"] is True
    assert dossier.evaluation_design["threshold_fixed_status"] == "PRESPECIFIED_PROTOCOL_ONLY"
    assert dossier.evaluation_design["evaluation_status"] == "NOT_PERFORMED"


def test_dossier_rejects_premature_approval_claim():
    dossier = create_pending_framework_assessment_dossier()
    data = dossier.to_dict()
    data["compatibility_approval"]["approved_for_inference"] = True
    with pytest.raises(ValueError, match="Cannot claim approved_for_inference: true"):
        validate_domain_assessment_dict(data)


def test_dossier_rejects_zero_participants_with_independent_validation_true():
    dossier = create_pending_framework_assessment_dossier()
    data = dossier.to_dict()
    data["independence"]["independent_validation"] = True
    with pytest.raises(ValueError, match="Cannot claim independent_validation: true"):
        validate_domain_assessment_dict(data)


def test_dossier_rejects_zero_participants_with_numeric_overlap_count():
    dossier = create_pending_framework_assessment_dossier()
    data = dossier.to_dict()
    data["independence"]["overlapping_participants_count"] = 0
    with pytest.raises(ValueError, match="overlapping_participants_count must be null"):
        validate_domain_assessment_dict(data)


def test_dossier_rejects_zero_participants_with_overlap_checked_true():
    dossier = create_pending_framework_assessment_dossier()
    data = dossier.to_dict()
    data["independence"]["participant_overlap_checked"] = True
    data["independence"]["overlap_check_receipt_sha256"] = "a" * 64
    with pytest.raises(
        ValueError,
        match="Cannot claim participant_overlap_checked: true when external cohort has zero",
    ):
        validate_domain_assessment_dict(data)


def test_dossier_rejects_overlap_checked_without_receipt():
    dossier = create_pending_framework_assessment_dossier()
    data = dossier.to_dict()
    data["cohort_summary"]["n_participants"] = 40
    data["independence"]["participant_overlap_checked"] = True
    with pytest.raises(ValueError, match="without an overlap_check_receipt_sha256 receipt"):
        validate_domain_assessment_dict(data)


def test_dossier_rejects_zero_recordings_with_frozen_model_applied_true():
    dossier = create_pending_framework_assessment_dossier()
    data = dossier.to_dict()
    data["evaluation_design"]["frozen_model_applied"] = True
    with pytest.raises(ValueError, match="Cannot claim frozen_model_applied: true"):
        validate_domain_assessment_dict(data)


def test_dossier_rejects_null_metric_labelled_estimated():
    dossier = create_pending_framework_assessment_dossier()
    data = dossier.to_dict()
    data["performance_metrics"]["balanced_accuracy"]["status"] = "ESTIMATED"
    with pytest.raises(ValueError, match="has null point_estimate but is marked as 'ESTIMATED'"):
        validate_domain_assessment_dict(data)


def test_candidate_dossier_strictly_rejected_by_compatibility_report_loader(tmp_path):
    """Candidate dossiers must NEVER be accepted as approved prediction compatibility reports."""
    dossier = create_pending_framework_assessment_dossier()
    dossier_path = tmp_path / "candidate_dossier.json"
    dossier_path.write_text(dossier.to_json(), encoding="utf-8")

    with pytest.raises(ValueError, match="Candidate domain assessment dossiers"):
        load_domain_validation_report(dossier_path)


def test_candidate_dossier_cannot_approve_bundle(tmp_path):
    """make_bundle must fail closed if someone attempts to pass a candidate assessment dossier."""
    dossier = create_pending_framework_assessment_dossier()
    dossier_path = tmp_path / "candidate_dossier.json"
    dossier_path.write_text(dossier.to_json(), encoding="utf-8")

    X = pd.DataFrame(np.zeros((2, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    model = DummyClassifier(strategy="constant", constant=0).fit(X, [0, 1])

    with pytest.raises(ValueError, match="Candidate domain assessment dossiers"):
        make_bundle(
            model,
            dataset_provenance="synthetic",
            dataset_version="v1",
            dataset_checksum_sha256="a" * 64,
            code_version="b" * 64,
            training_evaluation_receipt_sha256="c" * 64,
            validation_method="test",
            software_versions={"python": "3.12"},
            preprocessing_config={"target_sample_rate": 16000},
            feature_config={"schema_version": SCHEMA_VERSION},
            domain_validation_report=dossier_path,
        )


def test_pending_dossier_acquisition_differences_are_domain_specific():
    """Part 8.3: Dossier does not conflate NeuroVoz or IPVS with a sound-treated booth."""
    dossier = create_pending_framework_assessment_dossier()
    diffs = dossier.domain_shift_summary.acquisition_differences
    joined = "\n".join(diffs).lower()

    assert len(diffs) >= 3
    assert "neurovoz_studio" in joined
    assert "clinical_quiet_room" in joined
    assert "pc_gita_condenser" in joined
    assert "sound_treated_booth" in joined
    assert "italian_parkinsons_headset" in joined

    for entry in diffs:
        low = entry.lower()
        if "neurovoz_studio" in low:
            assert "sound_treated_booth" not in low
        if "italian_parkinsons_headset" in low:
            assert "44100" not in low and "44.1" not in low
            assert "sound_treated_booth" not in low
            assert "unknown" in low


def test_documentation_does_not_claim_verified_independence_while_not_assessed():
    """Part 8.2: Docs separate cohort origin from overlap status (NOT_ASSESSED)."""
    from pathlib import Path

    dossier = create_pending_framework_assessment_dossier()
    assert dossier.independence["independent_validation"] is False
    assert dossier.independence["participant_overlap_checked"] is False
    assert dossier.independence["overlap_status"] == "NOT_ASSESSED"
    assert dossier.cohort_summary["n_participants"] == 0

    for rel in (
        "docs/audit/M4_EXTERNAL_DATASET_REGISTER.md",
        "docs/audit/M4_COMPLETION_REPORT.md",
    ):
        text = Path(rel).read_text(encoding="utf-8")
        assert "NOT_ASSESSED" in text
        for line in text.splitlines():
            if line.strip().startswith("|") and (
                "NeuroVoz" in line or "PC-GITA" in line or "IPVS" in line or "UCI" in line
            ):
                assert "| Yes" not in line
                assert "| Independent |" not in line
