-- NINA Console — PostgreSQL schema
-- Run once against your database: psql $DATABASE_URL -f scripts/db_init.sql

CREATE TABLE IF NOT EXISTS nina_orgs (
    id                     TEXT    PRIMARY KEY,
    name                   TEXT    NOT NULL,
    owner_email            TEXT,
    dashboard_token_digest TEXT,
    dashboard_token_prefix TEXT,
    token_rotated_at       TEXT,
    created_at             TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS nina_sites (
    id              TEXT    PRIMARY KEY,
    org_id          TEXT    NOT NULL REFERENCES nina_orgs(id),
    name            TEXT    NOT NULL,
    base_url        TEXT    NOT NULL,
    plan            TEXT    NOT NULL DEFAULT 'free',
    currency        TEXT    NOT NULL DEFAULT 'INR',
    locales         TEXT    NOT NULL DEFAULT '["en"]',
    markets         TEXT    NOT NULL DEFAULT '[]',
    allowed_origins TEXT    NOT NULL DEFAULT '[]',
    verification    TEXT    NOT NULL DEFAULT '{"sandbox":"verified","production":"pending"}',
    agent_contract  TEXT,
    llm_config      TEXT,
    wa_number_id    TEXT,
    created_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS nina_sites_org_id ON nina_sites(org_id);
CREATE INDEX IF NOT EXISTS nina_sites_wa_number_id ON nina_sites(wa_number_id) WHERE wa_number_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS nina_api_keys (
    id          TEXT    PRIMARY KEY,
    site_id     TEXT    NOT NULL REFERENCES nina_sites(id),
    environment TEXT    NOT NULL,
    kind        TEXT    NOT NULL,
    prefix      TEXT    NOT NULL,
    digest      TEXT    NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS nina_api_keys_site_id  ON nina_api_keys(site_id);
CREATE INDEX IF NOT EXISTS nina_api_keys_digest   ON nina_api_keys(digest) WHERE NOT revoked;

CREATE TABLE IF NOT EXISTS nina_cli_tokens (
    id         TEXT    PRIMARY KEY,
    org_id     TEXT    NOT NULL REFERENCES nina_orgs(id),
    label      TEXT    NOT NULL,
    digest     TEXT    NOT NULL,
    prefix     TEXT    NOT NULL,
    revoked    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TEXT    NOT NULL
);

-- Capped at 500 rows via application logic (oldest deleted on overflow)
CREATE TABLE IF NOT EXISTS nina_webhook_events (
    id          SERIAL  PRIMARY KEY,
    event_type  TEXT    NOT NULL,
    payload     TEXT    NOT NULL,
    received_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS nina_usage (
    site_id      TEXT    PRIMARY KEY REFERENCES nina_sites(id),
    calls        INTEGER NOT NULL DEFAULT 0,
    last_call_at TEXT,
    period       TEXT    -- YYYYMM billing period, e.g. '202601'; NULL = pre-period data (treat as 0)
);
