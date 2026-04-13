-- 003_add_audit_log.sql
-- Indexes for the audit_log table to support efficient queries.

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
    ON audit_log (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_resource
    ON audit_log (resource_type, resource_id);
