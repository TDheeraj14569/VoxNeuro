"""Unit tests for recording domain registry and acquisition metadata governance."""

import pytest

from voxneuro.modeling.domain_registry import (
    RecordingDomainRegistry,
    load_domain_registry,
    validate_registry_document,
)


def test_load_default_registry():
    registry = load_domain_registry()
    assert isinstance(registry, RecordingDomainRegistry)
    assert registry.registry_version == "1.0.0"
    assert "uams_telephone" in registry.training_domains
    assert "neurovoz_studio" in registry.candidate_domains
    assert registry.approved_domains == []  # Crucial safety check
    assert registry.is_registered("uams_telephone")
    assert registry.is_candidate("neurovoz_studio")
    assert not registry.is_approved("neurovoz_studio")
    assert registry.fingerprint()


def test_registry_normalization():
    registry = load_domain_registry()
    assert registry.get_domain("UAMS_TELEPHONE").domain_id == "uams_telephone"
    assert registry.get_domain("neurovoz-studio").domain_id == "neurovoz_studio"
    with pytest.raises(KeyError):
        registry.get_domain("non_existent_domain_xyz")


def test_registry_rejects_duplicate_domain_declarations():
    doc = {
        "registry_version": "1.0.0",
        "registry_schema": "voxneuro.domain_registry.v1",
        "training_domains": ["uams_telephone", "uams_telephone"],
        "candidate_domains": ["neurovoz_studio"],
        "approved_domains": [],
        "domains": {},
    }
    with pytest.raises(ValueError, match="Duplicate entries"):
        validate_registry_document(doc)


def test_registry_rejects_invalid_device_category():
    doc = {
        "registry_version": "1.0.0",
        "registry_schema": "voxneuro.domain_registry.v1",
        "training_domains": ["uams_telephone"],
        "candidate_domains": [],
        "approved_domains": [],
        "domains": {
            "uams_telephone": {
                "domain_id": "uams_telephone",
                "domain_category": "training_domain",
                "dataset_id": "uams",
                "dataset_version": "v1",
                "collection_site_id": "site1",
                "country": "USA",
                "region": "AR",
                "collection_period": "2020",
                "device_category": "magical_acoustic_wand",  # Invalid
                "microphone_type": "dynamic",
                "audio_codec": "pcm_s16le",
                "container_format": "wav",
                "original_sample_rate": 16000,
                "bit_depth": 16,
                "channel_count": 1,
                "task_type": "sustained_vowel",
                "language": "en",
            }
        },
    }
    with pytest.raises(ValueError, match="device_category 'magical_acoustic_wand' is invalid"):
        validate_registry_document(doc)


def test_corrected_metadata_and_provenance_sources():
    registry = load_domain_registry()

    # NeuroVoz audit
    neurovoz = registry.get_domain("neurovoz_studio")
    assert neurovoz.metadata.device_manufacturer == "AKG"
    assert neurovoz.metadata.device_model == "C420"
    assert neurovoz.metadata.device_category == "headset_microphone"
    assert neurovoz.metadata.microphone_type == "electret_condenser_headset"
    assert neurovoz.metadata.recording_environment == "clinical_quiet_room"
    assert neurovoz.metadata.original_sample_rate == 44100
    assert len(neurovoz.sources) >= 1
    assert "PMC11655668" in neurovoz.sources[0]["reviewer_notes"]

    # PC-GITA audit
    pc_gita = registry.get_domain("pc_gita_condenser")
    assert pc_gita.metadata.device_manufacturer == "Shure"
    assert pc_gita.metadata.device_model == "SM63L"
    assert pc_gita.metadata.device_category == "dynamic_microphone"
    assert pc_gita.metadata.microphone_type == "dynamic_omnidirectional"
    assert pc_gita.metadata.recording_environment == "sound_treated_booth"
    assert len(pc_gita.sources) >= 1

    # Italian dataset audit
    italian = registry.get_domain("italian_parkinsons_headset")
    assert italian.metadata.collection_site_id == "uniba_bari"
    assert italian.metadata.country == "ITA"
    assert italian.metadata.device_manufacturer is None
    assert italian.metadata.device_model is None
    assert italian.candidate_compatibility_status == "CANDIDATE_TASK_COMPATIBILITY_UNVERIFIED"
    assert italian.research_evaluation_eligible is False
    assert len(italian.sources) >= 1
    assert "source_conflicts" in italian.sources[0]


def test_registry_safety_enforces_approved_domain_consistency():
    # If a domain declares inference_eligible: true but is not in approved_domains
    doc = {
        "registry_version": "1.0.0",
        "registry_schema": "voxneuro.domain_registry.v1",
        "training_domains": ["uams_telephone"],
        "candidate_domains": [],
        "approved_domains": [],
        "domains": {
            "uams_telephone": {
                "domain_id": "uams_telephone",
                "domain_category": "training_domain",
                "dataset_id": "uams",
                "dataset_version": "v1",
                "collection_site_id": "site1",
                "country": "USA",
                "region": "AR",
                "collection_period": "2020",
                "device_category": "telephone",
                "microphone_type": "dynamic",
                "audio_codec": "pcm_s16le",
                "container_format": "wav",
                "original_sample_rate": 16000,
                "bit_depth": 16,
                "channel_count": 1,
                "task_type": "sustained_vowel",
                "language": "en",
                "inference_eligible": True,  # Inconsistent with approved_domains: []
            }
        },
    }
    with pytest.raises(
        ValueError, match="declares inference_eligible: true but is not in approved_domains"
    ):
        validate_registry_document(doc)


def test_ipvs_metadata_and_register_scientific_consistency():
    """Part 8.1: IPVS hardware/rate/bit/codec/env remain unknown/null across registry & register."""
    from pathlib import Path

    reg = load_domain_registry()
    ipvs = reg.get_domain("italian_parkinsons_headset")
    assert ipvs.metadata.device_manufacturer is None
    assert ipvs.metadata.device_model is None
    assert ipvs.metadata.device_category == "unknown"
    assert ipvs.metadata.microphone_type == "unknown"
    assert ipvs.metadata.original_sample_rate is None
    assert ipvs.metadata.bit_depth is None
    assert ipvs.metadata.channel_count is None
    assert ipvs.metadata.audio_codec == "unknown"
    assert ipvs.metadata.recording_environment == "unknown"
    assert ipvs.research_evaluation_eligible is False

    sources_text = " ".join(
        f"{s.get('reviewer_notes', '')} {s.get('source_conflicts', '')}".lower()
        for s in ipvs.sources
    )
    assert "samson meteor" in sources_text
    assert "wh20" in sources_text
    assert "pa-ta-ka" in sources_text or "diadochokinetic" in sources_text

    register_path = Path("docs/audit/M4_EXTERNAL_DATASET_REGISTER.md")
    register_text = register_path.read_text(encoding="utf-8")
    ipvs_lines = [line for line in register_text.splitlines() if "ipvs" in line.lower()]
    assert ipvs_lines
    for line in ipvs_lines:
        assert "44.1 khz" not in line.lower()
        assert "16-bit" not in line.lower()
