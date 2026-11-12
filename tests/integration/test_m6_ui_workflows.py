"""Integration tests for redesigned M6 role-based UI flows and authorization gating."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import soundfile as sf
from streamlit.testing.v1 import AppTest

from tests.fixtures.synthetic_audio import sustained_vowel
from voxneuro.study.auth import authenticate_user, register_user
from voxneuro.study.database import get_connection, run_migrations


def _wav_bytes() -> bytes:
    buf = BytesIO()
    sf.write(buf, sustained_vowel(), 16000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_m6_public_pages_render_and_hide_privileged_admin_data(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "ui_public.db"
    monkeypatch.setattr("voxneuro.study.database.DEFAULT_DB_PATH", test_db)
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.run()
    assert not app.exception

    # Navigate to How It Works, Privacy & Safety, Help, About, Account cleanly via M6 view state
    for view_name, expected_heading in [
        ("How It Works", "How VoxNeuro Works"),
        ("About", "About VoxNeuro"),
        ("Privacy & Safety", "Privacy & Safety"),
        ("Help", "Help & Frequently Asked Questions"),
        ("Results", "Your Voice Check Results"),
        ("Account", "Account & Preferences"),
    ]:
        app.session_state["voxneuro_m6_view"] = view_name
        app.run()
        assert not app.exception
        assert any(expected_heading in t.value for t in app.title)

    # Unauthenticated visitor cannot access privileged Researcher / Admin portals
    for priv_view in ("Researcher", "Model Admin", "System Admin"):
        app.session_state["voxneuro_m6_view"] = priv_view
        app.run()
        assert not app.exception
        assert any("Access Restricted" in w.value for w in app.warning)


def test_m6_voice_check_produces_fail_closed_abstention_with_disclaimer(
    tmp_path: Path, monkeypatch
):
    test_db = tmp_path / "ui_voice.db"
    monkeypatch.setattr("voxneuro.study.database.DEFAULT_DB_PATH", test_db)
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=60)
    app.session_state["voxneuro_nav"] = "Voice assessment"
    app.run()
    app.radio[0].set_value("Upload WAV").run()
    app.get("file_uploader")[0].set_value(("check.wav", _wav_bytes(), "audio/wav")).run()
    next(b for b in app.button if b.label == "Analyze this recording").click().run()

    assert not app.exception
    pred = app.session_state["voxneuro_prediction"]
    assert pred.abstained is True
    assert pred.research_score is None
    assert "NOT diagnose" in pred.research_only_disclaimer


def test_m6_authenticated_admin_unlocks_role_portals_and_user_history(tmp_path: Path, monkeypatch):
    test_db = tmp_path / "ui_admin.db"
    run_migrations(test_db)
    conn = get_connection(test_db)
    try:
        register_user(
            conn,
            username="ui_admin",
            email="ui_admin@example.org",
            password="AdminStrongPassword123!",
            display_name="Dr. Admin",
            role="admin",
        )
        _, admin_token = authenticate_user(
            conn, identifier="ui_admin", password="AdminStrongPassword123!"
        )
    finally:
        conn.close()

    monkeypatch.setattr("voxneuro.study.database.DEFAULT_DB_PATH", test_db)
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.session_state["voxneuro_auth_token"] = admin_token
    for view_name in ("Dashboard", "My History", "Researcher", "Model Admin", "System Admin"):
        app.session_state["voxneuro_m6_view"] = view_name
        app.run()
        assert not app.exception
        assert not any("Access Restricted" in w.value for w in app.warning)
