"""
Admin endpoints for the new canonical layer:
- Review queue (list, decide)
- Audit log (list)
- Export/sync key management
- Watchlist alert subscriptions
"""
from __future__ import annotations

import json
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from backend.common import (
    generate_token,
    hash_token,
    write_audit,
    serialize_row,
)

log = logging.getLogger("vntaxdb.admin_extras")
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


async def require_admin(request: Request, db: AsyncSession = Depends(get_db)):
    from main import get_current_user
    user = await get_current_user(request, db)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user


# ----------------------------------------------------------------------
# Review queue
# ----------------------------------------------------------------------
@router.get("/review-queue")
async def list_review_queue(
    status: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    r = await db.execute(text("""
        SELECT id, source, doc_id, kind, proposed, confidence, status,
               decided_by, decided_at, notes, created_at
        FROM documents_ai_review
        WHERE status = :s
        ORDER BY created_at DESC
        LIMIT :l
    """), {"s": status, "l": limit})
    rows = [serialize_row(dict(m)) for m in r.mappings().all()]
    return {"items": rows, "count": len(rows)}


class ReviewDecision(BaseModel):
    action: str  # 'accept' | 'reject'
    notes: Optional[str] = None


@router.post("/review-queue/{review_id}/decision")
async def decide_review(
    review_id: int,
    body: ReviewDecision,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    if body.action not in ("accept", "reject"):
        raise HTTPException(400, "action must be accept|reject")
    r = await db.execute(text("SELECT * FROM documents_ai_review WHERE id=:i"), {"i": review_id})
    row = r.mappings().first()
    if not row:
        raise HTTPException(404, "Not found")
    if row["status"] != "pending":
        raise HTTPException(400, f"Already decided ({row['status']})")

    if body.action == "reject":
        await db.execute(text("""
            UPDATE documents_ai_review
            SET status='rejected', decided_at=NOW(), notes=:n
            WHERE id=:i
        """), {"n": body.notes, "i": review_id})
        await db.commit()
        await write_audit(
            db, source="documents_ai_review", doc_id=review_id, event="rejected",
            actor_kind="user", actor_label=user.get("email", "admin"),
            new_values={"notes": body.notes},
        )
        return {"ok": True, "action": "rejected", "id": review_id}

    # accept: if kind=='metadata' with doc_id=0, insert into target table
    proposed = row["proposed"]
    if isinstance(proposed, str):
        proposed = json.loads(proposed)

    target = row["source"]  # 'documents' or 'cong_van'
    if row["doc_id"] == 0 and row["kind"] == "metadata":
        # Brand-new doc — insert via ingest.upsert_document logic
        from backend.ingest import upsert_document
        res = await upsert_document(db, proposed, target, actor=user.get("email", "admin"))
        await db.execute(text("""
            UPDATE documents_ai_review
            SET status='accepted', decided_at=NOW(), notes=:n, doc_id=:d
            WHERE id=:i
        """), {"n": body.notes, "d": res.get("id"), "i": review_id})
        await db.commit()
        await write_audit(
            db, source="documents_ai_review", doc_id=review_id, event="accepted",
            actor_kind="user", actor_label=user.get("email", "admin"),
            new_values={"new_doc_id": res.get("id"), "target": target},
        )
        return {"ok": True, "action": "accepted", "result": res}

    # Otherwise: apply proposed fields onto existing document
    doc_id = row["doc_id"]
    allowed = {"ai_summary", "ai_tags", "ai_implications", "tom_tat", "effective_status",
               "effective_confidence", "supersedes_so_hieu", "superseded_by_so_hieu",
               "is_anchor", "importance", "quality_score"}
    updates = {k: v for k, v in proposed.items() if k in allowed}
    if updates:
        sets = ", ".join(f"{k}=:{k}" for k in updates.keys())
        params = dict(updates)
        params["i"] = doc_id
        # JSONB casting for tags/implications
        if "ai_implications" in params and isinstance(params["ai_implications"], (dict, list)):
            sets = sets.replace("ai_implications=:ai_implications", "ai_implications=CAST(:ai_implications AS JSONB)")
            params["ai_implications"] = json.dumps(params["ai_implications"], ensure_ascii=False)
        await db.execute(text(f"UPDATE {target} SET {sets} WHERE id=:i"), params)
    await db.execute(text("""
        UPDATE documents_ai_review
        SET status='accepted', decided_at=NOW(), notes=:n
        WHERE id=:i
    """), {"n": body.notes, "i": review_id})
    await db.commit()
    await write_audit(
        db, source=target, doc_id=doc_id, event=f"ai_review_{row['kind']}_accepted",
        actor_kind="user", actor_label=user.get("email", "admin"),
        new_values={"review_id": review_id, "fields": list(updates.keys())},
    )
    return {"ok": True, "action": "accepted", "id": review_id, "fields_applied": list(updates.keys())}


# ----------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------
@router.get("/audit")
async def list_audit(
    source: Optional[str] = None,
    doc_id: Optional[int] = None,
    event: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    wheres = []
    params = {"l": limit}
    if source:
        wheres.append("source=:s")
        params["s"] = source
    if doc_id is not None:
        wheres.append("doc_id=:d")
        params["d"] = doc_id
    if event:
        wheres.append("event=:e")
        params["e"] = event
    where_sql = (" WHERE " + " AND ".join(wheres)) if wheres else ""
    r = await db.execute(text(f"""
        SELECT id, source, doc_id, event, actor_id, actor_kind, actor_label,
               old_values, new_values, created_at
        FROM documents_audit
        {where_sql}
        ORDER BY created_at DESC
        LIMIT :l
    """), params)
    return {"items": [serialize_row(dict(m)) for m in r.mappings().all()]}


# ----------------------------------------------------------------------
# Export keys
# ----------------------------------------------------------------------
class ExportKeyCreate(BaseModel):
    app_name: str
    scopes: list[str] = ["read"]
    webhook_url: Optional[str] = None


@router.get("/export-keys")
async def list_keys(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    r = await db.execute(text("""
        SELECT id, prefix, app_name, scopes, webhook_url,
               last_used_at, revoked_at, created_at
        FROM documents_export_keys
        ORDER BY created_at DESC
    """))
    return {"items": [serialize_row(dict(m)) for m in r.mappings().all()]}


@router.post("/export-keys")
async def create_key(
    body: ExportKeyCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    token = generate_token()
    h = hash_token(token)
    prefix = token[:8]
    webhook_secret = secrets.token_urlsafe(24) if body.webhook_url else None
    r = await db.execute(text("""
        INSERT INTO documents_export_keys
            (token_hash, prefix, app_name, scopes, webhook_url, webhook_secret, created_by)
        VALUES (:h, :p, :a, :s, :w, :ws, :u)
        RETURNING id
    """), {
        "h": h, "p": prefix, "a": body.app_name, "s": body.scopes,
        "w": body.webhook_url, "ws": webhook_secret, "u": None,
    })
    new_id = r.scalar()
    await db.commit()
    await write_audit(
        db, source="documents_export_keys", doc_id=new_id, event="created",
        actor_kind="user", actor_label=user.get("email", "admin"),
        new_values={"app_name": body.app_name, "scopes": body.scopes},
    )
    return {
        "id": new_id,
        "prefix": prefix,
        "app_name": body.app_name,
        "token": token,        # only shown once
        "webhook_secret": webhook_secret,
        "scopes": body.scopes,
        "warning": "Lưu token ngay — không thể xem lại sau lần này.",
    }


@router.post("/export-keys/{key_id}/revoke")
async def revoke_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    await db.execute(text("UPDATE documents_export_keys SET revoked_at=NOW() WHERE id=:i"), {"i": key_id})
    await db.commit()
    await write_audit(
        db, source="documents_export_keys", doc_id=key_id, event="revoked",
        actor_kind="user", actor_label=user.get("email", "admin"),
    )
    return {"ok": True, "id": key_id}


# ----------------------------------------------------------------------
# Stats overview (for new admin dashboard panel)
# ----------------------------------------------------------------------
@router.get("/canonical-stats")
async def canonical_stats(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    out: dict = {}
    try:
        r = await db.execute(text("SELECT COUNT(*) FROM documents"))
        out["documents"] = r.scalar() or 0
        r = await db.execute(text("SELECT COUNT(*) FROM cong_van"))
        out["cong_van"] = r.scalar() or 0
        r = await db.execute(text("SELECT COUNT(*) FROM documents WHERE is_anchor=TRUE"))
        out["anchors"] = r.scalar() or 0
        r = await db.execute(text("SELECT COUNT(*) FROM documents_ai_review WHERE status='pending'"))
        out["review_pending"] = r.scalar() or 0
        r = await db.execute(text("SELECT COUNT(*) FROM documents_export_keys WHERE revoked_at IS NULL"))
        out["active_keys"] = r.scalar() or 0
        r = await db.execute(text("""
            SELECT effective_status, COUNT(*) AS c FROM documents
            WHERE effective_status IS NOT NULL
            GROUP BY effective_status
        """))
        out["effective_status"] = {m["effective_status"]: m["c"] for m in r.mappings().all()}
        r = await db.execute(text("""
            SELECT event, COUNT(*) AS c FROM documents_audit
            WHERE created_at >= NOW() - INTERVAL '7 days'
            GROUP BY event ORDER BY c DESC LIMIT 10
        """))
        out["recent_events"] = [{"event": m["event"], "count": m["c"]} for m in r.mappings().all()]
    except Exception as e:
        out["error"] = str(e)
    return out
