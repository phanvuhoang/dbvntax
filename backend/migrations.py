"""
Idempotent schema migrations for the canonical document layer.

Runs at FastAPI startup (after the existing migrations in `main.lifespan`).
Every statement uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS so it is safe
to run repeatedly and against a live production DB.

Tables touched (all in the canonical `postgres` database, `public` schema):
- documents       (ADD COLUMNS: source, source_url, source_site, content_hash,
                                ai_summary, ai_summary_at, ai_tags, ai_implications,
                                ai_review_status, ai_review_at, ai_review_by,
                                quality_score, html_source, updated_at,
                                effective_status, effective_confidence,
                                supersedes_so_hieu, superseded_by_so_hieu)
- cong_van        (ADD COLUMNS: source, source_url, source_site, content_hash,
                                ai_summary, ai_summary_at, ai_tags, ai_implications,
                                ai_review_status, ai_review_at, ai_review_by,
                                quality_score, html_source, updated_at,
                                is_anchor, importance)

New tables:
- documents_audit          — every create/update/status-change for canonical ops
- documents_ai_review      — review queue for AI-generated metadata
- documents_watchlist      — change-alert subscriptions (per user/email + filter)
- documents_export_keys    — API keys for downstream apps consuming the canonical API
- documents_sync_cursor    — server-side bookkeeping (last canonical change ts)

All indexes are CREATE INDEX IF NOT EXISTS.
"""
from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

log = logging.getLogger("vntaxdb.backend.migrations")


MIGRATION_STATEMENTS: list[str] = [
    # --- extensions ---
    "CREATE EXTENSION IF NOT EXISTS pgcrypto",        # gen_random_uuid()
    "CREATE EXTENSION IF NOT EXISTS unaccent",
    "CREATE EXTENSION IF NOT EXISTS vector",

    # --- documents canonical fields ---
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source VARCHAR(40)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_url TEXT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_site VARCHAR(80)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash CHAR(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS html_source TEXT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_summary TEXT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_summary_at TIMESTAMPTZ",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_tags TEXT[] DEFAULT '{}'::text[]",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_implications JSONB",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_review_status VARCHAR(20)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_review_at TIMESTAMPTZ",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS ai_review_by INT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS quality_score SMALLINT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS effective_status VARCHAR(30)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS effective_confidence REAL",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS supersedes_so_hieu VARCHAR(200)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS superseded_by_so_hieu VARCHAR(200)",

    # --- cong_van canonical fields (parity with documents) ---
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS source VARCHAR(40)",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS source_url TEXT",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS source_site VARCHAR(80)",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS content_hash CHAR(64)",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS html_source TEXT",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS ai_summary TEXT",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS ai_summary_at TIMESTAMPTZ",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS ai_tags TEXT[] DEFAULT '{}'::text[]",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS ai_implications JSONB",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS ai_review_status VARCHAR(20)",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS ai_review_at TIMESTAMPTZ",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS ai_review_by INT",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS quality_score SMALLINT",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS is_anchor BOOLEAN DEFAULT FALSE",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS importance SMALLINT DEFAULT 4",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS effective_status VARCHAR(30)",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS effective_confidence REAL",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS supersedes_so_hieu VARCHAR(200)",
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS superseded_by_so_hieu VARCHAR(200)",

    # --- triggers on update_at (use a generic trigger function) ---
    """
    CREATE OR REPLACE FUNCTION canonical_touch_updated_at() RETURNS trigger AS $$
    BEGIN
      NEW.updated_at = NOW();
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents",
    """
    CREATE TRIGGER trg_documents_updated_at
      BEFORE UPDATE ON documents
      FOR EACH ROW EXECUTE FUNCTION canonical_touch_updated_at()
    """,
    "DROP TRIGGER IF EXISTS trg_cong_van_updated_at ON cong_van",
    """
    CREATE TRIGGER trg_cong_van_updated_at
      BEFORE UPDATE ON cong_van
      FOR EACH ROW EXECUTE FUNCTION canonical_touch_updated_at()
    """,

    # --- audit log ---
    """
    CREATE TABLE IF NOT EXISTS documents_audit (
        id          BIGSERIAL PRIMARY KEY,
        source      VARCHAR(20) NOT NULL,          -- 'documents' | 'cong_van'
        doc_id      INT NOT NULL,
        event       VARCHAR(40) NOT NULL,          -- created|updated|superseded|anchor_marked|effective_status_changed|deleted|ai_review_decided
        actor_id    INT,
        actor_kind  VARCHAR(20) DEFAULT 'user',    -- user|system|api_key
        actor_label TEXT,
        old_values  JSONB,
        new_values  JSONB,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_documents_audit_doc ON documents_audit(source, doc_id)",
    "CREATE INDEX IF NOT EXISTS idx_documents_audit_created ON documents_audit(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_documents_audit_event ON documents_audit(event)",

    # --- AI review queue ---
    """
    CREATE TABLE IF NOT EXISTS documents_ai_review (
        id          BIGSERIAL PRIMARY KEY,
        source      VARCHAR(20) NOT NULL,
        doc_id      INT NOT NULL,
        kind        VARCHAR(30) NOT NULL,           -- summary|tags|implications|effective_status|metadata
        proposed    JSONB NOT NULL,
        confidence  REAL,
        status      VARCHAR(20) DEFAULT 'pending',  -- pending|accepted|rejected|auto_accepted
        decided_by  INT,
        decided_at  TIMESTAMPTZ,
        notes       TEXT,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_documents_ai_review_status ON documents_ai_review(status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_documents_ai_review_doc ON documents_ai_review(source, doc_id)",

    # --- watchlist (change alerts) ---
    """
    CREATE TABLE IF NOT EXISTS documents_alert_subscriptions (
        id          BIGSERIAL PRIMARY KEY,
        user_id     INT,
        email       TEXT,
        filter      JSONB NOT NULL,                 -- {sac_thue:["TNDN"], loai:["TT","ND"], anchor_only:true, ...}
        events      TEXT[] DEFAULT ARRAY['created','updated','superseded'],
        last_seen_at TIMESTAMPTZ DEFAULT NOW(),
        active      BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_alerts_user ON documents_alert_subscriptions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_active ON documents_alert_subscriptions(active) WHERE active",

    # --- API keys for downstream apps consuming the canonical API ---
    """
    CREATE TABLE IF NOT EXISTS documents_export_keys (
        id              BIGSERIAL PRIMARY KEY,
        token_hash      CHAR(64) UNIQUE NOT NULL,    -- sha256(token)
        prefix          VARCHAR(12) NOT NULL,        -- first 8 chars of token, for display
        app_name        VARCHAR(80) NOT NULL,        -- e.g. 'taxlegal', 'taxconsult', 'legalai-indexer'
        scopes          TEXT[] DEFAULT ARRAY['read'],-- read|write|webhook
        webhook_url     TEXT,
        webhook_secret  TEXT,
        last_used_at    TIMESTAMPTZ,
        revoked_at      TIMESTAMPTZ,
        created_by      INT,
        created_at      TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_export_keys_active ON documents_export_keys(token_hash) WHERE revoked_at IS NULL",

    # --- sync cursor / bookkeeping ---
    """
    CREATE TABLE IF NOT EXISTS documents_sync_cursor (
        consumer    VARCHAR(80) PRIMARY KEY,         -- e.g. 'taxlegal', 'legalai-indexer'
        last_ts     TIMESTAMPTZ,
        last_id     BIGINT,
        notes       TEXT,
        updated_at  TIMESTAMPTZ DEFAULT NOW()
    )
    """,

    # --- webhook delivery log ---
    """
    CREATE TABLE IF NOT EXISTS documents_webhook_deliveries (
        id          BIGSERIAL PRIMARY KEY,
        key_id      INT REFERENCES documents_export_keys(id) ON DELETE CASCADE,
        event       VARCHAR(40),
        payload     JSONB,
        url         TEXT,
        status_code INT,
        response    TEXT,
        attempt     SMALLINT DEFAULT 1,
        delivered_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_event ON documents_webhook_deliveries(event, delivered_at DESC)",

    # --- helpful covering indexes used by the canonical sync API ---
    "CREATE INDEX IF NOT EXISTS idx_documents_updated_at ON documents(updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cong_van_updated_at ON cong_van(updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source) WHERE source IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_cong_van_source ON cong_van(source) WHERE source IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash) WHERE content_hash IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_cong_van_content_hash ON cong_van(content_hash) WHERE content_hash IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_source_url ON documents(source_url) WHERE source_url IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_cong_van_source_url ON cong_van(source_url) WHERE source_url IS NOT NULL",
]


async def run_migrations(engine: AsyncEngine) -> None:
    """Run every migration statement once at startup. Errors are logged but non-fatal."""
    async with AsyncSession(engine) as db:
        ok = 0
        skipped = 0
        for sql in MIGRATION_STATEMENTS:
            try:
                await db.execute(text(sql))
                await db.commit()
                ok += 1
            except Exception as e:  # noqa: BLE001
                await db.rollback()
                skipped += 1
                log.warning(
                    "migration step skipped (%s) — %s",
                    sql.strip().split("\n", 1)[0][:80],
                    str(e)[:200],
                )
        log.info("canonical migrations done: %d ok, %d skipped", ok, skipped)
