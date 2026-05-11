"""
AI-extras router: structured implications extraction, document comparison,
summary cache. Reuses the existing `ai.py` Anthropic/OpenAI helpers when
available, falls back to a deterministic stub when no API key is configured.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from backend.common import write_audit, serialize_row

log = logging.getLogger("vntaxdb.ai_extras")
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------
class ImplBody(BaseModel):
    source: str  # 'documents' | 'cong_van'
    id: int
    force: bool = False  # bypass cache


class CompareBody(BaseModel):
    source_a: str
    id_a: int
    source_b: str
    id_b: int


# ----------------------------------------------------------------------
# Auth dependency — any logged-in user (admin or paying user)
# ----------------------------------------------------------------------
async def require_user(request, db: AsyncSession = Depends(get_db)):
    from main import get_current_user
    return await get_current_user(request, db)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
async def _load_doc(db: AsyncSession, source: str, doc_id: int) -> Optional[dict]:
    if source not in ("documents", "cong_van"):
        return None
    cols = "id, so_hieu, ten, sac_thue, ngay_ban_hanh, co_quan_ban_hanh, noi_dung, ai_summary, ai_tags, ai_implications"
    if source == "documents":
        cols += ", loai, tom_tat"
    r = await db.execute(text(f"SELECT {cols} FROM {source} WHERE id=:i"), {"i": doc_id})
    row = r.mappings().first()
    return dict(row) if row else None


def _stub_implications(doc: dict) -> dict:
    """Deterministic fallback when no AI provider key is set."""
    body = (doc.get("noi_dung") or doc.get("tom_tat") or "")[:4000]
    obligations: list[str] = []
    deadlines: list[str] = []
    rates: list[str] = []
    penalties: list[str] = []
    exemptions: list[str] = []
    actions: list[str] = []

    import re
    for m in re.finditer(r"(?:phải|bắt buộc|có trách nhiệm|chịu trách nhiệm)\s+([^\.\n]{10,200})", body, re.I):
        obligations.append(m.group(0).strip())
    for m in re.finditer(r"(?:thời hạn|hạn nộp|trước ngày|chậm nhất)\s+([^\.\n]{5,120})", body, re.I):
        deadlines.append(m.group(0).strip())
    for m in re.finditer(r"\b(\d+(?:[.,]\d+)?\s*%)\b", body):
        rates.append(m.group(1))
    for m in re.finditer(r"(?:phạt|xử phạt|tiền phạt)\s+([^\.\n]{5,200})", body, re.I):
        penalties.append(m.group(0).strip())
    for m in re.finditer(r"(?:miễn thuế|không chịu thuế|không phải nộp|được miễn)\s+([^\.\n]{5,200})", body, re.I):
        exemptions.append(m.group(0).strip())
    for m in re.finditer(r"(?:cần thực hiện|nên thực hiện|phải nộp|kê khai|đăng ký)\s+([^\.\n]{5,200})", body, re.I):
        actions.append(m.group(0).strip())

    def dedupe(arr):
        seen = set()
        out = []
        for s in arr:
            k = s.lower()[:80]
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
        return out[:10]

    return {
        "obligations": dedupe(obligations),
        "deadlines": dedupe(deadlines),
        "rates": dedupe(rates),
        "penalties": dedupe(penalties),
        "exemptions": dedupe(exemptions),
        "compliance_actions": dedupe(actions),
        "generated_by": "stub-v1",
    }


async def _ai_implications(doc: dict) -> dict:
    """Call OpenAI if configured, else fallback to stub."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return _stub_implications(doc)
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        body = (doc.get("noi_dung") or doc.get("tom_tat") or "")[:8000]
        prompt = f"""Bạn là chuyên gia thuế Việt Nam. Đọc văn bản sau và trả về JSON
với các trường: obligations (nghĩa vụ), deadlines (thời hạn), rates (mức thuế suất),
penalties (mức phạt), exemptions (miễn/giảm), compliance_actions (hành động cần thực hiện).
Mỗi trường là một mảng chuỗi tiếng Việt, tối đa 10 mục.

Số hiệu: {doc.get('so_hieu','')}
Tên: {doc.get('ten','')}

Nội dung:
{body}

Trả về CHỈ JSON, không kèm văn bản khác."""
        resp = await client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        data["generated_by"] = f"openai:{os.environ.get('OPENAI_MODEL','gpt-4o-mini')}"
        return data
    except Exception as e:
        log.warning("AI implications failed, falling back to stub: %s", e)
        return _stub_implications(doc)


# ----------------------------------------------------------------------
# POST /api/v1/ai/implications
# ----------------------------------------------------------------------
@router.post("/implications")
async def implications(
    body: ImplBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user),
):
    doc = await _load_doc(db, body.source, body.id)
    if not doc:
        raise HTTPException(404, "Document not found")

    if not body.force and doc.get("ai_implications"):
        cached = doc["ai_implications"]
        if isinstance(cached, str):
            try:
                cached = json.loads(cached)
            except Exception:
                pass
        return {"cached": True, "data": cached}

    data = await _ai_implications(doc)
    # Cache back
    try:
        await db.execute(
            text(f"UPDATE {body.source} SET ai_implications=CAST(:j AS JSONB) WHERE id=:i"),
            {"j": json.dumps(data, ensure_ascii=False), "i": body.id},
        )
        await db.commit()
        await write_audit(
            db, source=body.source, doc_id=body.id, event="ai_implications_updated",
            actor_kind="user", actor_label=user.get("email", "user"),
            new_values={"generated_by": data.get("generated_by")},
        )
    except Exception as e:
        log.warning("cache implications failed: %s", e)
    return {"cached": False, "data": data}


# ----------------------------------------------------------------------
# POST /api/v1/ai/compare  — SSE stream
# ----------------------------------------------------------------------
@router.post("/compare")
async def compare(
    body: CompareBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user),
):
    a = await _load_doc(db, body.source_a, body.id_a)
    b = await _load_doc(db, body.source_b, body.id_b)
    if not a or not b:
        raise HTTPException(404, "One or both documents not found")

    async def gen():
        def sse(event: str, data: dict | str):
            payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data
            return f"event: {event}\ndata: {payload}\n\n"

        yield sse("start", {"a": a.get("so_hieu"), "b": b.get("so_hieu")})

        # Try OpenAI streaming
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=api_key)
                prompt = f"""So sánh hai văn bản thuế/pháp luật Việt Nam sau. Trả lời bằng tiếng Việt,
có cấu trúc rõ ràng với các phần: 1) Phạm vi & đối tượng áp dụng, 2) Điểm chung,
3) Điểm khác biệt chính, 4) Văn bản nào ưu tiên áp dụng, 5) Khuyến nghị tuân thủ.

VĂN BẢN A — {a.get('so_hieu')} ({a.get('ten')}):
{(a.get('noi_dung') or a.get('tom_tat') or '')[:4000]}

VĂN BẢN B — {b.get('so_hieu')} ({b.get('ten')}):
{(b.get('noi_dung') or b.get('tom_tat') or '')[:4000]}
"""
                stream = await client.chat.completions.create(
                    model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield sse("delta", {"text": delta})
                yield sse("done", {})
                return
            except Exception as e:
                log.warning("compare stream failed: %s", e)
                yield sse("delta", {"text": f"\n[Lỗi AI: {e}. Trả về so sánh cơ bản.]\n"})

        # Stub comparison
        text_out = (
            f"## So sánh {a.get('so_hieu')} và {b.get('so_hieu')}\n\n"
            f"### Văn bản A: {a.get('ten')}\n"
            f"- Ngày ban hành: {a.get('ngay_ban_hanh')}\n"
            f"- Cơ quan: {a.get('co_quan_ban_hanh')}\n"
            f"- Sắc thuế: {a.get('sac_thue')}\n\n"
            f"### Văn bản B: {b.get('ten')}\n"
            f"- Ngày ban hành: {b.get('ngay_ban_hanh')}\n"
            f"- Cơ quan: {b.get('co_quan_ban_hanh')}\n"
            f"- Sắc thuế: {b.get('sac_thue')}\n\n"
            f"_Để có so sánh AI chi tiết, cấu hình OPENAI_API_KEY._"
        )
        for line in text_out.split("\n"):
            yield sse("delta", {"text": line + "\n"})
        yield sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream")


# ----------------------------------------------------------------------
# POST /api/v1/ai/summary  — generate / cache AI summary + tags
# ----------------------------------------------------------------------
class SummaryBody(BaseModel):
    source: str
    id: int
    force: bool = False


@router.post("/summary")
async def summary(
    body: SummaryBody,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_user),
):
    doc = await _load_doc(db, body.source, body.id)
    if not doc:
        raise HTTPException(404, "Document not found")

    if not body.force and doc.get("ai_summary"):
        return {"cached": True, "summary": doc["ai_summary"], "tags": doc.get("ai_tags") or []}

    api_key = os.environ.get("OPENAI_API_KEY")
    body_text = (doc.get("noi_dung") or doc.get("tom_tat") or "")[:8000]
    summary_text = ""
    tags: list[str] = []

    if api_key:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            prompt = f"""Tóm tắt văn bản pháp luật Việt Nam sau trong 4-6 câu tiếng Việt,
sau đó liệt kê 3-6 thẻ chủ đề (tags) bằng tiếng Việt.

Số hiệu: {doc.get('so_hieu')}
Tên: {doc.get('ten')}

Nội dung:
{body_text}

Trả về JSON: {{ "summary": "...", "tags": ["...","..."] }}"""
            resp = await client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content or "{}")
            summary_text = data.get("summary", "")
            tags = data.get("tags", []) or []
        except Exception as e:
            log.warning("summary AI failed: %s", e)

    if not summary_text:
        summary_text = (doc.get("tom_tat") or body_text[:400] or "").strip()
        tags = [doc.get("sac_thue")] if doc.get("sac_thue") else []

    try:
        await db.execute(
            text(f"UPDATE {body.source} SET ai_summary=:s, ai_tags=:t WHERE id=:i"),
            {"s": summary_text, "t": tags, "i": body.id},
        )
        await db.commit()
        await write_audit(
            db, source=body.source, doc_id=body.id, event="ai_summary_updated",
            actor_kind="user", actor_label=user.get("email", "user"),
            new_values={"tags_count": len(tags)},
        )
    except Exception as e:
        log.warning("cache summary failed: %s", e)

    return {"cached": False, "summary": summary_text, "tags": tags}
