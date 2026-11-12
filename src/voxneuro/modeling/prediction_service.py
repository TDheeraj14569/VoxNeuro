"""Standalone M6 fail-closed research prediction and mandatory abstention service."""

from __future__ import annotations

import json
import math
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from voxneuro.audio.io import decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.validation import AudioValidationConfig, validate_audio
from voxneuro.config import load_config
from voxneuro.features.extractor import extract_features
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
)
from voxneuro.modeling.domains import (
    TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256,
    is_microphone_domain,
    is_trusted_domain_validation_report,
)
from voxneuro.modeling.model_registry import (
    RegisteredModel,
    verify_and_load_registered_bundle,
)
from voxneuro.modeling.prediction import ELIGIBLE_CAPTURE_ORIGINS, InputCaptureContext
from voxneuro.study.audit import log_audit_event
from voxneuro.study.database import transaction
from voxneuro.study.schema import utc_now_iso
from voxneuro.study.session import preflight_session_ingestion

AUDIO_CONFIG = load_config("audio_config.yaml")
FEATURE_CONFIG = load_config("feature_config.yaml")
MODEL_CONFIG = load_config("model_config.yaml")

M6_MEDICAL_DISCLAIMER = (
    "VoxNeuro is an experimental research tool. It is NOT a medical device and does NOT diagnose, "
    "rule out, treat, or monitor Parkinson's disease or any medical condition. Consult a qualified "
    "clinician for any health or voice concerns."
)


@dataclass(frozen=True)
class PredictionResult:
    """Fail-closed M6 research inference response with mandatory disclaimer and provenance."""

    prediction_id: str
    status: str
    abstained: bool
    abstention_reasons: list[str]
    abstention_reason: str | None
    model_id: str | None
    model_version: str
    model_checksum: str | None
    research_score: float | None
    research_classification: str | None
    calibration_status: str
    uncertainty: dict[str, Any] = field(default_factory=dict)
    ood_status: str = "NOT_EVALUATED"
    acquisition_domain_id: str = "unknown"
    capture_origin: str = "unknown"
    retention_persisted: bool = False
    research_only_disclaimer: str = M6_MEDICAL_DISCLAIMER
    generated_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _assess_ood_features(
    features: dict[str, Any],
    distribution_stats: dict[str, dict[str, float]] | None,
    *,
    z_threshold: float = 6.0,
    max_extreme_features: int = 3,
) -> tuple[bool, str, dict[str, Any]]:
    """Detect severe out-of-distribution feature vectors relative to training statistics."""
    if not distribution_stats:
        return False, "OOD_REFERENCE_UNAVAILABLE", {"checked_features": 0, "extreme_features": []}
    extreme: list[str] = []
    max_z = 0.0
    checked = 0
    for name in FEATURE_NAMES:
        val = features.get(name)
        stat = distribution_stats.get(name)
        if val is None or stat is None:
            continue
        fval = float(val)
        if not math.isfinite(fval):
            continue
        checked += 1
        z = abs(fval - float(stat["mean"])) / max(float(stat["std"]), 1e-6)
        max_z = max(max_z, z)
        if z > z_threshold:
            extreme.append(name)
    is_in_dist = len(extreme) < max_extreme_features
    status = "WITHIN_TRAINING_RANGE" if is_in_dist else "OUT_OF_DISTRIBUTION"
    return (
        is_in_dist,
        status,
        {
            "checked_features": checked,
            "extreme_feature_count": len(extreme),
            "max_abs_z": round(max_z, 3),
        },
    )


def _record_abstention_event(
    conn: sqlite3.Connection | None,
    *,
    session_id: str | None,
    model_id: str | None,
    reason_codes: list[str],
    reason_detail: str,
    acquisition_domain_id: str,
    capture_origin: str,
) -> None:
    if conn is None:
        return
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='abstention_events';"
    ).fetchone()
    if not row:
        return
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO abstention_events (
                abstention_id, session_id, model_id, reason_code, reason_detail,
                acquisition_domain_id, capture_origin, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                f"abs-{uuid.uuid4().hex[:12]}",
                session_id,
                model_id,
                ";".join(reason_codes) or "UNSPECIFIED",
                reason_detail,
                acquisition_domain_id,
                capture_origin,
                utc_now_iso(),
            ),
        )


def _persist_prediction_if_permitted(
    conn: sqlite3.Connection | None,
    result: PredictionResult,
    *,
    session_id: str | None,
    participant_id: str | None,
    user_id: str | None,
    retention_permitted: bool,
) -> bool:
    """Persist prediction records ONLY when explicit retention opt-in is verified."""
    if conn is None or not retention_permitted:
        return False
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prediction_records';"
    ).fetchone()
    if not table_exists:
        return False
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO prediction_records (
                prediction_id, session_id, participant_id, user_id, model_id,
                model_version, model_checksum, acquisition_domain_id, capture_origin,
                research_score, research_classification, calibration_status, uncertainty_json,
                abstained, abstention_reason, retention_permitted, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
            """,
            (
                result.prediction_id,
                session_id,
                participant_id,
                user_id,
                result.model_id,
                result.model_version,
                result.model_checksum or "none",
                result.acquisition_domain_id,
                result.capture_origin,
                result.research_score,
                result.research_classification,
                result.calibration_status,
                json.dumps(result.uncertainty, sort_keys=True),
                1 if result.abstained else 0,
                result.abstention_reason,
                result.generated_utc,
            ),
        )
        log_audit_event(
            conn,
            operation_type="PREDICTION_RECORD_PERSISTED",
            entity_type="prediction_record",
            entity_id=result.prediction_id,
            actor_role="system",
            details={
                "abstained": result.abstained,
                "model_id": result.model_id,
                "acquisition_domain_id": result.acquisition_domain_id,
            },
        )
    return True


def run_prediction_service(
    *,
    features: dict[str, Any] | None,
    quality_valid: bool,
    capture_context: InputCaptureContext,
    input_domain: str = "unknown",
    conn: sqlite3.Connection | None = None,
    model_id: str | None = None,
    session_id: str | None = None,
    participant_id: str | None = None,
    user_id: str | None = None,
    allow_prediction_retention: bool = False,
) -> PredictionResult:
    """Execute fail-closed M6 research inference or abstain with explicit human-readable reasons."""
    pred_id = f"prd-{uuid.uuid4().hex[:12]}"
    reasons: list[str] = []
    reason_messages: list[str] = []

    if not quality_valid or features is None:
        reasons.append("QUALITY_GATE_FAILED")
        reason_messages.append("Recording quality checks did not pass or features are unavailable.")

    if capture_context.capture_origin not in ELIGIBLE_CAPTURE_ORIGINS:
        reasons.append("DISALLOWED_CAPTURE_ORIGIN")
        reason_messages.append(
            "Automated prediction is disabled for capture origin "
            f"'{capture_context.capture_origin}'."
        )

    if is_microphone_domain(input_domain) or (
        not bool(MODEL_CONFIG.get("allow_user_microphone_inference", False))
        and capture_context.capture_origin in {"live_browser_mic", "user_upload", "live_app_mic"}
    ):
        if "DISALLOWED_CAPTURE_ORIGIN" not in reasons:
            reasons.append("MICROPHONE_INFERENCE_DISABLED")
            reason_messages.append(
                "Live microphone and consumer upload classification remain disabled "
                "until prospective domain validation completes."
            )

    if features is not None and features.get("schema_version") != SCHEMA_VERSION:
        reasons.append("SCHEMA_VERSION_MISMATCH")
        reason_messages.append(f"Feature schema mismatch (expected {SCHEMA_VERSION}).")

    # Optional M5 study session consent/DUA gate
    retention_ok = bool(allow_prediction_retention)
    if conn is not None and session_id is not None:
        preflight_ok, preflight_msg, preflight_ctx = preflight_session_ingestion(
            conn,
            session_id,
            tasks_to_process=["sustained_vowel"],
            requested_operation="feature_extraction",
        )
        if not preflight_ok:
            reasons.append("CONSENT_OR_DUA_BLOCKED")
            reason_messages.append(preflight_msg)
            retention_ok = False
        else:
            consent = preflight_ctx["consent"]
            participant_id = participant_id or preflight_ctx["participant"].participant_id
            retention_ok = bool(
                allow_prediction_retention and consent.permission_to_retain_derived_features
            )
    elif conn is not None and user_id is not None and allow_prediction_retention:
        urow = conn.execute(
            "SELECT prediction_retention_opt_in FROM users WHERE user_id = ?;", (user_id,)
        ).fetchone()
        retention_ok = bool(urow and urow["prediction_retention_opt_in"])
    else:
        retention_ok = False if conn is None else bool(allow_prediction_retention)

    registered_model: RegisteredModel | None = None
    bundle: dict[str, Any] | None = None
    if not model_id or conn is None:
        reasons.append("NO_APPROVED_MODEL_REGISTERED")
        reason_messages.append(
            "No externally validated and approved research prediction model is currently active "
            "for your recording domain."
        )
    else:
        try:
            registered_model, bundle = verify_and_load_registered_bundle(
                conn,
                model_id,
                required_domain_id=input_domain,
                expected_schema_version=SCHEMA_VERSION,
            )
        except Exception as exc:
            reasons.append("MODEL_GOVERNANCE_OR_CHECKSUM_BLOCKED")
            reason_messages.append(f"Model governance check abstained: {exc}")

    # Additional M4 bundle domain validation gate
    if bundle is not None:
        report_sha = bundle.get("domain_validation_evidence_sha256") or bundle.get(
            "domain_validation_report_sha256"
        )
        if (
            not bundle.get("domain_compatibility_verified")
            or not is_trusted_domain_validation_report(report_sha)
            or not TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256
        ):
            reasons.append("EXTERNAL_DOMAIN_VALIDATION_PENDING")
            reason_messages.append(
                "Cross-domain external validation is still pending; model predictions are withheld."
            )

    # Check completeness & OOD before scoring
    ood_status = "NOT_EVALUATED"
    ood_meta: dict[str, Any] = {}
    if features is not None:
        missing_keys = [
            k
            for k in FEATURE_NAMES
            if k not in features
            or (isinstance(features[k], float) and not math.isfinite(features[k]))
            or features[k] is None
        ]
        if len(missing_keys) > 3:
            reasons.append("EXCESSIVE_MISSING_FEATURES")
            reason_messages.append(
                f"Too many acoustic measurements were undefined ({len(missing_keys)})."
            )
        dist_stats = (
            registered_model.metadata.get("feature_distribution_stats")
            if registered_model
            else None
        )
        in_dist, ood_status, ood_meta = _assess_ood_features(features, dist_stats)
        if not dist_stats:
            reasons.append("OOD_REFERENCE_UNAVAILABLE")
            reason_messages.append(
                "Training distribution statistics are unavailable for OOD assessment."
            )
        elif not in_dist:
            reasons.append("OUT_OF_DISTRIBUTION_FEATURES")
            reason_messages.append(
                "Voice measurements fall outside the distribution of the model's training cohort."
            )

    # ABSTAIN FAIL-CLOSED
    if reasons or bundle is None or registered_model is None or features is None:
        combined_msg = (
            " ".join(reason_messages) or "Prediction withheld by fail-closed safety rules."
        )
        abstained_result = PredictionResult(
            prediction_id=pred_id,
            status="ABSTAINED_FAIL_CLOSED",
            abstained=True,
            abstention_reasons=reasons or ["FAIL_CLOSED_DEFAULT"],
            abstention_reason=combined_msg,
            model_id=model_id,
            model_version=registered_model.model_version if registered_model else "none",
            model_checksum=registered_model.artifact_sha256 if registered_model else None,
            research_score=None,
            research_classification=None,
            calibration_status=registered_model.calibration_status
            if registered_model
            else "NOT_APPLICABLE",
            uncertainty={"ood": ood_meta},
            ood_status=ood_status,
            acquisition_domain_id=input_domain,
            capture_origin=capture_context.capture_origin,
            retention_persisted=False,
        )
        _record_abstention_event(
            conn,
            session_id=session_id,
            model_id=model_id,
            reason_codes=abstained_result.abstention_reasons,
            reason_detail=combined_msg,
            acquisition_domain_id=input_domain,
            capture_origin=capture_context.capture_origin,
        )
        persisted = _persist_prediction_if_permitted(
            conn,
            abstained_result,
            session_id=session_id,
            participant_id=participant_id,
            user_id=user_id,
            retention_permitted=retention_ok,
        )
        if persisted:
            return PredictionResult(**{**abstained_result.to_dict(), "retention_persisted": True})
        return abstained_result

    # VERIFIED RESEARCH SCORE COMPUTATION (only reached when all M4/M5/M6 gates pass)
    if bundle.get("feature_config_fingerprint") != feature_config_fingerprint(
        FEATURE_CONFIG
    ) or bundle.get("preprocessing_config_fingerprint") != configuration_fingerprint(AUDIO_CONFIG):
        return PredictionResult(
            prediction_id=pred_id,
            status="ABSTAINED_FAIL_CLOSED",
            abstained=True,
            abstention_reasons=["CONFIGURATION_FINGERPRINT_MISMATCH"],
            abstention_reason=(
                "Audio or feature extraction configuration does not match the registered model."
            ),
            model_id=registered_model.model_id,
            model_version=registered_model.model_version,
            model_checksum=registered_model.artifact_sha256,
            research_score=None,
            research_classification=None,
            calibration_status=registered_model.calibration_status,
            ood_status=ood_status,
            acquisition_domain_id=input_domain,
            capture_origin=capture_context.capture_origin,
        )

    X_row = pd.DataFrame(
        [[features.get(col) for col in FEATURE_NAMES]], columns=list(FEATURE_NAMES)
    )
    estimator = bundle["model"]
    if not hasattr(estimator, "predict_proba"):
        return PredictionResult(
            prediction_id=pred_id,
            status="ABSTAINED_FAIL_CLOSED",
            abstained=True,
            abstention_reasons=["NON_PROBABILISTIC_ESTIMATOR"],
            abstention_reason="Model estimator does not provide continuous probability outputs.",
            model_id=registered_model.model_id,
            model_version=registered_model.model_version,
            model_checksum=registered_model.artifact_sha256,
            research_score=None,
            research_classification=None,
            calibration_status=registered_model.calibration_status,
            uncertainty={"ood": ood_meta},
            ood_status=ood_status,
            acquisition_domain_id=input_domain,
            capture_origin=capture_context.capture_origin,
        )

    score = float(estimator.predict_proba(X_row)[0, 1])
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        return PredictionResult(
            prediction_id=pred_id,
            status="ABSTAINED_FAIL_CLOSED",
            abstained=True,
            abstention_reasons=["NON_FINITE_MODEL_OUTPUT"],
            abstention_reason="Model estimator returned non-finite or out-of-range output.",
            model_id=registered_model.model_id,
            model_version=registered_model.model_version,
            model_checksum=registered_model.artifact_sha256,
            research_score=None,
            research_classification=None,
            calibration_status=registered_model.calibration_status,
            uncertainty={"ood": ood_meta},
            ood_status=ood_status,
            acquisition_domain_id=input_domain,
            capture_origin=capture_context.capture_origin,
        )

    band = (
        "LOW_RESEARCH_SIGNAL"
        if score < 0.33
        else ("MODERATE_RESEARCH_SIGNAL" if score < 0.67 else "ELEVATED_RESEARCH_SIGNAL")
    )
    scored_result = PredictionResult(
        prediction_id=pred_id,
        status="RESEARCH_SCORE_RETURNED",
        abstained=False,
        abstention_reasons=[],
        abstention_reason=None,
        model_id=registered_model.model_id,
        model_version=registered_model.model_version,
        model_checksum=registered_model.artifact_sha256,
        research_score=round(score, 4),
        research_classification=band,
        calibration_status=registered_model.calibration_status,
        uncertainty={"ood": ood_meta, "note": "Research score only; not a diagnostic probability."},
        ood_status=ood_status,
        acquisition_domain_id=input_domain,
        capture_origin=capture_context.capture_origin,
        retention_persisted=False,
    )
    persisted = _persist_prediction_if_permitted(
        conn,
        scored_result,
        session_id=session_id,
        participant_id=participant_id,
        user_id=user_id,
        retention_permitted=retention_ok,
    )
    if persisted:
        return PredictionResult(**{**scored_result.to_dict(), "retention_persisted": True})
    return scored_result


def evaluate_audio_bytes_research(
    audio_bytes: bytes,
    *,
    capture_context: InputCaptureContext,
    input_domain: str = "unknown",
    conn: sqlite3.Connection | None = None,
    model_id: str | None = None,
    session_id: str | None = None,
    participant_id: str | None = None,
    user_id: str | None = None,
    allow_prediction_retention: bool = False,
) -> dict[str, Any]:
    """End-to-end M6 evaluation: decode -> quality -> Core39 -> fail-closed prediction."""
    audio_cfg = dict(AUDIO_CONFIG)
    feature_cfg = dict(FEATURE_CONFIG)
    feature_cfg.pop("schema_version", None)
    validation_cfg = AudioValidationConfig.from_dict(audio_cfg, feature_cfg)

    record = decode_audio(audio_bytes)
    quality = validate_audio(record, validation_cfg)
    if not quality.valid:
        prediction = run_prediction_service(
            features=None,
            quality_valid=False,
            capture_context=capture_context,
            input_domain=input_domain,
            conn=conn,
            model_id=model_id,
            session_id=session_id,
            participant_id=participant_id,
            user_id=user_id,
            allow_prediction_retention=False,
        )
        return {"record": record, "quality": quality, "features": None, "prediction": prediction}

    processed = preprocess_audio(
        record,
        target_sample_rate=int(audio_cfg["target_sample_rate"]),
        silence_relative_db=float(audio_cfg["silence_relative_db"]),
        mono_policy=str(audio_cfg["mono_policy"]),
        validation_config=validation_cfg,
    )
    features = extract_features(
        processed.samples,
        processed.sample_rate,
        original_sample_rate=record.sample_rate,
        preprocessing_config_fingerprint=configuration_fingerprint(audio_cfg),
        **feature_cfg,
    )
    prediction = run_prediction_service(
        features=features,
        quality_valid=True,
        capture_context=capture_context,
        input_domain=input_domain,
        conn=conn,
        model_id=model_id,
        session_id=session_id,
        participant_id=participant_id,
        user_id=user_id,
        allow_prediction_retention=allow_prediction_retention,
    )
    return {"record": record, "quality": quality, "features": features, "prediction": prediction}
