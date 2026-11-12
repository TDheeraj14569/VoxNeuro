"""Unified multi-task session orchestration for VoxNeuro Milestone 3.

Coordinates independent speech tasks (sustained vowel, DDK, connected speech,
and vowel space area), builds the voxneuro.voice.v4 envelope, and ensures failure
isolation across tasks.
"""

from __future__ import annotations

import json
import platform
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from voxneuro.audio.io import AudioRecord, decode_audio
from voxneuro.audio.preprocessing import preprocess_audio
from voxneuro.audio.task_preprocessing import preprocess_task_audio
from voxneuro.audio.validation import validate_audio
from voxneuro.exceptions import AudioValidationError
from voxneuro.features.extractor import extract_features
from voxneuro.features.schema import (
    FEATURE_NAMES as V3_FEATURE_NAMES,
)
from voxneuro.features.schema import (
    SCHEMA_VERSION as V3_SCHEMA_VERSION,
)
from voxneuro.features.schema import (
    configuration_fingerprint,
)
from voxneuro.features.schema import (
    schema_fingerprint as v3_schema_fingerprint,
)
from voxneuro.features.tasks.connected_speech import (
    STANDARD_PASSAGE_ID,
    ConnectedSpeechConfig,
    ConnectedSpeechResult,
    extract_connected_speech_features,
)
from voxneuro.features.tasks.ddk import (
    DDKConfig,
    DDKResult,
    extract_ddk_features,
)
from voxneuro.features.tasks.schema import (
    CONNECTED_SPEECH_FEATURE_NAMES,
    CONNECTED_SPEECH_SCHEMA_VERSION,
    DDK_FEATURE_NAMES,
    DDK_SCHEMA_VERSION,
    V4_SCHEMA_VERSION,
    VOWEL_SPACE_FEATURE_NAMES,
    VOWEL_SPACE_SCHEMA_VERSION,
    connected_speech_schema_fingerprint,
    ddk_schema_fingerprint,
    get_task_schema_registry,
    v4_envelope_schema_fingerprint,
    vowel_space_schema_fingerprint,
)
from voxneuro.features.tasks.vowel_space import (
    VowelFormantConfig,
    VowelSpaceResult,
    extract_vowel_space_features,
)
from voxneuro.provenance import project_code_fingerprint


@dataclass
class MultiTaskSessionResult:
    """Session container adhering to the voxneuro.voice.v4 specification."""

    schema_version: str
    schema_fingerprint: str
    session_id: str
    created_utc: str
    overall_processing_status: str
    tasks: dict[str, dict[str, Any]]
    task_registry: dict[str, Any]
    processing_metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return standardized JSON-serializable multi-task dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize session envelope to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, allow_nan=False)


def _coerce_audio_record(audio_input: AudioRecord | Path | str | bytes) -> AudioRecord:
    """Coerce various audio representations to AudioRecord."""
    if isinstance(audio_input, AudioRecord):
        return audio_input
    if isinstance(audio_input, (str, Path)):
        p = Path(audio_input)
        return decode_audio(p.read_bytes())
    if isinstance(audio_input, (bytes, bytearray)):
        return decode_audio(bytes(audio_input))
    raise TypeError(f"Unsupported audio input type: {type(audio_input).__name__}")


def analyze_multitask_session(
    sustained_vowel: AudioRecord | Path | str | bytes | None = None,
    ddk_recordings: dict[str, AudioRecord | Path | str | bytes] | None = None,
    connected_speech: AudioRecord | Path | str | bytes | None = None,
    vowel_space_recordings: dict[
        str,
        AudioRecord | Path | str | bytes | list[AudioRecord | Path | str | bytes],
    ]
    | None = None,
    session_id: str | None = None,
    ddk_config: DDKConfig | None = None,
    connected_speech_config: ConnectedSpeechConfig | None = None,
    vowel_space_config: VowelFormantConfig | None = None,
) -> MultiTaskSessionResult:
    """Orchestrate multi-task evaluation session, isolating errors across tasks."""
    sess_id = session_id or str(uuid.uuid4())
    created_utc = datetime.now(UTC).isoformat()
    tasks: dict[str, dict[str, Any]] = {}
    task_statuses: list[str] = []

    # -------------------------------------------------------------------------
    # 1. Sustained Vowel Task (voxneuro.voice.v3 preservation)
    # -------------------------------------------------------------------------
    v3_cfg_fp = configuration_fingerprint({"schema": V3_SCHEMA_VERSION})
    if sustained_vowel is not None:
        task_id = "sustained_vowel_a"
        rec = None
        try:
            rec = _coerce_audio_record(sustained_vowel)
            val_quality = validate_audio(rec)

            if not val_quality.valid:
                tasks[task_id] = {
                    "task_id": task_id,
                    "task_type": "sustained_vowel",
                    "task_schema_version": V3_SCHEMA_VERSION,
                    "task_schema_fingerprint": v3_schema_fingerprint(),
                    "task_status": "quality_failed",
                    "features": {name: None for name in V3_FEATURE_NAMES},
                    "quality": {
                        "valid": False,
                        "duration_seconds": val_quality.duration_seconds,
                        "clipping_fraction": val_quality.clipping_fraction,
                        "rms_amplitude": val_quality.rms_amplitude,
                    },
                    "configuration_fingerprint": v3_cfg_fp,
                    "preprocessing_status": "not_run",
                    "preprocessing_fingerprint": "not_run",
                    "source_audio_metadata": {
                        "sample_rate": rec.sample_rate,
                        "channels": rec.channels,
                        "duration_seconds": rec.duration_seconds,
                    },
                    "warnings": val_quality.warnings,
                    "errors": val_quality.errors or ["Audio validation failed"],
                }
                task_statuses.append("quality_failed")
            else:
                prep = preprocess_audio(rec)
                feat_raw = extract_features(prep.samples, prep.sample_rate)
                feat_dict = {name: feat_raw.get(name) for name in V3_FEATURE_NAMES}

                tasks[task_id] = {
                    "task_id": task_id,
                    "task_type": "sustained_vowel",
                    "task_schema_version": V3_SCHEMA_VERSION,
                    "task_schema_fingerprint": v3_schema_fingerprint(),
                    "task_status": "complete",
                    "features": feat_dict,
                    "quality": {
                        "valid": True,
                        "duration_seconds": val_quality.duration_seconds,
                        "clipping_fraction": val_quality.clipping_fraction,
                        "rms_amplitude": val_quality.rms_amplitude,
                    },
                    "configuration_fingerprint": v3_cfg_fp,
                    "preprocessing_status": "completed",
                    "preprocessing_fingerprint": getattr(
                        prep, "preprocessing_fingerprint", "legacy_v3_preprocessed"
                    ),
                    "source_audio_metadata": {
                        "sample_rate": rec.sample_rate,
                        "channels": rec.channels,
                        "duration_seconds": rec.duration_seconds,
                    },
                    "warnings": val_quality.warnings,
                    "errors": [],
                }
                task_statuses.append("complete")
        except AudioValidationError as ave:
            meta = (
                {
                    "sample_rate": rec.sample_rate,
                    "channels": rec.channels,
                    "duration_seconds": rec.duration_seconds,
                }
                if isinstance(rec, AudioRecord)
                else {}
            )
            tasks[task_id] = {
                "task_id": task_id,
                "task_type": "sustained_vowel",
                "task_schema_version": V3_SCHEMA_VERSION,
                "task_schema_fingerprint": v3_schema_fingerprint(),
                "task_status": "quality_failed",
                "features": {name: None for name in V3_FEATURE_NAMES},
                "quality": {"valid": False},
                "configuration_fingerprint": v3_cfg_fp,
                "preprocessing_status": "not_run",
                "preprocessing_fingerprint": "not_run",
                "source_audio_metadata": meta,
                "warnings": [],
                "errors": [f"{ave.__class__.__name__}: {ave}"],
            }
            task_statuses.append("quality_failed")
        except Exception as exc:
            meta = (
                {
                    "sample_rate": rec.sample_rate,
                    "channels": rec.channels,
                    "duration_seconds": rec.duration_seconds,
                }
                if isinstance(rec, AudioRecord)
                else {}
            )
            tasks[task_id] = {
                "task_id": task_id,
                "task_type": "sustained_vowel",
                "task_schema_version": V3_SCHEMA_VERSION,
                "task_schema_fingerprint": v3_schema_fingerprint(),
                "task_status": "processing_failed",
                "features": {name: None for name in V3_FEATURE_NAMES},
                "quality": {"valid": False},
                "configuration_fingerprint": v3_cfg_fp,
                "preprocessing_status": "not_run",
                "preprocessing_fingerprint": "not_run",
                "source_audio_metadata": meta,
                "warnings": [],
                "errors": [f"{exc.__class__.__name__}: {exc}"],
            }
            task_statuses.append("processing_failed")

    # -------------------------------------------------------------------------
    # 2. Diadochokinetic (DDK) Speech Tasks (voxneuro.task.ddk.v1)
    # -------------------------------------------------------------------------
    ddk_cfg = ddk_config or DDKConfig()
    ddk_cfg_fp = configuration_fingerprint(asdict(ddk_cfg))
    if ddk_recordings:
        for stim_key, audio_item in ddk_recordings.items():
            try:
                stim_norm = str(stim_key).strip().lower()
                t_id = f"ddk_{stim_norm}"
                rec = None
                rec = _coerce_audio_record(audio_item)
                prep_ddk = preprocess_task_audio(rec, task_type="ddk")
                ddk_res: DDKResult = extract_ddk_features(
                    prep_ddk,
                    task_id=t_id,
                    stimulus=stim_norm.upper(),
                    config=ddk_cfg,
                )
                tasks[t_id] = ddk_res.to_dict()
                task_statuses.append(ddk_res.task_status)
            except AudioValidationError as ave:
                stim_norm = str(stim_key).strip().lower()
                t_id = f"ddk_{stim_norm}"
                meta = (
                    {
                        "sample_rate": rec.sample_rate,
                        "channels": rec.channels,
                        "duration_seconds": rec.duration_seconds,
                    }
                    if isinstance(rec, AudioRecord)
                    else {}
                )
                tasks[t_id] = {
                    "task_id": t_id,
                    "task_type": "ddk",
                    "task_schema_version": DDK_SCHEMA_VERSION,
                    "task_schema_fingerprint": ddk_schema_fingerprint(),
                    "task_status": "quality_failed",
                    "stimulus": stim_norm.upper(),
                    "features": {name: None for name in DDK_FEATURE_NAMES},
                    "quality": {"valid": False},
                    "configuration_fingerprint": ddk_cfg_fp,
                    "preprocessing_status": "not_run",
                    "preprocessing_fingerprint": "not_run",
                    "source_audio_metadata": meta,
                    "warnings": [],
                    "errors": [f"{ave.__class__.__name__}: {ave}"],
                }
                task_statuses.append("quality_failed")
            except Exception as exc:
                stim_norm = str(stim_key).strip().lower()
                t_id = f"ddk_{stim_norm}"
                meta = (
                    {
                        "sample_rate": rec.sample_rate,
                        "channels": rec.channels,
                        "duration_seconds": rec.duration_seconds,
                    }
                    if isinstance(rec, AudioRecord)
                    else {}
                )
                tasks[t_id] = {
                    "task_id": t_id,
                    "task_type": "ddk",
                    "task_schema_version": DDK_SCHEMA_VERSION,
                    "task_schema_fingerprint": ddk_schema_fingerprint(),
                    "task_status": "processing_failed",
                    "stimulus": stim_norm.upper(),
                    "features": {name: None for name in DDK_FEATURE_NAMES},
                    "quality": {"valid": False},
                    "configuration_fingerprint": ddk_cfg_fp,
                    "preprocessing_status": "not_run",
                    "preprocessing_fingerprint": "not_run",
                    "source_audio_metadata": meta,
                    "warnings": [],
                    "errors": [f"{exc.__class__.__name__}: {exc}"],
                }
                task_statuses.append("processing_failed")

    # -------------------------------------------------------------------------
    # 3. Connected Speech Task (voxneuro.task.connected_speech.v1)
    # -------------------------------------------------------------------------
    cs_cfg = connected_speech_config or ConnectedSpeechConfig()
    cs_cfg_fp = configuration_fingerprint(asdict(cs_cfg))
    if connected_speech is not None:
        t_id = "connected_speech_passage"
        rec_cs = None
        try:
            rec_cs = _coerce_audio_record(connected_speech)
            prep_cs = preprocess_task_audio(rec_cs, task_type="connected_speech")
            cs_res: ConnectedSpeechResult = extract_connected_speech_features(
                prep_cs,
                task_id=t_id,
                config=cs_cfg,
            )
            tasks[t_id] = cs_res.to_dict()
            task_statuses.append(cs_res.task_status)
        except AudioValidationError as ave:
            meta = (
                {
                    "sample_rate": rec_cs.sample_rate,
                    "channels": rec_cs.channels,
                    "duration_seconds": rec_cs.duration_seconds,
                }
                if isinstance(rec_cs, AudioRecord)
                else {}
            )
            tasks[t_id] = {
                "task_id": t_id,
                "task_type": "connected_speech",
                "task_schema_version": CONNECTED_SPEECH_SCHEMA_VERSION,
                "task_schema_fingerprint": connected_speech_schema_fingerprint(),
                "task_status": "quality_failed",
                "stimulus_id": STANDARD_PASSAGE_ID,
                "language_code": "en",
                "features": {name: None for name in CONNECTED_SPEECH_FEATURE_NAMES},
                "quality": {"valid": False},
                "configuration_fingerprint": cs_cfg_fp,
                "preprocessing_status": "not_run",
                "preprocessing_fingerprint": "not_run",
                "source_audio_metadata": meta,
                "warnings": [],
                "errors": [f"{ave.__class__.__name__}: {ave}"],
            }
            task_statuses.append("quality_failed")
        except Exception as exc:
            meta = (
                {
                    "sample_rate": rec_cs.sample_rate,
                    "channels": rec_cs.channels,
                    "duration_seconds": rec_cs.duration_seconds,
                }
                if isinstance(rec_cs, AudioRecord)
                else {}
            )
            tasks[t_id] = {
                "task_id": t_id,
                "task_type": "connected_speech",
                "task_schema_version": CONNECTED_SPEECH_SCHEMA_VERSION,
                "task_schema_fingerprint": connected_speech_schema_fingerprint(),
                "task_status": "processing_failed",
                "stimulus_id": STANDARD_PASSAGE_ID,
                "language_code": "en",
                "features": {name: None for name in CONNECTED_SPEECH_FEATURE_NAMES},
                "quality": {"valid": False},
                "configuration_fingerprint": cs_cfg_fp,
                "preprocessing_status": "not_run",
                "preprocessing_fingerprint": "not_run",
                "source_audio_metadata": meta,
                "warnings": [],
                "errors": [f"{exc.__class__.__name__}: {exc}"],
            }
            task_statuses.append("processing_failed")

    # -------------------------------------------------------------------------
    # 4. Multi-Vowel Formants & VSA Task (voxneuro.task.vowel_space.v1)
    # -------------------------------------------------------------------------
    vs_cfg = vowel_space_config or VowelFormantConfig()
    vs_cfg_fp = configuration_fingerprint(asdict(vs_cfg))
    if vowel_space_recordings:
        t_id = "vowel_space_group"
        try:
            prep_vowels: dict[str, Any] = {}
            for v_key, v_input in vowel_space_recordings.items():
                v_norm = v_key.strip().lower()
                items = v_input if isinstance(v_input, list) else [v_input]
                prep_list = []
                for it in items:
                    r_v = _coerce_audio_record(it)
                    p_v = preprocess_task_audio(r_v, task_type="vowel_space")
                    prep_list.append(p_v)
                prep_vowels[v_norm] = prep_list

            vs_res: VowelSpaceResult = extract_vowel_space_features(
                prep_vowels,
                task_id=t_id,
                config=vs_cfg,
            )
            tasks[t_id] = vs_res.to_dict()
            task_statuses.append(vs_res.task_status)
        except AudioValidationError as ave:
            tasks[t_id] = {
                "task_id": t_id,
                "task_type": "vowel_space",
                "task_schema_version": VOWEL_SPACE_SCHEMA_VERSION,
                "task_schema_fingerprint": vowel_space_schema_fingerprint(),
                "task_status": "quality_failed",
                "vsa_estimable": False,
                "features": {name: None for name in VOWEL_SPACE_FEATURE_NAMES},
                "quality": {
                    "valid": False,
                    "vsa_estimable": False,
                    "vowels_provided": list(vowel_space_recordings.keys()),
                },
                "configuration_fingerprint": vs_cfg_fp,
                "preprocessing_status": "not_run",
                "preprocessing_fingerprint": "not_run",
                "source_audio_metadata": {},
                "warnings": [],
                "errors": [f"{ave.__class__.__name__}: {ave}"],
            }
            task_statuses.append("quality_failed")
        except Exception as exc:
            tasks[t_id] = {
                "task_id": t_id,
                "task_type": "vowel_space",
                "task_schema_version": VOWEL_SPACE_SCHEMA_VERSION,
                "task_schema_fingerprint": vowel_space_schema_fingerprint(),
                "task_status": "processing_failed",
                "vsa_estimable": False,
                "features": {name: None for name in VOWEL_SPACE_FEATURE_NAMES},
                "quality": {
                    "valid": False,
                    "vsa_estimable": False,
                    "vowels_provided": list(vowel_space_recordings.keys()),
                },
                "configuration_fingerprint": vs_cfg_fp,
                "preprocessing_status": "not_run",
                "preprocessing_fingerprint": "not_run",
                "source_audio_metadata": {},
                "warnings": [],
                "errors": [f"{exc.__class__.__name__}: {exc}"],
            }
            task_statuses.append("processing_failed")

    # -------------------------------------------------------------------------
    # Overall Status Aggregation
    # -------------------------------------------------------------------------
    if not task_statuses:
        overall_status = "pending"
    elif all(s == "complete" for s in task_statuses):
        overall_status = "complete"
    elif any(s == "complete" for s in task_statuses):
        overall_status = "partial"
    elif any(s == "quality_failed" for s in task_statuses):
        overall_status = "quality_failed"
    elif any(s == "insufficient_signal" for s in task_statuses):
        overall_status = "insufficient_signal"
    elif any(s == "not_estimable" for s in task_statuses):
        overall_status = "not_estimable"
    else:
        overall_status = "processing_failed"

    try:
        pipeline_fp = project_code_fingerprint()
    except Exception:
        pipeline_fp = "runtime_environment"

    metadata = {
        "pipeline_code_fingerprint": pipeline_fp,
        "environment": {
            "python_version": platform.python_version(),
            "platform": sys.platform,
        },
    }

    return MultiTaskSessionResult(
        schema_version=V4_SCHEMA_VERSION,
        schema_fingerprint=v4_envelope_schema_fingerprint(),
        session_id=sess_id,
        created_utc=created_utc,
        overall_processing_status=overall_status,
        tasks=tasks,
        task_registry=get_task_schema_registry(),
        processing_metadata=metadata,
    )
