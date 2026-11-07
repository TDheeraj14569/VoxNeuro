"""Feature names, order, units, and definitions for schema voxneuro.voice.v3."""

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FeatureDefinition:
    name: str
    units: str
    method: str
    validity: str
    missing_policy: str = "NaN; impute only inside each training fold"


PITCH = [
    FeatureDefinition(
        "f0_mean_hz",
        "Hz",
        "Praat autocorrelation pitch; mean voiced frames",
        "At least 3 valid voiced frames",
    ),
    FeatureDefinition(
        "f0_median_hz",
        "Hz",
        "Praat autocorrelation pitch; median voiced frames",
        "At least 3 valid voiced frames",
    ),
    FeatureDefinition(
        "f0_sd_hz", "Hz", "Sample standard deviation of voiced F0", "At least 3 valid voiced frames"
    ),
    FeatureDefinition(
        "f0_min_hz", "Hz", "Minimum valid voiced F0", "At least 3 valid voiced frames"
    ),
    FeatureDefinition(
        "f0_max_hz", "Hz", "Maximum valid voiced F0", "At least 3 valid voiced frames"
    ),
    FeatureDefinition(
        "f0_range_hz", "Hz", "Maximum minus minimum voiced F0", "At least 3 valid voiced frames"
    ),
]
VOICE = [
    FeatureDefinition(
        "jitter_local",
        "ratio",
        "Praat local jitter: mean absolute consecutive period difference / mean period",
        "Valid periodic pulses; Praat may return undefined",
    ),
    FeatureDefinition(
        "shimmer_local",
        "ratio",
        "Praat local shimmer: mean absolute consecutive pulse-amplitude difference "
        "/ mean amplitude",
        "Valid periodic pulses; Praat may return undefined",
    ),
    FeatureDefinition(
        "hnr_mean_db",
        "dB",
        "Praat cross-correlation harmonicity; mean valid voiced frames",
        "At least one valid voiced harmonicity frame (> -199 dB)",
    ),
]
MFCC = [
    FeatureDefinition(
        f"mfcc_{i:02d}_{stat}",
        "dimensionless numerical coefficient",
        f"DCT coefficient from the log-Mel power spectrum; Librosa MFCC index {i} "
        f"(zero-based); {stat} across frames",
        "At least one frame" if stat == "mean" else "At least two frames",
    )
    for i in range(13)
    for stat in ("mean", "sd")
]
SPECTRAL = [
    FeatureDefinition(
        "spectral_centroid_mean_hz",
        "Hz",
        "Librosa spectral centroid; mean over frames",
        "At least one frame",
    ),
    FeatureDefinition(
        "spectral_rolloff_mean_hz",
        "Hz",
        "Librosa 85% spectral rolloff; mean over frames",
        "At least one frame",
    ),
    FeatureDefinition(
        "spectral_bandwidth_mean_hz",
        "Hz",
        "Librosa spectral bandwidth; mean over frames",
        "At least one frame",
    ),
    FeatureDefinition(
        "zero_crossing_rate_mean",
        "fraction",
        "Librosa zero-crossing rate; mean over frames",
        "At least one frame",
    ),
]
FEATURE_DEFINITIONS = PITCH + VOICE + MFCC + SPECTRAL
FEATURE_NAMES = [feature.name for feature in FEATURE_DEFINITIONS]
SCHEMA_VERSION = "voxneuro.voice.v3"


def schema_document() -> dict[str, object]:
    """Return a JSON-serializable feature schema."""
    return {
        "schema_version": SCHEMA_VERSION,
        "feature_order": FEATURE_NAMES,
        "features": [asdict(f) for f in FEATURE_DEFINITIONS],
    }


def schema_fingerprint() -> str:
    """Return a stable digest of feature names, order, units, and measurement definitions."""
    payload = json.dumps(schema_document(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def feature_config_fingerprint(config: dict[str, Any]) -> str:
    """Fingerprint only the settings that control feature extraction."""
    settings = {key: value for key, value in config.items() if key != "schema_version"}
    return configuration_fingerprint(settings)


def configuration_fingerprint(config: dict[str, Any]) -> str:
    """Return a stable SHA-256 for a JSON-compatible configuration mapping."""
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()
