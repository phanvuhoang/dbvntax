# BRIEF: dbvntax v3 — RAG Multi-source + Doc Relations + Admin Enhancement
_Tạo: 2026-03-30_

## Tổng quan
Đây là brief tổng hợp 3 tính năng lớn, làm trong một lần:
1. **RAG v2** — search documents + cong_van, timeline-aware
2. **Doc Relations** — quan hệ giữa văn bản (sửa đổi, thay thế, hướng dẫn...)
3. **Admin Enhancement** — xem/sửa thuộc tính văn bản, quản lý relations, check VB thiếu

---

## PHẦN A — Database Migrations

### A1. Thêm 3 fields vào `documents` table

```sql
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS nguoi_ky VARCHAR(100),
  ADD COLUMN IF NOT EXISTS ngay_cong_bao DATE,
  ADD COLUMN IF NOT EXISTS so_cong_bao VARCHAR(100);
```

### A2. Tạo table `doc_relations`

```sql
CREATE TABLE IF NOT EXISTS doc_relations (
    id SERIAL PRIMARY KEY,
    source_id INT REFERENCES documents(id) ON DELETE CASCADE,
    target_so_hieu VARCHAR(200) NOT NULL,
    target_id INT REFERENCES documents(id) ON DELETE SET NULL,
    relation_type VARCHAR(50) NOT NULL,
    ghi_chu TEXT,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rel_source ON doc_relations(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target_so_hieu ON doc_relations(target_so_hieu);
CREATE INDEX IF NOT EXISTS idx_rel_type ON doc_relations(relation_type);
```

**relation_type values:**
- `huong_dan` — VB này hướng dẫn VB kia (VB này thấp hơn, ra sau)
- `duoc_huong_dan` — VB này được VB kia hướng dẫn
- `sua_doi` — VB này sửa đổi/bổ sung VB kia
- `bi_sua_doi` — VB này bị VB kia sửa đổi/bổ sung
- `thay_the` — VB này thay thế VB kia
- `bi_thay_the` — VB này bị VB kia thay thế
- `hop_nhat` — VB này hợp nhất VB kia
- `can_cu` — VB này căn cứ vào VB kia (VB kia là cơ sở pháp lý)
- `dinh_chinh` — VB này đính chính VB kia
- `lien_quan` — VB liên quan cùng nội dung

### A3. Tạo table `missing_docs_watchlist`

```sql
CREATE TABLE IF NOT EXISTS missing_docs_watchlist (
    id SERIAL PRIMARY KEY,
    so_hieu VARCHAR(200) UNIQUE NOT NULL,
    ten TEXT,
    loai VARCHAR(20),
    ngay_ban_hanh DATE,
    mentioned_in_ids INT[],          -- array of documents.id đã đề cập
    relation_types TEXT[],           -- các loại quan hệ được nhắc đến
    priority SMALLINT DEFAULT 3,     -- 1=cao, 2=medium, 3=thấp
    status VARCHAR(20) DEFAULT 'missing',  -- missing/ignored/imported
    tvpl_url TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_missing_status ON missing_docs_watchlist(status);
CREATE INDEX IF NOT EXISTS idx_missing_priority ON missing_docs_watchlist(priority);
```

---

## PHẦN B — Backend API (`main.py`)

### B1. Thêm import
Đầu file, thêm:
```python
import asyncio
```
(kiểm tra nếu chưa có)

### B2. Thêm Pydantic models

```python
class DocRelationCreate(BaseModel):
    source_id: int
    target_so_hieu: str
    target_id: Optional[int] = None
    relation_type: str
    ghi_chu: Optional[str] = None
    verified: bool = False

class DocRelationUpdate(BaseModel):
    target_so_hieu: Optional[str] = None
    target_id: Optional[int] = None
    relation_type: Optional[str] = None
    ghi_chu: Optional[str] = None
    verified: Optional[bool] = None

class DocumentUpdate(BaseModel):
    so_hieu: Optional[str] = None
    ten: Optional[str] = None
    loai: Optional[str] = None
    co_quan: Optional[str] = None
    nguoi_ky: Optional[str] = None
    ngay_ban_hanh: Optional[str] = None
    hieu_luc_tu: Optional[str] = None
    het_hieu_luc_tu: Optional[str] = None
    ngay_cong_bao: Optional[str] = None
    so_cong_bao: Optional[str] = None
    tinh_trang: Optional[str] = None
    sac_thue: Optional[List[str]] = None
    tom_tat: Optional[str] = None
    importance: Optional[int] = None

class MissingDocUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = None
    notes: Optional[str] = None
    tvpl_url: Optional[str] = None
```

### B3. Endpoints mới cho Doc Relations

```python
# ── GET relations của 1 văn bản ──────────────────────────────────────────────
@app.get("/api/admin/documents/{doc_id}/relations")
async def get_doc_relations(doc_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    r = await db.execute(text("""
        SELECT dr.*, d2.ten as target_ten, d2.loai as target_loai
        FROM doc_relations dr
        LEFT JOIN documents d2 ON dr.target_id = d2.id
        WHERE dr.source_id = :doc_id
        ORDER BY dr.relation_type, dr.created_at
    """), {"doc_id": doc_id})
    return [dict(row) for row in r.mappings().all()]

# ── CREATE relation ───────────────────────────────────────────────────────────
@app.post("/api/admin/relations")
async def create_relation(req: DocRelationCreate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    # Auto-resolve target_id từ target_so_hieu nếu chưa có
    if not req.target_id and req.target_so_hieu:
        r = await db.execute(text("SELECT id FROM documents WHERE so_hieu = :sh"), {"sh": req.target_so_hieu})
        row = r.fetchone()
        if row:
            req.target_id = row[0]
    r = await db.execute(text("""
        INSERT INTO doc_relations (source_id, target_so_hieu, target_id, relation_type, ghi_chu, verified)
        VALUES (:source_id, :target_so_hieu, :target_id, :relation_type, :ghi_chu, :verified)
        RETURNING id
    """), req.model_dump())
    await db.commit()
    return {"id": r.scalar(), "status": "created"}

# ── UPDATE relation ───────────────────────────────────────────────────────────
@app.put("/api/admin/relations/{rel_id}")
async def update_relation(rel_id: int, req: DocRelationUpdate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Không có field nào để update")
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates["rel_id"] = rel_id
    await db.execute(text(f"UPDATE doc_relations SET {set_clause}, updated_at=NOW() WHERE id=:rel_id"), updates)
    await db.commit()
    return {"status": "updated"}

# ── DELETE relation ───────────────────────────────────────────────────────────
@app.delete("/api/admin/relations/{rel_id}")
async def delete_relation(rel_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    await db.execute(text("DELETE FROM doc_relations WHERE id=:id"), {"id": rel_id})
    await db.commit()
    return {"status": "deleted"}
```

### B4. Endpoint UPDATE document (edit thuộc tính)

```python
@app.put("/api/admin/documents/{doc_id}")
async def update_document(doc_id: int, req: DocumentUpdate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Không có field nào để update")
    # Handle date fields
    for date_field in ["ngay_ban_hanh", "hieu_luc_tu", "het_hieu_luc_tu", "ngay_cong_bao"]:
        if date_field in updates and updates[date_field]:
            updates[date_field] = f"{updates[date_field]}::date"
    set_clause = ", ".join(f"{k}=:{k}" for k in updates if not str(updates.get(k, "")).endswith("::date"))
    # Rebuild properly for dates
    set_parts = []
    for k, v in updates.items():
        if k in ["ngay_ban_hanh", "hieu_luc_tu", "het_hieu_luc_tu", "ngay_cong_bao"] and v:
            set_parts.append(f"{k}=:{k}::date")
        else:
            set_parts.append(f"{k}=:{k}")
    updates["doc_id"] = doc_id
    await db.execute(text(f"UPDATE documents SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=:doc_id"), updates)
    await db.commit()
    return {"status": "updated"}
```

### B5. Endpoints Missing Docs Watchlist

```python
# ── GET watchlist ─────────────────────────────────────────────────────────────
@app.get("/api/admin/missing-docs")
async def get_missing_docs(
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin)
):
    where = ["1=1"]
    params = {}
    if status:
        where.append("status = :status")
        params["status"] = status
    if priority:
        where.append("priority = :priority")
        params["priority"] = priority
    clause = "WHERE " + " AND ".join(where)
    r = await db.execute(text(f"""
        SELECT * FROM missing_docs_watchlist {clause}
        ORDER BY priority ASC, created_at DESC
    """), params)
    return [dict(row) for row in r.mappings().all()]

# ── UPDATE missing doc status ────────────────────────────────────────────────
@app.put("/api/admin/missing-docs/{item_id}")
async def update_missing_doc(item_id: int, req: MissingDocUpdate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Không có field nào")
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates["item_id"] = item_id
    await db.execute(text(f"UPDATE missing_docs_watchlist SET {set_clause}, updated_at=NOW() WHERE id=:item_id"), updates)
    await db.commit()
    return {"status": "updated"}

# ── AI Extract relations từ 1 document ───────────────────────────────────────
@app.post("/api/admin/documents/{doc_id}/extract-relations")
async def extract_relations(doc_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    """
    Dùng OpenAI để extract quan hệ văn bản từ nội dung.
    Trả về relations tìm được + missing docs để admin review trước khi save.
    """
    import openai
    r = await db.execute(text("SELECT so_hieu, ten, loai, noi_dung, tom_tat FROM documents WHERE id=:id"), {"id": doc_id})
    doc = r.mappings().first()
    if not doc:
        raise HTTPException(404, "Không tìm thấy văn bản")

    content = (doc["noi_dung"] or doc["tom_tat"] or "")[:6000]

    prompt = f"""Phân tích văn bản pháp luật Việt Nam sau và extract các quan hệ pháp lý.

Văn bản: {doc["so_hieu"]} — {doc["ten"]}
Nội dung (trích):
{content}

Hãy tìm tất cả các văn bản pháp luật khác được đề cập và xác định quan hệ:
- huong_dan: văn bản này hướng dẫn thực hiện văn bản kia
- duoc_huong_dan: văn bản này được văn bản kia hướng dẫn
- sua_doi: văn bản này sửa đổi/bổ sung văn bản kia
- bi_sua_doi: văn bản này bị sửa đổi bởi văn bản kia
- thay_the: văn bản này thay thế văn bản kia
- bi_thay_the: văn bản này bị thay thế bởi văn bản kia
- hop_nhat: văn bản hợp nhất
- can_cu: văn bản này căn cứ vào văn bản kia
- dinh_chinh: văn bản đính chính
- lien_quan: liên quan cùng nội dung

Trả về JSON array:
[
  {{
    "target_so_hieu": "78/2014/TT-BTC",
    "relation_type": "bi_thay_the",
    "ghi_chu": "Bị thay thế từ ngày 01/01/2016"
  }},
  ...
]

Chỉ trả về JSON array, không giải thích thêm. Nếu không tìm thấy quan hệ nào, trả về [].
"""

    client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        messages=[
            {"role": "system", "content": "Bạn là chuyên gia pháp lý Việt Nam. Trả về JSON chính xác."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )

    raw = resp.choices[0].message.content
    try:
        # Handle cả trường hợp trả về {"relations": [...]} hoặc trực tiếp [...]
        parsed = json.loads(raw)
        relations = parsed if isinstance(parsed, list) else parsed.get("relations", parsed.get("data", []))
    except Exception:
        relations = []

    # Cross-check với DB để tìm missing docs
    missing = []
    for rel in relations:
        sh = rel.get("target_so_hieu", "")
        if sh:
            r2 = await db.execute(text("SELECT id FROM documents WHERE so_hieu = :sh"), {"sh": sh})
            row = r2.fetchone()
            rel["target_id"] = row[0] if row else None
            if not row:
                # Check missing_docs_watchlist
                r3 = await db.execute(text("SELECT id FROM missing_docs_watchlist WHERE so_hieu = :sh"), {"sh": sh})
                if not r3.fetchone():
                    missing.append({
                        "so_hieu": sh,
                        "relation_type": rel.get("relation_type"),
                        "mentioned_in": doc["so_hieu"]
                    })

    return {
        "doc_id": doc_id,
        "so_hieu": doc["so_hieu"],
        "relations_found": relations,
        "missing_docs": missing,
        "count": len(relations)
    }

# ── Save extracted relations (sau khi admin review) ────────────────────────
@app.post("/api/admin/documents/{doc_id}/save-relations")
async def save_relations(
    doc_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin)
):
    """
    Save relations sau khi admin review extract-relations output.
    body: { relations: [...], missing_docs: [...] }
    """
    relations = body.get("relations", [])
    missing_docs = body.get("missing_docs", [])

    # Get source doc so_hieu
    r = await db.execute(text("SELECT so_hieu FROM documents WHERE id=:id"), {"id": doc_id})
    doc = r.mappings().first()

    saved = 0
    for rel in relations:
        sh = rel.get("target_so_hieu", "")
        if not sh:
            continue
        # Resolve target_id
        r2 = await db.execute(text("SELECT id FROM documents WHERE so_hieu=:sh"), {"sh": sh})
        row = r2.fetchone()
        target_id = row[0] if row else None

        # Upsert
        await db.execute(text("""
            INSERT INTO doc_relations (source_id, target_so_hieu, target_id, relation_type, ghi_chu, verified)
            VALUES (:source_id, :target_so_hieu, :target_id, :relation_type, :ghi_chu, TRUE)
            ON CONFLICT DO NOTHING
        """), {
            "source_id": doc_id,
            "target_so_hieu": sh,
            "target_id": target_id,
            "relation_type": rel.get("relation_type", "lien_quan"),
            "ghi_chu": rel.get("ghi_chu")
        })
        saved += 1

    # Add to missing_docs_watchlist
    added_missing = 0
    for m in missing_docs:
        sh = m.get("so_hieu", "")
        if not sh:
            continue
        await db.execute(text("""
            INSERT INTO missing_docs_watchlist (so_hieu, ten, mentioned_in_ids, relation_types, priority)
            VALUES (:so_hieu, :ten, ARRAY[:doc_id], ARRAY[:rel_type], 2)
            ON CONFLICT (so_hieu) DO UPDATE SET
                mentioned_in_ids = array_append(missing_docs_watchlist.mentioned_in_ids, :doc_id),
                updated_at = NOW()
        """), {
            "so_hieu": sh,
            "ten": m.get("ten"),
            "doc_id": doc_id,
            "rel_type": m.get("relation_type", "lien_quan")
        })
        added_missing += 1

    await db.commit()
    return {"saved_relations": saved, "added_to_watchlist": added_missing}
```

### B6. Nâng cấp `/api/ask` endpoint (RAG v2)

Thêm import ở đầu file (sau `from rag import rag_answer`):
```python
from search import search_semantic_docs_for_rag  # sẽ thêm vào search.py bên dưới
```

Thêm `docs_top_k` vào `AskRequest`:
```python
class AskRequest(BaseModel):
    question: str
    top_k: int = 15
    docs_top_k: int = 5
```

Thay thế hàm `ask()`:
```python
@app.post("/api/ask")
async def ask(req: AskRequest, db: AsyncSession = Depends(get_db)):
    """RAG v2: tìm văn bản pháp luật + công văn → AI trả lời câu hỏi thuế."""
    if not req.question or len(req.question.strip()) < 5:
        raise HTTPException(400, "Câu hỏi quá ngắn")

    # Search song song documents + cong_van
    docs, (cv_results, _cv_total) = await asyncio.gather(
        search_semantic_docs_for_rag(db, req.question, top_k=req.docs_top_k),
        search_semantic_cv(db, req.question, {}, limit=req.top_k, offset=0)
    )

    answer_data = await rag_answer(req.question, cv_results, docs=docs)

    return {
        "question":      req.question,
        "answer":        answer_data["answer"],
        "model_used":    answer_data["model_used"],
        "is_timeline":   answer_data["is_timeline"],
        "sources_count": len(answer_data["sources"]),
        "docs_count":    len(docs),
        "cv_count":      len(cv_results),
        "sources":       answer_data["sources"],
    }
```

---

## PHẦN C — `search.py`

Thêm function mới (KHÔNG sửa function hiện có):

```python
async def search_semantic_docs_for_rag(db: AsyncSession, q: str, top_k: int = 5) -> list[dict]:
    """
    Semantic search trên documents table cho RAG.
    Lấy top_k tốt nhất, không threshold (documents ít, cần lấy đủ).
    """
    emb = await embed_text(q)
    if not emb:
        return []
    try:
        r = await db.execute(text("""
            SELECT id, so_hieu, ten, loai, co_quan,
                   ngay_ban_hanh, hieu_luc_tu, het_hieu_luc_tu,
                   tinh_trang, sac_thue, tvpl_url, link_tvpl,
                   LEFT(COALESCE(noi_dung, tom_tat, ''), 2000) as noi_dung,
                   1-(embedding <=> CAST(:emb AS vector)) AS score
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :top_k
        """), {"emb": str(emb), "top_k": top_k})
        rows = [dict(row) for row in r.mappings().all()]
        for row in rows:
            row["source"] = "document"
        return rows
    except Exception as e:
        print(f"search_semantic_docs_for_rag error: {e}")
        return []
```

---

## PHẦN D — `rag.py`

### D1. Thêm vào đầu file
```python
import unicodedata
```

### D2. Thêm `SYSTEM_PROMPT_TIMELINE` (bên cạnh `SYSTEM_PROMPT` hiện có)
```python
SYSTEM_PROMPT_TIMELINE = """Bạn là chuyên gia tư vấn thuế Việt Nam với 30 năm kinh nghiệm.

Trả lời câu hỏi dựa HOÀN TOÀN vào các văn bản và công văn được cung cấp.

Quy tắc:
- Chỉ dùng thông tin từ tài liệu được cung cấp, KHÔNG suy đoán
- Trích dẫn số hiệu văn bản/công văn cụ thể
- Khi có nhiều giai đoạn: trình bày TUẦN TỰ từ cũ đến mới, nêu rõ sự thay đổi
- Phân biệt rõ: 📜 Văn bản pháp luật (Luật/NĐ/TT) và 📨 Công văn hướng dẫn
- Nếu tài liệu không đủ → nói rõ "Chưa đủ thông tin trong cơ sở dữ liệu"
- Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc"""
```

### D3. Thêm `detect_timeline_query()`
```python
def detect_timeline_query(question: str) -> bool:
    """Phát hiện câu hỏi liên quan nhiều giai đoạn thời gian."""
    import re as _re
    q = unicodedata.normalize("NFC", question.lower())
    patterns = [
        r"từ năm|từ \d{4}|trước năm|sau năm|đến năm|giai đoạn|thời kỳ",
        r"trước khi|sau khi|kể từ|thay đổi|thay thế|sửa đổi",
        r"lịch sử|quá trình|quy định cũ|quy định mới|trước đây",
        r"năm 20\d\d.{1,20}năm 20\d\d",
        r"các thời kỳ|qua các năm|từng giai đoạn",
    ]
    return any(_re.search(p, q) for p in patterns)
```

### D4. Thêm `build_context_multisource()`
```python
def build_context_multisource(docs: list[dict], cvs: list[dict],
                               max_chars_doc: int = 2000, max_chars_cv: int = 1200) -> str:
    """Build context kết hợp documents (trước) + CV (sau)."""
    from bs4 import BeautifulSoup as _BS
    import re as _re

    def strip(html, n):
        if not html: return ""
        text = _BS(html, "html.parser").get_text(" ") if "<" in html else html
        return _re.sub(r"\s+", " ", text).strip()[:n]

    parts = []
    if docs:
        parts.append("=== VĂN BẢN PHÁP LUẬT ===")
        for i, d in enumerate(docs, 1):
            hl = f"Hiệu lực từ: {d.get('hieu_luc_tu')}" if d.get("hieu_luc_tu") else ""
            het = f" → {d.get('het_hieu_luc_tu')}" if d.get("het_hieu_luc_tu") else " (đến nay)"
            parts.append(
                f"[VB{i}] {d.get('loai','')} {d.get('so_hieu','')} "
                f"(ban hành: {d.get('ngay_ban_hanh','')}, score={float(d.get('score',0)):.3f})\n"
                f"Tiêu đề: {d.get('ten','')}\n"
                f"{hl}{het if hl else ''}\n"
                f"Tình trạng: {d.get('tinh_trang','')}\n"
                f"Nội dung: {strip(d.get('noi_dung') or d.get('tom_tat',''), max_chars_doc)}"
            )
    if cvs:
        parts.append("\n=== CÔNG VĂN HƯỚNG DẪN ===")
        for i, cv in enumerate(cvs, 1):
            parts.append(
                f"[CV{i}] {cv.get('so_hieu','')} "
                f"(ngày {cv.get('ngay_ban_hanh','')}, score={float(cv.get('score',0)):.3f})\n"
                f"Cơ quan: {cv.get('co_quan','')}\n"
                f"Tiêu đề: {cv.get('ten','')}\n"
                f"Nội dung: {strip(cv.get('noi_dung_day_du',''), max_chars_cv)}"
            )
    return "\n\n---\n\n".join(parts)
```

### D5. Thêm `build_context_timeline()`
```python
def build_context_timeline(docs: list[dict], cvs: list[dict],
                            max_chars_doc: int = 1500, max_chars_cv: int = 1000) -> str:
    """Build context phân theo giai đoạn thời gian."""
    from bs4 import BeautifulSoup as _BS
    import re as _re
    from datetime import date as _date

    def strip(html, n):
        if not html: return ""
        text = _BS(html, "html.parser").get_text(" ") if "<" in html else html
        return _re.sub(r"\s+", " ", text).strip()[:n]

    def get_year(item):
        val = item.get("hieu_luc_tu") or item.get("ngay_ban_hanh")
        if not val: return 9999
        try:
            return int(str(val)[:4])
        except: return 9999

    # Prep + sort
    all_items = []
    for d in docs:
        d = dict(d); d["_type"] = "document"
        d["_content"] = strip(d.get("noi_dung") or d.get("tom_tat",""), max_chars_doc)
        all_items.append(d)
    for cv in cvs:
        cv = dict(cv); cv["_type"] = "cong_van"
        cv["_content"] = strip(cv.get("noi_dung_day_du",""), max_chars_cv)
        all_items.append(cv)
    all_items.sort(key=lambda x: get_year(x))

    # Group by năm hiệu lực document → tạo breakpoints
    doc_years = sorted(set(get_year(d) for d in all_items if d["_type"] == "document" and get_year(d) != 9999))

    # Nếu ít hơn 2 mốc → không group, hiển thị flat
    if len(doc_years) < 2:
        return build_context_multisource(docs, cvs, max_chars_doc, max_chars_cv)

    # Group items vào periods
    periods = {}
    for item in all_items:
        y = get_year(item)
        # Tìm period phù hợp
        assigned = False
        for i, dy in enumerate(doc_years):
            next_dy = doc_years[i+1] if i+1 < len(doc_years) else 9999
            if dy <= y < next_dy:
                label = f"Từ {dy}" if i == len(doc_years)-1 else f"{dy}–{next_dy-1}"
                periods.setdefault(label, []).append(item)
                assigned = True
                break
        if not assigned:
            label = f"Trước {doc_years[0]}" if y < doc_years[0] else f"Từ {doc_years[-1]} đến nay"
            periods.setdefault(label, []).append(item)

    parts = []
    for label, items in periods.items():
        parts.append(f"=== GIAI ĐOẠN: {label} ===")
        for item in items:
            if item["_type"] == "document":
                hl = f" | Hiệu lực từ: {item.get('hieu_luc_tu')}" if item.get("hieu_luc_tu") else ""
                parts.append(
                    f"📜 [VB] {item.get('loai','')} {item.get('so_hieu','')} "
                    f"(ban hành: {item.get('ngay_ban_hanh','')}{hl})\n"
                    f"Tiêu đề: {item.get('ten','')}\n"
                    f"Tình trạng: {item.get('tinh_trang','')}\n"
                    f"Nội dung: {item.get('_content','')}"
                )
            else:
                parts.append(
                    f"📨 [CV] {item.get('so_hieu','')} (ngày {item.get('ngay_ban_hanh','')})\n"
                    f"Cơ quan: {item.get('co_quan','')}\n"
                    f"Tiêu đề: {item.get('ten','')}\n"
                    f"Nội dung: {item.get('_content','')}"
                )
        parts.append("")
    return "\n\n".join(parts)
```

### D6. Thay thế toàn bộ hàm `rag_answer()`

Giữ nguyên `ask_claudible()`, `ask_openai()`, `ask_anthropic()`, `build_context()` cũ (không xóa). Chỉ replace `rag_answer()`:

```python
async def rag_answer(question: str, cv_list: list[dict], docs: list[dict] = None) -> dict:
    """RAG v2 — multi-source + timeline-aware."""
    docs = docs or []

    if not cv_list and not docs:
        return {
            "answer": "Không tìm thấy văn bản hoặc công văn liên quan trong cơ sở dữ liệu.",
            "model_used": None, "sources": [], "is_timeline": False,
        }

    is_timeline = detect_timeline_query(question)

    if is_timeline:
        context = build_context_timeline(docs, cv_list)
        system = SYSTEM_PROMPT_TIMELINE
        user_msg = (
            f"CÁC TÀI LIỆU (theo giai đoạn):\n{context}\n\n---\n\n"
            f"CÂU HỎI: {question}\n\n"
            "Trả lời theo từng giai đoạn (cũ → mới), nêu rõ sự thay đổi giữa các giai đoạn. "
            "Kết thúc bằng tóm tắt ngắn gọn."
        )
    else:
        context = build_context_multisource(docs, cv_list)
        system = SYSTEM_PROMPT
        user_msg = (
            f"CÁC TÀI LIỆU THAM KHẢO:\n{context}\n\n---\n\n"
            f"CÂU HỎI: {question}\n\nHãy trả lời dựa vào các tài liệu trên."
        )

    answer = None
    model_used = None

    if OPENAI_KEY:
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                    json={"model": OPENAI_MODEL, "max_tokens": 2000,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]}
                )
                r.raise_for_status()
                answer = r.json()["choices"][0]["message"]["content"]
                model_used = f"openai/{OPENAI_MODEL}"
        except Exception as e:
            print(f"OpenAI error: {e}")

    if answer is None and ANTHROPIC_KEY:
        try:
            import anthropic as ant
            client = ant.AsyncAnthropic(api_key=ANTHROPIC_KEY)
            msg = await client.messages.create(
                model=ANTHROPIC_MODEL, max_tokens=2000, system=system,
                messages=[{"role": "user", "content": user_msg}]
            )
            answer = msg.content[0].text
            model_used = f"anthropic/{ANTHROPIC_MODEL}"
        except Exception as e:
            print(f"Anthropic error: {e}")

    if answer is None and CLAUDIBLE_KEY:
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post(
                    f"{CLAUDIBLE_BASE}/messages",
                    headers={"Authorization": f"Bearer {CLAUDIBLE_KEY}", "Content-Type": "application/json"},
                    json={"model": CLAUDIBLE_MODEL, "max_tokens": 2000, "system": system,
                          "messages": [{"role": "user", "content": user_msg}]}
                )
                r.raise_for_status()
                answer = r.json()["content"][0]["text"]
                model_used = f"claudible/{CLAUDIBLE_MODEL}"
        except Exception as e:
            print(f"Claudible error: {e}")
            answer = "Lỗi hệ thống: không thể kết nối AI."
            model_used = "error"

    # Build sources — documents trước, CV sau
    sources = []
    for d in docs:
        sources.append({
            "source_type": "document",
            "so_hieu": d.get("so_hieu"), "ten": d.get("ten"),
            "loai": d.get("loai"), "ngay_ban_hanh": str(d.get("ngay_ban_hanh") or ""),
            "hieu_luc_tu": str(d.get("hieu_luc_tu") or ""),
            "het_hieu_luc_tu": str(d.get("het_hieu_luc_tu") or ""),
            "tinh_trang": d.get("tinh_trang"),
            "link_nguon": d.get("tvpl_url") or d.get("link_tvpl"),
            "score": round(float(d.get("score") or 0), 3),
        })
    for cv in cv_list:
        sources.append({
            "source_type": "cong_van",
            "so_hieu": cv.get("so_hieu"), "ten": cv.get("ten"),
            "loai": "CV", "ngay_ban_hanh": str(cv.get("ngay_ban_hanh") or ""),
            "hieu_luc_tu": "", "het_hieu_luc_tu": "",
            "tinh_trang": cv.get("tinh_trang") or "",
            "link_nguon": cv.get("link_nguon"),
            "score": round(float(cv.get("score") or 0), 3),
        })

    return {"answer": answer, "model_used": model_used, "sources": sources, "is_timeline": is_timeline}
```

---

## PHẦN E — Frontend (`AdminPage.tsx`)

### E1. Thêm tab mới vào AdminPage

Hiện tại có 2 tabs: `corpus` | `tvpl`. Thêm 2 tabs mới:
- `documents` — Quản lý văn bản (xem/sửa thuộc tính + relations)
- `watchlist` — Văn bản thiếu cần bổ sung

```typescript
type AdminTab = 'corpus' | 'tvpl' | 'documents' | 'watchlist';
```

### E2. Tab "Văn bản" (`documents` tab)

**Layout:**
```
[Search/Filter bar: loai | sac_thue | keyword search]

Table: so_hieu | ten (truncate 60) | loai | ngay_ban_hanh | tinh_trang | Actions
       [Edit] [Relations] [Extract AI]
```

**Edit Modal** (khi click Edit):
Form với các fields:
- `so_hieu` (text)
- `ten` (textarea)
- `loai` (select: ND/TT/Luat/VBHN/QD/NQ/Khac)
- `co_quan` (text)
- `nguoi_ky` (text) — field mới
- `ngay_ban_hanh` (date picker)
- `hieu_luc_tu` (date picker)
- `het_hieu_luc_tu` (date picker — nếu điền = hết hiệu lực)
- `ngay_cong_bao` (date picker) — field mới
- `so_cong_bao` (text) — field mới
- `tinh_trang` (select: con_hieu_luc / het_hieu_luc / chua_hieu_luc)
- `sac_thue` (multi-select checkboxes)
- `tom_tat` (textarea)
- `importance` (select: 1=Rất quan trọng / 2=Quan trọng / 3=Bình thường)

Buttons: [Lưu] [Hủy]

**Relations Panel** (khi click Relations):
Side panel hoặc modal:
```
📋 Quan hệ văn bản: {so_hieu}

[+ Thêm quan hệ]

Table của relations hiện có:
Loại quan hệ | Văn bản liên quan | Ghi chú | Verified | [Xóa]

[Extract từ AI] → hiển thị kết quả → [Lưu tất cả] hoặc chọn từng cái
```

**"Extract từ AI" flow:**
1. Click button → gọi `POST /api/admin/documents/{id}/extract-relations`
2. Hiển thị kết quả: danh sách relations tìm được + missing docs
3. Cho admin check/uncheck từng relation
4. Click "Lưu đã chọn" → gọi `POST /api/admin/documents/{id}/save-relations`

### E3. Tab "VB Thiếu" (`watchlist` tab)

**Layout:**
```
[Filter: status=missing|ignored|imported] [priority filter]

Stats: X văn bản thiếu | Y đã xử lý

Table:
so_hieu | loai | Được đề cập trong | Loại quan hệ | Priority | Status | Actions
[Đã có] [Bỏ qua] [TVPL URL input + Crawl]
```

- **[Đã có]**: mark status='imported'
- **[Bỏ qua]**: mark status='ignored'
- Priority badge: 🔴 Cao / 🟡 Trung bình / ⚪ Thấp

### E4. Tab "Hỏi AI" (`AskAIPage.tsx`) — cập nhật sources display

Cập nhật TypeScript types:
```typescript
interface AskSource {
  source_type: 'document' | 'cong_van';
  so_hieu: string;
  ten: string;
  loai: string;
  ngay_ban_hanh: string;
  hieu_luc_tu: string;
  het_hieu_luc_tu: string;
  tinh_trang: string;
  link_nguon: string | null;
  score: number;
}

interface AskResponse {
  question: string;
  answer: string;
  model_used: string;
  is_timeline: boolean;
  sources_count: number;
  docs_count: number;
  cv_count: number;
  sources: AskSource[];
}
```

Trong phần render sources:
- Group sources: Documents trước (header "📜 Văn bản pháp luật"), CV sau ("📨 Công văn hướng dẫn")
- Mỗi source card:
  - Documents: badge loại văn bản (màu xanh dương), `so_hieu`, `ten` truncate, dòng nhỏ hiệu lực + tinh_trang
  - CV: badge "CV" (màu xám), `so_hieu`, `ten` truncate, ngày ban hành
  - Score badge góc phải, link nếu có
- Nếu `is_timeline`: hiển thị chip "⏱️ Câu hỏi đa giai đoạn"
- Stats bar: `📜 {docs_count} văn bản  •  📨 {cv_count} công văn  •  🤖 {model_used}`

---

## PHẦN F — Checklist cho Claude Code

### Database
- [ ] Chạy ALTER TABLE thêm `nguoi_ky`, `ngay_cong_bao`, `so_cong_bao` vào `documents`
- [ ] Tạo table `doc_relations`
- [ ] Tạo table `missing_docs_watchlist`
- [ ] Chạy migration trong `lifespan` hoặc file `database.py` (kiểm tra cách project đang handle migrations)

### Backend `search.py`
- [ ] Thêm `search_semantic_docs_for_rag()`

### Backend `rag.py`
- [ ] Thêm `import unicodedata`
- [ ] Thêm `SYSTEM_PROMPT_TIMELINE`
- [ ] Thêm `detect_timeline_query()`
- [ ] Thêm `build_context_multisource()`
- [ ] Thêm `build_context_timeline()`
- [ ] Replace `rag_answer()` (giữ các function cũ)

### Backend `main.py`
- [ ] Thêm `import asyncio` nếu chưa có
- [ ] Thêm `from search import search_semantic_docs_for_rag`
- [ ] Thêm Pydantic models: `DocRelationCreate`, `DocRelationUpdate`, `DocumentUpdate`, `MissingDocUpdate`
- [ ] Thêm `docs_top_k` vào `AskRequest`
- [ ] Replace `ask()` endpoint (RAG v2)
- [ ] Thêm endpoints doc relations: GET/POST/PUT/DELETE
- [ ] Thêm `PUT /api/admin/documents/{doc_id}` (update document)
- [ ] Thêm `POST /api/admin/documents/{doc_id}/extract-relations`
- [ ] Thêm `POST /api/admin/documents/{doc_id}/save-relations`
- [ ] Thêm `GET /api/admin/missing-docs`
- [ ] Thêm `PUT /api/admin/missing-docs/{item_id}`

### Frontend `AdminPage.tsx`
- [ ] Thêm tab `documents` + `watchlist` vào `AdminTab` type
- [ ] Tab Documents: table + Edit Modal + Relations Panel + Extract AI flow
- [ ] Tab Watchlist: table + filter + status actions

### Frontend `AskAIPage.tsx`
- [ ] Update `AskSource` + `AskResponse` types
- [ ] Render sources 2 nhóm (VB + CV)
- [ ] Timeline chip khi `is_timeline=true`
- [ ] Stats bar

### Build & Deploy
- [ ] `cd frontend && npm run build`
- [ ] `cp -r frontend/dist/* static/`
- [ ] Xóa file BRIEF này (`BRIEF-rag-v2-multisource-timeline.md` + file này)
- [ ] `git add -A && git commit -m "feat: RAG v2 + doc relations + admin enhancement" && git push`

---

## Ghi chú kỹ thuật

- Migration: kiểm tra file `database.py` xem có `CREATE TABLE IF NOT EXISTS` trong lifespan không — nếu có thì thêm vào đó, nếu không thì tạo file `migrations/001_v3.sql` và chạy trong lifespan
- `ON CONFLICT DO NOTHING` cho doc_relations: cần thêm UNIQUE constraint `(source_id, target_so_hieu, relation_type)`
- `response_format={"type": "json_object"}` cho OpenAI extract: cần wrap prompt để đảm bảo trả về JSON object (không phải array trực tiếp)
- Date fields trong UPDATE: dùng `::date` cast trong SQL thay vì xử lý trong Python
- AdminPage hiện dùng `fetch` trực tiếp (không qua api.ts) — giữ consistent với pattern hiện tại
