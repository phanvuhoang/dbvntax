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
from typing import Optional

# Claudible — OpenAI-completions format
# POST /v1/chat/completions với Bearer token
# Env vars: ANTHROPIC_BASE_URL (e.g. https://claudible.io) + ANTHROPIC_AUTH_TOKEN
_raw_base = os.getenv("ANTHROPIC_BASE_URL", "https://claudible.io")
CLAUDIBLE_BASE_URL   = _raw_base.rstrip("/").removesuffix("/v1")  # normalize, strip /v1 nếu ai lỡ thêm
CLAUDIBLE_AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN", "")

# Model names theo Claudible (dấu chấm, không phải gạch ngang)
CLAUDIBLE_HAIKU  = os.getenv("ANTHROPIC_DEFAULT_HAIKU_MODEL",  "claude-haiku-4.5")
CLAUDIBLE_SONNET = os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4.6")
CLAUDIBLE_OPUS   = os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL",   "claude-opus-4.6")

GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"  # v1 deprecated, dùng v1beta

OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")   # fallback 3 (intent only + last resort)
DEEPSEEK_KEY  = os.getenv("DEEPSEEK_API_KEY", "")  # DeepSeek Reasoner (V3.2 thinking mode)

ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY", "")  # fallback nếu Claudible down

# Intent analysis model (lightweight, fast)
INTENT_MODEL_OPENAI  = "gpt-4o-mini"
INTENT_MODEL_GEMINI  = "gemini-2.0-flash"

SYSTEM_PROMPT = """Bạn là chuyên gia tư vấn thuế Việt Nam. Trả lời câu hỏi dựa HOÀN TOÀN vào các tài liệu được cung cấp.

Quy tắc bắt buộc:
1. Chỉ dùng thông tin từ tài liệu được cung cấp, KHÔNG suy đoán hay dùng kiến thức ngoài
2. Trả lời đầy đủ, KHÔNG cắt giữa chừng
3. Trả lời bằng tiếng Việt, rõ ràng, có cấu trúc
4. ĐỌC VÀ TRÍCH DẪN TỪ TẤT CẢ văn bản được cung cấp — KHÔNG được chỉ tập trung vào 1 văn bản và bỏ qua phần còn lại
5. Luật quy định nguyên tắc, Nghị định quy định chi tiết, Thông tư hướng dẫn — mỗi loại có vai trò riêng, phải tổng hợp đầy đủ

Định dạng trả lời:
**[Kết luận ngắn gọn 1-2 câu]**

**Căn cứ pháp lý:**
- Trích dẫn TRỰC TIẾP điều/khoản liên quan từ văn bản pháp luật, ví dụ:
  > Theo **khoản X Điều Y NĐ 320/2025/NĐ-CP**: "nội dung nguyên văn..."
  > Theo **Điều Z TT 20/2026/TT-BTC**: "nội dung nguyên văn..."
- Nếu có công văn hướng dẫn liên quan: nêu số hiệu + nội dung chính

**Giải thích & áp dụng thực tế:**
[Giải thích ngắn gọn cách áp dụng vào tình huống cụ thể]

Lưu ý: Nếu tài liệu không đủ → nói rõ "Trong tài liệu hiện có chưa đề cập đến vấn đề này"."""

SYSTEM_PROMPT_TIMELINE = """Bạn là chuyên gia tư vấn thuế Việt Nam với 30 năm kinh nghiệm.
Trả lời câu hỏi dựa HOÀN TOÀN vào các văn bản và công văn được cung cấp.

Quy tắc bắt buộc:
1. Chỉ dùng thông tin từ tài liệu được cung cấp, KHÔNG suy đoán
2. Trả lời đầy đủ, KHÔNG cắt giữa chừng
3. Khi có nhiều giai đoạn: trình bày TUẦN TỰ từ cũ đến mới, nêu rõ sự thay đổi
4. Phân biệt rõ: 📜 Văn bản pháp luật (Luật/NĐ/TT) và 📨 Công văn hướng dẫn

Định dạng trả lời:
**Giai đoạn [thời kỳ]:** Căn cứ [số hiệu VB]
> Trích dẫn nguyên văn điều/khoản liên quan

**Giai đoạn [thời kỳ sau]:** Căn cứ [số hiệu VB mới]
> Trích dẫn nguyên văn điều/khoản liên quan

**Tóm tắt thay đổi:** [so sánh điểm khác nhau chính]

Nếu tài liệu không đủ → nói rõ "Chưa đủ thông tin trong cơ sở dữ liệu"."""


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


def extract_relevant_articles(text: str, question: str,
                               max_chars: int = 20_000,
                               context_lines: int = 8,
                               sac_thue_list: list = None) -> str:
    """
    Từ full text của văn bản, extract chỉ các Điều/Khoản liên quan đến câu hỏi.

    Strategy:
    1. Split text thành các block theo "Điều X"
    2. Score mỗi block theo keyword overlap với câu hỏi + sac_thue domains
    3. Luôn giữ: Điều 1 (phạm vi), Điều 2 (đối tượng) + top scored blocks
    4. Return concatenated, capped at max_chars
    """
    import re as _re

    if not text or len(text) < 500:
        return text[:max_chars] if text else ""

    # Normalize question → keywords
    q = unicodedata.normalize("NFC", question.lower())
    # Remove stopwords VN
    stopwords = {"và", "của", "có", "là", "được", "không", "trong", "cho", "với",
                 "các", "một", "này", "đó", "từ", "đến", "về", "theo", "thì",
                 "hay", "hoặc", "như", "khi", "nếu", "vì", "do", "bởi", "mà"}
    q_words = [w for w in _re.findall(r'[a-záàảãạăắằẳẵặâấầẩẫậđéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ\w]+', q)
               if len(w) > 2 and w not in stopwords]

    # Tax-domain keyword expansions — triggered by câu hỏi OR sac_thue_list
    SAC_THUE_KEYWORDS = {
        "TNDN":     ["thu nhập doanh nghiệp", "thuế tndn", "chi phí được trừ", "thu nhập chịu thuế",
                     "thuế suất tndn", "lợi nhuận", "doanh thu tính thuế"],
        "GTGT":     ["giá trị gia tăng", "thuế gtgt", "vat", "khấu trừ đầu vào", "thuế đầu ra",
                     "hàng hóa dịch vụ chịu thuế", "hoàn thuế gtgt"],
        "TNCN":     ["thu nhập cá nhân", "thuế tncn", "pit", "giảm trừ gia cảnh", "khấu trừ tại nguồn"],
        "FCT":      ["thuế nhà thầu", "nhà thầu nước ngoài", "foreign contractor", "withholding tax",
                     "tổ chức nước ngoài", "cá nhân nước ngoài", "dịch vụ nước ngoài"],
        "GDLK":     ["giao dịch liên kết", "transfer pricing", "chuyển giá", "arm's length",
                     "bên liên kết", "lãi vay liên kết", "ebitda", "30%", "vốn mỏng",
                     "nghị định 132", "nđ 132"],
        "TTDB":     ["tiêu thụ đặc biệt", "thuế ttdb", "excise tax", "rượu bia thuốc lá"],
        "HOA_DON":  ["hóa đơn điện tử", "hóa đơn hợp lệ", "hđkt", "chứng từ hợp lệ"],
        "HKD":      ["hộ kinh doanh", "hộ cá thể", "thuế khoán", "doanh thu hộ kinh doanh"],
        "XNK":      ["xuất nhập khẩu", "hải quan", "thuế nhập khẩu", "thuế xuất khẩu"],
        "QLT":      ["quản lý thuế", "kê khai thuế", "nộp thuế", "quyết toán thuế",
                     "ấn định thuế", "hoàn thuế", "miễn giảm thuế"],
        "MON_BAI_PHI": ["môn bài", "lệ phí môn bài", "phí"],
        "TAI_NGUYEN_DAT": ["tiền thuê đất", "sử dụng đất", "tài nguyên"],
    }

    # Build keyword set từ câu hỏi + sac_thue_list
    domain_keywords = list(q_words)
    active_domains = sac_thue_list or []
    for domain in active_domains:
        domain_keywords.extend(SAC_THUE_KEYWORDS.get(domain, []))

    # Thêm expansions từ câu hỏi (backward compat)
    QUESTION_EXPANSIONS = {
        "chi phí": ["chi phí được trừ", "khoản chi", "chi phí hợp lý", "điều kiện khấu trừ"],
        "lãi vay": ["lãi tiền vay", "chi phí lãi vay", "vốn mỏng", "ebitda", "30%"],
        "khấu hao": ["khấu hao tài sản", "tscđ", "tài sản cố định"],
        "công ty mẹ": ["bên liên kết", "giao dịch liên kết", "thuế nhà thầu"],
        "nước ngoài": ["nhà thầu nước ngoài", "tổ chức nước ngoài", "foreign"],
        "rủi ro":   ["vi phạm", "phạt", "truy thu", "không được trừ", "loại trừ"],
    }
    for kw, expansions in QUESTION_EXPANSIONS.items():
        if kw in q:
            domain_keywords.extend(expansions)

    # Deduplicate
    domain_keywords = list(dict.fromkeys(domain_keywords))

    # Split text into article blocks by "Điều X"
    article_pattern = _re.compile(r'(?=(?:Điều|ĐIỀU)\s+\d+[\.:]?\s)', _re.UNICODE)
    blocks = article_pattern.split(text)

    if len(blocks) <= 2:
        return text[:max_chars]

    # Score each block
    def score_block(block_text: str) -> float:
        bt = unicodedata.normalize("NFC", block_text.lower())
        score = 0.0
        for w in domain_keywords:
            count = bt.count(w)
            if count > 0:
                # Longer keywords = more specific = higher weight
                weight = 3.0 if len(w) > 10 else (2.0 if len(w) > 5 else 1.0)
                score += min(count, 3) * weight
        return score

    scored = []
    for i, block in enumerate(blocks):
        if not block.strip():
            continue
        m = _re.match(r'(?:Điều|ĐIỀU)\s+(\d+)', block.strip())
        art_num = int(m.group(1)) if m else 999
        s = score_block(block)
        # Điều 1-3 luôn hữu ích (scope/definitions)
        if art_num <= 3:
            s = max(s, 1.5)
        scored.append((s, art_num, i, block))

    # Sort: score DESC
    top = sorted(scored, key=lambda x: (-x[0], x[2]))

    # Build result
    selected_indices = set()
    result_parts = []
    total_chars = 0

    # Always include Điều 1-3
    for s, art_num, idx, block in scored:
        if art_num <= 3:
            selected_indices.add(idx)
            result_parts.append((idx, block))
            total_chars += len(block)

    # Top scored blocks
    for s, art_num, idx, block in top:
        if s <= 0:
            break
        if idx in selected_indices:
            continue
        if total_chars + len(block) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 500:
                result_parts.append((idx, block[:remaining] + "\n[... còn tiếp ...]"))
            break
        selected_indices.add(idx)
        result_parts.append((idx, block))
        total_chars += len(block)

    # Sort by original article order
    result_parts.sort(key=lambda x: x[0])
    result = "\n".join(p for _, p in result_parts)

    if len(result.strip()) < 200:
        return text[:max_chars]

    return result


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


async def load_anchor_docs(db, sac_thue_list: list[str],
                           max_chars_per_doc: int = 80_000,
                           question: str = "",
                           article_max_chars: int = 20_000) -> list[dict]:
    """
    Load anchor docs theo thứ tự ưu tiên sắc thuế.

    Strategy:
    - Sắc thuế đầu tiên trong list = sắc thuế CHÍNH → load tối đa 3 docs
    - Các sắc thuế phụ → mỗi sắc tối đa 1-2 docs
    - Sort cuối: sắc thuế chính trước, rồi importance ASC, ngay_ban_hanh DESC
    - Giới hạn tổng: 8 docs để không làm loãng context
    - extract_relevant_articles() → chỉ giữ Điều liên quan đến câu hỏi (~20k/doc)
    """
    from sqlalchemy import text as _text

    if not sac_thue_list:
        # Không detect được → load top anchor chung
        try:
            r = await db.execute(_text("""
                SELECT id, so_hieu, ten, loai, ngay_ban_hanh, hieu_luc_tu,
                       het_hieu_luc_tu, tinh_trang, sac_thue, tvpl_url, link_tvpl,
                       github_path, noi_dung
                FROM documents
                WHERE is_anchor = TRUE AND tinh_trang != 'het_hieu_luc'
                ORDER BY importance ASC, ngay_ban_hanh DESC
                LIMIT 5
            """))
            rows = [dict(row) for row in r.mappings().all()]
            for row in rows:
                full_text = strip_html_for_context(row.get("noi_dung") or "", max_chars=max_chars_per_doc)
                row["noi_dung_text"] = extract_relevant_articles(full_text, question, max_chars=article_max_chars) if question else full_text
                row["source"] = "anchor_doc"
            return rows
        except Exception as e:
            print(f"load_anchor_docs error: {e}")
            return []

    try:
        all_rows = []
        seen_ids = set()

        # Sắc thuế chính (index 0) → tối đa 3 docs
        # Sắc thuế phụ (index 1+) → tối đa 2 docs mỗi sắc
        limits = [3] + [2] * (len(sac_thue_list) - 1)

        for idx, st in enumerate(sac_thue_list):
            lim = limits[idx]
            r = await db.execute(_text("""
                SELECT id, so_hieu, ten, loai, ngay_ban_hanh, hieu_luc_tu,
                       het_hieu_luc_tu, tinh_trang, sac_thue, tvpl_url, link_tvpl,
                       github_path, noi_dung
                FROM documents
                WHERE is_anchor = TRUE
                  AND tinh_trang != 'het_hieu_luc'
                  AND sac_thue && ARRAY[:st]::varchar[]
                ORDER BY importance ASC, ngay_ban_hanh DESC
                LIMIT :lim
            """), {"st": st, "lim": lim})
            for row in r.mappings().all():
                d = dict(row)
                if d["id"] not in seen_ids:
                    seen_ids.add(d["id"])
                    d["_priority"] = idx  # 0 = sắc thuế chính
                    all_rows.append(d)

        # Sort: sắc thuế chính trước (priority 0), rồi importance, rồi ngay_ban_hanh
        all_rows.sort(key=lambda x: (x.get("_priority", 99), x.get("importance", 9), str(x.get("ngay_ban_hanh") or "")), reverse=False)

        # Strip HTML + extract relevant articles theo câu hỏi + sac_thue domains
        for row in all_rows:
            full_text = strip_html_for_context(row.get("noi_dung") or "", max_chars=max_chars_per_doc)
            if question:
                row["noi_dung_text"] = extract_relevant_articles(
                    full_text, question, max_chars=article_max_chars, sac_thue_list=sac_thue_list
                )
            else:
                row["noi_dung_text"] = full_text
            row["source"] = "anchor_doc"

        return all_rows[:8]  # tổng tối đa 8

    except Exception as e:
        print(f"load_anchor_docs error: {e}")
        return []
        print(f"load_anchor_docs error: {e}")
        return []


def build_context_with_anchors(anchor_docs: list[dict], cv_list: list[dict],
                                max_chars_cv: int = 1200) -> str:
    """
    Build context: anchor docs (full text) TRƯỚC, rồi CV liên quan SAU.
    """
    import re as _re
    from bs4 import BeautifulSoup as _BS

    def strip(html, n):
        if not html: return ""
        t = _BS(html, "html.parser").get_text(" ") if "<" in str(html) else str(html)
        return _re.sub(r"\s+", " ", t).strip()[:n]

    parts = []

    if anchor_docs:
        n = len(anchor_docs)
        parts.append(f"=== CÓ {n} VĂN BẢN PHÁP LUẬT — ĐỌC VÀ TRÍCH DẪN ĐẦY ĐỦ TẤT CẢ {n} VĂN BẢN ===")
        parts.append(
            f"⚠️ QUAN TRỌNG: Có {n} văn bản bên dưới. Bạn PHẢI đọc và trích dẫn từ TẤT CẢ {n} văn bản, "
            "không được bỏ qua bất kỳ văn bản nào. Mỗi văn bản có thể quy định các khía cạnh khác nhau "
            "của cùng một vấn đề (Luật quy định nguyên tắc, Nghị định quy định chi tiết, Thông tư hướng dẫn).\n"
        )
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


async def analyze_intent(question: str) -> dict:
    """
    Dùng LLM phân tích câu hỏi → intent, sac_thue, search queries.
    Ưu tiên: OpenAI gpt-4o-mini (nhanh, rẻ) → Gemini Flash → fallback basic
    """
    INTENT_PROMPT = """Bạn là chuyên gia phân tích câu hỏi pháp luật thuế Việt Nam.

Phân tích câu hỏi sau và trả về JSON:

Câu hỏi: "{question}"

Trả về JSON object với các fields:
- "sac_thue": array TẤT CẢ các loại thuế liên quan trực tiếp HOẶC gián tiếp (chọn từ: TNDN, GTGT, TNCN, TTDB, FCT, GDLK, QLT, HOA_DON, HKD, XNK, MON_BAI_PHI, TAI_NGUYEN_DAT).
  QUAN TRỌNG: Câu hỏi về "rủi ro", "giao dịch liên kết", "công ty mẹ", "nước ngoài" thường liên quan ĐỒNG THỜI nhiều sắc thuế. Liệt kê đầy đủ, KHÔNG bỏ sót.
- "chu_de": string mô tả chủ đề chính của câu hỏi (tiếng Việt, ngắn gọn)
- "search_queries": array 2-3 cách diễn đạt khác nhau, dùng thuật ngữ pháp lý VN chính xác để tìm kiếm văn bản/công văn liên quan. Mỗi query 8-15 từ.
- "is_timeline": boolean, true nếu câu hỏi liên quan đến nhiều giai đoạn thời gian khác nhau

Ví dụ:
Câu hỏi: "chi phí dịch vụ trả cho công ty mẹ nước ngoài có được khấu trừ thuế TNDN không? Có rủi ro gì khác không?"
→ {{"sac_thue": ["TNDN", "FCT", "GDLK"], "chu_de": "chi phí dịch vụ công ty mẹ - giao dịch liên kết - thuế nhà thầu", "search_queries": ["chi phí dịch vụ trả công ty mẹ nước ngoài điều kiện khấu trừ TNDN", "thuế nhà thầu FCT dịch vụ từ nước ngoài", "giao dịch liên kết chuyển giá điều kiện chi phí được trừ"], "is_timeline": false}}

Câu hỏi: "lãi vay trả công ty mẹ có bị giới hạn không?"
→ {{"sac_thue": ["TNDN", "FCT", "GDLK"], "chu_de": "lãi vay liên kết - giới hạn 30% EBITDA", "search_queries": ["lãi vay bên liên kết giới hạn khấu trừ 30% EBITDA NĐ 132", "thuế nhà thầu lãi vay trả nước ngoài", "giao dịch liên kết vốn mỏng thin capitalization"], "is_timeline": false}}

Chỉ trả về JSON object, không giải thích."""

    prompt = INTENT_PROMPT.format(question=question)
    result = None

    # Primary: Gemini Flash (fast + cheap + no OpenAI dependency)
    if GEMINI_KEY:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}",
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

    # Fallback: OpenAI gpt-4o-mini
    if result is None and OPENAI_KEY:
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


# ask_claudible() — hàm cũ, đã deprecated. Dùng _call_anthropic() trong rag_answer() thay thế.


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

async def ask_gemini(question: str, context: str, system: str) -> str:
    """Call Gemini 2.0 Flash."""
    combined = f"{system}\n\n{context}\n\n---\n\nCÂU HỎI: {question}\n\nHãy trả lời dựa vào các tài liệu trên."
    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(
            f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}",
            json={
                "contents": [{"parts": [{"text": combined}]}],
                "generationConfig": {"maxOutputTokens": 8192}
            }
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def rag_answer(question: str, cv_list: list[dict],
                     docs: list[dict] = None,
                     anchor_docs: list[dict] = None,
                     model: str = "anthropic/claude-haiku-4-5") -> dict:
    """
    RAG v5 — user-selectable model + anchor docs only (CV tạm bỏ).
    """
    docs = docs or []
    anchor_docs = anchor_docs or []
    is_timeline = detect_timeline_query(question)

    # Chỉ dùng anchor docs — bỏ CV khỏi context (chất lượng chưa đủ)
    if not anchor_docs and not docs:
        return {
            "answer": "Không tìm thấy văn bản pháp luật liên quan trong cơ sở dữ liệu. Vui lòng thử câu hỏi khác hoặc chỉ định rõ sắc thuế.",
            "model_used": None, "sources": [], "is_timeline": False,
        }

    # Build context — chỉ anchor docs + docs vector (không có CV)
    if anchor_docs:
        context = build_context_with_anchors(anchor_docs, [])   # cv_list=[]
        system = SYSTEM_PROMPT_TIMELINE if is_timeline else SYSTEM_PROMPT
    elif is_timeline:
        context = build_context_timeline(docs, [])
        system = SYSTEM_PROMPT_TIMELINE
    else:
        context = build_context_multisource(docs, [])
        system = SYSTEM_PROMPT

    user_msg = (
        f"CÁC TÀI LIỆU THAM KHẢO:\n{context}\n\n---\n\n"
        f"CÂU HỎI: {question}\n\n"
        + ("Trả lời theo từng giai đoạn (cũ → mới), nêu rõ sự thay đổi. Kết thúc bằng tóm tắt."
           if is_timeline else
           "Hãy trả lời dựa vào các tài liệu trên. Ưu tiên trích dẫn số hiệu văn bản pháp luật cụ thể. Trả lời đầy đủ, không cắt giữa chừng.")
    )

    answer = None
    model_used = None

    async def _call_anthropic(ant_model: str) -> Optional[str]:
        """Gọi qua Claudible — OpenAI-completions format. Dùng cho Haiku (fast, free)."""
        if not CLAUDIBLE_AUTH_TOKEN:
            return None
        _timeout = 180 if "sonnet" in ant_model or "opus" in ant_model else 120
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=_timeout) as client:
                    r = await client.post(
                        f"{CLAUDIBLE_BASE_URL}/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {CLAUDIBLE_AUTH_TOKEN}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": ant_model,
                            # Claudible Sonnet bị Cloudflare 524 nếu generate quá lâu (>100s)
                            # Haiku: 8192 OK, Sonnet: cap 4096 để fit trong 100s CF timeout
                            "max_tokens": 4096 if ("sonnet" in ant_model or "opus" in ant_model) else 8192,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user",   "content": user_msg},
                            ],
                        },
                    )
                    if r.status_code == 503 and attempt < max_retries:
                        wait = attempt * 3  # 3s, 6s
                        print(f"Claudible {ant_model} 503 (attempt {attempt}/{max_retries}), retry in {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    r.raise_for_status()
                    return r.json()["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 503 and attempt < max_retries:
                    wait = attempt * 3
                    print(f"Claudible {ant_model} 503 (attempt {attempt}/{max_retries}), retry in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                import traceback
                print(f"Claudible {ant_model} error: {type(e).__name__}: {e}")
                traceback.print_exc()
                return None
            except Exception as e:
                import traceback
                print(f"Claudible {ant_model} error: {type(e).__name__}: {e}")
                traceback.print_exc()
                return None
        return None

    async def _call_anthropic_direct(ant_model: str) -> Optional[str]:
        """Gọi Anthropic API trực tiếp (không qua Claudible). Dùng cho Sonnet/Opus."""
        if not ANTHROPIC_KEY:
            print("Anthropic direct: ANTHROPIC_API_KEY not set")
            return None
        try:
            async with httpx.AsyncClient(timeout=240) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_KEY,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": ant_model,
                        "max_tokens": 8192,
                        "system": system,
                        "messages": [{"role": "user", "content": user_msg}],
                    },
                )
                r.raise_for_status()
                return r.json()["content"][0]["text"]
        except Exception as e:
            import traceback
            print(f"Anthropic direct {ant_model} error: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None

    async def _call_openai(oai_model: str) -> Optional[str]:
        if not OPENAI_KEY:
            return None
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                    json={"model": oai_model, "max_tokens": 8192,
                          "messages": [{"role": "system", "content": system},
                                       {"role": "user", "content": user_msg[:300_000]}]}
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenAI {oai_model} error: {e}")
            return None

    async def _call_deepseek(ds_model: str) -> Optional[str]:
        """Gọi DeepSeek API — OpenAI-compatible format.
        deepseek-reasoner = DeepSeek-V3.2 thinking mode (có reasoning_content).
        """
        if not DEEPSEEK_KEY:
            print("DeepSeek: DEEPSEEK_API_KEY not set")
            return None
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": ds_model,
                        "max_tokens": 8000,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user",   "content": user_msg},
                        ],
                    },
                )
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            import traceback
            print(f"DeepSeek {ds_model} error: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None

    async def _call_gemini() -> Optional[str]:
        if not GEMINI_KEY:
            return None
        try:
            return await ask_gemini(question, context, system)
        except Exception as e:
            print(f"Gemini error: {e}")
            return None

    # ── Dispatch theo model đã chọn ─────────────────────────────────
    MODEL_MAP = {
        "claudible/claude-haiku-4.5":  lambda: _call_anthropic("claude-haiku-4.5"),         # Claudible Haiku (free, fast)
        "claudible/claude-sonnet-4.6": lambda: _call_anthropic("claude-sonnet-4.6"),         # Claudible Sonnet (free, slow)
        "anthropic/claude-sonnet-4-6": lambda: _call_anthropic_direct("claude-sonnet-4-6"), # Anthropic direct (paid)
        "openai/gpt-4o-mini":          lambda: _call_openai("gpt-4o-mini"),
        "openai/gpt-4o":               lambda: _call_openai("gpt-4o"),
        "google/gemini-2.0-flash":     _call_gemini,
        "deepseek/deepseek-reasoner":  lambda: _call_deepseek("deepseek-reasoner"),          # DeepSeek V3.2 thinking mode
    }
    DEFAULT_MODEL = "claudible/claude-haiku-4.5"

    selected = model if model in MODEL_MAP else DEFAULT_MODEL

    # Claudible Sonnet: NO fallback — fail fast, hiện lỗi rõ để debug
    no_fallback = {"claudible/claude-sonnet-4.6"}

    answer = await MODEL_MAP[selected]()
    model_used = selected

    # Fallback nếu model chính fail (skip no_fallback models)
    if answer is None and selected not in no_fallback:
        print(f"Primary model {selected} failed, trying fallbacks...")
        for fallback_key, fallback_fn in MODEL_MAP.items():
            if fallback_key == selected or fallback_key in no_fallback:
                continue
            answer = await fallback_fn()
            if answer:
                model_used = fallback_key
                break

    if answer is None:
        if selected in no_fallback:
            answer = f"⚠️ {selected} không phản hồi. Vui lòng thử lại hoặc chọn model khác."
        else:
            answer = "Lỗi hệ thống: không thể kết nối AI. Vui lòng thử lại."
        model_used = "error"

    # Build sources
    DBVNTAX_BASE = "https://dbvntax.gpt4vn.com"
    sources = []
    for d in (anchor_docs + docs):
        doc_id = d.get("id")
        link = (
            d.get("tvpl_url") or
            d.get("link_tvpl") or
            (f"{DBVNTAX_BASE}/?doc={doc_id}" if doc_id else None)
        )
        sources.append({
            "source_type": "document",
            "is_anchor": d.get("source") == "anchor_doc",
            "so_hieu": d.get("so_hieu"), "ten": d.get("ten"),
            "loai": d.get("loai"), "ngay_ban_hanh": str(d.get("ngay_ban_hanh") or ""),
            "hieu_luc_tu": str(d.get("hieu_luc_tu") or ""),
            "het_hieu_luc_tu": str(d.get("het_hieu_luc_tu") or ""),
            "tinh_trang": d.get("tinh_trang"),
            "link_nguon": link,
            "score": round(float(d.get("score") or 1.0), 3),
        })
    # CV tạm bỏ khỏi sources (chất lượng chưa đủ)

    return {"answer": answer, "model_used": model_used,
            "sources": sources, "is_timeline": is_timeline}
