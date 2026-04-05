# Roadmap

Planned features and pending verification tasks in priority order.

---

## Verification Tasks (immediate)

### V1. Apply Power BI Views Fix
`v_category_spend` was updated with a `row_id` surrogate key to fix the PBI duplicate-key error.
```powershell
Get-Content db/views.sql | docker exec -i expense_postgres psql -U expense_user -d expenses_db
```
Refresh Power BI and confirm all 4 views load without errors.

---

### V2. Test Amex PDF Parser End-to-End
```powershell
cd expense_assit_ai/app
python -m pipelines.pdf_pipeline "C:\Users\91915\Downloads\12_Feb_-_11_Mar.pdf"
```
Expected: `[PDF] Detected format: AMEX Credit Card`, transaction count in log, rows in DB with `bank_name='AMEX'`.

---

### V3. Import & Apply Merchant Mappings
```powershell
cd expense_assit_ai/app
python admin/manage_mappings.py import   # load merchant_mappings.csv → DB
python admin/manage_mappings.py apply    # bulk-correct existing rows
python admin/manage_mappings.py quality  # check remaining unknowns
```

---

### V4. Review Remaining Unknown / Uncategorised Rows
```powershell
python admin/manage_mappings.py review
```
Add inline mappings for any remaining unknowns, then re-run `apply`.

---

### V5. Verify Inbox Watcher
1. `python app/watcher.py`
2. Drop a PDF into `inbox/` — confirm `[WATCHER] Processing:` and `[WATCHER] Done` in log
3. Confirm file moves to `inbox/processed/` and new rows appear in DB

---

## Feature Backlog

### 1. Recurring Payment Detection

Analyse existing transaction history to identify merchants that charge at regular intervals.

**How it works:**
- Group expenses by merchant, compute day-intervals between consecutive transactions
- Classify intervals into bands: weekly / biweekly / monthly / quarterly / annual
- Filter out inconsistent spacing using coefficient of variation
- Return: merchant, period, average amount, last charge date, next expected date

**Integration points:**
- `ai/recurring_detector.py` — detection logic (no OpenAI calls, pure SQL + Python)
- `query_router.py` — route keywords like "recurring", "subscriptions" to detector
- `telegram_bot.py` — `/recurring` command
- `main_nlp_interface.py` — `GET /recurring` endpoint

---

### 2. Budget Tracking & Alerts

Set monthly spending limits per category and get notified when approaching or exceeding them.

**How it works:**
- New `budgets` table: `category`, `monthly_limit`, `currency`
- Budget checker compares current month's spend per category against the limit
- Alert when spend crosses 80% (warning) and 100% (exceeded)

**Integration points:**
- `storage/models.py` — new `Budget` ORM model
- `db/init.sql` — new `budgets` table
- `ai/budget_checker.py` — comparison logic
- `telegram_bot.py` — `/budget` command to view status; push alerts on ingestion
- `main_nlp_interface.py` — `GET /budget` endpoint

---

### 3. Monthly Summary Report

Auto-generate a monthly spend breakdown and send via Telegram.

**How it works:**
- Triggered by `/report` command or scheduled on 1st of each month
- Pulls from `v_monthly_spend`, `v_category_spend`, `v_top_merchants` views
- Formats as a readable Telegram message with key totals and top 5 categories

**Integration points:**
- `telegram_bot.py` — `/report [month]` command
- `ai/report_generator.py` — query views, format summary

---

### 4. Auto Expense Categorization Learning

Let the user correct a miscategorized transaction; save the correction and improve future parsing.

**How it works:**
- User flags a transaction via Telegram with the correct category
- Correction saved to a `category_overrides` table keyed by merchant
- Categorizer checks overrides before falling back to keyword dict

**Integration points:**
- `storage/models.py` — new `CategoryOverride` model
- `normalization/categorizer.py` — check overrides at lookup time
- `telegram_bot.py` — inline correction flow (e.g. reply to a transaction message)

---

### 5. Email Ingestion Scheduling

Run Gmail ingestion automatically on a schedule instead of manually.

**How it works:**
- Schedule `pipelines/expense_pipeline.py` via Windows Task Scheduler or a simple cron loop inside the process
- Configurable interval (e.g. every 6 hours)
- Log each run with count of new transactions saved

**Integration points:**
- `app/scheduler.py` — thin wrapper with `schedule` library
- `CLAUDE.md` / `INSTRUCTIONS.md` — setup guide

---

### 6. SMS Ingestion

Parse bank transaction SMS messages as an alternative ingestion source.

**How it works:**
- SMS forwarded via an Android app (e.g. SMS Forwarder) to a webhook or local endpoint
- FastAPI endpoint receives raw SMS text
- Parsed by `transaction_parser.py` (same regex pipeline as email)

**Integration points:**
- `main_nlp_interface.py` — `POST /sms` endpoint
- `ingestion/sms_parser.py` — thin adapter feeding into existing pipeline

---

## Status

| # | Item | Status |
|---|------|--------|
| V1 | Apply Power BI views fix | Done |
| V2 | Test Amex PDF parser | Pending |
| V3 | Import & apply merchant mappings | Pending |
| V4 | Review unknown rows | Pending |
| V5 | Verify inbox watcher | Done |
| 1 | Recurring Payment Detection | Pending |
| 2 | Budget Tracking & Alerts | Pending |
| 3 | Monthly Summary Report | Pending |
| 4 | Auto Categorization Learning | Pending |
| 5 | Email Ingestion Scheduling | Pending |
| 6 | SMS Ingestion | Pending |
| — | Dashboard UI (Power BI) | Done |
| — | Inbox Hot-Folder Watcher | Done |
| — | Amex Credit Card PDF Parser | Done |
| — | Merchant Mapping Table & CLI | Done |
| — | Data Quality Review Commands | Done |
| — | Merchant Name Cleaning Pipeline | Done |
