# BRIEF: Admin Import UI — Corpus & TVPL

**Date:** 2026-03-25  
**Scope:** Backend (main.py) + Frontend (new AdminPage + routing)  
**Priority:** HIGH

---

## Background

dbvntax có 218 văn bản quan trọng, tất cả đều có `noi_dung` (crawled từ TVPL).
- **KHÔNG dùng sync tự động nữa** — quá nguy hiểm, sync 1000+ docs không cần thiết
- Thay bằng: Admin tự chọn import từng văn bản mới

---

## Tổng quan features

### Feature 1: Import từ vn-tax-corpus (chỉ docs mới)
- Gọi GitHub API để lấy danh sách files trong corpus được tạo/sửa **từ hôm nay trở đi** (so với ngày import gần nhất)
- Hiển thị danh sách để admin tick → bấm Import
- Chỉ insert vào DB, không update docs đã có

### Feature 2: Import từ TVPL link
- Admin paste URL TVPL → app fetch, parse, insert vào DB
- Tự động classify (sac_thue, loai, so_hieu, ngay_ban_hanh)

### Feature 3: Tắt sync cron
- Xóa `/api/admin/update-embeddings` TVPL batch sync endpoint nếu có
- Xóa hoặc disable `sync_corpus.py` auto-trigger

---

## Backend changes (`main.py`)

### 1. New endpoint: `GET /api/admin/corpus-new`

Lấy danh sách files mới trong vn-tax-corpus chưa có trong DB.

```python
@app.get("/api/admin/corpus-new")
async def corpus_new_docs(
    since: Optional[str] = None,  # ISO date, default = ngày import gần nhất từ DB
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Gọi GitHub API để lấy commits gần đây trên vn-tax-corpus.
    So sánh với github_path đã có trong DB.
    Trả list docs mới (chưa có trong DB).
    """
    import httpx
    
    # Lấy ngày import gần nhất từ DB
    if not since:
        r = await db.execute(text("SELECT MAX(import_date)::date FROM documents"))
        max_date = r.scalar()
        since = str(max_date) if max_date else "2026-03-25"
    
    # GitHub API: list commits since date
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    # Get changed files since date
    url = f"https://api.github.com/repos/phanvuhoang/vn-tax-corpus/commits?since={since}T00:00:00Z&per_page=100"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        commits = resp.json()
    
    # Collect all changed html files
    changed_paths = set()
    for commit in commits[:20]:  # max 20 commits
        sha = commit["sha"]
        detail_url = f"https://api.github.com/repos/phanvuhoang/vn-tax-corpus/commits/{sha}"
        async with httpx.AsyncClient(timeout=30) as client:
            detail = (await client.get(detail_url, headers=headers)).json()
        for f in detail.get("files", []):
            fname = f.get("filename", "")
            if fname.startswith("docs/") and fname.endswith(".html"):
                # strip "docs/" prefix → github_path used in DB
                changed_paths.add(fname[5:])  # e.g. "I.THUE/001.../003._ND_320.html"
    
    if not changed_paths:
        return {"items": [], "since": since}
    
    # Check which are NOT yet in DB
    r = await db.execute(text("SELECT github_path FROM documents"))
    existing = {row[0] for row in r.fetchall()}
    
    r2 = await db.execute(text("SELECT github_path FROM cong_van"))
    existing |= {row[0] for row in r2.fetchall() if row[0]}
    
    new_paths = [p for p in changed_paths if p not in existing]
    
    # Fetch index.json from corpus to get metadata for each path
    index_url = "https://raw.githubusercontent.com/phanvuhoang/vn-tax-corpus/main/index.json"
    async with httpx.AsyncClient(timeout=30) as client:
        index_raw = (await client.get(index_url)).json()
    
    # Build path → metadata map (index uses relative path in field 'p')
    path_map = {item.get("p", ""): item for item in index_raw if item.get("p")}
    
    items = []
    for path in new_paths:
        meta = path_map.get(path, {})
        items.append({
            "github_path": path,
            "name": meta.get("n", path.split("/")[-1]),
            "so_hieu": meta.get("so_hieu", ""),
            "loai": meta.get("t", ""),
            "tx": meta.get("tx", ""),
            "date_id": meta.get("id", ""),
        })
    
    # Sort: newest first by date_id
    items.sort(key=lambda x: x.get("date_id", "") or "", reverse=True)
    
    return {"items": items, "since": since, "total": len(items)}
```

---

### 2. New endpoint: `POST /api/admin/corpus-import`

Import các docs được chọn từ corpus vào DB.

```python
class CorpusImportRequest(BaseModel):
    paths: List[str]  # list of github_paths to import

@app.post("/api/admin/corpus-import")
async def corpus_import(
    req: CorpusImportRequest,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Với mỗi path:
    1. Fetch HTML từ raw.githubusercontent.com
    2. Parse: so_hieu, ten, loai, ngay_ban_hanh
    3. Classify sac_thue từ content + path
    4. INSERT vào documents (không UPDATE nếu đã có)
    """
    import httpx
    from bs4 import BeautifulSoup
    import re
    
    # Load index.json once for metadata
    index_url = "https://raw.githubusercontent.com/phanvuhoang/vn-tax-corpus/main/index.json"
    async with httpx.AsyncClient(timeout=30) as client:
        index_raw = (await client.get(index_url)).json()
    path_map = {item.get("p", ""): item for item in index_raw if item.get("p")}
    
    results = []
    
    for path in req.paths:
        try:
            # Fetch HTML
            raw_url = f"https://raw.githubusercontent.com/phanvuhoang/vn-tax-corpus/main/docs/{path}"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(raw_url)
            
            if resp.status_code != 200:
                results.append({"path": path, "status": "error", "msg": f"HTTP {resp.status_code}"})
                continue
            
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text("\n", strip=True)
            
            # Get metadata from index
            meta = path_map.get(path, {})
            name = meta.get("n", "").strip()
            so_hieu = meta.get("so_hieu") or ""
            
            # Extract so_hieu from name if not set
            if not so_hieu:
                m = re.search(r'(\d{1,5}/\d{4}/[\wĐ\-]+)', name)
                if m:
                    so_hieu = m.group(1)
            
            # Extract ngay_ban_hanh from content
            date_match = re.search(r'[Hh]à\s*[Nn]ội[,\s]+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(20\d{2})', text_content)
            if date_match:
                d, mo, y = date_match.groups()
                ngay_ban_hanh = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
            else:
                # Fallback: parse id field (YYYYMMDD)
                date_id = meta.get("id", "") or ""
                if len(str(date_id)) == 8:
                    s = str(date_id)
                    ngay_ban_hanh = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
                else:
                    ngay_ban_hanh = None
            
            # Determine loai
            t_raw = meta.get("t", "")
            TYPE_MAP = {"NĐ": "ND", "Nghị định": "ND", "TT": "TT", "Luật": "Luat",
                       "VBHN": "VBHN", "QĐ": "QD", "NQ": "NQ", "CV": "CV", "Khác": "Khac"}
            loai = TYPE_MAP.get(t_raw, "Khac")
            
            # Classify sac_thue
            tx = meta.get("tx", "")
            TX_MAP = {"TNDN": "TNDN", "GTGT": "GTGT", "TNCN": "TNCN", "TTDB": "TTDB",
                     "NhaThau": "FCT", "GDLK": "GDLK", "QLT": "QLT", "HoaDon": "HOA_DON",
                     "HKD": "HKD", "CIT": "TNDN"}
            sac_thue = [TX_MAP[tx]] if tx in TX_MAP else ["QLT"]
            
            # importance
            IMP_MAP = {"ND": 1, "TT": 1, "Luat": 2, "VBHN": 2, "NQ": 2, "QD": 3, "CV": 4, "Khac": 3}
            importance = IMP_MAP.get(loai, 3)
            
            # Render clean HTML (strip TVPL layout artifacts)
            content_div = soup.find("div", id="divContentDoc") or soup.find("body")
            noi_dung = str(content_div) if content_div else html
            
            # Build link
            tvpl_url = f"https://thuvienphapluat.vn/van-ban/{path.replace('/', '-')}"
            
            if loai == "CV":
                # Insert to cong_van
                await db.execute(text("""
                    INSERT INTO cong_van (so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, chu_de,
                        nguon, link_nguon, github_path, doc_type, importance, import_date, keywords, noi_dung)
                    VALUES (:so_hieu, :ten, 'Tổng cục Thuế', :ngay::date, :sac_thue, '{}',
                        'corpus', :github_path, :github_path, 'congvan', :importance, NOW(), '{}', :noi_dung)
                    ON CONFLICT (link_nguon) DO NOTHING
                """), {
                    "so_hieu": so_hieu, "ten": name,
                    "ngay": ngay_ban_hanh, "sac_thue": sac_thue,
                    "github_path": path, "importance": importance, "noi_dung": noi_dung
                })
            else:
                # Insert to documents
                await db.execute(text("""
                    INSERT INTO documents (so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
                        github_path, doc_type, importance, import_date, keywords, noi_dung, tvpl_url)
                    VALUES (:so_hieu, :ten, :loai, :ngay::date, 'con_hieu_luc', :sac_thue,
                        :github_path, 'vanban', :importance, NOW(), '{}', :noi_dung, :tvpl_url)
                    ON CONFLICT (github_path) DO NOTHING
                """), {
                    "so_hieu": so_hieu, "ten": name, "loai": loai,
                    "ngay": ngay_ban_hanh, "sac_thue": sac_thue,
                    "github_path": path, "importance": importance,
                    "noi_dung": noi_dung, "tvpl_url": tvpl_url
                })
            
            await db.commit()
            results.append({"path": path, "status": "ok", "so_hieu": so_hieu, "ten": name[:60]})
        
        except Exception as e:
            results.append({"path": path, "status": "error", "msg": str(e)})
    
    return {"results": results}
```

---

### 3. New endpoint: `POST /api/admin/tvpl-import`

Import trực tiếp từ TVPL URL.

```python
class TVPLImportRequest(BaseModel):
    url: str
    loai_override: Optional[str] = None    # e.g. "ND", "TT", "Luat" — nếu auto-detect sai
    sac_thue_override: Optional[List[str]] = None  # e.g. ["GTGT"]

@app.post("/api/admin/tvpl-import")
async def tvpl_import(
    req: TVPLImportRequest,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch trực tiếp từ TVPL URL.
    NOTE: TVPL block IP Hostinger, nên endpoint này phải gọi qua
    một proxy request từ OpenClaw container — hoặc để frontend gọi và
    truyền HTML vào (client-side fetch workaround).
    
    API nhận HTML đã fetch sẵn (từ frontend hoặc proxy):
    """
    # Thực tế: TVPL block IP VPS → dùng client-side fetch
    # Endpoint nhận url + html (pre-fetched by client)
    pass
```

**⚠️ Vấn đề TVPL block IP:** TVPL block IP Hostinger nên VPS không fetch được trực tiếp.

**Giải pháp:** Tách thành 2 sub-features:
- **3a.** Frontend fetch TVPL URL client-side → gửi HTML lên server parse
- **3b.** Admin paste TVPL URL → copy HTML source → paste vào textarea

Dùng 3b là đơn giản nhất, không cần bypass gì cả.

#### Endpoint thực tế cho TVPL:

```python
class TVPLImportRequest(BaseModel):
    url: str                                # TVPL URL (để lưu làm reference)
    html_content: Optional[str] = None      # Pre-fetched HTML (nếu client fetch được)
    loai_override: Optional[str] = None
    sac_thue_override: Optional[List[str]] = None

@app.post("/api/admin/tvpl-import")
async def tvpl_import(
    req: TVPLImportRequest,
    current_user = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    import httpx, re
    from bs4 import BeautifulSoup
    
    html = req.html_content
    
    # Nếu không có HTML sẵn, thử fetch (có thể work hoặc không tùy IP)
    if not html:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36",
                "Accept-Language": "vi-VN,vi;q=0.9",
                "Cookie": ""  # No auth needed for most docs
            }
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(req.url, headers=headers)
            if resp.status_code == 200:
                html = resp.text
            else:
                return {"status": "error", "msg": f"Cannot fetch TVPL: HTTP {resp.status_code}. Please paste HTML manually."}
        except Exception as e:
            return {"status": "error", "msg": f"Fetch failed: {e}. Please paste HTML manually."}
    
    soup = BeautifulSoup(html, "html.parser")
    text_content = soup.get_text("\n", strip=True)
    lines = [l.strip() for l in text_content.split("\n") if l.strip()]
    
    # Extract so_hieu (look for "Số: XXX/YYYY/ZZZ" pattern)
    so_hieu = ""
    for line in lines[:50]:
        m = re.search(r'Số:\s*(\d{1,5}/\d{4}/[\wĐ\-]+)', line)
        if m:
            so_hieu = m.group(1)
            break
    
    # Extract title (after NGHỊ ĐỊNH / THÔNG TƯ / LUẬT header)
    title = ""
    for i, line in enumerate(lines[:80]):
        if line.upper() in ("NGHỊ ĐỊNH", "THÔNG TƯ", "LUẬT", "QUYẾT ĐỊNH", "NGHỊ QUYẾT", "VĂN BẢN HỢP NHẤT"):
            # Title is the next non-empty line(s)
            title_parts = []
            for j in range(i+1, min(i+6, len(lines))):
                if lines[j] and not lines[j].startswith("Căn cứ"):
                    title_parts.append(lines[j])
                else:
                    break
            title = " ".join(title_parts).strip()
            break
    if not title and so_hieu:
        title = so_hieu  # Fallback
    
    # Build ten = "ND 320/2025/NĐ-CP — [title]" style
    type_prefix = {"ND": "NĐ", "TT": "TT", "Luat": "Luật", "VBHN": "VBHN"}
    
    # Determine loai from URL or so_hieu
    loai = req.loai_override or "Khac"
    if not req.loai_override:
        url_lower = req.url.lower()
        if "nghi-dinh" in url_lower or "/nd-" in so_hieu.lower():
            loai = "ND"
        elif "thong-tu" in url_lower or "/tt-" in so_hieu.lower():
            loai = "TT"
        elif "luat" in url_lower:
            loai = "Luat"
        elif "quyet-dinh" in url_lower:
            loai = "QD"
        elif "nghi-quyet" in url_lower:
            loai = "NQ"
        elif "van-ban-hop-nhat" in url_lower:
            loai = "VBHN"
        elif "cong-van" in url_lower or "chi-thi" in url_lower:
            loai = "CV"
    
    # ten = full title
    pfx = type_prefix.get(loai, "")
    ten = f"{pfx} {so_hieu} — {title}".strip(" —") if so_hieu else title
    
    # Extract ngay_ban_hanh
    date_match = re.search(r'[Hh]à\s*[Nn]ội[,\s]+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(20\d{2})', text_content)
    ngay_ban_hanh = None
    if date_match:
        d, mo, y = date_match.groups()
        ngay_ban_hanh = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    
    # Classify sac_thue
    sac_thue = req.sac_thue_override or []
    if not sac_thue:
        KEYWORDS = {
            "TNDN": ["thu nhập doanh nghiệp", "tndn"],
            "GTGT": ["giá trị gia tăng", "gtgt", "vat"],
            "TNCN": ["thu nhập cá nhân", "tncn"],
            "TTDB": ["tiêu thụ đặc biệt", "ttdb", "ttđb"],
            "FCT": ["nhà thầu nước ngoài", "nhà thầu"],
            "GDLK": ["giao dịch liên kết", "chuyển giá"],
            "QLT": ["quản lý thuế", "kê khai", "nộp thuế"],
            "HOA_DON": ["hóa đơn điện tử", "hóa đơn"],
            "HKD": ["hộ kinh doanh"],
            "XNK": ["xuất nhập khẩu", "hải quan"],
        }
        text_lower = text_content[:2000].lower()
        for code, kws in KEYWORDS.items():
            if any(kw in text_lower for kw in kws):
                sac_thue.append(code)
        if not sac_thue:
            sac_thue = ["QLT"]
    
    IMP_MAP = {"ND": 1, "TT": 1, "Luat": 2, "VBHN": 2, "NQ": 2, "QD": 3, "CV": 4, "Khac": 3}
    importance = IMP_MAP.get(loai, 3)
    
    # Clean noi_dung
    content_div = soup.find("div", id="divContentDoc") or soup.find("body")
    noi_dung = str(content_div) if content_div else html
    # Strip TVPL layout artifacts (width, float, tooltip bar)
    noi_dung = re.sub(r'width:\s*\d+\.?\d*(pt|px|%)\s*;?\s*', '', noi_dung)
    noi_dung = re.sub(r'float:\s*\w+\s*;?\s*', '', noi_dung)
    
    # Build github_path from URL slug  
    import hashlib
    url_slug = req.url.split("/van-ban/")[-1].split(".aspx")[0] if "/van-ban/" in req.url else hashlib.md5(req.url.encode()).hexdigest()[:16]
    github_path = f"tvpl/{url_slug}.html"
    
    try:
        if loai == "CV":
            await db.execute(text("""
                INSERT INTO cong_van (so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, chu_de,
                    nguon, link_nguon, github_path, doc_type, importance, import_date, keywords, noi_dung, link_tvpl)
                VALUES (:so_hieu, :ten, 'Tổng cục Thuế', :ngay::date, :sac_thue, '{}',
                    'tvpl', :url, :github_path, 'congvan', :importance, NOW(), '{}', :noi_dung, :url)
                ON CONFLICT (link_nguon) DO NOTHING
            """), {
                "so_hieu": so_hieu, "ten": ten, "ngay": ngay_ban_hanh,
                "sac_thue": sac_thue, "url": req.url, "github_path": github_path,
                "importance": importance, "noi_dung": noi_dung
            })
        else:
            await db.execute(text("""
                INSERT INTO documents (so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
                    github_path, doc_type, importance, import_date, keywords, noi_dung, tvpl_url)
                VALUES (:so_hieu, :ten, :loai, :ngay::date, 'con_hieu_luc', :sac_thue,
                    :github_path, 'vanban', :importance, NOW(), '{}', :noi_dung, :url)
                ON CONFLICT (github_path) DO NOTHING
            """), {
                "so_hieu": so_hieu, "ten": ten, "loai": loai,
                "ngay": ngay_ban_hanh, "sac_thue": sac_thue,
                "github_path": github_path, "importance": importance,
                "noi_dung": noi_dung, "url": req.url
            })
        await db.commit()
    except Exception as e:
        return {"status": "error", "msg": str(e), "preview": {"so_hieu": so_hieu, "ten": ten, "loai": loai}}
    
    return {
        "status": "ok",
        "preview": {
            "so_hieu": so_hieu,
            "ten": ten,
            "loai": loai,
            "ngay_ban_hanh": ngay_ban_hanh,
            "sac_thue": sac_thue,
            "importance": importance
        }
    }
```

---

### 4. New endpoint: `POST /api/admin/tvpl-preview`

Preview metadata trước khi import (không save vào DB).

```python
@app.post("/api/admin/tvpl-preview")
async def tvpl_preview(req: TVPLImportRequest, current_user = Depends(require_admin)):
    """Chỉ parse + trả metadata, không insert vào DB. Dùng để user confirm trước."""
    # Same logic as tvpl_import nhưng return sớm, không INSERT
    ...
    return {"so_hieu": so_hieu, "ten": ten, "loai": loai, "ngay_ban_hanh": ngay_ban_hanh, "sac_thue": sac_thue}
```

---

### 5. Disable sync (main.py)

Xóa hoặc comment out bất kỳ auto-sync / background task nào liên quan đến `sync_corpus.py`.

---

## Frontend changes

### New page: `AdminPage.tsx`

Thêm route `/admin` (chỉ hiện khi user là admin).

#### Layout AdminPage:
```
[Tab: Từ Corpus] [Tab: Từ TVPL]
```

---

#### Tab 1: Từ Corpus

```
┌─────────────────────────────────────────────────┐
│ 📦 Import từ vn-tax-corpus                       │
│                                                   │
│ Tìm văn bản mới được thêm vào corpus             │
│ (so với lần import gần nhất: 2026-03-25)         │
│                                                   │
│ [🔍 Kiểm tra văn bản mới]                        │
│                                                   │
│ Kết quả: 3 văn bản mới                           │
│ ┌─────────────────────────────────────────────┐  │
│ │ ☑ NĐ 320/2025/NĐ-CP — Quy định chi tiết... │  │
│ │   Loại: ND | Sắc thuế: TNDN | 15/12/2025  │  │
│ │ ☑ TT 20/2026/TT-BTC — Hướng dẫn Luật...  │  │
│ │   Loại: TT | Sắc thuế: TNDN | 12/03/2026  │  │
│ │ ☐ NĐ 359/2025/NĐ-CP — Sửa đổi NĐ 181...  │  │
│ │   Loại: ND | Sắc thuế: GTGT | 31/12/2025  │  │
│ └─────────────────────────────────────────────┘  │
│                                                   │
│ [✅ Import đã chọn (2)]                           │
└─────────────────────────────────────────────────┘
```

**Behavior:**
- Bấm "Kiểm tra" → gọi `GET /api/admin/corpus-new` → hiện danh sách
- Mặc định tick tất cả
- Bấm "Import đã chọn" → gọi `POST /api/admin/corpus-import` với `paths` = các path đã tick
- Hiện progress và kết quả từng doc

---

#### Tab 2: Từ TVPL

```
┌─────────────────────────────────────────────────┐
│ 🌐 Import từ TVPL                                │
│                                                   │
│ URL văn bản:                                      │
│ [https://thuvienphapluat.vn/van-ban/...     ]     │
│                                                   │
│ [🔍 Preview]                                      │
│                                                   │
│ ── Preview ──────────────────────────────────    │
│ Số hiệu:  320/2025/NĐ-CP                        │
│ Tiêu đề:  NĐ 320/2025/NĐ-CP — Quy định...     │
│ Loại:     [ND ▼]  ← dropdown để override        │
│ Sắc thuế: [TNDN ▼] [+ thêm]                     │
│ Ngày:     15/12/2025                             │
│                                                   │
│ ⚠️ Ghi chú: TVPL có thể block IP server.        │
│ Nếu lỗi, paste HTML source vào đây:              │
│ [                                      ] ← textarea│
│                                                   │
│ [✅ Import vào DB]                                │
└─────────────────────────────────────────────────┘
```

**Behavior:**
1. Nhập URL → bấm Preview → gọi `POST /api/admin/tvpl-preview`
2. App thử fetch server-side
3. Nếu fail → hiện textarea để paste HTML thủ công
4. Preview hiện metadata parsed
5. Admin có thể override Loại và Sắc thuế nếu auto-detect sai
6. Bấm Import → gọi `POST /api/admin/tvpl-import`
7. Hiện kết quả (thành công / lỗi + reason)

---

### Navigation: Thêm link Admin vào header/sidebar

Trong `HomePage.tsx` hoặc layout component, nếu `auth.user?.role === 'admin'`:
- Hiện nút "⚙️ Admin" góc trên phải → navigate đến `/admin`
- Hoặc thêm vào menu mobile

---

### Router (`App.tsx`)

```tsx
import AdminPage from './pages/AdminPage';

// Trong routes:
<Route path="/admin" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
```

---

## Dependencies cần thêm vào `requirements.txt`

`httpx` — đã có (kiểm tra `requirements.txt`)

---

## Tắt sync cron trên VPS

Sau khi deploy, anh (hoặc em) cần chạy trên VPS:
```bash
# Remove cron job
crontab -l | grep -v sync_corpus | crontab -
```

Brief này không tự xóa cron — để tránh vô tình xóa nhầm.

---

## Testing checklist

- [ ] GET /api/admin/corpus-new → trả list docs mới từ GitHub
- [ ] POST /api/admin/corpus-import với 1 path → doc xuất hiện trong DB với noi_dung
- [ ] POST /api/admin/tvpl-preview với TVPL URL → trả metadata đúng
- [ ] POST /api/admin/tvpl-import → doc xuất hiện, searchable trên frontend
- [ ] User thường KHÔNG thấy /admin route (403)
- [ ] Admin thấy nút "Admin" trên UI

---

*Brief by Thanh AI — 2026-03-25*
