"""Small YAML configuration loader with explicit path handling."""

from math import isfinite
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_CONFIG_KEYS: dict[str, set[str]] = {
    "application_config.yaml": {
        "application_name",
        "max_upload_mb",
        "store_recordings",
        "store_reports_by_default",
    },
    "audio_config.yaml": {
        "target_sample_rate",
        "min_duration_seconds",
        "max_duration_seconds",
        "min_rms",
        "max_peak",
        "clipping_fraction_limit",
        "silence_relative_db",
        "frame_ms",
        "min_voiced_fraction",
        "min_harmonic_overtone_fraction",
        "min_second_harmonic_fraction",
        "second_harmonic_min_factor",
        "second_harmonic_max_factor",
        "second_harmonic_trigger_overtone_fraction",
        "min_waveform_kurtosis",
        "mono_policy",
    },
    "feature_config.yaml": {
        "schema_version",
        "pitch_floor_hz",
        "pitch_ceiling_hz",
        "pitch_step_seconds",
        "mfcc_count",
        "mel_bands",
        "fft_window_samples",
        "hop_samples",
        "mel_min_hz",
        "common_max_hz",
        "spectral_rolloff_fraction",
    },
    "model_config.yaml": {
        "random_seed",
        "cv_splits",
        "inner_cv_splits",
        "cv_repeats",
        "bootstrap_iterations",
        "allow_user_microphone_inference",
    },
    "reviewed_exclusions.yaml": {"reviewed_exclusions"},
}


def _require_number(
    value: Any,
    name: str,
    *,
    minimum: float,
    maximum: float,
    strict_minimum: bool = False,
    strict_maximum: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"Configuration value {name!r} must be a finite number.")
    lower_ok = value > minimum if strict_minimum else value >= minimum
    upper_ok = value < maximum if strict_maximum else value <= maximum
    if not lower_ok or not upper_ok:
        left = "(" if strict_minimum else "["
        right = ")" if strict_maximum else "]"
        raise ValueError(
            f"Configuration value {name!r} must be in {left}{minimum}, {maximum}{right}."
        )
    return float(value)


def _validate_config(name: str, value: dict[str, Any]) -> None:
    expected = _CONFIG_KEYS.get(name)
    if expected is None:
        raise ValueError(f"Unsupported configuration file: {name!r}.")
    if name == "reviewed_exclusions.yaml":
        unknown = value.keys() - {"reviewed_exclusions", "reviewed_exclusions_policy"}
        if "reviewed_exclusions" not in value and "reviewed_exclusions_policy" not in value:
            raise ValueError(f"Invalid {name}: missing required reviewed_exclusions key")
        if unknown:
            raise ValueError(f"Invalid {name}: unknown keys: {sorted(unknown)}")
    else:
        missing = expected - value.keys()
        unknown = value.keys() - expected
        if missing or unknown:
            details = []
            if missing:
                details.append(f"missing keys: {sorted(missing)}")
            if unknown:
                details.append(f"unknown keys: {sorted(unknown)}")
            raise ValueError(f"Invalid {name}: " + "; ".join(details))

    if name == "application_config.yaml":
        if not isinstance(value["application_name"], str) or not value["application_name"].strip():
            raise ValueError("application_name must be a non-empty string.")
        if type(value["max_upload_mb"]) is not int or not 1 <= value["max_upload_mb"] <= 512:
            raise ValueError("max_upload_mb must be an integer from 1 through 512.")
        for key in ("store_recordings", "store_reports_by_default"):
            if type(value[key]) is not bool:
                raise ValueError(f"{key} must be a boolean.")
    elif name == "audio_config.yaml":
        if (
            type(value["target_sample_rate"]) is not int
            or not 8000 <= value["target_sample_rate"] <= 48000
        ):
            raise ValueError("target_sample_rate must be an integer from 8000 through 48000 Hz.")
        if type(value["frame_ms"]) is not int or not 5 <= value["frame_ms"] <= 100:
            raise ValueError("frame_ms must be an integer from 5 through 100.")
        _require_number(
            value["min_duration_seconds"],
            "min_duration_seconds",
            minimum=0,
            maximum=3600,
            strict_minimum=True,
        )
        _require_number(
            value["max_duration_seconds"],
            "max_duration_seconds",
            minimum=0,
            maximum=3600,
            strict_minimum=True,
        )
        if value["min_duration_seconds"] >= value["max_duration_seconds"]:
            raise ValueError("min_duration_seconds must be less than max_duration_seconds.")
        _require_number(value["min_rms"], "min_rms", minimum=0, maximum=1)
        _require_number(value["max_peak"], "max_peak", minimum=0, maximum=1, strict_minimum=True)
        _require_number(
            value["clipping_fraction_limit"], "clipping_fraction_limit", minimum=0, maximum=1
        )
        _require_number(
            value["silence_relative_db"],
            "silence_relative_db",
            minimum=0,
            maximum=100,
            strict_minimum=True,
        )
        _require_number(value["min_voiced_fraction"], "min_voiced_fraction", minimum=0, maximum=1)
        _require_number(
            value["min_harmonic_overtone_fraction"],
            "min_harmonic_overtone_fraction",
            minimum=0,
            maximum=1,
        )
        _require_number(
            value["min_second_harmonic_fraction"],
            "min_second_harmonic_fraction",
            minimum=0,
            maximum=1,
        )
        _require_number(
            value["second_harmonic_min_factor"],
            "second_harmonic_min_factor",
            minimum=1.0,
            maximum=3.0,
            strict_minimum=True,
        )
        _require_number(
            value["second_harmonic_max_factor"],
            "second_harmonic_max_factor",
            minimum=1.0,
            maximum=4.0,
            strict_minimum=True,
        )
        if value["second_harmonic_min_factor"] >= value["second_harmonic_max_factor"]:
            raise ValueError(
                "second_harmonic_min_factor must be less than second_harmonic_max_factor."
            )
        _require_number(
            value["second_harmonic_trigger_overtone_fraction"],
            "second_harmonic_trigger_overtone_fraction",
            minimum=0,
            maximum=1,
        )
        _require_number(
            value["min_waveform_kurtosis"], "min_waveform_kurtosis", minimum=0, maximum=10
        )
        if value["mono_policy"] != "average_with_phase_check":
            raise ValueError("mono_policy must be 'average_with_phase_check'.")
    elif name == "feature_config.yaml":
        from voxneuro.features.schema import SCHEMA_VERSION

        if value["schema_version"] != SCHEMA_VERSION:
            raise ValueError(
                "Feature configuration schema_version must exactly match the implementation "
                f"schema ({SCHEMA_VERSION}); got {value['schema_version']!r}."
            )
        if type(value["mfcc_count"]) is not int or value["mfcc_count"] != 13:
            raise ValueError("The current feature schema requires exactly 13 MFCC coefficients.")
        integer_ranges = {
            "mel_bands": (13, 256),
            "fft_window_samples": (256, 8192),
            "hop_samples": (1, 8192),
        }
        for key, (minimum, maximum) in integer_ranges.items():
            if type(value[key]) is not int or not minimum <= value[key] <= maximum:
                raise ValueError(f"{key} must be an integer from {minimum} through {maximum}.")
        for key, bounds in {
            "pitch_floor_hz": (30, 500),
            "pitch_ceiling_hz": (60, 1200),
            "pitch_step_seconds": (0.001, 0.1),
            "mel_min_hz": (0, 1000),
            "common_max_hz": (100, 24000),
            "spectral_rolloff_fraction": (0, 1),
        }.items():
            _require_number(
                value[key],
                key,
                minimum=bounds[0],
                maximum=bounds[1],
                strict_minimum=key
                in {
                    "pitch_floor_hz",
                    "pitch_step_seconds",
                    "common_max_hz",
                    "spectral_rolloff_fraction",
                },
                strict_maximum=key in {"spectral_rolloff_fraction"},
            )
        if value["pitch_floor_hz"] >= value["pitch_ceiling_hz"]:
            raise ValueError("pitch_floor_hz must be less than pitch_ceiling_hz.")
        if value["mfcc_count"] > value["mel_bands"]:
            raise ValueError("mfcc_count cannot exceed mel_bands.")
        if value["hop_samples"] > value["fft_window_samples"]:
            raise ValueError("hop_samples cannot exceed fft_window_samples.")
        if value["fft_window_samples"] & (value["fft_window_samples"] - 1):
            raise ValueError("fft_window_samples must be a power of two.")
        if value["mel_min_hz"] >= value["common_max_hz"]:
            raise ValueError("mel_min_hz must be less than common_max_hz.")
        audio_config = load_config("audio_config.yaml")
        nyquist = audio_config["target_sample_rate"] / 2
        if value["common_max_hz"] >= nyquist:
            raise ValueError(
                "common_max_hz must be strictly below the configured target sample-rate "
                f"Nyquist frequency ({nyquist:g} Hz)."
            )
    elif name == "model_config.yaml":
        if type(value["random_seed"]) is not int or not 0 <= value["random_seed"] <= 2**32 - 1:
            raise ValueError("random_seed must be an integer in [0, 2**32 - 1].")
        if type(value["cv_splits"]) is not int or not 2 <= value["cv_splits"] <= 20:
            raise ValueError("cv_splits must be an integer from 2 through 20.")
        if type(value["inner_cv_splits"]) is not int or not 2 <= value["inner_cv_splits"] <= 10:
            raise ValueError("inner_cv_splits must be an integer from 2 through 10.")
        if type(value["cv_repeats"]) is not int or not 1 <= value["cv_repeats"] <= 10:
            raise ValueError("cv_repeats must be an integer from 1 through 10.")
        if (
            type(value["bootstrap_iterations"]) is not int
            or not 100 <= value["bootstrap_iterations"] <= 10000
        ):
            raise ValueError("bootstrap_iterations must be an integer from 100 through 10000.")
        if type(value["allow_user_microphone_inference"]) is not bool:
            raise ValueError("allow_user_microphone_inference must be a boolean.")
        if value["allow_user_microphone_inference"]:
            raise ValueError("Microphone disease inference is not supported by this prototype.")
    elif name == "reviewed_exclusions.yaml":
        exclusions = value.get("reviewed_exclusions")
        policy = value.get("reviewed_exclusions_policy")
        if exclusions is not None:
            if not isinstance(exclusions, dict) or not exclusions:
                raise ValueError("reviewed_exclusions must be a non-empty mapping.")
            required = {"review_status", "category", "expected_failure_fragment", "reason"}
            for sample_id, record in exclusions.items():
                if (
                    not isinstance(sample_id, str)
                    or not sample_id.strip()
                    or not isinstance(record, dict)
                ):
                    raise ValueError(
                        "Each reviewed exclusion needs a non-empty sample ID and mapping."
                    )
                if set(record) != required:
                    raise ValueError(
                        f"Reviewed exclusion {sample_id!r} has missing or unknown fields."
                    )
                if record["review_status"] != "reviewed" or record["category"] not in {"clipping"}:
                    raise ValueError(
                        f"Reviewed exclusion {sample_id!r} is not an accepted reviewed category."
                    )
                if any(
                    not isinstance(record[key], str) or not record[key].strip()
                    for key in ("expected_failure_fragment", "reason")
                ):
                    raise ValueError(
                        f"Reviewed exclusion {sample_id!r} needs a failure fragment and reason."
                    )
        if policy is not None:
            if not isinstance(policy, dict):
                raise ValueError("reviewed_exclusions_policy must be a mapping.")
            for req in (
                "review_status",
                "total_excluded",
                "categories",
                "expected_failure_fragment",
                "reasons",
            ):
                if req not in policy:
                    raise ValueError(f"reviewed_exclusions_policy missing required key {req!r}")
            if policy["review_status"] != "reviewed":
                raise ValueError("reviewed_exclusions_policy review_status must be 'reviewed'.")


def load_config(name: str) -> dict[str, Any]:
    """Load a named YAML file from the repository config directory."""
    if name not in _CONFIG_KEYS:
        raise ValueError(f"Unsupported configuration file: {name!r}.")
    path = PROJECT_ROOT / "configs" / name
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with path.open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Configuration must contain a YAML mapping: {path}")
    _validate_config(name, value)
    return value
