"""Canonical recording-domain names and auditable validation-evidence checks."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from numbers import Real
from pathlib import Path

MICROPHONE_DOMAIN_TOKENS = frozenset(
    {
        "mic",
        "microphone",
        "smartphone",
        "mobile",
        "cellphone",
        "phone",
        "browser",
        "web",
        "laptop",
        "computer",
        "desktop",
        "device",
        "iphone",
        "ipad",
        "android",
        "webcam",
        "headset",
        "streamlit",
        "getusermedia",
        "live",
    }
)
MAX_DOMAIN_REPORT_BYTES = 1_000_000
# A report is not approval by itself. Maintainers must review it and add its SHA-256 here.
TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256: frozenset[str] = frozenset()


def canonicalize_domain(value: object) -> str:
    """Normalize a domain label and reject values that cannot name a domain."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("An explicit input recording domain is required as a non-empty string.")
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    if not normalized:
        raise ValueError("An explicit input recording domain is required as a non-empty string.")
    return normalized


def is_microphone_domain(domain: str) -> bool:
    """Reject live-device aliases while allowing explicitly named telephone corpora."""
    try:
        domain = canonicalize_domain(domain)
    except ValueError:
        return True
    tokens = set(domain.split("_"))
    return bool(tokens & MICROPHONE_DOMAIN_TOKENS)


def is_trusted_domain_validation_report(sha256: object) -> bool:
    """Return true only for report hashes explicitly approved in source control."""
    return isinstance(sha256, str) and sha256.casefold() in TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256


def _validated_domains(report: object) -> list[str]:
    if not isinstance(report, dict):
        raise ValueError("Domain-validation evidence must be a JSON object.")
    required = {
        "report_version",
        "validated_utc",
        "validation_protocol",
        "validation_dataset",
        "independent_validation",
        "validated_input_domains",
        "results",
    }
    missing = required - report.keys()
    if missing:
        raise ValueError(f"Domain-validation report is missing fields: {sorted(missing)}")
    for field in ("report_version", "validation_protocol", "validation_dataset"):
        if not isinstance(report[field], str) or not report[field].strip():
            raise ValueError(f"Domain-validation report field {field!r} must be non-empty text.")
    if report["independent_validation"] is not True:
        raise ValueError("Domain-validation evidence must explicitly state independent validation.")
    if not isinstance(report["validated_utc"], str):
        raise ValueError("Domain-validation report date must be an ISO timestamp.")
    try:
        validated_at = datetime.fromisoformat(report["validated_utc"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Domain-validation report date must be an ISO timestamp.") from exc
    if validated_at.utcoffset() != timedelta(0):
        raise ValueError("Domain-validation report date must be expressed in UTC.")
    declared = report["validated_input_domains"]
    if not isinstance(declared, list) or not declared:
        raise ValueError("Domain-validation report must name at least one validated domain.")
    domains = [canonicalize_domain(domain) for domain in declared]
    if len(domains) != len(set(domains)):
        raise ValueError("Domain-validation report contains duplicate normalized domains.")
    if any(is_microphone_domain(domain) for domain in domains):
        raise ValueError("Microphone domains cannot be enabled in this prototype.")
    results = report["results"]
    if not isinstance(results, dict) or not results:
        raise ValueError("Domain-validation report must include non-empty results.")
    participant_count = results.get("n_participants")
    if (
        isinstance(participant_count, bool)
        or not isinstance(participant_count, int)
        or participant_count < 1
    ):
        raise ValueError("Domain-validation results must include a positive participant count.")
    scores = [
        value
        for key, value in results.items()
        if key != "n_participants" and isinstance(value, Real) and not isinstance(value, bool)
    ]
    if not scores or any(not 0.0 <= float(score) <= 1.0 for score in scores):
        raise ValueError(
            "Domain-validation results must include a numeric outcome between zero and one."
        )
    return domains


def load_domain_validation_report(path: Path) -> tuple[str, str, list[str]]:
    """Read a small JSON evidence report and return raw text, digest, and canonical domains."""
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"Could not read domain-validation report: {path}") from exc
    if not raw_bytes or len(raw_bytes) > MAX_DOMAIN_REPORT_BYTES:
        raise ValueError("Domain-validation report must be non-empty and no larger than 1 MB.")
    try:
        raw = raw_bytes.decode("utf-8")
        report = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Domain-validation report must be valid UTF-8 JSON.") from exc
    domains = _validated_domains(report)
    return raw, hashlib.sha256(raw_bytes).hexdigest(), domains


def validate_domain_validation_payload(raw: object, expected_sha256: object) -> list[str]:
    """Check stored evidence bytes and return normalized domains only when valid."""
    if not isinstance(raw, str) or not isinstance(expected_sha256, str):
        raise ValueError("Domain-validation evidence and its SHA-256 are required.")
    actual = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if actual != expected_sha256.casefold():
        raise ValueError("Domain-validation evidence SHA-256 does not match its report.")
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Stored domain-validation evidence is not valid JSON.") from exc
    return _validated_domains(report)
