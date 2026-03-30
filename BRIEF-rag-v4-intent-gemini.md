# BRIEF: dbvntax RAG v4 — Intent Classification + Multi-query + Gemini
_Tạo: 2026-03-30_

## Mục tiêu
Giải quyết vấn đề search không chính xác bằng cách:
1. **Intent Classification**: LLM phân tích câu hỏi → hiểu loại thuế, chủ đề, sinh ra nhiều search queries
2. **Multi-query Search**: search song song 2-3 queries → merge + dedup → kết quả liên quan hơn
3. **Gemini 2.0 Flash**: thêm vào fallback chain, env var `GEMINI_API_KEY`

---

## PHẦN A — `rag.py`

### A1. Thêm Gemini config (đầu file, sau các config hiện có)

```python
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"   # fast + cheap + good Vietnamese
```

### A2. Thêm `analyze_intent()`

Thêm function này vào `rag.py` (trước `rag_answer`):

```python
async def analyze_intent(question: str) -> dict:
    """
    Dùng LLM phân tích câu hỏi → intent, sac_thue, search queries.
    Ưu tiên: OpenAI gpt-4o-mini (nhanh, rẻ) → Gemini Flash → fallback basic
    
    Returns:
    {
      "sac_thue": ["TNDN"],
      "chu_de": "chi phí được trừ",
      "search_queries": [
        "chi phí quản lý trả công ty mẹ thuế TNDN được trừ",
        "chi phí phân bổ từ công ty nước ngoài khấu trừ",
        "điều kiện chi phí được trừ giao dịch liên kết TNDN"
      ],
      "is_timeline": false
    }
    """
    INTENT_PROMPT = """Bạn là chuyên gia phân tích câu hỏi pháp luật thuế Việt Nam.

Phân tích câu hỏi sau và trả về JSON:

Câu hỏi: "{question}"

Trả về JSON object với các fields:
- "sac_thue": array các loại thuế liên quan (chọn từ: TNDN, GTGT, TNCN, TTDB, FCT, GDLK, QLT, HOA_DON, HKD, XNK, MON_BAI_PHI, TAI_NGUYEN_DAT). Để [] nếu không xác định.
- "chu_de": string mô tả chủ đề chính của câu hỏi (tiếng Việt, ngắn gọn)
- "search_queries": array 2-3 cách diễn đạt khác nhau, dùng thuật ngữ pháp lý VN chính xác để tìm kiếm văn bản/công văn liên quan. Mỗi query 8-15 từ.
- "is_timeline": boolean, true nếu câu hỏi liên quan đến nhiều giai đoạn thời gian khác nhau

Ví dụ:
Câu hỏi: "chi phí trả cho công ty mẹ có được khấu trừ thuế TNDN không?"
→ {{"sac_thue": ["TNDN"], "chu_de": "chi phí được trừ - giao dịch liên kết", "search_queries": ["chi phí quản lý phân bổ từ công ty mẹ thuế TNDN được trừ", "chi phí giao dịch liên kết điều kiện được trừ TNDN", "khoản chi phí trả cho bên liên kết nước ngoài hợp lý"], "is_timeline": false}}

Chỉ trả về JSON object, không giải thích."""

    prompt = INTENT_PROMPT.format(question=question)
    result = None

    # Primary: OpenAI gpt-4o-mini (fast + cheap)
    if OPENAI_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-4o-mini",
                        "max_tokens": 400,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "user", "content": prompt}]
                    }
                )
                r.raise_for_status()
                result = json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:
            print(f"Intent OpenAI error: {e}")

    # Fallback: Gemini Flash
    if result is None and GEMINI_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "maxOutputTokens": 400,
                            "responseMimeType": "application/json"
                        }
                    }
                )
                r.raise_for_status()
                text_out = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                result = json.loads(text_out)
        except Exception as e:
            print(f"Intent Gemini error: {e}")

    # Fallback: basic (dùng câu hỏi gốc)
    if result is None:
        return {
            "sac_thue": [],
            "chu_de": question[:100],
            "search_queries": [question],
            "is_timeline": detect_timeline_query(question)
        }

    # Validate + ensure search_queries có ít nhất câu hỏi gốc
    queries = result.get("search_queries", [])
    if question not in queries:
        queries.append(question)
    result["search_queries"] = queries[:3]  # max 3
    result.setdefault("sac_thue", [])
    result.setdefault("is_timeline", detect_timeline_query(question))
    return result
```

### A3. Thêm `ask_gemini()`

Thêm sau `ask_anthropic()`:

```python
async def ask_gemini(question: str, context: str, system: str) -> str:
    """Call Gemini 2.0 Flash."""
    combined = f"{system}\n\n{context}\n\n---\n\nCÂU HỎI: {question}\n\nHãy trả lời dựa vào các tài liệu trên."
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}",
            json={
                "contents": [{"parts": [{"text": combined}]}],
                "generationConfig": {"maxOutputTokens": 2000}
            }
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
```

### A4. Nâng cấp `rag_answer()` — thêm intent + multi-query

Thay thế toàn bộ `rag_answer()` hiện tại:

```python
async def rag_answer(question: str, cv_list: list[dict], docs: list[dict] = None) -> dict:
    """
    RAG v4 — intent classification + multi-query + Gemini support.
    
    Flow:
    1. analyze_intent() → sac_thue, search_queries, is_timeline
    2. Multi-query search đã được thực hiện ở main.py (cv_list + docs đã được merge)
    3. Build context theo loại query
    4. Gọi LLM với fallback chain: GPT-4o → Gemini 2.0 Flash → Anthropic → Claudible
    """
    docs = docs or []

    if not cv_list and not docs:
        return {
            "answer": "Không tìm thấy văn bản hoặc công văn liên quan trong cơ sở dữ liệu.",
            "model_used": None, "sources": [], "is_timeline": False,
            "intent": None,
        }

    # Detect timeline (đã có trong intent nhưng cần cho context building)
    is_timeline = detect_timeline_query(question)

    # Build context
    if is_timeline:
        context = build_context_timeline(docs, cv_list)
        system = SYSTEM_PROMPT_TIMELINE
        user_instruction = (
            "Trả lời theo từng giai đoạn (cũ → mới), nêu rõ sự thay đổi. "
            "Kết thúc bằng tóm tắt ngắn."
        )
    else:
        context = build_context_multisource(docs, cv_list)
        system = SYSTEM_PROMPT
        user_instruction = "Hãy trả lời dựa vào các tài liệu trên."

    user_msg = (
        f"CÁC TÀI LIỆU THAM KHẢO:\n{context}\n\n---\n\n"
        f"CÂU HỎI: {question}\n\n{user_instruction}"
    )

    answer = None
    model_used = None

    # Tier 1: GPT-4o (best reasoning)
    if OPENAI_KEY:
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-4o",
                        "max_tokens": 2000,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user_msg}
                        ]
                    }
                )
                r.raise_for_status()
                answer = r.json()["choices"][0]["message"]["content"]
                model_used = "openai/gpt-4o"
        except Exception as e:
            print(f"GPT-4o error: {e}")

    # Tier 2: Gemini 2.0 Flash
    if answer is None and GEMINI_KEY:
        try:
            answer = await ask_gemini(question, context, system)
            model_used = f"google/{GEMINI_MODEL}"
        except Exception as e:
            print(f"Gemini error: {e}")

    # Tier 3: Anthropic Claude Haiku
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

    # Tier 4: Claudible (free fallback)
    if answer is None and CLAUDIBLE_KEY:
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post(
                    f"{CLAUDIBLE_BASE}/messages",
                    headers={"Authorization": f"Bearer {CLAUDIBLE_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": CLAUDIBLE_MODEL, "max_tokens": 2000, "system": system,
                        "messages": [{"role": "user", "content": user_msg}]
                    }
                )
                r.raise_for_status()
                answer = r.json()["content"][0]["text"]
                model_used = f"claudible/{CLAUDIBLE_MODEL}"
        except Exception as e:
            print(f"Claudible error: {e}")
            answer = "Lỗi hệ thống: không thể kết nối AI."
            model_used = "error"

    # Build sources
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

    return {
        "answer": answer,
        "model_used": model_used,
        "sources": sources,
        "is_timeline": is_timeline,
    }
```

---

## PHẦN B — `search.py`

### B1. Thêm `search_multi_query_cv()` và `search_multi_query_docs()`

Thêm 2 functions mới (KHÔNG sửa function hiện có):

```python
async def search_multi_query_cv(db: AsyncSession, queries: list[str], sac_thue: str = None,
                                 top_k: int = 15) -> list[dict]:
    """
    Multi-query semantic search trên cong_van.
    Search song song với nhiều queries, merge + dedup theo id, re-rank theo max score.
    """
    import asyncio as _asyncio

    async def _search_one(q: str) -> list[dict]:
        filters = {"sac_thue": sac_thue} if sac_thue else {}
        rows, _ = await search_semantic_cv(db, q, filters, limit=top_k, offset=0)
        return rows

    # Search song song tất cả queries
    all_results_lists = await _asyncio.gather(*[_search_one(q) for q in queries])

    # Merge + dedup: giữ score cao nhất cho mỗi id
    seen = {}
    for results in all_results_lists:
        for row in results:
            rid = row.get("id")
            if rid not in seen or float(row.get("score", 0)) > float(seen[rid].get("score", 0)):
                seen[rid] = row

    # Sort by score desc, lấy top_k
    merged = sorted(seen.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
    return merged[:top_k]


async def search_multi_query_docs(db: AsyncSession, queries: list[str], top_k: int = 5) -> list[dict]:
    """
    Multi-query semantic search trên documents.
    Search song song, merge + dedup, re-rank.
    """
    import asyncio as _asyncio

    all_results_lists = await _asyncio.gather(
        *[search_semantic_docs_for_rag(db, q, top_k=top_k) for q in queries]
    )

    seen = {}
    for results in all_results_lists:
        for row in results:
            rid = row.get("id")
            if rid not in seen or float(row.get("score", 0)) > float(seen[rid].get("score", 0)):
                seen[rid] = row

    merged = sorted(seen.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
    return merged[:top_k]
```

---

## PHẦN C — `main.py`

### C1. Thêm import

```python
from search import (
    do_search, get_doc_by_id, get_cv_by_id, get_article_by_id,
    list_cong_van, search_semantic_cv,
    search_semantic_docs_for_rag,
    search_multi_query_cv,       # MỚI
    search_multi_query_docs,     # MỚI
)
from rag import rag_answer, analyze_intent  # thêm analyze_intent
```

### C2. Cập nhật `AskRequest`

```python
class AskRequest(BaseModel):
    question: str
    top_k: int = 15
    docs_top_k: int = 5
    use_intent: bool = True   # MỚI: bật/tắt intent classification
```

### C3. Thay thế toàn bộ hàm `ask()`

```python
@app.post("/api/ask")
async def ask(req: AskRequest, db: AsyncSession = Depends(get_db)):
    """RAG v4: intent classification + multi-query search + Gemini support."""
    if not req.question or len(req.question.strip()) < 5:
        raise HTTPException(400, "Câu hỏi quá ngắn")

    # Step 1: Analyze intent (nếu bật)
    if req.use_intent:
        intent = await analyze_intent(req.question)
    else:
        intent = {
            "sac_thue": [],
            "chu_de": req.question,
            "search_queries": [req.question],
            "is_timeline": False,
        }

    queries = intent.get("search_queries", [req.question])
    sac_thue = intent.get("sac_thue", [])
    # Dùng sac_thue đầu tiên để filter (nếu có)
    filter_sac_thue = sac_thue[0] if sac_thue else None

    # Step 2: Multi-query search song song
    docs, cv_results = await asyncio.gather(
        search_multi_query_docs(db, queries, top_k=req.docs_top_k),
        search_multi_query_cv(db, queries, sac_thue=filter_sac_thue, top_k=req.top_k)
    )

    # Step 3: RAG answer
    answer_data = await rag_answer(req.question, cv_results, docs=docs)

    return {
        "question":      req.question,
        "answer":        answer_data["answer"],
        "model_used":    answer_data["model_used"],
        "is_timeline":   answer_data["is_timeline"],
        "intent":        intent,          # trả về để frontend hiển thị debug info
        "sources_count": len(answer_data["sources"]),
        "docs_count":    len(docs),
        "cv_count":      len(cv_results),
        "sources":       answer_data["sources"],
    }
```

---

## PHẦN D — Frontend `AskAIPage.tsx`

### D1. Hiển thị intent info (debug / UX)

Sau khi có kết quả, hiển thị nhỏ bên dưới câu hỏi:

```
🎯 Chủ đề: Chi phí được trừ - giao dịch liên kết  •  Loại thuế: TNDN
```

Chỉ hiển thị nếu `intent` có trong response và `intent.chu_de` không rỗng. Style nhỏ, màu xám nhạt.

### D2. Cập nhật type `AskResponse`

```typescript
interface AskIntent {
  sac_thue: string[];
  chu_de: string;
  search_queries: string[];
  is_timeline: boolean;
}

interface AskResponse {
  question: string;
  answer: string;
  model_used: string;
  is_timeline: boolean;
  intent: AskIntent | null;
  sources_count: number;
  docs_count: number;
  cv_count: number;
  sources: AskSource[];
}
```

---

## PHẦN E — Coolify Environment Variables

Thêm `GEMINI_API_KEY` vào Coolify env vars cho app `dbvntax` (UUID: `h2hondf1axrj2fyx8jheyknl`).

**Không hardcode** — chỉ đọc từ `os.getenv("GEMINI_API_KEY", "")` như các key khác.

Anh cần thêm thủ công trong Coolify dashboard:
- Key: `GEMINI_API_KEY`
- Value: (anh tự nhập API key từ Google AI Studio)

---

## Checklist cho Claude Code

### `rag.py`
- [ ] Thêm `GEMINI_KEY` + `GEMINI_MODEL` config đầu file
- [ ] Thêm `analyze_intent()`
- [ ] Thêm `ask_gemini()`
- [ ] Replace `rag_answer()` — đổi Tier 1 từ `gpt-4o-mini` → `gpt-4o`, thêm Tier 2 Gemini

### `search.py`
- [ ] Thêm `search_multi_query_cv()`
- [ ] Thêm `search_multi_query_docs()`

### `main.py`
- [ ] Update imports (thêm `analyze_intent`, `search_multi_query_cv`, `search_multi_query_docs`)
- [ ] Thêm `use_intent: bool = True` vào `AskRequest`
- [ ] Replace `ask()` endpoint

### `AskAIPage.tsx`
- [ ] Update `AskResponse` type (thêm `intent`)
- [ ] Hiển thị intent chip: `🎯 {chu_de}  •  Loại thuế: {sac_thue.join(', ')}`

### Build & Deploy
- [ ] `cd frontend && npm run build`
- [ ] `cp -r frontend/dist/* static/`
- [ ] Xóa file BRIEF này
- [ ] `git add -A && git commit -m "feat: RAG v4 — intent classification + multi-query + Gemini" && git push`

---

## Ghi chú kỹ thuật

- `analyze_intent` dùng `gpt-4o-mini` (không phải `gpt-4o`) — nhanh, rẻ, đủ cho task phân loại
- `response_format: {"type": "json_object"}` yêu cầu prompt phải mention "JSON" — đã có trong prompt
- Gemini API endpoint: `generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- `responseMimeType: "application/json"` cho Gemini intent call đảm bảo parse được
- Multi-query search dùng `asyncio.gather` — latency tăng không đáng kể vì chạy song song
- Filter `sac_thue` chỉ apply cho CV search (không apply cho documents — documents ít, lấy hết top_k)
- Nếu intent fail → fallback về câu hỏi gốc, không crash
