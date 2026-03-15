# CLAUDE.md — UI Fixes Sprint 4

## Tổng quan
5 thay đổi UI cho app dbvntax.gpt4vn.com. Tất cả chỉ là frontend (React/TypeScript/Tailwind).

---

## Fix 1: Tóm tắt dạng expandable (DocDetail.tsx)

**File:** `frontend/src/components/DocDetail.tsx`

Tìm đoạn render `tom_tat`:
```tsx
{(doc as Document).tom_tat && (
  <div className="bg-gray-50 border-l-[3px] border-primary p-3 rounded text-sm text-gray-600 leading-relaxed mb-4">
    <strong className="text-gray-700">Tóm tắt:</strong> {(doc as Document).tom_tat}
  </div>
)}
```

Thay bằng expandable collapsible box — mặc định **collapsed** (chỉ hiện 2 dòng), click để expand. Style tương tự `HieuLucDetail` (có header clickable, arrow toggle):

```tsx
{(doc as Document).tom_tat && (
  <TomTatBox text={(doc as Document).tom_tat!} />
)}
```

Tạo component `TomTatBox` inline hoặc trong file riêng `TomTatBox.tsx`:
```tsx
function TomTatBox({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded mb-4 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition text-left"
      >
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">📝 Tóm tắt</span>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 py-2 text-sm text-gray-600 leading-relaxed">
          {text}
        </div>
      )}
    </div>
  );
}
```

---

## Fix 2: Sidebar DANH_MUC resizable (đã có Divider nhưng sidebar chưa resize được)

**File:** `frontend/src/pages/HomePage.tsx`

Sidebar hiện tại dùng `style={{ width: sidebarW }}` nhưng trên mobile bị override bởi `fixed` + `translate`. Trên desktop (md+), sidebar đã có `sidebarW` state và `handleSidebarResize`. Vấn đề là `Divider` component chỉ xuất hiện sau sidebar nhưng sidebar width trên desktop chưa được apply đúng vì thiếu `flex-shrink-0`.

Sửa div wrap sidebar:
```tsx
<div
  className={`${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 transition-transform duration-200 fixed md:static z-40 md:z-auto h-full flex-shrink-0`}
  style={{ width: sidebarW }}
>
```

Thêm `flex-shrink-0` vào className. Đảm bảo `Divider` sau sidebar có thể drag để thay đổi `sidebarW`.

---

## Fix 3: Bỏ hover tooltip trên HieuLucBadge trong danh sách (DocCard.tsx / HieuLucBadge.tsx)

**Yêu cầu:** Badge hiệu lực trong danh sách văn bản (DocCard) không cần hover tooltip. Chỉ giữ tooltip trong DocDetail.

**Cách làm:** Thêm prop `noTooltip` vào `HieuLucBadge`:

**File:** `frontend/src/components/HieuLucBadge.tsx`

```tsx
export default function HieuLucBadge({ doc, noTooltip }: { doc: Document; noTooltip?: boolean }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const status = getHieuLucStatus(doc);
  const config = STATUS_CONFIG[status];
  const summary = !noTooltip ? doc.hieu_luc_index?.tom_tat_hieu_luc : undefined;

  return (
    <span
      className={`relative inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}
      onMouseEnter={() => summary && setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {config.label}
      {showTooltip && summary && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2 bg-gray-900 text-white text-xs rounded shadow-lg z-50 whitespace-normal">
          {summary}
        </span>
      )}
    </span>
  );
}
```

**File:** `frontend/src/components/DocCard.tsx` — Thêm `noTooltip` khi dùng HieuLucBadge:
```tsx
<HieuLucBadge doc={doc} noTooltip />
```

---

## Fix 4: Thay filter loại VB + box "tại ngày" → filter giai đoạn ban hành

**Yêu cầu:**
- Bỏ hoàn toàn: filter theo loại văn bản (Luật, Nghị định...) và box "Tại ngày" trong sidebar
- Thêm vào: box lọc **giai đoạn ban hành** (từ ngày → đến ngày) + nút Reset
- Filter này áp dụng cho cả tab Văn bản và Công văn (dùng `year_from`/`year_to` hoặc date range)

### 4a. Sidebar.tsx — Xóa section "Loại văn bản" và "Tại ngày", thêm "Giai đoạn ban hành"

**File:** `frontend/src/components/Sidebar.tsx`

Xóa:
- Toàn bộ section `Loại văn bản` (h3 + map LOAI_OPTIONS)
- Toàn bộ section `Tại ngày` (h3 + input date + button xóa)
- Toàn bộ section `Hiệu lực` (h3 + radio buttons)
- Props: `loai`, `onLoaiChange`, `hlFilter`, `onHlChange`, `dateAt`, `onDateAtChange`

Thêm section mới **"Giai đoạn ban hành"** (sau danh mục sắc thuế):
```tsx
interface Props {
  selected: string;
  onSelect: (code: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateRangeChange: (from: string, to: string) => void;
}

// Trong JSX, sau danh mục:
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
```

### 4b. HomePage.tsx — Cập nhật state và API calls

**File:** `frontend/src/pages/HomePage.tsx`

Xóa states: `loai`, `hlFilter`, `dateAt`

Thêm states:
```tsx
const [dateFrom, setDateFrom] = useState('');
const [dateTo, setDateTo] = useState('');
```

Thêm handler:
```tsx
const handleDateRangeChange = useCallback((from: string, to: string) => {
  setDateFrom(from); setDateTo(to); setPage(1);
}, []);
```

Cập nhật `useSearch` params — dùng `year_from`/`year_to` (extract năm từ date) hoặc dùng filter bằng `ngay_ban_hanh`. Backend hiện có `year_from`/`year_to` trong `build_filters`. Dùng:
```tsx
year_from: dateFrom ? parseInt(dateFrom.split('-')[0]) : undefined,
year_to: dateTo ? parseInt(dateTo.split('-')[0]) : undefined,
```

Cập nhật `useCongVan` params tương tự — thêm `year_from`/`year_to` vào API call công văn.

**Lưu ý:** Backend `useCongVan` hiện chưa support `year_from`/`year_to`. Cần thêm vào `list_cong_van` trong `search.py`:

```python
if filters.get("year_from"):
    where.append("EXTRACT(YEAR FROM ngay_ban_hanh) >= :year_from")
    params["year_from"] = filters["year_from"]
if filters.get("year_to"):
    where.append("EXTRACT(YEAR FROM ngay_ban_hanh) <= :year_to")
    params["year_to"] = filters["year_to"]
```

Và endpoint `/api/cong-van` trong `main.py` nhận thêm params `year_from`, `year_to`.

Cập nhật Sidebar usage trong HomePage — bỏ props cũ, dùng props mới:
```tsx
<Sidebar
  selected={category}
  onSelect={(code) => { handleCategorySelect(code); setSidebarOpen(false); }}
  dateFrom={dateFrom}
  dateTo={dateTo}
  onDateRangeChange={handleDateRangeChange}
/>
```

### 4c. FilterPanel.tsx — Không còn dùng, có thể xóa file

---

## Fix 5: Search box — verify và fix nếu chưa hoạt động

**Kiểm tra:** Search box dùng `debounce 300ms` rồi gọi `onChange` → set `query` trong HomePage → trigger `useSearch`. Sau khi deploy `unaccent` fix (commit ebcaf3e), search đã hoạt động với tiếng Việt có dấu và không dấu.

**Nếu search vẫn không có kết quả:**

Verify API trực tiếp:
```bash
curl "https://dbvntax.gpt4vn.com/api/search?q=TNDN&limit=5" | python3 -m json.tool | head -20
```

Nếu API trả kết quả nhưng UI không hiển thị, kiểm tra `api.ts` — hàm `useSearch` và mapping response. Response format là `{ total, results }` cho search, nhưng `{ total, items }` cho documents list. Đảm bảo HomePage đọc đúng field:
```tsx
const items = tab === 'vanban'
  ? (searchResult.data?.results ?? [])   // search endpoint dùng "results"
  : (congVanResult.data?.items ?? []);   // cong-van endpoint dùng "items"
```

Nếu có mismatch → fix trong `api.ts` hoặc `HomePage.tsx`.

---

## Checklist sau khi implement

```bash
# Test search tiếng Việt có dấu / không dấu
curl "https://dbvntax.gpt4vn.com/api/search?q=thuế+TNDN&limit=3" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"
curl "https://dbvntax.gpt4vn.com/api/search?q=thue+TNDN&limit=3" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"

# Test date range filter
curl "https://dbvntax.gpt4vn.com/api/search?year_from=2024&year_to=2026&limit=3" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"
curl "https://dbvntax.gpt4vn.com/api/cong-van?year_from=2024&limit=3" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"
```

Tất cả phải > 0.

---

## Commit message
`feat: UI sprint 4 — expandable tom_tat, date range filter, remove loai/dateAt filters, fix sidebar resize, no tooltip in DocCard`
