# Personal AI Expense Assistant

An AI-powered personal assistant that automatically collects expense data from Gmail/SMS, stores it in a structured database, and allows natural-language financial queries via semantic search and SQL reasoning.

## 🚀 Features

* Gmail ingestion of bank/transaction emails
* PDF bank statement ingestion (HDFC CC, HDFC account, SBI, Axis)
* Transaction parsing & normalization pipeline (email + PDF)
* Debit/credit split — expenses and income tracked separately
* PostgreSQL + pgvector storage with PII redaction
* Embedding-based semantic search
* Natural-language → SQL analytics
* Telegram bot — query expenses and upload PDF statements
* CLI interface for ingestion and querying

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

* Budget tracking & alerts
* Auto expense categorization learning
* Dashboard UI
* Recurring payment detection

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
