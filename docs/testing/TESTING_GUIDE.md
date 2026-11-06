# Testing guide

Run from repository root in the isolated environment:

```powershell
uv sync --all-extras --locked
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\python.exe scripts\verify_project.py
```

The synthetic fixtures are software-only signals and never clinical observations. Dataset-specific scripts require downloaded data and generate local outputs excluded from Git. Browser microphone permission, physical microphone behavior, and clinical workflow are manual checks; automated tests do not claim those occurred.

