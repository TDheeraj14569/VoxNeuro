# Privacy and local data handling

## App recordings

- Streamlit binds to `127.0.0.1` by default, with CORS/XSRF protections enabled and telemetry disabled.
- Browser microphone audio is provided only after the user activates the recording control and grants browser/OS permission. WAV upload is an alternative.
- The app processes audio in the local Streamlit process and keeps current recording/results in session memory. It does not write raw recordings or reports to a persistent folder by default.
- JSON/CSV files are created for download only when the user activates a download control. Reports omit the source filename/path and do not provide a diagnosis or calibrated disease-risk probability. If local model evidence passes all checks, a report may include an explicitly unvalidated exploratory candidate with its raw uncalibrated score, fixed threshold, evidence state, and domain status; that score must not guide care.
- Closing the session clears its in-memory application state. The assessment view also offers a clear-results action.

## Research data and generated artifacts

The UAMS workbook, raw WAV files, local manifest with participant IDs/demographics/paths, feature table, evaluation predictions, and model bundle are sensitive research materials. Dataset scripts write them only under ignored local `data/` and `artifacts/` folders. These are excluded from Git and the source ZIP. Do not commit or redistribute them. Follow source licenses and institutional rules for access, consent, retention, and deletion.

## Temporary files

UAMS ZIPs and UCI RAR content are inspected and extracted into temporary staging locations. Scripts verify checksums, member paths, expected contents, and WAV/CSV shape before moving validated output into the local destination. Temporary staging directories are removed automatically on normal exit; after a forced termination, inspect and remove only its task-specific temporary directory once it is inactive.

## Audio SHA-256 Provenance & Privacy Disclosure

- Exported HTML and JSON technical reports record a SHA-256 cryptographic digest of the ingested audio payload (`audio_sha256`) to support exact source-audio identification and file-level provenance without altering or storing the raw audio.
- **Privacy Notice:** While a one-way cryptographic SHA-256 digest cannot reconstruct the raw vocal recording, it serves as a deterministic content digest and file-level content fingerprint of the exact file. Anyone possessing both the original audio file and the exported report can confirm a 1-to-1 match.
- This digest does not anonymize the speaker and should not be treated as a substitute for participant-data de-identification or patient consent. Users distributing exported reports should consider whether sharing the file-level hash is permissible under applicable research governance protocols.

## Security boundaries

The app accepts audio, not model bundles. Joblib artifacts can execute code when deserialized; the loader checks a local checksum and must only load trusted, internally generated artifacts. A checksum is not a signature. Do not expose the local server on a network or use it with participant data in a deployed environment without an approved security/privacy design.

Voice may remain identifying even when direct identifiers are removed. Account identifiers (email, display name) and password hashes are stored in a local SQLite database for study role-based access control. The local database is not encrypted at rest. Raw voice recordings are processed in memory and discarded upon session completion unless explicitly recorded under an active study consent protocol. There is no external cloud service. Clinical data governance and encryption-at-rest require separate institutional review before multi-site or clinical deployment.
