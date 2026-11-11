"""Unit tests for multi-task session orchestration and voxneuro.voice.v4 envelope."""

from __future__ import annotations

import json
import uuid

import numpy as np

from tests.fixtures.synthetic_audio import sustained_vowel
from tests.fixtures.synthetic_connected_speech import synthetic_connected_speech
from tests.fixtures.synthetic_ddk_audio import synthetic_ddk_train
from tests.fixtures.synthetic_vowels import synthetic_formant_vowel
from voxneuro.audio.io import AudioRecord
from voxneuro.features.schema import (
    FEATURE_NAMES as V3_FEATURE_NAMES,
)
from voxneuro.features.schema import (
    SCHEMA_VERSION as V3_SCHEMA_VERSION,
)
from voxneuro.features.schema import (
    schema_fingerprint as v3_schema_fingerprint,
)
from voxneuro.features.tasks.pipeline import (
    MultiTaskSessionResult,
    analyze_multitask_session,
)
from voxneuro.features.tasks.schema import (
    V4_SCHEMA_VERSION,
    get_task_schema_registry,
    v4_envelope_schema_fingerprint,
)
from voxneuro.reporting.multitask_report import render_multitask_report_html


def _record(samples: np.ndarray, sr: int = 16000) -> AudioRecord:
    return AudioRecord(
        samples=samples.reshape(-1, 1),
        sample_rate=sr,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    )


class TestMultiTaskOrchestration:
    """Tests for multi-task session execution and schema v4 envelope."""

    def test_v4_envelope_fingerprint_and_registry(self) -> None:
        fp = v4_envelope_schema_fingerprint()
        assert isinstance(fp, str) and len(fp) == 64
        registry = get_task_schema_registry()
        assert len(registry) == 4
        assert V3_SCHEMA_VERSION in registry
        assert "voxneuro.task.ddk.v1" in registry
        assert "voxneuro.task.connected_speech.v1" in registry
        assert "voxneuro.task.vowel_space.v1" in registry

    def test_complete_multitask_session(self) -> None:
        # Create inputs for all 4 tasks
        v_a = _record(sustained_vowel(sample_rate=16000, duration=3.0))
        ddk_rec = _record(synthetic_ddk_train(sample_rate=16000, duration=4.0))
        cs_rec = _record(synthetic_connected_speech(sample_rate=16000))
        vs_recs = {
            "a": _record(synthetic_formant_vowel("a", duration=2.0)),
            "i": _record(synthetic_formant_vowel("i", duration=2.0)),
            "u": _record(synthetic_formant_vowel("u", duration=2.0)),
        }

        sess: MultiTaskSessionResult = analyze_multitask_session(
            sustained_vowel=v_a,
            ddk_recordings={"pa": ddk_rec},
            connected_speech=cs_rec,
            vowel_space_recordings=vs_recs,
        )

        assert sess.schema_version == V4_SCHEMA_VERSION
        assert sess.schema_fingerprint == v4_envelope_schema_fingerprint()
        assert sess.overall_processing_status == "complete"

        # Verify valid UUID4 session ID
        val_uuid = uuid.UUID(sess.session_id, version=4)
        assert str(val_uuid) == sess.session_id

        # Verify task keys present
        assert "sustained_vowel_a" in sess.tasks
        assert "ddk_pa" in sess.tasks
        assert "connected_speech_passage" in sess.tasks
        assert "vowel_space_group" in sess.tasks

        # Verify legacy Core39 v3 block
        v3_task = sess.tasks["sustained_vowel_a"]
        assert v3_task["task_schema_version"] == V3_SCHEMA_VERSION
        assert v3_task["task_schema_fingerprint"] == v3_schema_fingerprint()
        assert v3_task["task_status"] == "complete"
        assert len(v3_task["features"]) == 39
        assert list(v3_task["features"].keys()) == V3_FEATURE_NAMES

        # Verify JSON serialization
        json_str = sess.to_json()
        assert json_str.startswith("{")
        parsed = json.loads(json_str)
        assert parsed["session_id"] == sess.session_id

    def test_error_isolation_between_tasks(self) -> None:
        """A failure in DDK audio does not fail the sustained vowel or connected speech."""
        v_a = _record(sustained_vowel(sample_rate=16000, duration=3.0))
        # Intentionally invalid DDK (0.1s duration, fails quality check)
        bad_ddk = _record(np.zeros(1600, dtype=np.float64))
        cs_rec = _record(synthetic_connected_speech(sample_rate=16000))

        sess: MultiTaskSessionResult = analyze_multitask_session(
            sustained_vowel=v_a,
            ddk_recordings={"pa": bad_ddk},
            connected_speech=cs_rec,
        )

        # Overall status should be partial because some succeeded and one failed
        assert sess.overall_processing_status == "partial"
        assert sess.tasks["sustained_vowel_a"]["task_status"] == "complete"
        assert sess.tasks["connected_speech_passage"]["task_status"] == "complete"
        assert sess.tasks["ddk_pa"]["task_status"] == "quality_failed"

    def test_partial_session_with_only_ddk(self) -> None:
        ddk_rec = _record(synthetic_ddk_train(sample_rate=16000, duration=4.0))
        sess: MultiTaskSessionResult = analyze_multitask_session(ddk_recordings={"ta": ddk_rec})

        assert sess.overall_processing_status == "complete"
        assert len(sess.tasks) == 1
        assert "ddk_ta" in sess.tasks
        assert sess.tasks["ddk_ta"]["task_status"] == "complete"

    def test_render_multitask_report_html(self) -> None:
        v_a = _record(sustained_vowel(sample_rate=16000, duration=3.0))
        ddk_rec = _record(synthetic_ddk_train(sample_rate=16000, duration=4.0))
        sess = analyze_multitask_session(
            sustained_vowel=v_a,
            ddk_recordings={"pa": ddk_rec},
        )

        html_out = render_multitask_report_html(sess)
        assert "<!DOCTYPE html>" in html_out
        assert sess.session_id in html_out
        assert "sustained_vowel_a" in html_out
        assert "ddk_pa" in html_out
        assert "RESEARCH PROTOTYPE NOTICE" in html_out
