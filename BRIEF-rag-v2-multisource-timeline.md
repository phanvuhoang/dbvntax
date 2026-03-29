# BRIEF: dbvntax RAG v2 — Multi-source + Timeline-aware

## Mục tiêu
Nâng cấp tính năng "Hỏi đáp AI" để:
1. Search cả `documents` (Luật/NĐ/TT) lẫn `cong_van` — documents ưu tiên cao hơn
2. Tự phát hiện câu hỏi liên quan nhiều giai đoạn thời gian → tổ chức câu trả lời và sources theo timeline

---

## Thay đổi cần làm

### 1. `search.py` — thêm `search_semantic_docs_for_rag()`

Thêm function mới (KHÔNG sửa các function hiện có):

```python
async def search_semantic_docs_for_rag(db: AsyncSession, q: str, top_k: int = 5) -> list[dict]:
    """
    Semantic search trên documents table cho RAG.
    Trả về list dict gồm: id, so_hieu, ten, loai, ngay_ban_hanh, hieu_luc_tu,
    het_hieu_luc_tu, tinh_trang, sac_thue, noi_dung (stripped, max 2000 chars), score, source='document'
    Không có threshold filter — lấy top_k tốt nhất.
    """
    emb = await embed_text(q)
    if not emb:
        return []
    try:
        r = await db.execute(text("""
            SELECT id, so_hieu, ten, loai, ngay_ban_hanh, hieu_luc_tu, het_hieu_luc_tu,
                   tinh_trang, sac_thue, 
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

### 2. `rag.py` — toàn bộ thay đổi

#### 2a. Thêm imports ở đầu file
```python
import unicodedata
from datetime import date
```

#### 2b. Thêm SYSTEM_PROMPT_TIMELINE (bên cạnh SYSTEM_PROMPT hiện có)
```python
SYSTEM_PROMPT_TIMELINE = """Bạn là chuyên gia tư vấn thuế Việt Nam với kinh nghiệm 30 năm.

Trả lời câu hỏi dựa HOÀN TOÀN vào các văn bản và công văn được cung cấp.

Quy tắc:
- Chỉ dùng thông tin từ tài liệu được cung cấp, KHÔNG suy đoán
- Trích dẫn số hiệu văn bản/công văn cụ thể
- Khi có nhiều giai đoạn: trình bày TUẦN TỰ từ cũ đến mới, nêu rõ sự thay đổi
- Phân biệt rõ: 📜 Văn bản pháp luật (Luật/NĐ/TT) và 📨 Công văn hướng dẫn
- Nếu tài liệu không đủ → nói rõ "Chưa đủ thông tin trong cơ sở dữ liệu để trả lời"
- Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc"""
```

#### 2c. Thêm `detect_timeline_query()`
```python
def detect_timeline_query(question: str) -> bool:
    """Phát hiện câu hỏi liên quan nhiều giai đoạn thời gian."""
    q = question.lower()
    # Normalize unicode
    q = unicodedata.normalize("NFC", q)
    
    timeline_patterns = [
        r"\b(từ năm|từ \d{4}|trước năm|sau năm|đến năm|giai đoạn|thời kỳ|thời điểm)",
        r"\b(trước khi|sau khi|kể từ|hiện nay|hiện tại so với|thay đổi|thay thế)",
        r"\b(lịch sử|quá trình|quy định cũ|quy định mới|trước đây|trước đó)",
        r"\b(năm 20\d\d.*năm 20\d\d|20\d\d.*đến.*20\d\d)",
        r"\b(các thời kỳ|qua các năm|từng giai đoạn|theo từng năm)",
        r"(sửa đổi|bổ sung|thay thế|hiệu lực từ)",
    ]
    import re as _re
    for pattern in timeline_patterns:
        if _re.search(pattern, q):
            return True
    return False
```

#### 2d. Thêm `group_by_period()`
```python
def group_by_period(items: list[dict]) -> dict:
    """
    Nhóm documents + CV theo giai đoạn dựa trên ngày hiệu lực.
    
    Input: list of dicts, mỗi item có:
      - source: 'document' hoặc 'cong_van'
      - ngay_ban_hanh: date hoặc str 'YYYY-MM-DD' hoặc None
      - hieu_luc_tu: date hoặc str hoặc None (chỉ documents)
      - het_hieu_luc_tu: date hoặc None (chỉ documents)
    
    Output: dict { "label": [items] } ordered từ cũ đến mới
    """
    import re as _re
    from datetime import date as _date, datetime as _dt
    
    def parse_date(val):
        if val is None:
            return None
        if isinstance(val, _date):
            return val
        if isinstance(val, str):
            m = _re.match(r'(\d{4})-(\d{2})-(\d{2})', val)
            if m:
                try:
                    return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except:
                    return None
        return None
    
    def get_effective_date(item):
        """Lấy ngày bắt đầu hiệu lực (ưu tiên hieu_luc_tu, fallback ngay_ban_hanh)."""
        d = parse_date(item.get("hieu_luc_tu")) or parse_date(item.get("ngay_ban_hanh"))
        return d
    
    def get_expiry_date(item):
        return parse_date(item.get("het_hieu_luc_tu"))
    
    # Sort tất cả items theo ngày hiệu lực (cũ → mới), None xuống cuối
    sorted_items = sorted(items, key=lambda x: get_effective_date(x) or _date(9999, 1, 1))
    
    # Tìm các mốc thời gian quan trọng từ documents (văn bản pháp luật)
    breakpoints = set()
    for item in sorted_items:
        if item.get("source") == "document":
            d = get_effective_date(item)
            if d:
                breakpoints.add(d.year)
            exp = get_expiry_date(item)
            if exp:
                breakpoints.add(exp.year + 1)
    
    # Nếu không có breakpoints rõ ràng (chỉ CV) → group theo năm
    if not breakpoints or len(breakpoints) <= 1:
        groups = {}
        for item in sorted_items:
            d = get_effective_date(item)
            label = str(d.year) if d else "Không rõ ngày"
            groups.setdefault(label, []).append(item)
        return groups
    
    # Tạo periods từ breakpoints
    years = sorted(breakpoints)
    periods = []
    for i, y in enumerate(years):
        if i == 0:
            label = f"Trước {y}" if sorted_items and get_effective_date(sorted_items[0]) and get_effective_date(sorted_items[0]).year < y else f"Từ {y}"
        elif i == len(years) - 1:
            label = f"Từ {y} đến nay"
        else:
            label = f"{y}–{years[i+1]-1}"
        periods.append((y, label))
    
    groups = {}
    today_year = _date.today().year
    
    for item in sorted_items:
        d = get_effective_date(item)
        item_year = d.year if d else None
        
        assigned = False
        for i, (y, label) in enumerate(periods):
            next_y = periods[i+1][0] if i+1 < len(periods) else today_year + 1
            if item_year is None:
                bucket = "Không rõ ngày"
                assigned = True
            elif item_year < periods[0][0]:
                bucket = f"Trước {periods[0][0]}"
                assigned = True
            elif y <= item_year < next_y:
                bucket = label
                assigned = True
            if assigned:
                groups.setdefault(bucket if assigned and item_year else "Không rõ ngày", []).append(item)
                break
        if not assigned:
            # Thuộc period cuối
            groups.setdefault(periods[-1][1], []).append(item)
    
    return groups
```

#### 2e. Thêm `build_context_multisource()` — thay thế `build_context()` khi có documents
```python
def build_context_multisource(
    docs: list[dict],
    cvs: list[dict],
    max_chars_doc: int = 2000,
    max_chars_cv: int = 1200,
) -> str:
    """
    Build context kết hợp documents + CV.
    Documents đứng trước (nguồn gốc pháp lý), CV đứng sau (hướng dẫn cụ thể).
    """
    from bs4 import BeautifulSoup
    import re as _re

    def strip_html(html_or_text: str, max_chars: int) -> str:
        if not html_or_text:
            return ""
        if "<" in html_or_text:
            text = BeautifulSoup(html_or_text, "html.parser").get_text(separator=" ")
        else:
            text = html_or_text
        text = _re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]

    parts = []

    # ── Phần 1: Văn bản pháp luật ──────────────────────────────
    if docs:
        parts.append("=== VĂN BẢN PHÁP LUẬT (Nguồn gốc pháp lý) ===\n")
        for i, doc in enumerate(docs, 1):
            so_hieu  = doc.get("so_hieu") or ""
            ten      = doc.get("ten") or ""
            loai     = doc.get("loai") or ""
            ngay     = str(doc.get("ngay_ban_hanh") or "")
            hl_tu    = str(doc.get("hieu_luc_tu") or "")
            hl_den   = str(doc.get("het_hieu_luc_tu") or "")
            tinh_trang = doc.get("tinh_trang") or ""
            score    = doc.get("score") or 0
            noi_dung = strip_html(doc.get("noi_dung") or doc.get("tom_tat") or "", max_chars_doc)
            
            hl_info = f"Hiệu lực: {hl_tu}" + (f" → {hl_den}" if hl_den else " đến nay") if hl_tu else ""
            
            block = f"""[VB{i}] {loai} {so_hieu} (ban hành: {ngay}, score={score:.3f})
Tiêu đề: {ten}
{hl_info}
Tình trạng: {tinh_trang}
Nội dung: {noi_dung}"""
            parts.append(block)

    # ── Phần 2: Công văn hướng dẫn ─────────────────────────────
    if cvs:
        parts.append("\n=== CÔNG VĂN HƯỚNG DẪN ===\n")
        for i, cv in enumerate(cvs, 1):
            so_hieu  = cv.get("so_hieu") or ""
            ten      = cv.get("ten") or ""
            ngay     = str(cv.get("ngay_ban_hanh") or "")
            co_quan  = cv.get("co_quan") or ""
            score    = cv.get("score") or 0
            noi_dung = strip_html(cv.get("noi_dung_day_du") or "", max_chars_cv)
            
            block = f"""[CV{i}] {so_hieu} (ngày {ngay}, score={score:.3f})
Cơ quan: {co_quan}
Tiêu đề: {ten}
Nội dung: {noi_dung}"""
            parts.append(block)

    return "\n\n---\n\n".join(parts)
```

#### 2f. Thêm `build_context_timeline()` — cho câu hỏi đa giai đoạn
```python
def build_context_timeline(
    docs: list[dict],
    cvs: list[dict],
    max_chars_doc: int = 1500,
    max_chars_cv: int = 1000,
) -> str:
    """
    Build context có cấu trúc GIAI ĐOẠN cho timeline queries.
    Gộp documents + CV, group theo period, sắp từ cũ đến mới.
    """
    from bs4 import BeautifulSoup
    import re as _re

    def strip_html(html_or_text: str, max_chars: int) -> str:
        if not html_or_text:
            return ""
        if "<" in html_or_text:
            text = BeautifulSoup(html_or_text, "html.parser").get_text(separator=" ")
        else:
            text = html_or_text
        text = _re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]

    # Prep items
    all_items = []
    for doc in docs:
        doc["source"] = "document"
        doc["_content"] = strip_html(doc.get("noi_dung") or doc.get("tom_tat") or "", max_chars_doc)
        all_items.append(doc)
    for cv in cvs:
        cv["source"] = "cong_van"
        cv["_content"] = strip_html(cv.get("noi_dung_day_du") or "", max_chars_cv)
        all_items.append(cv)

    periods = group_by_period(all_items)

    parts = []
    for period_label, items in periods.items():
        parts.append(f"=== GIAI ĐOẠN: {period_label} ===\n")
        for item in items:
            if item["source"] == "document":
                tag = "VB"
                icon = "📜"
                so_hieu = item.get("so_hieu") or ""
                loai = item.get("loai") or ""
                ngay = str(item.get("ngay_ban_hanh") or "")
                hl_tu = str(item.get("hieu_luc_tu") or "")
                score = item.get("score") or 0
                content = item.get("_content", "")
                hl_info = f" | Hiệu lực từ: {hl_tu}" if hl_tu else ""
                parts.append(f"""{icon} [{tag}] {loai} {so_hieu} (ban hành: {ngay}{hl_info}, score={score:.3f})
Tiêu đề: {item.get("ten","")}
Nội dung: {content}""")
            else:
                so_hieu = item.get("so_hieu") or ""
                ngay = str(item.get("ngay_ban_hanh") or "")
                score = item.get("score") or 0
                content = item.get("_content", "")
                parts.append(f"""📨 [CV] {so_hieu} (ngày {ngay}, score={score:.3f})
Cơ quan: {item.get("co_quan","")}
Tiêu đề: {item.get("ten","")}
Nội dung: {content}""")
        parts.append("")  # blank line between periods

    return "\n\n".join(parts)
```

#### 2g. Nâng cấp `rag_answer()` — nhận thêm `docs` param, auto-detect timeline

Thay thế toàn bộ function `rag_answer()` hiện tại bằng:

```python
async def rag_answer(question: str, cv_list: list[dict], docs: list[dict] = None) -> dict:
    """
    Main RAG function — v2: multi-source + timeline-aware.
    
    Args:
        question: câu hỏi người dùng
        cv_list: list công văn từ semantic search
        docs: list văn bản pháp luật (documents table), optional
    
    Returns: { answer, model_used, sources, is_timeline }
    """
    docs = docs or []
    
    if not cv_list and not docs:
        return {
            "answer": "Không tìm thấy văn bản hoặc công văn liên quan đến câu hỏi này trong cơ sở dữ liệu.",
            "model_used": None,
            "sources": [],
            "is_timeline": False,
        }

    # Auto-detect timeline query
    is_timeline = detect_timeline_query(question)
    
    # Build context theo loại query
    if is_timeline and (docs or cv_list):
        context = build_context_timeline(docs, cv_list)
        system_prompt = SYSTEM_PROMPT_TIMELINE
        user_instruction = """Hãy trả lời theo từng giai đoạn thời gian (từ cũ đến mới).
Với mỗi giai đoạn, nêu rõ:
- Quy định/hướng dẫn áp dụng là gì (trích dẫn số hiệu)
- Điểm khác biệt so với giai đoạn trước (nếu có)

Kết thúc bằng tóm tắt: "Tóm lại, sự thay đổi qua các giai đoạn là..."."""
    else:
        context = build_context_multisource(docs, cv_list)
        system_prompt = SYSTEM_PROMPT
        user_instruction = "Hãy trả lời dựa vào các văn bản và công văn trên."

    user_content = f"""CÁC TÀI LIỆU THAM KHẢO:
{context}

---

CÂU HỎI: {question}

{user_instruction}"""

    answer = None
    model_used = None

    # Primary: OpenAI gpt-4o-mini
    if OPENAI_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json",
            }
            body = {
                "model": OPENAI_MODEL,
                "max_tokens": 2000,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            }
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
                r.raise_for_status()
                answer = r.json()["choices"][0]["message"]["content"]
                model_used = f"openai/{OPENAI_MODEL}"
        except Exception as e:
            print(f"OpenAI error: {e}, falling back to Anthropic...")

    # Fallback 1: Anthropic Claude Haiku
    if answer is None and ANTHROPIC_KEY:
        try:
            import anthropic as ant
            client = ant.AsyncAnthropic(api_key=ANTHROPIC_KEY)
            msg = await client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}]
            )
            answer = msg.content[0].text
            model_used = f"anthropic/{ANTHROPIC_MODEL}"
        except Exception as e:
            print(f"Anthropic error: {e}, trying Claudible...")

    # Fallback 2: Claudible
    if answer is None and CLAUDIBLE_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {CLAUDIBLE_KEY}",
                "Content-Type": "application/json",
            }
            body = {
                "model": CLAUDIBLE_MODEL,
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_content}],
            }
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post(f"{CLAUDIBLE_BASE}/messages", headers=headers, json=body)
                r.raise_for_status()
                answer = r.json()["content"][0]["text"]
                model_used = f"claudible/{CLAUDIBLE_MODEL}"
        except Exception as e:
            print(f"Claudible error: {e}")
            answer = "Lỗi hệ thống: không thể kết nối AI. Vui lòng thử lại sau."
            model_used = "error"

    # Build sources: documents trước, CV sau
    sources = []
    for doc in docs:
        sources.append({
            "source_type": "document",
            "so_hieu": doc.get("so_hieu"),
            "ten": doc.get("ten"),
            "loai": doc.get("loai"),
            "ngay_ban_hanh": str(doc.get("ngay_ban_hanh") or ""),
            "hieu_luc_tu": str(doc.get("hieu_luc_tu") or ""),
            "het_hieu_luc_tu": str(doc.get("het_hieu_luc_tu") or ""),
            "tinh_trang": doc.get("tinh_trang"),
            "link_nguon": doc.get("tvpl_url") or doc.get("link_tvpl"),
            "score": round(float(doc.get("score") or 0), 3),
        })
    for cv in cv_list:
        sources.append({
            "source_type": "cong_van",
            "so_hieu": cv.get("so_hieu"),
            "ten": cv.get("ten"),
            "loai": "CV",
            "ngay_ban_hanh": str(cv.get("ngay_ban_hanh") or ""),
            "hieu_luc_tu": "",
            "het_hieu_luc_tu": "",
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

**Lưu ý:** Các function cũ `ask_claudible()`, `ask_openai()`, `ask_anthropic()`, `build_context()` vẫn giữ nguyên (không xóa) để không break gì. Chỉ `rag_answer()` được replace.

---

### 3. `main.py` — nâng cấp `/api/ask` endpoint

#### 3a. Thêm import ở đầu (trong block import rag)
```python
from rag import rag_answer
from search import search_semantic_docs_for_rag  # thêm dòng này
```

#### 3b. Thêm `docs_top_k` vào `AskRequest`

Tìm class `AskRequest` và thêm field:
```python
class AskRequest(BaseModel):
    question: str
    top_k: int = 15       # số CV đưa vào LLM
    docs_top_k: int = 5   # số văn bản pháp luật đưa vào LLM (MỚI)
```

#### 3c. Thay thế toàn bộ hàm `ask()`:
```python
@app.post("/api/ask")
async def ask(req: AskRequest, db: AsyncSession = Depends(get_db)):
    """RAG v2: tìm văn bản pháp luật + công văn liên quan → AI trả lời câu hỏi thuế."""
    if not req.question or len(req.question.strip()) < 5:
        raise HTTPException(400, "Câu hỏi quá ngắn")

    # Search song song: documents + cong_van
    docs_task = search_semantic_docs_for_rag(db, req.question, top_k=req.docs_top_k)
    cv_task   = search_semantic_cv(db, req.question, {}, limit=req.top_k, offset=0)
    docs, (cv_results, cv_total) = await asyncio.gather(docs_task, cv_task)

    # RAG
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

**Lưu ý:** Cần `import asyncio` ở đầu main.py (kiểm tra xem đã có chưa, nếu chưa thì thêm).

---

### 4. `frontend/src/pages/AskAIPage.tsx` — nâng cấp UI

#### 4a. Cập nhật TypeScript types (thêm vào đầu file hoặc vào `api.ts`):
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

#### 4b. Sources section — thay thế phần render sources hiện tại

Render sources theo 2 nhóm: **Văn bản pháp luật** trước, **Công văn** sau. Mỗi source card:

**Văn bản pháp luật (source_type === 'document'):**
- Icon: 📜
- Badge màu xanh dương: loại văn bản (Luật/NĐ/TT/VBHN)
- `so_hieu` + `ten` (truncate 80 chars)
- Dòng nhỏ: `Hiệu lực: {hieu_luc_tu}` nếu có, `{tinh_trang}` badge (xanh = còn hiệu lực, đỏ = hết hiệu lực)
- Score badge nhỏ góc phải
- Click → mở `link_nguon` nếu có

**Công văn (source_type === 'cong_van'):**
- Icon: 📨
- Badge màu xám: "Công văn"
- `so_hieu` + `ten` (truncate 80 chars)
- Dòng nhỏ: ngày ban hành
- Score badge nhỏ góc phải
- Click → mở `link_nguon` nếu có

#### 4c. Timeline indicator

Nếu `is_timeline === true`, hiển thị badge/chip ở đầu phần sources:
```
⏱️ Câu hỏi liên quan nhiều giai đoạn — nguồn được sắp xếp theo thời gian
```

#### 4d. Stats bar nhỏ (dưới câu trả lời, trên sources)
```
📜 {docs_count} văn bản  •  📨 {cv_count} công văn  •  🤖 {model_used}
```

---

## Checklist cho Claude Code

- [ ] `search.py`: thêm `search_semantic_docs_for_rag()`
- [ ] `rag.py`: thêm imports `unicodedata`, `date`
- [ ] `rag.py`: thêm `SYSTEM_PROMPT_TIMELINE`
- [ ] `rag.py`: thêm `detect_timeline_query()`
- [ ] `rag.py`: thêm `group_by_period()`
- [ ] `rag.py`: thêm `build_context_multisource()`
- [ ] `rag.py`: thêm `build_context_timeline()`
- [ ] `rag.py`: replace `rag_answer()` với version mới (giữ các function cũ)
- [ ] `main.py`: thêm import `search_semantic_docs_for_rag`
- [ ] `main.py`: thêm `docs_top_k` vào `AskRequest`
- [ ] `main.py`: replace `ask()` endpoint
- [ ] `main.py`: verify `import asyncio` có ở đầu file
- [ ] `AskAIPage.tsx`: update types
- [ ] `AskAIPage.tsx`: render sources 2 nhóm (VB + CV)
- [ ] `AskAIPage.tsx`: timeline badge
- [ ] `AskAIPage.tsx`: stats bar
- [ ] Build frontend: `cd frontend && npm run build`
- [ ] Copy dist: `cp -r frontend/dist/* static/`
- [ ] Xóa file BRIEF này
- [ ] `git add -A && git commit -m "feat: RAG v2 — multi-source documents+CV + timeline-aware" && git push`

---

## Ghi chú kỹ thuật

- `documents.embedding` và `cong_van.embedding` cùng dim **vector(1536)** — dùng cùng embed model (OpenAI text-embedding-3-small)
- `search_semantic_docs_for_rag` dùng `top_k` trực tiếp, không threshold — vì documents ít (186), cần lấy đủ
- `group_by_period` dùng `hieu_luc_tu` của documents làm breakpoints chính
- Timeline detection dùng regex đơn giản, không cần ML
- `max_tokens` nâng lên 2000 (từ 1500) để đủ chỗ cho timeline answer
- Search song song bằng `asyncio.gather` — không tăng latency
