# Architecture Baseline

The application is a local Streamlit interface over a Python package under src/voxneuro. Audio decoding/validation/preprocessing feed Praat/Librosa extraction. Dataset scripts create manifests, validate datasets, extract features, run grouped evaluation, and serialize research-only model bundles. Reports and visualizations are separate modules. YAML configuration is stored in configs/; pytest coverage is in tests/; the interface starts from app.py.

The app is intended for local technical voice analysis. It does not produce a disease classification for new microphone recordings. Training and evaluation are exploratory research workflows and remain separate from app-time analysis.

The completed architecture and release boundaries are documented in `docs/ARCHITECTURE.md`.
