-- 004_dataset_access_dua_fingerprint.sql
-- Milestone 5: Store authoritative DUA document cryptographic fingerprint on dataset_access records

ALTER TABLE dataset_access
ADD COLUMN dua_document_fingerprint TEXT NOT NULL DEFAULT '';
