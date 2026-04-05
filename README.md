# Personal AI Expense Assistant

An AI-powered personal assistant that automatically collects expense data from Gmail/SMS, stores it in a structured database, and allows natural-language financial queries via semantic search and SQL reasoning.

## 🚀 Features

* Gmail ingestion of bank/transaction emails
* PDF bank statement ingestion (HDFC CC, HDFC account, SBI, Axis, Amex Credit Card)
* Transaction parsing & normalization pipeline (email + PDF)
* Debit/credit split — expenses and income tracked separately
* PostgreSQL + pgvector storage with PII redaction
* Embedding-based semantic search
* Natural-language → SQL analytics
* Telegram bot — query expenses, upload PDFs, manage merchant mappings
* Inbox hot-folder — drop a PDF into `inbox/` and it auto-imports
* Power BI dashboard — 4 pre-aggregated PostgreSQL views
* CLI interface for ingestion, querying, and data quality management
* Merchant mapping table — user-managed canonical names and categories with priority ordering

---

## 🏗 Architecture

```
Email/SMS → Ingestion → Parsing → Normalization → Storage → AI Query Layer → CLI/Bot
```

### Core modules

* `ingestion/` — data collection (Gmail/SMS)
* `parsing/` — extract transaction fields
* `normalization/` — merchant/category cleanup
* `storage/` — SQLAlchemy models & DB access
* `ai/`

  * `sql_agent.py` — NL → SQL analytics
  * `embeddings.py` — vector creation utilities
  * `semantic_search.py` — pgvector similarity search
  * `query_router.py` — routes user queries
* `pipelines/` — orchestrates ingestion flow
* `admin/` — maintenance scripts (rebuild embeddings, reset DB)

---

## 🧠 Example Queries

```
How much did I spend on Amazon last month?
Show payments similar to Uber rides
Do I have recurring subscriptions?
```

---

## 🛠 Tech Stack

* Python 3.10+
* PostgreSQL
* pgvector
* SQLAlchemy
* Gmail API
* OpenAI embeddings
* Docker (recommended)

---

## 🔐 Security

Secrets are **never stored in the repo**.

Use `.env` locally and see `.env.example` for required variables.

---

## ▶️ Quick Start

See **INSTRUCTIONS.md** for full setup steps.

---

## 📋 Changelog

### 2026-04-02

**Ingestion & Parsing**
- Fixed `is_transaction_email` scoping bug; filter now applies to all emails (plain-text + HTML)
- Bank name extracted from sender email domain and passed through the pipeline
- Amount regex now strips commas; implausible amounts (> ₹1 crore) are rejected
- Merchant regex extended to match UPI `to`, `paid to`, `payment to`, and VPA patterns
- Merchant stopword filter added (rejects single common words like "the"); capped at 50 chars
- `payment_method` extracted from email body (UPI/NEFT/IMPS/RTGS/Credit Card/Debit Card)
- Transaction date now parsed from email body text with email timestamp as fallback

**Normalization**
- Categorizer expanded from 12 to 40+ merchants with case-insensitive partial matching
- `sub_category` now populated (e.g. Food → Food Delivery, Transport → Ride Hailing)

**Pipeline**
- Fixed incorrect `parser.parse()` call (was passing string, now passes full dict)
- Null check added before normalization to prevent crashes on failed parses
- Deduplication by `message_id` — re-runs won't insert duplicate records
- Per-transaction `try/except` so one bad email doesn't abort the full run
- Replaced all `print` statements with structured `logging`; pipeline reports saved/skipped/failed counts

**Storage**
- Fixed DB session leak in `repository.py` (added `try/finally` with `db.close()`)
- Added `exists()` method for dedup checks
- Added `sub_category` column to SQLAlchemy ORM model

**Query Routing**
- Extended SQL agent keyword list to include `more than`, `less than`, `above`, `below`, `show me`, `list`, `find`, `highest`, `lowest`, and date terms — fixing misrouting of numeric/filter queries to semantic search

**Admin**
- Added `admin/clean_bad_rows.py` — interactive script to identify and delete malformed expense records
- Added `test_data_quality.py` — reports field population rates, category/payment breakdown, and sample records
- Fixed `gmail_auth.py` to resolve `credentials.json` and `token.pkl` relative to `app/` directory regardless of working directory

### 2026-04-05

**Amex Credit Card PDF Ingestion**
- `ingestion/pdf_parser.py` now detects and parses Amex statements (plain text, no PDF tables)
- Transaction line format: `February 13   AMAZON   Mumbai   640.00`
- Strips trailing foreign-currency amounts and PDF tilde artifacts from descriptions
- Year-boundary handling for Dec–Jan spanning statements
- Skips finance charges, GST, and installment breakdown lines automatically
- `debug_pdf_headers.py` extended to dump raw page text for PDFs with no tables

**Merchant Mapping System**
- New `merchant_mappings` PostgreSQL table (see `db/migrations/001_merchant_mappings.sql`)
- Priority-ordered substring matching — DB mappings checked before hardcoded fallback
- `MappingRepository` with `get_all_sorted()`, `upsert()`, `delete_by_pattern()`
- `apply_mappings_to_db()` bulk-retroactive correction across `expenses` and `credits` tables
- `merchant_mappings.csv` — seed file with 40+ mappings; `python admin/manage_mappings.py import`

**Merchant Name Cleaning**
- New `parsing/parse_utils.py` — shared `clean_merchant_name()` (13-step pipeline):
  strips EMI prefix, asterisk separators, trailing ref numbers, city suffixes (30+ cities),
  IN+CITY concatenated patterns, legal suffixes; rejects sentence fragments and Ref# lines
- New `clean_vpa()` — maps UPI VPA handles to readable names or "UPI Transfer"
- `transaction_parser.py` updated to use shared utilities

**Data Quality CLI & Telegram Commands**
- `admin/manage_mappings.py`: `quality`, `list`, `add`, `delete`, `apply`, `clean-existing`, `import`, `review`
- `review` command: interactive loop showing raw_text for unknown/uncategorised rows; inline add derives pattern from raw_text automatically
- Telegram: `/quality`, `/review`, `/listmaps`, `/applymap`, `/addmap` (guided 4-step conversation)

### 2026-04-04

**Inbox Hot-Folder (auto-import)**
- New `app/watcher.py` — watchdog-based filesystem monitor watches `inbox/` for new PDFs
- Successful imports moved to `inbox/processed/`; failures moved to `inbox/failed/`
- Password-protected PDFs: place a `filename.pdf.password` sidecar file alongside the PDF
- Run: `python app/watcher.py` from the project root

**Power BI Dashboard**
- New `db/views.sql` — 4 pre-aggregated PostgreSQL views: `v_monthly_spend`, `v_category_spend`, `v_top_merchants`, `v_monthly_income_vs_expense`
- Views auto-applied on fresh Docker container start via `db/init.sql`
- Connect Power BI Desktop to `localhost:5432 / expenses_db` using psqlODBC or Npgsql driver
- See `INSTRUCTIONS.md` Step 13 for full dashboard setup

**Documentation**
- Added `ROADMAP.md` — prioritised feature backlog
- Added `SYSTEM_DESIGN.md` — full architecture reference with ASCII diagram, data model, all layers

### 2026-04-02 (continued)

**PDF Bank Statement Ingestion**
- New `ingestion/pdf_parser.py` — parses HDFC Credit Card, HDFC account, SBI, and Axis Bank statement PDFs
- Handles password-protected PDFs via `pikepdf`; no temp files written to disk
- Debit transactions → `expenses` table; credit transactions → new `credits` table
- PII redaction applied to `raw_text` before storage (card numbers, emails, account numbers)
- New `pipelines/pdf_pipeline.py` — orchestrates PDF ingestion with dedup, categorization, and embeddings
- Telegram bot now accepts PDF uploads; password can be sent as file caption
- CLI usage: `python -m pipelines.pdf_pipeline /path/to/statement.pdf [password]`
- Added `admin/debug_pdf_headers.py` — inspects raw table headers from any PDF for format debugging

**Code Quality**
- Shared `parsing/parse_utils.py` — `MAX_AMOUNT`, `parse_amount`, `parse_date` used by both email and PDF parsers
- `ExpenseRepository` and `CreditRepository` unified under generic `BaseRepository[T]`
- `logging.basicConfig()` removed from module scope in both pipelines
- Categorizer match keys precomputed at import time (no per-call `.lower()` overhead)
- `config.py` auto-resolves `DB_HOST=db` to `localhost` when running outside Docker

---

## 📌 Future Roadmap

* Recurring payment detection
* Budget tracking & alerts
* Auto expense categorization learning

---

## 👤 Author

Built as a personal AI systems project demonstrating:

* data pipelines
* AI-assisted querying
* vector search integration
* backend architecture design

---

## ⭐ If you like this project

Give it a star and feel free to fork!
