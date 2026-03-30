# BRIEF: dbvntax RAG v5 — Anchor Docs + Hybrid Search + Haiku Default
_Tạo: 2026-03-30_

## Mục tiêu
1. **Anchor system**: tag 3-5 VB quan trọng nhất mỗi sắc thuế → RAG luôn load full text làm nền
2. **Hybrid search CV**: kết hợp BM25 full-text + vector → fix lỗi "trích trước" match "trước bạ"
3. **Haiku default**: đặt Claudible claude-haiku-4-5 làm model mặc định (200K context, free)
4. **Strip HTML**: strip HTML trước khi đưa vào context → NĐ 70 từ 1.4MB → ~150KB text thực

---

## PHẦN A — Database Migration

### A1. Thêm field `is_anchor` vào `documents`

```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_anchor BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_documents_anchor ON documents(is_anchor, sac_thue) WHERE is_anchor = TRUE;
```

Chạy trong `database.py` lifespan (kiểm tra file database.py xem cách project handle migrations rồi thêm vào đúng chỗ).

---

## PHẦN B — `rag.py`

### B1. Đổi thứ tự fallback chain — Haiku làm default

Thay toàn bộ config models đầu file:

```python
CLAUDIBLE_BASE  = os.getenv("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")
CLAUDIBLE_KEY   = os.getenv("CLAUDIBLE_API_KEY", "")
CLAUDIBLE_MODEL = "claude-haiku-4-5"   # DEFAULT — 200K context, free via Claudible

GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")  # fallback 2

OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")   # fallback 3 (intent only + last resort)

ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")  # fallback 4
ANTHROPIC_MODEL = "claude-haiku-4-5"

# Intent analysis model (lightweight, fast)
INTENT_MODEL_OPENAI  = "gpt-4o-mini"
INTENT_MODEL_GEMINI  = "gemini-2.0-flash"
```

### B2. Thêm `strip_html_for_context()`

Thêm function này (dùng BeautifulSoup đã có):

```python
def strip_html_for_context(html: str, max_chars: int = 0) -> str:
    """Strip HTML tags, normalize whitespace. Optionally truncate."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup as _BS
        text = _BS(html, "html.parser").get_text(separator=" ")
    except Exception:
        import re as _re
        text = _re.sub(r"<[^>]+>", " ", html)
    import re as _re
    text = _re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... nội dung còn lại đã được rút gọn ...]"
    return text
```

### B3. Thêm `load_anchor_docs()`

```python
async def load_anchor_docs(db: AsyncSession, sac_thue_list: list[str],
                            max_chars_per_doc: int = 80_000) -> list[dict]:
    """
    Load các văn bản anchor (is_anchor=TRUE) cho sắc thuế đã xác định.
    Strip HTML → truncate → trả về list dict.
    max_chars_per_doc: sau khi strip HTML (text thực, không phải raw HTML)
    """
    if not sac_thue_list:
        return []
    try:
        # Dùng ANY để match sac_thue array
        placeholders = ", ".join(f":{i}" for i in range(len(sac_thue_list)))
        params = {str(i): st for i, st in enumerate(sac_thue_list)}
        r = await db.execute(text(f"""
            SELECT id, so_hieu, ten, loai, ngay_ban_hanh, hieu_luc_tu,
                   het_hieu_luc_tu, tinh_trang, sac_thue, tvpl_url, link_tvpl,
                   noi_dung
            FROM documents
            WHERE is_anchor = TRUE
              AND tinh_trang != 'het_hieu_luc'
              AND sac_thue && ARRAY[{placeholders}]::varchar[]
            ORDER BY importance ASC, ngay_ban_hanh DESC
        """), params)
        rows = [dict(row) for row in r.mappings().all()]
        # Strip HTML + truncate
        for row in rows:
            raw = row.get("noi_dung") or ""
            row["noi_dung_text"] = strip_html_for_context(raw, max_chars=max_chars_per_doc)
            row["source"] = "anchor_doc"
        return rows
    except Exception as e:
        print(f"load_anchor_docs error: {e}")
        return []
```

### B4. Thêm `build_context_with_anchors()`

```python
def build_context_with_anchors(anchor_docs: list[dict], cv_list: list[dict],
                                 max_chars_cv: int = 1200) -> str:
    """
    Build context: anchor docs (full text) TRƯỚC, rồi CV liên quan SAU.
    Anchor docs là nền pháp lý → CV là hướng dẫn cụ thể.
    """
    import re as _re
    from bs4 import BeautifulSoup as _BS

    def strip(html, n):
        if not html: return ""
        t = _BS(html, "html.parser").get_text(" ") if "<" in str(html) else str(html)
        return _re.sub(r"\s+", " ", t).strip()[:n]

    parts = []

    if anchor_docs:
        parts.append("=== VĂN BẢN PHÁP LUẬT NỀN TẢNG (Hiện hành) ===")
        parts.append("Đây là các văn bản pháp luật hiện hành quan trọng nhất. "
                     "Ưu tiên trích dẫn từ các văn bản này.\n")
        for i, d in enumerate(anchor_docs, 1):
            hl = f" | Hiệu lực từ: {d.get('hieu_luc_tu')}" if d.get("hieu_luc_tu") else ""
            noi_dung = d.get("noi_dung_text") or strip(d.get("noi_dung", ""), 80_000)
            parts.append(
                f"[VB{i}] {d.get('loai', '')} {d.get('so_hieu', '')} "
                f"(ban hành: {d.get('ngay_ban_hanh', '')}{hl})\n"
                f"Tiêu đề: {d.get('ten', '')}\n"
                f"Tình trạng: {d.get('tinh_trang', '')}\n\n"
                f"{noi_dung}"
            )

    if cv_list:
        parts.append("\n\n=== CÔNG VĂN HƯỚNG DẪN LIÊN QUAN ===")
        for i, cv in enumerate(cv_list, 1):
            noi_dung_cv = strip(cv.get("noi_dung_day_du", ""), max_chars_cv)
            parts.append(
                f"[CV{i}] {cv.get('so_hieu', '')} "
                f"(ngày {cv.get('ngay_ban_hanh', '')}, score={float(cv.get('score', 0)):.3f})\n"
                f"Cơ quan: {cv.get('co_quan', '')}\n"
                f"Tiêu đề: {cv.get('ten', '')}\n"
                f"Nội dung: {noi_dung_cv}"
            )

    return "\n\n---\n\n".join(parts)
```

### B5. Nâng cấp `rag_answer()` — Haiku default + anchor docs

Thay toàn bộ `rag_answer()`:

```python
async def rag_answer(question: str, cv_list: list[dict],
                     docs: list[dict] = None,
                     anchor_docs: list[dict] = None) -> dict:
    """
    RAG v5 — Haiku default (200K context) + anchor docs + hybrid CV.

    Priority:
    - anchor_docs: VB pháp luật hiện hành (full text, luôn load nếu có)
    - cv_list: CV hướng dẫn liên quan (hybrid search)
    - docs: VB từ vector search (dự phòng nếu không có anchor)
    """
    docs = docs or []
    anchor_docs = anchor_docs or []
    is_timeline = detect_timeline_query(question)

    if not cv_list and not docs and not anchor_docs:
        return {
            "answer": "Không tìm thấy văn bản hoặc công văn liên quan trong cơ sở dữ liệu.",
            "model_used": None, "sources": [], "is_timeline": False,
        }

    # Build context
    if anchor_docs:
        # Có anchor → dùng context anchor + CV
        context = build_context_with_anchors(anchor_docs, cv_list)
        system = SYSTEM_PROMPT_TIMELINE if is_timeline else SYSTEM_PROMPT
    elif is_timeline:
        context = build_context_timeline(docs, cv_list)
        system = SYSTEM_PROMPT_TIMELINE
    else:
        context = build_context_multisource(docs, cv_list)
        system = SYSTEM_PROMPT

    user_msg = (
        f"CÁC TÀI LIỆU THAM KHẢO:\n{context}\n\n---\n\n"
        f"CÂU HỎI: {question}\n\n"
        + ("Trả lời theo từng giai đoạn (cũ → mới), nêu rõ sự thay đổi. Kết thúc bằng tóm tắt."
           if is_timeline else
           "Hãy trả lời dựa vào các tài liệu trên. Ưu tiên trích dẫn số hiệu văn bản pháp luật cụ thể.")
    )

    answer = None
    model_used = None

    # Tier 1: Claudible Haiku (DEFAULT — free, 200K context)
    if CLAUDIBLE_KEY:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{CLAUDIBLE_BASE}/messages",
                    headers={"Authorization": f"Bearer {CLAUDIBLE_KEY}",
                             "Content-Type": "application/json"},
                    json={"model": CLAUDIBLE_MODEL, "max_tokens": 4096,
                          "system": system,
                          "messages": [{"role": "user", "content": user_msg}]}
                )
                r.raise_for_status()
                answer = r.json()["content"][0]["text"]
                model_used = f"claudible/{CLAUDIBLE_MODEL}"
        except Exception as e:
            print(f"Claudible Haiku error: {e}")

    # Tier 2: Gemini 2.0 Flash (1M context, good Vietnamese)
    if answer is None and GEMINI_KEY:
        try:
            answer = await ask_gemini(question, context, system)
            model_used = f"google/{GEMINI_MODEL}"
        except Exception as e:
            print(f"Gemini error: {e}")

    # Tier 3: OpenAI GPT-4o (128K context — trim nếu cần)
    if answer is None and OPENAI_KEY:
        try:
            # GPT-4o chỉ 128K → trim context nếu quá dài
            trimmed_msg = user_msg[:300_000]  # ~75K tokens, safe cho 128K window
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_KEY}",
                             "Content-Type": "application/json"},
                    json={"model": "gpt-4o", "max_tokens": 4096,
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": trimmed_msg}]}
                )
                r.raise_for_status()
                answer = r.json()["choices"][0]["message"]["content"]
                model_used = "openai/gpt-4o"
        except Exception as e:
            print(f"OpenAI error: {e}")

    # Tier 4: Anthropic Haiku (direct — dùng khi Claudible down)
    if answer is None and ANTHROPIC_KEY:
        try:
            import anthropic as ant
            client = ant.AsyncAnthropic(api_key=ANTHROPIC_KEY)
            msg = await client.messages.create(
                model=ANTHROPIC_MODEL, max_tokens=4096, system=system,
                messages=[{"role": "user", "content": user_msg}]
            )
            answer = msg.content[0].text
            model_used = f"anthropic/{ANTHROPIC_MODEL}"
        except Exception as e:
            print(f"Anthropic error: {e}")
            answer = "Lỗi hệ thống: không thể kết nối AI."
            model_used = "error"

    # Build sources
    sources = []
    for d in (anchor_docs + docs):
        sources.append({
            "source_type": "document",
            "is_anchor": d.get("source") == "anchor_doc",
            "so_hieu": d.get("so_hieu"), "ten": d.get("ten"),
            "loai": d.get("loai"), "ngay_ban_hanh": str(d.get("ngay_ban_hanh") or ""),
            "hieu_luc_tu": str(d.get("hieu_luc_tu") or ""),
            "het_hieu_luc_tu": str(d.get("het_hieu_luc_tu") or ""),
            "tinh_trang": d.get("tinh_trang"),
            "link_nguon": d.get("tvpl_url") or d.get("link_tvpl"),
            "score": round(float(d.get("score") or 1.0), 3),
        })
    for cv in cv_list:
        sources.append({
            "source_type": "cong_van",
            "is_anchor": False,
            "so_hieu": cv.get("so_hieu"), "ten": cv.get("ten"),
            "loai": "CV", "ngay_ban_hanh": str(cv.get("ngay_ban_hanh") or ""),
            "hieu_luc_tu": "", "het_hieu_luc_tu": "",
            "tinh_trang": cv.get("tinh_trang") or "",
            "link_nguon": cv.get("link_nguon"),
            "score": round(float(cv.get("score") or 0), 3),
        })

    return {"answer": answer, "model_used": model_used,
            "sources": sources, "is_timeline": is_timeline}
```

---

## PHẦN C — `search.py`

### C1. Thêm `search_hybrid_cv()`

Thay thế `search_multi_query_cv()` bằng hàm này (đổi tên, giữ multi_query cũ để không break gì):

```python
async def search_hybrid_cv(db: AsyncSession, queries: list[str],
                            sac_thue: str = None, top_k: int = 15) -> list[dict]:
    """
    Hybrid search: BM25 full-text + vector semantic, merge score.
    BM25 chính xác với thuật ngữ pháp lý (không nhầm 'trích trước' vs 'trước bạ').
    Vector tốt với câu hỏi ngữ nghĩa.

    Formula: hybrid_score = 0.5 * vector_score + 0.5 * bm25_score (normalized)
    """
    import asyncio as _asyncio

    async def _vector_search(q: str) -> list[dict]:
        """Vector search với sac_thue filter."""
        filters = {"sac_thue": sac_thue} if sac_thue else {}
        rows, _ = await search_semantic_cv(db, q, filters, limit=top_k * 2, offset=0)
        return rows

    async def _bm25_search(q: str) -> list[dict]:
        """PostgreSQL full-text search (BM25-like ts_rank)."""
        try:
            # Build sac_thue filter
            st_clause = ""
            params: dict = {"q": q, "limit": top_k * 2}
            if sac_thue:
                st_clause = "AND :sac_thue = ANY(sac_thue)"
                params["sac_thue"] = sac_thue

            r = await db.execute(text(f"""
                SELECT id, so_hieu, ten, co_quan, ngay_ban_hanh,
                       sac_thue, noi_dung_day_du, link_nguon, tinh_trang,
                       ts_rank(
                           to_tsvector('simple',
                               COALESCE(ten,'') || ' ' || COALESCE(noi_dung_day_du,'')),
                           plainto_tsquery('simple', :q)
                       ) as bm25_score
                FROM cong_van
                WHERE to_tsvector('simple',
                          COALESCE(ten,'') || ' ' || COALESCE(noi_dung_day_du,''))
                      @@ plainto_tsquery('simple', :q)
                {st_clause}
                ORDER BY bm25_score DESC
                LIMIT :limit
            """), params)
            rows = [dict(row) for row in r.mappings().all()]
            # Normalize BM25 score sang [0,1]
            if rows:
                max_score = max(float(r.get("bm25_score", 0)) for r in rows) or 1
                for row in rows:
                    row["score"] = float(row.get("bm25_score", 0)) / max_score
            return rows
        except Exception as e:
            print(f"BM25 search error: {e}")
            return []

    # Search song song tất cả queries với cả 2 phương pháp
    tasks = []
    for q in queries:
        tasks.append(_vector_search(q))
        tasks.append(_bm25_search(q))
    all_results = await _asyncio.gather(*tasks)

    # Merge: tính hybrid score cho mỗi id
    seen: dict[int, dict] = {}
    for results in all_results:
        for row in results:
            rid = row.get("id")
            if not rid:
                continue
            if rid not in seen:
                seen[rid] = dict(row)
                seen[rid]["vector_score"] = 0.0
                seen[rid]["bm25_raw"] = 0.0
            # Track max scores
            cur_score = float(row.get("score", 0))
            if "bm25_score" in row:
                seen[rid]["bm25_raw"] = max(seen[rid]["bm25_raw"], cur_score)
            else:
                seen[rid]["vector_score"] = max(seen[rid]["vector_score"], cur_score)

    # Compute hybrid score
    for item in seen.values():
        item["score"] = 0.5 * item["vector_score"] + 0.5 * item["bm25_raw"]

    merged = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return merged[:top_k]
```

---

## PHẦN D — `main.py`

### D1. Update imports

```python
from search import (
    do_search, get_doc_by_id, get_cv_by_id, get_article_by_id,
    list_cong_van, search_semantic_cv,
    search_semantic_docs_for_rag,
    search_multi_query_docs,
    search_hybrid_cv,        # MỚI — thay search_multi_query_cv
)
from rag import rag_answer, analyze_intent, load_anchor_docs  # thêm load_anchor_docs
```

### D2. Cập nhật `ask()` endpoint

Thay thế toàn bộ hàm `ask()`:

```python
@app.post("/api/ask")
async def ask(req: AskRequest, db: AsyncSession = Depends(get_db)):
    """RAG v5: Haiku default + anchor docs + hybrid search."""
    if not req.question or len(req.question.strip()) < 5:
        raise HTTPException(400, "Câu hỏi quá ngắn")

    # Step 1: Analyze intent
    if req.use_intent:
        intent = await analyze_intent(req.question)
    else:
        intent = {
            "sac_thue": [], "chu_de": req.question,
            "search_queries": [req.question], "is_timeline": False,
        }

    queries    = intent.get("search_queries", [req.question])
    sac_thue   = intent.get("sac_thue", [])
    filter_st  = sac_thue[0] if sac_thue else None

    # Step 2: Load anchor docs + hybrid CV search song song
    is_timeline = intent.get("is_timeline", False)

    anchor_docs, cv_results = await asyncio.gather(
        # Không load anchor khi timeline query (tránh lẫn lộn thời kỳ)
        load_anchor_docs(db, sac_thue) if (sac_thue and not is_timeline) else asyncio.coroutine(lambda: [])(),
        search_hybrid_cv(db, queries, sac_thue=filter_st, top_k=req.top_k)
    )

    # Step 3: Nếu không có anchor → fallback vector search docs
    docs = []
    if not anchor_docs:
        docs = await search_multi_query_docs(db, queries, top_k=req.docs_top_k)

    # Step 4: RAG answer
    answer_data = await rag_answer(
        req.question, cv_results, docs=docs, anchor_docs=anchor_docs
    )

    return {
        "question":       req.question,
        "answer":         answer_data["answer"],
        "model_used":     answer_data["model_used"],
        "is_timeline":    answer_data["is_timeline"],
        "intent":         intent,
        "sources_count":  len(answer_data["sources"]),
        "anchor_count":   len(anchor_docs),
        "docs_count":     len(docs),
        "cv_count":       len(cv_results),
        "sources":        answer_data["sources"],
    }
```

**Lưu ý:** `asyncio.coroutine` đã deprecated trong Python 3.11+. Thay bằng helper:
```python
async def _empty_list():
    return []

# Trong ask():
anchor_docs, cv_results = await asyncio.gather(
    load_anchor_docs(db, sac_thue) if (sac_thue and not is_timeline) else _empty_list(),
    search_hybrid_cv(db, queries, sac_thue=filter_st, top_k=req.top_k)
)
```

### D3. Update `AskRequest`

```python
class AskRequest(BaseModel):
    question: str
    top_k: int = 15
    docs_top_k: int = 5
    use_intent: bool = True
```

---

## PHẦN E — Frontend `AdminPage.tsx`

### E1. Thêm Anchor checkbox vào Edit Modal của Documents tab

Trong form Edit văn bản, thêm field:

```typescript
// Trong DocumentEdit interface
is_anchor: boolean;

// Trong form (sau field importance)
<div className="flex items-center gap-2 mt-2">
  <input
    type="checkbox"
    id="is_anchor"
    checked={editForm.is_anchor || false}
    onChange={e => setEditForm({...editForm, is_anchor: e.target.checked})}
    className="w-4 h-4 text-primary"
  />
  <label htmlFor="is_anchor" className="text-sm font-medium">
    ⭐ Anchor — VB nền tảng (RAG luôn load full text)
  </label>
</div>
```

### E2. Hiển thị badge Anchor trong Documents table

Trong cột `so_hieu` hoặc `ten`, nếu `is_anchor=true` → thêm badge nhỏ:

```typescript
{doc.is_anchor && (
  <span className="ml-1 px-1 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded">
    ⭐ Anchor
  </span>
)}
```

### E3. Update `PUT /api/admin/documents/{doc_id}` để nhận `is_anchor`

`DocumentUpdate` model trong `main.py` đã có `importance` — thêm `is_anchor`:

```python
class DocumentUpdate(BaseModel):
    # ... các fields hiện có ...
    is_anchor: Optional[bool] = None
```

---

## PHẦN F — `AskAIPage.tsx`

### F1. Update response types

```typescript
interface AskResponse {
  question: string;
  answer: string;
  model_used: string;
  is_timeline: boolean;
  intent: AskIntent | null;
  sources_count: number;
  anchor_count: number;   // MỚI
  docs_count: number;
  cv_count: number;
  sources: AskSource[];
}

interface AskSource {
  source_type: 'document' | 'cong_van';
  is_anchor: boolean;     // MỚI
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
```

### F2. Hiển thị Anchor sources nổi bật hơn

Anchor docs → hiển thị với badge ⭐ và border vàng nhạt:

```typescript
{source.is_anchor && (
  <span className="text-xs bg-yellow-100 text-yellow-700 px-1 rounded">⭐ Anchor</span>
)}
```

Stats bar: thêm `⭐ {anchor_count} VB anchor` nếu > 0.

---

## Checklist cho Claude Code

### Database
- [ ] Thêm migration `ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_anchor BOOLEAN DEFAULT FALSE`
- [ ] Thêm index `idx_documents_anchor`

### `rag.py`
- [ ] Update config models (Claudible Haiku default, thêm INTENT_MODEL consts)
- [ ] Thêm `strip_html_for_context()`
- [ ] Thêm `load_anchor_docs()`
- [ ] Thêm `build_context_with_anchors()`
- [ ] Replace `rag_answer()` — Haiku tier 1, Gemini tier 2, GPT-4o tier 3, Anthropic tier 4
- [ ] `max_tokens` tăng lên 4096 (Haiku 200K context cho phép output dài hơn)

### `search.py`
- [ ] Thêm `search_hybrid_cv()` — hybrid BM25 + vector
- [ ] GIỮ NGUYÊN `search_multi_query_cv()` và các functions cũ (không xóa)

### `main.py`
- [ ] Update imports (thêm `search_hybrid_cv`, `load_anchor_docs`)
- [ ] Thêm helper `async def _empty_list(): return []` (trước hàm `ask`)
- [ ] Thêm `is_anchor` vào `DocumentUpdate` model
- [ ] Replace `ask()` endpoint
- [ ] Thêm `is_anchor` vào `PUT /api/admin/documents/{doc_id}` handler

### `AskAIPage.tsx`
- [ ] Update `AskResponse` + `AskSource` types (thêm `is_anchor`, `anchor_count`)
- [ ] Anchor badge ⭐ trong sources list
- [ ] Stats bar: thêm anchor count

### `AdminPage.tsx`
- [ ] Thêm `is_anchor` vào `DocumentEdit` interface + form checkbox
- [ ] Anchor badge ⭐ trong Documents table

### Build & Deploy
- [ ] `cd frontend && npm run build`
- [ ] `cp -r frontend/dist/* static/`
- [ ] Xóa file BRIEF này
- [ ] `git add -A && git commit -m "feat: RAG v5 — anchor docs + hybrid search + Haiku default" && git push`

---

## Ghi chú kỹ thuật

- `plainto_tsquery('simple', q)` phù hợp hơn `to_tsquery` vì không cần escape ký tự đặc biệt
- Index `idx_cv_fts` đã có trong DB (từ migration trước) → BM25 search sẽ nhanh
- `sac_thue && ARRAY[...]::varchar[]` dùng GIN operator `&&` (overlap) — cần index GIN trên `sac_thue`, kiểm tra xem đã có chưa
- Haiku 200K context: `noi_dung_text` sau strip HTML thường 50-200KB → fit tốt cho 2-3 anchor docs
- GPT-4o 128K context: trim `user_msg[:300_000]` chars ≈ ~75K tokens — safe
- `is_anchor` ban đầu tất cả = FALSE → anh tự tag qua Admin UI sau khi deploy
