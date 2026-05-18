-- Allow Review Passport records generated directly from Review DNA.

ALTER TABLE review_passports
    DROP CONSTRAINT IF EXISTS ck_review_passports_spec_source_type;

ALTER TABLE review_passports
    ADD CONSTRAINT ck_review_passports_spec_source_type
    CHECK (spec_source_type IN ('manual', 'local_demo', 'pr_body', 'github_issue', 'review_dna'));
