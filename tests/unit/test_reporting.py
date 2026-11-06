import json
import math

from voxneuro.features.schema import SCHEMA_VERSION
from voxneuro.reporting.report import build_report


def test_report_preserves_schema_version_and_sanitizes_measurements():
    report = build_report(
        {},
        {
            "schema_version": SCHEMA_VERSION,
            "schema_fingerprint": "a" * 64,
            "feature_config_fingerprint": "b" * 64,
            "preprocessing_config_fingerprint": "c" * 64,
            "f0_mean_hz": 180.0,
            "jitter_local": math.nan,
            "extra_text": "not feature metadata",
        },
        {},
        model_status="Unavailable",
    )
    assert report["features"]["schema_version"] == SCHEMA_VERSION
    assert report["feature_provenance"]["schema_fingerprint"] == "a" * 64
    assert report["feature_provenance"]["feature_config_fingerprint"] == "b" * 64
    assert report["features"]["preprocessing_config_fingerprint"] == "c" * 64
    assert report["features"]["f0_mean_hz"] == 180.0
    assert report["features"]["jitter_local"] is None
    assert report["features"]["extra_text"] is None
    json.dumps(report, allow_nan=False)
