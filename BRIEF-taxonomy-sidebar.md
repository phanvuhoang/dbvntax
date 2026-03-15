# BRIEF: Taxonomy Sidebar + Cron Crawler
**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-16  
**Priority:** High

---

## Tổng quan

3 việc cần làm:
1. **API endpoint mới** — `GET /api/cong-van/taxonomy` trả chu_de counts
2. **Backend update** — thêm `chu_de` filter vào `list_cong_van` + `/api/cong-van`
3. **Frontend** — Sidebar accordion khi tab Công Văn, flat khi tab Văn Bản
4. **Cron setup** — incremental crawl hàng ngày trên VPS

---

## Context cần biết trước khi code

### DB hiện tại
- Table `cong_van`: có column `chu_de text[]`, `sac_thue text[]`, `tinh_trang varchar(50)`
- **9,845 công văn** đã có trong DB, nguồn `luatvietnam`, từ 06/2022–03/2026
- Sắc thuế dùng codes: `QLT`, `GTGT`, `TNDN`, `TNCN`, `HOA_DON`, `FCT`, `TAI_NGUYEN_DAT`, `MON_BAI_PHI`, `XNK`, `TTDB`, `HKD`, `THUE_QT`, `GDLK`
- `SAC_THUE_MAP` trong `types.ts` có mapping code → tên hiển thị

### Taxonomy hiện tại
`taxonomy.py` có `CHU_DE_MAP` — dict mapping mỗi sắc thuế → list các chủ đề con:
```python
CHU_DE_MAP = {
    "TNDN": {
        "Chi phí được trừ": [...keywords...],
        "Ưu đãi thuế TNDN": [...],
        ...
    },
    "GTGT": {...},
    ...
}
```
`classify_chu_de(title, sac_thue_list)` → trả `list[str]` các chủ đề đã classify.

### Frontend hiện tại
- `Sidebar.tsx`: flat list, props `{selected, onSelect, dateFrom, dateTo, onDateRangeChange}`
- `api.ts`: `useCongVan(params)`, `useCategories()` đã có
- `types.ts`: `CATEGORIES` array dùng codes `CIT/VAT/PIT` (khác với DB dùng `TNDN/GTGT/TNCN`)
- `SAC_THUE_MAP` trong types.ts đã handle cả 2 kiểu code

### ⚠️ Lưu ý CATEGORIES mismatch
`CATEGORIES` trong `types.ts` dùng `CIT`, `VAT`, `PIT` nhưng DB thực tế dùng `TNDN`, `GTGT`, `TNCN`.  
`SAC_THUE_MAP` đã map cả 2 chiều.  
Taxonomy endpoint nên trả theo code DB (TNDN, GTGT...) vì đó là gì thực sự trong DB.  
Sidebar khi render cần dùng `SAC_THUE_MAP` để hiển thị tên đẹp.

---

## 1. Backend — `main.py`

### 1a. Thêm endpoint taxonomy (TRƯỚC endpoint `/api/cong_van/{cv_id}`)

```python
@app.get("/api/cong-van/taxonomy")
async def cong_van_taxonomy(
    sac_thue: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Trả chu_de counts, grouped by sac_thue.
    Chỉ trả các sac_thue + chu_de có ít nhất 1 công văn.
    
    Response:
    {
      "TNDN": [
        {"chu_de": "Chi phí được trừ", "count": 142},
        {"chu_de": "Ưu đãi thuế TNDN", "count": 87}
      ],
      "GTGT": [...],
      ...
    }
    """
    where_clause = ""
    params: dict = {}
    if sac_thue:
        where_clause = "WHERE :sac_thue = ANY(sac_thue)"
        params["sac_thue"] = sac_thue

    r = await db.execute(text(f"""
        SELECT
            st  AS sac_thue,
            cd  AS chu_de,
            COUNT(*) AS count
        FROM cong_van
        CROSS JOIN LATERAL unnest(sac_thue) AS st
        CROSS JOIN LATERAL unnest(chu_de)   AS cd
        {where_clause}
        WHERE cd IS NOT NULL AND cd != ''
        GROUP BY st, cd
        ORDER BY st, count DESC
    """), params)

    rows = r.mappings().all()
    result: dict[str, list] = {}
    for row in rows:
        st = row["sac_thue"]
        if st not in result:
            result[st] = []
        result[st].append({"chu_de": row["chu_de"], "count": row["count"]})
    return result
```

### 1b. Update endpoint `/api/cong-van` — thêm `chu_de` param

```python
@app.get("/api/cong-van")
async def cong_van_list(
    q: str = "",
    sac_thue: Optional[str] = None,
    nguon: Optional[str] = None,
    chu_de: Optional[str] = None,       # ← MỚI
    tinh_trang: Optional[str] = None,   # ← MỚI
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

## 2. Backend — `search.py`

Update function `list_cong_van`:

```python
async def list_cong_van(
    db: AsyncSession,
    q: str,
    sac_thue: str,
    nguon: str,
    limit: int,
    offset: int,
    year_from: int = None,
    year_to: int = None,
    chu_de: str = None,       # ← MỚI
    tinh_trang: str = None,   # ← MỚI
):
    where = ["1=1"]
    params = {}

    # ... (giữ nguyên các filters hiện tại) ...

    # Thêm vào sau các where hiện tại:
    if chu_de:
        where.append(":chu_de = ANY(chu_de)")
        params["chu_de"] = chu_de

    if tinh_trang:
        where.append("tinh_trang = :tinh_trang")
        params["tinh_trang"] = tinh_trang

    # Phần còn lại giữ nguyên
```

---

## 3. Frontend

### 3a. `frontend/src/types.ts` — thêm types mới

Thêm vào cuối file:
```typescript
export interface TaxonomyItem {
  chu_de: string;
  count: number;
}

// key = sac_thue code (TNDN, GTGT, ...)
export type CongVanTaxonomy = Record<string, TaxonomyItem[]>;
```

### 3b. `frontend/src/api.ts` — thêm hook + update useCongVan

**Thêm import type:**
```typescript
import type {
  // ... existing ...
  CongVanTaxonomy,   // ← thêm
} from './types';
```

**Update CongVanParams:**
```typescript
export interface CongVanParams {
  q?: string;
  sac_thue?: string;
  chu_de?: string;       // ← MỚI
  tinh_trang?: string;   // ← MỚI
  year_from?: number;
  year_to?: number;
  limit?: number;
  offset?: number;
}
```

**Update buildCongVanURL:**
```typescript
function buildCongVanURL(params: CongVanParams): string {
  const p = new URLSearchParams();
  if (params.q) p.set('q', params.q);
  if (params.sac_thue) p.set('sac_thue', params.sac_thue);
  if (params.chu_de) p.set('chu_de', params.chu_de);           // ← MỚI
  if (params.tinh_trang) p.set('tinh_trang', params.tinh_trang); // ← MỚI
  if (params.year_from) p.set('year_from', String(params.year_from));
  if (params.year_to) p.set('year_to', String(params.year_to));
  p.set('limit', String(params.limit ?? 20));
  p.set('offset', String(params.offset ?? 0));
  return `/api/cong-van?${p}`;
}
```

**Thêm hook taxonomy:**
```typescript
export function useCongVanTaxonomy(sacThue?: string) {
  const url = sacThue
    ? `/api/cong-van/taxonomy?sac_thue=${encodeURIComponent(sacThue)}`
    : '/api/cong-van/taxonomy';
  return useQuery<CongVanTaxonomy>({
    queryKey: ['cong-van-taxonomy', sacThue ?? ''],
    queryFn: () => fetchJSON<CongVanTaxonomy>(url),
    staleTime: 5 * 60 * 1000,
  });
}
```

### 3c. `frontend/src/components/Sidebar.tsx` — accordion mode

**Full rewrite:**

```tsx
import { useState } from 'react';
import { useCategories, useCongVanTaxonomy } from '../api';
import { CATEGORIES, SAC_THUE_MAP } from '../types';

// Mapping từ CATEGORIES codes (CIT/VAT) sang DB codes (TNDN/GTGT)
// để link taxonomy
const CATEGORY_TO_DB: Record<string, string> = {
  CIT:     'TNDN',
  VAT:     'GTGT',
  PIT:     'TNCN',
  HDDT:    'HOA_DON',
  SCT:     'TTDB',
  TP:      'GDLK',
  QLT:     'QLT',
  FCT:     'FCT',
  HKD:     'HKD',
  THUE_QT: 'THUE_QT',
};

// Và ngược lại (DB code → display name đẹp)
const DB_TO_NAME: Record<string, string> = {
  TNDN:           'Thuế TNDN',
  GTGT:           'Thuế GTGT',
  TNCN:           'Thuế TNCN',
  HOA_DON:        'Hóa đơn',
  TTDB:           'Thuế TTĐB',
  GDLK:           'Giao dịch LK',
  QLT:            'Quản lý thuế',
  FCT:            'Thuế nhà thầu',
  HKD:            'Hộ kinh doanh',
  THUE_QT:        'Thuế Quốc tế',
  XNK:            'Xuất nhập khẩu',
  TAI_NGUYEN_DAT: 'Tài nguyên/Đất',
  MON_BAI_PHI:    'Môn bài/Phí',
};

interface Props {
  selected: string;
  onSelect: (code: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateRangeChange: (from: string, to: string) => void;
  tab: 'vanban' | 'congvan';             // ← MỚI
  selectedChuDe?: string;                // ← MỚI
  onChuDeSelect?: (chuDe: string) => void; // ← MỚI
}

export default function Sidebar({
  selected, onSelect,
  dateFrom, dateTo, onDateRangeChange,
  tab,
  selectedChuDe = '',
  onChuDeSelect,
}: Props) {
  const { data: apiCategories } = useCategories();
  const { data: taxonomy } = useCongVanTaxonomy(); // load toàn bộ taxonomy 1 lần
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const categories = apiCategories?.length
    ? apiCategories.map((c) => ({
        ...c,
        color: CATEGORIES.find((s) => s.code === c.code)?.color || 'gray',
      }))
    : CATEGORIES.map((c) => ({ ...c, count: 0 }));

  const toggleExpand = (code: string) => {
    setExpanded((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  // Lấy DB code từ category code
  const getDbCode = (catCode: string) => CATEGORY_TO_DB[catCode] ?? catCode;

  return (
    <aside className="w-full h-full bg-white border-r border-gray-200 overflow-y-auto">
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-3 pb-2">
        Sắc thuế
      </h3>

      {/* Tất cả */}
      <button
        onClick={() => { onSelect(''); onChuDeSelect?.(''); }}
        className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
          ${!selected ? 'bg-primary-light text-primary font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
      >
        <span>Tất cả</span>
      </button>

      {tab === 'vanban' ? (
        /* ── FLAT MODE (tab Văn Bản) — giữ nguyên UI cũ ── */
        categories.map((cat) => (
          <button
            key={cat.code}
            onClick={() => onSelect(cat.code === selected ? '' : cat.code)}
            className={`w-full flex justify-between items-center px-3 py-1.5 text-sm transition
              ${cat.code === selected
                ? 'bg-primary-light text-primary font-semibold'
                : 'text-gray-600 hover:bg-gray-50'}`}
          >
            <span>{cat.name}</span>
            {cat.count > 0 && (
              <span className={`text-[11px] rounded-full px-1.5 min-w-[20px] text-center
                ${cat.code === selected ? 'bg-primary text-white' : 'bg-gray-100 text-gray-500'}`}>
                {cat.count}
              </span>
            )}
          </button>
        ))
      ) : (
        /* ── ACCORDION MODE (tab Công Văn) ── */
        <>
          {/* Hiện các sắc thuế CÓ trong taxonomy (DB codes) */}
          {Object.entries(taxonomy ?? {})
            .sort(([, a], [, b]) => {
              // Sort theo tổng count
              const sumA = a.reduce((s, i) => s + i.count, 0);
              const sumB = b.reduce((s, i) => s + i.count, 0);
              return sumB - sumA;
            })
            .map(([dbCode, items]) => {
              const isSelected = selected === dbCode;
              const isExpanded = expanded[dbCode];
              const totalCount = items.reduce((s, i) => s + i.count, 0);
              const displayName = DB_TO_NAME[dbCode] ?? SAC_THUE_MAP[dbCode] ?? dbCode;

              return (
                <div key={dbCode}>
                  {/* Header sắc thuế */}
                  <div className="flex items-center">
                    {/* Click tên → filter theo sắc thuế, reset chu_de */}
                    <button
                      onClick={() => {
                        onSelect(isSelected && !selectedChuDe ? '' : dbCode);
                        onChuDeSelect?.('');
                      }}
                      className={`flex-1 flex justify-between items-center px-3 py-1.5 text-sm transition text-left
                        ${isSelected
                          ? 'bg-primary-light text-primary font-semibold'
                          : 'text-gray-600 hover:bg-gray-50'}`}
                    >
                      <span>{displayName}</span>
                      {totalCount > 0 && (
                        <span className={`text-[11px] rounded-full px-1.5 min-w-[20px] text-center mr-1
                          ${isSelected ? 'bg-primary text-white' : 'bg-gray-100 text-gray-500'}`}>
                          {totalCount}
                        </span>
                      )}
                    </button>

                    {/* Nút expand/collapse */}
                    <button
                      onClick={() => toggleExpand(dbCode)}
                      className="px-2 py-1.5 text-gray-400 hover:text-primary transition flex-shrink-0"
                      aria-label={isExpanded ? 'Thu gọn' : 'Mở rộng'}
                    >
                      <span className={`text-[10px] inline-block transition-transform duration-150
                        ${isExpanded ? 'rotate-90' : ''}`}>
                        ▶
                      </span>
                    </button>
                  </div>

                  {/* Chu_de items — chỉ hiện khi expanded */}
                  {isExpanded && (
                    <div className="border-l-2 border-primary-light ml-3">
                      {/* "Tất cả" trong sắc thuế này */}
                      <button
                        onClick={() => { onSelect(dbCode); onChuDeSelect?.(''); }}
                        className={`w-full text-left px-3 py-1 text-xs transition
                          ${isSelected && !selectedChuDe
                            ? 'text-primary font-semibold'
                            : 'text-gray-500 hover:text-primary hover:bg-gray-50'}`}
                      >
                        — Tất cả
                      </button>

                      {items.slice(0, 12).map((item) => (
                        <button
                          key={item.chu_de}
                          onClick={() => {
                            onSelect(dbCode);
                            onChuDeSelect?.(item.chu_de);
                          }}
                          className={`w-full flex justify-between items-center px-3 py-1 text-xs transition
                            ${selectedChuDe === item.chu_de && isSelected
                              ? 'text-primary font-semibold bg-primary-light'
                              : 'text-gray-500 hover:text-primary hover:bg-gray-50'}`}
                        >
                          <span className="truncate pr-1">{item.chu_de}</span>
                          <span className="text-[10px] text-gray-400 flex-shrink-0">{item.count}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
        </>
      )}

      {/* Giai đoạn ban hành — giữ nguyên */}
      <h3 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-3 pt-4 pb-2">
        Giai đoạn ban hành
      </h3>
      <div className="px-3 pb-3 space-y-2">
        <div>
          <label className="text-[10px] text-gray-400 uppercase tracking-wide block mb-1">Từ ngày</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => onDateRangeChange(e.target.value, dateTo)}
            className="w-full px-2 py-1 border border-gray-200 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
          />
        </div>
        <div>
          <label className="text-[10px] text-gray-400 uppercase tracking-wide block mb-1">Đến ngày</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => onDateRangeChange(dateFrom, e.target.value)}
            className="w-full px-2 py-1 border border-gray-200 rounded bg-white text-xs text-gray-600 focus:border-primary focus:outline-none"
          />
        </div>
        {(dateFrom || dateTo) && (
          <button
            onClick={() => onDateRangeChange('', '')}
            className="w-full text-xs text-gray-400 hover:text-primary py-1 border border-gray-200 rounded hover:border-primary transition"
          >
            ↺ Reset bộ lọc
          </button>
        )}
      </div>
    </aside>
  );
}
```

### 3d. `frontend/src/pages/HomePage.tsx` — thêm state + pass props

```tsx
// Thêm state
const [selectedChuDe, setSelectedChuDe] = useState('');

// Update useCongVan — thêm chu_de
const congVanResult = useCongVan({
  q: query,
  sac_thue: category,
  chu_de: selectedChuDe,   // ← MỚI
  year_from: dateFrom ? parseInt(dateFrom.split('-')[0]) : undefined,
  year_to: dateTo ? parseInt(dateTo.split('-')[0]) : undefined,
  limit: LIMIT,
  offset: (page - 1) * LIMIT,
});

// Update handleTabChange — reset selectedChuDe
const handleTabChange = useCallback((t: Tab) => {
  setTab(t); setPage(1); setSelectedItem(null);
  setSelectedChuDe('');   // ← MỚI
}, []);

// Update handleCategorySelect — reset selectedChuDe
const handleCategorySelect = useCallback((code: string) => {
  setCategory(code); setPage(1); setSelectedItem(null);
  setSelectedChuDe('');   // ← MỚI
}, []);

// Update <Sidebar> usage — thêm props mới
<Sidebar
  selected={category}
  onSelect={(code) => { handleCategorySelect(code); setSidebarOpen(false); }}
  dateFrom={dateFrom}
  dateTo={dateTo}
  onDateRangeChange={handleDateRangeChange}
  tab={tab}                                // ← MỚI
  selectedChuDe={selectedChuDe}           // ← MỚI
  onChuDeSelect={(cd) => {                // ← MỚI
    setSelectedChuDe(cd);
    setPage(1);
    setSelectedItem(null);
    setSidebarOpen(false);
  }}
/>
```

---

## 4. Cron Crawler — setup trên VPS

### Script đã có: `/opt/dbvntax/crawl_luatvietnam.py`

Script hỗ trợ `--mode incremental` (dừng khi gặp CV đã có trong DB).

### Crontab entry (thêm vào VPS crontab)

```bash
# Chạy incremental mỗi ngày lúc 11pm VN (16:00 UTC)
0 16 * * * cd /opt/dbvntax && python3 -u crawl_luatvietnam.py --mode incremental >> /var/log/tvpl-incremental.log 2>&1
```

**Tuy nhiên** — `crawl_luatvietnam.py` hiện chưa có `--mode` flag. Script hiện tại luôn chạy full bulk và dừng khi detect loop.

### Cần thêm vào `crawl_luatvietnam.py` — mode incremental

Thêm logic này vào `main()`:

```python
parser.add_argument("--mode", choices=["bulk", "incremental"], default="bulk",
                    help="bulk: crawl toàn bộ đến loop; incremental: dừng khi gặp CV đã có")

# Trong vòng lặp while, sau khi parse items, nếu mode==incremental:
if args.mode == "incremental":
    # Check xem có item nào đã tồn tại không
    new_items = []
    found_existing = False
    for item in items:
        if link_exists(conn, item["link_nguon"]):
            found_existing = True
            break
        new_items.append(item)
    
    if new_items:
        ins, skip = insert_batch(conn, new_items, dry_run=args.dry_run)
        total_inserted += ins
        total_skipped += skip
        print(f"Page {page:5d}: +{ins:3d} inserted | last_date={new_items[-1]['ngay_ban_hanh']}")
    
    if found_existing:
        print(f"Page {page}: found existing CV — incremental done.")
        break
else:
    # bulk mode — giữ nguyên logic cũ
    ins, skip = insert_batch(conn, items, dry_run=args.dry_run)
    ...
```

**Sau khi thêm mode:** Setup cron:
```bash
# SSH vào VPS 72.62.197.183 và chạy:
(crontab -l 2>/dev/null; echo "0 16 * * * cd /opt/dbvntax && python3 -u crawl_luatvietnam.py --mode incremental >> /var/log/tvpl-incremental.log 2>&1") | crontab -
```

---

## Thứ tự implement

1. **`search.py`** — update `list_cong_van` (thêm chu_de + tinh_trang filter) — 5 phút
2. **`main.py`** — thêm taxonomy endpoint + update cong-van endpoint — 10 phút
3. **`crawl_luatvietnam.py`** — thêm `--mode` flag — 10 phút
4. **`frontend/src/types.ts`** — thêm TaxonomyItem, CongVanTaxonomy — 2 phút
5. **`frontend/src/api.ts`** — update CongVanParams + hook taxonomy — 5 phút
6. **`frontend/src/components/Sidebar.tsx`** — full rewrite với accordion — 20 phút
7. **`frontend/src/pages/HomePage.tsx`** — thêm state + update props — 10 phút
8. **Deploy** — push GitHub → Coolify auto-deploy
9. **Cron** — SSH vào VPS, thêm crontab entry

## Files cần thay đổi

| File | Action |
|------|--------|
| `search.py` | Sửa: thêm `chu_de`, `tinh_trang` params vào `list_cong_van` |
| `main.py` | Sửa: thêm `/api/cong-van/taxonomy` endpoint; update `/api/cong-van` |
| `crawl_luatvietnam.py` | Sửa: thêm `--mode bulk/incremental` flag |
| `frontend/src/types.ts` | Sửa: thêm `TaxonomyItem`, `CongVanTaxonomy` |
| `frontend/src/api.ts` | Sửa: update `CongVanParams`, `buildCongVanURL`, thêm `useCongVanTaxonomy` |
| `frontend/src/components/Sidebar.tsx` | Rewrite: accordion khi tab congvan |
| `frontend/src/pages/HomePage.tsx` | Sửa: thêm `selectedChuDe` state, update Sidebar props |

## Notes cho Claude Code

- `taxonomy endpoint` phải đặt **TRƯỚC** `@app.get("/api/cong_van/{cv_id}")` — FastAPI match theo thứ tự
- `CATEGORY_TO_DB` mapping cần vì frontend dùng `CIT/VAT/PIT` nhưng DB dùng `TNDN/GTGT/TNCN`
- Sidebar accordion chỉ load taxonomy 1 lần (không refetch khi expand), `staleTime: 5min`
- `crawl_luatvietnam.py` đang ở `/opt/dbvntax/` trên VPS `72.62.197.183`, không trong repo
- Sau khi Claude Code implement xong, cron cần setup thủ công trên VPS (không phải trong code)
