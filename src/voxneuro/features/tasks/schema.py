"""Task-specific and multi-task envelope feature schemas for VoxNeuro M3.

Defines schemas for:
- DDK syllable repetition: voxneuro.task.ddk.v1
- Connected speech: voxneuro.task.connected_speech.v1
- Vowel space area: voxneuro.task.vowel_space.v1
- Multi-task session envelope: voxneuro.voice.v4
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from voxneuro.features.schema import (
    FEATURE_DEFINITIONS as V3_FEATURE_DEFINITIONS,
)
from voxneuro.features.schema import (
    SCHEMA_VERSION as V3_SCHEMA_VERSION,
)
from voxneuro.features.schema import (
    schema_fingerprint as v3_schema_fingerprint,
)


@dataclass(frozen=True)
class TaskFeatureDefinition:
    """Standardized metadata specification for a speech acoustic feature."""

    name: str
    units: str
    method: str
    validity: str
    missing_policy: str = "null (None); no zero substitution without signal"
    algorithm_version: str = "1.0.0"


# -----------------------------------------------------------------------------
# DDK Schema: voxneuro.task.ddk.v1
# -----------------------------------------------------------------------------
DDK_SCHEMA_VERSION = "voxneuro.task.ddk.v1"

DDK_FEATURE_DEFINITIONS: list[TaskFeatureDefinition] = [
    TaskFeatureDefinition(
        "estimated_event_count",
        "count",
        "Count of detected syllable acoustic onset/peak events",
        "At least 1 event detected",
    ),
    TaskFeatureDefinition(
        "estimated_event_rate_per_s",
        "events/s",
        "Syllable event repetition rate over active speech duration",
        "At least 3 valid events and active duration > 0.2 s",
    ),
    TaskFeatureDefinition(
        "mean_inter_event_interval_s",
        "s",
        "Arithmetic mean duration between consecutive syllable acoustic events",
        "At least 2 valid intervals",
    ),
    TaskFeatureDefinition(
        "median_inter_event_interval_s",
        "s",
        "Median duration between consecutive syllable acoustic events",
        "At least 2 valid intervals",
    ),
    TaskFeatureDefinition(
        "sd_inter_event_interval_s",
        "s",
        "Sample standard deviation of inter-event intervals",
        "At least 3 valid intervals",
    ),
    TaskFeatureDefinition(
        "cv_inter_event_interval",
        "ratio",
        "Coefficient of variation of inter-event intervals (SD / Mean)",
        "At least 3 valid intervals and non-zero mean",
    ),
    TaskFeatureDefinition(
        "rmssd_inter_event_interval_s",
        "s",
        "Root mean square of successive differences between consecutive intervals",
        "At least 3 valid intervals",
    ),
    TaskFeatureDefinition(
        "inter_event_interval_slope_s_per_event",
        "s/event",
        "Linear regression slope of interval duration over sequential event index",
        "At least 4 valid intervals",
    ),
    TaskFeatureDefinition(
        "valid_intervals_count",
        "count",
        "Number of measured inter-event intervals",
        "At least 1 interval",
    ),
    TaskFeatureDefinition(
        "active_speech_duration_s",
        "s",
        "Duration from first detected syllable event to last detected syllable event",
        "At least 2 detected events",
    ),
    TaskFeatureDefinition(
        "task_duration_s",
        "s",
        "Total analyzed recording duration",
        "Valid audio recording",
    ),
]

DDK_FEATURE_NAMES = [f.name for f in DDK_FEATURE_DEFINITIONS]


def ddk_schema_document() -> dict[str, object]:
    """Return the canonical JSON document for voxneuro.task.ddk.v1."""
    return {
        "schema_version": DDK_SCHEMA_VERSION,
        "feature_order": DDK_FEATURE_NAMES,
        "features": [asdict(f) for f in DDK_FEATURE_DEFINITIONS],
    }


def ddk_schema_fingerprint() -> str:
    """Return the stable cryptographic SHA-256 fingerprint for DDK schema."""
    payload = json.dumps(ddk_schema_document(), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


# -----------------------------------------------------------------------------
# Connected Speech Schema: voxneuro.task.connected_speech.v1
# -----------------------------------------------------------------------------
CONNECTED_SPEECH_SCHEMA_VERSION = "voxneuro.task.connected_speech.v1"

CONNECTED_SPEECH_FEATURE_DEFINITIONS: list[TaskFeatureDefinition] = [
    TaskFeatureDefinition(
        "total_recording_duration_s",
        "s",
        "Total duration of speech recording analyzed",
        "Valid audio recording",
    ),
    TaskFeatureDefinition(
        "estimated_active_speech_duration_s",
        "s",
        "Cumulative duration of voiced/active speech frames",
        "At least 1 active speech frame",
    ),
    TaskFeatureDefinition(
        "estimated_silence_duration_s",
        "s",
        "Cumulative duration of pause and silent frames",
        "Valid audio recording",
    ),
    TaskFeatureDefinition(
        "pause_count",
        "count",
        "Number of acoustic pause intervals exceeding threshold duration (> 200 ms)",
        "At least 1 pause detected",
    ),
    TaskFeatureDefinition(
        "mean_pause_duration_s",
        "s",
        "Arithmetic mean duration of detected acoustic pauses",
        "At least 1 pause detected",
    ),
    TaskFeatureDefinition(
        "median_pause_duration_s",
        "s",
        "Median duration of detected acoustic pauses",
        "At least 1 pause detected",
    ),
    TaskFeatureDefinition(
        "max_pause_duration_s",
        "s",
        "Duration of the longest acoustic pause",
        "At least 1 pause detected",
    ),
    TaskFeatureDefinition(
        "pause_duration_sd_s",
        "s",
        "Sample standard deviation of acoustic pause durations",
        "At least 2 pauses detected",
    ),
    TaskFeatureDefinition(
        "pause_fraction",
        "ratio",
        "Ratio of silent pause duration to total recording duration",
        "Valid audio recording",
    ),
    TaskFeatureDefinition(
        "speech_activity_fraction",
        "ratio",
        "Ratio of active speech duration to total recording duration",
        "Valid audio recording",
    ),
    TaskFeatureDefinition(
        "speech_bout_count",
        "count",
        "Number of continuous speech segments between pauses",
        "At least 1 speech bout",
    ),
    TaskFeatureDefinition(
        "mean_speech_bout_duration_s",
        "s",
        "Mean duration of continuous speech bouts",
        "At least 1 speech bout",
    ),
    TaskFeatureDefinition(
        "median_speech_bout_duration_s",
        "s",
        "Median duration of continuous speech bouts",
        "At least 1 speech bout",
    ),
    TaskFeatureDefinition(
        "f0_median_hz",
        "Hz",
        "Median fundamental frequency across voiced speech frames",
        "At least 10 valid voiced frames",
    ),
    TaskFeatureDefinition(
        "f0_sd_hz",
        "Hz",
        "Sample standard deviation of fundamental frequency across voiced frames",
        "At least 10 valid voiced frames",
    ),
    TaskFeatureDefinition(
        "f0_q10_hz",
        "Hz",
        "10th percentile fundamental frequency across voiced frames",
        "At least 10 valid voiced frames",
    ),
    TaskFeatureDefinition(
        "f0_q90_hz",
        "Hz",
        "90th percentile fundamental frequency across voiced frames",
        "At least 10 valid voiced frames",
    ),
    TaskFeatureDefinition(
        "f0_range_semitones",
        "semitones",
        "Pitch excursion range in semitones: 12 * log2(F0_q90 / F0_q10)",
        "At least 10 valid voiced frames and F0_q10 > 0",
    ),
    TaskFeatureDefinition(
        "intensity_median_dbfs",
        "dBFS",
        "Median frame RMS level relative to full scale",
        "At least 1 valid frame",
    ),
    TaskFeatureDefinition(
        "intensity_iqr_db",
        "dB",
        "Interquartile range of frame intensity levels",
        "At least 10 valid frames",
    ),
]

CONNECTED_SPEECH_FEATURE_NAMES = [f.name for f in CONNECTED_SPEECH_FEATURE_DEFINITIONS]


def connected_speech_schema_document() -> dict[str, object]:
    """Return the canonical JSON document for voxneuro.task.connected_speech.v1."""
    return {
        "schema_version": CONNECTED_SPEECH_SCHEMA_VERSION,
        "feature_order": CONNECTED_SPEECH_FEATURE_NAMES,
        "features": [asdict(f) for f in CONNECTED_SPEECH_FEATURE_DEFINITIONS],
    }


def connected_speech_schema_fingerprint() -> str:
    """Return the stable cryptographic SHA-256 fingerprint for connected speech schema."""
    payload = json.dumps(
        connected_speech_schema_document(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# -----------------------------------------------------------------------------
# Vowel Space Schema: voxneuro.task.vowel_space.v1
# -----------------------------------------------------------------------------
VOWEL_SPACE_SCHEMA_VERSION = "voxneuro.task.vowel_space.v1"

VOWEL_SPACE_FEATURE_DEFINITIONS: list[TaskFeatureDefinition] = [
    TaskFeatureDefinition(
        "f1_a_median_hz",
        "Hz",
        "Median first formant (F1) frequency for sustained vowel /a/",
        "At least 10 valid formant frames in central stable region",
    ),
    TaskFeatureDefinition(
        "f2_a_median_hz",
        "Hz",
        "Median second formant (F2) frequency for sustained vowel /a/",
        "At least 10 valid formant frames in central stable region",
    ),
    TaskFeatureDefinition(
        "f1_a_sd_hz",
        "Hz",
        "Standard deviation of F1 for vowel /a/",
        "At least 10 valid formant frames",
    ),
    TaskFeatureDefinition(
        "f2_a_sd_hz",
        "Hz",
        "Standard deviation of F2 for vowel /a/",
        "At least 10 valid formant frames",
    ),
    TaskFeatureDefinition(
        "valid_frames_a_count",
        "count",
        "Number of valid formant frames extracted for vowel /a/",
        "Valid audio recording",
    ),
    TaskFeatureDefinition(
        "f1_i_median_hz",
        "Hz",
        "Median first formant (F1) frequency for sustained vowel /i/",
        "At least 10 valid formant frames in central stable region",
    ),
    TaskFeatureDefinition(
        "f2_i_median_hz",
        "Hz",
        "Median second formant (F2) frequency for sustained vowel /i/",
        "At least 10 valid formant frames in central stable region",
    ),
    TaskFeatureDefinition(
        "f1_i_sd_hz",
        "Hz",
        "Standard deviation of F1 for vowel /i/",
        "At least 10 valid formant frames",
    ),
    TaskFeatureDefinition(
        "f2_i_sd_hz",
        "Hz",
        "Standard deviation of F2 for vowel /i/",
        "At least 10 valid formant frames",
    ),
    TaskFeatureDefinition(
        "valid_frames_i_count",
        "count",
        "Number of valid formant frames extracted for vowel /i/",
        "Valid audio recording",
    ),
    TaskFeatureDefinition(
        "f1_u_median_hz",
        "Hz",
        "Median first formant (F1) frequency for sustained vowel /u/",
        "At least 10 valid formant frames in central stable region",
    ),
    TaskFeatureDefinition(
        "f2_u_median_hz",
        "Hz",
        "Median second formant (F2) frequency for sustained vowel /u/",
        "At least 10 valid formant frames in central stable region",
    ),
    TaskFeatureDefinition(
        "f1_u_sd_hz",
        "Hz",
        "Standard deviation of F1 for vowel /u/",
        "At least 10 valid formant frames",
    ),
    TaskFeatureDefinition(
        "f2_u_sd_hz",
        "Hz",
        "Standard deviation of F2 for vowel /u/",
        "At least 10 valid formant frames",
    ),
    TaskFeatureDefinition(
        "valid_frames_u_count",
        "count",
        "Number of valid formant frames extracted for vowel /u/",
        "Valid audio recording",
    ),
    TaskFeatureDefinition(
        "vowel_space_area_hz2",
        "Hz^2",
        "Geometric triangular area formed by (F1, F2) coordinates of /a/, /i/, and /u/: "
        "0.5 * |F1_a(F2_i - F2_u) + F1_i(F2_u - F2_a) + F1_u(F2_a - F2_i)|",
        "Valid median F1 and F2 formants for all three corner vowels (/a/, /i/, /u/)",
    ),
]

VOWEL_SPACE_FEATURE_NAMES = [f.name for f in VOWEL_SPACE_FEATURE_DEFINITIONS]


def vowel_space_schema_document() -> dict[str, object]:
    """Return the canonical JSON document for voxneuro.task.vowel_space.v1."""
    return {
        "schema_version": VOWEL_SPACE_SCHEMA_VERSION,
        "feature_order": VOWEL_SPACE_FEATURE_NAMES,
        "features": [asdict(f) for f in VOWEL_SPACE_FEATURE_DEFINITIONS],
    }


def vowel_space_schema_fingerprint() -> str:
    """Return the stable cryptographic SHA-256 fingerprint for vowel space schema."""
    payload = json.dumps(
        vowel_space_schema_document(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# -----------------------------------------------------------------------------
# Multi-Task Session Envelope: voxneuro.voice.v4
# -----------------------------------------------------------------------------
V4_SCHEMA_VERSION = "voxneuro.voice.v4"


def get_task_schema_registry() -> dict[str, dict[str, Any]]:
    """Return registry of all active task schema versions and their canonical fingerprints."""
    return {
        V3_SCHEMA_VERSION: {
            "name": "sustained_vowel",
            "schema_version": V3_SCHEMA_VERSION,
            "feature_count": len(V3_FEATURE_DEFINITIONS),
            "fingerprint": v3_schema_fingerprint(),
        },
        DDK_SCHEMA_VERSION: {
            "name": "diadochokinetic_speech",
            "schema_version": DDK_SCHEMA_VERSION,
            "feature_count": len(DDK_FEATURE_DEFINITIONS),
            "fingerprint": ddk_schema_fingerprint(),
        },
        CONNECTED_SPEECH_SCHEMA_VERSION: {
            "name": "connected_speech",
            "schema_version": CONNECTED_SPEECH_SCHEMA_VERSION,
            "feature_count": len(CONNECTED_SPEECH_FEATURE_DEFINITIONS),
            "fingerprint": connected_speech_schema_fingerprint(),
        },
        VOWEL_SPACE_SCHEMA_VERSION: {
            "name": "vowel_space_area",
            "schema_version": VOWEL_SPACE_SCHEMA_VERSION,
            "feature_count": len(VOWEL_SPACE_FEATURE_DEFINITIONS),
            "fingerprint": vowel_space_schema_fingerprint(),
        },
    }


def v4_envelope_schema_document() -> dict[str, object]:
    """Return the canonical specification for the voxneuro.voice.v4 multi-task session envelope."""
    registry = get_task_schema_registry()
    return {
        "schema_version": V4_SCHEMA_VERSION,
        "envelope_type": "multitask_session",
        "supported_tasks": ["sustained_vowel", "ddk", "connected_speech", "vowel_space"],
        "task_registry": {k: v["fingerprint"] for k, v in sorted(registry.items())},
        "description": "Multi-task session envelope containing independent task evaluation blocks",
    }


def v4_envelope_schema_fingerprint() -> str:
    """Return stable cryptographic SHA-256 fingerprint for v4 session envelope."""
    payload = json.dumps(
        v4_envelope_schema_document(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def generate_task_schema_registry_document() -> dict[str, Any]:
    """Generate the authoritative schema registry document consumed by evidence and audits."""
    registry = get_task_schema_registry()
    envelope_fp = v4_envelope_schema_fingerprint()
    return {
        "milestone": "M3",
        "envelope_schema_version": V4_SCHEMA_VERSION,
        "envelope_schema_fingerprint": envelope_fp,
        "schemas": [
            {
                "schema_name": "sustained_vowel",
                "schema_version": V3_SCHEMA_VERSION,
                "schema_fingerprint": registry[V3_SCHEMA_VERSION]["fingerprint"],
                "feature_count": registry[V3_SCHEMA_VERSION]["feature_count"],
                "description": (
                    "Canonical sustained vowel /a/ Core39 features for vocal fold vibration "
                    "and acoustic stability."
                ),
                "failure_isolation_policy": "independent",
                "is_legacy_canonical": True,
                "model_compatible": True,
            },
            {
                "schema_name": "ddk",
                "schema_version": DDK_SCHEMA_VERSION,
                "schema_fingerprint": registry[DDK_SCHEMA_VERSION]["fingerprint"],
                "feature_count": registry[DDK_SCHEMA_VERSION]["feature_count"],
                "description": (
                    "Diadochokinetic syllable repetition (AMR/SMR) event rate, regularity, "
                    "and rate drift features."
                ),
                "failure_isolation_policy": "independent",
                "is_legacy_canonical": False,
                "model_compatible": False,
            },
            {
                "schema_name": "connected_speech",
                "schema_version": CONNECTED_SPEECH_SCHEMA_VERSION,
                "schema_fingerprint": registry[CONNECTED_SPEECH_SCHEMA_VERSION]["fingerprint"],
                "feature_count": registry[CONNECTED_SPEECH_SCHEMA_VERSION]["feature_count"],
                "description": (
                    "Connected speech segmentation, pause architecture, prosodic f0 dynamics, "
                    "and intensity decay."
                ),
                "failure_isolation_policy": "independent",
                "is_legacy_canonical": False,
                "model_compatible": False,
            },
            {
                "schema_name": "vowel_space",
                "schema_version": VOWEL_SPACE_SCHEMA_VERSION,
                "schema_fingerprint": registry[VOWEL_SPACE_SCHEMA_VERSION]["fingerprint"],
                "feature_count": registry[VOWEL_SPACE_SCHEMA_VERSION]["feature_count"],
                "description": (
                    "Corner vowels (/a/, /i/, /u/) Burg LPC formant tracking and "
                    "triangular Vowel Space Area (VSA)."
                ),
                "failure_isolation_policy": "independent",
                "is_legacy_canonical": False,
                "model_compatible": False,
            },
            {
                "schema_name": "multi_task_envelope",
                "schema_version": V4_SCHEMA_VERSION,
                "schema_fingerprint": envelope_fp,
                "feature_count": "variable_by_active_tasks",
                "description": (
                    "Hierarchical multi-task session envelope packaging independent task outputs "
                    "with failure isolation."
                ),
                "failure_isolation_policy": "hierarchical_aggregation",
                "is_legacy_canonical": False,
                "model_compatible": False,
            },
        ],
    }
