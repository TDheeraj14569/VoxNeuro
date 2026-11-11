# VoxNeuro Milestone 1: Data Acquisition Report

**Date:** 2026-11-11  
**Milestone:** M1 – Dataset Acquisition, Reproducible Processing, Model Evaluation, Training and M1 Verified Archive  
**Agent:** Antigravity (Gemini 3.8 Flash High)  

---

## 1. UAMS Dataset Acquisition

### Source Record
- **Repository:** Figshare
- **Article Title:** Voice Samples for Patients with Parkinson's Disease and Healthy Controls
- **DOI:** `10.6084/m9.figshare.23849127.v1`
- **URL:** `https://figshare.com/articles/dataset/Voice_Samples_for_Patients_with_Parkinson_s_Disease_and_Healthy_Controls/23849127`
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Local Destination:** `data/raw/uams/`

### Download Receipts & Checksums

| File | Source URL | Retrieval Timestamp (UTC) | Size (bytes) | MD5 | SHA-256 | Integrity Status |
|---|---|---|---|---|---|---|
| `Demographics_age_sex.xlsx` | `https://ndownloader.figshare.com/files/41836707` | 2026-11-10T18:40:13Z | 122,854 | `15bfde0fcb441c55dcd2fc3138c3a672` | `af622ccbd8b8051f19326688ad4138c4c72983f4b21aaae3ca58f6e1566a7305` | **VERIFIED** |
| `PD_AH.zip` | `https://ndownloader.figshare.com/files/41836710` | 2026-11-10T18:41:21Z | 2,247,417 | `2e525e419abdad509e5cbf201e30ef36` | `58cb6cc7e5cbc4d714de313b1ff8c612b13ddde4f096f5925593a8d9b3e9ca33` | **VERIFIED (Matches expected)** |
| `HC_AH.zip` | `https://ndownloader.figshare.com/files/41836713` | 2026-11-10T18:41:23Z | 2,007,786 | `55fd33d365380372dcfbae4f7f520246` | `b380943e2b49d15a3ff4b13fe2bc4aad50cf42d3a45a3239b14f26b8ba36f7db` | **VERIFIED (Matches expected)** |

### Expected Archive Inventory
- `PD_AH.zip`: 40 audio recordings (`/a/` vowel sustained phonation, Parkinson's disease cohort).
- `HC_AH.zip`: 41 audio recordings (`/a/` vowel sustained phonation, healthy control cohort).
- `Demographics_age_sex.xlsx`: Demographics workbook containing the required `Parselmouth` worksheet.

---

## 2. Privacy & Data Handling Compliance

1. **Local Retention Only:** All downloaded audio files and the demographic workbook are retained strictly within local directory `data/raw/uams/`.
2. **Git & Archive Exclusion:** `data/raw/` is excluded from git commits and will be excluded from all distribution archives.
3. **No Third-Party Transmission:** No participant recordings or demographic spreadsheets have been or will be uploaded to external APIs, review bundles, or public services.
