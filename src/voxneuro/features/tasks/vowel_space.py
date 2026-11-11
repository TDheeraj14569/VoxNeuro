"""Multi-vowel formant extraction and Vowel Space Area (VSA) calculation.

Implements Burg LPC formant estimation for corner vowels (/a/, /i/, /u/),
central stable segment selection, repeated-trial aggregation, and geometric
triangular Vowel Space Area computation in Hz^2.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import parselmouth

from voxneuro.audio.task_preprocessing import TaskPreprocessingResult
from voxneuro.features.schema import configuration_fingerprint
from voxneuro.features.tasks.schema import (
    VOWEL_SPACE_FEATURE_NAMES,
    VOWEL_SPACE_SCHEMA_VERSION,
    vowel_space_schema_fingerprint,
)


@dataclass(frozen=True)
class VowelFormantConfig:
    """Configurable parameters for Burg LPC formant analysis."""

    time_step_s: float = 0.01
    max_formants: int = 5
    max_formant_hz: float = 5000.0  # Standard adult reference ceiling
    window_length_s: float = 0.025
    pre_emphasis_from_hz: float = 50.0
    stable_window_start_fraction: float = 0.25  # Middle 50% start
    stable_window_end_fraction: float = 0.75  # Middle 50% end
    min_valid_frames: int = 10
    f1_min_hz: float = 180.0
    f1_max_hz: float = 1300.0
    f2_min_hz: float = 450.0
    f2_max_hz: float = 3200.0


@dataclass
class SingleVowelFormantResult:
    """Formant estimation results for an individual vowel trial."""

    vowel_label: str  # "a", "i", "u"
    f1_median_hz: float | None
    f2_median_hz: float | None
    f1_sd_hz: float | None
    f2_sd_hz: float | None
    valid_frames_count: int
    total_frames_count: int
    valid_fraction: float
    f1_track_hz: list[float]
    f2_track_hz: list[float]
    is_valid: bool
    warnings: list[str]


@dataclass
class VowelSpaceResult:
    """Complete multi-vowel formant analysis and geometric VSA outcome."""

    task_id: str
    task_type: str
    task_schema_version: str
    task_schema_fingerprint: str
    task_status: str
    vsa_estimable: bool
    features: dict[str, float | None]
    per_vowel_results: dict[str, SingleVowelFormantResult]
    quality: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    configuration_fingerprint: str = ""
    preprocessing_status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        """Return standardized JSON-serializable task dictionary."""
        d = asdict(self)
        d.pop("per_vowel_results", None)
        return d


def extract_vowel_formants(
    samples: np.ndarray,
    sample_rate: int,
    vowel_label: str = "a",
    config: VowelFormantConfig | None = None,
) -> SingleVowelFormantResult:
    """Extract F1 and F2 formant tracks from the central stable region of a sustained vowel."""
    cfg = config or VowelFormantConfig()
    warnings: list[str] = []
    vowel_norm = vowel_label.strip().lower()

    x = np.asarray(samples, dtype=np.float64)
    duration_s = float(len(x) / sample_rate) if sample_rate > 0 else 0.0

    if duration_s < 0.20 or len(x) < int(sample_rate * 0.20):
        return SingleVowelFormantResult(
            vowel_label=vowel_norm,
            f1_median_hz=None,
            f2_median_hz=None,
            f1_sd_hz=None,
            f2_sd_hz=None,
            valid_frames_count=0,
            total_frames_count=0,
            valid_fraction=0.0,
            f1_track_hz=[],
            f2_track_hz=[],
            is_valid=False,
            warnings=["Vowel audio duration is too brief (< 200 ms) for formant tracking."],
        )

    try:
        sound = parselmouth.Sound(x, sampling_frequency=sample_rate)
        formant = sound.to_formant_burg(
            time_step=cfg.time_step_s,
            max_number_of_formants=cfg.max_formants,
            maximum_formant=cfg.max_formant_hz,
            window_length=cfg.window_length_s,
            pre_emphasis_from=cfg.pre_emphasis_from_hz,
        )

        # Restrict analysis to stable central segment
        t_start = duration_s * cfg.stable_window_start_fraction
        t_end = duration_s * cfg.stable_window_end_fraction
        sample_times = np.arange(t_start, t_end, cfg.time_step_s)

        f1_list: list[float] = []
        f2_list: list[float] = []

        for t in sample_times:
            val_f1 = formant.get_value_at_time(1, t)
            val_f2 = formant.get_value_at_time(2, t)

            if (
                val_f1 is not None
                and not math.isnan(val_f1)
                and val_f2 is not None
                and not math.isnan(val_f2)
                and (cfg.f1_min_hz <= val_f1 <= cfg.f1_max_hz)
                and (cfg.f2_min_hz <= val_f2 <= cfg.f2_max_hz)
                and (val_f2 > val_f1)
            ):
                f1_list.append(float(val_f1))
                f2_list.append(float(val_f2))

        n_valid = len(f1_list)
        n_total = len(sample_times)
        valid_frac = float(n_valid / n_total) if n_total > 0 else 0.0

        if n_valid >= cfg.min_valid_frames:
            f1_med = float(np.median(f1_list))
            f2_med = float(np.median(f2_list))
            f1_sd = float(np.std(f1_list, ddof=1)) if n_valid >= 2 else 0.0
            f2_sd = float(np.std(f2_list, ddof=1)) if n_valid >= 2 else 0.0
            is_valid = True
        else:
            f1_med = None
            f2_med = None
            f1_sd = None
            f2_sd = None
            is_valid = False
            warnings.append(
                f"Fewer than {cfg.min_valid_frames} valid formant frames ({n_valid}) extracted "
                f"for vowel /{vowel_norm}/ in central window."
            )

        return SingleVowelFormantResult(
            vowel_label=vowel_norm,
            f1_median_hz=round(f1_med, 2) if f1_med is not None else None,
            f2_median_hz=round(f2_med, 2) if f2_med is not None else None,
            f1_sd_hz=round(f1_sd, 2) if f1_sd is not None else None,
            f2_sd_hz=round(f2_sd, 2) if f2_sd is not None else None,
            valid_frames_count=n_valid,
            total_frames_count=n_total,
            valid_fraction=round(valid_frac, 4),
            f1_track_hz=[round(v, 2) for v in f1_list],
            f2_track_hz=[round(v, 2) for v in f2_list],
            is_valid=is_valid,
            warnings=warnings,
        )
    except Exception as exc:
        return SingleVowelFormantResult(
            vowel_label=vowel_norm,
            f1_median_hz=None,
            f2_median_hz=None,
            f1_sd_hz=None,
            f2_sd_hz=None,
            valid_frames_count=0,
            total_frames_count=0,
            valid_fraction=0.0,
            f1_track_hz=[],
            f2_track_hz=[],
            is_valid=False,
            warnings=[f"Formant extraction error for /{vowel_norm}/: {exc}"],
        )


def calculate_vsa_triangle(
    f1_a: float | None,
    f2_a: float | None,
    f1_i: float | None,
    f2_i: float | None,
    f1_u: float | None,
    f2_u: float | None,
) -> float | None:
    """Calculate geometric Vowel Space Area (VSA) using shoelace triangle formula.

    Formula:
        VSA = 0.5 * abs(F1_a * (F2_i - F2_u) + F1_i * (F2_u - F2_a) + F1_u * (F2_a - F2_i))
    Units: Hz^2

    Returns None if any coordinate is missing or non-finite.
    """
    coords = (f1_a, f2_a, f1_i, f2_i, f1_u, f2_u)
    if any(c is None or not math.isfinite(c) for c in coords):
        return None

    # Cast safe floats
    a1, a2 = float(f1_a), float(f2_a)
    i1, i2 = float(f1_i), float(f2_i)
    u1, u2 = float(f1_u), float(f2_u)

    area = 0.5 * abs(a1 * (i2 - u2) + i1 * (u2 - a2) + u1 * (a2 - i2))
    return float(area)


def extract_vowel_space_features(
    vowel_recordings: dict[str, TaskPreprocessingResult | list[TaskPreprocessingResult]],
    task_id: str = "vowel_space_group",
    config: VowelFormantConfig | None = None,
) -> VowelSpaceResult:
    """Extract formants for /a/, /i/, /u/ and calculate geometric Vowel Space Area.

    Supports repeated trials per vowel with median aggregation across valid trials.
    """
    cfg = config or VowelFormantConfig()
    warnings: list[str] = []
    errors: list[str] = []

    features: dict[str, float | None] = {name: None for name in VOWEL_SPACE_FEATURE_NAMES}
    per_vowel: dict[str, SingleVowelFormantResult] = {}

    target_vowels = ("a", "i", "u")

    for v in target_vowels:
        prep_inputs = vowel_recordings.get(v)
        if prep_inputs is None:
            warnings.append(f"Corner vowel /{v}/ was not provided in session input.")
            continue

        trial_list = prep_inputs if isinstance(prep_inputs, list) else [prep_inputs]
        trial_results: list[SingleVowelFormantResult] = []

        for trial in trial_list:
            res = extract_vowel_formants(
                trial.samples, trial.sample_rate, vowel_label=v, config=cfg
            )
            trial_results.append(res)
            if res.warnings:
                warnings.extend([f"/{v}/ trial: {w}" for w in res.warnings])

        valid_trials = [t for t in trial_results if t.is_valid and t.f1_median_hz is not None]

        if valid_trials:
            # Aggregate across valid trials via median
            agg_f1 = float(np.median([t.f1_median_hz for t in valid_trials]))
            agg_f2 = float(np.median([t.f2_median_hz for t in valid_trials]))
            agg_f1_sd = float(np.mean([t.f1_sd_hz for t in valid_trials if t.f1_sd_hz is not None]))
            agg_f2_sd = float(np.mean([t.f2_sd_hz for t in valid_trials if t.f2_sd_hz is not None]))
            total_frames = sum(t.valid_frames_count for t in valid_trials)

            per_vowel[v] = SingleVowelFormantResult(
                vowel_label=v,
                f1_median_hz=round(agg_f1, 2),
                f2_median_hz=round(agg_f2, 2),
                f1_sd_hz=round(agg_f1_sd, 2),
                f2_sd_hz=round(agg_f2_sd, 2),
                valid_frames_count=total_frames,
                total_frames_count=sum(t.total_frames_count for t in valid_trials),
                valid_fraction=round(float(np.mean([t.valid_fraction for t in valid_trials])), 4),
                f1_track_hz=[],
                f2_track_hz=[],
                is_valid=True,
                warnings=[],
            )

            features[f"f1_{v}_median_hz"] = round(agg_f1, 2)
            features[f"f2_{v}_median_hz"] = round(agg_f2, 2)
            features[f"f1_{v}_sd_hz"] = round(agg_f1_sd, 2)
            features[f"f2_{v}_sd_hz"] = round(agg_f2_sd, 2)
            features[f"valid_frames_{v}_count"] = float(total_frames)
        else:
            warnings.append(f"No valid formant estimates obtained for vowel /{v}/.")

    # Calculate VSA
    f1_a = features.get("f1_a_median_hz")
    f2_a = features.get("f2_a_median_hz")
    f1_i = features.get("f1_i_median_hz")
    f2_i = features.get("f2_i_median_hz")
    f1_u = features.get("f1_u_median_hz")
    f2_u = features.get("f2_u_median_hz")

    vsa_val = calculate_vsa_triangle(f1_a, f2_a, f1_i, f2_i, f1_u, f2_u)

    if vsa_val is not None:
        features["vowel_space_area_hz2"] = round(vsa_val, 2)
        task_status = "complete"
        vsa_estimable = True
    else:
        features["vowel_space_area_hz2"] = None
        vsa_estimable = False
        missing_vowels = [v for v in target_vowels if features.get(f"f1_{v}_median_hz") is None]
        task_status = "not_estimable"
        errors.append(
            f"Vowel Space Area is NOT ESTIMABLE: Missing valid formant estimates for "
            f"corner vowels: {missing_vowels}."
        )

    return VowelSpaceResult(
        task_id=task_id,
        task_type="vowel_space",
        task_schema_version=VOWEL_SPACE_SCHEMA_VERSION,
        task_schema_fingerprint=vowel_space_schema_fingerprint(),
        task_status=task_status,
        vsa_estimable=vsa_estimable,
        features=features,
        per_vowel_results=per_vowel,
        quality={
            "vowels_provided": list(vowel_recordings.keys()),
            "valid_vowels": list(per_vowel.keys()),
            "vsa_estimable": vsa_estimable,
        },
        warnings=warnings,
        errors=errors,
        configuration_fingerprint=configuration_fingerprint(asdict(cfg)),
        preprocessing_status="completed",
    )
