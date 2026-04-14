-- Fix finding severity CHECK constraint.
-- The original constraint only allowed ('critical', 'warning', 'info') but all
-- analysis agents emit ('critical', 'high', 'medium', 'low', 'info'), causing
-- every INSERT of a finding to fail with a constraint violation.

ALTER TABLE findings
    DROP CONSTRAINT IF EXISTS chk_finding_severity;

ALTER TABLE findings
    ADD CONSTRAINT chk_finding_severity
    CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info'));
