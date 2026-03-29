"""
RAG (Retrieval-Augmented Generation) module for dbvntax.
Primary: Claudible (Claude Haiku — free)
Fallback: OpenAI gpt-4o-mini
"""

import os
import re
import json
import asyncio
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

async def rag_answer(question: str, cv_list: list[dict]) -> dict:
    """
    Main RAG function.
    Returns: { answer, model_used, sources }
    Priority: OpenAI gpt-4o-mini → Anthropic Claude Haiku → Claudible (fallback)
    """
    if not cv_list:
        return {
            "answer": "Không tìm thấy công văn liên quan đến câu hỏi này trong cơ sở dữ liệu.",
            "model_used": None,
            "sources": [],
        }

    context = build_context(cv_list, max_chars_per_cv=1500)
    answer = None
    model_used = None

    # Primary: OpenAI gpt-4o-mini
    if OPENAI_KEY:
        try:
            answer = await ask_openai(question, context)
            model_used = f"openai/{OPENAI_MODEL}"
        except Exception as e:
            print(f"OpenAI error: {e}, falling back to Anthropic...")

    # Fallback 1: Anthropic Claude Haiku direct
    if answer is None and ANTHROPIC_KEY:
        try:
            answer = await ask_anthropic(question, context)
            model_used = f"anthropic/{ANTHROPIC_MODEL}"
        except Exception as e:
            print(f"Anthropic error: {e}, trying Claudible...")

    # Fallback 2: Claudible
    if answer is None and CLAUDIBLE_KEY:
        try:
            answer = await ask_claudible(question, context)
            model_used = f"claudible/{CLAUDIBLE_MODEL}"
        except Exception as e:
            print(f"Claudible error: {e}")
            answer = "Lỗi hệ thống: không thể kết nối AI. Vui lòng thử lại sau."
            model_used = "error"

    # Build sources list
    sources = [
        {
            "so_hieu": cv.get("so_hieu"),
            "ten": cv.get("ten"),
            "ngay_ban_hanh": str(cv.get("ngay_ban_hanh") or ""),
            "link_nguon": cv.get("link_nguon"),
            "score": round(float(cv.get("score") or 0), 3),
        }
        for cv in cv_list
    ]

    return {"answer": answer, "model_used": model_used, "sources": sources}
