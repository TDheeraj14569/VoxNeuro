-- 005_dataset_access_registry_binding.sql
-- Milestone 4/5: Bind dataset_access DUA records to signed M4 trust registry metadata

ALTER TABLE dataset_access
ADD COLUMN authorization_ref TEXT NOT NULL DEFAULT '';

ALTER TABLE dataset_access
ADD COLUMN source_id TEXT NOT NULL DEFAULT '';

ALTER TABLE dataset_access
ADD COLUMN authorization_registry_id TEXT NOT NULL DEFAULT '';

ALTER TABLE dataset_access
ADD COLUMN authorization_registry_version TEXT NOT NULL DEFAULT '';

ALTER TABLE dataset_access
ADD COLUMN issuing_authority TEXT NOT NULL DEFAULT '';

ALTER TABLE dataset_access
ADD COLUMN dua_source_artifact_reference TEXT NOT NULL DEFAULT '';

ALTER TABLE dataset_access
ADD COLUMN dua_verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED';
