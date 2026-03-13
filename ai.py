"""
AI module: Claudible streaming analysis, factcheck, related docs
"""
import os, re, json
from typing import AsyncGenerator
import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from search import embed_text

CLAUDIBLE_KEY   = os.environ.get("CLAUDIBLE_API_KEY", "")
CLAUDIBLE_URL   = os.environ.get("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")
CLAUDIBLE_MODEL = os.environ.get("CLAUDIBLE_MODEL", "claude-sonnet-4.6")

def get_client():
    return anthropic.Anthropic(api_key=CLAUDIBLE_KEY, base_url=CLAUDIBLE_URL)

async def get_context_docs(db: AsyncSession, question: str, context_ids: list) -> tuple:
    docs_info = []
    if context_ids:
        for item in context_ids[:5]:
            src = item.get("source", "documents")
            doc_id = item.get("id")
            if not doc_id:
                continue
            if src == "documents":
                r = await db.execute(text(
                    "SELECT so_hieu, ten, tinh_trang, tom_tat, LEFT(noi_dung,3000) as nd FROM documents WHERE id=:id"
                ), {"id": doc_id})
            elif src == "cong_van":
                r = await db.execute(text(
                    "SELECT so_hieu, ten, 'con_hieu_luc' as tinh_trang, ket_luan as tom_tat, LEFT(noi_dung_day_du,3000) as nd FROM cong_van WHERE id=:id"
                ), {"id": doc_id})
            else:
                continue
            row = r.mappings().first()
            if row:
                docs_info.append(dict(row))
    else:
        emb = await embed_text(question)
        if emb:
            r = await db.execute(text("""
                SELECT so_hieu, ten, tinh_trang, tom_tat, LEFT(noi_dung,2000) as nd,
                       1-(embedding<=>:emb::vector) AS score
                FROM documents WHERE embedding IS NOT NULL
                ORDER BY embedding<=>:emb::vector LIMIT 5
            """), {"emb": str(emb)})
            docs_info.extend([dict(row) for row in r.mappings().all()])
            r2 = await db.execute(text("""
                SELECT so_hieu, ten, 'con_hieu_luc' as tinh_trang, ket_luan as tom_tat,
                       LEFT(noi_dung_day_du,2000) as nd,
                       1-(embedding<=>:emb::vector) AS score
                FROM cong_van WHERE embedding IS NOT NULL
                ORDER BY embedding<=>:emb::vector LIMIT 3
            """), {"emb": str(emb)})
            docs_info.extend([dict(row) for row in r2.mappings().all()])
            docs_info.sort(key=lambda x: x.get("score", 0), reverse=True)
            docs_info = docs_info[:6]
        else:
            r = await db.execute(text("""
                SELECT so_hieu, ten, tinh_trang, tom_tat, LEFT(noi_dung,2000) as nd
                FROM documents
                WHERE to_tsvector('simple', coalesce(ten,'') || ' ' || coalesce(noi_dung,''))
                      @@ plainto_tsquery('simple', :q)
                LIMIT 5
            """), {"q": question})
            docs_info.extend([dict(row) for row in r.mappings().all()])

    context_parts = []
    citations = []
    for d in docs_info[:6]:
        so = d.get("so_hieu", "")
        ten = d.get("ten", "")
        status = "⚠️ HẾT HIỆU LỰC" if d.get("tinh_trang") == "het_hieu_luc" else "✅ Còn hiệu lực"
        summary = d.get("tom_tat") or d.get("nd") or ""
        context_parts.append(f"**{so} — {ten}** [{status}]\n{summary[:1500]}")
        citations.append({"so_hieu": so, "ten": ten, "tinh_trang": d.get("tinh_trang")})

    return "\n\n---\n\n".join(context_parts), citations


async def stream_quick_analysis(db: AsyncSession, question: str, context_ids: list) -> AsyncGenerator:
    context, citations = await get_context_docs(db, question, context_ids)
    prompt = f"""Bạn là chuyên gia tư vấn thuế Việt Nam với 30 năm kinh nghiệm tại Big 4.

**Câu hỏi:** {question}

**Văn bản và công văn liên quan:**
{context if context else "(Không tìm thấy văn bản liên quan)"}

**Yêu cầu:**
- Phân tích ngắn gọn, súc tích (~1 trang A4)
- Nêu rõ điều, khoản, điểm cụ thể
- Chỉ trích dẫn văn bản có trong dữ liệu
- Lưu ý nếu văn bản đã hết hiệu lực
- Kết luận rõ ràng
- Tiếng Việt chuyên nghiệp"""

    yield {"type": "citations", "docs": citations}
    try:
        client = get_client()
        with client.messages.stream(
            model=CLAUDIBLE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for chunk in stream.text_stream:
                yield {"type": "text", "content": chunk}
    except Exception as e:
        yield {"type": "error", "content": f"Lỗi AI: {str(e)}"}
    yield {"type": "done"}


async def stream_analyze_doc(db: AsyncSession, source: str, doc_id: int) -> AsyncGenerator:
    if source == "documents":
        r = await db.execute(text(
            "SELECT so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue, noi_dung FROM documents WHERE id=:id"
        ), {"id": doc_id})
    elif source == "cong_van":
        r = await db.execute(text(
            "SELECT so_hieu, ten, 'CV' as loai, ngay_ban_hanh, 'con_hieu_luc' as tinh_trang, sac_thue, noi_dung_day_du as noi_dung FROM cong_van WHERE id=:id"
        ), {"id": doc_id})
    else:
        yield {"type": "error", "content": "Nguồn không hợp lệ"}
        return

    row = r.mappings().first()
    if not row:
        yield {"type": "error", "content": "Không tìm thấy văn bản"}
        return

    d = dict(row)
    status = "ĐÃ HẾT HIỆU LỰC" if d.get("tinh_trang") == "het_hieu_luc" else "Còn hiệu lực"
    prompt = f"""Phân tích văn bản thuế sau:

**{d.get("so_hieu","")} — {d.get("ten","")}**
Loại: {d.get("loai","")} | Ngày: {str(d.get("ngay_ban_hanh",""))[:10]} | Tình trạng: {status}

**Nội dung:**
{(d.get("noi_dung") or "")[:5000]}

**Yêu cầu:**
1. **Tóm tắt** — nội dung chính (3-5 câu)
2. **Ý nghĩa pháp lý** — điểm mới/thay đổi quan trọng
3. **Tác động thực tế** — ảnh hưởng đến DN/cá nhân
4. **Điểm cần chú ý** — dễ hiểu sai, deadline, điều kiện
5. **Trạng thái:** {status}"""

    try:
        client = get_client()
        with client.messages.stream(
            model=CLAUDIBLE_MODEL, max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for chunk in stream.text_stream:
                yield {"type": "text", "content": chunk}
    except Exception as e:
        yield {"type": "error", "content": f"Lỗi AI: {str(e)}"}
    yield {"type": "done"}


async def do_factcheck(db: AsyncSession, text_input: str) -> dict:
    patterns = re.findall(
        r'\b(\d{1,4}/\d{4}/[A-ZĐÀ\-]+(?:-\w+)*|\d{1,4}/[A-ZĐÀÁÂĂẢẠÊẾỆ\-]+-\w+)\b',
        text_input
    )
    all_refs = list(set(patterns))[:20]
    citations = []
    for ref in all_refs:
        r1 = await db.execute(text(
            "SELECT id, so_hieu, ten, tinh_trang FROM documents WHERE so_hieu ILIKE :ref LIMIT 1"
        ), {"ref": f"%{ref}%"})
        row = r1.mappings().first()
        if row:
            citations.append({"claimed": ref, "found": row["so_hieu"], "ten": row["ten"],
                               "status": "expired" if row["tinh_trang"] == "het_hieu_luc" else "valid",
                               "doc_id": row["id"], "source": "documents"})
            continue
        r2 = await db.execute(text(
            "SELECT id, so_hieu, ten FROM cong_van WHERE so_hieu ILIKE :ref LIMIT 1"
        ), {"ref": f"%{ref}%"})
        row2 = r2.mappings().first()
        if row2:
            citations.append({"claimed": ref, "found": row2["so_hieu"], "ten": row2["ten"],
                               "status": "valid", "doc_id": row2["id"], "source": "cong_van"})
        else:
            citations.append({"claimed": ref, "found": None, "ten": None,
                               "status": "not_found", "doc_id": None, "source": None})
    return {"citations": citations, "total_found": len([c for c in citations if c["status"] != "not_found"])}


async def do_related(db: AsyncSession, source: str, doc_id: int) -> dict:
    if source == "documents":
        r = await db.execute(text("SELECT embedding FROM documents WHERE id=:id"), {"id": doc_id})
    elif source == "cong_van":
        r = await db.execute(text("SELECT embedding FROM cong_van WHERE id=:id"), {"id": doc_id})
    else:
        return {"related": []}
    row = r.mappings().first()
    if not row or row["embedding"] is None:
        return {"related": []}
    emb_str = str(list(row["embedding"]))
    r2 = await db.execute(text("""
        SELECT id, so_hieu, ten, loai, tinh_trang, sac_thue,
               1-(embedding<=>:emb::vector) AS score
        FROM documents WHERE id != :did AND embedding IS NOT NULL
        ORDER BY embedding<=>:emb::vector LIMIT 5
    """), {"emb": emb_str, "did": doc_id if source == "documents" else -1})
    related = [{"id": d["id"], "so_hieu": d["so_hieu"], "ten": d["ten"],
                "loai": d["loai"], "tinh_trang": d["tinh_trang"],
                "sac_thue": d["sac_thue"], "source": "documents",
                "score": round(float(d["score"]), 3)} for d in r2.mappings().all()]
    return {"related": sorted(related, key=lambda x: x["score"], reverse=True)}
