"""Explicitly exploratory, provenance-checked individual research scoring."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from voxneuro.config import PROJECT_ROOT, load_config
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling.domains import canonicalize_domain
from voxneuro.modeling.inference_provenance import verify_local_exploratory_provenance
from voxneuro.modeling.model_bundle import load_bundle
from voxneuro.modeling.prediction import VALID_CAPTURE_ORIGINS
from voxneuro.modeling.prediction_service import M6_MEDICAL_DISCLAIMER, PredictionResult
from voxneuro.study.schema import utc_now_iso

EXPLORATORY_DOMAIN_IDS = frozenset(
    {
        "uams_telephone",
        "neurovoz_studio",
        "pc_gita_condenser",
        "italian_parkinsons_headset",
        "smartphone_microphone",
        "laptop_microphone",
        "laptop_webcam_microphone",
        "consumer_headset",
        "laboratory_microphone",
    }
)
ALLOWED_MISSING_FEATURES = frozenset({"jitter_local", "shimmer_local"})


class OODStatus(StrEnum):
    IN_DISTRIBUTION = "IN_DISTRIBUTION"
    MILD_SHIFT = "MILD_SHIFT"
    OUT_OF_DISTRIBUTION = "OUT_OF_DISTRIBUTION"
    INSUFFICIENT_REFERENCE_DATA = "INSUFFICIENT_REFERENCE_DATA"
    OOD_ASSESSMENT_UNAVAILABLE = "OOD_ASSESSMENT_UNAVAILABLE"


@dataclass(frozen=True)
class OODAssessment:
    status: OODStatus
    checked_features: int
    missing_features: tuple[str, ...] = ()
    robust_range_flags: tuple[str, ...] = ()
    extreme_z_flags: tuple[str, ...] = ()
    maximum_absolute_z: float | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "checked_features": self.checked_features,
            "missing_features": list(self.missing_features),
            "outside_training_q01_q99": list(self.robust_range_flags),
            "more_than_six_training_standard_deviations": list(self.extreme_z_flags),
            "maximum_absolute_z": self.maximum_absolute_z,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExploratoryPredictionInput:
    """Actual Core39 output and acquisition context passed to the research model."""

    features: dict[str, Any]
    feature_names: tuple[str, ...]
    feature_schema_fingerprint: str
    task_type: str
    capture_origin: str
    acquisition_domain_id: str
    acquisition_domain_source: str
    preprocessing_fingerprint: str
    quality_valid: bool
    source_audio_sha256: str | None = None
    repetition_count: int = 1
    recording_metadata: dict[str, Any] = field(default_factory=dict)


def assess_training_distribution(
    features: dict[str, Any],
    manifest: dict[str, Any] | None,
    *,
    allowed_missing_features: frozenset[str] = ALLOWED_MISSING_FEATURES,
) -> OODAssessment:
    """Report interpretable quantile and six-SD checks against training-only references."""
    if not isinstance(manifest, dict):
        return OODAssessment(
            OODStatus.OOD_ASSESSMENT_UNAVAILABLE,
            0,
            reason="The model bundle contains no training-distribution manifest.",
        )
    if (
        manifest.get("schema_version") != "voxneuro.training_distribution.v1"
        or manifest.get("feature_names") != list(FEATURE_NAMES)
        or manifest.get("feature_schema_version") != SCHEMA_VERSION
    ):
        return OODAssessment(
            OODStatus.INSUFFICIENT_REFERENCE_DATA,
            0,
            reason=(
                "The training-distribution reference does not match the Core39 feature contract."
            ),
        )
    statistics = manifest.get("statistics")
    if not isinstance(statistics, dict) or set(statistics) != set(FEATURE_NAMES):
        return OODAssessment(
            OODStatus.INSUFFICIENT_REFERENCE_DATA,
            0,
            reason="Training statistics are incomplete for the Core39 feature schema.",
        )

    missing: list[str] = []
    range_flags: list[str] = []
    extreme_flags: list[str] = []
    max_z = 0.0
    checked = 0
    for name in FEATURE_NAMES:
        value = features.get(name)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            missing.append(name)
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
            return OODAssessment(
                OODStatus.OOD_ASSESSMENT_UNAVAILABLE,
                checked,
                tuple(missing),
                reason=f"Feature {name} is not a finite numeric measurement.",
            )
        measurement = float(value)
        if not math.isfinite(measurement):
            return OODAssessment(
                OODStatus.OOD_ASSESSMENT_UNAVAILABLE,
                checked,
                tuple(missing),
                reason=f"Feature {name} is not finite.",
            )
        reference = statistics.get(name)
        required = {"n", "mean", "std", "q01", "q99"}
        if not isinstance(reference, dict) or required - reference.keys():
            return OODAssessment(
                OODStatus.INSUFFICIENT_REFERENCE_DATA,
                checked,
                tuple(missing),
                reason=f"Training reference statistics are incomplete for {name}.",
            )
        try:
            mean = float(reference["mean"])
            deviation = float(reference["std"])
            lower = float(reference["q01"])
            upper = float(reference["q99"])
            count = int(reference["n"])
        except (TypeError, ValueError, OverflowError):
            return OODAssessment(
                OODStatus.INSUFFICIENT_REFERENCE_DATA,
                checked,
                tuple(missing),
                reason=f"Training reference statistics are malformed for {name}.",
            )
        if (
            count < 2
            or not all(math.isfinite(v) for v in (mean, deviation, lower, upper))
            or deviation <= 0
            or lower > upper
        ):
            return OODAssessment(
                OODStatus.INSUFFICIENT_REFERENCE_DATA,
                checked,
                tuple(missing),
                reason=f"Training reference statistics are insufficient for {name}.",
            )
        z_score = abs(measurement - mean) / max(deviation, 1e-6)
        max_z = max(max_z, z_score)
        checked += 1
        if measurement < lower or measurement > upper:
            range_flags.append(name)
        if z_score > 6.0:
            extreme_flags.append(name)

    unapproved_missing = set(missing) - allowed_missing_features
    if unapproved_missing or len(missing) > len(allowed_missing_features):
        return OODAssessment(
            OODStatus.INSUFFICIENT_REFERENCE_DATA,
            checked,
            tuple(missing),
            tuple(range_flags),
            tuple(extreme_flags),
            round(max_z, 3),
            (
                "Required acoustic measurements are missing; only undefined jitter/shimmer "
                "are permitted."
            ),
        )
    if checked < len(FEATURE_NAMES) - len(allowed_missing_features):
        return OODAssessment(
            OODStatus.INSUFFICIENT_REFERENCE_DATA,
            checked,
            tuple(missing),
            tuple(range_flags),
            tuple(extreme_flags),
            round(max_z, 3),
            "Too few measurements have usable training references.",
        )
    if len(extreme_flags) >= 3:
        status = OODStatus.OUT_OF_DISTRIBUTION
        reason = "At least three features exceed six training standard deviations."
    elif range_flags:
        status = OODStatus.MILD_SHIFT
        reason = (
            "One or more features fall outside the training cohort's 1st–99th percentile range."
        )
    else:
        status = OODStatus.IN_DISTRIBUTION
        reason = (
            "All available features fall within the training cohort's 1st–99th percentile range."
        )
    return OODAssessment(
        status,
        checked,
        tuple(missing),
        tuple(range_flags),
        tuple(extreme_flags),
        round(max_z, 3),
        reason,
    )


def _abstain(
    *,
    reason_code: str,
    reason: str,
    context: ExploratoryPredictionInput,
    model_id: str | None = None,
    model_version: str = "unavailable",
    model_checksum: str | None = None,
    ood: OODAssessment | None = None,
) -> PredictionResult:
    prediction_id = f"prd-{uuid.uuid4().hex[:12]}"
    return PredictionResult(
        prediction_id=prediction_id,
        status="INDIVIDUAL_CLASSIFICATION_UNAVAILABLE",
        abstained=True,
        abstention_reasons=[reason_code],
        abstention_reason=reason,
        model_id=model_id,
        model_version=model_version,
        model_checksum=model_checksum,
        research_score=None,
        research_classification=None,
        calibration_status="NOT_CALIBRATED",
        uncertainty={"ood": ood.to_dict()} if ood else {},
        ood_status=ood.status.value if ood else OODStatus.OOD_ASSESSMENT_UNAVAILABLE.value,
        acquisition_domain_id=context.acquisition_domain_id,
        capture_origin=context.capture_origin,
        score_kind="unavailable",
        decision_threshold=None,
        model_evaluation_metrics={},
        domain_validation_status="NOT_VALIDATED",
        acquisition_domain_source=context.acquisition_domain_source,
        task_type=context.task_type,
        generated_utc=utc_now_iso(),
        research_only_disclaimer=M6_MEDICAL_DISCLAIMER,
    )


def run_exploratory_prediction(
    context: ExploratoryPredictionInput,
    *,
    project_root: Path = PROJECT_ROOT,
) -> PredictionResult:
    """Return an uncalibrated candidate class only after strict local provenance and OOD checks."""
    if not context.quality_valid:
        return _abstain(
            reason_code="QUALITY_GATE_FAILED",
            reason="Audio quality checks did not pass; the research model was not run.",
            context=context,
        )
    if context.capture_origin not in VALID_CAPTURE_ORIGINS or context.capture_origin == "unknown":
        return _abstain(
            reason_code="CAPTURE_ORIGIN_UNKNOWN",
            reason=(
                "The file-entry method is unknown. Capture origin and recording device must "
                "be recorded separately."
            ),
            context=context,
        )
    if context.task_type != "sustained_vowel":
        return _abstain(
            reason_code="TASK_MISMATCH",
            reason="The local research model supports only the sustained-vowel /a/ task.",
            context=context,
        )
    if (
        isinstance(context.repetition_count, bool)
        or not isinstance(context.repetition_count, int)
        or context.repetition_count < 1
    ):
        return _abstain(
            reason_code="MISSING_REPETITION",
            reason="At least one completed sustained-vowel recording is required.",
            context=context,
        )
    if context.acquisition_domain_source not in {"user_declared", "independently_established"}:
        return _abstain(
            reason_code="DOMAIN_SOURCE_INVALID",
            reason=(
                "Recording-device provenance must be marked self-reported or independently "
                "established."
            ),
            context=context,
        )
    try:
        domain = canonicalize_domain(context.acquisition_domain_id)
    except ValueError:
        domain = "unknown"
    if domain not in EXPLORATORY_DOMAIN_IDS:
        return _abstain(
            reason_code="ACQUISITION_DOMAIN_UNKNOWN",
            reason=(
                "Choose a known recording-device category. Upload method alone does not "
                "identify the device."
            ),
            context=context,
        )
    if context.feature_names != tuple(FEATURE_NAMES):
        return _abstain(
            reason_code="FEATURE_SCHEMA_MISMATCH",
            reason="The feature names or ordering do not match the current Core39 model contract.",
            context=context,
        )
    expected_metadata = {
        "schema_version",
        "schema_fingerprint",
        "feature_config_fingerprint",
        "preprocessing_config_fingerprint",
    }
    incoming_names = tuple(name for name in context.features if name in FEATURE_NAMES)
    if incoming_names != tuple(FEATURE_NAMES) or set(context.features) != set(FEATURE_NAMES) | set(
        expected_metadata
    ):
        return _abstain(
            reason_code="FEATURE_SCHEMA_MISMATCH",
            reason="The extracted feature vector is incomplete or contains unexpected fields.",
            context=context,
        )
    try:
        audio_config = load_config("audio_config.yaml")
        feature_config = load_config("feature_config.yaml")
    except (OSError, ValueError):
        return _abstain(
            reason_code="APPLICATION_CONFIG_INVALID",
            reason="The application audio or feature configuration could not be validated.",
            context=context,
        )
    if (
        context.feature_schema_fingerprint != schema_fingerprint()
        or context.features.get("schema_version") != SCHEMA_VERSION
        or context.features.get("schema_fingerprint") != schema_fingerprint()
        or context.features.get("feature_config_fingerprint")
        != feature_config_fingerprint(feature_config)
    ):
        return _abstain(
            reason_code="FEATURE_SCHEMA_MISMATCH",
            reason=(
                "The feature schema or extraction configuration does not match this application."
            ),
            context=context,
        )
    expected_preprocessing = configuration_fingerprint(audio_config)
    if (
        context.preprocessing_fingerprint != expected_preprocessing
        or context.features.get("preprocessing_config_fingerprint") != expected_preprocessing
    ):
        return _abstain(
            reason_code="PREPROCESSING_MISMATCH",
            reason="The recording preprocessing contract does not match the research model.",
            context=context,
        )

    root = project_root.resolve()
    model_path = root / "artifacts" / "models" / "uams_logistic_research.joblib"
    if not model_path.is_file():
        return _abstain(
            reason_code="MODEL_ARTIFACT_MISSING",
            reason=(
                "No local trained Core39 research model is available. The GitHub source release "
                "does not include model binaries; train from the documented UAMS dataset first."
            ),
            context=context,
        )
    try:
        bundle = load_bundle(model_path)
        model_checksum = (
            model_path.with_suffix(model_path.suffix + ".sha256")
            .read_text(encoding="ascii")
            .strip()
        )
    except Exception:
        return _abstain(
            reason_code="MODEL_ARTIFACT_INVALID",
            reason=(
                "The local research model failed its checksum, integrity, or compatibility checks. "
                "Rebuild it from the documented local training workflow."
            ),
            context=context,
        )
    try:
        provenance_issues = verify_local_exploratory_provenance(
            bundle, model_path=model_path, project_root=root
        )
    except Exception:
        provenance_issues = ["Current local evaluation evidence could not be verified."]
    if provenance_issues:
        return _abstain(
            reason_code="MODEL_PROVENANCE_INVALID",
            reason="The local model does not match current verified training evidence: "
            + " ".join(provenance_issues),
            context=context,
            model_id=str(
                bundle.get("training_details", {}).get("model_id", "uams_logistic_research")
            ),
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )

    source_hash = context.source_audio_sha256
    if (
        not isinstance(source_hash, str)
        or len(source_hash) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in source_hash)
    ):
        return _abstain(
            reason_code="SOURCE_AUDIO_FINGERPRINT_MISSING",
            reason=(
                "The original WAV fingerprint is unavailable, so the app cannot check whether "
                "this recording is already part of model training. No research score was shown."
            ),
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    manifest_path = root / "data" / "processed" / "feature_manifest.csv"
    try:
        training_hashes = {
            value.casefold()
            for value in pd.read_csv(manifest_path, usecols=["waveform_sha256"], dtype=str)[
                "waveform_sha256"
            ].dropna()
        }
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        return _abstain(
            reason_code="TRAINING_AUDIO_MANIFEST_INVALID",
            reason=(
                "Training-audio fingerprints could not be checked. No individual research "
                "score was shown."
            ),
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    if source_hash.casefold() in training_hashes:
        return _abstain(
            reason_code="KNOWN_TRAINING_RECORDING",
            reason=(
                "This exact WAV is already in the model-development dataset. A score would be "
                "in-sample and misleading, so no individual candidate is shown. Use the "
                "participant-grouped out-of-fold evaluation to assess known cohort recordings."
            ),
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )

    if (
        bundle.get("research_only") is not True
        or bundle.get("allow_user_microphone_inference") is not False
    ):
        return _abstain(
            reason_code="MODEL_POLICY_MISMATCH",
            reason=(
                "The local model does not carry the required research-only and disabled "
                "validated-mic policy."
            ),
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    if bundle.get("domain_compatibility_verified") is not False:
        return _abstain(
            reason_code="MODEL_MODE_MISMATCH",
            reason="This artifact is not marked for the exploratory, non-domain-validated path.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    if bundle.get("feature_schema_fingerprint") != context.feature_schema_fingerprint:
        return _abstain(
            reason_code="FEATURE_SCHEMA_MISMATCH",
            reason="The trained model feature fingerprint does not match this recording.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    if bundle.get("feature_config_fingerprint") != feature_config_fingerprint(feature_config):
        return _abstain(
            reason_code="FEATURE_CONFIG_MISMATCH",
            reason="The model and recording use different feature-extraction settings.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    if bundle.get("preprocessing_config_fingerprint") != expected_preprocessing:
        return _abstain(
            reason_code="PREPROCESSING_MISMATCH",
            reason="The trained model and recording use different preprocessing settings.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    manifest = bundle.get("training_distribution_manifest")
    if not isinstance(manifest, dict):
        return _abstain(
            reason_code="OOD_REFERENCE_UNAVAILABLE",
            reason="The model has no training-derived reference statistics for OOD assessment.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )
    if manifest.get("task") != context.task_type:
        return _abstain(
            reason_code="TASK_MISMATCH",
            reason="The training reference was built for a different voice task.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
        )

    ood = assess_training_distribution(
        context.features,
        manifest,
        allowed_missing_features=frozenset(bundle.get("allowed_missing_features", ())),
    )
    if ood.status == OODStatus.OUT_OF_DISTRIBUTION:
        return _abstain(
            reason_code="OUT_OF_DISTRIBUTION_FEATURES",
            reason=ood.reason or "The input is outside the training feature distribution.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
            ood=ood,
        )
    if ood.status in {
        OODStatus.OOD_ASSESSMENT_UNAVAILABLE,
        OODStatus.INSUFFICIENT_REFERENCE_DATA,
    }:
        return _abstain(
            reason_code="OOD_REFERENCE_UNAVAILABLE",
            reason=ood.reason or "The training reference is not sufficient for OOD assessment.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
            ood=ood,
        )

    contract = bundle.get("score_contract", {})
    estimator = bundle["model"]
    if contract.get("method") != "decision_function" or not callable(
        getattr(estimator, "decision_function", None)
    ):
        return _abstain(
            reason_code="SCORE_CONTRACT_UNSUPPORTED",
            reason="The model has no supported, explicit decision-score contract.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
            ood=ood,
        )
    classes = list(getattr(estimator, "classes_", []))
    if classes != [0, 1] or contract.get("positive_class_label") != "PD":
        return _abstain(
            reason_code="MODEL_LABEL_CONTRACT_INVALID",
            reason="The model's positive-class mapping is not explicitly PD.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
            ood=ood,
        )
    row = pd.DataFrame([[context.features[name] for name in FEATURE_NAMES]], columns=FEATURE_NAMES)
    try:
        score = float(estimator.decision_function(row)[0])
        threshold = float(contract["threshold"])
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return _abstain(
            reason_code="MODEL_OUTPUT_INVALID",
            reason="The model did not return a valid decision score for this recording.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
            ood=ood,
        )
    if not math.isfinite(score) or not math.isfinite(threshold):
        return _abstain(
            reason_code="MODEL_OUTPUT_INVALID",
            reason="The model decision score or threshold is non-finite.",
            context=context,
            model_id="uams_logistic_research",
            model_version=str(bundle.get("model_version", "unknown")),
            model_checksum=model_checksum,
            ood=ood,
        )
    candidate = "PD-pattern candidate" if score >= threshold else "HC-pattern candidate"
    details = bundle.get("training_details", {})
    metrics = details.get("evaluation_metrics", {}) if isinstance(details, dict) else {}
    valid_metrics = {
        key: float(value)
        for key, value in metrics.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    }
    return PredictionResult(
        prediction_id=f"prd-{uuid.uuid4().hex[:12]}",
        status="EXPLORATORY_NOT_DOMAIN_VALIDATED",
        abstained=False,
        abstention_reasons=[],
        abstention_reason=None,
        model_id=str(details.get("model_id", "uams_logistic_research")),
        model_version=str(bundle.get("model_version", "unknown")),
        model_checksum=model_checksum,
        research_score=score,
        research_classification=candidate,
        calibration_status="UNCALIBRATED_DECISION_SCORE",
        uncertainty={"ood": ood.to_dict()},
        ood_status=ood.status.value,
        acquisition_domain_id=domain,
        capture_origin=context.capture_origin,
        score_kind="uncalibrated_logit",
        decision_threshold=threshold,
        model_evaluation_metrics=valid_metrics,
        domain_validation_status="NOT_VALIDATED",
        acquisition_domain_source=context.acquisition_domain_source,
        task_type=context.task_type,
        generated_utc=utc_now_iso(),
        research_only_disclaimer=M6_MEDICAL_DISCLAIMER,
    )
