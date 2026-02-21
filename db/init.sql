CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE expenses (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    txn_date TIMESTAMP NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',

    merchant TEXT,
    category TEXT,
    sub_category TEXT,

    payment_method TEXT,
    bank_name TEXT,

    source TEXT,
    raw_text TEXT,

    embedding vector(1536), -- future AI magic

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_date ON expenses(txn_date);
CREATE INDEX idx_merchant ON expenses(merchant);
CREATE INDEX idx_category ON expenses(category);
