-- v8 additive migration: Phase 1 security and account-management fields.
-- Safe to re-run. Existing rows receive must_change_password = 0, so current
-- accounts retain their existing login behavior. No credential values are reset.
BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS must_change_password INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS temporary_password_fingerprint TEXT;

-- Fingerprints are stored only for newly generated temporary credentials.
-- NULL values are intentionally excluded so existing accounts are unaffected.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_temp_password_fingerprint
    ON users (temporary_password_fingerprint)
    WHERE temporary_password_fingerprint IS NOT NULL;

COMMIT;
