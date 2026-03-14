-- Pivota Postgres Role Definitions
-- Run once at infra setup via: python scripts/create_db_roles.py
-- Idempotent — roles created with IF NOT EXISTS where supported.

-- Application role (primary API + workers)
CREATE ROLE pivota_app WITH LOGIN PASSWORD '${APP_PASSWORD}';
GRANT CONNECT ON DATABASE pivota TO pivota_app;
GRANT USAGE ON SCHEMA public TO pivota_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pivota_app;
-- audit_events: INSERT only — audit log is immutable
REVOKE UPDATE, DELETE ON audit_events FROM pivota_app;
-- transactions: INSERT only — append-only ledger, use reversals for corrections
REVOKE UPDATE, DELETE ON transactions FROM pivota_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pivota_app;

-- AI readonly role (LangChain agent, pgvector queries only)
CREATE ROLE pivota_ai WITH LOGIN PASSWORD '${AI_PASSWORD}';
GRANT CONNECT ON DATABASE pivota TO pivota_ai;
GRANT USAGE ON SCHEMA public TO pivota_ai;
GRANT SELECT ON transactions TO pivota_ai;
GRANT SELECT ON accounts TO pivota_ai;
GRANT SELECT ON transaction_embeddings TO pivota_ai;

-- Audit readonly role (compliance officers, external auditors)
CREATE ROLE pivota_audit WITH LOGIN PASSWORD '${AUDIT_PASSWORD}';
GRANT CONNECT ON DATABASE pivota TO pivota_audit;
GRANT USAGE ON SCHEMA public TO pivota_audit;
GRANT SELECT ON audit_events TO pivota_audit;

-- Migrations role (Alembic schema management only)
CREATE ROLE pivota_migrations WITH LOGIN PASSWORD '${MIGRATIONS_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE pivota TO pivota_migrations;
