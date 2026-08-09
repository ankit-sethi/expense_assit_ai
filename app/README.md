# Personal AI Expense Assistant — Application Code

This folder contains the application source. Full project documentation lives at the repository root:

- [README.md](../README.md) — features, changelog, quick start
- [INSTRUCTIONS.md](../INSTRUCTIONS.md) — setup steps
- [SYSTEM_DESIGN.md](../SYSTEM_DESIGN.md) — architecture reference
- [ROADMAP.md](../ROADMAP.md) — feature backlog and status
- [CLAUDE.md](../CLAUDE.md) — commands and development guidance

## Module layout

| Module | Role |
|--------|------|
| `ingestion/` | Gmail client, PDF parser (HDFC CC/account, SBI, Axis, Amex, OneCard), SMS parser |
| `parsing/` | Transaction field extraction, shared parse utilities |
| `normalization/` | Merchant/category cleanup |
| `storage/` | SQLAlchemy models, repositories, DB session management |
| `ai/` | SQL agent, semantic search, embeddings, query router, SQL validator |
| `pipelines/` | Email and PDF ingestion orchestration |
| `admin/` | Maintenance CLIs: merchant mappings, SMS staging, DB reset |
| `templates/` | Chart.js dashboard HTML |

## Entry points

| Command | Purpose |
|---------|---------|
| `python app/main.py` | Run Gmail ingestion pipeline once |
| `uvicorn app.main_nlp_interface:app --port 8000` | FastAPI server (`/query`, `/dashboard`, `/ingest`) |
| `python app/telegram_bot.py` | Telegram bot (polling) |
| `python app/watcher.py` | Inbox hot-folder watcher |
| `python app/test_query_CLI.py` | Interactive query REPL |
