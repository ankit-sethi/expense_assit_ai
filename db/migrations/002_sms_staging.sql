-- SMS Staging table — holds incoming SMS transactions pending review
-- Apply: Get-Content db/migrations/002_sms_staging.sql | docker exec -i expense_postgres psql -U expense_user -d expenses_db

CREATE TABLE IF NOT EXISTS sms_staging (
    id              SERIAL PRIMARY KEY,
    raw_sms         TEXT          NOT NULL,
    sender          TEXT,
    received_at     TIMESTAMP,

    -- Parsed fields (NULL if parser could not extract)
    parsed_amount   NUMERIC(12,2),
    parsed_merchant TEXT,
    parsed_date     DATE,
    parsed_bank     TEXT,
    txn_type        TEXT,                              -- 'debit' | 'credit' | NULL

    -- Dedup / lifecycle
    source          TEXT UNIQUE,                       -- sha256(body+sender+date) — prevents double-staging
    status          TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | duplicate
    duplicate_of    TEXT,                              -- source key of matched expense/credit row

    -- Set after approval
    expense_id      UUID REFERENCES expenses(id) ON DELETE SET NULL,
    credit_id       UUID REFERENCES credits(id)  ON DELETE SET NULL,

    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sms_staging_status   ON sms_staging (status);
CREATE INDEX IF NOT EXISTS idx_sms_staging_received ON sms_staging (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_sms_staging_bank     ON sms_staging (parsed_bank);
