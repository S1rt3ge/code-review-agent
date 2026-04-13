-- 004_add_password.sql
-- Adds hashed_password column to users for JWT-based authentication.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS hashed_password TEXT;
