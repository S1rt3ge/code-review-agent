-- Add webhook idempotency and database-level tenant isolation policies.

CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_repo_pr_head_sha
    ON reviews (repo_id, github_pr_number, head_sha)
    WHERE head_sha IS NOT NULL;

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE repositories ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_jobs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'users' AND policyname = 'tenant_users_self') THEN
        CREATE POLICY tenant_users_self ON users
            USING (id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
            WITH CHECK (id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'repositories' AND policyname = 'tenant_repositories_self') THEN
        CREATE POLICY tenant_repositories_self ON repositories
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'tenant_reviews_self') THEN
        CREATE POLICY tenant_reviews_self ON reviews
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'audit_log' AND policyname = 'tenant_audit_log_self') THEN
        CREATE POLICY tenant_audit_log_self ON audit_log
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'findings' AND policyname = 'tenant_findings_by_review') THEN
        CREATE POLICY tenant_findings_by_review ON findings
            USING (
                EXISTS (
                    SELECT 1 FROM reviews
                    WHERE reviews.id = findings.review_id
                      AND reviews.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM reviews
                    WHERE reviews.id = findings.review_id
                      AND reviews.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
            );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'agent_executions' AND policyname = 'tenant_agent_executions_by_review') THEN
        CREATE POLICY tenant_agent_executions_by_review ON agent_executions
            USING (
                EXISTS (
                    SELECT 1 FROM reviews
                    WHERE reviews.id = agent_executions.review_id
                      AND reviews.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM reviews
                    WHERE reviews.id = agent_executions.review_id
                      AND reviews.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
            );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'analysis_jobs' AND policyname = 'tenant_analysis_jobs_by_review') THEN
        CREATE POLICY tenant_analysis_jobs_by_review ON analysis_jobs
            USING (
                EXISTS (
                    SELECT 1 FROM reviews
                    WHERE reviews.id = analysis_jobs.review_id
                      AND reviews.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM reviews
                    WHERE reviews.id = analysis_jobs.review_id
                      AND reviews.user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
                )
            );
    END IF;
END
$$;
