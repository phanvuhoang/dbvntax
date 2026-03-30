"""
RAG (Retrieval-Augmented Generation) module for dbvntax.
Primary: Claudible (Claude Haiku — free)
Fallback: OpenAI gpt-4o-mini
"""

import os
import re
import json
import asyncio
import unicodedata
import httpx

CLAUDIBLE_BASE = os.getenv("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")
CLAUDIBLE_KEY  = os.getenv("CLAUDIBLE_API_KEY", "")
CLAUDIBLE_MODEL = "claude-haiku-4-5"  # cheapest, fastest

OPENAI_KEY     = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o-mini"

ANTHROPIC_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """Bạn là chuyên gia tư vấn thuế Việt Nam. Trả lời câu hỏi dựa HOÀN TOÀN vào các công văn được cung cấp.

Quy tắc:
- Chỉ dùng thông tin từ các công văn được cung cấp, KHÔNG suy đoán
- Trích dẫn số hiệu công văn cụ thể khi đưa ra nhận định
- Nếu công văn không đủ thông tin → nói rõ "Dựa vào các công văn được cung cấp, chưa có đủ thông tin để trả lời chính xác"
- Trả lời bằng tiếng Việt, ngắn gọn, rõ ràng
- Format: câu trả lời ngắn → giải thích chi tiết → list công văn liên quan nhất"""

SYSTEM_PROMPT_TIMELINE = """Bạn là chuyên gia tư vấn thuế Việt Nam với 30 năm kinh nghiệm.

Trả lời câu hỏi dựa HOÀN TOÀN vào các văn bản và công văn được cung cấp.

Quy tắc:
- Chỉ dùng thông tin từ tài liệu được cung cấp, KHÔNG suy đoán
- Trích dẫn số hiệu văn bản/công văn cụ thể
- Khi có nhiều giai đoạn: trình bày TUẦN TỰ từ cũ đến mới, nêu rõ sự thay đổi
- Phân biệt rõ: 📜 Văn bản pháp luật (Luật/NĐ/TT) và 📨 Công văn hướng dẫn
- Nếu tài liệu không đủ → nói rõ "Chưa đủ thông tin trong cơ sở dữ liệu"
- Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc"""


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


def build_context_multisource(docs: list, cvs: list,
                               max_chars_doc: int = 2000, max_chars_cv: int = 1200) -> str:
    """Build context combining documents (first) + CVs (second)."""
    from bs4 import BeautifulSoup as _BS
    import re as _re

    def strip(html, n):
        if not html: return ""
        text = _BS(html, "html.parser").get_text(" ") if "<" in str(html) else str(html)
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


def build_context_timeline(docs: list, cvs: list,
                            max_chars_doc: int = 1500, max_chars_cv: int = 1000) -> str:
    """Build context grouped by time period."""
    from bs4 import BeautifulSoup as _BS
    import re as _re

    def strip(html, n):
        if not html: return ""
        text = _BS(html, "html.parser").get_text(" ") if "<" in str(html) else str(html)
        return _re.sub(r"\s+", " ", text).strip()[:n]

    def get_year(item):
        val = item.get("hieu_luc_tu") or item.get("ngay_ban_hanh")
        if not val: return 9999
        try: return int(str(val)[:4])
        except: return 9999

    all_items = []
    for d in docs:
        d = dict(d); d["_type"] = "document"
        d["_content"] = strip(d.get("noi_dung") or d.get("tom_tat", ""), max_chars_doc)
        all_items.append(d)
    for cv in cvs:
        cv = dict(cv); cv["_type"] = "cong_van"
        cv["_content"] = strip(cv.get("noi_dung_day_du", ""), max_chars_cv)
        all_items.append(cv)
    all_items.sort(key=lambda x: get_year(x))

    doc_years = sorted(set(get_year(d) for d in all_items if d["_type"] == "document" and get_year(d) != 9999))
    if len(doc_years) < 2:
        return build_context_multisource(docs, cvs, max_chars_doc, max_chars_cv)

    periods: dict = {}
    for item in all_items:
        y = get_year(item)
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

def build_context(cv_list: list[dict], max_chars_per_cv: int = 1500) -> str:
    """Build context string từ list công văn."""
    parts = []
    for i, cv in enumerate(cv_list, 1):
        so_hieu = cv.get("so_hieu") or ""
        ten = cv.get("ten") or ""
        ngay = cv.get("ngay_ban_hanh") or ""
        score = cv.get("score") or 0
        noi_dung = cv.get("noi_dung_day_du") or ""

        # Strip HTML
        if noi_dung:
            from bs4 import BeautifulSoup
            text = BeautifulSoup(noi_dung, "html.parser").get_text(separator=" ")
            text = re.sub(r"\s+", " ", text).strip()
            noi_dung = text[:max_chars_per_cv]

        block = f"""[CV{i}] {so_hieu} (ngày {ngay}, score={score:.3f})
Tiêu đề: {ten}
Nội dung: {noi_dung}"""
        parts.append(block)

    return "\n\n---\n\n".join(parts)


async def ask_claudible(question: str, context: str) -> str:
    """Call Claudible API (Claude Haiku)."""
    headers = {
        "Authorization": f"Bearer {CLAUDIBLE_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": CLAUDIBLE_MODEL,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"""CÁC CÔNG VĂN THAM KHẢO:
{context}

---

CÂU HỎI: {question}

Hãy trả lời dựa vào các công văn trên.""",
            }
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{CLAUDIBLE_BASE}/messages", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
        return data["content"][0]["text"]


async def ask_openai(question: str, context: str) -> str:
    """Call OpenAI gpt-4o-mini as fallback."""
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENAI_MODEL,
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""CÁC CÔNG VĂN THAM KHẢO:
{context}

---

CÂU HỎI: {question}

Hãy trả lời dựa vào các công văn trên.""",
            },
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=body
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]



async def ask_anthropic(question: str, context: str) -> str:
    """Call Anthropic Claude Haiku directly as second fallback."""
    import anthropic as ant
    client = ant.AsyncAnthropic(api_key=ANTHROPIC_KEY)
    msg = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""CÁC CÔNG VĂN THAM KHẢO:\n{context}\n\n---\n\nCÂU HỎI: {question}\n\nHãy trả lời dựa vào các công văn trên."""
        }]
    )
    return msg.content[0].text

async def rag_answer(question: str, cv_list: list, docs: list = None) -> dict:
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

    # Build sources — documents first, CVs second
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
