# Milestone 5 Release Verification Protocol

**Release Artifact:** `VoxNeuro_M5_VERIFIED.zip`  
**Sidecar Checksum File:** `VoxNeuro_M5_VERIFIED.zip.sha256`  
**Target Environment:** Isolated clean-room temporary directory on Python 3.12 (`uv`)  

---

## 1. Clean-Room Verification Procedure

Release verification must follow a strict clean-room protocol executed from a clean temporary directory:

### Step 1: Checksum Verification
Verify that the SHA-256 digest of `VoxNeuro_M5_VERIFIED.zip` matches the contents of `VoxNeuro_M5_VERIFIED.zip.sha256` character-for-character.

### Step 2: Archive Integrity & Policy Inspection
Inspect the ZIP archive contents:
1. `zipfile.ZipFile.testzip()` returns `None` (zero CRC or header corruption).
2. Prohibited Binary Audit:
   - Zero raw audio files (`.wav`, `.flac`, `.mp3`).
   - Zero SQLite databases (`.db`, `.sqlite`, `.sqlite3`).
   - Zero serialized binary model weights (`.joblib`, `.pkl`) except the authorized reference model.
   - Zero unredacted personal identifiers or host absolute paths.

### Step 3: Complete Automated Test Execution
In the extracted directory, execute the full test suite under `uv`:
```powershell
uv run pytest -q
```
In the full local workspace with UAMS/UCI processed artifacts and model binary, all 566 tests pass (0 failures, 0 errors, 0 skipped). In a source-only clean-room extraction where private datasets/models are intentionally excluded, private-artifact tests skip cleanly per design with zero failures or errors.

### Step 4: Code Quality & Linting
Execute static analysis checks:
```powershell
uv run ruff check .
uv run ruff format --check .
```
Zero linting violations or formatting errors permitted.

### Step 5: Provenance & Release Integrity Verification
Execute project verification script:
```powershell
uv run python scripts/verify_project.py
```
Confirms project code fingerprint, schema fingerprints, manifest checksums, absence of workstation paths in `review_evidence/`, and `RUNTIME_DATASET_AUTHORIZATION_NOT_INCLUDED_IN_RELEASE` / `derived_features_retention_default: false`.

### Step 6: Mandatory Release Safety Invariants
1. `allow_user_microphone_inference = false` in `configs/model_config.yaml`
2. `TRUSTED_DOMAIN_VALIDATION_REPORT_SHA256 = frozenset()` in `src/voxneuro/modeling/domains.py`
3. `approved_domains = []` in `configs/recording_domain_registry.yaml`
4. `clinical_diagnostic_use = false` in `configs/model_config.yaml`
5. `external_domain_validation_status = DOMAIN_VALIDATION_PENDING` in `src/voxneuro/modeling/domains.py`
6. Zero participant exclusion IDs (the three clipped PD sample IDs) in public files.
