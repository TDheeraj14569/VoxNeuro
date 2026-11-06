import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier

from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.modeling import domains as domain_safety
from voxneuro.modeling.model_bundle import make_bundle
from voxneuro.modeling.prediction import predict_research


def test_research_bundle_prediction_contract(tmp_path, monkeypatch):
    X = pd.DataFrame(np.zeros((2, len(FEATURE_NAMES))), columns=FEATURE_NAMES)
    model = DummyClassifier(strategy="constant", constant=1).fit(X, [0, 1])
    report = tmp_path / "domain_validation.json"
    report.write_text(
        json.dumps(
            {
                "report_version": "1.0",
                "validated_utc": "2026-11-06T00:00:00+00:00",
                "validation_protocol": "held-out synthetic test protocol",
                "validation_dataset": "synthetic test cohort",
                "independent_validation": True,
                "validated_input_domains": ["uams_telephone"],
                "results": {"n_participants": 20, "balanced_accuracy": 0.7},
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(report.read_bytes()).hexdigest()
    monkeypatch.setattr(
        domain_safety, "TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256", frozenset({digest})
    )
    bundle = make_bundle(
        model,
        dataset_provenance="synthetic",
        dataset_version="synthetic-v1",
        dataset_checksum_sha256="a" * 64,
        code_version="b" * 64,
        training_evaluation_receipt_sha256="c" * 64,
        validation_method="unit test",
        software_versions={"python": "3.12"},
        preprocessing_config={"target_sample_rate": 16000},
        feature_config={"schema_version": SCHEMA_VERSION},
        validated_input_domains=["uams_telephone"],
        domain_validation_report=report,
    )
    output = predict_research(
        bundle,
        {
            **dict.fromkeys(FEATURE_NAMES, 0.0),
            "schema_version": SCHEMA_VERSION,
            "schema_fingerprint": schema_fingerprint(),
            "feature_config_fingerprint": feature_config_fingerprint(
                {"schema_version": SCHEMA_VERSION}
            ),
            "preprocessing_config_fingerprint": configuration_fingerprint(
                {"target_sample_rate": 16000}
            ),
        },
        input_domain="uams_telephone",
    )
    assert output["experimental_class"] == 1
    assert output["clinical_probability"] is None
    assert bundle["feature_schema_version"] == SCHEMA_VERSION
