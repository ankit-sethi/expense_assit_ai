# Roadmap

Planned features in priority order.

---

## 1. Recurring Payment Detection

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

## 2. Budget Tracking & Alerts

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

## 3. Auto Expense Categorization Learning

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

## 4. Dashboard UI (Power BI)

Visual dashboard via **Power BI Desktop** (free) connected directly to PostgreSQL — no frontend code needed.

**How it works:**
- 4 PostgreSQL views pre-aggregate data for each dashboard page
- Power BI Desktop connects to `localhost:5432 / expenses_db` and imports the views
- Charts are built inside Power BI; data refreshed on demand

**Dashboard pages:**
- Monthly Spend Trend — bar/line chart of total spend per month
- Spend by Category — donut chart (Food, Shopping, Transport, etc.)
- Top Merchants — horizontal bar chart of highest-spend merchants
- Income vs Expenses — clustered bar comparing credits vs debits per month

**Integration points:**
- `db/views.sql` _(new)_ — 4 pre-aggregated views
- `db/init.sql` — includes views.sql on fresh DB start
- `INSTRUCTIONS.md` Step 12 — Npgsql connector + Power BI connection guide

---

## Status

| # | Feature | Status |
|---|---------|--------|
| 1 | Recurring Payment Detection | Pending |
| 2 | Budget Tracking & Alerts | Pending |
| 3 | Auto Categorization Learning | Pending |
| 4 | Dashboard UI (Power BI) | In Progress |
