"""Generate a local, privacy-conscious voice analysis report."""

from __future__ import annotations

import math
from datetime import UTC, datetime

DISCLAIMER = (
    "Research prototype only. Voice measures are not specific to Parkinson's disease. "
    "This report does not diagnose or rule out a condition and must not guide treatment."
)


def build_report(quality: dict, features: dict, preprocessing: dict, *, model_status: str) -> dict:
    """Return a JSON-ready report with no identity fields and a clear safety boundary."""
    clean_features = {}
    for key, value in features.items():
        if key in {
            "schema_version",
            "schema_fingerprint",
            "feature_config_fingerprint",
            "preprocessing_config_fingerprint",
        } and isinstance(value, str):
            clean_features[key] = value
        elif isinstance(value, (float, int)) and not isinstance(value, bool):
            clean_features[key] = float(value) if math.isfinite(value) else None
        else:
            clean_features[key] = None
    return {
        "report_version": "0.3.0",
        "generated_utc": datetime.now(UTC).isoformat(),
        "audio_quality": quality,
        "preprocessing": preprocessing,
        "features": clean_features,
        "feature_provenance": {
            "schema_version": clean_features.get("schema_version"),
            "schema_fingerprint": clean_features.get("schema_fingerprint"),
            "feature_config_fingerprint": clean_features.get("feature_config_fingerprint"),
            "preprocessing_config_fingerprint": clean_features.get(
                "preprocessing_config_fingerprint"
            ),
        },
        "model_assessment": {"status": model_status, "interpretation": DISCLAIMER},
        "clinical_disclaimer": DISCLAIMER,
        "stored_by_default": False,
    }
