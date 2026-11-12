-- 002_participant_study_constraints.sql
-- Safe forward migration: enforce pending consent defaults and participant-study constraints

-- 1. Create indexes for participant-study and consent-study linkage
CREATE INDEX IF NOT EXISTS idx_participants_study ON participants (participant_id, study_id);
CREATE INDEX IF NOT EXISTS idx_consents_participant_study ON consents (participant_id, study_id, withdrawal_status);
CREATE INDEX IF NOT EXISTS idx_sessions_participant_study ON sessions (participant_id, study_id);

-- 2. Update any legacy enrolled participants who lack an active consent record to pending consent
UPDATE participants
SET consent_status = 'pending', consent_version = 'none'
WHERE participant_id NOT IN (
    SELECT DISTINCT participant_id FROM consents WHERE withdrawal_status = 0
) AND enrollment_status IN ('enrolled', 'active');
