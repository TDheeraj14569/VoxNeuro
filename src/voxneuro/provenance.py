"""Content fingerprints for the source and configuration used in experiments."""

from __future__ import annotations

import hashlib
from pathlib import Path

from voxneuro.config import PROJECT_ROOT

PROVENANCE_REQUIRED_FILES: tuple[str, ...] = (
    "app.py",
    "pyproject.toml",
    "requirements-lock.txt",
    "uv.lock",
    ".streamlit/config.toml",
)

FRONTEND_PROVENANCE_REQUIRED_FILES: tuple[str, ...] = (
    "frontend/acoustic-visualizer/package.json",
    "frontend/acoustic-visualizer/package-lock.json",
    "frontend/acoustic-visualizer/src/main.js",
    "frontend/acoustic-visualizer/dist/visualizer.bundle.js",
)


def project_code_fingerprint() -> str:
    """Hash tracked source, configuration, and dependency-lock files deterministically."""
    required_paths = [PROJECT_ROOT / rel for rel in PROVENANCE_REQUIRED_FILES]
    for req in required_paths:
        if not req.is_file():
            raise FileNotFoundError(f"Required provenance file is missing: {req}")
    paths = list(required_paths)
    for directory in (PROJECT_ROOT / "src", PROJECT_ROOT / "scripts", PROJECT_ROOT / "configs"):
        if not directory.is_dir():
            raise FileNotFoundError(f"Required provenance directory is missing: {directory}")
        paths.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix.casefold() in {".py", ".yaml", ".yml", ".json", ".sql"}
        )
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        if not path.is_file():
            raise FileNotFoundError(f"Provenance file is missing: {path}")
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
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


def frontend_code_fingerprint() -> str:
    """Hash frontend source, bundle, and package manifests deterministically."""
    required_paths = [PROJECT_ROOT / rel for rel in FRONTEND_PROVENANCE_REQUIRED_FILES]
    for req in required_paths:
        if not req.is_file():
            raise FileNotFoundError(f"Required frontend provenance file is missing: {req}")
    digest = hashlib.sha256()
    for path in sorted(required_paths):
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def release_provenance() -> dict[str, str]:
    """Return provenance fingerprints for model pipeline and frontend release."""
    return {
        "model_pipeline_fingerprint": project_code_fingerprint(),
        "frontend_fingerprint": frontend_code_fingerprint(),
    }
