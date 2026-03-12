-- TraderFlow Postgres Role Definitions
-- Run once at infra setup via: python scripts/create_db_roles.py
-- Idempotent — roles created with IF NOT EXISTS where supported.

-- Application role (primary API + workers)
CREATE ROLE traderflow_app WITH LOGIN PASSWORD '${APP_PASSWORD}';
GRANT CONNECT ON DATABASE traderflow TO traderflow_app;
GRANT USAGE ON SCHEMA public TO traderflow_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO traderflow_app;
-- audit_events: INSERT only — audit log is immutable
REVOKE UPDATE, DELETE ON audit_events FROM traderflow_app;
-- transactions: INSERT only — append-only ledger, use reversals for corrections
REVOKE UPDATE, DELETE ON transactions FROM traderflow_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO traderflow_app;

-- AI readonly role (LangChain agent, pgvector queries only)
CREATE ROLE traderflow_ai WITH LOGIN PASSWORD '${AI_PASSWORD}';
GRANT CONNECT ON DATABASE traderflow TO traderflow_ai;
GRANT USAGE ON SCHEMA public TO traderflow_ai;
GRANT SELECT ON transactions TO traderflow_ai;
GRANT SELECT ON accounts TO traderflow_ai;
GRANT SELECT ON transaction_embeddings TO traderflow_ai;

-- Audit readonly role (compliance officers, external auditors)
CREATE ROLE traderflow_audit WITH LOGIN PASSWORD '${AUDIT_PASSWORD}';
GRANT CONNECT ON DATABASE traderflow TO traderflow_audit;
GRANT USAGE ON SCHEMA public TO traderflow_audit;
GRANT SELECT ON audit_events TO traderflow_audit;

-- Migrations role (Alembic schema management only)
CREATE ROLE traderflow_migrations WITH LOGIN PASSWORD '${MIGRATIONS_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE traderflow TO traderflow_migrations;
