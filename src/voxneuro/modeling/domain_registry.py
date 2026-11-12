"""Authoritative recording-domain registry and metadata governance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from voxneuro.modeling.domains import canonicalize_domain

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "configs" / "recording_domain_registry.yaml"

VALID_DOMAIN_CATEGORIES = frozenset(
    {"training_domain", "candidate_external_domain", "approved_compatible_domain"}
)
VALID_DEVICE_CATEGORIES = frozenset(
    {
        "telephone",
        "studio_microphone",
        "headset_microphone",
        "dynamic_microphone",
        "condenser_microphone",
        "smartphone",
        "laptop_microphone",
        "webcam_microphone",
        "unknown",
    }
)
VALID_TASK_TYPES = frozenset({"sustained_vowel", "ddk", "connected_speech", "vowel_space"})
VALID_COMPATIBILITY_STATUSES = frozenset(
    {
        "REFERENCE_TRAINING_CORPUS",
        "DOMAIN_VALIDATION_PENDING",
        "CANDIDATE_DOMAIN_EVALUATED_PENDING_REVIEW",
        "CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED",
        "DOMAIN_VALIDATION_BLOCKED",
        "DOMAIN_VALIDATION_REJECTED",
        "DOMAIN_COMPATIBILITY_APPROVED",
    }
)


@dataclass(frozen=True)
class DomainSourceReference:
    """Documented literature or institutional provenance for domain acquisition specifications."""

    source_title: str
    author_or_institution: str
    publication_year: int | None = None
    doi_or_url: str | None = None
    dataset_repository_url: str | None = None
    access_date: str | None = None
    fields_supported: list[str] = field(default_factory=list)
    verification_status: str = "VERIFIED"
    reviewer_notes: str | None = None
    source_conflicts: str | None = None
    dataset_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AcquisitionMetadata:
    """Structured physical and digital audio acquisition metadata."""

    domain_id: str
    dataset_id: str
    dataset_version: str
    collection_site_id: str
    country: str
    region: str
    collection_period: str
    device_category: str
    microphone_type: str
    audio_codec: str
    container_format: str
    original_sample_rate: int | str | None
    bit_depth: int | str | None
    channel_count: int | str | None
    task_type: str
    language: str
    device_manufacturer: str | None = None
    device_model: str | None = None
    recording_software: str | None = None
    recording_software_version: str | None = None
    microphone_distance_cm: float | None = None
    microphone_angle_degrees: float | None = None
    automatic_gain_control: bool | str = "unknown"
    noise_suppression: bool | str = "unknown"
    compression_enabled: bool | str = "unknown"
    recording_environment: str = "unknown"
    estimated_background_noise_db: float | None = None
    protocol_id: str = "unknown"
    dialect_metadata: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecordingDomainEntry:
    """Registry entry representing a defined recording domain."""

    domain_id: str
    domain_name: str
    domain_category: str
    metadata: AcquisitionMetadata
    feature_schema_compatibility: str = "voxneuro.voice.v3"
    research_evaluation_eligible: bool = True
    candidate_compatibility_status: str = "DOMAIN_VALIDATION_PENDING"
    inference_eligible: bool = False
    human_review_status: str = "UNREVIEWED"
    approval_status: str = "UNAPPROVED"
    sources: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        meta = data.pop("metadata")
        # Flatten metadata fields at top level of domain record for YAML compatibility
        return {**data, **meta}


@dataclass
class RecordingDomainRegistry:
    """Authoritative registry containing all defined recording domains."""

    registry_version: str
    registry_schema: str
    training_domains: list[str]
    candidate_domains: list[str]
    approved_domains: list[str]
    domains: dict[str, RecordingDomainEntry] = field(default_factory=dict)

    def get_domain(self, domain_id: str) -> RecordingDomainEntry:
        canonical = canonicalize_domain(domain_id)
        if canonical not in self.domains:
            raise KeyError(f"Domain {domain_id!r} (canonical {canonical!r}) is not in registry.")
        return self.domains[canonical]

    def is_registered(self, domain_id: str) -> bool:
        try:
            canonical = canonicalize_domain(domain_id)
            return canonical in self.domains
        except ValueError:
            return False

    def is_candidate(self, domain_id: str) -> bool:
        canonical = canonicalize_domain(domain_id)
        return canonical in self.candidate_domains

    def is_approved(self, domain_id: str) -> bool:
        canonical = canonicalize_domain(domain_id)
        return canonical in self.approved_domains

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "registry_schema": self.registry_schema,
            "training_domains": list(self.training_domains),
            "candidate_domains": list(self.candidate_domains),
            "approved_domains": list(self.approved_domains),
            "domains": {k: v.to_dict() for k, v in sorted(self.domains.items())},
        }

    def fingerprint(self) -> str:
        """Deterministic cryptographic digest of registry content."""
        canonical_json = json.dumps(
            self.to_dict(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _validate_metadata_dict(raw: dict[str, Any], domain_id: str) -> AcquisitionMetadata:
    required_str = [
        "dataset_id",
        "dataset_version",
        "collection_site_id",
        "country",
        "region",
        "collection_period",
        "device_category",
        "microphone_type",
        "audio_codec",
        "container_format",
        "task_type",
        "language",
    ]
    for key in required_str:
        val = raw.get(key)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"Domain {domain_id!r} metadata {key!r} must be a non-empty string.")

    if raw["device_category"] not in VALID_DEVICE_CATEGORIES:
        raise ValueError(
            f"Domain {domain_id!r} device_category {raw['device_category']!r} is invalid."
        )

    if raw["task_type"] not in VALID_TASK_TYPES:
        raise ValueError(f"Domain {domain_id!r} task_type {raw['task_type']!r} is invalid.")

    for int_key in ("original_sample_rate", "bit_depth", "channel_count"):
        val = raw.get(int_key)
        if val is not None and val != "unknown":
            if isinstance(val, bool) or not isinstance(val, int) or val <= 0:
                raise ValueError(
                    f"Domain {domain_id!r} {int_key!r} must be positive int, null, or 'unknown'."
                )

    return AcquisitionMetadata(
        domain_id=domain_id,
        dataset_id=raw["dataset_id"],
        dataset_version=raw["dataset_version"],
        collection_site_id=raw["collection_site_id"],
        country=raw["country"],
        region=raw["region"],
        collection_period=raw["collection_period"],
        device_category=raw["device_category"],
        microphone_type=raw["microphone_type"],
        audio_codec=raw["audio_codec"],
        container_format=raw["container_format"],
        original_sample_rate=raw["original_sample_rate"],
        bit_depth=raw["bit_depth"],
        channel_count=raw["channel_count"],
        task_type=raw["task_type"],
        language=raw["language"],
        device_manufacturer=raw.get("device_manufacturer"),
        device_model=raw.get("device_model"),
        recording_software=raw.get("recording_software"),
        recording_software_version=raw.get("recording_software_version"),
        microphone_distance_cm=(
            float(raw["microphone_distance_cm"])
            if raw.get("microphone_distance_cm") is not None
            else None
        ),
        microphone_angle_degrees=(
            float(raw["microphone_angle_degrees"])
            if raw.get("microphone_angle_degrees") is not None
            else None
        ),
        automatic_gain_control=raw.get("automatic_gain_control", "unknown"),
        noise_suppression=raw.get("noise_suppression", "unknown"),
        compression_enabled=raw.get("compression_enabled", "unknown"),
        recording_environment=str(raw.get("recording_environment", "unknown")),
        estimated_background_noise_db=(
            float(raw["estimated_background_noise_db"])
            if raw.get("estimated_background_noise_db") is not None
            else None
        ),
        protocol_id=str(raw.get("protocol_id", "unknown")),
        dialect_metadata=raw.get("dialect_metadata"),
    )


def validate_registry_document(doc: dict[str, Any]) -> RecordingDomainRegistry:
    """Validate a parsed domain registry dictionary and construct a typed registry."""
    if not isinstance(doc, dict):
        raise ValueError("Domain registry root must be a YAML mapping.")

    required_keys = {
        "registry_version",
        "registry_schema",
        "training_domains",
        "candidate_domains",
        "approved_domains",
        "domains",
    }
    missing = required_keys - set(doc)
    if missing:
        raise ValueError(f"Domain registry missing required keys: {sorted(missing)}")

    for list_key in ("training_domains", "candidate_domains", "approved_domains"):
        val = doc[list_key]
        if not isinstance(val, list) or any(not isinstance(x, str) for x in val):
            raise ValueError(f"Registry key {list_key!r} must be a list of strings.")

    # Canonicalize and verify unique domain lists
    training = [canonicalize_domain(d) for d in doc["training_domains"]]
    candidates = [canonicalize_domain(d) for d in doc["candidate_domains"]]
    approved = [canonicalize_domain(d) for d in doc["approved_domains"]]

    if len(training) != len(set(training)):
        raise ValueError("Duplicate entries found in training_domains.")
    if len(candidates) != len(set(candidates)):
        raise ValueError("Duplicate entries found in candidate_domains.")
    if len(approved) != len(set(approved)):
        raise ValueError("Duplicate entries found in approved_domains.")

    raw_domains = doc["domains"]
    if not isinstance(raw_domains, dict):
        raise ValueError("Registry 'domains' must be a mapping of domain entries.")

    parsed_entries: dict[str, RecordingDomainEntry] = {}
    for raw_id, raw_entry in raw_domains.items():
        canonical_id = canonicalize_domain(raw_id)
        if not isinstance(raw_entry, dict):
            raise ValueError(f"Domain entry {raw_id!r} must be a dictionary.")

        entry_domain_id = canonicalize_domain(raw_entry.get("domain_id", raw_id))
        if entry_domain_id != canonical_id:
            raise ValueError(
                f"Domain ID mismatch: key is {canonical_id!r} but entry "
                f"declares {entry_domain_id!r}."
            )

        cat = raw_entry.get("domain_category", "")
        if cat not in VALID_DOMAIN_CATEGORIES:
            raise ValueError(f"Domain {canonical_id!r} has invalid category {cat!r}.")

        status = raw_entry.get("candidate_compatibility_status", "DOMAIN_VALIDATION_PENDING")
        if status not in VALID_COMPATIBILITY_STATUSES:
            raise ValueError(
                f"Domain {canonical_id!r} has invalid compatibility status {status!r}."
            )

        meta = _validate_metadata_dict(raw_entry, canonical_id)
        raw_sources = raw_entry.get("sources", [])
        parsed_sources: list[dict[str, Any]] = []
        if isinstance(raw_sources, list):
            for s in raw_sources:
                if isinstance(s, dict):
                    ref = DomainSourceReference(
                        source_title=str(s.get("source_title", "")),
                        author_or_institution=str(s.get("author_or_institution", "")),
                        publication_year=s.get("publication_year"),
                        doi_or_url=s.get("doi_or_url"),
                        dataset_repository_url=s.get("dataset_repository_url"),
                        access_date=s.get("access_date"),
                        fields_supported=list(s.get("fields_supported", [])),
                        verification_status=str(s.get("verification_status", "VERIFIED")),
                        reviewer_notes=s.get("reviewer_notes"),
                        source_conflicts=s.get("source_conflicts"),
                        dataset_version=s.get("dataset_version"),
                    )
                    parsed_sources.append(ref.to_dict())

        parsed_entries[canonical_id] = RecordingDomainEntry(
            domain_id=canonical_id,
            domain_name=str(raw_entry.get("domain_name", canonical_id)),
            domain_category=cat,
            metadata=meta,
            feature_schema_compatibility=str(
                raw_entry.get("feature_schema_compatibility", "voxneuro.voice.v3")
            ),
            research_evaluation_eligible=bool(raw_entry.get("research_evaluation_eligible", True)),
            candidate_compatibility_status=status,
            inference_eligible=bool(raw_entry.get("inference_eligible", False)),
            human_review_status=str(raw_entry.get("human_review_status", "UNREVIEWED")),
            approval_status=str(raw_entry.get("approval_status", "UNAPPROVED")),
            sources=parsed_sources,
        )

    # Check that all declared lists exist in parsed domains
    for d in training:
        if d not in parsed_entries:
            raise ValueError(f"Training domain {d!r} is declared but not defined in domains.")
    for d in candidates:
        if d not in parsed_entries:
            raise ValueError(f"Candidate domain {d!r} is declared but not defined in domains.")
    for d in approved:
        if d not in parsed_entries:
            raise ValueError(f"Approved domain {d!r} is declared but not defined in domains.")

    # Safety: approved domains must strictly match inference_eligible == True
    for d, entry in parsed_entries.items():
        if entry.inference_eligible and d not in approved:
            raise ValueError(
                f"Domain {d!r} declares inference_eligible: true but is not in approved_domains."
            )
        if d in approved and not entry.inference_eligible:
            raise ValueError(
                f"Domain {d!r} is in approved_domains but has inference_eligible: false."
            )

    return RecordingDomainRegistry(
        registry_version=str(doc["registry_version"]),
        registry_schema=str(doc["registry_schema"]),
        training_domains=training,
        candidate_domains=candidates,
        approved_domains=approved,
        domains=parsed_entries,
    )


def load_domain_registry(path: Path | None = None) -> RecordingDomainRegistry:
    """Load and validate the recording domain registry from YAML."""
    registry_path = path or DEFAULT_REGISTRY_PATH
    if not registry_path.is_file():
        raise FileNotFoundError(f"Recording domain registry not found: {registry_path}")

    with registry_path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)

    return validate_registry_document(raw)
