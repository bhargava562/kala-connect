-- PostgreSQL schema used by SQLAlchemy. Apply before startup in hosted environments.
BEGIN;
CREATE TABLE IF NOT EXISTS users (
 id VARCHAR(64) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE,
 name VARCHAR(120) NOT NULL, role VARCHAR(20) NOT NULL,
 password TEXT NOT NULL,
 CONSTRAINT valid_role CHECK (role IN ('artist','customer','operator','admin'))
);
CREATE TABLE IF NOT EXISTS sessions (
 id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL,
 expires VARCHAR(40) NOT NULL
);
-- Version 1 document store. Record kinds: artist, booking, notification, audit, report.
-- Booking quotes, consent, approvals, case state, milestones and history are persisted
-- together atomically. Only the API database role should access these tables.
CREATE TABLE IF NOT EXISTS records (
 id VARCHAR(64) PRIMARY KEY, kind VARCHAR(32) NOT NULL, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_records_kind ON records(kind);
COMMIT;
