-- Add per-user agent and LLM preference columns
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS default_agents TEXT[] NOT NULL DEFAULT ARRAY['security','performance','style','logic'],
    ADD COLUMN IF NOT EXISTS lm_preference  TEXT    NOT NULL DEFAULT 'auto';
