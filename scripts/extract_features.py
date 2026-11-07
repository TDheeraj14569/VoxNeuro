"""Extract UAMS voice features with manifest validation and explicit exclusions."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from voxneuro.audio.io import decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.validation import AudioValidationConfig, validate_audio
from voxneuro.config import load_config
from voxneuro.dataset.validation import validate_features, validate_manifest
from voxneuro.features.extractor import extract_features
from voxneuro.features.schema import (
    FEATURE_NAMES,
    SCHEMA_VERSION,
    configuration_fingerprint,
    feature_config_fingerprint,
    schema_fingerprint,
)
from voxneuro.provenance import project_code_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reviewed_exclusion_failures(
    statuses: list[dict[str, str]], policy: dict, requested: bool
) -> tuple[bool, list[str]]:
    failures = [row for row in statuses if row["extraction_status"] != "success"]
    if not failures:
        return True, []
    if not requested:
        return False, ["Partial extraction requires --allow-reviewed-exclusions."]
    approved = policy.get("reviewed_exclusions", {})
    reasons = []
    for row in failures:
        entry = approved.get(row["sample_id"])
        if not isinstance(entry, dict) or entry.get("review_status") != "reviewed":
            reasons.append(
                f"{row['sample_id']} is not explicitly reviewed in the exclusion policy."
            )
            continue
        expected = str(entry.get("expected_failure_fragment", "")).casefold()
        if (
            entry.get("category") != "clipping"
            or not expected
            or expected not in row["failure_reason"].casefold()
        ):
            reasons.append(f"{row['sample_id']} did not fail for its reviewed clipping reason.")
    return not reasons, reasons


def _write_receipt(
    path: Path,
    status: str,
    manifest_path: Path,
    feature_path: Path | None,
    successful: int,
    total: int,
    exclusions: list[str],
    feature_config: dict | None = None,
    preprocessing_config: dict | None = None,
) -> None:
    receipt = {
        "status": status,
        "manifest_sha256": _sha256(manifest_path) if manifest_path.is_file() else None,
        "feature_table_sha256": (
            _sha256(feature_path) if feature_path and feature_path.is_file() else None
        ),
        "feature_schema_version": SCHEMA_VERSION,
        "feature_schema_fingerprint": schema_fingerprint(),
        "feature_config_fingerprint": (
            feature_config_fingerprint(feature_config) if feature_config is not None else None
        ),
        "preprocessing_config_fingerprint": (
            configuration_fingerprint(preprocessing_config)
            if preprocessing_config is not None
            else None
        ),
        "code_version": project_code_fingerprint(),
        "created_utc": datetime.now(UTC).isoformat(),
        "successful_recordings": successful,
        "total_recordings": total,
        "excluded_sample_ids": exclusions,
    }
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-reviewed-exclusions",
        action="store_true",
        help="Accept only sample failures explicitly listed in configs/reviewed_exclusions.yaml.",
    )
    args = parser.parse_args()
    manifest_path = ROOT / "data" / "processed" / "feature_manifest.csv"
    output = ROOT / "data" / "processed"
    report_path = output / "feature_extraction_report.csv"
    receipt_path = output / "feature_extraction_receipt.json"
    feature_path = output / "voice_features.csv"
    if not manifest_path.is_file():
        print("Manifest not found. Run scripts/build_manifest.py first.")
        return 2
    audio_config = load_config("audio_config.yaml")
    full_feature_config = load_config("feature_config.yaml")
    feature_config = dict(full_feature_config)
    feature_config.pop("schema_version", None)
    manifest = pd.read_csv(manifest_path)
    manifest_issues = validate_manifest(manifest, require_integrity=True)
    if manifest_issues:
        print("Manifest validation failed:")
        for issue in manifest_issues:
            print(f"- {issue}")
        _write_receipt(
            receipt_path,
            "blocked_invalid_manifest",
            manifest_path,
            None,
            0,
            len(manifest),
            [],
            full_feature_config,
            audio_config,
        )
        return 1
    quality_config = AudioValidationConfig.from_dict(audio_config, feature_config)
    feature_rows, statuses = [], []
    for row in manifest.to_dict("records"):
        status = {
            "sample_id": str(row["sample_id"]),
            "extraction_status": "failed",
            "failure_reason": "",
        }
        try:
            record = decode_audio(Path(row["audio_path"]).read_bytes())
            quality = validate_audio(record, quality_config)
            if not quality.valid:
                raise ValueError(" ".join(quality.errors))
            processed = preprocess_audio(
                record,
                target_sample_rate=int(audio_config["target_sample_rate"]),
                silence_relative_db=float(audio_config["silence_relative_db"]),
                mono_policy=str(audio_config["mono_policy"]),
                validation_config=quality_config,
            )
            extracted = extract_features(
                processed.samples,
                processed.sample_rate,
                original_sample_rate=record.sample_rate,
                preprocessing_config_fingerprint=configuration_fingerprint(audio_config),
                **feature_config,
            )
            feature_rows.append(
                {
                    "sample_id": row["sample_id"],
                    "participant_id": row["participant_id"],
                    "class_label": row["class_label"],
                    "age": row.get("age"),
                    "sex": row.get("sex"),
                    **{name: extracted[name] for name in FEATURE_NAMES},
                }
            )
            status["extraction_status"] = "success"
        except Exception as exc:
            status["failure_reason"] = str(exc)
        statuses.append(status)
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(statuses).to_csv(report_path, index=False)
    allowed, exclusion_issues = _reviewed_exclusion_failures(
        statuses,
        load_config("reviewed_exclusions.yaml"),
        args.allow_reviewed_exclusions,
    )
    failures = [row for row in statuses if row["extraction_status"] != "success"]
    excluded_ids = [row["sample_id"] for row in failures]
    success_count = len(feature_rows)
    print(f"Extracted features for {success_count}/{len(statuses)} recordings; see {report_path}.")
    if not allowed:
        for issue in exclusion_issues:
            print(f"- {issue}")
        _write_receipt(
            receipt_path,
            "blocked_unreviewed_exclusions",
            manifest_path,
            None,
            success_count,
            len(statuses),
            excluded_ids,
            full_feature_config,
            audio_config,
        )
        print(
            "No final feature table was written; modeling is blocked until failures are reviewed."
        )
        return 1
    columns = ["sample_id", "participant_id", "class_label", "age", "sex", *FEATURE_NAMES]
    feature_frame = pd.DataFrame(feature_rows, columns=columns)
    feature_issues = validate_features(feature_frame, FEATURE_NAMES)
    if feature_issues:
        for issue in feature_issues:
            print(f"Feature-table validation failed: {issue}")
        _write_receipt(
            receipt_path,
            "blocked_invalid_features",
            manifest_path,
            None,
            success_count,
            len(statuses),
            excluded_ids,
            full_feature_config,
            audio_config,
        )
        return 1
    if feature_frame["sample_id"].duplicated().any() or not set(
        feature_frame["class_label"]
    ).issubset({"HC", "PD"}):
        print("Feature-table identity or label validation failed; refusing to save.")
        _write_receipt(
            receipt_path,
            "blocked_invalid_features",
            manifest_path,
            None,
            success_count,
            len(statuses),
            excluded_ids,
            full_feature_config,
            audio_config,
        )
        return 1
    feature_frame.to_csv(feature_path, index=False)
    status = "accepted_reviewed_exclusions" if failures else "complete"
    _write_receipt(
        receipt_path,
        status,
        manifest_path,
        feature_path,
        success_count,
        len(statuses),
        excluded_ids,
        full_feature_config,
        audio_config,
    )
    print(f"Saved validated feature table with status {status} to {feature_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
