# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A personal expense tracking AI system that ingests bank transaction emails from Gmail and PDF bank statements, parses/categorizes them using a priority-ordered merchant mapping table, stores them in PostgreSQL with vector embeddings, and exposes querying via FastAPI, a Telegram bot, and a CLI. Natural language queries are routed either to an LLM-generated SQL agent or a pgvector semantic search.

Supported PDF formats: HDFC Credit Card, HDFC account, SBI, Axis Bank, Amex Credit Card, OneCard (Federal Bank).

## Commands

```bash
# Infrastructure
docker-compose up -d                                          # start PostgreSQL 16 + pgvector

# Running the app
python app/main.py                                            # run Gmail ingestion pipeline once
uvicorn app.main_nlp_interface:app --host 0.0.0.0 --port 8000  # start FastAPI query server
python app/telegram_bot.py                                    # start Telegram bot (polling)
python app/watcher.py                                         # watch inbox/ folder and auto-import dropped PDFs
python app/test_query_CLI.py                                  # interactive CLI query REPL

# Tests (run individually, no test runner configured)
python app/test_db.py
python app/test_embeddings.py
python app/test_ingestion.py
python app/test_pipeline.py

# Admin / DB
python app/admin/db_reset.py                                                          # truncate or drop expenses table
docker exec -i expense_postgres psql -U expense_user -d expenses_db < db/views.sql   # apply Power BI dashboard views
python app/admin/docker_reset.py                                                      # stop containers, remove volumes, recreate
Get-Content db/migrations/001_merchant_mappings.sql | docker exec -i expense_postgres psql -U expense_user -d expenses_db  # run migration

# Merchant mappings
python app/admin/manage_mappings.py quality        # data quality report
python app/admin/manage_mappings.py list           # list all mappings
python app/admin/manage_mappings.py import         # import from merchant_mappings.csv
python app/admin/manage_mappings.py apply          # bulk-apply mappings to existing DB rows
python app/admin/manage_mappings.py review         # interactive review of unknown/uncategorised rows
python app/admin/manage_mappings.py clean-existing # re-clean all existing merchant names

# SMS staging
python app/admin/manage_sms.py stats              # count staged SMS rows by status
python app/admin/manage_sms.py review             # interactive approve/reject loop
python app/admin/manage_sms.py list [--status]    # list rows by status
python app/admin/manage_sms.py approve <id>       # approve a specific row
python app/admin/manage_sms.py reject <id>        # reject a specific row

# SMS migration
Get-Content db/migrations/002_sms_staging.sql | docker exec -i expense_postgres psql -U expense_user -d expenses_db
```

## Architecture

Data flows in two directions: **ingestion** and **query**.

**Ingestion path:**
```
Gmail API → ingestion/gmail_client.py
          → parsing/transaction_parser.py   (regex: amount, merchant, date; requires score ≥ 2)
          → normalization/categorizer.py    (keyword dict → category)
          → ai/embeddings.py                (OpenAI text-embedding-3-small, 1536-dim)
          → storage/repository.py           (saves Expense row + vector to PostgreSQL)
```
Orchestrated by `pipelines/expense_pipeline.py`, triggered via `app/main.py`.

**Query path** — each interface routes differently:
```
CLI (test_query_CLI.py) → ai/query_router.py
                        ├─ numeric keywords → ai/sql_agent.py     (GPT-4.1-mini: NL → SQL)
                        │                   → ai/sql_validator.py  (blocks non-SELECT statements)
                        └─ other           → ai/semantic_search.py (pgvector cosine similarity)

FastAPI GET /query      → ai/sql_agent.py directly (validator applied; no semantic search branch)
Telegram text messages  → heuristic keyword parser in telegram_bot.py (not AI-routed)
```

**FastAPI endpoints (`app/main_nlp_interface.py`):**
- `GET /query?q=...` — NL → SQL query
- `GET /dashboard` — browser Chart.js dashboard (`app/templates/dashboard.html`)
- `GET /dashboard/data` — JSON from the 4 Power BI views
- `POST /ingest` — scan `inbox/` and ingest all PDFs; per-file status/error report
- `POST /upload` — multipart PDF upload from the dashboard (optional `password` form field); same per-file report

## Key Files

| File | Role |
|------|------|
| `app/config.py` | All env vars (`DB_*`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`) |
| `db/init.sql` | PostgreSQL schema — `expenses` + `credits` tables with pgvector index |
| `db/views.sql` | Pre-aggregated views for Power BI dashboard |
| `db/migrations/001_merchant_mappings.sql` | `merchant_mappings` table + auto-update trigger |
| `merchant_mappings.csv` | Seed file for merchant mappings — edit here, then run `import` |
| `app/admin/manage_mappings.py` | CLI for data quality, mapping management, review workflow |
| `app/parsing/parse_utils.py` | Shared `clean_merchant_name()`, `clean_vpa()`, `parse_amount()`, `parse_date()` |
| `docker-compose.yml` | PostgreSQL 16 with pgvector, volume, credentials |
| `credentials.json` | Gmail OAuth2 client secrets (not committed, user-provided) |
| `.env` | Runtime secrets (not committed) |

## Environment Variables Required

```
DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
OPENAI_API_KEY
TELEGRAM_BOT_TOKEN
```
Gmail auth also requires `credentials.json` (OAuth2) and will generate `token.json` on first run.

## Data Model

```python
Expense(
    id: UUID,
    txn_date: TIMESTAMP,
    amount: NUMERIC(12,2),
    currency: VARCHAR,       # default 'INR'
    merchant: TEXT,
    category: TEXT,
    payment_method: TEXT,
    bank_name: TEXT,
    source: TEXT,
    raw_text: TEXT,
    embedding: Vector(1536), # pgvector
    created_at: TIMESTAMP
)
```

## Query Routing Logic

Keywords that trigger **SQL Agent**: `how much`, `total`, `sum`, `spent`, `count`, `average`, `monthly`, `last month`, `this year`.
Everything else goes to **semantic search** via embedding similarity.

SQL safety: `ai/sql_validator.py` allows only `SELECT` — blocks `DELETE`, `DROP`, `INSERT`, `UPDATE`, `ALTER`, `TRUNCATE`.

## Changelog

### 2026-04-05
- Amex Credit Card PDF parser (`pdf_parser.py`) — plain-text format, year-boundary handling, skip finance/GST lines
- Merchant mapping system — `merchant_mappings` table, `MappingRepository`, `apply_mappings_to_db()`, `merchant_mappings.csv`
- `parsing/parse_utils.py` — shared `clean_merchant_name()` (13-step) and `clean_vpa()` utilities
- Data quality CLI (`admin/manage_mappings.py`): `quality`, `review`, `import`, `apply`, `clean-existing`
- Telegram commands: `/quality`, `/review`, `/listmaps`, `/applymap`, `/addmap`
- `storage/db.py` — `get_db()` context manager; all repository methods migrated away from manual `try/finally`
- `normalization/categorizer.py` — `matched` flag replaces `category == "Other"` sentinel
- `admin/manage_mappings.py` — `_NOISE` and `TABLE_MODELS` as module-level constants; filter logic de-duplicated

### 2026-04-04
- `app/watcher.py` — watchdog inbox hot-folder; processed → `inbox/processed/`, failed → `inbox/failed/`
- `db/views.sql` — 4 Power BI views: `v_monthly_spend`, `v_category_spend`, `v_top_merchants`, `v_monthly_income_vs_expense`
