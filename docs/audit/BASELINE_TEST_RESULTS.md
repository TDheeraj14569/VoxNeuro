# Baseline Test Results

Captured before this task's implementation changes on 2026-11-06.

| Check | Command | Result |
|---|---|---|
| Python version | .venv\Scripts\python.exe --version | CPython 3.12.14 |
| Tests | uv run --locked python -m pytest -q | 74 passed in 16.32s |
| Ruff lint | uv run --locked ruff check . | Passed |
| Ruff format | uv run --locked ruff format --check . | 110 files already formatted |
| Project verifier | uv run --locked python scripts/verify_project.py | 10 imports and 7 required files passed |
| Model verifier | uv run --locked python scripts/verify_model.py | Passed |

These are local baseline results; they must not be presented as final results.
