# CLAUDE.md — dbvntax Frontend Build Instructions

## Mục tiêu

Build frontend React cho **dbvntax.gpt4vn.com** — ứng dụng tra cứu văn bản pháp luật & công văn thuế Việt Nam.

Backend FastAPI đã có sẵn (`main.py`). Nhiệm vụ của bạn: build toàn bộ frontend.

---

## Tech Stack

- **React 18 + TypeScript**
- **Tailwind CSS v3**
- **Vite** (build tool)
- **React Query** (data fetching + caching)
- **React Router v6** (routing)
- **Primary color:** `#028a39` — dùng cho TẤT CẢ accent, button, link, badge active. KHÔNG dùng blue/indigo mặc định.

---

## Cấu trúc dự án

```
/
├── main.py              ← FastAPI backend (ĐÃ CÓ, không sửa)
├── requirements.txt     ← Backend deps (ĐÃ CÓ)
├── taxonomy.py          ← Tax classification (ĐÃ CÓ)
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── package.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── types.ts
│       ├── api.ts
│       ├── components/
│       │   ├── Sidebar.tsx
│       │   ├── DocList.tsx
│       │   ├── DocCard.tsx
│       │   ├── DocDetail.tsx
│       │   ├── HieuLucBadge.tsx      ← QUAN TRỌNG
│       │   ├── HieuLucDetail.tsx     ← QUAN TRỌNG
│       │   ├── SearchBar.tsx
│       │   └── FilterPanel.tsx
│       └── pages/
│           ├── HomePage.tsx
│           └── NotFound.tsx
└── Dockerfile           ← Update để serve frontend build
```

---

## Database Schema

```sql
documents (
  id              serial primary key,
  so_hieu         varchar,       -- "126/2020/NĐ-CP"
  ten             text,          -- tên đầy đủ
  loai            varchar,       -- TT | ND | LUAT | QD | NQ | VBHN | CV | KHAC
  ngay_ban_hanh   date,
  tinh_trang      varchar,       -- "con_hieu_luc" | "het_hieu_luc" | text mô tả
  hl              integer,       -- 1=còn HL, 0=hết HL
  sac_thue        varchar,       -- QLT | CIT | VAT | HDDT | PIT | SCT | FCT | TP | HKD
  category_name   varchar,       -- "Quản lý thuế" | "Thuế TNDN" | ...
  github_path     varchar unique,-- path trong vn-tax-corpus repo
  p2              varchar,
  p3              varchar,
  doc_type        varchar,
  importance      integer,
  import_date     timestamp,
  keywords        varchar[],
  hieu_luc_index  jsonb          -- AI-extracted, xem cấu trúc dưới
)
```

### hieu_luc_index (jsonb) — cấu trúc quan trọng:

```typescript
interface HieuLucIndex {
  hieu_luc: Array<{
    pham_vi: string;       // "Toàn bộ" hoặc tên điều khoản cụ thể
    tu_ngay: string | null; // "2026-01-01"
    den_ngay: string | null; // null = còn hiệu lực đến nay
    ghi_chu: string;       // ghi chú chuyển tiếp, thay thế
  }>;
  van_ban_thay_the: string[];  // số hiệu bị thay thế hoàn toàn
  van_ban_sua_doi: string[];   // số hiệu bị sửa đổi một phần
  tom_tat_hieu_luc: string;    // 1-2 câu tóm tắt
}
```

---

## API Endpoints (main.py)

Cập nhật `main.py` để thêm các endpoints sau (nếu chưa có):

```
GET  /api/documents
     ?category=CIT          -- filter by sac_thue
     &loai=TT               -- filter by loai
     &hl=1                  -- filter hiệu lực (0/1)
     &search=keyword        -- full-text search ten + so_hieu
     &date_at=2023-07-01    -- filter: tu_ngay <= date AND (den_ngay IS NULL OR den_ngay >= date)
     &page=1&limit=20
     → { items: Document[], total: number, page: number }

GET  /api/documents/{id}    → Document (full, với hieu_luc_index)

GET  /api/categories        → { code, name, count }[]

GET  /api/cong-van
     ?category=CIT&page=1&limit=20&search=...
     → { items: CongVan[], total: number }
```

Lưu ý: `date_at` filter cần query vào `hieu_luc_index->'hieu_luc'` jsonb array.

---

## UI Layout

```
┌────────────────────────────────────────────────────────┐
│  [VNTaxDB logo]         [Search bar]          [?]      │  ← Header
├──────────┬─────────────────────────────────────────────┤
│          │  [Văn bản]  [Công văn]    sort: Mới nhất ▼ │  ← Tabs + sort
│ Sidebar  ├─────────────────────────────────────────────┤
│          │                                             │
│ Danh mục │   [DocCard] [DocCard] [DocCard]             │
│ ─────── │   [DocCard] [DocCard] [DocCard]             │
│ □ Tất cả │   ...                                       │
│ □ QLT 86 │                                             │
│ □ CIT 37 │                          [Pagination]       │
│ □ VAT 32 ├─────────────────────────────────────────────┤
│ □ ...    │                                             │
│          │   ← DocDetail panel (slide-in khi click)   │
│ Loại VB  │                                             │
│ ─────── │                                             │
│ □ Luật   │                                             │
│ □ NĐ     │                                             │
│ □ TT     │                                             │
│ □ VBHN   │                                             │
│          │                                             │
│ Hiệu lực │                                             │
│ ─────── │                                             │
│ ● Tất cả │                                             │
│ ○ Còn HL │                                             │
│ ○ Hết HL │                                             │
│          │                                             │
│ Tại ngày:│                                             │
│ [date 📅]│                                             │
└──────────┴─────────────────────────────────────────────┘
```

---

## DocCard Component

```tsx
// Mỗi card trong danh sách
<div className="doc-card">
  <div className="flex justify-between items-start">
    <span className="so-hieu text-[#028a39] font-semibold">{doc.so_hieu}</span>
    <LoaiBadge loai={doc.loai} />   {/* TT | NĐ | LUAT | CV... */}
  </div>
  
  <p className="ten line-clamp-2">{doc.ten}</p>
  
  <div className="flex items-center gap-2 mt-2">
    <span className="ngay text-gray-500 text-sm">
      {formatDate(doc.ngay_ban_hanh)}  {/* DD/MM/YYYY */}
    </span>
    <HieuLucBadge doc={doc} />   {/* ← QUAN TRỌNG */}
  </div>
</div>
```

---

## HieuLucBadge Component — ⚠️ QUAN TRỌNG

```tsx
// 3 cấp độ hiển thị:

// 1. Xác định trạng thái
const getStatus = (doc: Document) => {
  if (!doc.hieu_luc_index) {
    return doc.hl === 1 ? 'active' : 'inactive';
  }
  const entries = doc.hieu_luc_index.hieu_luc;
  const hasExpired = entries.some(e => e.den_ngay !== null);
  const allExpired = entries.every(e => e.den_ngay !== null);
  if (allExpired || doc.hl === 0) return 'inactive';
  if (hasExpired) return 'partial';  // một phần hết HL
  return 'active';
};

// 2. Badge màu
// 'active'   → bg-green-100 text-green-800  "Còn hiệu lực"
// 'inactive' → bg-red-100   text-red-800    "Hết hiệu lực"
// 'partial'  → bg-yellow-100 text-yellow-800 "Hiệu lực một phần"

// 3. Tooltip khi hover (nếu có hieu_luc_index)
// Hiển thị: doc.hieu_luc_index.tom_tat_hieu_luc
```

---

## DocDetail Panel — Section Hiệu lực

```tsx
// Slide-in panel bên phải khi click card
// Width: 480px trên desktop, full-width trên mobile

<div className="doc-detail-panel">
  {/* Header */}
  <div className="header">
    <h2>{doc.so_hieu}</h2>
    <HieuLucBadge doc={doc} />
    <button onClick={onClose}>✕</button>
  </div>

  <p className="ten">{doc.ten}</p>
  
  <div className="meta flex gap-4">
    <span>📅 {formatDate(doc.ngay_ban_hanh)}</span>
    <span>🏷️ {loaiLabel[doc.loai]}</span>
    <span>📂 {doc.category_name}</span>
  </div>

  {/* Hiệu lực chi tiết — chỉ render nếu có hieu_luc_index */}
  {doc.hieu_luc_index && (
    <HieuLucDetail index={doc.hieu_luc_index} />
  )}

  {/* Link xem văn bản gốc */}
  <a 
    href={`https://vntaxdoc.gpt4vn.com/docs/${doc.github_path}`}
    target="_blank"
    className="btn-primary"
  >
    📄 Xem văn bản gốc ↗
  </a>
</div>
```

---

## HieuLucDetail Component

```tsx
interface Props {
  index: HieuLucIndex;
}

export const HieuLucDetail = ({ index }: Props) => (
  <div className="hieu-luc-detail">
    <h3>⚡ Hiệu lực chi tiết</h3>
    
    {/* Tóm tắt */}
    {index.tom_tat_hieu_luc && (
      <p className="summary text-sm text-gray-600 italic mb-3">
        {index.tom_tat_hieu_luc}
      </p>
    )}
    
    {/* Bảng từng giai đoạn */}
    {index.hieu_luc.length > 0 && (
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-gray-50">
            <th>Phạm vi</th>
            <th>Từ ngày</th>
            <th>Đến ngày</th>
            <th>Ghi chú</th>
          </tr>
        </thead>
        <tbody>
          {index.hieu_luc.map((entry, i) => (
            <tr key={i} className={entry.den_ngay ? 'bg-red-50' : ''}>
              <td>{entry.pham_vi}</td>
              <td>{entry.tu_ngay ? formatDate(entry.tu_ngay) : '—'}</td>
              <td>{entry.den_ngay ? formatDate(entry.den_ngay) : 
                   <span className="text-green-600">Hiện nay</span>}</td>
              <td className="text-gray-500">{entry.ghi_chu || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )}
    
    {/* Văn bản liên quan */}
    {index.van_ban_thay_the.length > 0 && (
      <div className="mt-3">
        <span className="font-medium text-red-700">🔴 Thay thế hoàn toàn: </span>
        {index.van_ban_thay_the.join(', ')}
      </div>
    )}
    {index.van_ban_sua_doi.length > 0 && (
      <div className="mt-1">
        <span className="font-medium text-yellow-700">🟡 Sửa đổi một phần: </span>
        {index.van_ban_sua_doi.join(', ')}
      </div>
    )}
  </div>
);
```

---

## 9 Categories với màu

```typescript
export const CATEGORIES = [
  { code: 'QLT',  name: 'Quản lý thuế',       color: 'blue',   count: 86 },
  { code: 'CIT',  name: 'Thuế TNDN',           color: 'green',  count: 37 },
  { code: 'VAT',  name: 'Thuế GTGT',           color: 'teal',   count: 32 },
  { code: 'HDDT', name: 'Hóa đơn điện tử',     color: 'purple', count: 31 },
  { code: 'PIT',  name: 'Thuế TNCN',           color: 'orange', count: 41 },
  { code: 'SCT',  name: 'Thuế TTĐB',           color: 'red',    count: 22 },
  { code: 'FCT',  name: 'Thuế nhà thầu',       color: 'yellow', count: 13 },
  { code: 'TP',   name: 'Giao dịch liên kết',  color: 'indigo', count: 18 },
  { code: 'HKD',  name: 'Hộ kinh doanh',       color: 'pink',   count: 14 },
];

export const LOAI_LABELS: Record<string, string> = {
  LUAT: 'Luật', ND: 'Nghị định', TT: 'Thông tư',
  QD: 'Quyết định', NQ: 'Nghị quyết', VBHN: 'VB Hợp nhất',
  TTLT: 'Thông tư liên tịch', CV: 'Công văn', KHAC: 'Khác',
};
```

---

## Dockerfile update

Backend + Frontend serve cùng container:

```dockerfile
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend-builder /frontend/dist ./static

# main.py serve static files từ /static
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Trong `main.py`, thêm static file mounting:
```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    return FileResponse("static/index.html")
```

---

## Deploy

Sau khi build xong:
1. Push lên `github.com/phanvuhoang/dbvntax`
2. Coolify sẽ auto-redeploy từ GitHub
3. App live tại `dbvntax.gpt4vn.com`

---

## Checklist

- [ ] `frontend/` folder với Vite + React + TS + Tailwind setup
- [ ] `src/types.ts` — Document, HieuLucIndex interfaces
- [ ] `src/api.ts` — React Query hooks cho tất cả endpoints
- [ ] Sidebar với 9 categories + filters
- [ ] DocList với pagination
- [ ] DocCard với HieuLucBadge + tooltip
- [ ] DocDetail panel (slide-in)
- [ ] HieuLucDetail component (table + van_ban liên quan)
- [ ] Tab Văn bản / Công văn
- [ ] Filter "Hiệu lực tại ngày" (date picker → date_at param)
- [ ] Responsive mobile
- [ ] Dockerfile updated
- [ ] main.py updated với static file serving + /api/documents endpoint đầy đủ
