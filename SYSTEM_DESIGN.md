# System Design — Personal AI Expense Assistant

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Data Model](#data-model)
5. [Ingestion Layer](#ingestion-layer)
6. [Parsing Layer](#parsing-layer)
7. [Normalization Layer](#normalization-layer)
8. [Storage Layer](#storage-layer)
9. [AI / Query Layer](#ai--query-layer)
10. [Interfaces](#interfaces)
11. [Dashboard (Power BI)](#dashboard-power-bi)
12. [Infrastructure](#infrastructure)
13. [Security](#security)
14. [Error Handling & Resilience](#error-handling--resilience)
15. [Limitations & Future Work](#limitations--future-work)

---

## Overview

A personal finance AI system that automatically collects bank transaction data from two sources — Gmail transaction alerts and PDF bank statements — parses and normalises it, stores it in a vector-enabled PostgreSQL database, and exposes intelligent querying via natural language through three interfaces: a FastAPI REST server, a Telegram bot, and an interactive CLI. A background inbox watcher auto-imports PDFs dropped into a local folder. A Power BI Desktop dashboard visualises the data.

---

## Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│                                                                 │
│  Gmail API          PDF (Telegram)      PDF (inbox/)            │
│  (bank alerts)      (file upload)       (drop folder)           │
└──────┬──────────────────┬───────────────────┬───────────────────┘
       │                  │                   │
       ▼                  ▼                   ▼
┌──────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                          │
│  gmail_client.py          pdf_parser.py        watcher.py   │
│  - OAuth2 Gmail API       - pikepdf decrypt    - watchdog   │
│  - filter bank emails     - pdfplumber tables  - auto-trigger│
│  - extract body text      - bank format detect              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      PARSING LAYER                           │
│  transaction_parser.py (email)   pdf_parser.py (PDF rows)   │
│  - regex: amount, merchant,      - per-bank column maps     │
│    date, payment method          - HDFC CC special format   │
│  - score ≥ 2 to pass             - debit / credit split     │
│  - VPA / UPI pattern matching    - PII redaction            │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   NORMALIZATION LAYER                        │
│  categorizer.py                                              │
│  - 40+ merchant → (category, sub_category) mappings         │
│  - case-insensitive substring matching                       │
│  - precomputed lowercase key dict (no per-call overhead)     │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   AI ENRICHMENT                              │
│  embeddings.py                                               │
│  - build_embedding_text(): merchant + category +             │
│    payment_method + raw_text                                 │
│  - create_embedding(): OpenAI text-embedding-3-small         │
│    1536-dimensional vector                                   │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     STORAGE LAYER                            │
│  PostgreSQL 16 + pgvector (Docker)                           │
│  ┌──────────────┐        ┌──────────────┐                   │
│  │  expenses    │        │   credits    │                   │
│  │  (debits)    │        │  (income)    │                   │
│  └──────────────┘        └──────────────┘                   │
│  repository.py — BaseRepository[T] (generic CRUD + dedup)   │
└──────────────────────────┬───────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
┌─────────────────────┐   ┌────────────────────────────────┐
│    QUERY LAYER      │   │        DASHBOARD               │
│  query_router.py    │   │  db/views.sql (4 views)        │
│  ├─ recurring kws   │   │  Power BI Desktop              │
│  ├─ numeric kws     │   │  Direct PostgreSQL connection  │
│  │  → sql_agent.py  │   └────────────────────────────────┘
│  │  → sql_validator │
│  └─ other           │
│     → semantic_     │
│       search.py     │
└──────────┬──────────┘
           │
   ┌───────┴────────┐
   ▼                ▼
FastAPI          Telegram
REST API         Bot
/query           /start
/recurring       /recurring
                 PDF upload
                 Text queries
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.10+ | All backend code |
| Web framework | FastAPI + Uvicorn | REST API server |
| Database | PostgreSQL 16 | Structured transaction storage |
| Vector extension | pgvector | Cosine similarity search on embeddings |
| ORM | SQLAlchemy | Database models and query abstraction |
| DB driver | psycopg2-binary | PostgreSQL ↔ Python connection |
| Containerisation | Docker + Docker Compose | PostgreSQL with pgvector, volume persistence |
| Gmail access | Google OAuth2 + Gmail API | Email ingestion (`google-api-python-client`) |
| PDF parsing | pdfplumber | Table extraction from bank statements |
| PDF decryption | pikepdf | Password-protected PDF handling |
| HTML parsing | BeautifulSoup4 | Extract text from HTML email bodies |
| Date parsing | python-dateutil | Flexible date string normalisation |
| AI embeddings | OpenAI text-embedding-3-small | 1536-dim vectors for semantic search |
| AI SQL agent | GPT-4.1-mini | Natural language → SQL generation |
| Telegram bot | python-telegram-bot | Messaging interface |
| File watcher | watchdog | OS-level file system event monitoring |
| Dashboard | Power BI Desktop | Visualisation (connects via psqlODBC) |
| Config | python-dotenv | `.env` → environment variable loading |

---

## Data Model

### `expenses` table — debit transactions

```
id             UUID         Primary key (gen_random_uuid)
txn_date       TIMESTAMP    Transaction date (NOT NULL)
amount         NUMERIC(12,2) Transaction amount in INR (NOT NULL)
currency       VARCHAR(3)   Default 'INR'
merchant       TEXT         Merchant name (indexed)
category       TEXT         Primary category (indexed) e.g. Food, Shopping
sub_category   TEXT         Sub-category e.g. Food Delivery, Ride Hailing
payment_method TEXT         UPI / NEFT / IMPS / CREDIT CARD / DEBIT CARD
bank_name      TEXT         HDFC / SBI / Axis / ICICI / Kotak
source         TEXT         message_id (Gmail) or pdf:{filename}:{hash} (PDF)
raw_text       TEXT         Original text after PII redaction
embedding      vector(1536) OpenAI embedding for semantic search
created_at     TIMESTAMP    Row insert time (server default)
```

**Indexes:** `idx_date (txn_date)`, `idx_merchant (merchant)`, `idx_category (category)`

### `credits` table — income / credit transactions

Identical schema to `expenses`. Populated by PDF pipeline when `txn_type = "credit"`.

### Deduplication

- **Gmail:** deduplicated by `source = message_id` via `BaseRepository.exists()`
- **PDF:** deduplicated by `source = pdf:{filename}:{sha256_hash[:16]}` of the raw row text

---

## Ingestion Layer

### Gmail Ingestion (`ingestion/gmail_client.py`, `gmail_auth.py`)

**Authentication:**
- OAuth2 via `InstalledAppFlow` (Desktop app credentials)
- Token persisted to `token.pkl` (pickle) — refreshed automatically on expiry
- Scopes: `gmail.readonly` only

**Email fetching:**
- Gmail search query filters to primary category, last 30 days, from known bank sender addresses (HDFC, SBI, Axis)
- Up to 100 messages per run (configurable)
- HTML bodies stripped via BeautifulSoup; plain text bodies used directly

**Transaction filter (`is_transaction_email`):**
- Requires ≥ 2 of: `debited`, `credited`, `upi txn`, `rs.`, `inr`, `a/c`, `account`
- Non-transaction emails (newsletters, OTPs) are discarded before parsing

**Bank name resolution:**
- Extracted from sender email domain (`hdfcbank` → `HDFC`, `sbi.co.in` → `SBI`, etc.)

**Output per message:**
```python
{
  "source": "gmail",
  "message_id": str,     # Gmail message ID (dedup key)
  "timestamp": int,      # internalDate in ms (fallback for date parsing)
  "raw_text": str,       # decoded and HTML-stripped body
  "bank_name": str,
}
```

### PDF Ingestion (`ingestion/pdf_parser.py`)

**Supported formats:**
- HDFC Credit Card — single merged cell per row; regex-based row parser
- HDFC Bank Account — standard multi-column table
- Axis Bank — standard multi-column table
- SBI — standard multi-column table

**Bank detection:**
1. Check first table header cell for HDFC CC keywords (`date & time`, `transaction`, `description`, `amount`)
2. Otherwise match header columns against `BANK_SIGNATURES` dict (sets of required column names)

**Column mapping (`COLUMN_MAP`):**
```
axis: date=0, description=1, debit=4, credit=5
hdfc: date=0, description=1, debit=3, credit=4
sbi:  date=0, description=2, debit=4, credit=5
```

**Password-protected PDFs:**
- Decrypted in-memory via `pikepdf.open(password=...)` → written to `BytesIO` buffer
- No temp files written to disk

**PII redaction (before `raw_text` storage):**
```
Card numbers:    [REDACTED_CARD]
Account numbers: [REDACTED_ACCT]
Email addresses: [REDACTED_EMAIL]
PIN codes:       [REDACTED_PIN]
Reference nos:   Ref#[REDACTED]
```

**Dedup key:** SHA-256 of raw row text, first 16 hex chars → `pdf:{filename}:{hash}`

**Output per row:**
```python
{
  "txn_date": datetime,
  "amount": float,
  "merchant": str,
  "payment_method": str,
  "bank_name": str,
  "source": str,          # dedup key
  "raw_text": str,        # PII-redacted
  "txn_type": "debit" | "credit",
}
```

---

## Parsing Layer

### Email Parser (`parsing/transaction_parser.py`)

**Scoring system** — a message must score ≥ 2 to be accepted:
- +1 if amount pattern matches (`INR` or `Rs.` followed by number)
- +1 if merchant pattern or VPA pattern matches
- +1 if `debited` appears in text

**Extracted fields:**

| Field | Regex / Logic |
|-------|--------------|
| `amount` | `(?:INR\|Rs\.?)\s?([0-9,]+(?:\.[0-9]{1,2})?)` — commas stripped; rejected if > ₹1 crore |
| `merchant` | `(?:paid to\|payment to\|at\|for\|name\|to)\s+([A-Za-z0-9 &.\-]+)` |
| `merchant` (UPI) | `VPA\s+([A-Za-z0-9.\-_]+@[A-Za-z0-9.\-_]+)` — preferred over text match |
| `payment_method` | `UPI\|NEFT\|IMPS\|RTGS\|credit card\|debit card\|net banking` |
| `txn_date` | Date patterns in body text; falls back to email `internalDate` timestamp |

**Merchant validation:**
- Min 3 characters
- Not a common stopword (`the`, `a`, `an`, `your`, etc.)
- Capped at 50 characters

### Shared Utilities (`parsing/parse_utils.py`)

- `MAX_AMOUNT = 10_000_000` (₹1 crore) — upper bound for plausible amounts
- `parse_amount(val)` — strips commas, validates range
- `parse_date(val)` — tries 6 date formats: `DD/MM/YYYY`, `DD-MM-YYYY`, `DD/MM/YY`, `DD-MM-YY`, `DD Month YYYY`, `DD Mon YYYY`

---

## Normalization Layer

### Categorizer (`normalization/categorizer.py`)

**Merchant → Category mapping (40+ entries):**

| Category | Sub-categories | Example merchants |
|----------|---------------|-------------------|
| Shopping | Online Shopping, Fashion, Beauty | Amazon, Flipkart, Myntra, Nykaa |
| Food | Food Delivery, Grocery Delivery | Swiggy, Zomato, Blinkit, BigBasket |
| Transport | Ride Hailing, Bus, Train, Flight | Uber, Ola, IRCTC, IndiGo |
| Entertainment | Streaming, Events | Netflix, Spotify, BookMyShow |
| Bills | Bank, Telecom, Electricity | Jio, Airtel, BESCOM |
| Finance | UPI, Wallet | PhonePe, GPay, Paytm |
| Health | Pharmacy, Consultation | Apollo, 1mg, Practo |
| Travel | Booking | MakeMyTrip, Goibibo |
| Other | — | Default fallback |

**Matching strategy:**
- Case-insensitive substring match (merchant field contains keyword)
- Keys precomputed as lowercase at import time — no per-call `.lower()` overhead
- First match wins; falls back to `("Other", "")`

---

## Storage Layer

### Repository Pattern (`storage/repository.py`)

```
BaseRepository[T]              Generic base — model type injected
├── exists(source_id) → bool   Dedup check by source field
└── save(txn: dict)            Insert row; rolls back on error

ExpenseRepository              BaseRepository[Expense]
CreditRepository               BaseRepository[Credit]
```

All methods open and close a `SessionLocal` session per call with `try/finally` to prevent session leaks.

### Database Connection (`storage/db.py`)

- SQLAlchemy engine with connection pool: `pool_size=10`, `max_overflow=20`
- `SessionLocal` — bound sessionmaker
- `Base` — declarative base for ORM models

---

## AI / Query Layer

### Embedding Generation (`ai/embeddings.py`)

**Text construction for embedding:**
```
"{merchant} {category} {payment_method} {raw_text}"
```
Combining structured fields with raw text improves semantic search relevance.

**Model:** `text-embedding-3-small` (OpenAI) — 1536 dimensions

### Semantic Search (`ai/semantic_search.py`)

- Generates embedding for user query
- Runs pgvector cosine distance query (`<->` operator)
- Returns top-5 results: `merchant`, `amount`, `txn_date`, `distance`
- Only searches rows where `embedding IS NOT NULL`

### SQL Agent (`ai/sql_agent.py`)

- **Model:** `gpt-4.1-mini`, `temperature=0`
- System prompt includes today's date and schema (table name + column names)
- Returns only `SELECT` statements
- `clean_sql()` strips markdown code fences (` ```sql ... ``` `)
- Results returned as raw tuples from `fetchall()`

### SQL Validator (`ai/sql_validator.py`)

Blocks any query containing: `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`
Also requires query to start with `SELECT`.

### Query Router (`ai/query_router.py`)

Three-branch routing on lowercased query:

```
1. Recurring keywords → recurring_detector.detect_recurring()
   Keywords: "recurring", "subscription", "subscriptions",
             "regular payments", "every month", "repeat", "repeating"

2. Numeric keywords → sql_agent.ask()
   Keywords: "how much", "total", "sum", "spent", "count", "average",
             "monthly", "last month", "this year", "more than", "less than",
             "above", "below", "highest", "lowest", "show me", "list", "find",
             "transactions", "yesterday", "today", "last week", "this month", ...

3. Everything else → semantic_search.search_similar()
```

---

## Interfaces

### 1. FastAPI REST Server (`app/main_nlp_interface.py`)

Run: `uvicorn app.main_nlp_interface:app --host 0.0.0.0 --port 8000`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query?q=...` | GET | Natural language query — routes via query_router |
| `/recurring` | GET | Returns list of detected recurring payments |

**Response format `/query`:**
```json
{
  "sql": "SELECT ...",
  "result": [[...], [...]]
}
```

### 2. Telegram Bot (`app/telegram_bot.py`)

Run: `python app/telegram_bot.py`

| Trigger | Handler | Description |
|---------|---------|-------------|
| `/start` | `start()` | Help message listing commands and examples |
| `/recurring` | `handle_recurring()` | Formatted list of recurring payments |
| Text message | `handle_message()` | Heuristic query parser → sum with filters |
| PDF document | `handle_pdf()` | Download → `run_pdf_pipeline()` → summary reply |

**Text query heuristics in Telegram** (`interpret_query`):
- Last word → merchant filter
- `today` / `yesterday` / `week` / `month` → date range filter
- `food`, `shopping`, `transport`, `travel` → category filter
- `upi` → payment method filter
- Returns `SUM(amount)` matching filters

**PDF via Telegram:**
- Caption used as password for password-protected PDFs
- Temp file written, pipeline run, temp file deleted in `finally` block
- Summary sent back: debits saved, credits saved, skipped, failed

### 3. CLI (`app/main_nlp_interface.py` run directly / `test_query_CLI.py`)

```
python app/test_query_CLI.py
> How much did I spend on Swiggy?   → SQL agent
> Show me payments similar to Uber   → semantic search
> Do I have recurring subscriptions? → recurring detector
> exit
```

### 4. Inbox Watcher (`app/watcher.py`)

Run: `python app/watcher.py`

**Folder structure:**
```
inbox/
├── (drop PDFs here)
├── processed/    ← moved here on success
└── failed/       ← moved here on error
```

**Flow:**
1. `watchdog.Observer` monitors `inbox/` for `on_created` filesystem events
2. 2-second delay after detection (ensures file fully written)
3. Checks for optional `{filename}.pdf.password` sidecar for encrypted PDFs
4. Runs `run_pdf_pipeline(path, password)`
5. Moves file to `processed/` or `failed/`
6. Continues watching — a single failure does not stop the watcher

**Password-protected PDF workflow:**
```
inbox/
├── hdfc_april.pdf
└── hdfc_april.pdf.password     ← contains password as plain text
```

---

## Dashboard (Power BI)

### Connection

Power BI Desktop connects directly to PostgreSQL via psqlODBC driver:
- Host: `localhost`, Port: `5432`, Database: `expenses_db`
- Imports 4 pre-aggregated views (Import mode)
- Refreshed manually: **Home → Refresh**

### Views (`db/views.sql`)

| View | Query logic | Dashboard page |
|------|------------|----------------|
| `v_monthly_spend` | `SUM(amount) GROUP BY DATE_TRUNC('month', txn_date)` | Monthly Trend bar chart |
| `v_category_spend` | `SUM(amount) GROUP BY COALESCE(category, 'Other')` | Spend by Category donut |
| `v_top_merchants` | `SUM(amount) GROUP BY merchant ORDER BY total DESC LIMIT 20` | Top Merchants bar chart |
| `v_monthly_income_vs_expense` | FULL OUTER JOIN of monthly expenses + credits | Income vs Expenses clustered bar |

Views are created on fresh DB start via `\i views.sql` in `init.sql`.
Apply to existing DB: `Get-Content db/views.sql | docker exec -i expense_postgres psql -U expense_user -d expenses_db`

---

## Infrastructure

### Docker Compose (`docker-compose.yml`)

```
service: postgres
  image:     pgvector/pgvector:pg16
  container: expense_postgres
  port:      5432:5432
  env:       POSTGRES_USER / PASSWORD / DB (hardcoded)
  volume:    postgres_data (named, persistent)
  init:      ./db/init.sql → /docker-entrypoint-initdb.d/init.sql
             ./db/views.sql → /docker-entrypoint-initdb.d/views.sql
  restart:   always
```

### DB Initialisation (`db/init.sql`)

On first container start:
1. Creates `vector` and `pgcrypto` extensions
2. Creates `expenses` table + 3 indexes
3. Creates `credits` table + 3 indexes
4. Runs `views.sql` — creates 4 Power BI views

### Environment Variables (`.env`)

```
DB_HOST=localhost        # use 'db' only inside Docker containers
DB_PORT=5432
DB_USER=expense_user
DB_PASSWORD=UltraStrongPass
DB_NAME=expenses_db
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
```

`config.py` auto-resolves `DB_HOST=db` → `localhost` when DNS fails (for host-machine scripts), but `localhost` is the correct value when running outside Docker.

---

## Security

| Concern | Mitigation |
|---------|-----------|
| SQL injection | `sql_validator.py` blocks all non-SELECT statements; parameterised queries via SQLAlchemy `text()` |
| Sensitive data in DB | PII redacted from `raw_text` before storage (card numbers, account numbers, emails, PINs) |
| Gmail credentials | `credentials.json` and `token.pkl` in `.gitignore`, never committed |
| Secrets | `.env` in `.gitignore`; no secrets hardcoded in source |
| Gmail access scope | `gmail.readonly` only — no send/modify permissions |
| PDF passwords | Sidecar `.password` files in `.gitignore` (`inbox/*.password`) |
| DB credentials | Not exposed in API responses; connection string only in `config.py` |

---

## Error Handling & Resilience

| Component | Strategy |
|-----------|---------|
| Gmail pipeline | Per-email `try/except`; one bad email doesn't abort the run; counts saved/skipped/failed |
| PDF pipeline | Per-row `try/except`; one bad row doesn't abort; counts reported |
| Inbox watcher | Per-file `try/except`; failed files moved to `inbox/failed/`; watcher keeps running |
| DB session | `try/finally` with `db.close()` in every repository method — no session leaks |
| DB save | `db.rollback()` on exception before re-raise |
| SQL agent | `sql_validator.py` as safety gate before any query execution |
| Telegram PDF | `finally: os.unlink(tmp_path)` — temp file always cleaned up |
| Config | `_resolve_db_host()` falls back to `localhost` on DNS failure |

---

## Limitations & Future Work

### Current Limitations

| Area | Limitation |
|------|-----------|
| Gmail query | Hardcoded to 3 bank sender addresses; other banks not fetched |
| Email parser | Regex-based; sensitive to email format changes by banks |
| Categorizer | Static keyword dict; new merchants default to "Other" until manually added |
| SQL agent | Schema prompt only includes `expenses` table — `credits` not queryable via NL |
| Telegram text queries | Heuristic parser (not AI-powered); limited query understanding |
| PDF formats | Only HDFC CC, HDFC Account, Axis, SBI supported |
| Embeddings | Not generated for PDF rows where `raw_text` is sparse — semantic search quality varies |
| Power BI refresh | Manual — no scheduled refresh or real-time push |

### Roadmap

| # | Feature | Notes |
|---|---------|-------|
| 1 | Recurring payment detection | Interval analysis on expenses — planned, design complete |
| 2 | Budget tracking & alerts | New `budgets` table; Telegram push alerts on ingestion |
| 3 | Auto categorization learning | User corrections via Telegram → `category_overrides` table |
| 4 | Dashboard (Power BI) | Views created; Power BI connection documented |
