"""Unit tests for the AI review bundle packaging and integrity verifications."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

from scripts.build_ai_review_bundle import (
    EVIDENCE_SOURCES,
    build_review_bundle,
)


def test_ai_review_bundle_builds_and_verifies_integrity(tmp_path: Path):
    bundle_path = tmp_path / "test_review_bundle.zip"
    report = build_review_bundle(bundle_path)
    assert report["members"] >= 180
    assert report["bytes"] > 0
    assert bundle_path.is_file()

    with zipfile.ZipFile(bundle_path) as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        assert "AI_REVIEW_BUNDLE_README.txt" in names
        assert "app.py" in names
        assert "pyproject.toml" in names

        # Verify all declared evidence files exist inside review_evidence/
        for evidence_name in EVIDENCE_SOURCES:
            assert f"review_evidence/{evidence_name}" in names


def test_ai_review_bundle_blocks_sample_ids_and_forbidden_binaries(tmp_path: Path):
    bundle_path = tmp_path / "test_review_bundle_privacy.zip"
    build_review_bundle(bundle_path)

    with zipfile.ZipFile(bundle_path) as zf:
        for name in zf.namelist():
            # No binary models, raw audio, or cache files allowed
            assert not name.casefold().endswith((".wav", ".joblib", ".pkl", ".parquet"))
            assert "oof_predictions" not in name.casefold()

            # No patient-level raw identifiers in review_evidence
            if name.startswith("review_evidence/"):
                payload = zf.read(name).lower()
                assert b"uams-0" not in payload


def test_ai_review_bundle_readme_hashes_match_entries(tmp_path: Path):
    bundle_path = tmp_path / "test_review_bundle_hashes.zip"
    build_review_bundle(bundle_path)

    with zipfile.ZipFile(bundle_path) as zf:
        readme_text = zf.read("AI_REVIEW_BUNDLE_README.txt").decode("utf-8")
        # Match pattern: - `filename` — SHA-256 `sha256_hash`
        hash_pattern = re.compile(r"- `([a-zA-Z0-9_\-\.]+)` — SHA-256 `([a-fA-F0-9]{64})`")
        found = dict(hash_pattern.findall(readme_text))
        assert len(found) >= len(EVIDENCE_SOURCES)

        for filename, expected_hash in found.items():
            member_path = f"review_evidence/{filename}"
            if member_path in zf.namelist():
                actual_hash = hashlib.sha256(zf.read(member_path)).hexdigest()
                assert actual_hash.casefold() == expected_hash.casefold()
