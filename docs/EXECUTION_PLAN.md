# Pivota – Execution Plan & Sprints

This document defines the **step-by-step execution plan** for building Pivota once the required skills are in place.  
It is intentionally staged to avoid premature complexity and technical debt.

---

## Phase 0 — Skill Readiness (Pre-Build Phase)

**Status:** Mandatory before coding  
**Duration:** 2–4 weeks (parallel with school)

### Objective
Build enough depth to avoid guessing while designing fintech systems.

### Daily Focus (1–2 hours/day)
- FastAPI fundamentals (routing, dependencies, middleware)
- SQLAlchemy ORM (models, relationships, sessions)
- PostgreSQL basics
- REST & HTTP semantics (status codes, idempotency)
- JWT authentication & authorization
- Linux basics (users, permissions, processes)
- Deployment basics (Docker, env vars)

### Rule
Do **not** start Pivota implementation during this phase.

---

## Phase 1 — Skeleton & Discipline

**Duration:** 1 week  
**Goal:** A clean, deployable backend skeleton

### Deliverables
- Repository initialized
- FastAPI app running
- `/health` endpoint available
- Environment configuration in place
- CI pipeline passing
- Documentation committed

### Daily Breakdown
- **Day 1:** Repo setup, FastAPI bootstrap
- **Day 2:** Environment config, settings handling
- **Day 3:** Dockerfile & local run
- **Day 4:** Deployment dry run
- **Day 5:** Documentation review & cleanup

### Rule
No business logic. No shortcuts.

---

## Phase 2 — Core Foundations

**Duration:** 2 weeks  
**Goal:** A secure, stable backend base

### Week 1
- User model
- Authentication (JWT)
- Role separation (merchant, admin)
- Database migrations

### Week 2
- Merchant accounts
- Business profiles
- Audit logging
- Rate limiting & basic protections

### Rule
If auth or data integrity is weak, stop and fix it.

---

## Phase 3 — Transaction Engine (Critical Phase)

**Duration:** 3 weeks  
**Goal:** Reliable transaction tracking with idempotency

### Focus Areas
- Transaction model
- External transaction IDs
- Idempotency enforcement
- Duplicate handling
- Reconciliation logic

### Daily Discipline
- One invariant per day
- One failure case per day

### Rule
If you can’t explain the logic on paper, do not code it.

---

## Phase 4 — MoMo Integration

**Duration:** 2 weeks  
**Goal:** Safe and resilient payment integration

### Scope
- Collections API
- Disbursement API
- Webhooks
- Signature verification
- Retry & timeout handling
- Downtime recovery logic

### Rule
Move slowly. This is where fintech systems break.

---

## Phase 5 — Reporting & Documents

**Duration:** 1–2 weeks  
**Goal:** Turn infrastructure into a usable product

### Features
- Monthly summaries
- Transaction notifications (email)
- PDF exports
- CSV downloads

---

## Phase 6 — AI Layer (Optional, Last)

**Duration:** Open-ended  
**Goal:** Add intelligence without compromising stability

### Examples
- Transaction explanations
- Spending insights
- Anomaly detection
- Natural language summaries

### Rule
AI is a feature, not the foundation.

---

## Non-Negotiable Rule

If you ever say:
> “I’ll fix this later”

You are introducing technical debt.

Fix it or stop.

---

## Review Cadence

- Weekly: Architecture & decisions review
- Monthly: Security & failure scenarios review
- Always: Prefer clarity over speed
