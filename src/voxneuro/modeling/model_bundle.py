"""Versioned joblib bundles; load only model artifacts created by this trusted project."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

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
    load_domain_validation_report,
    validate_domain_validation_payload,
)

DEFAULT_ALLOWED_MISSING_FEATURES = ("jitter_local", "shimmer_local")


def make_bundle(
    model: Any,
    *,
    dataset_provenance: str,
    dataset_version: str,
    dataset_checksum_sha256: str,
    code_version: str,
    training_evaluation_receipt_sha256: str,
    validation_method: str,
    software_versions: dict[str, str],
    preprocessing_config: dict,
    feature_config: dict,
    allow_user_microphone_inference: bool = False,
    validated_input_domains: list[str] | None = None,
    domain_validation_report: Path | None = None,
    allowed_missing_features: tuple[str, ...] = DEFAULT_ALLOWED_MISSING_FEATURES,
    training_details: dict[str, Any] | None = None,
    training_distribution_manifest: dict[str, Any] | None = None,
    score_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wrap a fitted pipeline with complete data, feature, and domain metadata."""
    if validated_input_domains is not None and not isinstance(
        validated_input_domains, (list, tuple)
    ):
        raise ValueError("Validated input domains must be a list or tuple of strings.")
    requested_domains = list(validated_input_domains or [])
    allowed_missing = list(allowed_missing_features)
    if any(not isinstance(name, str) for name in allowed_missing):
        raise ValueError("Imputation-allowed feature names must be strings.")
    if any(not isinstance(domain, str) or not domain.strip() for domain in requested_domains):
        raise ValueError("Validated input domains must be non-empty strings.")
    domains = [canonicalize_domain(domain) for domain in requested_domains]
    if len(set(domains)) != len(domains):
        raise ValueError("Validated input domains must be unique after normalization.")
    if any(is_microphone_domain(domain) for domain in domains):
        raise ValueError("Microphone domains cannot be enabled in this prototype.")
    if domain_validation_report is None:
        if domains:
            raise ValueError(
                "A domain-validation report is required; a domain-name list is not evidence."
            )
        evidence_json = None
        evidence_sha256 = None
    else:
        evidence_json, evidence_sha256, evidence_domains = load_domain_validation_report(
            Path(domain_validation_report)
        )
        if domains and domains != evidence_domains:
            raise ValueError("Validated input domains do not match the evidence report.")
        domains = evidence_domains
    unknown_missing = set(allowed_missing) - set(FEATURE_NAMES)
    if unknown_missing:
        raise ValueError(f"Unknown imputation-allowed features: {sorted(unknown_missing)}")
    if (
        not dataset_version
        or not dataset_provenance
        or not validation_method
        or not software_versions
    ):
        raise ValueError("Dataset, validation, and software provenance must be recorded.")
    fingerprints = (dataset_checksum_sha256, code_version, training_evaluation_receipt_sha256)
    if any(
        not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value)
        for value in fingerprints
    ):
        raise ValueError(
            "Dataset, code, and evaluation receipt fingerprints must be SHA-256 values."
        )
    if not isinstance(preprocessing_config, dict) or not isinstance(feature_config, dict):
        raise ValueError("Audio and feature extraction configurations must be mappings.")
    if training_details is not None and not isinstance(training_details, dict):
        raise ValueError("Training details must be a mapping when provided.")
    if training_distribution_manifest is not None and not isinstance(
        training_distribution_manifest, dict
    ):
        raise ValueError("Training-distribution manifest must be a mapping when provided.")
    if score_contract is not None and not isinstance(score_contract, dict):
        raise ValueError("Score contract must be a mapping when provided.")
    if allow_user_microphone_inference:
        raise ValueError("Microphone inference cannot be enabled in this prototype.")
    distribution_digest = None
    if training_distribution_manifest is not None:
        distribution_digest = hashlib.sha256(
            json.dumps(
                training_distribution_manifest,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
    contract = dict(
        score_contract
        or {
            "method": "predict_proba",
            "kind": "uncalibrated_probability_score",
            "threshold": 0.5,
            "positive_class_label": "PD",
        }
    )
    return {
        "bundle_version": 4,
        "model_version": "0.4.0-research",
        "created_utc": datetime.now(UTC).isoformat(),
        "model": model,
        "feature_schema_version": SCHEMA_VERSION,
        "feature_schema_fingerprint": schema_fingerprint(),
        "feature_names": list(FEATURE_NAMES),
        "dataset_provenance": dataset_provenance,
        "dataset_version": dataset_version,
        "dataset_checksum_sha256": dataset_checksum_sha256,
        "code_version": code_version,
        "training_evaluation_receipt_sha256": training_evaluation_receipt_sha256,
        "validation_method": validation_method,
        "software_versions": dict(software_versions),
        "preprocessing_config": dict(preprocessing_config),
        "preprocessing_config_fingerprint": configuration_fingerprint(preprocessing_config),
        "feature_config": dict(feature_config),
        "feature_config_fingerprint": feature_config_fingerprint(feature_config),
        "training_details": dict(training_details or {}),
        "training_distribution_manifest": training_distribution_manifest,
        "training_distribution_manifest_sha256": distribution_digest,
        "score_contract": contract,
        "allowed_missing_features": allowed_missing,
        "research_only": True,
        "domain_compatibility_verified": bool(
            evidence_sha256 and domains and is_trusted_domain_validation_report(evidence_sha256)
        ),
        "validated_input_domains": domains,
        "domain_validation_evidence_json": evidence_json,
        "domain_validation_evidence_sha256": evidence_sha256,
        "allow_user_microphone_inference": bool(allow_user_microphone_inference),
    }


def save_bundle(bundle: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(digest + "\n", encoding="ascii")


def load_bundle(path: Path) -> dict:
    """Verify local artifact integrity before deserialization; never load user uploads.

    The checksum detects accidental or uncoordinated file changes; it is not a digital
    signature. The caller must still restrict loading to trusted, internally generated files.
    """
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    if not path.is_file() or not checksum_path.is_file():
        raise ValueError("Trusted model artifact or its SHA-256 sidecar is missing.")
    expected_checksum = checksum_path.read_text(encoding="ascii").strip().casefold()
    payload = path.read_bytes()
    actual_checksum = hashlib.sha256(payload).hexdigest()
    if expected_checksum != actual_checksum:
        raise ValueError("Model artifact SHA-256 does not match its integrity sidecar.")
    bundle = joblib.load(io.BytesIO(payload))
    if not isinstance(bundle, dict):
        raise ValueError("Model bundle must be a metadata dictionary.")
    required = {
        "bundle_version",
        "model",
        "feature_schema_version",
        "feature_schema_fingerprint",
        "feature_names",
        "dataset_version",
        "dataset_checksum_sha256",
        "code_version",
        "training_evaluation_receipt_sha256",
        "dataset_provenance",
        "validation_method",
        "created_utc",
        "model_version",
        "software_versions",
        "preprocessing_config",
        "preprocessing_config_fingerprint",
        "feature_config",
        "feature_config_fingerprint",
        "research_only",
        "domain_compatibility_verified",
        "validated_input_domains",
        "domain_validation_evidence_json",
        "domain_validation_evidence_sha256",
        "allow_user_microphone_inference",
        "allowed_missing_features",
        "training_distribution_manifest",
        "training_distribution_manifest_sha256",
        "score_contract",
    }
    missing = required - bundle.keys()
    if missing:
        raise ValueError(f"Model bundle is missing metadata: {sorted(missing)}")
    if (
        bundle["bundle_version"] != 4
        or bundle["feature_schema_version"] != SCHEMA_VERSION
        or bundle["feature_schema_fingerprint"] != schema_fingerprint()
    ):
        raise ValueError("Model bundle version or feature schema is incompatible.")
    if bundle["feature_names"] != list(FEATURE_NAMES):
        raise ValueError("Model bundle feature order is incompatible.")
    if not isinstance(bundle["validated_input_domains"], list) or any(
        not isinstance(domain, str) or not domain.strip()
        for domain in bundle["validated_input_domains"]
    ):
        raise ValueError("Model bundle input domains are invalid.")
    allowed_missing = bundle["allowed_missing_features"]
    if (
        not isinstance(allowed_missing, list)
        or any(not isinstance(name, str) for name in allowed_missing)
        or set(allowed_missing) - set(FEATURE_NAMES)
    ):
        raise ValueError("Model bundle missing-feature policy is invalid.")
    if not isinstance(bundle["software_versions"], dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in bundle["software_versions"].items()
    ):
        raise ValueError("Model bundle software-version metadata is invalid.")
    if bundle["research_only"] is not True:
        raise ValueError("Only research-only model bundles are accepted.")
    evidence_json = bundle["domain_validation_evidence_json"]
    evidence_sha256 = bundle["domain_validation_evidence_sha256"]
    if evidence_json is None and evidence_sha256 is None:
        evidence_domains = []
    else:
        try:
            evidence_domains = validate_domain_validation_payload(evidence_json, evidence_sha256)
        except ValueError as exc:
            raise ValueError(f"Model domain-validation evidence is invalid: {exc}") from exc
    if bundle["validated_input_domains"] != evidence_domains or bundle[
        "domain_compatibility_verified"
    ] is not bool(
        evidence_sha256
        and evidence_domains
        and is_trusted_domain_validation_report(evidence_sha256)
    ):
        raise ValueError("Model domain-verification metadata is inconsistent with its evidence.")
    if bundle["allow_user_microphone_inference"] is not False:
        raise ValueError("Microphone inference is disabled for this prototype.")
    if (
        not bundle["software_versions"]
        or not isinstance(bundle["feature_config"], dict)
        or not bundle["feature_config"]
        or not isinstance(bundle["preprocessing_config"], dict)
        or not bundle["preprocessing_config"]
    ):
        raise ValueError("Model bundle is missing software or feature-extraction provenance.")
    distribution = bundle["training_distribution_manifest"]
    distribution_digest = bundle["training_distribution_manifest_sha256"]
    if (distribution is None) != (distribution_digest is None):
        raise ValueError(
            "Training-distribution manifest and fingerprint must be supplied together."
        )
    if distribution is not None:
        if not isinstance(distribution, dict):
            raise ValueError("Training-distribution manifest must be a mapping.")
        actual_distribution_digest = hashlib.sha256(
            json.dumps(distribution, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                "utf-8"
            )
        ).hexdigest()
        if actual_distribution_digest != distribution_digest:
            raise ValueError("Training-distribution manifest SHA-256 is invalid.")
        if (
            distribution.get("schema_version") != "voxneuro.training_distribution.v1"
            or distribution.get("feature_schema_version") != SCHEMA_VERSION
            or distribution.get("feature_schema_fingerprint") != schema_fingerprint()
            or distribution.get("feature_names") != list(FEATURE_NAMES)
        ):
            raise ValueError(
                "Training-distribution manifest is incompatible with this feature schema."
            )
        statistics = distribution.get("statistics")
        if not isinstance(statistics, dict) or set(statistics) != set(FEATURE_NAMES):
            raise ValueError("Training-distribution statistics do not cover the complete schema.")
        required_statistics = {"n", "missing_rate", "mean", "std", "min", "max", "q01", "q99"}
        for name, stat in statistics.items():
            if not isinstance(stat, dict) or required_statistics - stat.keys():
                raise ValueError(f"Training-distribution statistics are incomplete for {name}.")
            if isinstance(stat["n"], bool) or not isinstance(stat["n"], int) or stat["n"] < 1:
                raise ValueError(f"Training-distribution sample count is invalid for {name}.")
            numeric_values = [stat[key] for key in required_statistics - {"n"}]
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in numeric_values
            ):
                raise ValueError(f"Training-distribution values are invalid for {name}.")
    contract = bundle["score_contract"]
    if not isinstance(contract, dict) or contract.get("method") not in {
        "decision_function",
        "predict_proba",
    }:
        raise ValueError("Model score contract is invalid.")
    threshold = contract.get("threshold")
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(float(threshold))
    ):
        raise ValueError("Model decision threshold must be a finite number.")
    if bundle["feature_config_fingerprint"] != feature_config_fingerprint(bundle["feature_config"]):
        raise ValueError("Model bundle feature configuration fingerprint is invalid.")
    if bundle["preprocessing_config_fingerprint"] != configuration_fingerprint(
        bundle["preprocessing_config"]
    ):
        raise ValueError("Model bundle preprocessing configuration fingerprint is invalid.")
    return bundle
