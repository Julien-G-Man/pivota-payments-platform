# Pivota

A fintech backend for traders to track money in/out via MTN Mobile Money, get AI-powered spending insights, view real-time dashboards, and receive automated monthly financial reports.

---

## Features

- **MoMo Ingestion** — Webhook + polling-based transaction ingestion from MTN Mobile Money
- **Analytics** — Cashflow, category breakdowns, trend analysis, and anomaly detection
- **AI Chatbot** — LangChain ReAct agent with read-only access to the trader's financial data
- **Monthly Reports** — Auto-generated PDF reports emailed on the 1st of every month
- **Real-time Notifications** — WebSocket dashboard updates, SMS, email, and push alerts
- **Compliance** — KYC verification, AML monitoring, and immutable audit logging

---

## Architecture

Single FastAPI application structured as **domain modules**. Each domain is a self-contained Python package under `app/domains/`. Domains communicate via service function calls and Redis Streams — never by importing each other's models directly.

Three containers, one image:

| Container | Command |
|-----------|---------|
| API | `uvicorn app.main:app` |
| Worker | `celery -A app.config.celery worker` |
| Beat | `celery -A app.config.celery beat` |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 16 + pgvector |
| ORM / Migrations | SQLAlchemy (async) + Alembic |
| Task Queue | Celery + Redis |
| AI / LLM | LangChain + Claude (Anthropic) |
| Auth | JWT RS256 + TOTP 2FA |
| PDF Reports | WeasyPrint + Jinja2 |
| Email | SendGrid |
| SMS | Hubtel |
| Push | Firebase Cloud Messaging |
| Storage | AWS S3 |
| Secrets | AWS Secrets Manager |

---

## Repository Structure

```
pivota-backend/
├── app/
│   ├── main.py                      # FastAPI app factory
│   ├── lifespan.py                  # Startup / shutdown lifecycle
│   ├── core/                        # Money, exceptions, idempotency, security, events
│   ├── config/                      # Settings, DB engines, Redis pools, Celery schedule
│   ├── middleware/                  # JWT auth, rate limiting, request ID, audit trail
│   ├── domains/
│   │   ├── auth/                    # Login, refresh tokens, 2FA, password reset
│   │   ├── users/                   # Profiles, KYC status
│   │   ├── accounts/                # MoMo accounts, computed balances (no balance column)
│   │   ├── transactions/            # Append-only transaction ledger
│   │   ├── ingest/                  # MoMo webhook handler + polling fallback
│   │   ├── compliance/              # KYC, AML rules, INSERT-only audit log
│   │   ├── analytics/               # Cashflow, categories, trends, anomaly detection
│   │   ├── reports/                 # Monthly PDF pipeline + S3 storage + email delivery
│   │   ├── notifications/           # WebSocket, SMS, email, push channels
│   │   └── ai/                      # LangChain chatbot + pgvector RAG
│   ├── workers/                     # Celery task definitions (6 queues)
│   └── db/                          # Base, session helpers, mixins, roles.sql
├── migrations/                      # Alembic schema + data migrations
├── tests/                           # Unit + integration test suite
├── scripts/                         # Dev tooling: seed data, DLQ replay, role setup
├── docker/                          # Dockerfile, docker-compose.yml, .env.example
├── .github/                         # CI/CD workflows, CODEOWNERS
├── pyproject.toml
├── ruff.toml
├── mypy.ini
└── CLAUDE.md                        # Architecture guide — single source of truth
```

---

## Core Rules

These are enforced at the database and runtime level and must never be broken.

1. **No floats for money** — All monetary values use the `Money` class (Decimal-backed). `FloatMoneyError` is raised at runtime.
2. **Idempotent MoMo writes** — Every webhook handler calls `check_and_set()` before processing.
3. **Transactions are append-only** — No `UPDATE` or `DELETE` on the `transactions` table. Corrections use reversals.
4. **Audit log is INSERT-only** — `audit_events` is never modified after write.
5. **AI domain never writes** — Connected via a read-only Postgres role (`pivota_ai`).
6. **No silent job failures** — Every Celery task has a DLQ handler and max 3 retries with backoff.
7. **Secrets from AWS in production** — No `.env` files in prod. All secrets via AWS Secrets Manager.
8. **Analytics uses the read replica** — `get_read_db()` always, never `get_db()`.

Full details in [CLAUDE.md](./CLAUDE.md).

---

## Getting Started

**Prerequisites:** Docker, Docker Compose, OpenSSL

```bash
# 1. Generate RS256 JWT keys
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem

# 2. Set up environment
cp docker/.env.example docker/.env
# Edit docker/.env with your MoMo sandbox credentials and Anthropic API key

# 3. Start all services
docker compose -f docker/docker-compose.yml up -d

# 4. Run migrations
docker compose exec api alembic upgrade head

# 5. Create Postgres roles
docker compose exec api python scripts/create_db_roles.py --env development

# 6. Seed dev data
docker compose exec api python scripts/seed_dev_data.py

# 7. Run tests
pytest tests/ -v
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Mailhog | http://localhost:8025 |

---

## License

Private / Proprietary
