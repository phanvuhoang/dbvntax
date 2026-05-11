"""
Canonical document sync API for dbvntax.

This module exposes /api/v1/canonical/* endpoints that other apps
(taxlegal, taxconsult, legalai, ...) consume as their single source of
truth for Vietnamese tax/legal documents.

Authentication: X-Sync-Token header. Tokens are managed via
documents_export_keys and resolved via backend.common.resolve_sync_key.
Admin JWT (role='admin') is also accepted as a fallback for browser usage.

All routes are read-only except the optional /heartbeat ping.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from backend.common import (
    resolve_sync_key,
    write_audit,
    serialize_row,
    parse_iso,
    fe_sac_thue,
)

log = logging.getLogger("vntaxdb.canonical")

router = APIRouter(prefix="/api/v1/canonical", tags=["canonical"])


# ----------------------------------------------------------------------
# Auth dependency
# ----------------------------------------------------------------------
async def require_sync_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept either a valid X-Sync-Token OR an admin JWT in Authorization."""
    raw = request.headers.get("X-Sync-Token") or request.headers.get("x-sync-token")
    if raw:
        key = await resolve_sync_key(db, raw)
        if not key:
            raise HTTPException(401, "Invalid sync token")
        # Update last_used_at
        try:
            await db.execute(
                text("UPDATE documents_export_keys SET last_used_at=NOW() WHERE id=:i"),
                {"i": key["id"]},
            )
            await db.commit()
        except Exception:
            pass
        return {"kind": "sync_key", "id": key["id"], "name": key.get("name"), "app": key.get("app_name")}

    # Fallback: admin JWT
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from main import decode_token  # late import to avoid cycle
            payload = decode_token(auth[7:])
            if payload.get("role") == "admin":
                return {"kind": "admin", "email": payload.get("email")}
        except Exception:
            pass

    raise HTTPException(401, "Missing or invalid X-Sync-Token")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
async def _fetch_document(db: AsyncSession, source: str, doc_id: int) -> Optional[dict]:
    if source == "documents":
        q = text("""
            SELECT id, so_hieu, ten, loai, sac_thue, ngay_ban_hanh,
                   hieu_luc_tu AS ngay_hieu_luc,
                   het_hieu_luc_tu,
                   co_quan AS co_quan_ban_hanh,
                   nguoi_ky, ngay_cong_bao, so_cong_bao,
                   tom_tat, noi_dung,
                   COALESCE(tvpl_url, link_tvpl) AS tvpl_url,
                   is_anchor,
                   source, source_url, source_site, content_hash,
                   ai_summary, ai_tags, ai_implications, ai_review_status,
                   quality_score, effective_status, effective_confidence,
                   supersedes_so_hieu, superseded_by_so_hieu,
                   tinh_trang, chu_de, keywords,
                   created_at, updated_at
            FROM documents WHERE id=:i
        """)
    elif source == "cong_van":
        q = text("""
            SELECT id, so_hieu, ten, sac_thue, ngay_ban_hanh,
                   co_quan AS co_quan_ban_hanh,
                   noi_dung_day_du AS noi_dung,
                   link_nguon AS tvpl_url,
                   is_anchor, importance,
                   source, source_url, source_site, content_hash,
                   ai_summary, ai_tags, ai_implications, ai_review_status,
                   quality_score, effective_status, effective_confidence,
                   supersedes_so_hieu, superseded_by_so_hieu,
                   tinh_trang, chu_de, keywords,
                   created_at, updated_at
            FROM cong_van WHERE id=:i
        """)
    else:
        return None
    r = await db.execute(q, {"i": doc_id})
    row = r.mappings().first()
    if not row:
        return None
    return serialize_row(dict(row))


# ----------------------------------------------------------------------
# GET /api/v1/canonical/heartbeat
# ----------------------------------------------------------------------
@router.get("/heartbeat")
async def heartbeat(
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    r1 = await db.execute(text("SELECT COUNT(*) FROM documents"))
    r2 = await db.execute(text("SELECT COUNT(*) FROM cong_van"))
    r3 = await db.execute(text("SELECT MAX(updated_at) FROM documents"))
    r4 = await db.execute(text("SELECT MAX(updated_at) FROM cong_van"))
    return {
        "ok": True,
        "documents": r1.scalar() or 0,
        "cong_van": r2.scalar() or 0,
        "documents_updated_at": serialize_row({"v": r3.scalar()})["v"],
        "cong_van_updated_at": serialize_row({"v": r4.scalar()})["v"],
        "caller": auth,
    }


# ----------------------------------------------------------------------
# GET /api/v1/canonical/documents
#   Cursor-based pull. since= ISO, source=documents|cong_van|all
# ----------------------------------------------------------------------
@router.get("/documents")
async def list_documents(
    source: str = Query("documents", regex="^(documents|cong_van|all)$"),
    since: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    cursor: Optional[str] = None,  # "<source>:<updated_at_iso>:<id>"
    sac_thue: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    since_dt = parse_iso(since)
    cursor_dt: Optional[datetime] = None
    cursor_id: Optional[int] = None
    cursor_src: Optional[str] = None
    if cursor:
        try:
            parts = cursor.split(":", 2)
            cursor_src = parts[0]
            cursor_dt = parse_iso(parts[1])
            cursor_id = int(parts[2])
        except Exception:
            raise HTTPException(400, "Invalid cursor")

    sources = [source] if source != "all" else ["documents", "cong_van"]
    items: list[dict] = []

    for src in sources:
        if cursor and cursor_src and src != cursor_src and source == "all":
            # When paging "all", we only continue the current cursor source
            continue

        params: dict = {"l": limit}
        wheres = []
        if since_dt:
            wheres.append("updated_at >= :since")
            params["since"] = since_dt
        if cursor_dt and cursor_id and src == cursor_src:
            wheres.append("(updated_at, id) > (:cdt, :cid)")
            params["cdt"] = cursor_dt
            params["cid"] = cursor_id
        if sac_thue:
            wheres.append(":sac = ANY(sac_thue)")
            params["sac"] = sac_thue

        where_sql = (" WHERE " + " AND ".join(wheres)) if wheres else ""
        if src == "documents":
            select_sql = (
                "id, so_hieu, ten, loai, sac_thue, ngay_ban_hanh, "
                "hieu_luc_tu AS ngay_hieu_luc, nguoi_ky, tom_tat, "
                "co_quan AS co_quan_ban_hanh, "
                "COALESCE(tvpl_url, link_tvpl) AS tvpl_url, is_anchor, "
                "source, source_url, source_site, content_hash, "
                "ai_summary, ai_tags, ai_review_status, effective_status, "
                "supersedes_so_hieu, superseded_by_so_hieu, created_at, updated_at"
            )
        else:  # cong_van
            select_sql = (
                "id, so_hieu, ten, sac_thue, ngay_ban_hanh, importance, "
                "co_quan AS co_quan_ban_hanh, "
                "link_nguon AS tvpl_url, is_anchor, "
                "source, source_url, source_site, content_hash, "
                "ai_summary, ai_tags, ai_review_status, effective_status, "
                "supersedes_so_hieu, superseded_by_so_hieu, created_at, updated_at"
            )

        q = text(f"""
            SELECT '{src}' AS _src, {select_sql}
            FROM {src}
            {where_sql}
            ORDER BY updated_at NULLS LAST, id
            LIMIT :l
        """)
        r = await db.execute(q, params)
        rows = [serialize_row(dict(m)) for m in r.mappings().all()]
        items.extend(rows)

    # Build next cursor
    next_cursor = None
    if items and len(items) >= limit:
        last = items[-1]
        if last.get("updated_at") and last.get("id") is not None:
            next_cursor = f"{last['_src']}:{last['updated_at']}:{last['id']}"

    return {"items": items, "count": len(items), "next_cursor": next_cursor}


# ----------------------------------------------------------------------
# GET /api/v1/canonical/documents/{source}/{id}
# ----------------------------------------------------------------------
@router.get("/documents/{source}/{doc_id}")
async def get_document(
    source: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    if source not in ("documents", "cong_van"):
        raise HTTPException(404, "Unknown source")
    doc = await _fetch_document(db, source, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    return {"source": source, "document": doc}


# ----------------------------------------------------------------------
# GET /api/v1/canonical/documents/{source}/{id}/chunks
# ----------------------------------------------------------------------
@router.get("/documents/{source}/{doc_id}/chunks")
async def get_chunks(
    source: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    """Return article-level RAG chunks. For 'documents' we use the articles
    table. For 'cong_van' we synthesize a single chunk from noi_dung."""
    if source == "documents":
        try:
            r = await db.execute(text("""
                SELECT id, document_id, dieu_so, dieu_ten, noi_dung, ngay_hieu_luc
                FROM articles WHERE document_id=:d ORDER BY id
            """), {"d": doc_id})
            return {"chunks": [serialize_row(dict(m)) for m in r.mappings().all()]}
        except Exception as e:
            log.warning("articles table query failed: %s", e)
            return {"chunks": []}
    elif source == "cong_van":
        r = await db.execute(text("SELECT id, noi_dung FROM cong_van WHERE id=:i"), {"i": doc_id})
        row = r.mappings().first()
        if not row:
            return {"chunks": []}
        return {"chunks": [{"id": row["id"], "noi_dung": row["noi_dung"]}]}
    raise HTTPException(404, "Unknown source")


# ----------------------------------------------------------------------
# GET /api/v1/canonical/documents/{source}/{id}/related
# ----------------------------------------------------------------------
@router.get("/documents/{source}/{doc_id}/related")
async def get_related(
    source: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    """Relations via doc_relations table (documents only)."""
    if source != "documents":
        return {"relations": []}
    r = await db.execute(text("""
        SELECT id, source_id, target_id, target_so_hieu, relation_type, ghi_chu, verified, created_at
        FROM doc_relations WHERE source_id=:i OR target_id=:i
        ORDER BY relation_type, created_at
    """), {"i": doc_id})
    return {"relations": [serialize_row(dict(m)) for m in r.mappings().all()]}


# ----------------------------------------------------------------------
# GET /api/v1/canonical/documents/{source}/{id}/chain
#   { predecessors: [], successors: [], amendments: [] }
# ----------------------------------------------------------------------
@router.get("/documents/{source}/{doc_id}/chain")
async def get_chain(
    source: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    if source not in ("documents", "cong_van"):
        raise HTTPException(404, "Unknown source")
    doc = await _fetch_document(db, source, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")

    so_hieu = doc.get("so_hieu")
    predecessors: list[dict] = []
    successors: list[dict] = []
    amendments: list[dict] = []

    # Predecessor: this doc supersedes X → find X
    if doc.get("supersedes_so_hieu"):
        r = await db.execute(
            text(f"SELECT id, so_hieu, ten, ngay_ban_hanh, effective_status FROM {source} WHERE so_hieu=:s"),
            {"s": doc["supersedes_so_hieu"]},
        )
        predecessors.extend([serialize_row(dict(m)) for m in r.mappings().all()])

    # Successor: X is superseded by this doc → find X where supersedes/superseded_by points back
    if so_hieu:
        r = await db.execute(
            text(f"SELECT id, so_hieu, ten, ngay_ban_hanh, effective_status FROM {source} WHERE (supersedes_so_hieu=:s OR superseded_by_so_hieu=:s)"),
            {"s": so_hieu},
        )
        for m in r.mappings().all():
            m = dict(m)
            if m["id"] == doc_id:
                continue
            successors.append(serialize_row(m))

    # Amendments: from doc_relations (documents only)
    if source == "documents":
        try:
            r = await db.execute(text("""
                SELECT id, source_id, target_id, target_so_hieu, relation_type, ghi_chu
                FROM doc_relations
                WHERE (source_id=:i OR target_id=:i)
                  AND relation_type IN ('amends','amended_by','supersedes','superseded_by','replaces','replaced_by')
            """), {"i": doc_id})
            amendments = [serialize_row(dict(m)) for m in r.mappings().all()]
        except Exception:
            pass

    return {
        "document": {"id": doc_id, "source": source, "so_hieu": so_hieu, "ten": doc.get("ten")},
        "predecessors": predecessors,
        "successors": successors,
        "amendments": amendments,
    }


# ----------------------------------------------------------------------
# GET /api/v1/canonical/documents/{source}/{id}/ai
# ----------------------------------------------------------------------
@router.get("/documents/{source}/{doc_id}/ai")
async def get_ai_meta(
    source: str,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    if source not in ("documents", "cong_van"):
        raise HTTPException(404, "Unknown source")
    r = await db.execute(
        text(f"SELECT id, so_hieu, ai_summary, ai_tags, ai_implications, ai_review_status, quality_score, updated_at FROM {source} WHERE id=:i"),
        {"i": doc_id},
    )
    row = r.mappings().first()
    if not row:
        raise HTTPException(404, "Not found")
    return serialize_row(dict(row))


# ----------------------------------------------------------------------
# GET /api/v1/canonical/documents/{source}/{id}/export?format=md|json|html
# ----------------------------------------------------------------------
@router.get("/documents/{source}/{doc_id}/export")
async def export_document(
    source: str,
    doc_id: int,
    format: str = Query("json", regex="^(json|md|html)$"),
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    if source not in ("documents", "cong_van"):
        raise HTTPException(404, "Unknown source")
    doc = await _fetch_document(db, source, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")

    if format == "json":
        return JSONResponse(doc)

    title = doc.get("ten") or doc.get("so_hieu") or f"Document {doc_id}"
    so_hieu = doc.get("so_hieu") or ""
    body = doc.get("noi_dung") or doc.get("tom_tat") or ""

    if format == "md":
        meta_lines = [
            f"# {title}",
            "",
            f"- **Số hiệu:** {so_hieu}",
            f"- **Cơ quan:** {doc.get('co_quan_ban_hanh','')}",
            f"- **Ngày ban hành:** {doc.get('ngay_ban_hanh','')}",
            f"- **Sắc thuế:** {fe_sac_thue(doc.get('sac_thue','')) if doc.get('sac_thue') else ''}",
            f"- **Hiệu lực:** {doc.get('effective_status','')}",
        ]
        if doc.get("ai_summary"):
            meta_lines += ["", "## Tóm tắt AI", "", doc["ai_summary"]]
        meta_lines += ["", "---", "", body]
        return PlainTextResponse("\n".join(meta_lines), media_type="text/markdown; charset=utf-8")

    # html
    html = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>{title}</title>
<style>body{{font-family:-apple-system,system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;line-height:1.6;color:#1f2937}}
h1{{color:#016b2c}}.meta{{background:#e8f5ee;padding:1rem;border-radius:8px;margin:1rem 0}}
.meta div{{margin:.25rem 0}}</style></head><body>
<h1>{title}</h1>
<div class="meta">
<div><b>Số hiệu:</b> {so_hieu}</div>
<div><b>Cơ quan:</b> {doc.get('co_quan_ban_hanh','')}</div>
<div><b>Ngày ban hành:</b> {doc.get('ngay_ban_hanh','')}</div>
<div><b>Hiệu lực:</b> {doc.get('effective_status','')}</div>
</div>
<article>{body}</article>
</body></html>"""
    return PlainTextResponse(html, media_type="text/html; charset=utf-8")


# ----------------------------------------------------------------------
# Schema probe — useful since we cannot exec shell on Coolify
# ----------------------------------------------------------------------
@router.get("/_schema")
async def get_schema(
    db: AsyncSession = Depends(get_db),
    auth: dict = Depends(require_sync_auth),
):
    out: dict = {}
    for tbl in ("documents", "cong_van", "articles", "users", "doc_relations",
                "missing_docs_watchlist", "documents_audit", "documents_ai_review",
                "documents_alert_subscriptions", "documents_export_keys",
                "documents_sync_cursor", "documents_webhook_deliveries"):
        try:
            r = await db.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=:t
                ORDER BY ordinal_position
            """), {"t": tbl})
            cols = [(m["column_name"], m["data_type"]) for m in r.mappings().all()]
            if cols:
                out[tbl] = cols
        except Exception as e:
            out[tbl] = f"error: {e}"
    return out
