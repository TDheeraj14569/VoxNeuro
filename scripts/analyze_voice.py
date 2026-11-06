"""Analyse a WAV locally and write an honest, self-contained HTML report."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from voxneuro.audio.io import decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.validation import AudioValidationConfig, validate_audio
from voxneuro.config import load_config
from voxneuro.exceptions import VoxNeuroError
from voxneuro.features.extractor import extract_features
from voxneuro.features.schema import configuration_fingerprint
from voxneuro.reporting.html_report import render_voice_report_html
from voxneuro.reporting.report import build_report

ROOT = Path(__file__).resolve().parents[1]


def _analysis_config() -> tuple[AudioValidationConfig, dict, dict]:
    audio_config = load_config("audio_config.yaml")
    feature_config = load_config("feature_config.yaml")
    feature_config.pop("schema_version", None)
    validation = AudioValidationConfig(
        min_duration_seconds=float(audio_config["min_duration_seconds"]),
        max_duration_seconds=float(audio_config["max_duration_seconds"]),
        min_rms=float(audio_config["min_rms"]),
        max_peak=float(audio_config["max_peak"]),
        clipping_fraction_limit=float(audio_config["clipping_fraction_limit"]),
        min_voiced_fraction=float(audio_config["min_voiced_fraction"]),
        frame_ms=int(audio_config["frame_ms"]),
        mono_policy=str(audio_config["mono_policy"]),
        pitch_floor_hz=float(feature_config["pitch_floor_hz"]),
        pitch_ceiling_hz=float(feature_config["pitch_ceiling_hz"]),
    )
    return validation, feature_config, audio_config


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a WAV, extract the current Core39 acoustic measurements, and write a "
            "local HTML report. This command does not predict PD/HC status."
        )
    )
    parser.add_argument("--audio", required=True, type=Path, help="Path to a WAV file")
    parser.add_argument(
        "--report",
        type=Path,
        help="HTML output path; defaults to a timestamped file under artifacts/reports/individual",
    )
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error(f"WAV file does not exist: {args.audio}")
    max_bytes = int(load_config("application_config.yaml")["max_upload_mb"]) * 1024 * 1024
    if args.audio.stat().st_size > max_bytes:
        print(f"Input WAV exceeds the configured {max_bytes // (1024 * 1024)} MB size limit.")
        return 2
    try:
        validation_config, feature_config, audio_config = _analysis_config()
        record = decode_audio(args.audio.read_bytes())
        quality = validate_audio(record, validation_config)
        if not quality.valid:
            print("Recording failed technical quality checks:")
            for message in quality.errors:
                print(f"- {message}")
            for message in quality.warnings:
                print(f"- Warning: {message}")
            return 1
        processed = preprocess_audio(
            record,
            target_sample_rate=int(audio_config["target_sample_rate"]),
            silence_relative_db=float(audio_config["silence_relative_db"]),
            mono_policy=str(audio_config["mono_policy"]),
            validation_config=validation_config,
        )
        features = extract_features(
            processed.samples,
            processed.sample_rate,
            original_sample_rate=record.sample_rate,
            preprocessing_config_fingerprint=configuration_fingerprint(audio_config),
            **feature_config,
        )
    except (OSError, ValueError, VoxNeuroError) as exc:
        print(f"WAV analysis failed: {exc}")
        return 1

    report = build_report(
        {
            "valid": quality.valid,
            "duration_seconds": quality.duration_seconds,
            "sample_rate_hz": record.sample_rate,
            "channels": record.channels,
            "subtype": record.subtype,
            "peak_amplitude_fs": quality.peak_amplitude,
            "rms_amplitude_fs": quality.rms_amplitude,
            "clipping_fraction": quality.clipping_fraction,
            "voiced_fraction": quality.voiced_fraction,
            "active_fraction": quality.active_fraction,
            "warnings": quality.warnings,
        },
        features,
        {
            "target_sample_rate_hz": processed.sample_rate,
            "original_sample_rate_hz": processed.original_sample_rate,
            "dc_offset_removed_fs": processed.dc_offset_removed,
            "trim_start_seconds": processed.trim_start_seconds,
            "trimmed_tail_seconds": processed.trimmed_tail_seconds,
            "retained_duration_seconds": processed.retained_duration_seconds,
            "resampled": processed.resampled,
        },
        model_status=(
            "Unavailable for this recording: recording-domain compatibility and clinical "
            "validation are not established."
        ),
    )
    report_path = args.report or (
        ROOT
        / "artifacts"
        / "reports"
        / "individual"
        / f"voice-analysis-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.html"
    )
    if report_path.suffix.casefold() not in {".html", ".htm"}:
        print("Report output path must have an .html or .htm extension.")
        return 2
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_voice_report_html(
            report,
            processed_samples=processed.samples,
            sample_rate=processed.sample_rate,
        ),
        encoding="utf-8",
    )
    print(f"Technical quality: passed; extracted {len(features)} feature/provenance values.")
    print(f"Feature schema: {features['schema_version']}.")
    print(f"HTML report: {report_path.resolve()}")
    print(
        "No disease classification was made. This research prototype cannot establish "
        "recording-domain compatibility or a diagnosis."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
