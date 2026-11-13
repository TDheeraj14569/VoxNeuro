"""Strict, approved-domain prediction gate; exploratory scoring lives in its own module.

This module does not authorize a user microphone or uploaded recording. The distinct exploratory
candidate path is implemented by ``modeling.exploratory`` and remains unvalidated and non-clinical.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any

import numpy as np
import pandas as pd

from voxneuro.exceptions import ModelCompatibilityError
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling.domains import (
    canonicalize_domain,
    is_microphone_domain,
    is_trusted_domain_validation_report,
    validate_domain_validation_payload,
)

VALID_CAPTURE_ORIGINS = frozenset(
    {
        "pre_recorded_research",
        "controlled_research_session",
        "user_upload",
        "live_browser_mic",
        "live_app_mic",
        "unknown",
    }
)

ELIGIBLE_CAPTURE_ORIGINS = frozenset({"pre_recorded_research", "controlled_research_session"})


@dataclass(frozen=True)
class InputCaptureContext:
    """Explicit acquisition context and provenance for incoming acoustic records."""

    capture_origin: str
    task_type: str = "sustained_vowel"
    verified_origin: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def predict_research(
    bundle: dict,
    features: dict[str, float | str],
    *,
    input_domain: str,
    capture_origin: str = "pre_recorded_research",
    capture_context: InputCaptureContext | dict[str, Any] | None = None,
) -> dict[str, object]:
    """Predict only when safety metadata, domain, origin, schema, and features all match."""
    effective_origin = capture_origin
    if capture_context is not None:
        if isinstance(capture_context, InputCaptureContext):
            effective_origin = capture_context.capture_origin
            if capture_context.task_type != "sustained_vowel":
                raise ModelCompatibilityError(
                    f"Task type {capture_context.task_type!r} is not compatible "
                    "with sustained-vowel model."
                )
            if not capture_context.verified_origin:
                raise ModelCompatibilityError("Input capture origin could not be verified.")
        elif isinstance(capture_context, dict):
            effective_origin = capture_context.get("capture_origin", "unknown")
            task_type = capture_context.get("task_type", "sustained_vowel")
            if task_type != "sustained_vowel":
                raise ModelCompatibilityError(
                    f"Task type {task_type!r} is not compatible with sustained-vowel model."
                )
            if capture_context.get("verified_origin") is False:
                raise ModelCompatibilityError("Input capture origin could not be verified.")
        else:
            raise ModelCompatibilityError("Invalid capture_context type.")

    if (
        effective_origin is None
        or not isinstance(effective_origin, str)
        or not effective_origin.strip()
        or effective_origin.casefold() in {"unknown", "none", "null"}
    ):
        raise ModelCompatibilityError(
            "Acquisition origin is missing or unknown; inference must fail closed."
        )

    try:
        norm_origin = canonicalize_domain(effective_origin)
    except ValueError as exc:
        raise ModelCompatibilityError(f"Invalid capture origin: {exc}") from exc

    if is_microphone_domain(norm_origin) or any(
        token
        in {"upload", "user_upload", "live", "browser", "mic", "microphone", "smartphone", "laptop"}
        for token in norm_origin.split("_")
    ):
        raise ModelCompatibilityError(
            f"Capture origin {effective_origin!r} is a microphone or user-upload source "
            "and is ineligible for inference."
        )

    if norm_origin not in ELIGIBLE_CAPTURE_ORIGINS:
        raise ModelCompatibilityError(
            f"Capture origin {effective_origin!r} is not eligible for inference."
        )

    try:
        normalized_domain = canonicalize_domain(input_domain)
    except ValueError as exc:
        raise ModelCompatibilityError(str(exc)) from exc
    if is_microphone_domain(normalized_domain):
        raise ModelCompatibilityError("Microphone inference is disabled for this prototype.")
    required_metadata = {
        "feature_schema_version",
        "feature_schema_fingerprint",
        "feature_names",
        "feature_config",
        "feature_config_fingerprint",
        "preprocessing_config",
        "preprocessing_config_fingerprint",
        "research_only",
        "domain_compatibility_verified",
        "validated_input_domains",
        "domain_validation_evidence_json",
        "domain_validation_evidence_sha256",
        "allow_user_microphone_inference",
        "allowed_missing_features",
        "model",
    }
    missing_metadata = required_metadata - bundle.keys()
    if missing_metadata:
        raise ModelCompatibilityError(
            f"Model bundle is missing safety metadata: {sorted(missing_metadata)}"
        )
    if bundle["research_only"] is not True:
        raise ModelCompatibilityError("Only explicitly research-only bundles are accepted.")
    if not callable(getattr(bundle["model"], "predict", None)):
        raise ModelCompatibilityError("Model bundle does not contain a usable fitted estimator.")
    if bundle["feature_schema_version"] != SCHEMA_VERSION:
        raise ModelCompatibilityError(
            "Model feature-schema version does not match this application."
        )
    if bundle["feature_names"] != list(FEATURE_NAMES):
        raise ModelCompatibilityError("Model feature order does not match this application.")
    if bundle["feature_schema_fingerprint"] != schema_fingerprint():
        raise ModelCompatibilityError("Model feature-schema fingerprint does not match this app.")
    if not isinstance(bundle["feature_config"], dict) or bundle[
        "feature_config_fingerprint"
    ] != feature_config_fingerprint(bundle["feature_config"]):
        raise ModelCompatibilityError("Model feature-extraction configuration is inconsistent.")
    if not isinstance(bundle["preprocessing_config"], dict) or bundle[
        "preprocessing_config_fingerprint"
    ] != configuration_fingerprint(bundle["preprocessing_config"]):
        raise ModelCompatibilityError("Model preprocessing configuration is inconsistent.")
    if bundle["allow_user_microphone_inference"] is not False:
        raise ModelCompatibilityError("Microphone inference is disabled for this prototype.")
    evidence_json = bundle["domain_validation_evidence_json"]
    evidence_sha256 = bundle["domain_validation_evidence_sha256"]
    if evidence_json is None and evidence_sha256 is None:
        evidence_domains = []
    else:
        try:
            evidence_domains = validate_domain_validation_payload(evidence_json, evidence_sha256)
        except ValueError as exc:
            raise ModelCompatibilityError(
                f"Model domain-validation evidence is invalid: {exc}"
            ) from exc
    validated_domains = bundle["validated_input_domains"]
    verified = bool(evidence_domains and is_trusted_domain_validation_report(evidence_sha256))
    if bundle["domain_compatibility_verified"] is not verified:
        raise ModelCompatibilityError("Model input-domain compatibility metadata is inconsistent.")
    if not verified:
        raise ModelCompatibilityError("Model input-domain compatibility has not been verified.")
    if validated_domains != evidence_domains or normalized_domain not in evidence_domains:
        raise ModelCompatibilityError(
            f"Input domain {input_domain!r} is not validated for this model."
        )
    if features.get("schema_version") != SCHEMA_VERSION:
        raise ModelCompatibilityError("Incoming feature schema version is missing or incompatible.")
    metadata_names = {
        "schema_version",
        "schema_fingerprint",
        "feature_config_fingerprint",
        "preprocessing_config_fingerprint",
    }
    if set(features) != set(FEATURE_NAMES) | metadata_names:
        raise ModelCompatibilityError(
            "Incoming features must contain every measurement and provenance field exactly once."
        )
    measurement_names = [name for name in features if name in FEATURE_NAMES]
    if measurement_names != FEATURE_NAMES:
        raise ModelCompatibilityError(
            "Incoming features must contain every required measurement in the exact schema order."
        )
    if features.get("schema_fingerprint") != schema_fingerprint():
        raise ModelCompatibilityError(
            "Incoming feature-schema fingerprint is missing or incompatible."
        )
    if features.get("feature_config_fingerprint") != bundle["feature_config_fingerprint"]:
        raise ModelCompatibilityError(
            "Incoming feature-extraction settings do not match the model bundle."
        )
    if (
        features.get("preprocessing_config_fingerprint")
        != bundle["preprocessing_config_fingerprint"]
    ):
        raise ModelCompatibilityError(
            "Incoming preprocessing settings do not match the model bundle."
        )
    if not isinstance(bundle["allowed_missing_features"], list):
        raise ModelCompatibilityError("Model bundle missing-feature policy is invalid.")
    if any(not isinstance(name, str) for name in bundle["allowed_missing_features"]):
        raise ModelCompatibilityError("Model bundle missing-feature policy is invalid.")
    allowed_missing = set(bundle["allowed_missing_features"])
    if allowed_missing - set(FEATURE_NAMES):
        raise ModelCompatibilityError("Model bundle allows missing values for unknown features.")
    row: dict[str, float] = {}
    for name in FEATURE_NAMES:
        value = features[name]
        if isinstance(value, (bool, np.bool_)):
            raise ModelCompatibilityError(f"Feature {name!r} must be numeric, not boolean.")
        if not isinstance(value, Real):
            raise ModelCompatibilityError(f"Feature {name!r} is not a numeric measurement.")
        numeric = float(value)
        if math.isfinite(numeric):
            row[name] = numeric
        elif math.isnan(numeric) and name in allowed_missing:
            row[name] = float("nan")
        else:
            raise ModelCompatibilityError(f"Feature {name!r} is missing or non-finite.")
    frame = pd.DataFrame([row], columns=FEATURE_NAMES)
    prediction = int(bundle["model"].predict(frame)[0])
    return {
        "experimental_class": prediction,
        "clinical_probability": None,
        "status": "experimental; not for clinical use",
    }
