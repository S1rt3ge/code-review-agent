-- Store GitHub comment metadata for Review Passport PR comments.

ALTER TABLE review_passports
    ADD COLUMN IF NOT EXISTS github_comment_id BIGINT,
    ADD COLUMN IF NOT EXISTS github_comment_url TEXT,
    ADD COLUMN IF NOT EXISTS github_comment_posted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_review_passports_github_comment_id
    ON review_passports(github_comment_id)
    WHERE github_comment_id IS NOT NULL;
