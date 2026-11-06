from scripts import verify_model


def test_model_verifier_reports_missing_local_artifacts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(verify_model, "ROOT", tmp_path)
    assert verify_model.main() == 2
    assert "Model bundle or UAMS feature table missing" in capsys.readouterr().out
