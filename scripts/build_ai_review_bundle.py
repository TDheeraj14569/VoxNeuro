"""Build a compact AI-review ZIP with source and aggregate-only ML evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.build_source_archive import OUTPUT as SOURCE_ARCHIVE  # noqa: E402
from scripts.build_source_archive import ROOT, build_archive  # noqa: E402

REVIEW_ARCHIVE = ROOT / "VoxNeuro_AI_review_bundle.zip"
M2_ARCHIVE = ROOT / "VoxNeuro_M2_VERIFIED.zip"
M3_ARCHIVE = ROOT / "VoxNeuro_M3_VERIFIED.zip"
M4_ARCHIVE = ROOT / "VoxNeuro_M4_VERIFIED.zip"
M5_ARCHIVE = ROOT / "VoxNeuro_M5_VERIFIED.zip"
M6_ARCHIVE = ROOT / "VoxNeuro_M6_VERIFIED.zip"

EVIDENCE_SOURCES = {
    "uams_nested_evaluation.html": ROOT / "artifacts/reports/model_evaluation/uams_nested.html",
    "uams_nested_summary.csv": ROOT / "data/processed/nested_uams_summary.csv",
    "uams_nested_fold_metrics.csv": ROOT / "data/processed/nested_uams_fold_metrics.csv",
    "uci_grouped_fold_metrics.csv": ROOT / "data/processed/uci_model_metrics.csv",
    "uci_duplicate_sensitivity.csv": ROOT / "data/processed/uci_duplicate_sensitivity.csv",
    "uams_feature_extraction_receipt.json": ROOT / "data/processed/feature_extraction_receipt.json",
    "uams_grouped_evaluation_receipt.json": ROOT / "data/processed/model_evaluation_receipt.json",
    "uams_nested_evaluation_receipt.json": ROOT
    / "data/processed/nested_uams_evaluation_receipt.json",
    "uci_evaluation_receipt.json": ROOT / "data/processed/uci_model_evaluation_receipt.json",
}

M2_ADDITIONAL_EVIDENCE = {
    "m2_demographic_audit.html": ROOT
    / "artifacts/reports/scientific_audit/m2_demographic_audit.html",
    "m2_attrition_analysis.html": ROOT
    / "artifacts/reports/scientific_audit/m2_attrition_analysis.html",
    "m2_matching_balance.html": ROOT
    / "artifacts/reports/scientific_audit/m2_matching_balance.html",
    "m2_bias_audit.html": ROOT / "artifacts/reports/scientific_audit/m2_bias_audit.html",
    "m2_model_comparison.html": ROOT
    / "artifacts/reports/scientific_audit/m2_model_comparison.html",
    "m2_demographic_summary.json": ROOT / "data/processed/m2_demographic_summary.json",
    "m2_attrition_summary.json": ROOT / "data/processed/m2_attrition_summary.json",
    "m2_matching_sensitivity.csv": ROOT / "data/processed/m2_matching_sensitivity.csv",
    "m2_comparator_metrics.csv": ROOT / "data/processed/m2_comparator_metrics.csv",
    "m2_paired_incremental_voice.csv": ROOT / "data/processed/m2_paired_incremental_voice.csv",
    "m2_sex_subgroup_summary.csv": ROOT / "data/processed/m2_sex_subgroup_summary.csv",
    "m2_age_subgroup_summary.csv": ROOT / "data/processed/m2_age_subgroup_summary.csv",
    "m2_feature_fdr_summary.csv": ROOT / "data/processed/m2_feature_fdr_summary.csv",
    "m2_analysis_receipt.json": ROOT / "data/processed/m2_analysis_receipt.json",
}

M3_ADDITIONAL_EVIDENCE = {
    "m3_task_schema_registry.json": ROOT / "review_evidence/m3_task_schema_registry.json",
    "m3_task_feature_contract.csv": ROOT / "review_evidence/m3_task_feature_contract.csv",
    "m3_synthetic_fixture_verification.json": ROOT
    / "review_evidence/m3_synthetic_fixture_verification.json",
    "m3_implementation_test_summary.json": ROOT
    / "review_evidence/m3_implementation_test_summary.json",
    "m3_provenance_summary.json": ROOT / "review_evidence/m3_provenance_summary.json",
}

M4_ADDITIONAL_EVIDENCE = {
    "m4_domain_registry.json": ROOT / "review_evidence/m4_domain_registry.json",
    "m4_domain_assessment.json": ROOT / "review_evidence/m4_domain_assessment.json",
    "m4_domain_shift_summary.csv": ROOT / "review_evidence/m4_domain_shift_summary.csv",
    "m4_domain_shift_summary.json": ROOT / "review_evidence/m4_domain_shift_summary.json",
    "m4_safety_gate_test_summary.json": ROOT / "review_evidence/m4_safety_gate_test_summary.json",
    "m4_provenance_summary.json": ROOT / "review_evidence/m4_provenance_summary.json",
    "m4_review_manifest.json": ROOT / "review_evidence/m4_review_manifest.json",
    "m4_authorization_registry_verification.json": (
        ROOT / "review_evidence/m4_authorization_registry_verification.json"
    ),
    "m4_reviewer_authorization_summary.json": (
        ROOT / "review_evidence/m4_reviewer_authorization_summary.json"
    ),
    "m4_source_authorization_summary.json": (
        ROOT / "review_evidence/m4_source_authorization_summary.json"
    ),
    "m4_dataset_access_authentication_summary.json": (
        ROOT / "review_evidence/m4_dataset_access_authentication_summary.json"
    ),
}

M5_ADDITIONAL_EVIDENCE = {
    "m5_study_registry_summary.json": ROOT / "review_evidence/m5_study_registry_summary.json",
    "m5_database_schema_summary.json": ROOT / "review_evidence/m5_database_schema_summary.json",
    "m5_consent_governance_summary.json": ROOT
    / "review_evidence/m5_consent_governance_summary.json",
    "m5_dataset_access_summary.json": ROOT / "review_evidence/m5_dataset_access_summary.json",
    "m5_session_pipeline_summary.json": ROOT / "review_evidence/m5_session_pipeline_summary.json",
    "m5_quality_control_summary.json": ROOT / "review_evidence/m5_quality_control_summary.json",
    "m5_longitudinal_analysis_summary.json": ROOT
    / "review_evidence/m5_longitudinal_analysis_summary.json",
    "m5_privacy_audit_summary.json": ROOT / "review_evidence/m5_privacy_audit_summary.json",
    "m5_provenance_summary.json": ROOT / "review_evidence/m5_provenance_summary.json",
    "m5_test_summary.json": ROOT / "review_evidence/m5_test_summary.json",
    "m5_review_manifest.json": ROOT / "review_evidence/m5_review_manifest.json",
}

M6_ADDITIONAL_EVIDENCE = {
    "m6_dataset_readiness.json": ROOT / "review_evidence/m6_dataset_readiness.json",
    "m6_experiment_summary.json": ROOT / "review_evidence/m6_experiment_summary.json",
    "m6_model_card.json": ROOT / "review_evidence/m6_model_card.json",
    "m6_model_card.html": ROOT / "review_evidence/m6_model_card.html",
    "m6_database_and_auth_summary.json": (
        ROOT / "review_evidence/m6_database_and_auth_summary.json"
    ),
    "m6_prediction_service_summary.json": (
        ROOT / "review_evidence/m6_prediction_service_summary.json"
    ),
    "m6_ui_architecture_summary.json": (ROOT / "review_evidence/m6_ui_architecture_summary.json"),
    "m6_provenance_summary.json": ROOT / "review_evidence/m6_provenance_summary.json",
    "m6_test_summary.json": ROOT / "review_evidence/m6_test_summary.json",
    "m6_review_manifest.json": ROOT / "review_evidence/m6_review_manifest.json",
}


def get_evidence_sources(milestone: str = "m1") -> dict[str, Path]:
    """Return the evidence mapping for the given milestone."""
    m = str(milestone).strip().lower()
    if m == "m6":
        return {
            **EVIDENCE_SOURCES,
            **M2_ADDITIONAL_EVIDENCE,
            **M3_ADDITIONAL_EVIDENCE,
            **M4_ADDITIONAL_EVIDENCE,
            **M5_ADDITIONAL_EVIDENCE,
            **M6_ADDITIONAL_EVIDENCE,
        }
    if m == "m5":
        return {
            **EVIDENCE_SOURCES,
            **M2_ADDITIONAL_EVIDENCE,
            **M3_ADDITIONAL_EVIDENCE,
            **M4_ADDITIONAL_EVIDENCE,
            **M5_ADDITIONAL_EVIDENCE,
        }
    if m == "m4":
        return {
            **EVIDENCE_SOURCES,
            **M2_ADDITIONAL_EVIDENCE,
            **M3_ADDITIONAL_EVIDENCE,
            **M4_ADDITIONAL_EVIDENCE,
        }
    if m == "m3":
        return {**EVIDENCE_SOURCES, **M2_ADDITIONAL_EVIDENCE, **M3_ADDITIONAL_EVIDENCE}
    if m == "m2":
        return {**EVIDENCE_SOURCES, **M2_ADDITIONAL_EVIDENCE}
    return dict(EVIDENCE_SOURCES)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def _truthy(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"true", "1", "yes", "y"}


def _render_aggregate_dataset_audit(
    manifest_path: Path | None = None,
    extraction_path: Path | None = None,
) -> bytes:
    """Render cohort QC counts without publishing sample-level identifiers."""
    manifest_file = manifest_path or (ROOT / "data/processed/feature_manifest.csv")
    extraction_file = extraction_path or (ROOT / "data/processed/feature_extraction_report.csv")
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Required manifest file is missing: {manifest_file}")
    if not extraction_file.is_file():
        raise FileNotFoundError(f"Required extraction report is missing: {extraction_file}")
    manifest = _read_csv(manifest_file)
    extraction = _read_csv(extraction_file)
    labels = {row["sample_id"]: row["class_label"].strip().upper() for row in manifest}
    if not manifest or not extraction or set(labels) != {row["sample_id"] for row in extraction}:
        raise ValueError(
            "Manifest and extraction report must contain the same nonempty sample set."
        )

    success = [
        row for row in extraction if row["extraction_status"].strip().casefold() == "success"
    ]
    failed = [row for row in extraction if row["extraction_status"].strip().casefold() != "success"]
    accepted_counts = Counter(labels[row["sample_id"]] for row in success)
    excluded_counts = Counter(labels[row["sample_id"]] for row in failed)
    reasons = [row.get("failure_reason", "") for row in failed]
    clipping_exclusions = sum("clip" in reason.casefold() for reason in reasons)
    nonclipping_exclusions = len(failed) - clipping_exclusions

    hashes = [row.get("waveform_sha256", "").strip().casefold() for row in manifest]
    duplicate_hash_rows = sum(
        count for value, count in Counter(hashes).items() if value and count > 1
    )
    label_mismatches = sum(not _truthy(row.get("label_match")) for row in manifest)
    metadata_mismatches = sum(not _truthy(row.get("metadata_match")) for row in manifest)
    participant_count = len(
        {row["participant_id"] for row in manifest if row.get("participant_id")}
    )
    group_counts = Counter(row["class_label"].strip().upper() for row in manifest)

    content = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VoxNeuro UAMS aggregate dataset audit</title>
<style>
body {{ font:16px/1.55 system-ui,sans-serif;max-width:900px;margin:2rem auto;
       padding:0 1rem;color:#172f38 }}
table {{ border-collapse:collapse;width:100% }}
th,td {{ border:1px solid #ccd8dc;padding:.6rem;text-align:left }}
th {{ background:#eff5f5 }}
.callout {{ padding:1rem;border-left:4px solid #b56d14;background:#fff7e9 }}
</style>
</head>
<body>
<h1>UAMS dataset quality audit</h1>
<p>Aggregate-only summary generated from the local manifest and feature-extraction receipt.
No sample identifiers are included in this report.</p>
<h2>Source cohort</h2><table><tbody>
<tr><th>Manifest recordings</th><td>{len(manifest)}</td></tr>
<tr><th>Unique participants</th><td>{participant_count}</td></tr>
<tr><th>Healthy controls</th><td>{group_counts.get("HC", 0)}</td></tr>
<tr><th>Parkinson group</th><td>{group_counts.get("PD", 0)}</td></tr>
<tr><th>Label mismatches</th><td>{label_mismatches}</td></tr>
<tr><th>Metadata mismatches</th><td>{metadata_mismatches}</td></tr>
<tr><th>Duplicate waveform-hash rows</th><td>{duplicate_hash_rows}</td></tr>
</tbody></table>
<h2>Feature extraction</h2><table><tbody>
<tr><th>Core39 extraction success</th><td>{len(success)} of {len(extraction)}</td></tr>
<tr><th>Accepted PD participants</th><td>{accepted_counts.get("PD", 0)}</td></tr>
<tr><th>Accepted healthy-control participants</th><td>{accepted_counts.get("HC", 0)}</td></tr>
<tr><th>Reviewed PD exclusions</th><td>{excluded_counts.get("PD", 0)}</td></tr>
<tr><th>Reviewed healthy-control exclusions</th><td>{excluded_counts.get("HC", 0)}</td></tr>
<tr><th>Clipping-related exclusions</th><td>{clipping_exclusions}</td></tr>
<tr><th>Other extraction exclusions</th><td>{nonclipping_exclusions}</td></tr>
</tbody></table>
<div class="callout"><strong>Interpretation:</strong> all quality exclusions are in the
Parkinson group, so class-specific missingness may bias the cohort. These are historical
research recordings and cannot be rerecorded as a corrective action. This audit does not
establish representativeness or clinical validity.</div>
<p>Source: UAMS Figshare DOI 10.6084/m9.figshare.23849127.v1. Voice files and
participant-level predictions are not included.</p>
</body>
</html>"""
    rendered = content.encode("utf-8")
    if manifest_path is None:
        output = ROOT / "artifacts/reports/dataset_audit/uams_dataset_audit.html"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(rendered)
    return rendered


def _review_readme(evidence: dict[str, bytes], milestone: str = "m1") -> bytes:
    rows = "\n".join(
        f"- `{name}` — SHA-256 `{hashlib.sha256(payload).hexdigest()}`"
        for name, payload in sorted(evidence.items())
    )
    title = f"VoxNeuro AI review bundle ({milestone.upper()})"
    content = f"""{title}
========================

This ZIP contains the complete compact source package plus aggregate model-evaluation evidence.
The hashes below let a reviewer check the exact evidence files.

Scope and privacy
-----------------
- `review_evidence/` contains cohort summaries, fold metrics, and provenance receipts.
- Audio, participant-level feature/prediction rows, and model binaries are excluded.
- The review package includes aggregate exclusion counts and reasons;
  participant-level exclusion IDs are excluded for privacy.
  The supplemental dataset audit HTML contains aggregate counts only.
- The bundled feature-extraction receipt replaces its excluded-ID list with a count.
- UAMS results are internal estimates from a small, age-confounded cohort. They are not
  external or clinical validation. When local model/evaluation receipts are present, the app
  may show a separate, explicitly unvalidated exploratory candidate after input checks pass;
  its approved prediction path remains disabled.
- UCI is a separate pre-extracted feature benchmark; it does not validate raw-WAV processing.
- Exact evaluation settings and limits are in `configs/model_config.yaml`, `docs/methodology/`,
  and `docs/reports/MODEL_CARD.md`.

Evidence files
--------------
{rows}

The source inventory excludes this README and `review_evidence/`: they are review
attachments, not project source files.
"""
    return content.encode("utf-8")


def _write_member(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload)


def build_review_bundle(
    output_path: Path | None = None,
    *,
    milestone: str = "m1",
    manifest_path: Path | None = None,
    extraction_report_path: Path | None = None,
    evidence_sources: dict[str, Path] | None = None,
    source_archive_path: Path | None = None,
) -> dict[str, object]:
    """Rebuild the source archive and add only aggregate, hashed review evidence."""
    active_evidence = (
        evidence_sources if evidence_sources is not None else get_evidence_sources(milestone)
    )
    for _name, path in active_evidence.items():
        if not path.is_file():
            raise FileNotFoundError(f"Required review evidence is missing: {path}")

    audit_payload = _render_aggregate_dataset_audit(
        manifest_path=manifest_path, extraction_path=extraction_report_path
    )

    if source_archive_path is not None and source_archive_path.is_file():
        source_archive = source_archive_path
        with zipfile.ZipFile(source_archive) as sz:
            source_members_count = len(sz.namelist())
    else:
        source_report = build_archive()
        source_archive = SOURCE_ARCHIVE
        source_members_count = source_report["members"]

    evidence = {"uams_dataset_audit.html": audit_payload}
    for name, path in active_evidence.items():
        payload = path.read_bytes()
        if name == "uams_feature_extraction_receipt.json":
            receipt = json.loads(payload)
            excluded_ids = receipt.pop("excluded_sample_ids", [])
            receipt["excluded_recording_count"] = len(excluded_ids)
            receipt["review_bundle_redactions"] = ["excluded_sample_ids removed; count retained"]
            payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
        evidence[name] = payload

    audit_html = evidence["uams_dataset_audit.html"].decode("utf-8").casefold()
    if re.search(r"\buams-\d+\b", audit_html):
        raise ValueError("Aggregate dataset audit must not include sample identifiers.")
    readme = _review_readme(evidence, milestone=milestone)
    m = str(milestone).strip().lower()
    default_out = (
        M6_ARCHIVE
        if m == "m6"
        else M5_ARCHIVE
        if m == "m5"
        else M4_ARCHIVE
        if m == "m4"
        else M3_ARCHIVE
        if m == "m3"
        else M2_ARCHIVE
        if m == "m2"
        else REVIEW_ARCHIVE
    )
    target_out = output_path or default_out
    output = target_out.resolve()
    with tempfile.NamedTemporaryFile(
        prefix=f".{output.stem}-", suffix=".tmp", dir=output.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(source_archive) as source_zip:
            source_names = source_zip.namelist()
            if source_zip.testzip() is not None:
                raise zipfile.BadZipFile("Source archive CRC validation failed.")
            with zipfile.ZipFile(
                temporary_path,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            ) as review_zip:
                for name in source_names:
                    _write_member(review_zip, name, source_zip.read(name))
                _write_member(review_zip, "AI_REVIEW_BUNDLE_README.txt", readme)
                for name, payload in sorted(evidence.items()):
                    _write_member(review_zip, f"review_evidence/{name}", payload)
        with zipfile.ZipFile(temporary_path) as review_zip:
            if review_zip.testzip() is not None:
                raise zipfile.BadZipFile("AI review bundle CRC validation failed.")
            actual_names = set(review_zip.namelist())
            expected_names = (
                set(source_names)
                | {"AI_REVIEW_BUNDLE_README.txt"}
                | {f"review_evidence/{name}" for name in evidence}
            )
            if actual_names != expected_names:
                raise zipfile.BadZipFile("AI review bundle members differ from the expected set.")
            forbidden = [
                name
                for name in actual_names
                if name.casefold().endswith(
                    (".wav", ".joblib", ".pkl", ".parquet", ".db", ".sqlite", ".sqlite3")
                )
                or "oof_predictions" in name.casefold()
                or "matching_assignments" in name.casefold()
                or (
                    name.startswith("review_evidence/")
                    and b"uams-0" in review_zip.read(name).lower()
                )
            ]
            if forbidden:
                raise zipfile.BadZipFile(
                    f"Non-aggregate or excluded evidence entered bundle: {forbidden}"
                )

            path_leak_pattern = re.compile(rb"[A-Za-z]:(?:\\\\|\\|/(?!/))|/[Uu]sers/|/home/")
            for ev_name, ev_bytes in evidence.items():
                if path_leak_pattern.search(ev_bytes):
                    raise ValueError(f"Workstation path detected in review_evidence/{ev_name}")

            for manifest_name in (
                "m4_review_manifest.json",
                "m5_review_manifest.json",
                "m6_review_manifest.json",
            ):
                if manifest_name in evidence:
                    manifest_data = json.loads(evidence[manifest_name].decode("utf-8"))
                    entries = [
                        (fname, meta.get("sha256"))
                        for fname, meta in manifest_data.get("files", {}).items()
                    ] + [
                        (
                            item["path"].removeprefix("review_evidence/"),
                            item.get("sha256"),
                        )
                        for item in manifest_data.get("artifacts", [])
                    ]
                    if not entries:
                        raise ValueError(f"{manifest_name} contains no manifest entries")
                    for fname, expected_sha in entries:
                        if fname not in evidence:
                            raise ValueError(f"{manifest_name} references missing file {fname!r}")
                        actual_sha = hashlib.sha256(evidence[fname]).hexdigest()
                        if actual_sha != expected_sha:
                            raise ValueError(
                                f"{manifest_name} checksum mismatch for {fname!r}: "
                                f"{actual_sha} != {expected_sha}"
                            )
        size = temporary_path.stat().st_size
        if size > 5 * 1024 * 1024:
            raise ValueError(
                f"AI review bundle unexpectedly exceeds the 5 MiB limit: {size} bytes."
            )
        os.replace(temporary_path, output)
    finally:
        temporary_path.unlink(missing_ok=True)

    return {
        "path": str(output),
        "bytes": size,
        "members": len(source_names) + len(evidence) + 1,
        "source_members": source_members_count,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an AI review bundle.")
    parser.add_argument(
        "--milestone",
        choices=["m1", "m2", "m3", "m4", "m5", "m6"],
        default="m6",
        help="Target milestone review evidence set (default: m5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to output archive (default: depends on --milestone)",
    )
    args = parser.parse_args(argv)

    report = build_review_bundle(output_path=args.output, milestone=args.milestone)
    print(
        f"PASS AI review bundle: {report['members']} files ({report['source_members']} source, "
        f"{report['members'] - report['source_members']} review attachments), "
        f"{report['bytes']:,} bytes, SHA-256 {report['sha256']}"
    )
    print(report["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
