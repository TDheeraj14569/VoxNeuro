"""Build and verify the compact source-only project review archive."""

from __future__ import annotations

import hashlib
import os
import tempfile
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "VoxNeuro_source_audit.zip"
MAX_SOURCE_FILE_BYTES = 25 * 1024 * 1024
EXCLUDED_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    "node_modules",
    "__pycache__",
    "htmlcov",
    "build",
    "dist",
}
REVIEW_BUNDLE_EVIDENCE_DIRECTORY = "review_evidence"
REVIEW_BUNDLE_README = "AI_REVIEW_BUNDLE_README.txt"
PLACEHOLDER_ONLY_DIRECTORIES = {
    "data/raw",
    "data/interim",
    "data/processed",
    "artifacts/models",
    "artifacts/reports",
}
REQUIRED_FILES = {
    "app.py",
    "README.md",
    "pyproject.toml",
    "requirements-lock.txt",
    "uv.lock",
    "src/voxneuro/__init__.py",
    "scripts/verify_project.py",
    "tests/__init__.py",
    "configs/audio_config.yaml",
    "docs/ARCHITECTURE.md",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".wav",
    ".mp3",
    ".flac",
    ".joblib",
    ".pkl",
    ".parquet",
    ".npy",
    ".npz",
    ".h5",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
}
EXCLUDED_SECRET_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".p7b",
    ".p7c",
    ".p8",
    ".ppk",
    ".jks",
    ".keystore",
    ".crt",
    ".cer",
    ".der",
}
EXCLUDED_SECRET_FILENAMES = {
    "secrets.toml",
    "credentials",
    "credentials.json",
    "service-account.json",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "identity",
    ".netrc",
    ".pypirc",
    ".npmrc",
    ".envrc",
}
EXCLUDED_SECRET_PATHS = {
    ".aws/credentials",
    ".config/gcloud/application_default_credentials.json",
}


def _is_placeholder(path: Path, root: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    return any(
        relative.startswith(f"{directory}/")
        and relative.removeprefix(f"{directory}/") != "README.md"
        for directory in PLACEHOLDER_ONLY_DIRECTORIES
    )


def _directory_is_excluded(parent: str, name: str) -> bool:
    """Keep ordinary build outputs out, but ship the required local WebGL bundle."""
    if parent == "frontend/acoustic-visualizer" and name == "dist":
        return False
    if parent == "" and name == REVIEW_BUNDLE_EVIDENCE_DIRECTORY:
        return True
    return name in EXCLUDED_DIRECTORIES or name.startswith(".venv")


def _path_has_excluded_directory(relative: Path) -> bool:
    parent: list[str] = []
    for part in relative.parts[:-1]:
        if _directory_is_excluded("/".join(parent), part):
            return True
        parent.append(part)
    return False


def _is_secret_file(relative: Path) -> bool:
    """Exclude common local credentials and private-key/certificate formats."""
    filename = relative.name.casefold()
    return (
        filename == ".env"
        or (filename.startswith(".env.") and filename != ".env.example")
        or filename.startswith(".envrc.")
        or filename in EXCLUDED_SECRET_FILENAMES
        or (filename.startswith("id_") and "." not in filename)
        or relative.as_posix().casefold() in EXCLUDED_SECRET_PATHS
        or relative.suffix.casefold() in EXCLUDED_SECRET_SUFFIXES
    )


def source_files(root: Path, output: Path) -> list[Path]:
    """List project files while excluding environments, generated data, and caches."""
    files = []
    for directory, child_directories, filenames in os.walk(root):
        current = Path(directory)
        current_relative = current.relative_to(root).as_posix()
        if current_relative == ".":
            current_relative = ""
        child_directories[:] = sorted(
            name for name in child_directories if not _directory_is_excluded(current_relative, name)
        )
        for filename in filenames:
            path = current / filename
            relative = path.relative_to(root)
            if len(relative.parts) == 1 and filename == REVIEW_BUNDLE_README:
                continue
            if path.resolve() == output.resolve() or path.is_symlink():
                continue
            if _is_secret_file(relative):
                continue
            if path.suffix.casefold() in EXCLUDED_SUFFIXES:
                continue
            if path.stat().st_size > MAX_SOURCE_FILE_BYTES:
                continue
            if _is_placeholder(path, root):
                continue
            if any(part.startswith(".venv") for part in relative.parts):
                continue
            if _path_has_excluded_directory(relative):
                continue
            if filename in {".coverage"} or filename.endswith(".tmp"):
                continue
            files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix().casefold())


def _refresh_inventory_documents(root: Path, output: Path) -> None:
    """Regenerate the detailed and summarized inventories from the ZIP inclusion rules."""
    audit_dir = root / "docs" / "audit"
    if not audit_dir.is_dir():
        return
    members = source_files(root, output)
    relative_paths = [path.relative_to(root).as_posix() for path in members]
    counts = Counter(path.split("/", maxsplit=1)[0] for path in relative_paths)
    generated = date.today().isoformat()
    detail = (
        "# Project source file inventory\n\n"
        f"Generated from `scripts/build_source_archive.py` inclusion rules on {generated}. "
        "The source ZIP, separately-added AI review bundle evidence, local datasets, model "
        "artifacts, secrets, caches, and virtual environments are excluded.\n\n"
        + "\n".join(f"- `{path}`" for path in relative_paths)
        + f"\n\nTotal included source/documentation files: **{len(relative_paths)}**.\n"
    )
    summary = (
        "Included file counts by top-level path (same source-archive rules):\n\n"
        + "\n".join(f"{name}: {counts[name]}" for name in sorted(counts, key=str.casefold))
        + f"\n\nTotal: {len(relative_paths)}\n"
    )
    (audit_dir / "PROJECT_FILE_INVENTORY.md").write_text(detail, encoding="utf-8")
    (audit_dir / "PROJECT_FILE_INVENTORY_COUNTS.txt").write_text(summary, encoding="utf-8")


def build_archive(root: Path = ROOT, output: Path = OUTPUT) -> dict[str, object]:
    """Write a deterministic source ZIP, verify CRCs, and report its contents."""
    root = root.resolve()
    output = output.resolve()
    _refresh_inventory_documents(root, output)
    members = source_files(root, output)
    relative_names = {path.relative_to(root).as_posix() for path in members}
    missing = REQUIRED_FILES - relative_names
    if missing:
        raise FileNotFoundError(f"Source archive is missing required files: {sorted(missing)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{output.stem}-", suffix=".tmp", dir=output.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(
            temporary_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in members:
                relative = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
        with zipfile.ZipFile(temporary_path) as archive:
            corrupt = archive.testzip()
            if corrupt is not None:
                raise zipfile.BadZipFile(f"CRC validation failed for {corrupt}")
            names = set(archive.namelist())
            missing = REQUIRED_FILES - names
            if missing:
                raise zipfile.BadZipFile(f"Required files missing from archive: {sorted(missing)}")
            forbidden = [
                name
                for name in names
                if _is_secret_file(Path(name))
                or _path_has_excluded_directory(Path(name))
                or any(
                    part.endswith((".pyc", ".pyo", ".wav", ".joblib", ".parquet"))
                    for part in Path(name).parts
                )
            ]
            if forbidden:
                raise zipfile.BadZipFile(f"Excluded files entered the archive: {forbidden[:10]}")
        os.replace(temporary_path, output)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {
        "path": str(output),
        "bytes": output.stat().st_size,
        "members": len(members),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def main() -> int:
    report = build_archive()
    print(
        f"PASS source archive: {report['members']} files, {report['bytes']:,} bytes, "
        f"SHA-256 {report['sha256']}"
    )
    print(report["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
