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
        "LICENSE": "MIT",
        ".streamlit/config.toml": "headless = true",
        "src/voxneuro/provenance.py": "def project_code_fingerprint(): pass",
        "frontend/acoustic-visualizer/package.json": "{}",
        "frontend/acoustic-visualizer/package-lock.json": "{}",
        "frontend/acoustic-visualizer/src/main.js": "console.log();",
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
    assert ".streamlit/config.toml" in names
    assert "LICENSE" in names
    assert "src/voxneuro/provenance.py" in names
    assert "frontend/acoustic-visualizer/package.json" in names
    assert "frontend/acoustic-visualizer/package-lock.json" in names
    assert "frontend/acoustic-visualizer/src/main.js" in names
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


def test_source_archive_fails_when_mandatory_provenance_file_missing(tmp_path):
    files = {
        "app.py": "import streamlit",
        "README.md": "project",
        "pyproject.toml": "project = true",
        "requirements-lock.txt": "package==1",
        "uv.lock": "version = 1",
        "LICENSE": "MIT",
        "src/voxneuro/__init__.py": "",
        "src/voxneuro/provenance.py": "code",
        "scripts/verify_project.py": "",
        "tests/__init__.py": "",
        "configs/audio_config.yaml": "sample_rate: 16000",
        "docs/ARCHITECTURE.md": "# Architecture",
        "frontend/acoustic-visualizer/package.json": "{}",
        "frontend/acoustic-visualizer/package-lock.json": "{}",
        "frontend/acoustic-visualizer/src/main.js": "console.log();",
        "frontend/acoustic-visualizer/dist/visualizer.bundle.js": "local bundle",
        # Intentionally omit .streamlit/config.toml
    }
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    import pytest

    with pytest.raises(FileNotFoundError) as exc_info:
        build_archive(tmp_path, tmp_path / "broken.zip", refresh_inventory=False)
    assert ".streamlit/config.toml" in str(exc_info.value)


def test_release_manifest_refresh_preserves_verification_claims(tmp_path, monkeypatch):
    import json

    import scripts.build_source_archive as archive_builder

    manifest_path = tmp_path / "RELEASE_MANIFEST.json"
    original = {
        "status": "ENGINEERING_VERIFIED_RESEARCH_ONLY",
        "provenance": {"project_code_fingerprint": "old"},
        "verification": {
            "total_tests": 611,
            "passed_tests": 611,
            "failed_tests": 0,
            "github_actions_status": "PENDING",
        },
    }
    manifest_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(archive_builder, "project_code_fingerprint", lambda: "new-code-hash")

    archive_builder.update_release_manifest(
        manifest_path,
        {
            "path": str(tmp_path / "VoxNeuro_PRODUCTION_RELEASE.zip"),
            "sha256": "a" * 64,
            "bytes": 1234,
            "members": 321,
        },
    )

    updated = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert updated["status"] == original["status"]
    assert updated["verification"] == original["verification"]
    assert updated["provenance"]["project_code_fingerprint"] == "new-code-hash"
    assert updated["archive"]["sha256"] == "a" * 64
    assert updated["archive"]["file_count"] == 321


def test_clean_extraction_contains_all_provenance_inputs_and_computes_fingerprint(tmp_path):
    import subprocess
    import sys

    # 1. Build an archive to a temporary path without dirtying git inventory
    archive_path = tmp_path / "clean_test_archive.zip"
    report = build_archive(ROOT, archive_path, refresh_inventory=False)
    assert archive_path.is_file()
    assert report["members"] > 0

    # 2. Extract into a clean directory outside the repository
    extraction_dir = tmp_path / "extracted_project"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as zf:
        zf.extractall(extraction_dir)

    # 3. Verify mandatory provenance files exist in the clean extraction
    assert (extraction_dir / ".streamlit" / "config.toml").is_file()
    assert (extraction_dir / "app.py").is_file()
    assert (extraction_dir / "pyproject.toml").is_file()
    assert (extraction_dir / "uv.lock").is_file()
    assert (extraction_dir / "requirements-lock.txt").is_file()
    assert (extraction_dir / "src" / "voxneuro" / "provenance.py").is_file()
    assert (
        extraction_dir / "frontend" / "acoustic-visualizer" / "dist" / "visualizer.bundle.js"
    ).is_file()

    # 4. Verify sensitive / generated files are absent
    for p in extraction_dir.rglob("*"):
        if p.is_file():
            assert not p.name.startswith(".env") or p.name == ".env.example"
            assert p.suffix.casefold() not in {
                ".pyc",
                ".pyo",
                ".wav",
                ".joblib",
                ".parquet",
                ".pkl",
            }
            assert not any(
                part in {".venv", "__pycache__", ".pytest_cache", ".git"} for part in p.parts
            )

    # 5. Run provenance computation inside clean extraction via isolated subprocess
    cmd = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "from pathlib import Path; "
            "root = Path.cwd(); "
            "sys.path.insert(0, str(root / 'src')); "
            "from voxneuro import config; "
            "config.PROJECT_ROOT = root; "
            "from voxneuro.provenance import project_code_fingerprint, frontend_code_fingerprint; "
            "p_fp = project_code_fingerprint(); "
            "f_fp = frontend_code_fingerprint(); "
            "assert len(p_fp) == 64; "
            "assert len(f_fp) == 64; "
            "print('PASS clean extraction fingerprint:', p_fp[:8], f_fp[:8])"
        ),
    ]
    proc = subprocess.run(cmd, cwd=str(extraction_dir), capture_output=True, text=True, check=True)
    assert "PASS clean extraction fingerprint:" in proc.stdout
