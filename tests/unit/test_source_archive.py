import zipfile
from collections import Counter

from scripts.build_source_archive import OUTPUT, ROOT, build_archive, source_files


def test_source_archive_keeps_project_files_and_excludes_data_and_caches(tmp_path):
    files = {
        "app.py": "import streamlit",
        "README.md": "project",
        "pyproject.toml": "project = true",
        "requirements-lock.txt": "package==1",
        "uv.lock": "version = 1",
        "src/voxneuro/__init__.py": "",
        "scripts/verify_project.py": "",
        "tests/__init__.py": "",
        "configs/audio_config.yaml": "sample_rate: 16000",
        "docs/ARCHITECTURE.md": "# Architecture",
        "data/raw/README.md": "# Put source datasets here",
        "data/raw/recording.wav": "audio",
        "data/processed/features.csv": "features",
        "src/voxneuro/__pycache__/module.pyc": "bytecode",
        ".venv/pyvenv.cfg": "environment",
        ".git/config": "repository",
        ".env": "SECRET=value",
        ".env.local": "SECRET=value",
        ".env.example": "SECRET=replace-me",
        ".envrc": "export SECRET=value",
        ".streamlit/secrets.toml": "api_key = 'private'",
        ".aws/credentials": "aws_access_key_id = private",
        ".npmrc": "//registry/:_authToken=private",
        "keys/private.pem": "private key",
        "keys/private.key": "private key",
        "keys/identity.p12": "private certificate",
        "keys/id_ed25519": "private key",
        "frontend/acoustic-visualizer/dist/visualizer.bundle.js": "local frontend bundle",
        "other-project/dist/build.js": "ordinary build output",
        "AI_REVIEW_BUNDLE_README.txt": "review-bundle-only notes",
        "review_evidence/uams_nested_summary.csv": "aggregate review-only evidence",
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    result = build_archive(tmp_path, tmp_path / "review.zip")
    with zipfile.ZipFile(tmp_path / "review.zip") as archive:
        names = set(archive.namelist())
        assert archive.testzip() is None
    assert result["members"] == len(names)
    assert result["sha256"]
    assert "app.py" in names
    assert "data/raw/README.md" in names
    assert "data/raw/recording.wav" not in names
    assert "data/processed/features.csv" not in names
    assert not any("__pycache__" in name or ".venv" in name or ".git/" in name for name in names)
    assert ".env.example" in names
    assert "frontend/acoustic-visualizer/dist/visualizer.bundle.js" in names
    assert "other-project/dist/build.js" not in names
    assert "AI_REVIEW_BUNDLE_README.txt" not in names
    assert "review_evidence/uams_nested_summary.csv" not in names
    assert not any(
        name in names
        for name in (
            ".env",
            ".env.local",
            ".envrc",
            ".streamlit/secrets.toml",
            ".aws/credentials",
            ".npmrc",
            "keys/private.pem",
            "keys/private.key",
            "keys/identity.p12",
            "keys/id_ed25519",
        )
    )


def test_checked_in_source_inventory_matches_archive_inclusion_rules():
    expected = [path.relative_to(ROOT).as_posix() for path in source_files(ROOT, OUTPUT)]
    inventory = (ROOT / "docs" / "audit" / "PROJECT_FILE_INVENTORY.md").read_text(encoding="utf-8")
    listed = [line[3:-1] for line in inventory.splitlines() if line.startswith("- `")]

    assert listed == expected
    assert "AI_REVIEW_BUNDLE_README.txt" not in expected
    assert not any(path.startswith("review_evidence/") for path in expected)
    assert f"Total included source/documentation files: **{len(expected)}**." in inventory

    counts = Counter(path.split("/", maxsplit=1)[0] for path in expected)
    summary = (ROOT / "docs" / "audit" / "PROJECT_FILE_INVENTORY_COUNTS.txt").read_text(
        encoding="utf-8"
    )
    assert f"Total: {len(expected)}" in summary
    for path, count in counts.items():
        assert f"{path}: {count}" in summary
