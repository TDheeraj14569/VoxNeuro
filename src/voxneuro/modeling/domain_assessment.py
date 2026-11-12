"""Domain assessment dossier schema, validation, and cryptographic hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from voxneuro.features.schema import (
    SCHEMA_VERSION as V3_SCHEMA_VERSION,
)
from voxneuro.features.schema import (
    schema_fingerprint as get_v3_schema_fingerprint,
)
from voxneuro.modeling.domain_registry import RecordingDomainRegistry, load_domain_registry

ASSESSMENT_SCHEMA_VERSION = "voxneuro.domain_assessment.v1"
VALID_ASSESSMENT_STATUSES = frozenset(
    {
        "FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING",
        "CANDIDATE_DOMAIN_EVALUATED_PENDING_REVIEW",
        "DOMAIN_VALIDATION_BLOCKED",
        "DOMAIN_VALIDATION_REJECTED",
        "DOMAIN_COMPATIBILITY_APPROVED",
    }
)


@dataclass
class SourceModelMetadata:
    model_artifact_sha256: str
    feature_schema_version: str
    feature_schema_fingerprint: str
    feature_config_fingerprint: str
    preprocessing_config_fingerprint: str
    training_dataset_checksum: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricSummary:
    point_estimate: float | None
    ci_lower: float | None = None
    ci_upper: float | None = None
    status: str = "ESTIMATED"  # "ESTIMATED", "NOT_ESTIMABLE", "UNRELIABLE_SMALL_SAMPLE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QualityAttritionSummary:
    total_enrolled: int
    recordings_attempted: int
    recordings_passed_quality: int
    attrition_rate: float
    reasons: dict[str, int] = field(default_factory=dict)
    failures_by_group: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DomainShiftSummary:
    n_features_evaluated: int
    n_features_significant_shift_fdr: int
    n_features_significant_shift_bonferroni: int
    max_absolute_smd: float | None
    mean_absolute_smd: float | None
    acquisition_differences: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DomainAssessmentDossier:
    """Rich candidate domain assessment dossier conforming to voxneuro.domain_assessment.v1."""

    schema_version: str
    assessment_id: str
    generated_utc: str
    assessment_protocol_id: str
    source_model: SourceModelMetadata
    reference_domain: dict[str, Any]
    candidate_domains: list[dict[str, Any]]
    independence: dict[str, Any]
    evaluation_design: dict[str, Any]
    cohort_summary: dict[str, Any]
    quality_attrition: QualityAttritionSummary
    performance_metrics: dict[str, MetricSummary]
    domain_shift_summary: DomainShiftSummary
    status: str
    decision_rationale: str
    compatibility_approval: dict[str, Any] = field(
        default_factory=lambda: {
            "approved_for_inference": False,
            "approved_utc": None,
            "approved_by": None,
            "review_evidence_sha256": None,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "assessment_id": self.assessment_id,
            "generated_utc": self.generated_utc,
            "assessment_protocol_id": self.assessment_protocol_id,
            "source_model": self.source_model.to_dict(),
            "reference_domain": self.reference_domain,
            "candidate_domains": self.candidate_domains,
            "independence": self.independence,
            "evaluation_design": self.evaluation_design,
            "cohort_summary": self.cohort_summary,
            "quality_attrition": self.quality_attrition.to_dict(),
            "performance_metrics": {k: v.to_dict() for k, v in self.performance_metrics.items()},
            "domain_shift_summary": self.domain_shift_summary.to_dict(),
            "status": self.status,
            "decision_rationale": self.decision_rationale,
            "compatibility_approval": self.compatibility_approval,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_domain_assessment_dict(data: object) -> DomainAssessmentDossier:
    """Validate a parsed JSON candidate assessment dossier."""
    if not isinstance(data, dict):
        raise ValueError("Domain assessment dossier must be a JSON dictionary.")

    if data.get("schema_version") != ASSESSMENT_SCHEMA_VERSION:
        raise ValueError(
            f"Expected schema_version {ASSESSMENT_SCHEMA_VERSION!r}, "
            f"got {data.get('schema_version')!r}."
        )

    required_keys = {
        "schema_version",
        "assessment_id",
        "generated_utc",
        "assessment_protocol_id",
        "source_model",
        "reference_domain",
        "candidate_domains",
        "independence",
        "evaluation_design",
        "cohort_summary",
        "quality_attrition",
        "performance_metrics",
        "domain_shift_summary",
        "status",
        "decision_rationale",
        "compatibility_approval",
    }
    missing = required_keys - set(data)
    if missing:
        raise ValueError(f"Domain assessment dossier missing required fields: {sorted(missing)}")

    status = data["status"]
    if status not in VALID_ASSESSMENT_STATUSES:
        raise ValueError(f"Invalid assessment status: {status!r}")

    # Safety invariant: approved_for_inference must be False for all unapproved/candidate dossiers
    approval = data["compatibility_approval"]
    if not isinstance(approval, dict):
        raise ValueError("compatibility_approval must be a dictionary.")
    if status != "DOMAIN_COMPATIBILITY_APPROVED" and approval.get("approved_for_inference") is True:
        raise ValueError(
            "Cannot claim approved_for_inference: true when status "
            "is not DOMAIN_COMPATIBILITY_APPROVED."
        )

    src = data["source_model"]
    source_model = SourceModelMetadata(
        model_artifact_sha256=str(src["model_artifact_sha256"]),
        feature_schema_version=str(src["feature_schema_version"]),
        feature_schema_fingerprint=str(src["feature_schema_fingerprint"]),
        feature_config_fingerprint=str(src["feature_config_fingerprint"]),
        preprocessing_config_fingerprint=str(src["preprocessing_config_fingerprint"]),
        training_dataset_checksum=str(src["training_dataset_checksum"]),
    )

    cohort = data["cohort_summary"]
    if not isinstance(cohort, dict):
        raise ValueError("cohort_summary must be a dictionary.")
    n_participants = int(cohort.get("n_participants", 0))
    n_recordings_attempted = int(cohort.get("n_recordings_attempted", 0))

    indep = data["independence"]
    if not isinstance(indep, dict):
        raise ValueError("independence must be a dictionary.")

    # Invariant: Cannot claim independent validation with zero external participants
    if n_participants == 0 and indep.get("independent_validation") is True:
        raise ValueError(
            "Cannot claim independent_validation: true when cohort has zero external participants."
        )

    # Invariant: Zero external participants cannot have a numeric overlapping count
    if n_participants == 0 and indep.get("overlapping_participants_count") is not None:
        raise ValueError(
            "overlapping_participants_count must be null when external "
            "cohort has zero participants."
        )

    # Invariant: Cannot claim overlap checked with zero participants
    if n_participants == 0 and indep.get("participant_overlap_checked") is True:
        raise ValueError(
            "Cannot claim participant_overlap_checked: true when external "
            "cohort has zero participants."
        )

    # Invariant: Claiming overlap checked requires an overlap check receipt
    if indep.get("participant_overlap_checked") is True and not indep.get(
        "overlap_check_receipt_sha256"
    ):
        raise ValueError(
            "Cannot claim participant_overlap_checked: true without an "
            "overlap_check_receipt_sha256 receipt."
        )

    eval_design = data["evaluation_design"]
    if not isinstance(eval_design, dict):
        raise ValueError("evaluation_design must be a dictionary.")

    # Invariant: Cannot claim frozen model applied with zero attempted recordings or participants
    if (n_recordings_attempted == 0 or n_participants == 0) and eval_design.get(
        "frozen_model_applied"
    ) is True:
        raise ValueError(
            "Cannot claim frozen_model_applied: true when no external "
            "recordings or participants were evaluated."
        )

    if (n_recordings_attempted == 0 or n_participants == 0) and eval_design.get(
        "evaluation_status"
    ) == "COMPLETED":
        raise ValueError(
            "Cannot claim evaluation_status: 'COMPLETED' when zero "
            "external recordings were attempted."
        )

    # Invariant: Candidate dataset checksum required for completed comparison or approval
    if (
        eval_design.get("evaluation_status") == "COMPLETED"
        or status == "DOMAIN_COMPATIBILITY_APPROVED"
    ):
        cands = data.get("candidate_domains", [])
        if not cands or not any(
            c.get("candidate_dataset_checksum_sha256") or c.get("candidate_dataset_checksum")
            for c in cands
            if isinstance(c, dict)
        ):
            raise ValueError(
                "Completed external comparison or approval requires candidate_dataset_checksum."
            )

    qa = data["quality_attrition"]
    quality_attrition = QualityAttritionSummary(
        total_enrolled=int(qa["total_enrolled"]),
        recordings_attempted=int(qa["recordings_attempted"]),
        recordings_passed_quality=int(qa["recordings_passed_quality"]),
        attrition_rate=float(qa["attrition_rate"]),
        reasons=dict(qa.get("reasons", {})),
        failures_by_group=dict(qa.get("failures_by_group", {})),
    )

    metrics: dict[str, MetricSummary] = {}
    for k, v in data["performance_metrics"].items():
        if isinstance(v, dict):
            pt = float(v["point_estimate"]) if v.get("point_estimate") is not None else None
            m_status = str(v.get("status", "ESTIMATED"))
            if pt is None and m_status in {
                "ESTIMATED",
                "SUCCESSFULLY_EVALUATED",
                "COMPLETED",
            }:
                raise ValueError(
                    f"Performance metric {k!r} has null point_estimate but is "
                    f"marked as {m_status!r}."
                )
            if pt is not None and m_status == "NOT_ESTIMABLE_PENDING_DATA":
                raise ValueError(
                    f"Performance metric {k!r} has non-null point_estimate but is "
                    "marked as 'NOT_ESTIMABLE_PENDING_DATA'."
                )
            metrics[k] = MetricSummary(
                point_estimate=pt,
                ci_lower=float(v["ci_lower"]) if v.get("ci_lower") is not None else None,
                ci_upper=float(v["ci_upper"]) if v.get("ci_upper") is not None else None,
                status=m_status,
            )

    if status == "DOMAIN_COMPATIBILITY_APPROVED":
        if any(m.point_estimate is None for m in metrics.values()):
            raise ValueError(
                "Cannot approve domain compatibility when performance metrics "
                "contain null estimates."
            )

    ds = data["domain_shift_summary"]
    domain_shift = DomainShiftSummary(
        n_features_evaluated=int(ds["n_features_evaluated"]),
        n_features_significant_shift_fdr=int(ds["n_features_significant_shift_fdr"]),
        n_features_significant_shift_bonferroni=int(ds["n_features_significant_shift_bonferroni"]),
        max_absolute_smd=(
            float(ds["max_absolute_smd"]) if ds.get("max_absolute_smd") is not None else None
        ),
        mean_absolute_smd=(
            float(ds["mean_absolute_smd"]) if ds.get("mean_absolute_smd") is not None else None
        ),
        acquisition_differences=list(ds.get("acquisition_differences", [])),
    )

    return DomainAssessmentDossier(
        schema_version=str(data["schema_version"]),
        assessment_id=str(data["assessment_id"]),
        generated_utc=str(data["generated_utc"]),
        assessment_protocol_id=str(data["assessment_protocol_id"]),
        source_model=source_model,
        reference_domain=dict(data["reference_domain"]),
        candidate_domains=list(data["candidate_domains"]),
        independence=dict(data["independence"]),
        evaluation_design=dict(data["evaluation_design"]),
        cohort_summary=dict(data["cohort_summary"]),
        quality_attrition=quality_attrition,
        performance_metrics=metrics,
        domain_shift_summary=domain_shift,
        status=status,
        decision_rationale=str(data["decision_rationale"]),
        compatibility_approval=approval,
    )


def load_domain_assessment_dossier(path: Path) -> DomainAssessmentDossier:
    """Load, validate, and parse a candidate domain assessment dossier file."""
    if not path.is_file():
        raise FileNotFoundError(f"Dossier file not found: {path}")
    raw_text = path.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    return validate_domain_assessment_dict(data)


def _build_domain_specific_acquisition_differences(
    reg: RecordingDomainRegistry,
    ref_domain_id: str = "uams_telephone",
) -> list[str]:
    """Summarize documented acquisition differences per candidate domain against reference."""
    ref_entry = reg.get_domain(ref_domain_id)
    ref_meta = ref_entry.metadata
    differences = [
        (
            f"{ref_entry.domain_id} (reference): {ref_meta.recording_environment} acquisition "
            f"(source rate {ref_meta.original_sample_rate or 'unknown'} Hz, "
            f"{ref_meta.bit_depth or 'unknown'}-bit, hardware {ref_meta.device_category})."
        )
    ]
    for cid in reg.candidate_domains:
        c_entry = reg.get_domain(cid)
        c_meta = c_entry.metadata
        env_label = c_meta.recording_environment or "unknown"
        hw_parts = [
            p
            for p in (c_meta.device_manufacturer, c_meta.device_model)
            if p is not None and str(p).strip()
        ]
        hw_desc = (
            " ".join(hw_parts) if hw_parts else f"unknown transducer ({c_meta.device_category})"
        )
        rate_desc = (
            f"{c_meta.original_sample_rate} Hz"
            if c_meta.original_sample_rate is not None
            else "unknown sample rate"
        )
        bit_desc = (
            f"{c_meta.bit_depth}-bit" if c_meta.bit_depth is not None else "unknown bit depth"
        )
        codec_desc = c_meta.audio_codec or "unknown"
        ch_desc = (
            f"{c_meta.channel_count}-ch" if c_meta.channel_count is not None else "unknown channels"
        )
        if env_label == "clinical_quiet_room":
            env_note = f"{env_label} (quiet clinical room, not acoustically isolated)"
        elif env_label == "sound_treated_booth":
            env_note = f"{env_label} (sound-treated acoustical booth)"
        else:
            env_note = f"{env_label} (recording environment unverified/unknown)"
        differences.append(
            f"{c_entry.domain_id}: {env_note}; {hw_desc}; "
            f"{rate_desc}, {bit_desc}, {ch_desc}, codec {codec_desc} vs. "
            f"{ref_entry.domain_id} telephone acquisition."
        )
    return differences


def create_pending_framework_assessment_dossier(
    registry: RecordingDomainRegistry | None = None,
    protocol_id: str = "VOXNEURO-M4-EXT-VAL-2026-V1",
    model_artifact_sha256: str = (
        "eaa271934410f72d6e4130c66aba086d24055f532b360a02425e4a4bf8ef9333"
    ),
    training_dataset_checksum: str = (
        "d83d37e901ab2e5ec2499f070bd507b1c5c2b754dda36d115184f57a1383ab77"
    ),
    feature_config_fingerprint: str = (
        "190e79c16b8a92f6c7fa8de47956531ade096c43e5f3974d9ce9b5d88b74b5f9"
    ),
    preprocessing_config_fingerprint: str = (
        "8cd060e419204da2beb98454d8511631e3f00e87971b17b3ea732d39e606189d"
    ),
) -> DomainAssessmentDossier:
    """Create the authoritative Milestone 4 framework assessment dossier with pending status."""
    reg = registry or load_domain_registry()
    ref_entry = reg.get_domain("uams_telephone")
    candidates = [reg.get_domain(cid).to_dict() for cid in reg.candidate_domains]

    source_model = SourceModelMetadata(
        model_artifact_sha256=model_artifact_sha256,
        feature_schema_version=V3_SCHEMA_VERSION,
        feature_schema_fingerprint=get_v3_schema_fingerprint(),
        feature_config_fingerprint=feature_config_fingerprint,
        preprocessing_config_fingerprint=preprocessing_config_fingerprint,
        training_dataset_checksum=training_dataset_checksum,
    )

    metrics = {
        "balanced_accuracy": MetricSummary(
            point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"
        ),
        "sensitivity": MetricSummary(point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"),
        "specificity": MetricSummary(point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"),
        "precision": MetricSummary(point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"),
        "f1": MetricSummary(point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"),
        "roc_auc": MetricSummary(point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"),
        "average_precision": MetricSummary(
            point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"
        ),
        "mcc": MetricSummary(point_estimate=None, status="NOT_ESTIMABLE_PENDING_DATA"),
    }

    quality_attrition = QualityAttritionSummary(
        total_enrolled=0,
        recordings_attempted=0,
        recordings_passed_quality=0,
        attrition_rate=0.0,
        reasons={},
        failures_by_group={},
    )

    domain_shift = DomainShiftSummary(
        n_features_evaluated=0,
        n_features_significant_shift_fdr=0,
        n_features_significant_shift_bonferroni=0,
        max_absolute_smd=None,
        mean_absolute_smd=None,
        acquisition_differences=_build_domain_specific_acquisition_differences(reg),
    )

    return DomainAssessmentDossier(
        schema_version=ASSESSMENT_SCHEMA_VERSION,
        assessment_id="VOXNEURO-M4-DOSSIER-PENDING-001",
        generated_utc="2026-11-12T03:00:00Z",
        assessment_protocol_id=protocol_id,
        source_model=source_model,
        reference_domain=ref_entry.to_dict(),
        candidate_domains=candidates,
        independence={
            "independent_validation": False,
            "participant_overlap_checked": False,
            "overlapping_participants_count": None,
            "overlap_status": "NOT_ASSESSED",
            "overlap_verification_method": None,
        },
        evaluation_design={
            "frozen_model_applied": False,
            "threshold_fixed": True,
            "threshold_fixed_status": "PRESPECIFIED_PROTOCOL_ONLY",
            "decision_threshold": 0.5,
            "evaluation_status": "NOT_PERFORMED",
            "bootstrap_iterations": 1000,
            "random_seed": 2026,
            "unit_of_analysis": "participant_level",
        },
        cohort_summary={
            "status": "AWAITING_EXTERNAL_RAW_AUDIO_DUA",
            "n_participants": 0,
            "n_healthy_controls": 0,
            "n_parkinsons": 0,
            "n_recordings_attempted": 0,
            "n_recordings_passed_quality": 0,
        },
        quality_attrition=quality_attrition,
        performance_metrics=metrics,
        domain_shift_summary=domain_shift,
        status="FRAMEWORK_VERIFIED_DOMAIN_VALIDATION_PENDING",
        decision_rationale=(
            "M4 domain-validation framework implementation and software verification are complete. "
            "Independent external recording-domain validation has not been performed. "
            "No candidate domain has been approved. Prediction compatibility remains disabled."
        ),
        compatibility_approval={
            "approved_for_inference": False,
            "approved_utc": None,
            "approved_by": None,
            "review_evidence_sha256": None,
        },
    )
