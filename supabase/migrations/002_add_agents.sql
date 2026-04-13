-- 002_add_agents.sql
-- Additional indexes for performance and check constraints for enum-like columns.

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_findings_review_id_severity
    ON findings (review_id, severity);

CREATE INDEX IF NOT EXISTS idx_agent_executions_review_id
    ON agent_executions (review_id, agent_name);

CREATE INDEX IF NOT EXISTS idx_reviews_user_status
    ON reviews (user_id, status, created_at DESC);

-- Check constraints on status / severity enum columns
ALTER TABLE reviews
    ADD CONSTRAINT chk_review_status
    CHECK (status IN ('pending', 'analyzing', 'done', 'error'));

ALTER TABLE findings
    ADD CONSTRAINT chk_finding_severity
    CHECK (severity IN ('critical', 'warning', 'info'));

ALTER TABLE agent_executions
    ADD CONSTRAINT chk_execution_status
    CHECK (status IN ('pending', 'running', 'done', 'error'));
