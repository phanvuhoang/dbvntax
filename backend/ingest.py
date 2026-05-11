"""
Unified ingestion pipeline for dbvntax.

Supports:
- POST /api/v1/admin/ingest/upload    (file upload: pdf/html/text)
- POST /api/v1/admin/ingest/paste     (paste HTML or text)
- POST /api/v1/admin/ingest/url       (single URL fetch+classify)
- POST /api/v1/admin/crawl/url        (alias for url, sent to review queue)
- POST /api/v1/admin/crawl/batch      (batch list of URLs)
- POST /api/v1/admin/ingest/bulk      (JSON array of records)

All ingested rows go through the same normalization:
  1. Detect source (tvpl / luatvietnam / other)
  2. Extract / clean text
  3. Compute content_hash for dedupe
  4. Try to dedupe by source_url, so_hieu, or content_hash
  5. Decide target table (documents vs cong_van) — công văn = "Công văn" loại,
     or so_hieu matches công văn pattern. Otherwise documents.
  6. If quality_score < threshold OR ambiguous → write to documents_ai_review
  7. Otherwise upsert into the appropriate table
"""
from __future__ import annotations

import io
import json
import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from backend.common import (
    sha256_hex,
    html_to_text,
    normalize_html,
    detect_source,
    fetch_html,
    classify_sac_thue_from_text,
    importance_for,
    write_audit,
    serialize_row,
)

log = logging.getLogger("vntaxdb.ingest")

router = APIRouter(prefix="/api/v1/admin", tags=["ingest"])


# ----------------------------------------------------------------------
# Admin auth dependency — reuses main.get_current_user
# ----------------------------------------------------------------------
async def require_admin(request: Request, db: AsyncSession = Depends(get_db)):
    from main import get_current_user
    user = await get_current_user(request, db)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin only")
    return user


# ----------------------------------------------------------------------
# Pydantic models
# ----------------------------------------------------------------------
class PasteBody(BaseModel):
    so_hieu: Optional[str] = None
    ten: Optional[str] = None
    loai: Optional[str] = None
    sac_thue: Optional[str] = None
    ngay_ban_hanh: Optional[str] = None
    co_quan_ban_hanh: Optional[str] = None
    content: str
    is_html: bool = True
    source_url: Optional[str] = None


class UrlBody(BaseModel):
    url: str
    auto_publish: bool = False


class BatchBody(BaseModel):
    urls: list[str]


class BulkRecord(BaseModel):
    so_hieu: str
    ten: str
    loai: Optional[str] = None
    sac_thue: Optional[str] = None
    ngay_ban_hanh: Optional[str] = None
    co_quan_ban_hanh: Optional[str] = None
    noi_dung: Optional[str] = None
    tvpl_url: Optional[str] = None
    source_url: Optional[str] = None


# ----------------------------------------------------------------------
# Core normalizer / classifier
# ----------------------------------------------------------------------
CONG_VAN_PATTERN = re.compile(r"^\s*\d+\s*[/\-]\s*\w+", re.IGNORECASE)


def classify_loai(loai: str | None, so_hieu: str | None, ten: str | None) -> str:
    """Decide target table. Returns 'cong_van' or 'documents'."""
    if loai:
        if "công văn" in loai.lower() or loai.lower().strip() == "cv":
            return "cong_van"
    if ten and "công văn" in ten.lower()[:80]:
        return "cong_van"
    return "documents"


def quality_score_for(record: dict) -> int:
    score = 0
    for f in ("so_hieu", "ten", "noi_dung", "ngay_ban_hanh", "co_quan_ban_hanh"):
        if record.get(f):
            score += 20
    if record.get("source_url"):
        score += 10
    return min(100, score)


# ----------------------------------------------------------------------
# Upsert helpers
# ----------------------------------------------------------------------
async def upsert_document(
    db: AsyncSession,
    record: dict,
    table: str,
    actor: str,
) -> dict:
    """Insert or update by source_url first, then so_hieu+(loai if documents)."""
    src_url = record.get("source_url")
    so_hieu = record.get("so_hieu")
    content = record.get("noi_dung")
    content_hash = sha256_hex(content) if content else None
    record["content_hash"] = content_hash

    # Try to find existing
    existing_id: Optional[int] = None
    if src_url:
        r = await db.execute(text(f"SELECT id FROM {table} WHERE source_url=:u LIMIT 1"), {"u": src_url})
        row = r.mappings().first()
        if row:
            existing_id = row["id"]
    if not existing_id and so_hieu:
        if table == "documents" and record.get("loai"):
            r = await db.execute(
                text("SELECT id FROM documents WHERE so_hieu=:s AND loai=:l LIMIT 1"),
                {"s": so_hieu, "l": record["loai"]},
            )
        else:
            r = await db.execute(text(f"SELECT id FROM {table} WHERE so_hieu=:s LIMIT 1"), {"s": so_hieu})
        row = r.mappings().first()
        if row:
            existing_id = row["id"]
    if not existing_id and content_hash:
        r = await db.execute(text(f"SELECT id FROM {table} WHERE content_hash=:h LIMIT 1"), {"h": content_hash})
        row = r.mappings().first()
        if row:
            existing_id = row["id"]

    if table == "documents":
        cols = [
            "so_hieu", "ten", "loai", "sac_thue", "ngay_ban_hanh", "ngay_hieu_luc",
            "co_quan_ban_hanh", "nguoi_ky", "tom_tat", "noi_dung", "tvpl_url",
            "source", "source_url", "source_site", "content_hash", "quality_score",
        ]
    else:
        cols = [
            "so_hieu", "ten", "sac_thue", "ngay_ban_hanh", "co_quan_ban_hanh",
            "noi_dung", "tvpl_url", "importance",
            "source", "source_url", "source_site", "content_hash", "quality_score",
        ]

    if existing_id:
        sets = ", ".join(f"{c}=:{c}" for c in cols if c in record)
        params = {c: record.get(c) for c in cols if c in record}
        params["i"] = existing_id
        if sets:
            await db.execute(text(f"UPDATE {table} SET {sets} WHERE id=:i"), params)
            await db.commit()
        await write_audit(
            db, source=table, doc_id=existing_id, event="updated",
            actor_kind="user", actor_label=actor,
            new_values={"fields": list(params.keys())},
        )
        return {"action": "updated", "id": existing_id, "table": table}

    insert_cols = [c for c in cols if c in record]
    placeholders = ", ".join(f":{c}" for c in insert_cols)
    col_sql = ", ".join(insert_cols)
    params = {c: record.get(c) for c in insert_cols}
    r = await db.execute(
        text(f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders}) RETURNING id"),
        params,
    )
    new_id = r.scalar()
    await db.commit()
    await write_audit(
        db, source=table, doc_id=new_id, event="created",
        actor_kind="user", actor_label=actor,
        new_values={k: v for k, v in params.items() if k != "noi_dung"},
    )
    return {"action": "inserted", "id": new_id, "table": table}


# ----------------------------------------------------------------------
# Route: paste
# ----------------------------------------------------------------------
@router.post("/ingest/paste")
async def ingest_paste(
    body: PasteBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    raw = body.content or ""
    if body.is_html:
        html = normalize_html(raw)
        text_body = html_to_text(html)
    else:
        text_body = raw

    src, site = detect_source(body.source_url)
    sac_classified = classify_sac_thue_from_text(text_body) if not body.sac_thue else []
    sac = body.sac_thue or (sac_classified[0] if sac_classified else None)

    table = classify_loai(body.loai, body.so_hieu, body.ten)
    record = {
        "so_hieu": body.so_hieu,
        "ten": body.ten or (text_body[:200] if text_body else None),
        "loai": body.loai,
        "sac_thue": sac,
        "ngay_ban_hanh": body.ngay_ban_hanh,
        "co_quan_ban_hanh": body.co_quan_ban_hanh,
        "noi_dung": text_body,
        "source": src,
        "source_url": body.source_url,
        "source_site": site,
    }
    if table == "cong_van":
        record["importance"] = importance_for("Công văn")
    record["quality_score"] = quality_score_for(record)
    if not body.so_hieu or not body.ten or record["quality_score"] < 60:
        return await _send_to_review(db, table, record, user, reason="low_quality_or_missing_fields")
    return await upsert_document(db, record, table, actor=user.get("email", "admin"))


# ----------------------------------------------------------------------
# Route: url (alias of crawl/url)
# ----------------------------------------------------------------------
@router.post("/ingest/url")
@router.post("/crawl/url")
async def ingest_url(
    body: UrlBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    html, err = await fetch_html(body.url)
    if err or not html:
        raise HTTPException(400, f"Fetch failed: {err}")
    html = normalize_html(html)
    text_body = html_to_text(html)
    src, site = detect_source(body.url)
    sac = (classify_sac_thue_from_text(text_body) or [None])[0]

    # Heuristic title from <title>
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = (title_m.group(1).strip() if title_m else text_body[:200]).strip()

    # Heuristic so_hieu: pattern like "12/2024/TT-BTC" in first 500 chars
    so_m = re.search(r"\b(\d+[\-/]\d{4}[/\-][A-ZĐ\-]+)\b", text_body[:1000])
    so_hieu = so_m.group(1) if so_m else None

    # Guess loai from so_hieu
    loai = None
    if so_hieu:
        for marker, name in (("TT-", "Thông tư"), ("NĐ-", "Nghị định"),
                              ("QĐ-", "Quyết định"), ("CT-", "Chỉ thị"),
                              ("CV-", "Công văn")):
            if marker in so_hieu:
                loai = name
                break

    table = classify_loai(loai, so_hieu, title)
    record = {
        "so_hieu": so_hieu,
        "ten": title,
        "loai": loai,
        "sac_thue": sac,
        "noi_dung": text_body,
        "source": src,
        "source_url": body.url,
        "source_site": site,
    }
    if table == "cong_van":
        record["importance"] = importance_for("Công văn")
    record["quality_score"] = quality_score_for(record)

    if not body.auto_publish or record["quality_score"] < 60 or not so_hieu:
        return await _send_to_review(db, table, record, user, reason="needs_admin_review")
    return await upsert_document(db, record, table, actor=user.get("email", "admin"))


# ----------------------------------------------------------------------
# Route: crawl/batch
# ----------------------------------------------------------------------
@router.post("/crawl/batch")
async def crawl_batch(
    body: BatchBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    if not body.urls:
        raise HTTPException(400, "urls required")
    if len(body.urls) > 50:
        raise HTTPException(400, "Max 50 URLs per batch")
    results = []
    for url in body.urls:
        try:
            res = await ingest_url(UrlBody(url=url, auto_publish=False), db=db, user=user)
            results.append({"url": url, "ok": True, "result": res})
        except HTTPException as he:
            results.append({"url": url, "ok": False, "error": he.detail})
        except Exception as e:
            results.append({"url": url, "ok": False, "error": str(e)})
    return {"count": len(results), "results": results}


# ----------------------------------------------------------------------
# Route: bulk JSON
# ----------------------------------------------------------------------
@router.post("/ingest/bulk")
async def ingest_bulk(
    items: list[BulkRecord] = Body(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    if not items:
        raise HTTPException(400, "items required")
    if len(items) > 500:
        raise HTTPException(400, "Max 500 items per batch")
    results = []
    for it in items:
        record = it.model_dump()
        src, site = detect_source(record.get("source_url"))
        record["source"] = src
        record["source_site"] = site
        table = classify_loai(record.get("loai"), record.get("so_hieu"), record.get("ten"))
        if table == "cong_van":
            record["importance"] = importance_for("Công văn")
        record["quality_score"] = quality_score_for(record)
        try:
            res = await upsert_document(db, record, table, actor=user.get("email", "admin"))
            results.append({"so_hieu": it.so_hieu, "ok": True, "result": res})
        except Exception as e:
            results.append({"so_hieu": it.so_hieu, "ok": False, "error": str(e)})
    return {"count": len(results), "results": results}


# ----------------------------------------------------------------------
# Route: upload file
# ----------------------------------------------------------------------
@router.post("/ingest/upload")
async def ingest_upload(
    file: UploadFile = File(...),
    so_hieu: Optional[str] = Form(None),
    ten: Optional[str] = Form(None),
    loai: Optional[str] = Form(None),
    sac_thue: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_admin),
):
    raw = await file.read()
    fname = (file.filename or "").lower()
    if fname.endswith((".htm", ".html")):
        html = raw.decode("utf-8", errors="replace")
        text_body = html_to_text(normalize_html(html))
    elif fname.endswith(".txt"):
        text_body = raw.decode("utf-8", errors="replace")
    elif fname.endswith(".pdf"):
        # Defer to optional OCR/text extraction (best-effort)
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            text_body = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            raise HTTPException(400, f"PDF extract failed (install pypdf): {e}")
    else:
        raise HTTPException(400, "Unsupported file type. Use .html, .txt, or .pdf")

    table = classify_loai(loai, so_hieu, ten)
    record = {
        "so_hieu": so_hieu,
        "ten": ten or (text_body[:200] if text_body else file.filename),
        "loai": loai,
        "sac_thue": sac_thue,
        "noi_dung": text_body,
        "source": "upload",
        "source_url": None,
        "source_site": None,
    }
    if table == "cong_van":
        record["importance"] = importance_for("Công văn")
    record["quality_score"] = quality_score_for(record)
    if not so_hieu or record["quality_score"] < 60:
        return await _send_to_review(db, table, record, user, reason="upload_needs_review")
    return await upsert_document(db, record, table, actor=user.get("email", "admin"))


# ----------------------------------------------------------------------
# Internal: send to review queue
# ----------------------------------------------------------------------
async def _send_to_review(
    db: AsyncSession,
    table: str,
    record: dict,
    user: dict,
    reason: str,
) -> dict:
    proposed = json.dumps(record, default=str, ensure_ascii=False)
    r = await db.execute(text("""
        INSERT INTO documents_ai_review (source, doc_id, kind, proposed, status, notes)
        VALUES (:s, 0, 'metadata', CAST(:p AS JSONB), 'pending', :n)
        RETURNING id
    """), {"s": table, "p": proposed, "n": reason})
    rid = r.scalar()
    await db.commit()
    await write_audit(
        db, source="documents_ai_review", doc_id=rid, event="created",
        actor_kind="user", actor_label=user.get("email", "admin"),
        new_values={"reason": reason, "target_table": table},
    )
    return {"action": "review_queued", "review_id": rid, "reason": reason, "table": table}
