"""Inspect supplied UAMS/UCI archives and write a privacy-safe dataset report."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath, PureWindowsPath

import pandas as pd
import soundfile as sf

from voxneuro.dataset.uci import load_uci_feature_table, load_uci_schema, uci_schema_fingerprint
from voxneuro.dataset.validation import read_json_object

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_UAMS_MD5 = {
    "PD_AH.zip": "2e525e419abdad509e5cbf201e30ef36",
    "HC_AH.zip": "55fd33d365380372dcfbae4f7f520246",
}
EXPECTED_UAMS_WAVS = {"PD_AH.zip": 40, "HC_AH.zip": 41}


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_uci_members(members: list[str], verbose_listing: str) -> None:
    """Accept only the official single-file UCI RAR layout and reject links/traversal."""
    csv_member = str(load_uci_schema()["csv_member"])
    if members != [csv_member]:
        raise ValueError(f"Unexpected UCI archive layout; expected only {csv_member}.")
    lines = [line for line in verbose_listing.splitlines() if line.strip()]
    if len(lines) != 1 or not lines[0].startswith("-"):
        raise ValueError("UCI RAR must contain one regular file and no links or special files.")
    if lines[0].split()[-1] != csv_member:
        raise ValueError("UCI RAR verbose listing does not match its member listing.")
    for member in members:
        normalized = member.replace("\\", "/")
        relative = PurePosixPath(normalized)
        windows_relative = PureWindowsPath(member)
        if (
            relative.is_absolute()
            or windows_relative.is_absolute()
            or windows_relative.drive
            or ".." in relative.parts
            or relative.as_posix() != csv_member
        ):
            raise ValueError(f"Unsafe UCI archive member path: {member!r}")


def _load_uci_table(path: Path) -> pd.DataFrame:
    """Read and validate the fixed official UCI feature-table release."""
    return load_uci_feature_table(path)


def _extract_uci_rar(archive: Path, output: Path, csv_path: Path) -> pd.DataFrame:
    """Extract into an isolated staging directory and atomically replace only a valid CSV."""
    try:
        listing = subprocess.run(
            ["tar", "-tf", str(archive)], check=True, capture_output=True, text=True
        ).stdout.splitlines()
        verbose = subprocess.run(
            ["tar", "-tvf", str(archive)], check=True, capture_output=True, text=True
        ).stdout
    except FileNotFoundError as exc:
        raise RuntimeError(
            "A bsdtar-compatible tar command is required to inspect the UCI RAR archive."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Could not inspect the UCI RAR archive. Install a RAR-capable bsdtar/libarchive "
            "tar command and ensure it is available as 'tar' on PATH."
        ) from exc
    _validate_uci_members(listing, verbose)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".uci-rar-", dir=output.parent) as temporary:
        staging = Path(temporary)
        try:
            subprocess.run(
                ["tar", "-xf", str(archive), "-C", str(staging)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(
                "Could not extract the UCI RAR archive with the installed tar command."
            ) from exc
        staged_csv = staging / str(load_uci_schema()["csv_member"])
        if staged_csv.is_symlink() or not staged_csv.is_file():
            raise ValueError("UCI archive did not produce a regular feature CSV.")
        if staged_csv.resolve().parent != staging.resolve():
            raise ValueError("Extracted UCI CSV escaped its temporary directory.")
        frame = _load_uci_table(staged_csv)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_csv, csv_path)
    receipt_path = output / "uci_extraction_receipt.json"
    receipt = {
        "dataset_id": int(load_uci_schema()["dataset_id"]),
        "doi": str(load_uci_schema()["doi"]),
        "official_url": str(load_uci_schema()["publisher_page"]),
        "schema_manifest_sha256": uci_schema_fingerprint(),
        "publisher_archive_sha256": load_uci_schema()["publisher_archive_sha256"],
        "archive_sha256": sha256(archive),
        "csv_sha256": sha256(csv_path),
        "rows": int(frame.shape[0]),
        "columns": int(frame.shape[1]),
    }
    temporary_receipt = receipt_path.with_suffix(".json.tmp")
    temporary_receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    os.replace(temporary_receipt, receipt_path)
    return frame


def extract_zip_once(
    archive: Path,
    destination: Path,
    *,
    expected_md5: str,
    expected_wavs: int,
    expected_class_folder: str,
) -> None:
    """Verify and safely extract a complete WAV archive before replacing prior output."""
    actual_md5 = md5(archive)
    if actual_md5.casefold() != expected_md5.casefold():
        raise ValueError(
            f"Checksum mismatch for {archive.name}: expected {expected_md5}, got {actual_md5}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-extract-", dir=destination.parent
    ) as temporary:
        staging = Path(temporary) / "complete"
        staging.mkdir()
        with zipfile.ZipFile(archive) as source:
            corrupt_member = source.testzip()
            if corrupt_member is not None:
                raise ValueError(f"Corrupt member {corrupt_member!r} in {archive.name}")
            seen_members: set[str] = set()
            for member in source.infolist():
                normalized_name = member.filename.replace("\\", "/")
                relative = PurePosixPath(normalized_name)
                windows_relative = PureWindowsPath(member.filename)
                normalized_key = relative.as_posix().casefold()
                if (
                    relative.is_absolute()
                    or windows_relative.is_absolute()
                    or windows_relative.drive
                    or ".." in relative.parts
                    or any(
                        ":" in part or part.rstrip(". ") != part or any(ord(c) < 32 for c in part)
                        for part in relative.parts
                    )
                ):
                    raise ValueError(f"Unsafe archive member path: {member.filename!r}")
                if not relative.parts:
                    continue
                if normalized_key in seen_members:
                    raise ValueError(f"Duplicate archive member path: {member.filename!r}")
                seen_members.add(normalized_key)
                mode = member.external_attr >> 16
                if (mode & 0o170000) == 0o120000:
                    raise ValueError(f"Symbolic links are not accepted in {archive.name}")
                target = staging.joinpath(*relative.parts)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        wavs = sorted(staging.rglob("*.wav"))
        if len(wavs) != expected_wavs:
            raise ValueError(
                f"{archive.name} contains {len(wavs)} WAV files; expected {expected_wavs}."
            )
        for wav in wavs:
            class_folders = {part.casefold() for part in wav.relative_to(staging).parts} & {
                "pd_ah",
                "hc_ah",
            }
            if class_folders != {expected_class_folder.casefold()}:
                raise ValueError(
                    f"Unexpected class folder in {archive.name}: {wav.relative_to(staging)}"
                )
            try:
                sf.info(wav)
            except (RuntimeError, ValueError, sf.LibsndfileError) as exc:
                raise ValueError(f"Invalid WAV member {wav.relative_to(staging)}") from exc
        backup = destination.with_name(f"{destination.name}.previous-{uuid.uuid4().hex}")
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except OSError:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)


def inspect_uams() -> dict:
    raw = ROOT / "data" / "raw" / "uams"
    interim = ROOT / "data" / "interim" / "uams"
    for name in ("PD_AH.zip", "HC_AH.zip"):
        archive = raw / name
        if not archive.is_file():
            raise FileNotFoundError(
                f"Missing UAMS archive {archive}. Follow docs/dataset/UAMS_DATASET_REPORT.md."
            )
        expected_folder = "PD_AH" if name.startswith("PD") else "HC_AH"
        extract_zip_once(
            archive,
            interim / ("pd" if archive.stem.startswith("PD") else "hc"),
            expected_md5=EXPECTED_UAMS_MD5[name],
            expected_wavs=EXPECTED_UAMS_WAVS[name],
            expected_class_folder=expected_folder,
        )
    workbook = raw / "Demographics_age_sex.xlsx"
    if not workbook.is_file():
        raise FileNotFoundError(f"Missing demographics workbook {workbook}.")
    sheets = pd.read_excel(workbook, sheet_name=None)
    sheet_summary = {
        name: {"rows": int(len(frame)), "columns": [str(c) for c in frame.columns]}
        for name, frame in sheets.items()
    }
    wavs = sorted(interim.rglob("*.wav"))
    formats: Counter = Counter()
    rates: Counter = Counter()
    channels: Counter = Counter()
    durations = []
    hashes = Counter()
    corrupt = 0
    for path in wavs:
        try:
            info = sf.info(path)
            formats[info.format + "/" + info.subtype] += 1
            rates[int(info.samplerate)] += 1
            channels[int(info.channels)] += 1
            durations.append(float(info.duration))
            hashes[md5(path)] += 1
        except (RuntimeError, ValueError, sf.LibsndfileError):
            corrupt += 1
    groups = {"HC": 0, "PD": 0}
    for path in wavs:
        parts = {part.casefold() for part in path.parts}
        class_folders = parts & {"pd_ah", "hc_ah"}
        if len(class_folders) != 1:
            raise ValueError(f"Unrecognized or ambiguous diagnosis folder for {path}")
        groups["PD" if "pd_ah" in class_folders else "HC"] += 1
    report = {
        "source": "Figshare DOI 10.6084/m9.figshare.23849127.v1",
        "license": "CC BY 4.0 per Figshare API record",
        "archive_checksums_md5": {path.name: md5(path) for path in sorted(raw.glob("*.zip"))},
        "archive_checksums_match_figshare": True,
        "wav_count": len(wavs),
        "class_counts_from_archive_directory": groups,
        "format_subtype_counts": dict(formats),
        "sample_rate_counts_hz": dict(rates),
        "channel_counts": dict(channels),
        "duration_seconds": {
            "min": min(durations) if durations else None,
            "median": float(pd.Series(durations).median()) if durations else None,
            "max": max(durations) if durations else None,
        },
        "corrupt_wav_count": corrupt,
        "duplicate_waveform_hash_groups": sum(1 for count in hashes.values() if count > 1),
        "demographics_workbook_sheets": sheet_summary,
        "filename_privacy_review": (
            "Names are pseudonymous-looking codes/UUIDs, not participant names; source folders "
            "encode diagnosis class. Paths are kept out of the report."
        ),
    }
    (ROOT / "docs" / "dataset" / "uams_inspection.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def inspect_uci() -> dict:
    raw = ROOT / "data" / "raw" / "uci" / "download" / "pd_speech_features.rar"
    out = ROOT / "data" / "interim" / "uci"
    csv_path = out / "pd_speech_features.csv"
    if not raw.is_file():
        raise FileNotFoundError(
            "Missing official UCI archive. See docs/dataset/UCI_DATASET_REPORT.md."
        )
    source_hash = sha256(raw)
    receipt_path = out / "uci_extraction_receipt.json"
    frame = None
    if csv_path.is_file() and receipt_path.is_file():
        try:
            receipt = read_json_object(receipt_path, "UCI extraction receipt")
            if (
                receipt.get("dataset_id") == load_uci_schema()["dataset_id"]
                and receipt.get("doi") == load_uci_schema()["doi"]
                and receipt.get("official_url") == load_uci_schema()["publisher_page"]
                and receipt.get("schema_manifest_sha256") == uci_schema_fingerprint()
                and receipt.get("publisher_archive_sha256")
                == load_uci_schema()["publisher_archive_sha256"]
                and receipt.get("archive_sha256") == source_hash
                and receipt.get("csv_sha256") == sha256(csv_path)
            ):
                frame = _load_uci_table(csv_path)
        except ValueError:
            frame = None
    if frame is None:
        frame = _extract_uci_rar(raw, out, csv_path)
    exact_duplicate_rows = frame.duplicated(keep="first")
    duplicate_participant_count = int(frame.loc[exact_duplicate_rows, "id"].nunique())
    report = {
        "source": "UCI Machine Learning Repository, dataset 470, DOI 10.24432/C5MS4X",
        "official_url": str(load_uci_schema()["publisher_page"]),
        "official_download_url": str(load_uci_schema()["official_download_url"]),
        "schema_manifest_sha256": uci_schema_fingerprint(),
        "ordered_header_sha256": str(load_uci_schema()["ordered_header_sha256"]),
        "publisher_archive_sha256": load_uci_schema()["publisher_archive_sha256"],
        "archive_hash_note": (
            "The archive SHA-256 is a local integrity fingerprint; the UCI dataset record "
            "does not publish an archive SHA-256."
        ),
        "license": "CC BY 4.0 per UCI page",
        "archive_bytes": raw.stat().st_size,
        "archive_sha256": source_hash,
        "extracted_csv_sha256": sha256(csv_path),
        "rows": int(frame.shape[0]),
        "columns": int(frame.shape[1]),
        "column_names": [str(c) for c in frame.columns],
        "missing_values": int(frame.isna().sum().sum()),
        "exact_duplicate_rows": int(frame.duplicated().sum()),
        "exact_duplicate_rows_for_sensitivity_analysis": int(exact_duplicate_rows.sum()),
        "participants_with_exact_duplicate_rows": duplicate_participant_count,
        "unique_class_values": frame["class"].value_counts().to_dict()
        if "class" in frame.columns
        else None,
        "participant_label_inconsistencies": int((frame.groupby("id")["class"].nunique() > 1).sum())
        if {"id", "class"} <= set(frame.columns)
        else None,
        "participant_column_candidates": [
            str(c)
            for c in frame.columns
            if str(c).casefold() in {"id", "subject", "participant", "subject_id"}
        ],
        "target_column_candidates": [
            str(c)
            for c in frame.columns
            if "class" in str(c).casefold() or "target" in str(c).casefold()
        ],
        "repeated_rows_per_participant": frame.groupby("id")
        .size()
        .value_counts()
        .sort_index()
        .to_dict()
        if "id" in frame.columns
        else None,
    }
    (ROOT / "docs" / "dataset" / "uci_inspection.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a dataset source without mixing workflows."
    )
    parser.add_argument(
        "--dataset",
        choices=("all", "uams", "uci"),
        default="all",
        help="Select one independent dataset workflow, or inspect both (default).",
    )
    args = parser.parse_args()
    if args.dataset in {"all", "uams"}:
        print("Inspecting UAMS archive...")
        uams = inspect_uams()
        print(
            json.dumps(
                {
                    key: value
                    for key, value in uams.items()
                    if key != "demographics_workbook_sheets"
                },
                indent=2,
            )
        )
    if args.dataset in {"all", "uci"}:
        print("Inspecting UCI archive...")
        uci = inspect_uci()
        summary = {key: value for key, value in uci.items() if key != "column_names"}
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
