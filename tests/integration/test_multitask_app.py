"""Integration tests for Streamlit Multi-Task assessment view."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import soundfile as sf
from streamlit.testing.v1 import AppTest

from tests.fixtures.synthetic_connected_speech import synthetic_connected_speech
from tests.fixtures.synthetic_ddk_audio import synthetic_ddk_train
from tests.fixtures.synthetic_vowels import synthetic_formant_vowel


def _wav_bytes(samples: np.ndarray, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_multitask_page_renders_without_exception():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Multi-task assessment"
    app.run()
    assert not app.exception
    assert any("Multi-task speech assessment" in t.value for t in app.title)


def test_research_operations_page_renders_without_exception():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Research operations"
    app.run()
    assert not app.exception
    assert any("Research operations" in t.value for t in app.title)


def test_multitask_ddk_upload_and_analysis():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Multi-task assessment"
    app.run()

    # Generate synthetic DDK audio
    ddk_audio = synthetic_ddk_train(sample_rate=16000, duration=4.0, target_rate_hz=5.0)
    wav_data = _wav_bytes(ddk_audio, 16000)

    # Find file uploader for DDK /pa/
    ddk_uploaders = [
        u for u in app.get("file_uploader") if "mt_ddk_file_pa" in getattr(u, "key", "")
    ]
    assert len(ddk_uploaders) == 1
    ddk_uploaders[0].set_value(("ddk_pa.wav", wav_data, "audio/wav")).run()

    # Click analyze button for AMR_PA
    analyze_btn = next(b for b in app.button if "mt_ddk_btn_pa" in getattr(b, "key", ""))
    analyze_btn.click().run()

    assert not app.exception
    assert "voxneuro_mt_ddk_runs" in app.session_state
    assert "pa" in app.session_state["voxneuro_mt_ddk_runs"]
    res = app.session_state["voxneuro_mt_ddk_runs"]["pa"]["result"]
    assert res.task_status == "complete"
    assert res.features["estimated_event_rate_per_s"] is not None


def test_multitask_connected_speech_upload_and_analysis():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Multi-task assessment"
    app.run()

    cs_audio = synthetic_connected_speech(sample_rate=16000)
    wav_data = _wav_bytes(cs_audio, 16000)

    cs_uploaders = [
        u for u in app.get("file_uploader") if "mt_cs_file_uploader" in getattr(u, "key", "")
    ]
    assert len(cs_uploaders) == 1
    cs_uploaders[0].set_value(("connected_speech.wav", wav_data, "audio/wav")).run()

    analyze_btn = next(b for b in app.button if "mt_cs_btn" in getattr(b, "key", ""))
    analyze_btn.click().run()

    assert not app.exception
    assert "voxneuro_mt_cs_run" in app.session_state
    res = app.session_state["voxneuro_mt_cs_run"]["result"]
    assert res.task_status == "complete"
    assert res.features["total_recording_duration_s"] > 0


def test_multitask_vowel_space_upload_and_computation():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Multi-task assessment"
    app.run()

    # Upload corner vowels /a/, /i/, /u/
    v_a = _wav_bytes(synthetic_formant_vowel("a", duration=2.0))
    v_i = _wav_bytes(synthetic_formant_vowel("i", duration=2.0))
    v_u = _wav_bytes(synthetic_formant_vowel("u", duration=2.0))

    u_a = next(u for u in app.get("file_uploader") if "mt_vs_file_a" in getattr(u, "key", ""))
    u_i = next(u for u in app.get("file_uploader") if "mt_vs_file_i" in getattr(u, "key", ""))
    u_u = next(u for u in app.get("file_uploader") if "mt_vs_file_u" in getattr(u, "key", ""))

    u_a.set_value(("vowel_a.wav", v_a, "audio/wav"))
    u_i.set_value(("vowel_i.wav", v_i, "audio/wav"))
    u_u.set_value(("vowel_u.wav", v_u, "audio/wav")).run()

    compute_btn = next(b for b in app.button if "mt_vs_compute_btn" in getattr(b, "key", ""))
    compute_btn.click().run()

    assert not app.exception
    assert "voxneuro_mt_vs_result" in app.session_state
    vs_res = app.session_state["voxneuro_mt_vs_result"]
    assert vs_res.task_status == "complete"
    assert vs_res.features["vowel_space_area_hz2"] is not None


def test_multitask_unified_session_assembly_and_clear():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Multi-task assessment"
    app.run()

    # Upload and analyze DDK /pa/
    ddk_audio = synthetic_ddk_train(sample_rate=16000, duration=4.0, target_rate_hz=5.0)
    wav_data = _wav_bytes(ddk_audio, 16000)
    u_pa = next(u for u in app.get("file_uploader") if "mt_ddk_file_pa" in getattr(u, "key", ""))
    u_pa.set_value(("ddk_pa.wav", wav_data, "audio/wav")).run()
    next(b for b in app.button if "mt_ddk_btn_pa" in getattr(b, "key", "")).click().run()

    # Click Assemble Multi-Task Session
    assemble_btn = next(b for b in app.button if "mt_assemble_btn" in getattr(b, "key", ""))
    assemble_btn.click().run()

    assert not app.exception
    assert "voxneuro_mt_session_envelope" in app.session_state
    envelope = app.session_state["voxneuro_mt_session_envelope"]
    assert envelope.overall_processing_status == "complete"
    assert "ddk_pa" in envelope.tasks

    # Verify download buttons are present
    assert any("mt_download_json_btn" in getattr(d, "key", "") for d in app.get("download_button"))
    assert any("mt_download_html_btn" in getattr(d, "key", "") for d in app.get("download_button"))

    # Test Clear button
    clear_btn = next(b for b in app.button if "mt_clear_btn" in getattr(b, "key", ""))
    clear_btn.click().run()

    assert not app.exception
    assert "voxneuro_mt_session_envelope" not in app.session_state
    assert len(app.session_state.get("voxneuro_mt_ddk_runs", {})) == 0
