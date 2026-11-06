"""Quick source-tree and import verification independent of external datasets."""

from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "app.py",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "src/voxneuro/audio/io.py",
    "src/voxneuro/features/extractor.py",
    "src/voxneuro/dataset/uci.py",
    "src/voxneuro/modeling/evaluation.py",
]
MODULES = [
    "voxneuro.audio.io",
    "voxneuro.audio.validation",
    "voxneuro.audio.preprocessing",
    "voxneuro.features.extractor",
    "voxneuro.dataset.audit",
    "voxneuro.dataset.uci",
    "voxneuro.modeling.evaluation",
    "voxneuro.modeling.model_bundle",
    "voxneuro.modeling.prediction",
    "voxneuro.provenance",
    "voxneuro.reporting.report",
]


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).is_file()]
    for path in missing:
        print(f"FAIL missing {path}")
    if missing:
        return 1
    for name in MODULES:
        importlib.import_module(name)
        print(f"PASS import {name}")
    print(f"PASS required files ({len(REQUIRED)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
