"""
AI module: Claudible streaming analysis, factcheck, related docs
Claudible dùng OpenAI-compatible API (không phải Anthropic SDK).
Context window: 200K tokens — cost $0 qua Claudible.
"""
import os, re, json
from typing import AsyncGenerator
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from search import embed_text

CLAUDIBLE_KEY   = os.environ.get("CLAUDIBLE_API_KEY", "")
CLAUDIBLE_URL   = os.environ.get("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")
CLAUDIBLE_MODEL = os.environ.get("CLAUDIBLE_MODEL", "claude-sonnet-4.6")

# Max tokens cho output (Claudible 200K context window, cost $0)
MAX_OUTPUT_TOKENS  = 8192   # output dài hơn, không bị ngắt
MAX_CONTEXT_CHARS  = 80000  # ~60K tokens context — tận dụng 200K window
MAX_DOC_CHARS      = 40000  # mỗi văn bản tối đa 40K chars (~30K tokens)
MAX_CV_CHARS       = 20000  # công văn tối đa 20K chars

def get_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=CLAUDIBLE_KEY, base_url=CLAUDIBLE_URL)


async def get_context_docs(db: AsyncSession, question: str, context_ids: list) -> tuple:
    """Lấy context từ DB. Dùng full noi_dung nếu được chỉ định, semantic search nếu không."""
    docs_info = []

    if context_ids:
        # Người dùng chỉ định document cụ thể → lấy full content
        for item in context_ids[:5]:
            src    = item.get("source", "documents")
            doc_id = item.get("id")
            if not doc_id:
                continue
            if src == "documents":
                r = await db.execute(text("""
                    SELECT so_hieu, ten, tinh_trang, tom_tat,
                           LEFT(noi_dung, :maxc) as nd
                    FROM documents WHERE id=:id
                """), {"id": doc_id, "maxc": MAX_DOC_CHARS})
            elif src == "cong_van":
                r = await db.execute(text("""
                    SELECT so_hieu, ten, 'con_hieu_luc' as tinh_trang,
                           ket_luan as tom_tat,
                           LEFT(noi_dung_day_du, :maxc) as nd
                    FROM cong_van WHERE id=:id
                """), {"id": doc_id, "maxc": MAX_CV_CHARS})
            else:
                continue
            row = r.mappings().first()
            if row:
                docs_info.append(dict(row))
    else:
        # Semantic search → lấy nhiều docs liên quan
        emb = await embed_text(question)
        if emb:
            r = await db.execute(text("""
                SELECT so_hieu, ten, tinh_trang, tom_tat,
                       LEFT(noi_dung, :maxc) as nd,
                       1-(embedding<=>:emb::vector) AS score
                FROM documents WHERE embedding IS NOT NULL
                ORDER BY embedding<=>:emb::vector LIMIT 5
            """), {"emb": str(emb), "maxc": MAX_DOC_CHARS})
            docs_info.extend([dict(row) for row in r.mappings().all()])

            r2 = await db.execute(text("""
                SELECT so_hieu, ten, 'con_hieu_luc' as tinh_trang,
                       ket_luan as tom_tat,
                       LEFT(noi_dung_day_du, :maxc) as nd,
                       1-(embedding<=>:emb::vector) AS score
                FROM cong_van WHERE embedding IS NOT NULL
                ORDER BY embedding<=>:emb::vector LIMIT 3
            """), {"emb": str(emb), "maxc": MAX_CV_CHARS})
            docs_info.extend([dict(row) for row in r.mappings().all()])
            docs_info.sort(key=lambda x: x.get("score", 0), reverse=True)
            docs_info = docs_info[:6]
        else:
            # Fallback: full-text search
            r = await db.execute(text("""
                SELECT so_hieu, ten, tinh_trang, tom_tat,
                       LEFT(noi_dung, :maxc) as nd
                FROM documents
                WHERE to_tsvector('simple', coalesce(ten,'') || ' ' || coalesce(noi_dung,''))
                      @@ plainto_tsquery('simple', :q)
                LIMIT 5
            """), {"q": question, "maxc": MAX_DOC_CHARS})
            docs_info.extend([dict(row) for row in r.mappings().all()])

    # Build context string — tổng không quá MAX_CONTEXT_CHARS
    context_parts = []
    citations     = []
    total_chars   = 0

    for d in docs_info[:6]:
        so      = d.get("so_hieu", "")
        ten     = d.get("ten", "")
        status  = "⚠️ ĐÃ HẾT HIỆU LỰC" if d.get("tinh_trang") == "het_hieu_luc" else "✅ Còn hiệu lực"
        content = d.get("nd") or d.get("tom_tat") or ""

        # Strip HTML tags nếu có
        content = re.sub(r'<[^>]+>', ' ', content)
        content = re.sub(r'\s+', ' ', content).strip()

        # Cắt nếu tổng context quá lớn
        remaining = MAX_CONTEXT_CHARS - total_chars
        if remaining <= 500:
            break
        content = content[:remaining]
        total_chars += len(content)

        context_parts.append(f"### {so} — {ten} [{status}]\n{content}")
        citations.append({"so_hieu": so, "ten": ten, "tinh_trang": d.get("tinh_trang")})

    return "\n\n---\n\n".join(context_parts), citations


async def stream_quick_analysis(db: AsyncSession, question: str, context_ids: list) -> AsyncGenerator:
    context, citations = await get_context_docs(db, question, context_ids)

    prompt = f"""Bạn là chuyên gia tư vấn thuế Việt Nam với 30 năm kinh nghiệm tại Big 4 (KPMG/Deloitte/PwC/E&Y).

## Câu hỏi của khách hàng:
{question}

## Văn bản pháp luật và công văn liên quan:
{context if context else "(Không tìm thấy văn bản liên quan trong database — hãy trả lời dựa trên kiến thức chung về thuế Việt Nam và lưu ý điều này)"}

## Yêu cầu trả lời:
- Phân tích đầy đủ, chuyên sâu — không bị giới hạn độ dài
- Trích dẫn cụ thể: số điều, khoản, điểm của từng văn bản
- Cảnh báo rõ nếu văn bản đã hết hiệu lực và văn bản thay thế
- Nêu các trường hợp ngoại lệ, điều kiện áp dụng
- Ví dụ thực tế minh họa khi phù hợp
- Kết luận rõ ràng, actionable
- Ngôn ngữ: Tiếng Việt chuyên nghiệp"""

    yield {"type": "citations", "docs": citations}
    try:
        client = get_client()
        stream = await client.chat.completions.create(
            model=CLAUDIBLE_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            stream=True,
            messages=[{"role": "user", "content": prompt}],
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield {"type": "text", "content": delta}
    except Exception as e:
        yield {"type": "error", "content": f"Lỗi AI: {str(e)}"}
    yield {"type": "done"}


async def stream_analyze_doc(db: AsyncSession, source: str, doc_id: int) -> AsyncGenerator:
    """Phân tích toàn bộ văn bản — dùng full noi_dung không cắt."""
    if source == "documents":
        r = await db.execute(text("""
            SELECT so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
                   LEFT(noi_dung, :maxc) as noi_dung
            FROM documents WHERE id=:id
        """), {"id": doc_id, "maxc": MAX_DOC_CHARS})
    elif source == "cong_van":
        r = await db.execute(text("""
            SELECT so_hieu, ten, 'CV' as loai, ngay_ban_hanh,
                   'con_hieu_luc' as tinh_trang, sac_thue,
                   LEFT(noi_dung_day_du, :maxc) as noi_dung
            FROM cong_van WHERE id=:id
        """), {"id": doc_id, "maxc": MAX_CV_CHARS})
    else:
        yield {"type": "error", "content": "Nguồn không hợp lệ"}
        return

    row = r.mappings().first()
    if not row:
        yield {"type": "error", "content": "Không tìm thấy văn bản"}
        return

    d = dict(row)
    status  = "ĐÃ HẾT HIỆU LỰC" if d.get("tinh_trang") == "het_hieu_luc" else "Còn hiệu lực"
    # Strip HTML
    noi_dung = re.sub(r'<[^>]+>', ' ', d.get("noi_dung") or "")
    noi_dung = re.sub(r'\s+', ' ', noi_dung).strip()

    prompt = f"""Bạn là chuyên gia tư vấn thuế Việt Nam với 30 năm kinh nghiệm tại Big 4.
Hãy phân tích toàn diện văn bản pháp luật thuế sau:

## {d.get("so_hieu","(chưa có số hiệu)")} — {d.get("ten","")}
- **Loại văn bản:** {d.get("loai","")}
- **Ngày ban hành:** {str(d.get("ngay_ban_hanh",""))[:10]}
- **Tình trạng hiệu lực:** {status}

## Toàn văn:
{noi_dung if noi_dung else "(Nội dung chưa được import)"}

## Yêu cầu phân tích — trả lời đầy đủ, không giới hạn độ dài:

### 1. Tóm tắt nội dung
Tóm tắt các quy định chính (5-10 câu).

### 2. Điểm mới / Thay đổi quan trọng
So với quy định trước, văn bản này thay đổi gì? Điểm nào là mới hoàn toàn?

### 3. Phạm vi áp dụng
Ai phải tuân thủ? Đối tượng nào được miễn/loại trừ?

### 4. Các quy định quan trọng cần chú ý
Liệt kê và giải thích từng điều khoản quan trọng (số điều, khoản, điểm cụ thể).

### 5. Tác động thực tế
Ảnh hưởng đến doanh nghiệp / cá nhân như thế nào? Ví dụ minh họa.

### 6. Rủi ro & Điểm dễ sai
Những điểm thường bị hiểu sai, deadline quan trọng, điều kiện dễ bỏ sót.

### 7. Tình trạng hiệu lực
{status}. Nếu hết hiệu lực: văn bản nào thay thế?"""

    try:
        client = get_client()
        stream = await client.chat.completions.create(
            model=CLAUDIBLE_MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            stream=True,
            messages=[{"role": "user", "content": prompt}],
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield {"type": "text", "content": delta}
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
        ORDER BY embedding<=>:emb::vector LIMIT 8
    """), {"emb": emb_str, "did": doc_id if source == "documents" else -1})
    related = [{"id": d["id"], "so_hieu": d["so_hieu"], "ten": d["ten"],
                "loai": d["loai"], "tinh_trang": d["tinh_trang"],
                "sac_thue": d["sac_thue"], "source": "documents",
                "score": round(float(d["score"]), 3)} for d in r2.mappings().all()]
    return {"related": sorted(related, key=lambda x: x["score"], reverse=True)}
