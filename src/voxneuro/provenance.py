"""Content fingerprints for the source and configuration used in experiments."""

from __future__ import annotations

import hashlib
from pathlib import Path

from voxneuro.config import PROJECT_ROOT


def project_code_fingerprint() -> str:
    """Hash tracked source, configuration, and dependency-lock files deterministically."""
    paths = [
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "pyproject.toml",
        PROJECT_ROOT / "requirements-lock.txt",
        PROJECT_ROOT / "uv.lock",
        PROJECT_ROOT / ".streamlit" / "config.toml",
    ]
    for directory in (PROJECT_ROOT / "src", PROJECT_ROOT / "scripts", PROJECT_ROOT / "configs"):
        paths.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.casefold() in {".py", ".yaml", ".yml", ".json"}
        )
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        if not path.is_file():
            continue
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def combined_file_sha256(*paths: Path) -> str:
    """Hash the ordered contents of several provenance files as one receipt."""
    if not paths:
        raise ValueError("At least one file is required for a combined fingerprint.")
    digest = hashlib.sha256()
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        digest.update(path.read_bytes())
    return digest.hexdigest()
