"""Automated tests for multi-task failure metadata, schema preservation, and task isolation."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from tests.fixtures.synthetic_audio import sustained_vowel
from tests.fixtures.synthetic_connected_speech import synthetic_connected_speech
from tests.fixtures.synthetic_ddk_audio import synthetic_ddk_train
from tests.fixtures.synthetic_vowels import synthetic_formant_vowel
from voxneuro.audio.io import AudioRecord
from voxneuro.features.tasks.pipeline import (
    analyze_multitask_session,
)
from voxneuro.features.tasks.schema import (
    CONNECTED_SPEECH_SCHEMA_VERSION,
    DDK_SCHEMA_VERSION,
    VOWEL_SPACE_SCHEMA_VERSION,
    connected_speech_schema_fingerprint,
    ddk_schema_fingerprint,
    v4_envelope_schema_fingerprint,
    vowel_space_schema_fingerprint,
)


def _valid_sustained() -> AudioRecord:
    samples = sustained_vowel(duration=3.0, sample_rate=16000)[:, np.newaxis]
    return AudioRecord(
        samples=samples, sample_rate=16000, channels=1, subtype="PCM_16", format="WAV"
    )


def _valid_ddk() -> AudioRecord:
    samples = synthetic_ddk_train(duration=4.0, sample_rate=16000, target_rate_hz=5.0)
    return AudioRecord(
        samples=samples, sample_rate=16000, channels=1, subtype="PCM_16", format="WAV"
    )


def _valid_cs() -> AudioRecord:
    samples = synthetic_connected_speech(sample_rate=16000)
    return AudioRecord(
        samples=samples, sample_rate=16000, channels=1, subtype="PCM_16", format="WAV"
    )


def _valid_vowels() -> dict[str, AudioRecord]:
    return {
        v: AudioRecord(
            samples=synthetic_formant_vowel(v, duration=2.0, sample_rate=16000),
            sample_rate=16000,
            channels=1,
            subtype="PCM_16",
            format="WAV",
        )
        for v in ("a", "i", "u")
    }


def _invalid_audio_clipped() -> AudioRecord:
    """Severely clipped audio that fails audio validation."""
    samples = np.ones(16000 * 3, dtype=np.float64) * 0.999
    return AudioRecord(
        samples=samples, sample_rate=16000, channels=1, subtype="PCM_16", format="WAV"
    )


def _invalid_audio_short() -> AudioRecord:
    """Too short audio (< 0.2s) that fails duration checks."""
    samples = np.zeros(100, dtype=np.float64)
    return AudioRecord(
        samples=samples, sample_rate=16000, channels=1, subtype="PCM_16", format="WAV"
    )


class TestMultiTaskFailureMetadata:
    """Test task failure metadata, schema retention, and isolation across speech tasks."""

    def test_invalid_ddk_recording_retains_schema_identity(self) -> None:
        """1. Invalid DDK recording must retain correct schema identity and explicit status."""
        session = analyze_multitask_session(ddk_recordings={"pa": _invalid_audio_clipped()})
        assert "ddk_pa" in session.tasks
        ddk_task = session.tasks["ddk_pa"]
        assert ddk_task["task_status"] == "quality_failed"
        assert ddk_task["task_schema_version"] == DDK_SCHEMA_VERSION
        assert ddk_task["task_schema_fingerprint"] == ddk_schema_fingerprint()
        assert ddk_task["preprocessing_status"] == "not_run"
        assert ddk_task["configuration_fingerprint"] != ""
        assert len(ddk_task["errors"]) > 0

    def test_invalid_connected_speech_recording_retains_schema_identity(self) -> None:
        """2. Invalid connected speech recording must retain schema identity and explicit status."""
        session = analyze_multitask_session(connected_speech=_invalid_audio_short())
        assert "connected_speech_passage" in session.tasks
        cs_task = session.tasks["connected_speech_passage"]
        assert cs_task["task_status"] == "quality_failed"
        assert cs_task["task_schema_version"] == CONNECTED_SPEECH_SCHEMA_VERSION
        assert cs_task["task_schema_fingerprint"] == connected_speech_schema_fingerprint()
        assert cs_task["preprocessing_status"] == "not_run"
        assert cs_task["configuration_fingerprint"] != ""
        assert len(cs_task["errors"]) > 0

    def test_missing_corner_vowel_a_marks_vsa_not_estimable(self) -> None:
        """3. Missing corner vowel /a/ must mark VSA as not estimable with correct fingerprint."""
        vowels = _valid_vowels()
        vowels.pop("a")
        session = analyze_multitask_session(vowel_space_recordings=vowels)
        assert "vowel_space_group" in session.tasks
        vs_task = session.tasks["vowel_space_group"]
        assert vs_task["task_status"] == "not_estimable"
        assert vs_task["task_schema_version"] == VOWEL_SPACE_SCHEMA_VERSION
        assert vs_task["task_schema_fingerprint"] == vowel_space_schema_fingerprint()
        assert vs_task["vsa_estimable"] is False
        assert vs_task["features"]["vowel_space_area_hz2"] is None

    def test_missing_corner_vowel_i_marks_vsa_not_estimable(self) -> None:
        """4. Missing corner vowel /i/ must mark VSA as not estimable."""
        vowels = _valid_vowels()
        vowels.pop("i")
        session = analyze_multitask_session(vowel_space_recordings=vowels)
        vs_task = session.tasks["vowel_space_group"]
        assert vs_task["task_status"] == "not_estimable"
        assert vs_task["task_schema_fingerprint"] == vowel_space_schema_fingerprint()
        assert vs_task["vsa_estimable"] is False

    def test_missing_corner_vowel_u_marks_vsa_not_estimable(self) -> None:
        """5. Missing corner vowel /u/ must mark VSA as not estimable."""
        vowels = _valid_vowels()
        vowels.pop("u")
        session = analyze_multitask_session(vowel_space_recordings=vowels)
        vs_task = session.tasks["vowel_space_group"]
        assert vs_task["task_status"] == "not_estimable"
        assert vs_task["task_schema_fingerprint"] == vowel_space_schema_fingerprint()
        assert vs_task["vsa_estimable"] is False

    def test_invalid_audio_input_type_handles_safely(self) -> None:
        """6. Passing non-audio, corrupt or invalid types must be caught cleanly."""
        session = analyze_multitask_session(
            ddk_recordings={"ta": "not_an_audio_file.nonexistent"},
            connected_speech=b"not a valid wav binary buffer",
        )
        assert session.tasks["ddk_ta"]["task_status"] == "processing_failed"
        assert session.tasks["ddk_ta"]["task_schema_fingerprint"] == ddk_schema_fingerprint()
        assert session.tasks["ddk_ta"]["preprocessing_status"] == "not_run"

        assert session.tasks["connected_speech_passage"]["task_status"] == "processing_failed"
        assert (
            session.tasks["connected_speech_passage"]["task_schema_fingerprint"]
            == connected_speech_schema_fingerprint()
        )
        assert session.tasks["connected_speech_passage"]["preprocessing_status"] == "not_run"

    def test_unexpected_extraction_exception_isolation(self) -> None:
        """7. Unexpected internal extraction errors must not leak stack traces or crash session."""
        with patch(
            "voxneuro.features.tasks.pipeline.extract_ddk_features",
            side_effect=RuntimeError("Simulated internal math error"),
        ):
            session = analyze_multitask_session(ddk_recordings={"ka": _valid_ddk()})
            task = session.tasks["ddk_ka"]
            assert task["task_status"] == "processing_failed"
            assert task["task_schema_fingerprint"] == ddk_schema_fingerprint()
            assert any(
                "RuntimeError: Simulated internal math error" in err for err in task["errors"]
            )

    def test_partial_successful_session_failure_isolation(self) -> None:
        """8. A failed task must NOT invalidate unrelated successfully completed tasks."""
        session = analyze_multitask_session(
            sustained_vowel=_valid_sustained(),
            ddk_recordings={"pa": _invalid_audio_clipped()},  # fails
            connected_speech=_valid_cs(),  # succeeds
            vowel_space_recordings=_valid_vowels(),  # succeeds
        )
        assert session.overall_processing_status == "partial"
        assert session.tasks["sustained_vowel_a"]["task_status"] == "complete"
        assert session.tasks["ddk_pa"]["task_status"] == "quality_failed"
        assert session.tasks["connected_speech_passage"]["task_status"] == "complete"
        assert session.tasks["vowel_space_group"]["task_status"] == "complete"

        # Check all fingerprints are valid and populated
        assert session.tasks["ddk_pa"]["task_schema_fingerprint"] == ddk_schema_fingerprint()
        assert session.tasks["connected_speech_passage"]["task_schema_fingerprint"] == (
            connected_speech_schema_fingerprint()
        )
        assert session.tasks["vowel_space_group"]["task_schema_fingerprint"] == (
            vowel_space_schema_fingerprint()
        )

    def test_all_tasks_failed_overall_status(self) -> None:
        """9. When all provided tasks fail, overall status must reflect failure without crashes."""
        session = analyze_multitask_session(
            sustained_vowel=_invalid_audio_short(),
            ddk_recordings={"pa": _invalid_audio_clipped()},
            connected_speech=_invalid_audio_short(),
        )
        assert session.overall_processing_status == "quality_failed"
        for t_data in session.tasks.values():
            assert t_data["task_status"] == "quality_failed"
            assert t_data["task_schema_fingerprint"] != ""

    def test_schema_fingerprints_remain_correct_after_all_failures(self) -> None:
        """10. Schema fingerprints must never be blank strings regardless of processing outcome."""
        session = analyze_multitask_session(
            sustained_vowel=_invalid_audio_clipped(),
            ddk_recordings={"pa": _invalid_audio_clipped()},
            connected_speech=_invalid_audio_clipped(),
            vowel_space_recordings={"a": _invalid_audio_clipped(), "i": _invalid_audio_clipped()},
        )
        assert session.schema_fingerprint == v4_envelope_schema_fingerprint()
        for t_name, t_data in session.tasks.items():
            fp = t_data["task_schema_fingerprint"]
            assert fp != "", f"Empty fingerprint found in task: {t_name}"
            assert len(fp) == 64, f"Invalid SHA-256 length in task {t_name}: {fp}"
