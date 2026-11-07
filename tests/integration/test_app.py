import shutil
from io import BytesIO
from pathlib import Path

import numpy as np
import soundfile as sf
from streamlit.testing.v1 import AppTest

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro import config
from voxneuro.features.schema import FEATURE_NAMES, SCHEMA_VERSION


def test_app_home_renders_and_start_button_opens_recording_page():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=20).run()
    assert not app.exception
    assert any("VoxNeuro" in element.value for element in app.title)
    app.button[0].click().run()
    assert not app.exception
    assert len(app.audio_input) == 1


def test_app_wav_upload_runs_analysis_features_and_report():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    payload = BytesIO()
    sf.write(payload, sustained_vowel(), 16000, format="WAV", subtype="PCM_16")
    # Cold uv environments may pay first-use Librosa/Numba compilation costs.
    app = AppTest.from_file(app_path, default_timeout=90)
    app.session_state["voxneuro_nav"] = "Voice assessment"
    app.run()
    app.radio[0].set_value("Upload WAV").run()
    app.get("file_uploader")[0].set_value(("synthetic.wav", payload.getvalue(), "audio/wav")).run()
    analyze = next(button for button in app.button if button.label == "Analyze this recording")
    analyze.click().run()

    assert not app.exception
    assert app.session_state["voxneuro_quality"].valid
    assert app.session_state["voxneuro_features"]["schema_version"] == SCHEMA_VERSION
    assert (
        len([key for key in app.session_state["voxneuro_features"] if key in FEATURE_NAMES]) == 39
    )
    assert app.session_state["voxneuro_report"]["features"]["schema_version"] == SCHEMA_VERSION
    assert app.session_state["voxneuro_analysis_status"] == "complete"
    assert app.session_state["voxneuro_report"]["model_assessment"]["status"].startswith(
        "Unavailable"
    )
    assert "mfcc_12_sd" in app.session_state["voxneuro_html_report"]
    assert any("HTML report" in button.label for button in app.get("download_button"))

    app.sidebar.radio[0].set_value("Signal analysis").run()
    assert not app.exception
    assert any(item.value == "Interactive 3D signal views" for item in app.subheader)
    assert len(app.slider) == 1
    app.slider[0].set_value(0.1).run()
    assert not app.exception
    app.radio[0].set_value("Spectrogram").run()
    assert not app.exception

    app.sidebar.radio[0].set_value("Feature analysis").run()
    assert not app.exception
    assert len(app.dataframe) == 4
    assert len(app.session_state["voxneuro_features"]) == 43
    csv_frame = app.dataframe[0].value
    assert {
        "schema_version",
        "schema_fingerprint",
        "feature_config_fingerprint",
        "preprocessing_config_fingerprint",
    }.issubset(csv_frame.columns)
    assert csv_frame["schema_version"].eq(SCHEMA_VERSION).all()
    app.sidebar.radio[0].set_value("Reports").run()
    assert not app.exception
    assert len(app.get("download_button")) == 3
    assert any("Limit: ≤ 1.00%" in md.value for md in app.markdown)
    assert any("Mono" in md.value for md in app.markdown)
    assert any("Method &amp; Interpretation" in md.value for md in app.markdown)


def test_app_all_navigation_sections_render_without_exceptions():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    pages = [
        "Overview",
        "Voice assessment",
        "Signal analysis",
        "Feature analysis",
        "Research model",
        "Reports",
        "Method & privacy",
    ]
    app = AppTest.from_file(app_path, default_timeout=30).run()
    for page in pages:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f"The {page!r} section raised an exception."


def test_app_invalid_wav_shows_actionable_error_without_crashing():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Voice assessment"
    app.run()
    app.radio[0].set_value("Upload WAV").run()
    app.get("file_uploader")[0].set_value(("invalid.wav", b"not a WAV file", "audio/wav")).run()
    next(button for button in app.button if button.label == "Analyze this recording").click().run()

    assert not app.exception
    assert app.session_state["voxneuro_analysis_status"] == "failed"
    assert app.session_state["voxneuro_analysis_error"]


def test_app_shows_safe_empty_state_when_research_receipts_and_report_are_absent(
    tmp_path, monkeypatch
):
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    project_root = Path(__file__).resolve().parents[2]
    shutil.copytree(project_root / "configs", tmp_path / "configs")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)

    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_nav"] = "Research model"
    app.run()
    assert not app.exception
    assert any("Current evaluation results are unavailable" in item.value for item in app.info)

    app.sidebar.radio[0].set_value("Reports").run()
    assert not app.exception
    assert any("Complete a successful analysis" in item.value for item in app.info)


def test_app_stereo_upload_displays_stereo_channel_text():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    payload = BytesIO()
    mono = sustained_vowel()
    stereo = np.column_stack((mono, mono))
    sf.write(payload, stereo, 16000, format="WAV", subtype="PCM_16")
    app = AppTest.from_file(app_path, default_timeout=60)
    app.session_state["voxneuro_nav"] = "Voice assessment"
    app.run()
    app.radio[0].set_value("Upload WAV").run()
    app.get("file_uploader")[0].set_value(("stereo.wav", payload.getvalue(), "audio/wav")).run()
    analyze = next(button for button in app.button if button.label == "Analyze this recording")
    analyze.click().run()

    assert not app.exception
    assert app.session_state["voxneuro_quality"].valid
    app.sidebar.radio[0].set_value("Reports").run()
    assert not app.exception
    assert any("2-ch stereo" in md.value for md in app.markdown)
