# Personal AI Expense Assistant

An AI-powered personal assistant that automatically collects expense data from Gmail/SMS, stores it in a structured database, and allows natural-language financial queries via semantic search and SQL reasoning.

## 🚀 Features

* Gmail ingestion of bank/transaction emails
* Transaction parsing & normalization pipeline
* PostgreSQL + pgvector storage
* Embedding-based semantic search
* Natural-language → SQL analytics
* Modular ingestion-layer architecture
* CLI interface for querying (Telegram-ready design)

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

## 📌 Future Roadmap

* Telegram / WhatsApp bot interface (Pending tweaks due to result mismatch)
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
