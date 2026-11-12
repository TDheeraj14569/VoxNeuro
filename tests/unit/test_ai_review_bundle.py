"""Unit tests for the AI review bundle packaging and integrity verifications."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path

import pytest
from scripts.build_ai_review_bundle import (
    EVIDENCE_SOURCES,
    build_review_bundle,
)


@pytest.fixture
def synthetic_bundle_fixtures(tmp_path: Path):
    """Hermetic synthetic fixtures allowing AI bundle tests to run without private datasets."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = data_dir / "feature_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "sample_id",
                "participant_id",
                "class_label",
                "label_match",
                "metadata_match",
                "waveform_sha256",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "sample_id": "syn-01",
                "participant_id": "p01",
                "class_label": "HC",
                "label_match": "True",
                "metadata_match": "True",
                "waveform_sha256": "a" * 64,
            }
        )
        writer.writerow(
            {
                "sample_id": "syn-02",
                "participant_id": "p02",
                "class_label": "PD",
                "label_match": "True",
                "metadata_match": "True",
                "waveform_sha256": "b" * 64,
            }
        )

    extraction_path = data_dir / "feature_extraction_report.csv"
    with extraction_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sample_id", "extraction_status", "failure_reason"])
        writer.writeheader()
        writer.writerow(
            {
                "sample_id": "syn-01",
                "extraction_status": "success",
                "failure_reason": "",
            }
        )
        writer.writerow(
            {
                "sample_id": "syn-02",
                "extraction_status": "failed",
                "failure_reason": "clipping detected",
            }
        )

    evidence_sources = {}
    for name in EVIDENCE_SOURCES:
        file_path = data_dir / name
        if name == "uams_feature_extraction_receipt.json":
            file_path.write_text(
                json.dumps(
                    {
                        "status": "accepted_reviewed_exclusions",
                        "excluded_sample_ids": ["sample-ex-01", "sample-ex-02"],
                        "total_recordings": 2,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        elif name.endswith(".json"):
            file_path.write_text(
                json.dumps({"status": "complete", "model": "test"}, indent=2), encoding="utf-8"
            )
        elif name.endswith(".html"):
            file_path.write_text("<!doctype html><html><body>Test</body></html>", encoding="utf-8")
        else:
            file_path.write_text("model,score\ntest,0.85\n", encoding="utf-8")
        evidence_sources[name] = file_path

    return {
        "manifest_path": manifest_path,
        "extraction_report_path": extraction_path,
        "evidence_sources": evidence_sources,
    }


def test_ai_review_bundle_builds_and_verifies_integrity(
    tmp_path: Path, synthetic_bundle_fixtures: dict
):
    bundle_path = tmp_path / "test_review_bundle.zip"
    report = build_review_bundle(
        bundle_path,
        manifest_path=synthetic_bundle_fixtures["manifest_path"],
        extraction_report_path=synthetic_bundle_fixtures["extraction_report_path"],
        evidence_sources=synthetic_bundle_fixtures["evidence_sources"],
    )
    assert report["members"] >= 180
    assert report["bytes"] > 0
    assert bundle_path.is_file()

    with zipfile.ZipFile(bundle_path) as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        assert "AI_REVIEW_BUNDLE_README.txt" in names
        assert "app.py" in names
        assert "pyproject.toml" in names

        for evidence_name in EVIDENCE_SOURCES:
            assert f"review_evidence/{evidence_name}" in names


def test_ai_review_bundle_blocks_sample_ids_and_forbidden_binaries(
    tmp_path: Path, synthetic_bundle_fixtures: dict
):
    bundle_path = tmp_path / "test_review_bundle_privacy.zip"
    build_review_bundle(
        bundle_path,
        manifest_path=synthetic_bundle_fixtures["manifest_path"],
        extraction_report_path=synthetic_bundle_fixtures["extraction_report_path"],
        evidence_sources=synthetic_bundle_fixtures["evidence_sources"],
    )

    with zipfile.ZipFile(bundle_path) as zf:
        for name in zf.namelist():
            assert not name.casefold().endswith((".wav", ".joblib", ".pkl", ".parquet"))
            assert "oof_predictions" not in name.casefold()

            if name.startswith("review_evidence/"):
                payload = zf.read(name).lower()
                assert b"uams-0" not in payload


def test_ai_review_bundle_readme_hashes_match_entries(
    tmp_path: Path, synthetic_bundle_fixtures: dict
):
    bundle_path = tmp_path / "test_review_bundle_hashes.zip"
    build_review_bundle(
        bundle_path,
        manifest_path=synthetic_bundle_fixtures["manifest_path"],
        extraction_report_path=synthetic_bundle_fixtures["extraction_report_path"],
        evidence_sources=synthetic_bundle_fixtures["evidence_sources"],
    )

    with zipfile.ZipFile(bundle_path) as zf:
        readme_text = zf.read("AI_REVIEW_BUNDLE_README.txt").decode("utf-8")
        hash_pattern = re.compile(r"- `([a-zA-Z0-9_\-\.]+)` — SHA-256 `([a-fA-F0-9]{64})`")
        found = dict(hash_pattern.findall(readme_text))
        assert len(found) >= len(EVIDENCE_SOURCES)

        for filename, expected_hash in found.items():
            member_path = f"review_evidence/{filename}"
            if member_path in zf.namelist():
                actual_hash = hashlib.sha256(zf.read(member_path)).hexdigest()
                assert actual_hash.casefold() == expected_hash.casefold()


def test_ai_review_bundle_m6_milestone_verifies_m6_manifest(
    tmp_path: Path, synthetic_bundle_fixtures: dict
):
    import json

    from scripts.build_ai_review_bundle import M6_ADDITIONAL_EVIDENCE

    evidence_dir = tmp_path / "m6_ev"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_sources = dict(synthetic_bundle_fixtures["evidence_sources"])
    manifest_files = {}
    for name in sorted(M6_ADDITIONAL_EVIDENCE):
        if name == "m6_review_manifest.json":
            continue
        p = evidence_dir / name
        content = (
            "<!doctype html><html><body>Aggregate M6 card</body></html>"
            if name.endswith(".html")
            else json.dumps({"milestone": "M6", "artifact": name})
        ).encode("utf-8")
        p.write_bytes(content)
        evidence_sources[name] = p
        manifest_files[name] = {
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    manifest_path = evidence_dir / "m6_review_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"milestone": "M6", "total_files": len(manifest_files), "files": manifest_files}
        ),
        encoding="utf-8",
    )
    evidence_sources["m6_review_manifest.json"] = manifest_path

    out_zip = tmp_path / "VoxNeuro_M6_TEST.zip"
    build_review_bundle(
        out_zip,
        milestone="m6",
        manifest_path=synthetic_bundle_fixtures["manifest_path"],
        extraction_report_path=synthetic_bundle_fixtures["extraction_report_path"],
        evidence_sources=evidence_sources,
    )
    with zipfile.ZipFile(out_zip) as zf:
        assert zf.testzip() is None
        readme = zf.read("AI_REVIEW_BUNDLE_README.txt").decode("utf-8")
        assert "(M6)" in readme
        assert "review_evidence/m6_review_manifest.json" in zf.namelist()
        assert "review_evidence/m6_model_card.json" in zf.namelist()
