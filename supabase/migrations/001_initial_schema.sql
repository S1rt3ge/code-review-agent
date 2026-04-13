-- 001_initial_schema.sql
-- Creates all core tables for the AI Code Review Agent.

-- Enable uuid generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =========================================================================
-- users
-- =========================================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT NOT NULL UNIQUE,
    username        TEXT NOT NULL UNIQUE,
    plan            TEXT NOT NULL DEFAULT 'free',
    api_key_claude  TEXT,                -- Fernet-encrypted
    api_key_gpt     TEXT,                -- Fernet-encrypted
    ollama_enabled  BOOLEAN NOT NULL DEFAULT FALSE,
    ollama_host     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================================
-- repositories
-- =========================================================================
CREATE TABLE IF NOT EXISTS repositories (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    github_repo_owner       TEXT NOT NULL,
    github_repo_name        TEXT NOT NULL,
    github_repo_url         TEXT NOT NULL,
    github_installation_id  BIGINT,
    webhook_secret          TEXT,        -- Fernet-encrypted
    enabled                 BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_repo_user_owner_name UNIQUE (user_id, github_repo_owner, github_repo_name)
);

-- =========================================================================
-- reviews
-- =========================================================================
CREATE TABLE IF NOT EXISTS reviews (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    repo_id           UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    github_pr_number  INTEGER NOT NULL,
    github_pr_title   TEXT,
    head_sha          TEXT,
    base_sha          TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    error_message     TEXT,
    selected_agents   JSONB,
    lm_used           TEXT,
    total_findings    INTEGER NOT NULL DEFAULT 0,
    tokens_input      INTEGER NOT NULL DEFAULT 0,
    tokens_output     INTEGER NOT NULL DEFAULT 0,
    estimated_cost    NUMERIC(10, 4) NOT NULL DEFAULT 0,
    pr_comment_id     BIGINT,
    pr_comment_posted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_reviews_user_status_created
    ON reviews (user_id, status, created_at DESC);

-- =========================================================================
-- findings
-- =========================================================================
CREATE TABLE IF NOT EXISTS findings (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_id     UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    agent_name    TEXT NOT NULL,
    finding_type  TEXT NOT NULL,
    severity      TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    line_number   INTEGER NOT NULL,
    message       TEXT NOT NULL,
    suggestion    TEXT,
    code_snippet  TEXT,
    category      TEXT,
    is_duplicate  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_findings_review_severity
    ON findings (review_id, severity);

CREATE INDEX IF NOT EXISTS idx_findings_file_line
    ON findings (file_path, line_number);

-- =========================================================================
-- agent_executions
-- =========================================================================
CREATE TABLE IF NOT EXISTS agent_executions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    review_id       UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    agent_name      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    tokens_input    INTEGER NOT NULL DEFAULT 0,
    tokens_output   INTEGER NOT NULL DEFAULT 0,
    findings_count  INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_exec_review_agent
    ON agent_executions (review_id, agent_name);

-- =========================================================================
-- audit_log
-- =========================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action         TEXT NOT NULL,
    resource_type  TEXT NOT NULL,
    resource_id    TEXT,
    metadata       JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
