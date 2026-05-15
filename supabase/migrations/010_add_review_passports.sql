-- Add deterministic Review Passport storage.

CREATE TABLE IF NOT EXISTS review_passports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    spec_source_type TEXT NOT NULL,
    spec_source_ref TEXT,
    spec_input TEXT,
    spec_digest TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence_score INTEGER NOT NULL DEFAULT 0,
    coverage_summary JSONB NOT NULL DEFAULT '[]'::jsonb,
    anti_slop_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    qa_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_review_passports_review_id UNIQUE (review_id),
    CONSTRAINT ck_review_passports_mode CHECK (mode IN ('spec_evidence', 'anti_ai_slop', 'combined')),
    CONSTRAINT ck_review_passports_spec_source_type CHECK (spec_source_type IN ('manual', 'local_demo', 'pr_body', 'github_issue')),
    CONSTRAINT ck_review_passports_verdict CHECK (verdict IN ('READY', 'READY_WITH_RISKS', 'BLOCKED')),
    CONSTRAINT ck_review_passports_confidence_score CHECK (confidence_score >= 0 AND confidence_score <= 100)
);

CREATE INDEX IF NOT EXISTS review_passports_user_id_idx
    ON review_passports (user_id);

CREATE INDEX IF NOT EXISTS review_passports_review_id_idx
    ON review_passports (review_id);

CREATE INDEX IF NOT EXISTS review_passports_verdict_idx
    ON review_passports (verdict);

CREATE TABLE IF NOT EXISTS review_input_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    input_type TEXT NOT NULL,
    content_digest TEXT NOT NULL,
    changed_files JSONB NOT NULL DEFAULT '[]'::jsonb,
    added_lines JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_review_input_snapshots_review_type UNIQUE (review_id, input_type),
    CONSTRAINT ck_review_input_snapshots_input_type CHECK (input_type IN ('diff'))
);

CREATE INDEX IF NOT EXISTS review_input_snapshots_review_id_idx
    ON review_input_snapshots (review_id);

CREATE INDEX IF NOT EXISTS review_input_snapshots_user_id_idx
    ON review_input_snapshots (user_id);

ALTER TABLE review_passports ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_input_snapshots ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'review_passports' AND policyname = 'tenant_review_passports_self') THEN
        CREATE POLICY tenant_review_passports_self ON review_passports
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'review_input_snapshots' AND policyname = 'tenant_review_input_snapshots_self') THEN
        CREATE POLICY tenant_review_input_snapshots_self ON review_input_snapshots
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    END IF;
END
$$;
