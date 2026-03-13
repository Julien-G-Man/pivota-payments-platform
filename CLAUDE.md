# Pivota Backend — Complete Architecture & Implementation Guide

> **For Claude Code:** This document is the single source of truth for the Pivota backend.
> Read it fully before writing any code. Every structural decision here is intentional.
> Do not deviate from the patterns defined in this document without explicit instruction.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Non-Negotiable Rules](#2-non-negotiable-rules)
3. [Technology Stack](#3-technology-stack)
4. [Repository Structure](#4-repository-structure)
5. [Core Layer](#5-core-layer)
6. [Configuration Layer](#6-configuration-layer)
7. [Middleware Layer](#7-middleware-layer)
8. [Domain: Auth](#8-domain-auth)
9. [Domain: Users](#9-domain-users)
10. [Domain: Accounts](#10-domain-accounts)
11. [Domain: Transactions](#11-domain-transactions)
12. [Domain: Ingest (MTN MoMo)](#12-domain-ingest-mtn-momo)
13. [Domain: Compliance (KYC / AML / Audit)](#13-domain-compliance-kyc--aml--audit)
14. [Domain: Analytics](#14-domain-analytics)
15. [Domain: Reports](#15-domain-reports)
16. [Domain: Notifications](#16-domain-notifications)
17. [Domain: AI Chatbot](#17-domain-ai-chatbot)
18. [Workers (Celery)](#18-workers-celery)
19. [Database Layer](#19-database-layer)
20. [Migrations (Alembic)](#20-migrations-alembic)
21. [Tests](#21-tests)
22. [Scripts](#22-scripts)
23. [Docker & Local Dev](#23-docker--local-dev)
24. [CI/CD](#24-cicd)
25. [Security Architecture](#25-security-architecture)
26. [Data Flow Diagrams](#26-data-flow-diagrams)
27. [Environment Variables Reference](#27-environment-variables-reference)
28. [Postgres Role Definitions](#28-postgres-role-definitions)
29. [Redis Key Conventions](#29-redis-key-conventions)
30. [Error Handling Strategy](#30-error-handling-strategy)
31. [Getting Started (Local Dev)](#31-getting-started-local-dev)

---

## 1. Project Overview

**Pivota** is a fintech platform for traders to manage expenses, track money in/out via MTN Mobile Money (MoMo), receive AI-powered spending insights, view dashboards, and get automated monthly email reports.

### What the platform does

- Ingests transactions from MTN MoMo via webhooks and polling
- Categorises and analyses spend patterns
- Serves real-time dashboards via WebSocket
- Generates and emails monthly PDF financial reports
- Provides an AI chatbot with full read access to the trader's financial data
- Enforces KYC, AML monitoring, and immutable audit logging

### Architecture style

Single FastAPI application structured as **domain modules** — not microservices, not a flat monolith. Each domain (`transactions`, `compliance`, `analytics`, etc.) is a self-contained Python package under `app/domains/`. Domains communicate through service function calls and Redis Streams events — never by importing each other's models directly.

The app runs as two containers from the same Docker image:

- **API container**: `uvicorn app.main:app`
- **Worker container**: `celery -A app.config.celery worker`

A third container runs Celery Beat for scheduled tasks.

---

## 2. Non-Negotiable Rules

These rules must never be broken. They exist because violations cause financial data corruption or regulatory failure.

### Rule 1 — Never use float for money

```python
# ILLEGAL everywhere in this codebase
amount = 29.99          # float literal — NEVER
amount = float(value)   # float cast — NEVER
Column(Float)           # SQLAlchemy Float column for money — NEVER

# CORRECT
from app.core.money import Money
amount = Money("29.99")                          # string input
amount = Money(2999, unit="minor")               # integer minor units (pesewas)
db_column = Column(Numeric(19, 4))               # NUMERIC in Postgres — always
```

The `Money` class in `app/core/money.py` raises `FloatMoneyError` if a float is passed. This is enforced at runtime and by mypy strict typing. There are no exceptions to this rule.

### Rule 2 — Every MoMo transaction write must be idempotent

```python
# Every webhook handler and poller must do this FIRST
from app.core.idempotency import check_and_set

is_new, cached = await check_and_set(
    key=f"momo:{momo_transaction_id}",
    redis=redis,
    ttl_seconds=86400  # 24 hours
)
if not is_new:
    return cached  # Return immediately — do not process again
```

MTN MoMo retries webhooks on timeout. Without idempotency, duplicate processing causes double-counted transactions. The idempotency key is the MoMo transaction ID. TTL is 24 hours.

### Rule 3 — Transactions are append-only

The `transactions` table has no application-level `UPDATE` or `DELETE` path. If a transaction must be corrected, a new reversal transaction is created. The `tf_app` Postgres role does not have `UPDATE` or `DELETE` grants on the `transactions` table. This is enforced at the database level.

### Rule 4 — The audit log is INSERT-only

`compliance/audit_log.py` exposes only `append_event()`. There is no `update_event()` or `delete_event()` function. The `tf_app` Postgres role has `INSERT` only on `audit_events`. The `tf_audit_readonly` role has `SELECT` only. This is enforced at the database level via `db/roles.sql`.

### Rule 5 — The AI domain never writes to the database

`app/domains/ai/` connects to Postgres using the `tf_ai_readonly` role which has `SELECT` only on the permitted tables. The AI domain calls analytics service functions — it does not write SQL directly. There is no write path through the AI domain.

### Rule 6 — Failed jobs must never disappear silently

Every Celery task that can fail must have:

- `max_retries=3`
- `retry_backoff=True` with `retry_backoff_max=3600`
- A DLQ publish call in the `on_failure` handler

The DLQ is a Redis Stream key `dlq:events`. A Celery Beat task checks it hourly and alerts if depth exceeds threshold.

### Rule 7 — Secrets never come from environment variables in production

In production, all secrets are read from AWS Secrets Manager via `app/core/secrets.py`. The `SecretsClient` caches values in memory with a 5-minute TTL. `.env` files are for local development only. The Docker production image has no `.env` file.

### Rule 8 — All analytics reads use the read replica

`app/domains/analytics/` and `app/domains/ai/` use `get_read_db()` which connects to the Postgres read replica. They never use `get_db()` (primary). This is enforced by the session dependency injected in each router.

---

## 3. Technology Stack

| Layer           | Library                 | Version          | Purpose                                      |
|-----------------|-------------------------|------------------|----------------------------------------------|
| Web framework   | FastAPI                 | `>=0.111`        | API, WebSocket, dependency injection         |
| ASGI server     | Uvicorn                 | `>=0.29`         | Production server with `--workers`           |
| ORM             | SQLAlchemy              | `>=2.0`          | Async ORM, `AsyncSession`                    |
| Validation      | Pydantic                | `v2`             | Schemas, settings, strict types              |
| Migrations      | Alembic                 | `>=1.13`         | Schema versioning                            |
| Task queue      | Celery                  | `>=5.3`          | Async jobs, scheduled tasks                  |
| Cache / broker  | Redis                   | `>=5.0`          | Caching, Celery broker, pub/sub, idempotency |
| AI agent        | LangChain               | `>=0.2`          | ReAct agent, tool orchestration              |
| LLM             | Anthropic / OpenAI      | latest           | Claude or GPT-4 for chatbot                  |
| Vector search   | pgvector                | `>=0.3`          | Transaction embedding search                 |
| Data processing | Pandas                  | `>=2.2`          | Analytics aggregations                       |
| PDF generation  | WeasyPrint              | `>=61`           | HTML-to-PDF for monthly reports              |
| Template engine | Jinja2                  | `>=3.1`          | Report HTML templates                        |
| Email           | sendgrid                | `>=6.11`         | Transactional email                          |
| SMS             | httpx (Hubtel)          | `>=0.27`         | SMS gateway (Hubtel Ghana)                   |
| Push            | firebase-admin          | `>=6.5`          | Mobile push notifications                    |
| Object storage  | boto3                   | `>=1.34`         | S3 / Cloudflare R2 for PDFs                  |
| Secrets         | boto3                   | `>=1.34`         | AWS Secrets Manager                          |
| Auth            | python-jose             | `>=3.3`          | JWT (RS256)                                  |
| Password hash   | passlib[bcrypt]         | `>=1.7`          | bcrypt password hashing                      |
| OTP             | pyotp                   | `>=2.9`          | TOTP 2FA                                     |
| HTTP client     | httpx                   | `>=0.27`         | MoMo API client, Hubtel client               |
| Logging         | structlog               | `>=24`           | Structured JSON logs                         |
| Linting         | ruff                    | `>=0.4`          | Lint + format + banned imports               |
| Type checking   | mypy                    | `>=1.10`         | Strict static types                          |
| Testing         | pytest + pytest-asyncio | `>=8`            | Async test suite                             |
| Test HTTP       | httpx                   | `>=0.27`         | Test client for FastAPI                      |

---

## 4. Repository Structure

```
pivota-backend/
│
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                  # Lint → typecheck → test → build → push
│   │   ├── cd.yml                  # Deploy staging (main) / prod (tag)
│   │   └── migrate.yml             # Run Alembic migrations before deploy
│   └── CODEOWNERS                  # PR review requirements per path
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory
│   ├── lifespan.py                 # Startup/shutdown lifecycle
│   │
│   ├── core/                       # CRITICAL — imported by everything
│   │   ├── __init__.py
│   │   ├── money.py                # Money class (Decimal-backed, no floats)
│   │   ├── exceptions.py           # All typed application exceptions
│   │   ├── idempotency.py          # Redis SET NX idempotency primitive
│   │   ├── security.py             # JWT, bcrypt, HMAC utilities
│   │   ├── secrets.py              # AWS Secrets Manager client
│   │   ├── events.py               # Redis Streams publisher
│   │   ├── pagination.py           # Cursor + page-based pagination
│   │   └── logging.py              # Structlog configuration
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py             # Pydantic BaseSettings
│   │   ├── database.py             # SQLAlchemy engines (primary, replica, ai_readonly)
│   │   ├── redis.py                # Redis connection pool
│   │   └── celery.py               # Celery app + beat schedule
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                 # JWT verification → request.state
│   │   ├── rate_limit.py           # Redis sliding window
│   │   ├── request_id.py           # X-Request-ID injection
│   │   ├── audit_trail.py          # Post-response audit event fire
│   │   └── security_headers.py     # HSTS, CSP, X-Frame-Options
│   │
│   ├── domains/
│   │   │
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   └── dependencies.py     # get_current_user(), require_role()
│   │   │
│   │   ├── users/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── accounts/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── transactions/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── enums.py
│   │   │   └── categorizer.py
│   │   │
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # POST /momo/webhook
│   │   │   ├── webhook_handler.py  # Celery task — process incoming webhook
│   │   │   ├── poller.py           # Celery beat — poll MoMo API
│   │   │   ├── momo_client.py      # MTN MoMo REST client
│   │   │   ├── normalizer.py       # MoMo payload → internal schema
│   │   │   └── dlq.py              # Dead letter queue on failure
│   │   │
│   │   ├── compliance/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── kyc_service.py
│   │   │   ├── aml_monitor.py      # Redis Streams consumer
│   │   │   ├── aml_rules.py        # Threshold-based flagging rules
│   │   │   ├── audit_log.py        # INSERT-only audit log writer
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   └── stream_consumer.py  # Async Redis Streams consumer loop
│   │   │
│   │   ├── analytics/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── cache.py            # Redis cache decorator
│   │   │   └── aggregators/
│   │   │       ├── __init__.py
│   │   │       ├── cashflow.py
│   │   │       ├── categories.py
│   │   │       ├── trends.py
│   │   │       └── anomaly.py
│   │   │
│   │   ├── reports/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── generator.py        # Celery task — full report pipeline
│   │   │   ├── renderer.py         # HTML → PDF via WeasyPrint
│   │   │   ├── models.py
│   │   │   ├── tasks.py            # Beat schedule definitions
│   │   │   ├── dlq.py
│   │   │   └── templates/
│   │   │       ├── monthly.html
│   │   │       └── styles.css
│   │   │
│   │   ├── notifications/
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # WebSocket + notification list
│   │   │   ├── stream_consumer.py  # Redis Streams consumer
│   │   │   ├── websocket_manager.py
│   │   │   ├── models.py
│   │   │   └── channels/
│   │   │       ├── __init__.py
│   │   │       ├── email.py        # SendGrid
│   │   │       ├── sms.py          # Hubtel
│   │   │       └── push.py         # Firebase Cloud Messaging
│   │   │
│   │   └── ai/
│   │       ├── __init__.py
│   │       ├── router.py           # POST /ai/chat (SSE), session management
│   │       ├── agent.py            # LangChain ReAct agent
│   │       ├── tools.py            # Agent tools (all read-only)
│   │       ├── guardrails.py       # System prompt builder
│   │       ├── session.py          # Chat session persistence
│   │       ├── models.py
│   │       └── rag/
│   │           ├── __init__.py
│   │           ├── embedder.py     # Text → pgvector embeddings
│   │           └── retriever.py    # Semantic transaction search
│   │
│   └── workers/
│       ├── __init__.py
│       ├── ingest_tasks.py
│       ├── report_tasks.py
│       ├── analytics_tasks.py
│       ├── notification_tasks.py
│       ├── compliance_tasks.py
│       └── dlq_tasks.py
│
├── app/db/
│   ├── __init__.py
│   ├── base.py                     # SQLAlchemy DeclarativeBase
│   ├── session.py                  # get_db(), get_read_db(), get_ai_db()
│   ├── mixins.py                   # TimestampMixin, UUIDMixin, SoftDeleteMixin
│   └── roles.sql                   # Postgres role definitions (run once at infra setup)
│
├── migrations/
│   ├── env.py                      # Alembic environment
│   ├── script.py.mako
│   ├── versions/                   # Schema migrations only
│   └── data/                       # Data migrations (run separately)
│
├── tests/
│   ├── conftest.py                 # Fixtures: test DB, Redis mock, Celery eager, mock clients
│   ├── core/
│   │   ├── test_money.py
│   │   └── test_idempotency.py
│   └── domains/
│       ├── ingest/
│       │   ├── test_webhook.py
│       │   └── test_poller.py
│       ├── compliance/
│       │   ├── test_aml.py
│       │   └── test_audit.py
│       ├── transactions/
│       │   └── test_service.py
│       ├── analytics/
│       │   └── test_cashflow.py
│       └── integration/
│           ├── test_momo_flow.py
│           └── test_report_flow.py
│
├── scripts/
│   ├── seed_dev_data.py
│   ├── replay_dlq.py
│   ├── create_db_roles.py
│   └── rotate_momo_token.py
│
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   ├── docker-compose.yml
│   └── .env.example
│
├── pyproject.toml
├── ruff.toml
├── mypy.ini
├── .pre-commit-config.yaml
└── README.md
```

---

## 5. Core Layer

### `app/core/money.py`

The most important file in the codebase. All financial values pass through this.

```python
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from dataclasses import dataclass
from typing import Union
from app.core.exceptions import FloatMoneyError, CurrencyMismatchError

SUPPORTED_CURRENCIES = {"GHS", "USD", "EUR"}
MINOR_UNIT_FACTORS = {"GHS": 100, "USD": 100, "EUR": 100}

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "GHS"

    def __new__(cls, amount: Union[str, int, Decimal], currency: str = "GHS", unit: str = "major"):
        if isinstance(amount, float):
            raise FloatMoneyError(
                f"Float passed to Money({amount}). Use string, int, or Decimal. "
                "Floats cause precision loss in financial calculations."
            )
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {currency}")
        instance = object.__new__(cls)
        try:
            if unit == "minor":
                factor = MINOR_UNIT_FACTORS[currency]
                decimal_amount = Decimal(str(amount)) / Decimal(str(factor))
            else:
                decimal_amount = Decimal(str(amount))
        except InvalidOperation:
            raise ValueError(f"Cannot convert {amount!r} to Decimal")
        object.__setattr__(instance, "amount", decimal_amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
        object.__setattr__(instance, "currency", currency)
        return instance

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"Cannot subtract {self.currency} and {other.currency}")
        return Money(self.amount - other.amount, self.currency)

    def __gt__(self, other: "Money") -> bool:
        return self.amount > other.amount

    def __lt__(self, other: "Money") -> bool:
        return self.amount < other.amount

    def format(self) -> str:
        """Human-readable. Always use this for display — never .amount directly."""
        return f"{self.currency} {self.amount:.2f}"

    def to_minor_units(self) -> int:
        """Returns integer minor units (pesewas for GHS). Use for storage comparisons."""
        factor = MINOR_UNIT_FACTORS[self.currency]
        return int(self.amount * factor)

    @classmethod
    def from_db(cls, amount: Decimal, currency: str = "GHS") -> "Money":
        """Use this when reading Numeric values from SQLAlchemy — already Decimal."""
        return cls(amount, currency)

    def __repr__(self) -> str:
        return f"Money({self.amount!r}, {self.currency!r})"
```

### `app/core/exceptions.py`

```python
class PivotaError(Exception):
    """Base exception for all application errors."""

class FloatMoneyError(PivotaError):
    """Raised when float is passed to Money()."""

class CurrencyMismatchError(PivotaError):
    """Raised on arithmetic between different currencies."""

class DuplicateTransactionError(PivotaError):
    """Raised when idempotency check finds existing transaction."""

class IdempotencyConflictError(PivotaError):
    """Raised when idempotency key is acquired concurrently."""

class ComplianceHoldError(PivotaError):
    """Raised when a transaction is blocked by AML hold."""

class KYCRequiredError(PivotaError):
    """Raised when action requires completed KYC."""

class InsufficientFundsError(PivotaError):
    """Raised when account balance is insufficient."""

class MoMoAPIError(PivotaError):
    """Raised on MTN MoMo API errors."""

class WebhookSignatureError(PivotaError):
    """Raised when MoMo webhook HMAC signature fails verification."""

class SecretsError(PivotaError):
    """Raised when secret cannot be retrieved."""
```

### `app/core/idempotency.py`

```python
import json
from dataclasses import dataclass
from typing import Any, Optional, Tuple
from redis.asyncio import Redis

@dataclass
class IdempotencyResult:
    is_new: bool
    cached_response: Optional[dict]

async def check_and_set(
    key: str,
    redis: Redis,
    ttl_seconds: int = 86400,
    response: Optional[dict] = None,
) -> IdempotencyResult:
    """
    Atomically check if key exists and set it if not.

    Returns IdempotencyResult(is_new=True) on first call.
    Returns IdempotencyResult(is_new=False, cached_response=...) on repeat calls.
    """
    full_key = f"idempotency:{key}"
    was_set = await redis.set(full_key, "processing", nx=True, ex=ttl_seconds)

    if was_set:
        return IdempotencyResult(is_new=True, cached_response=None)

    value = await redis.get(full_key)
    if value and value != b"processing":
        try:
            cached = json.loads(value)
            return IdempotencyResult(is_new=False, cached_response=cached)
        except json.JSONDecodeError:
            pass

    return IdempotencyResult(is_new=False, cached_response=None)

async def mark_complete(key: str, redis: Redis, response: dict, ttl_seconds: int = 86400) -> None:
    """Store the final response for the idempotency key."""
    full_key = f"idempotency:{key}"
    await redis.set(full_key, json.dumps(response), ex=ttl_seconds)
```

### `app/core/security.py`

```python
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.secrets import secrets_client

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str, role: str, expires_minutes: int = 15) -> str:
    private_key = secrets_client.get("jwt/private_key")
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
        "type": "access",
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

def create_refresh_token(user_id: str, expires_days: int = 7) -> str:
    private_key = secrets_client.get("jwt/private_key")
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=expires_days),
        "type": "refresh",
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

def decode_token(token: str) -> dict:
    public_key = secrets_client.get("jwt/public_key")
    return jwt.decode(token, public_key, algorithms=["RS256"])

def verify_momo_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify MTN MoMo webhook HMAC-SHA256 signature."""
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### `app/core/events.py`

```python
import json
from datetime import datetime, timezone
from redis.asyncio import Redis

async def publish(stream: str, event_type: str, payload: dict, redis: Redis) -> None:
    """
    Publish an event to a Redis Stream.

    Streams used:
      - "transactions" → event_type: "transaction.created"
      - "compliance"   → event_type: "aml.flagged", "kyc.approved", "kyc.rejected"
      - "reports"      → event_type: "report.ready"
      - "auth"         → event_type: "login.failed", "password.reset"
      - "dlq"          → event_type: "job.failed"
    """
    event = {
        "event_type": event_type,
        "payload": json.dumps(payload),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await redis.xadd(stream, event)
```

---

## 6. Configuration Layer

### `app/config/settings.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

class Settings(BaseSettings):
    app_name: str = "Pivota"
    environment: str = Field("development", pattern="^(development|staging|production)$")
    debug: bool = False

    database_url: str
    database_replica_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379"
    redis_db_cache: int = 0
    redis_db_celery: int = 1
    redis_db_idempotency: int = 2
    redis_db_rate_limit: int = 3
    redis_db_sessions: int = 4

    momo_base_url: str
    momo_subscription_key: str
    momo_webhook_secret: str
    momo_environment: str = "sandbox"
    momo_poll_interval_seconds: int = 300

    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    sendgrid_api_key: str
    sendgrid_from_email: str = "reports@pivota.com"

    hubtel_client_id: str
    hubtel_client_secret: str
    hubtel_sender_id: str = "Pivota"

    aws_region: str = "eu-west-1"
    s3_bucket_reports: str
    s3_bucket_kyc_docs: str

    anthropic_api_key: str
    llm_model: str = "claude-opus-4-5"

    aml_large_tx_threshold_ghs: str = "5000.00"
    aml_velocity_max_per_hour: int = 10
    aml_zscore_threshold: float = 3.0

    firebase_credentials_json: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### `app/config/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config.settings import settings

engine_primary = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    echo=settings.debug,
)

engine_replica = create_async_engine(
    settings.database_replica_url,
    pool_size=10,
    pool_pre_ping=True,
)

engine_ai_readonly = create_async_engine(
    settings.database_url.replace("pivota_app", "pivota_ai"),
    pool_size=5,
    pool_pre_ping=True,
)

AsyncSessionPrimary = async_sessionmaker(engine_primary, expire_on_commit=False)
AsyncSessionReplica = async_sessionmaker(engine_replica, expire_on_commit=False)
AsyncSessionAI = async_sessionmaker(engine_ai_readonly, expire_on_commit=False)
```

### `app/config/redis.py`

```python
import redis.asyncio as aioredis
from app.config.settings import settings

def get_redis_pool(db: int) -> aioredis.Redis:
    return aioredis.from_url(
        settings.redis_url,
        db=db,
        encoding="utf-8",
        decode_responses=True,
    )

cache_redis = get_redis_pool(settings.redis_db_cache)
idempotency_redis = get_redis_pool(settings.redis_db_idempotency)
rate_limit_redis = get_redis_pool(settings.redis_db_rate_limit)
session_redis = get_redis_pool(settings.redis_db_sessions)
```

### `app/config/celery.py`

```python
from celery import Celery
from celery.schedules import crontab
from app.config.settings import settings

celery_app = Celery(
    "pivota",
    broker=f"{settings.redis_url}/{settings.redis_db_celery}",
    backend=f"{settings.redis_url}/{settings.redis_db_celery}",
    include=[
        "app.workers.ingest_tasks",
        "app.workers.report_tasks",
        "app.workers.analytics_tasks",
        "app.workers.notification_tasks",
        "app.workers.compliance_tasks",
        "app.workers.dlq_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
)

celery_app.conf.beat_schedule = {
    "poll-momo-transactions": {
        "task": "app.workers.ingest_tasks.poll_momo_transactions",
        "schedule": crontab(minute="*/5"),
    },
    "trigger-monthly-reports": {
        "task": "app.workers.report_tasks.trigger_monthly_reports",
        "schedule": crontab(day_of_month="1", hour="8", minute="0"),
    },
    "precompute-weekly-summaries": {
        "task": "app.workers.analytics_tasks.precompute_weekly_summaries",
        "schedule": crontab(day_of_week="0", hour="0", minute="0"),
    },
    "check-dlq-depth": {
        "task": "app.workers.dlq_tasks.check_dlq_depth",
        "schedule": crontab(minute="0"),
    },
}
```

---

## 7. Middleware Layer

### `app/middleware/auth.py`

```python
from fastapi import Request, HTTPException, status
from app.core.security import decode_token
from jose import JWTError

async def jwt_auth_middleware(request: Request, call_next):
    """
    Public paths that skip auth:
      - /health
      - /api/v1/auth/login
      - /api/v1/auth/refresh
      - /api/v1/momo/webhook  (uses HMAC auth instead)
      - /docs, /openapi.json (disabled in production)
    """
    PUBLIC_PATHS = {"/health", "/api/v1/auth/login", "/api/v1/auth/refresh", "/api/v1/momo/webhook"}

    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        request.state.user_id = payload["sub"]
        request.state.role = payload.get("role", "trader")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return await call_next(request)
```

### `app/middleware/rate_limit.py`

```
Sliding window rate limiter using Redis.

Limits:
  - Default API:           100 requests / minute per user
  - Auth endpoints:         10 requests / minute per IP
  - MoMo webhook:            5 requests / minute per IP
  - AI chat:                20 requests / minute per user
```

### `app/middleware/audit_trail.py`

```
For mutating HTTP methods (POST, PATCH, DELETE):
After response is sent, fire an async audit event containing:
  - actor_id (from request.state.user_id)
  - method + path
  - response status code
  - X-Request-ID
  - client IP
  - timestamp

Does NOT block the response. Uses asyncio.create_task() to fire-and-forget.
```

---

## 8. Domain: Auth

### Models (`app/domains/auth/models.py`)

```python
class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "auth_users"
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="trader")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class RefreshToken(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "auth_refresh_tokens"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

class TOTPDevice(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "auth_totp_devices"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id"), unique=True)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)  # Encrypted at rest
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes_hash: Mapped[Optional[str]] = mapped_column(Text)
```

### Dependencies (`app/domains/auth/dependencies.py`)

```python
async def get_current_user(request: Request) -> dict:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user_id": user_id, "role": request.state.role}

def require_role(*roles: str):
    """Usage: Depends(require_role('admin', 'compliance_officer'))"""
    async def checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker
```

### Router endpoints

```
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
POST /api/v1/auth/2fa/setup
POST /api/v1/auth/2fa/verify
POST /api/v1/auth/2fa/validate
POST /api/v1/auth/password/reset
POST /api/v1/auth/password/confirm
```

---

## 9. Domain: Users

### Models (`app/domains/users/models.py`)

```python
class UserProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_profiles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    address: Mapped[Optional[str]] = mapped_column(Text)
    kyc_status: Mapped[str] = mapped_column(String(20), default="pending")
    preferred_currency: Mapped[str] = mapped_column(String(3), default="GHS")
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Accra")
    notification_preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
```

### Router endpoints

```
GET    /api/v1/users/me
PATCH  /api/v1/users/me
GET    /api/v1/users/{id}          # Admin only
GET    /api/v1/users/me/kyc-status
```

---

## 10. Domain: Accounts

### Key Design Decision

**There is no `balance` column.** The account balance is always computed from the sum of completed transactions on the read replica. The computed balance is cached in Redis for 1 minute.

```python
async def get_balance(account_id: UUID, db: AsyncSession, redis: Redis) -> Money:
    cache_key = f"balance:{account_id}"
    cached = await redis.get(cache_key)
    if cached:
        return Money(cached)

    result = await db.execute(
        select(func.sum(Transaction.amount))
        .where(Transaction.account_id == account_id)
        .where(Transaction.status == TransactionStatus.COMPLETED)
    )
    total = result.scalar() or Decimal("0")
    balance = Money.from_db(total)
    await redis.set(cache_key, str(balance.amount), ex=60)
    return balance
```

### Models

```python
class Account(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "accounts"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id"), nullable=False)
    momo_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    momo_account_name: Mapped[Optional[str]] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="GHS")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # NO balance column
```

### Router endpoints

```
GET  /api/v1/accounts
POST /api/v1/accounts
GET  /api/v1/accounts/{id}
GET  /api/v1/accounts/{id}/balance
```

---

## 11. Domain: Transactions

### Models (`app/domains/transactions/models.py`)

```python
class Transaction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "transactions"
    account_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)  # NEVER Float
    currency: Mapped[str] = mapped_column(String(3), default="GHS")
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus), nullable=False)
    category: Mapped[Optional[Category]] = mapped_column(Enum(Category))
    momo_ref: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    counterparty_name: Mapped[Optional[str]] = mapped_column(String(255))
    counterparty_number: Mapped[Optional[str]] = mapped_column(String(20))
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    transacted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index("ix_transactions_account_transacted", "account_id", "transacted_at"),
        Index("ix_transactions_account_category", "account_id", "category"),
        Index("ix_transactions_account_type", "account_id", "type"),
    )
```

### Enums (`app/domains/transactions/enums.py`)

```python
class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    REVERSAL = "reversal"

class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"

class Category(str, enum.Enum):
    AIRTIME = "airtime"
    TRANSFER = "transfer"
    MERCHANT = "merchant"
    UTILITY = "utility"
    SALARY = "salary"
    CASH_OUT = "cash_out"
    CASH_IN = "cash_in"
    LOAN = "loan"
    OTHER = "other"
```

### Schemas

```python
class TransactionResponse(BaseModel):
    id: UUID
    account_id: UUID
    amount: str              # Money.format() — NEVER float or raw Decimal
    currency: str
    type: TransactionType
    status: TransactionStatus
    category: Optional[Category]
    description: Optional[str]
    counterparty_name: Optional[str]
    momo_ref: Optional[str]
    transacted_at: datetime
    created_at: datetime

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal) -> str:
        return Money.from_db(amount).format()
```

### Router endpoints

```
GET  /api/v1/transactions       # Paginated, filterable
GET  /api/v1/transactions/{id}
# No POST/PATCH/DELETE — all writes via ingest domain
```

---

## 12. Domain: Ingest (MTN MoMo)

### Webhook flow

```
MTN MoMo → POST /api/v1/momo/webhook
  1. HMAC verify (reject 403 if invalid)
  2. Rate limit check
  3. check_and_set(idempotency_key=momo_ref) — return 200 if duplicate
  4. Enqueue Celery task: process_momo_webhook(raw_payload)
  5. Return HTTP 200 immediately

Celery worker:
  6. Normalizer maps MoMo fields → internal schema
  7. Money(amount_str) created
  8. Categorizer assigns category
  9. Transaction written to DB
  10. AuditEvent appended
  11. publish("transactions", "transaction.created")
  12. Invalidate balance cache
```

### Router (`app/domains/ingest/router.py`)

```python
@router.post("/momo/webhook", status_code=200)
async def momo_webhook(request: Request, redis: Redis = Depends(get_idempotency_redis)):
    body = await request.body()
    signature = request.headers.get("X-Momo-Signature", "")

    if not verify_momo_webhook_signature(body, signature, settings.momo_webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    payload = json.loads(body)
    momo_ref = payload.get("externalId") or payload.get("referenceId")

    result = await check_and_set(f"momo:{momo_ref}", redis)
    if not result.is_new:
        return {"status": "duplicate", "message": "Already processed"}

    process_momo_webhook.delay(payload)
    return {"status": "accepted"}
```

### Normalizer notes

- MoMo sends amounts as strings (`"29.99"`) or integers (`2999`)
- Always convert via `Money("29.99")` — never via `float()`
- Full raw payload stored as JSONB in `metadata`

### Polling fallback

Celery beat task runs every 5 minutes. Calls MoMo API to fetch recent transactions. Idempotency via `momo_ref` prevents double-writes. This is the safety net — not the primary path.

---

## 13. Domain: Compliance (KYC / AML / Audit)

### KYC Flow

```
1. User submits ID document via POST /compliance/kyc/submit
2. Document encrypted and uploaded to S3 (KYC bucket)
3. KYCSubmission record created with status=pending
4. Webhook registered with Smile Identity / Onfido
5. Verification provider calls our webhook on completion
6. KYC status updated to approved or rejected
7. AuditEvent logged for each status change
8. User notified via notification domain
```

### AML Rules

```
Rule: Large Transaction
  Triggers when: amount > settings.aml_large_tx_threshold_ghs
  Severity: HIGH

Rule: Velocity
  Triggers when: >10 transactions from same account in any 60-minute window
  Severity: MEDIUM

Rule: Unusual Pattern (Z-score)
  Triggers when: amount is >3 std deviations from user's 90-day rolling mean
  Requires at least 30 historical transactions to activate
  Severity: MEDIUM

Rule: After-Hours
  Triggers when: 00:00–04:00 Africa/Accra AND amount > GHS 500
  Severity: LOW
```

### Audit Log (`app/domains/compliance/audit_log.py`)

```python
async def append_event(
    db: AsyncSession,
    actor_id: Optional[str],      # user_id or "system"
    action: str,                   # e.g. "transaction.ingested"
    entity_type: str,
    entity_id: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    ip_address: Optional[str] = None,
    request_id: Optional[str] = None,
) -> None:
    """INSERT only. No update or delete path exists."""
```

### Audit Model

```python
class AuditEvent(Base, UUIDMixin):
    """Immutable — no TimestampMixin (no updated_at). No soft delete."""
    __tablename__ = "audit_events"
    actor_id: Mapped[Optional[str]] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    before_json: Mapped[Optional[str]] = mapped_column(Text)
    after_json: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    request_id: Mapped[Optional[str]] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    # No updated_at. No deleted_at. This record never changes after insert.
```

### Router endpoints

```
POST  /api/v1/compliance/kyc/submit
GET   /api/v1/compliance/kyc/status
POST  /api/v1/compliance/kyc/webhook
GET   /api/v1/compliance/flags          # Admin only
PATCH /api/v1/compliance/flags/{id}     # Admin only
GET   /api/v1/compliance/audit          # Admin only
```

---

## 14. Domain: Analytics

### Key Design Decisions

- All reads use read replica — `get_read_db()` injected, never `get_db()`
- All responses cached 5 minutes in Redis — invalidated on `transaction.created`
- All monetary values returned as `Money.format()` strings — never Decimal or float
- Pandas used for aggregations

### Aggregators

**`cashflow.py`** — Daily/weekly/monthly credit vs debit totals, net cashflow per period

**`categories.py`** — Spend breakdown by category, month-over-month delta

**`trends.py`** — 7d/30d/90d rolling average spend, velocity, peak spend heatmap

**`anomaly.py`** — Z-score on 90-day rolling window, IQR outlier detection, returns `anomaly_score` 0.0–1.0

### Router endpoints

```
GET /api/v1/analytics/summary
GET /api/v1/analytics/cashflow
GET /api/v1/analytics/categories
GET /api/v1/analytics/trends
GET /api/v1/analytics/anomalies
GET /api/v1/analytics/ai-context    # Internal only — called by AI domain directly
```

---

## 15. Domain: Reports

### Monthly Report Pipeline

```
Celery Beat (1st of month, 08:00 UTC)
  → trigger_monthly_reports (fans out per user)
    → generate_monthly_report(user_id, period)
      1. Check if Report record exists — SKIP if yes (idempotent)
      2. Fetch analytics data
      3. Fetch top 10 transactions
      4. Render HTML via Jinja2
      5. Convert HTML → PDF via WeasyPrint
      6. Upload PDF to S3: reports/{user_id}/{period}/report.pdf
      7. Create Report record
      8. Send email via SendGrid (PDF attachment)
      9. Update Report.email_sent_at
```

### Report Model

```python
class Report(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reports"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("auth_users.id"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    pdf_s3_key: Mapped[Optional[str]] = mapped_column(String(500))
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    generation_status: Mapped[str] = mapped_column(String(20), default="pending")

    __table_args__ = (
        UniqueConstraint("user_id", "period_start", name="uq_reports_user_period"),
    )
```

### Template sections (`reports/templates/monthly.html`)

1. Header: logo, trader name, period, generation date
2. Summary KPIs: Total In, Total Out, Net, Transaction Count
3. Cashflow chart: embedded as base64 PNG
4. Category breakdown table
5. Top transactions
6. Anomalies flagged
7. Footer: Report ID, generated timestamp

All monetary values rendered via `Money.format()`. Template never does arithmetic.

---

## 16. Domain: Notifications

### Event routing

| Redis Stream Event                    | Channel           | Recipient                      |
|---------------------------------------|-------------------|--------------------------------|
| `transaction.created`                 | WebSocket         | Trader (live dashboard)        |
| `transaction.created` (> GHS 1000)    | SMS               | Trader                         |
| `aml.flagged`                         | SMS + WebSocket   | Trader + internal Slack        |
| `report.ready`                        | Email + WebSocket | Trader                         |
| `kyc.approved`                        | Email + WebSocket | Trader                         |
| `kyc.rejected`                        | Email + WebSocket | Trader                         |
| `login.failed` (>3 times)             | Email             | Trader                         |

### WebSocket

```python
@router.websocket("/ws/notifications")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    manager: WebSocketManager = Depends(get_ws_manager),
):
    user_id = verify_ws_token(token)
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
```

In multi-instance deployments, uses Redis pub/sub for cross-instance broadcast.

---

## 17. Domain: AI Chatbot

### Architecture

LangChain ReAct agent. All tools call analytics domain functions — agent never writes SQL. Connects to Postgres via `tf_ai_readonly` role for pgvector queries only.

### Tools (`app/domains/ai/tools.py`)

```
1. get_cashflow_summary(period: str) → str
2. get_category_breakdown(period: str) → str
3. search_transactions(query: str, limit: int = 10) → str
4. get_anomalies(period: str) → str
5. get_account_balance() → str

All tools return strings. All monetary values are Money.format() strings.
No tool has a write path.
```

### System prompt (`app/domains/ai/guardrails.py`)

```
You are Pivota AI, a financial assistant for traders in Ghana.

Rules:
1. Never modify, delete, or create financial data
2. Never reveal another user's data
3. Always display amounts as "GHS X.XX"
4. If outside tool capabilities, say so clearly
5. Do not speculate without data
6. Use tools to answer — never guess from memory
```

### RAG System

- **Embedder**: triggered by `transaction.created` event, embeds `"{description} {counterparty_name} {category} {amount_str}"`, stores in `transaction_embeddings` (pgvector)
- **Retriever**: cosine similarity search, returns top-K matching transactions

### Streaming Response

```python
@router.post("/ai/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    async def generate():
        async for chunk in agent.astream(input=request.message, config={"user_id": current_user["user_id"]}):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## 18. Workers (Celery)

### Queue assignments

```
ingest      → process_momo_webhook, poll_momo_transactions
reports     → generate_monthly_report, trigger_monthly_reports
analytics   → invalidate_analytics_cache, precompute_weekly_summaries
compliance  → run_aml_check, embed_transaction
notify      → send_email, send_sms, send_push
monitoring  → check_dlq_depth
```

### All tasks must have

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=3600,
    on_failure=publish_to_dlq,
)
```

### DLQ check

Hourly Celery Beat task. If `dlq:events` stream depth > threshold: log ERROR, send Slack alert.

---

## 19. Database Layer

### `app/db/session.py`

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Primary DB — use for all writes."""
    async with AsyncSessionPrimary() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def get_read_db() -> AsyncGenerator[AsyncSession, None]:
    """Read replica — analytics, AI context, reports. Never use for writes."""
    async with AsyncSessionReplica() as session:
        yield session

async def get_ai_db() -> AsyncGenerator[AsyncSession, None]:
    """AI readonly role — pgvector queries only."""
    async with AsyncSessionAI() as session:
        yield session
```

### `app/db/mixins.py`

```python
class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), ...)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=..., ...)

class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

---

## 20. Migrations (Alembic)

### Rules

1. Never run `alembic upgrade head` on app startup — run as separate CI/CD job before deploy
2. Never change an existing migration file — create a new one
3. Schema migrations (`migrations/versions/`) and data migrations (`migrations/data/`) are separate
4. The `amount` column is `NUMERIC(19, 4)` from the first migration — never `Float`

### Critical constraint

```python
# CORRECT
sa.Column("amount", sa.Numeric(precision=19, scale=4), nullable=False)

# ILLEGAL — reject any migration showing this
sa.Column("amount", sa.Float(), ...)
```

### pgvector migration

```python
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table("transaction_embeddings", ...)
    op.execute("""
        CREATE INDEX ON transaction_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
```

---

## 21. Tests

### Architecture

- Test DB: separate Postgres `pivota_test`, fresh per session
- Redis: `fakeredis` for unit tests, real Redis for integration tests
- Celery: `CELERY_TASK_ALWAYS_EAGER = True` — tasks run synchronously
- MoMo client: mocked with `AsyncMock` — never calls real MTN API
- LLM: mocked — tests verify tool calls and prompt construction

### Coverage requirements

| Module                               | Minimum | Key tests                                              |
|--------------------------------------|---------|--------------------------------------------------------|
| `core/money.py`                      | 100%    | Float rejection, arithmetic, format, currency mismatch |
| `core/idempotency.py`                | 100%    | First call, duplicate, TTL, concurrent                 |
| `domains/ingest/webhook_handler.py`  | 95%     | Valid, invalid HMAC, duplicate, amount precision       |
| `domains/compliance/audit_log.py`    | 100%    | Insert-only, no update/delete path                     |
| `domains/compliance/aml_rules.py`    | 90%     | Each rule fires at threshold, passes below             |
| Integration: MoMo flow               | —       | Webhook → transaction → event → notification           |
| Integration: Report flow             | —       | Trigger → generate → store → email                     |

---

## 22. Scripts

```
scripts/seed_dev_data.py     — 3 users, 6 months history, anomalous transactions (dev only)
scripts/replay_dlq.py        — Inspect and replay DLQ entries
scripts/create_db_roles.py   — Run db/roles.sql against target database (idempotent)
scripts/rotate_momo_token.py — Force MoMo OAuth token rotation
```

---

## 23. Docker & Local Dev

### Services (docker-compose.yml)

```
api           — uvicorn app.main:app (port 8000)
worker        — celery worker (queues: ingest,reports,analytics,compliance,notify)
beat          — celery beat (scheduled tasks)
postgres      — pgvector/pgvector:pg16 (port 5432)
postgres_replica — streaming replica (port 5433)
redis         — redis:7-alpine (port 6379)
mailhog       — local email capture (SMTP 1025, UI 8025)
```

### Image notes

- Non-root user `pivota` in production
- Two-stage build: builder + runtime
- Worker uses same image, different CMD

---

## 24. CI/CD

### CI pipeline (ci.yml)

```
1. ruff check . && ruff format --check .
2. mypy app/ --strict
3. pytest tests/ -v --cov=app
4. coverage report --fail-under=85
5. docker build
6. docker push to ECR
```

### CD pipeline

- `main` branch → staging
- Git tag → production
- Migrations (`alembic upgrade head`) run as separate job BEFORE app deploy

### CODEOWNERS — require team lead approval on

```
app/core/money.py
app/core/idempotency.py
app/domains/compliance/
app/db/roles.sql
migrations/versions/
```

---

## 25. Security Architecture

### JWT

- RS256 (RSA 2048-bit)
- Private key: AWS Secrets Manager `pivota/jwt/private_key`
- Access token: 15 min TTL
- Refresh token: 7 day TTL, rotated on every use, stored as bcrypt hash
- Refresh token reuse detection: old token reuse → revoke all user tokens

### MoMo Webhook Security

- HMAC-SHA256 on raw request body
- Timing-safe comparison: `hmac.compare_digest()`
- IP allowlist for MTN IPs

### Postgres Roles

| Role                    | Permissions                                                   |
|-------------------------|---------------------------------------------------------------|
| `pivota_app`        | CRUD on most tables; INSERT-only on `audit_events` + `transactions` |
| `pivota_ai`         | SELECT on `transactions`, `accounts`, `transaction_embeddings` only |
| `pivota_audit`      | SELECT on `audit_events` only                                 |
| `pivota_migrations` | Schema management (Alembic only)                              |

### Data Protection

- KYC documents: SSE-KMS in S3
- TOTP secrets: encrypted at rest via pgcrypto
- TLS 1.2+ enforced everywhere
- No PII in logs — structlog strips `password`, `token`, `secret`, `credit_card`

---

## 26. Data Flow Diagrams

### MoMo Webhook (happy path)

```
MTN MoMo → POST /api/v1/momo/webhook
  API: verify HMAC → idempotency check → enqueue → return 200
  Celery: normalize → Money() → categorize → write DB → audit → publish stream → invalidate cache

Redis Streams: "transactions"
  ├── compliance/stream_consumer → AML rules → flag if triggered
  ├── notifications/stream_consumer → WebSocket push + SMS if > GHS 1000
  └── compliance_tasks.embed_transaction → pgvector
```

### Monthly Report

```
Beat (1st, 08:00 UTC) → trigger task → fan out per user
Per user: check idempotency → fetch analytics → render HTML → PDF → S3 → DB record → email
On failure: retry (max 3, exponential) → DLQ → alert engineering
```

### AI Chat

```
POST /ai/chat → JWT verify → load session
LangChain ReAct:
  → get_cashflow_summary() → analytics.cashflow
  → search_transactions() → rag/retriever → pgvector
  → LLM synthesis
→ SSE stream to frontend → save ChatMessage
```

---

## 27. Environment Variables Reference

```bash
# Application
ENVIRONMENT=development
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://pivota_app:password@localhost:5432/pivota
DATABASE_REPLICA_URL=postgresql+asyncpg://pivota_app:password@localhost:5433/pivota

# Redis
REDIS_URL=redis://localhost:6379

# MTN MoMo
MOMO_BASE_URL=https://sandbox.momodeveloper.mtn.com
MOMO_SUBSCRIPTION_KEY=your_subscription_key
MOMO_WEBHOOK_SECRET=your_hmac_secret
MOMO_ENVIRONMENT=sandbox

# Email
SENDGRID_API_KEY=SG.xxx
SENDGRID_FROM_EMAIL=reports@pivota.com

# SMS
HUBTEL_CLIENT_ID=xxx
HUBTEL_CLIENT_SECRET=xxx
HUBTEL_SENDER_ID=Pivota

# AWS
AWS_REGION=eu-west-1
AWS_ACCESS_KEY_ID=xxx          # Dev only — prod uses IAM role
AWS_SECRET_ACCESS_KEY=xxx      # Dev only
S3_BUCKET_REPORTS=pivota-reports-dev
S3_BUCKET_KYC_DOCS=pivota-kyc-dev

# LLM
ANTHROPIC_API_KEY=sk-ant-xxx
LLM_MODEL=claude-opus-4-5

# Firebase
FIREBASE_CREDENTIALS_JSON={"type":"service_account",...}

# Compliance thresholds
AML_LARGE_TX_THRESHOLD_GHS=5000.00
AML_VELOCITY_MAX_PER_HOUR=10
```

---

## 28. Postgres Role Definitions

**File: `app/db/roles.sql`** — run once at infra setup

```sql
CREATE ROLE pivota_app WITH LOGIN PASSWORD '${APP_PASSWORD}';
GRANT CONNECT ON DATABASE pivota TO pivota_app;
GRANT USAGE ON SCHEMA public TO pivota_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pivota_app;
REVOKE UPDATE, DELETE ON audit_events FROM pivota_app;
REVOKE UPDATE, DELETE ON transactions FROM pivota_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pivota_app;

CREATE ROLE pivota_ai WITH LOGIN PASSWORD '${AI_PASSWORD}';
GRANT CONNECT ON DATABASE pivota TO pivota_ai;
GRANT USAGE ON SCHEMA public TO pivota_ai;
GRANT SELECT ON transactions TO pivota_ai;
GRANT SELECT ON accounts TO pivota_ai;
GRANT SELECT ON transaction_embeddings TO pivota_ai;

CREATE ROLE pivota_audit WITH LOGIN PASSWORD '${AUDIT_PASSWORD}';
GRANT CONNECT ON DATABASE pivota TO pivota_audit;
GRANT USAGE ON SCHEMA public TO pivota_audit;
GRANT SELECT ON audit_events TO pivota_audit;

CREATE ROLE pivota_migrations WITH LOGIN PASSWORD '${MIGRATIONS_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE pivota TO pivota_migrations;
```

---

## 29. Redis Key Conventions

```
# Idempotency (DB: 2, TTL: 24h)
idempotency:momo:{momo_transaction_id}
idempotency:report:{user_id}:{period}

# Cache (DB: 0)
cache:balance:{account_id}                    TTL: 60s
cache:analytics:summary:{user_id}:{period}    TTL: 300s
cache:analytics:cashflow:{user_id}:{period}   TTL: 300s
cache:analytics:categories:{user_id}:{period} TTL: 300s

# MoMo OAuth
momo:access_token                             TTL: token_expiry - 60s

# Rate limiting (DB: 3, TTL: 60s window)
ratelimit:api:{user_id}
ratelimit:auth:{ip_address}
ratelimit:webhook:{ip_address}

# Sessions (DB: 4, TTL: 7 days)
session:{user_id}:{session_id}

# Redis Streams (consumed by consumer groups)
transactions      # transaction.created
compliance        # aml.flagged, kyc.approved, kyc.rejected
reports           # report.ready
auth              # login.failed
dlq:events        # all failed tasks
```

---

## 30. Error Handling Strategy

### HTTP error shape

```json
{
  "error": {
    "code": "DUPLICATE_TRANSACTION",
    "message": "This transaction has already been processed.",
    "request_id": "uuid-here"
  }
}
```

### FastAPI exception handlers

```python
@app.exception_handler(FloatMoneyError)
async def float_money_handler(request, exc):
    logger.error("FloatMoneyError reached API layer", error=str(exc))
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR"}})

@app.exception_handler(WebhookSignatureError)
async def webhook_sig_handler(request, exc):
    return JSONResponse(status_code=403, content={"error": {"code": "INVALID_SIGNATURE"}})

@app.exception_handler(DuplicateTransactionError)
async def duplicate_tx_handler(request, exc):
    return JSONResponse(status_code=200, content={"status": "duplicate"})

@app.exception_handler(ComplianceHoldError)
async def compliance_hold_handler(request, exc):
    return JSONResponse(status_code=422, content={"error": {"code": "COMPLIANCE_HOLD"}})
```

### Celery failure handler

```python
def on_task_failure(exc, task_id, args, kwargs, einfo):
    publish_sync("dlq:events", "job.failed", {
        "task_id": task_id,
        "task_name": einfo.type.__name__,
        "args": args,
        "kwargs": kwargs,
        "error": str(exc),
        "traceback": str(einfo),
    })
```

---

## 31. Getting Started (Local Dev)

```bash
# 1. Clone
git clone git@github.com:your-org/pivota-backend.git
cd pivota-backend

# 2. Generate JWT keys
mkdir -p keys
openssl genrsa -out keys/private.pem 2048
openssl rsa -in keys/private.pem -pubout -out keys/public.pem

# 3. Configure env
cp docker/.env.example docker/.env
# Edit with your MTN MoMo sandbox keys and Anthropic API key

# 4. Start services
docker compose -f docker/docker-compose.yml up -d

# 5. Run migrations
docker compose exec api alembic upgrade head

# 6. Create Postgres roles
docker compose exec api python scripts/create_db_roles.py --env development

# 7. Seed dev data
docker compose exec api python scripts/seed_dev_data.py

# 8. Install pre-commit hooks
pip install pre-commit && pre-commit install

# 9. Run tests
pytest tests/ -v

# API:      http://localhost:8000
# Docs:     http://localhost:8000/docs  (dev only)
# Mailhog:  http://localhost:8025
```

### Testing webhooks locally

```bash
ngrok http 8000
# Register https://your-ngrok-url.ngrok.io/api/v1/momo/webhook
# in the MTN MoMo Developer Portal
```

---

*This document is the single source of truth. Update it when adding domains, changing core patterns, or modifying critical rules. CODEOWNERS requires team lead approval on changes to this file.*
