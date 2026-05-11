"""
dbvntax `backend/` — overhaul layer (additive, May 2026).

All files in this package extend the existing flat-module FastAPI app
(`main.py`, `database.py`, `search.py`, `ai.py`, `rag.py`) without replacing it.

The architecture decision implemented here:
- dbvntax's `documents` and `cong_van` (in DB `postgres`) are the CANONICAL source.
- taxlegal's `law_documents_v2` and legalai's `law_documents`/`law_chunks` are
  treated as downstream caches/indices that pull from the canonical sync API
  exposed in `backend.canonical`.
- All ingestion paths (upload / paste / URL / TVPL / LuatVietnam / bulk) feed
  the same normalized pipeline in `backend.ingest`.
- The AI layer in `backend.ai_extras` reuses existing embeddings and adds
  implication extraction, document comparison, and a review queue.

Migrations are run on FastAPI startup via `backend.migrations.run_migrations`.
Every statement is idempotent (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`).
"""
