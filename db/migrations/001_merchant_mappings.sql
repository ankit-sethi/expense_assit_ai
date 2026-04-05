-- Migration 001: merchant_mappings table
-- Run manually:
--   Get-Content db/migrations/001_merchant_mappings.sql | docker exec -i expense_postgres psql -U expense_user -d expenses_db

CREATE TABLE IF NOT EXISTS merchant_mappings (
    id           SERIAL PRIMARY KEY,
    raw_pattern  TEXT UNIQUE NOT NULL,
    clean_name   TEXT NOT NULL,
    category     TEXT NOT NULL,
    sub_category TEXT NOT NULL DEFAULT '',
    priority     INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mm_priority ON merchant_mappings(priority DESC);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_mm_updated_at ON merchant_mappings;
CREATE TRIGGER trg_mm_updated_at
    BEFORE UPDATE ON merchant_mappings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
