-- Store GitHub commit status metadata for Review Passport merge gates.

ALTER TABLE review_passports
    ADD COLUMN IF NOT EXISTS github_gate_state TEXT,
    ADD COLUMN IF NOT EXISTS github_gate_url TEXT,
    ADD COLUMN IF NOT EXISTS github_gate_posted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_review_passports_github_gate_state
    ON review_passports(github_gate_state)
    WHERE github_gate_state IS NOT NULL;
