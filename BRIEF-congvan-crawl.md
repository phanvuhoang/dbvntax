# BRIEF: Công Văn Thuế — Crawl + Taxonomy Sidebar
**Repo:** phanvuhoang/dbvntax  
**PAT:** ghp_XXXXXXXXXXXXXXXXXXXX (lấy từ anh Hoàng)  
**Push từ:** OpenClaw container (GitHub chặn IP Hostinger VPS)  
**Date:** 2026-03-15

---

## Tổng quan

Implement 4 thứ:
1. `crawl_tvpl.py` — crawler công văn thuế từ thuvienphapluat.vn (46k+ CVs)
2. DB migration — thêm unique constraint + tvpl_id field
3. API endpoint mới — `GET /api/cong-van/taxonomy` (trả chu_de counts)
4. Sidebar update — accordion expandable taxonomy khi ở tab Công Văn

---

## 1. `crawl_tvpl.py` (file mới ở root repo)

### Cách hoạt động — 3 modes

```
python3 crawl_tvpl.py --mode bulk        # Lần đầu: crawl toàn bộ 46k CVs
python3 crawl_tvpl.py --mode incremental # Hàng ngày: chỉ CVs mới
python3 crawl_tvpl.py --mode enrich      # Background: fetch full content + embed
python3 crawl_tvpl.py --dry-run          # Test không insert DB
python3 crawl_tvpl.py --limit 100        # Giới hạn số bản ghi
```

### Logic chi tiết

#### Login TVPL (shared cho tất cả modes)
```python
# 1. GET https://thuvienphapluat.vn/page/login.aspx  →  lấy ASP.NET_SessionId
# 2. POST https://thuvienphapluat.vn/page/ajaxcontroler.aspx
#    data: "l_txtUser=pvhptm&l_txtPass=368Charter&action=Login"
#    headers: X-Requested-With: XMLHttpRequest
#    → response: "<ok>" nếu thành công
# 3. Sau đó session có cookies: dl_user, lg_user, thuvienphapluatnew, c_user
# Dùng session object của requests để giữ cookies tự động
```

#### URL crawl (filter sẵn: công văn thuế)
```
https://thuvienphapluat.vn/page/tim-van-ban.aspx
  ?keyword=&area=0&match=True&type=3&status=0&signer=0
  &sort=1&lan=1&scan=0&org=0&fields=6
  &Page=N   ← thêm param này để phân trang (bắt đầu từ 1)
```

#### Extract từ listing page (HTML parsing, không cần JS)
```python
import re
from html import unescape

# Mỗi item có: <div class="left-col"> + <div class="right-col">
# left-col chứa: lawid, title, link
# right-col chứa: ngày ban hành, hiệu lực, tình trạng

# Pattern lấy pairs:
pairs = re.findall(
    r'<div class="left-col">(.*?)</div>\s*<div class="right-col">(.*?)</div>',
    html, re.DOTALL
)

for left, right in pairs:
    lawid = re.search(r"lawid='(\d+)'", left).group(1)
    title_m = re.search(r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', left)
    link = title_m.group(1)          # full URL
    title = unescape(title_m.group(2))

    date_m = re.search(r'Ban hành:\s*</span>\s*(\d{2}/\d{2}/\d{4})', right)
    status_m = re.search(r'Tình trạng:\s*</span>[^<]*<span[^>]*>([^<]+)', right)
    # nếu không có span thì:
    if not status_m:
        status_m = re.search(r'Tình trạng:\s*</span>\s*([^\n<]{3,40})', right)

    ngay_ban_hanh = date_m.group(1) if date_m else None   # format dd/mm/yyyy
    tinh_trang = status_m.group(1).strip() if status_m else ''
    # "Còn hiệu lực" / "Hết hiệu lực" / "Chưa có hiệu lực"
```

#### Extract số hiệu (so_hieu) và cơ quan (co_quan) từ title
```python
# Title format: "Công văn 1410/CT-CS năm 2026 ... do Cục Thuế ban hành"
# hoặc:        "Công văn 265/SLA-NVDTPC năm 2026 ... do Thuế tỉnh Sơn La ban hành"

so_hieu_m = re.match(r'Công văn\s+(\S+)\s+năm', title, re.IGNORECASE)
so_hieu = so_hieu_m.group(1) if so_hieu_m else ''
# VD: "1410/CT-CS", "265/SLA-NVDTPC"

co_quan_m = re.search(r'\bdo\s+(.+?)\s+ban hành', title, re.IGNORECASE)
co_quan = co_quan_m.group(1) if co_quan_m else ''
# VD: "Cục Thuế", "Thuế tỉnh Sơn La", "Tổng cục Thuế"
```

#### Total pages
```python
# Tổng số CVs:
total_m = re.search(r'<span[^>]*id="lbTotal"[^>]*>(\d+)', html)
total = int(total_m.group(1))  # VD: 46849
pages = (total + 19) // 20     # 20 items/page → ~2342 pages
```

#### Mode BULK
```python
# Crawl từ page 1 đến hết
# Delay 0.5s giữa các request (lịch sự với server)
# Log tiến độ mỗi 50 trang: "Page 50/2342 — 1000 CVs inserted"
# Nếu gặp lỗi 429/503: wait 30s rồi retry
```

#### Mode INCREMENTAL
```python
# Crawl từ page 1, sort=1 (mới nhất trước)
# Với mỗi item, check link_nguon trong DB:
#   SELECT 1 FROM cong_van WHERE link_nguon = :link LIMIT 1
# Nếu đã có → STOP (không cần crawl thêm)
# Nếu 3 trang liên tiếp đều có CVs mới → tiếp tục
# Thường chỉ cần 1-3 trang (20-60 CVs mới/ngày)
```

#### Mode ENRICH
```python
# Tìm CVs chưa có noi_dung_day_du hoặc embedding:
#   SELECT id, link_nguon FROM cong_van 
#   WHERE (noi_dung_day_du IS NULL OR embedding IS NULL)
#   AND nguon = 'tvpl'
#   ORDER BY importance DESC, ngay_ban_hanh DESC
#   LIMIT 500
# Với mỗi CV: GET link_nguon → extract nội dung → tạo embedding
# Cần login TVPL (một số nội dung yêu cầu đăng nhập)
# Delay 1s/request
```

### Insert vào DB
```python
# Dùng SQLAlchemy async (giống crawl_congvan.py hiện tại)
# DATABASE_URL từ env hoặc default

INSERT INTO cong_van (
    so_hieu, ten, co_quan, ngay_ban_hanh, tinh_trang,
    sac_thue, chu_de,
    nguon, link_nguon,
    tvpl_id, keywords
)
VALUES (...)
ON CONFLICT (link_nguon) DO UPDATE SET
    tinh_trang = EXCLUDED.tinh_trang,
    import_date = NOW()
-- Chỉ update tinh_trang nếu đã có (văn bản có thể hết hiệu lực)

# tvpl_id = lawid từ HTML (integer)
# nguon = 'tvpl'
```

### Phân loại tự động
```python
# Import từ taxonomy.py (đã có sẵn)
from taxonomy import classify_document, classify_chu_de

sac_thue_list = classify_document(title)
chu_de_list = classify_chu_de(title, sac_thue_list)

# classify_document(title) → ["TNDN", "QLT"] (có thể nhiều sắc thuế)
# classify_chu_de(title, sac_thue_list) → ["Chi phí được trừ", "Kê khai & quyết toán"]
```

### Dependency
```
pip install requests sqlalchemy asyncpg httpx
# Không cần Playwright hay Selenium - site server-side render được
```

---

## 2. DB Migration (thêm vào lifespan trong main.py)

```python
# Thêm vào khối migration trong lifespan():

# tvpl_id field
await db.execute(text(
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS tvpl_id INTEGER"
))

# tinh_trang field  
await db.execute(text(
    "ALTER TABLE cong_van ADD COLUMN IF NOT EXISTS tinh_trang VARCHAR(50)"
))

# Unique constraint: (so_hieu, ngay_ban_hanh) để detect duplicates
# Dùng partial index (chỉ khi so_hieu không null)
await db.execute(text("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_cv_so_hieu_ngay
    ON cong_van (so_hieu, ngay_ban_hanh)
    WHERE so_hieu IS NOT NULL AND so_hieu != ''
"""))

# Index cho tvpl_id
await db.execute(text(
    "CREATE INDEX IF NOT EXISTS idx_cv_tvpl_id ON cong_van (tvpl_id) WHERE tvpl_id IS NOT NULL"
))
```

---

## 3. API Endpoint Mới (thêm vào main.py)

```python
@app.get("/api/cong-van/taxonomy")
async def cong_van_taxonomy(
    sac_thue: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Trả về danh sách chu_de với count, grouped by sac_thue.
    Dùng cho Sidebar accordion khi ở tab Công Văn.
    
    Response format:
    {
      "TNDN": [
        {"chu_de": "Chi phí được trừ", "count": 142},
        {"chu_de": "Ưu đãi thuế TNDN", "count": 87},
        ...
      ],
      "GTGT": [...],
      ...
    }
    """
    # Nếu có filter sac_thue → chỉ trả taxonomy của sắc thuế đó
    where = ""
    params = {}
    if sac_thue:
        where = "WHERE :sac_thue = ANY(sac_thue)"
        params["sac_thue"] = sac_thue
    
    r = await db.execute(text(f"""
        SELECT 
            st as sac_thue,
            cd as chu_de,
            COUNT(*) as count
        FROM cong_van
        CROSS JOIN LATERAL unnest(sac_thue) as st
        CROSS JOIN LATERAL unnest(chu_de) as cd
        {where}
        GROUP BY st, cd
        ORDER BY st, count DESC
    """), params)
    
    rows = r.mappings().all()
    
    # Group by sac_thue
    result = {}
    for row in rows:
        st = row["sac_thue"]
        if st not in result:
            result[st] = []
        result[st].append({"chu_de": row["chu_de"], "count": row["count"]})
    
    return result
```

**Lưu ý:** Thêm endpoint này VÀO TRƯỚC endpoint `/api/cong-van` hiện tại trong main.py (FastAPI match theo thứ tự, "taxonomy" phải trước `/{cv_id}`).

---

## 4. Sidebar — Accordion Taxonomy (frontend)

### Thay đổi trong `frontend/src/components/Sidebar.tsx`

**Logic:**
- Khi `tab === 'vanban'`: giữ nguyên như hiện tại (flat list sắc thuế)
- Khi `tab === 'congvan'`: mỗi sắc thuế có accordion expandable → hiển thị danh sách chu_de bên trong

**Props mới cần thêm:**
```typescript
interface Props {
  selected: string;
  onSelect: (code: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateRangeChange: (from: string, to: string) => void;
  tab: 'vanban' | 'congvan';              // MỚI
  selectedChuDe?: string;                  // MỚI
  onChuDeSelect?: (chuDe: string) => void; // MỚI
}
```

**API hook mới trong `frontend/src/api.ts`:**
```typescript
// Thêm hook useCongVanTaxonomy
export function useCongVanTaxonomy(sacThue?: string) {
  return useQuery({
    queryKey: ['congvan-taxonomy', sacThue],
    queryFn: () => api.get(`/api/cong-van/taxonomy${sacThue ? `?sac_thue=${sacThue}` : ''}`).then(r => r.data),
    staleTime: 5 * 60 * 1000,
  });
}
```

**Types mới trong `frontend/src/types.ts`:**
```typescript
export interface TaxonomyItem {
  chu_de: string;
  count: number;
}

export interface CongVanTaxonomy {
  [sacThue: string]: TaxonomyItem[];
}
```

**Sidebar render khi tab === 'congvan':**
```tsx
// Thay thế phần categories.map() bằng:
{tab === 'congvan' ? (
  // Accordion mode
  categories.map((cat) => (
    <div key={cat.code}>
      {/* Header sắc thuế — clickable để expand/collapse */}
      <button
        onClick={() => toggleExpanded(cat.code)}
        className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
          ${category === cat.code ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
      >
        <span className="flex items-center gap-1">
          <span className={`text-xs transition-transform ${expanded[cat.code] ? 'rotate-90' : ''}`}>▶</span>
          {cat.name}
        </span>
        {cat.count > 0 && (
          <span className="text-[11px] rounded-full px-1.5 bg-gray-100 text-gray-500">
            {cat.count}
          </span>
        )}
      </button>
      
      {/* Taxonomy items — chỉ hiện khi expanded */}
      {expanded[cat.code] && taxonomy?.[cat.code] && (
        <div className="ml-4 border-l border-gray-100">
          {/* "Tất cả" option */}
          <button
            onClick={() => { onSelect(cat.code); onChuDeSelect?.(''); }}
            className={`w-full text-left px-3 py-1 text-xs transition
              ${category === cat.code && !selectedChuDe
                ? 'text-primary font-semibold'
                : 'text-gray-500 hover:text-primary hover:bg-gray-50'}`}
          >
            Tất cả
          </button>
          
          {taxonomy[cat.code].slice(0, 10).map((item) => (
            <button
              key={item.chu_de}
              onClick={() => { onSelect(cat.code); onChuDeSelect?.(item.chu_de); }}
              className={`w-full flex justify-between items-center px-3 py-1 text-xs transition
                ${selectedChuDe === item.chu_de && category === cat.code
                  ? 'text-primary font-semibold bg-primary-light'
                  : 'text-gray-500 hover:text-primary hover:bg-gray-50'}`}
            >
              <span className="truncate">{item.chu_de}</span>
              <span className="text-[10px] text-gray-400 ml-1 flex-shrink-0">{item.count}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  ))
) : (
  // Flat mode (tab vanban) — giữ nguyên code hiện tại
  categories.map((cat) => (
    <button ... />
  ))
)}
```

**State trong Sidebar:**
```typescript
const [expanded, setExpanded] = useState<Record<string, boolean>>({});
const { data: taxonomy } = useCongVanTaxonomy();  // load toàn bộ taxonomy

const toggleExpanded = (code: string) => {
  setExpanded(prev => ({ ...prev, [code]: !prev[code] }));
};
```

### Thay đổi trong `frontend/src/pages/HomePage.tsx`

```typescript
// Thêm state
const [selectedChuDe, setSelectedChuDe] = useState('');

// Update useCongVan hook call — thêm chu_de filter
const congVanResult = useCongVan({
  q: query,
  sac_thue: category,
  chu_de: selectedChuDe,   // MỚI
  year_from: ...,
  year_to: ...,
  limit: LIMIT,
  offset: (page - 1) * LIMIT,
});

// handleTabChange: reset selectedChuDe
const handleTabChange = useCallback((t: Tab) => {
  setTab(t); setPage(1); setSelectedItem(null);
  setSelectedChuDe('');   // MỚI
}, []);
```

### Thay đổi trong `search.py` — `list_cong_van` function

```python
async def list_cong_van(
    db, q, sac_thue, nguon, limit, offset,
    year_from=None, year_to=None,
    chu_de=None,      # MỚI
    tinh_trang=None,  # MỚI (filter "Còn hiệu lực" / "Hết hiệu lực")
):
    # Thêm filter chu_de:
    if chu_de:
        where.append(":chu_de = ANY(chu_de)")
        params['chu_de'] = chu_de
    
    if tinh_trang:
        where.append("tinh_trang = :tinh_trang")
        params['tinh_trang'] = tinh_trang
```

### Thay đổi trong `main.py` — `/api/cong-van` endpoint

```python
@app.get("/api/cong-van")
async def cong_van_list(
    q: str = "",
    sac_thue: Optional[str] = None,
    nguon: Optional[str] = None,
    chu_de: Optional[str] = None,      # MỚI
    tinh_trang: Optional[str] = None,  # MỚI
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    results, total = await list_cong_van(
        db, q, sac_thue, nguon, limit, offset,
        year_from=year_from, year_to=year_to,
        chu_de=chu_de, tinh_trang=tinh_trang,
    )
    return {"total": total, "items": results}
```

---

## Thứ tự implement (quan trọng)

1. **DB migration** (main.py lifespan) → deploy trước
2. **`crawl_tvpl.py`** → test `--dry-run --limit 5` trước
3. **API endpoint `/api/cong-van/taxonomy`** + update `/api/cong-van` với chu_de filter
4. **search.py** update `list_cong_van`
5. **Frontend** (types.ts → api.ts → Sidebar.tsx → HomePage.tsx)
6. **Deploy** → chạy `python3 crawl_tvpl.py --mode incremental` để test
7. **Chạy bulk** sau khi confirm incremental OK

---

## Files cần thay đổi

| File | Action |
|------|--------|
| `crawl_tvpl.py` | **TẠO MỚI** |
| `main.py` | Sửa: add migration, add taxonomy endpoint, update cong-van endpoint |
| `search.py` | Sửa: add chu_de + tinh_trang filter vào list_cong_van |
| `frontend/src/types.ts` | Sửa: thêm TaxonomyItem, CongVanTaxonomy |
| `frontend/src/api.ts` | Sửa: thêm useCongVanTaxonomy hook, update useCongVan với chu_de |
| `frontend/src/components/Sidebar.tsx` | Sửa: accordion mode khi tab congvan |
| `frontend/src/pages/HomePage.tsx` | Sửa: thêm selectedChuDe state, pass props mới |

---

## Cách chạy crawl (quan trọng)

### PostgreSQL chỉ accessible trong Docker network trên VPS
- DB URL: `postgresql://legaldb_user:PbSV8bfxQdta4ljBsDVtZEe74yjMG6l7uW3dSczT8Iaajm9MKX07wHqyf0xBTTMF@i11456c94loppyu9vzmgyb44:5432/postgres`
- **Không expose port 5432 ra ngoài** → phải chạy script trên VPS (72.62.197.183)
- VPS có sẵn: Python 3.12, psycopg2, requests

### Bulk crawl lần đầu (chạy 1 lần từ VPS)
```bash
# SSH vào VPS
ssh root@72.62.197.183

# Clone repo (hoặc copy file lên)
git clone https://github.com/phanvuhoang/dbvntax.git /opt/dbvntax
cd /opt/dbvntax

# Test trước
python3 crawl_tvpl.py --dry-run --limit 20

# Chạy bulk (có thể mất 30-60 phút)
# Dùng nohup để không bị ngắt khi đóng terminal
nohup python3 crawl_tvpl.py --mode bulk > /var/log/tvpl-bulk.log 2>&1 &

# Theo dõi tiến độ
tail -f /var/log/tvpl-bulk.log
```

### Incremental (cron job hàng ngày trên VPS)
```bash
# Thêm vào crontab của VPS (không phải container):
# Chạy 11pm VN (10pm SGT = 16:00 UTC)
0 16 * * * cd /opt/dbvntax && python3 crawl_tvpl.py --mode incremental >> /var/log/tvpl-incremental.log 2>&1
```

### Checkpoint logic trong crawl_tvpl.py
Script phải implement checkpoint để resume nếu bị ngắt giữa chừng:
```python
CHECKPOINT_FILE = "/tmp/tvpl_bulk_checkpoint.json"

# Load checkpoint khi start
checkpoint = load_checkpoint()  # {"last_page": 150, "total_inserted": 2987}
start_page = checkpoint.get("last_page", 1)

# Save checkpoint mỗi 50 trang
if page % 50 == 0:
    save_checkpoint({"last_page": page, "total_inserted": total_inserted})

# Dùng --resume flag để tiếp tục từ checkpoint
# python3 crawl_tvpl.py --mode bulk --resume
```

### Rate limiting & retry
```python
DELAY_BETWEEN_PAGES = 0.7   # giây, lịch sự với TVPL
MAX_RETRIES = 3
RETRY_WAIT = 30             # giây khi bị 429/503

# Re-login nếu session expire (nhận redirect về trang login)
def is_session_expired(response):
    return 'login.aspx' in response.url or response.status_code in [401, 403]
```

---

## Notes cho Claude Code

- **Không cần Playwright/Selenium** — TVPL render server-side, `requests` là đủ
- **psycopg2 sync** (không async) cho crawl_tvpl.py — đơn giản hơn, chạy standalone
- **DATABASE_URL env var** — script đọc từ env, fallback hardcode cho VPS
- **Login session expire** — kiểm tra redirect về login page sau mỗi request, re-login tự động
- **Delay** 0.7s giữa các trang listing để không bị ban IP
- **Checkpoint** — save mỗi 50 trang vào `/tmp/tvpl_bulk_checkpoint.json`
- **taxonomy endpoint** phải đặt TRƯỚC `@app.get("/api/cong_van/{cv_id}")` trong main.py
- **`--dry-run --limit 20`** để test trước khi chạy bulk thật
