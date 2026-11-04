-- v7 additive migration. Back up first; startup also applies these idempotently.
BEGIN;
ALTER TABLE inventory_audits ADD COLUMN IF NOT EXISTS assigned_to INTEGER;
ALTER TABLE inventory_audits ADD COLUMN IF NOT EXISTS draft_saved_at TEXT;
ALTER TABLE inventory_audits ADD COLUMN IF NOT EXISTS draft_saved_by INTEGER;
ALTER TABLE inventory_audits ADD COLUMN IF NOT EXISTS draft_revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE inventory_audit_items ADD COLUMN IF NOT EXISTS draft_qty INTEGER;
ALTER TABLE inventory_audit_items ADD COLUMN IF NOT EXISTS draft_notes TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 0;
COMMIT;
