# Setup Instructions

Step-by-step guide to build the Personal AI Expense Assistant from scratch.

---

## Prerequisites

- Python 3.10+
- Docker Desktop (for PostgreSQL)
- A Google account (for Gmail ingestion)
- An OpenAI account (for embeddings and SQL agent)
- A Telegram bot token (for the Telegram interface)

---

## Step 1 — Clone the repository

```bash
git clone <repo-url>
cd expense_assit_ai
```

---

## Step 2 — Create the `.env` file

Create a `.env` file in the project root (`expense_assit_ai/`):

```env
DB_HOST=db
DB_PORT=5432
DB_USER=expense_user
DB_PASSWORD=UltraStrongPass
DB_NAME=expenses_db

OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
```

> **DB_HOST note:** Use `db` when running inside Docker Compose. When running Python scripts directly on your machine (outside Docker), `config.py` automatically falls back to `localhost` via DNS resolution — no change needed.

---

## Step 3 — Start PostgreSQL with pgvector

```bash
docker-compose up -d
```

This starts a `pgvector/pgvector:pg16` container named `expense_postgres` on port 5432.

On first start, Docker automatically runs `db/init.sql`, which creates:
- `vector` and `pgcrypto` extensions
- `expenses` table (debit transactions)
- `credits` table (credit/income transactions)
- Indexes on `txn_date`, `merchant`, `category` for both tables

Verify the DB is ready:

```bash
docker exec -it expense_postgres psql -U expense_user -d expenses_db -c "\dt"
```

Expected output: `expenses` and `credits` tables listed.

**If the DB already exists (re-setup)** and you need the `credits` table added:

```sql
docker exec -it expense_postgres psql -U expense_user -d expenses_db -c "
CREATE TABLE IF NOT EXISTS credits (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    txn_date       TIMESTAMP NOT NULL,
    amount         NUMERIC(12,2) NOT NULL,
    currency       VARCHAR(3) DEFAULT 'INR',
    merchant       TEXT,
    category       TEXT,
    sub_category   TEXT,
    payment_method TEXT,
    bank_name      TEXT,
    source         TEXT,
    raw_text       TEXT,
    embedding      vector(1536),
    created_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_credits_date     ON credits(txn_date);
CREATE INDEX IF NOT EXISTS idx_credits_merchant ON credits(merchant);
CREATE INDEX IF NOT EXISTS idx_credits_category ON credits(category);
"
```

---

## Step 4 — Install Python dependencies

```bash
cd app
pip install -r requirements.txt
```

Key packages:
- `fastapi`, `uvicorn` — API server
- `sqlalchemy`, `psycopg2-binary` — PostgreSQL ORM
- `openai` — embeddings and SQL agent
- `google-auth-oauthlib`, `google-api-python-client` — Gmail OAuth2
- `pdfplumber` — PDF table extraction
- `pikepdf` — password-protected PDF decryption
- `python-telegram-bot` — Telegram bot
- `bs4`, `python-dateutil` — HTML parsing and date normalization

---

## Step 5 — Set up Gmail API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Gmail API**.
3. Create **OAuth 2.0 credentials** (Desktop app type).
4. Download the credentials file and save it as `app/credentials.json`.

First run authenticates interactively:

```bash
cd app
python -c "from ingestion.gmail_auth import get_gmail_service; get_gmail_service()"
```

A browser window opens — log in and grant read-only Gmail access. A `token.pkl` file is saved to `app/` for future runs (no re-authentication needed unless the token expires).

> Both `credentials.json` and `token.pkl` must be in the `app/` directory. They are in `.gitignore` and are never committed.

---

## Step 6 — Verify the database connection

```bash
cd app
python test_db.py
```

Expected: connected successfully, tables accessible.

---

## Step 7 — Run the Gmail ingestion pipeline

```bash
cd app
python main.py
```

This fetches bank/transaction emails from Gmail, parses amounts, merchants, and dates, categorizes transactions, generates embeddings, and saves to the `expenses` table. Re-running is safe — duplicate emails are skipped by `message_id`.

Check results:

```bash
python test_data_quality.py
```

This prints field population rates, category distribution, and 5 sample records.

---

## Step 8 — Import PDF bank statements (optional)

Supported formats: HDFC Credit Card, HDFC Bank Account, Axis Bank, SBI.

```bash
cd app
python -m pipelines.pdf_pipeline /path/to/statement.pdf
# For password-protected PDFs:
python -m pipelines.pdf_pipeline /path/to/statement.pdf mypassword
```

- Debit transactions → `expenses` table
- Credit transactions → `credits` table
- Re-running is safe — duplicates are skipped by row hash

Debug an unrecognised PDF format:

```bash
python admin/debug_pdf_headers.py /path/to/statement.pdf
```

---

## Step 9 — Run the query CLI

```bash
cd app
python main_nlp_interface.py
```

Enter natural language queries at the prompt:

```
> How much did I spend on Amazon last month?
> Show me my top 5 merchants by spending
> Do I have any recurring subscriptions?
```

---

## Step 10 — Auto-import via Inbox Folder

Drop PDF bank statements into the `inbox/` folder and the system imports them automatically.

1. Start the watcher:
   ```bash
   cd expense_assit_ai
   python app/watcher.py
   ```
2. Drop any bank statement PDF into `inbox/`.
3. The watcher detects it, runs the PDF pipeline, and moves it to `inbox/processed/`.
4. For password-protected PDFs, place a sidecar file alongside the PDF:
   - PDF: `hdfc_statement.pdf`
   - Password file: `hdfc_statement.pdf.password` (plain text, just the password)
5. If processing fails, the file moves to `inbox/failed/` — check the watcher terminal for the error.
6. After import, click **Refresh** in Power BI Desktop to see the new data.

---

## Step 11 — Start the Telegram bot (alternative to inbox folder)

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.
2. Add `TELEGRAM_BOT_TOKEN=...` to your `.env`.
3. Start the bot:

```bash
cd app
python telegram_bot.py
```

**Text queries** — ask natural language expense questions directly in chat.

**PDF upload** — send a bank statement PDF directly in the chat:
- The bot downloads, parses, and imports it automatically.
- For password-protected PDFs, add the password as the file caption.
- The bot replies with a summary: debits saved, credits saved, skipped, failed.

---

## Step 12 — Start the FastAPI server (optional)

```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000
```

API available at `http://localhost:8000`.

---

## Admin utilities

| Script | Purpose |
|--------|---------|
| `python admin/db_reset.py` | Drop and recreate all tables (destructive) |
| `python admin/clean_bad_rows.py` | Remove rows with implausible amounts or junk merchants |
| `python admin/debug_pdf_headers.py <pdf>` | Print table headers from a PDF to debug format detection |
| `python test_data_quality.py` | Report field population rates and category breakdown |
| `python test_embeddings.py` | Verify OpenAI embedding generation |
| `python test_ingestion.py` | Test Gmail fetch without saving to DB |
| `python test_pipeline.py` | End-to-end pipeline dry run |
| `python test_query_CLI.py` | Test semantic search and SQL agent queries |

---

## Step 13 — Connect Power BI Desktop (Dashboard)

### Prerequisites

1. **Power BI Desktop** — free download from `microsoft.com/en-us/power-bi/downloads`
2. **Npgsql PostgreSQL connector** — required for Power BI to talk to PostgreSQL:
   - Download the latest `Npgsql-X.X.X.msi` from `github.com/npgsql/npgsql/releases`
   - Run the installer, restart Power BI Desktop after

### Apply the dashboard views (one-time)

```bash
docker exec -i expense_postgres psql -U expense_user -d expenses_db < db/views.sql
```

Verify:
```bash
docker exec -it expense_postgres psql -U expense_user -d expenses_db -c "\dv"
```
Expected: 4 views listed — `v_monthly_spend`, `v_category_spend`, `v_top_merchants`, `v_monthly_income_vs_expense`.

### Connect Power BI Desktop

1. Open Power BI Desktop → **Home** → **Get Data** → **PostgreSQL database**
2. Enter:
   - Server: `localhost`
   - Database: `expenses_db`
3. Select **Import** mode → click **OK**
4. In the Navigator, tick all 4 views:
   - `v_monthly_spend`
   - `v_category_spend`
   - `v_top_merchants`
   - `v_monthly_income_vs_expense`
5. Click **Load**

### Build the dashboard pages

| Page | Chart type | X / Legend | Y / Values |
|------|-----------|------------|------------|
| Monthly Trend | Clustered bar chart | `month` | `total_spent` |
| By Category | Donut chart | `category` | `total_spent` |
| Top Merchants | Bar chart (horizontal) | `merchant` | `total_spent` |
| Income vs Expenses | Clustered bar chart | `month` | `expenses` + `income` |

> **Refresh data:** Click **Home → Refresh** in Power BI Desktop whenever new transactions have been ingested.

---

## Stopping and resetting

```bash
# Stop the database container
docker-compose down

# Stop and remove all data (full reset)
docker-compose down -v
```

After a full reset, re-run `docker-compose up -d` — `init.sql` will re-create tables on fresh container start.
