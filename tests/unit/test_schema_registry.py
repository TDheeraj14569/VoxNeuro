"""Automated tests for M3 multi-task schema registry consistency and immutability."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from voxneuro.features.schema import (
    FEATURE_DEFINITIONS as V3_FEATURE_DEFINITIONS,
)
from voxneuro.features.schema import (
    SCHEMA_VERSION as V3_SCHEMA_VERSION,
)
from voxneuro.features.schema import (
    schema_fingerprint as v3_schema_fingerprint,
)
from voxneuro.features.tasks.schema import (
    CONNECTED_SPEECH_FEATURE_DEFINITIONS,
    CONNECTED_SPEECH_SCHEMA_VERSION,
    DDK_FEATURE_DEFINITIONS,
    DDK_SCHEMA_VERSION,
    V4_SCHEMA_VERSION,
    VOWEL_SPACE_FEATURE_DEFINITIONS,
    VOWEL_SPACE_SCHEMA_VERSION,
    TaskFeatureDefinition,
    connected_speech_schema_fingerprint,
    ddk_schema_fingerprint,
    generate_task_schema_registry_document,
    get_task_schema_registry,
    v4_envelope_schema_fingerprint,
    vowel_space_schema_fingerprint,
)

CANONICAL_V3_FINGERPRINT = "a7e3374210617f1e94897a219bf373be4aaa73a4fa5ec1d9581947cce2ab3e9f"
EXPECTED_DDK_FINGERPRINT = "b26bf914d14af54d85e98b40238c653d4134c5b72af3f7140ccf95f606ab4e5b"
EXPECTED_CONNECTED_SPEECH_FINGERPRINT = (
    "7a5763d4cdbda4b1034113a47dd197bf9942621df73312134cece35b8ae419b1"
)
EXPECTED_VOWEL_SPACE_FINGERPRINT = (
    "e20bbc3ba00eb1f80d864823fc7e27537dcb0665693baf04ea149054c5b53993"
)
EXPECTED_V4_ENVELOPE_FINGERPRINT = (
    "cc1d53b907cdf6f86e882a980d98015c3e04e2e10cccf59670c87bc6a54c0429"
)


class TestSchemaRegistryIntegrity:
    """Validate runtime schema fingerprints and persisted review evidence."""

    def test_v3_canonical_fingerprint_immutable(self) -> None:
        """The canonical v3 Core39 schema fingerprint must remain strictly unchanged."""
        runtime_v3 = v3_schema_fingerprint()
        err_msg = f"Expected {CANONICAL_V3_FINGERPRINT}, got {runtime_v3}"
        assert runtime_v3 == CANONICAL_V3_FINGERPRINT, err_msg

    def test_runtime_task_schema_fingerprints_match_authoritative_values(self) -> None:
        """Runtime schema functions must return exact expected cryptographic digests."""
        assert ddk_schema_fingerprint() == EXPECTED_DDK_FINGERPRINT
        assert connected_speech_schema_fingerprint() == EXPECTED_CONNECTED_SPEECH_FINGERPRINT
        assert vowel_space_schema_fingerprint() == EXPECTED_VOWEL_SPACE_FINGERPRINT
        assert v4_envelope_schema_fingerprint() == EXPECTED_V4_ENVELOPE_FINGERPRINT

    def test_schema_feature_counts(self) -> None:
        """Feature counts must match canonical definitions."""
        assert len(V3_FEATURE_DEFINITIONS) == 39
        assert len(DDK_FEATURE_DEFINITIONS) == 11
        assert len(CONNECTED_SPEECH_FEATURE_DEFINITIONS) == 20
        assert len(VOWEL_SPACE_FEATURE_DEFINITIONS) == 16

    def test_v4_envelope_contains_all_registered_tasks(self) -> None:
        """V4 session envelope must include all 4 active task schemas."""
        registry = get_task_schema_registry()
        assert len(registry) == 4
        assert V3_SCHEMA_VERSION in registry
        assert DDK_SCHEMA_VERSION in registry
        assert CONNECTED_SPEECH_SCHEMA_VERSION in registry
        assert VOWEL_SPACE_SCHEMA_VERSION in registry

        # Check each task's registered fingerprint matches runtime function
        assert registry[V3_SCHEMA_VERSION]["fingerprint"] == v3_schema_fingerprint()
        assert registry[DDK_SCHEMA_VERSION]["fingerprint"] == ddk_schema_fingerprint()
        assert (
            registry[CONNECTED_SPEECH_SCHEMA_VERSION]["fingerprint"]
            == connected_speech_schema_fingerprint()
        )
        assert (
            registry[VOWEL_SPACE_SCHEMA_VERSION]["fingerprint"] == vowel_space_schema_fingerprint()
        )

    def test_persisted_review_evidence_matches_runtime_registry(self) -> None:
        """review_evidence/m3_task_schema_registry.json must strictly match runtime."""
        evidence_path = Path("review_evidence/m3_task_schema_registry.json")
        if not evidence_path.is_file():
            pytest.skip("m3_task_schema_registry.json has not been generated yet.")

        with open(evidence_path, encoding="utf-8") as f:
            persisted = json.load(f)

        runtime_doc = generate_task_schema_registry_document()

        assert persisted["milestone"] == "M3"
        assert persisted["envelope_schema_version"] == V4_SCHEMA_VERSION
        assert persisted["envelope_schema_fingerprint"] == v4_envelope_schema_fingerprint()

        persisted_map = {s["schema_version"]: s for s in persisted["schemas"]}
        runtime_map = {s["schema_version"]: s for s in runtime_doc["schemas"]}

        assert set(persisted_map.keys()) == set(runtime_map.keys())

        for s_ver, r_entry in runtime_map.items():
            p_entry = persisted_map[s_ver]
            assert p_entry["schema_fingerprint"] == r_entry["schema_fingerprint"], (
                f"Mismatch in schema fingerprint for {s_ver}: "
                f"persisted={p_entry['schema_fingerprint']},\n"
                f"runtime={r_entry['schema_fingerprint']}"
            )
            assert p_entry["feature_count"] == r_entry["feature_count"]
            assert p_entry["schema_name"] == r_entry["schema_name"]

    def test_modifying_feature_definition_changes_schema_fingerprint(self) -> None:
        """Altering any feature definition must alter the cryptographic digest."""
        import hashlib

        # Create a modified DDK definition list
        modified_defs = list(DDK_FEATURE_DEFINITIONS)
        modified_defs[0] = TaskFeatureDefinition(
            name=modified_defs[0].name,
            units="modified_units",
            method=modified_defs[0].method,
            validity=modified_defs[0].validity,
        )

        mod_doc = {
            "schema_version": DDK_SCHEMA_VERSION,
            "feature_order": [f.name for f in modified_defs],
            "features": [asdict(f) for f in modified_defs],
        }
        mod_payload = json.dumps(mod_doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
        mod_hash = hashlib.sha256(mod_payload).hexdigest()

        assert mod_hash != ddk_schema_fingerprint(), (
            "Modifying a feature definition failed to change the DDK schema fingerprint!"
        )
