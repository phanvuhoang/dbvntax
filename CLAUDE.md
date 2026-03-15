# CLAUDE.md — dbvntax Frontend Build Brief

> **Last updated:** 2026-03-15 by ThanhAI
> **Task:** Build complete SPA frontend for VNTaxDB — cơ sở dữ liệu pháp luật thuế Việt Nam

---

## 🎯 Mục tiêu

Build frontend SPA hoàn chỉnh cho app tra cứu văn bản + công văn thuế VN.

**Backend đã sẵn sàng** — tất cả API endpoints hoạt động, DB có 159 văn bản + 93 công văn.

---

## 🗄️ Database hiện có

- **159 văn bản** (`documents` table): Luật/NĐ/TT/VBHN/QĐ — 9 categories
- **93 công văn** (`cong_van` table): hướng dẫn cụ thể từ Tổng cục Thuế
- **PostgreSQL + pgvector** on Coolify VPS

---

## 🔌 API Endpoints

### Documents (Văn bản pháp luật)

```
GET /api/documents
    ?q=keyword          -- full-text search (optional)
    &category=CIT       -- filter by sac_thue code
    &loai=TT            -- filter: TT|ND|Luat|VBHN|QD|NQ|CV
    &hl=1               -- 1=còn hiệu lực, 0=hết hiệu lực
    &year_from=2020
    &year_to=2025
    &page=1&limit=20
    → {"items": [...], "total": 159, "page": 1, "limit": 20}

GET /api/documents/{id}
    → Document object đầy đủ
```

### Categories

```
GET /api/categories
    → plain array (KHÔNG phải {items:[...]})
    → [{code, name, count}, ...]
```

### Công văn

```
GET /api/cong-van
    ?q=keyword
    &sac_thue=CIT
    &page=1&limit=20
    → {"items": [...], "total": 93}

GET /api/cong_van/{id}
    → CongVan object đầy đủ
```

### Search (unified)

```
GET /api/search
    ?q=keyword
    &type=all           -- all|documents|cong_van
    &sac_thue=CIT
    &mode=hybrid        -- hybrid|keyword|semantic
    &limit=20&offset=0
    → {"total": N, "results": [...], "q": "...", "mode": "..."}
```

### Auth

```
POST /api/auth/register  → {email, password, ho_ten}
POST /api/auth/login     → {email, password} → {token, user}
GET  /api/auth/me        → user object (Bearer token)
```

---

## 📦 Document Object Structure

```typescript
interface Document {
  id: number;
  so_hieu: string;          // "68/2026/NĐ-CP"
  ten: string;              // Tên đầy đủ
  loai: string;             // "ND"|"TT"|"Luat"|"VBHN"|"QD"|"NQ"|"CV"
  co_quan: string | null;
  ngay_ban_hanh: string | null;  // "2026-03-05"
  tinh_trang: string;       // "con_hieu_luc"|"het_hieu_luc"
  hl: number;               // 1=còn HL, 0=hết HL
  sac_thue: string[];       // ["HKD"]
  category_name: string;    // "Hộ kinh doanh"
  github_path: string;      // path in vn-tax-corpus repo
  hieu_luc_index: HieuLucIndex | null;
  snippet?: string;         // search result excerpt
}

interface HieuLucIndex {
  hieu_luc: Array<{
    pham_vi: string;
    tu_ngay: string | null;
    den_ngay: string | null;
    ghi_chu: string;
  }>;
  van_ban_thay_the: string[];   // ["NĐ 83/2013"]
  van_ban_sua_doi: string[];
  tom_tat_hieu_luc: string;
}

interface Category {
  code: string;       // "QLT"
  name: string;       // "Quản lý thuế"
  count: number;      // 26
}
```

---

## 🎨 UI Layout & Design

### Màu sắc
- **Primary:** `#028a39` (xanh lá đậm) — buttons, links, active states
- **Primary light:** `#e8f5ee` — hover bg, selected bg
- **Primary dark:** `#016b2c` — hover on primary buttons

### Layout tổng thể

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER: Logo + Tabs (Văn bản | Công văn) + Search + Auth   │
├───────────────┬─────────────────────────────────────────────┤
│               │                                             │
│   SIDEBAR     │           MAIN CONTENT                      │
│   (240px)     │                                             │
│               │  [DocCard] [DocCard] [DocCard]              │
│  Categories   │  [DocCard] [DocCard] [DocCard]              │
│  (9 items)    │                                             │
│               │  ← 1  2  3  →   (pagination)               │
│  Filters:     │                                             │
│  - Loại VB    │                                             │
│  - Hiệu lực   ├─────────────────────────────────────────────┤
│  - Năm        │  DETAIL PANEL (slide-in, 480px wide)        │
│               │  (hiện khi click DocCard)                   │
└───────────────┴─────────────────────────────────────────────┘
```

### 9 Categories (sidebar)

```typescript
const CATEGORIES = [
  { code: 'QLT',  name: 'Quản lý thuế',        icon: '⚖️' },
  { code: 'CIT',  name: 'Thuế TNDN',            icon: '🏢' },
  { code: 'VAT',  name: 'Thuế GTGT',            icon: '🧾' },
  { code: 'HDDT', name: 'Hóa đơn điện tử',      icon: '📄' },
  { code: 'PIT',  name: 'Thuế TNCN',            icon: '👤' },
  { code: 'SCT',  name: 'Thuế TTĐB',            icon: '🚗' },
  { code: 'FCT',  name: 'Thuế nhà thầu',        icon: '🌐' },
  { code: 'TP',   name: 'Giao dịch liên kết',   icon: '🔗' },
  { code: 'HKD',  name: 'Hộ kinh doanh',        icon: '🏪' },
];
```

> Lưu ý: API dùng `sac_thue` codes như `VAT`, `CIT`, `PIT`... Trong DB các code là: `QLT`, `VAT`, `CIT`, `HDDT`, `PIT`, `SCT`, `FCT`, `TP`, `HKD`

### DocCard component

```
┌────────────────────────────────────────────┐
│ [ND] NĐ 68/2026/NĐ-CP          🟢 Còn HL  │
│ Chính sách thuế và quản lý thuế đối với    │
│ hộ kinh doanh, cá nhân kinh doanh          │
│ 📅 05/03/2026  •  Hộ kinh doanh            │
└────────────────────────────────────────────┘
```

- `so_hieu` bold, màu `#028a39`
- Badge loại: `ND`/`TT`/`Luật`/`VBHN`/`QĐ` — màu xám nhạt
- Tên: 2 dòng, truncate
- Ngày: format `DD/MM/YYYY`
- HieuLucBadge (xem dưới)

### HieuLucBadge

```typescript
// Logic xác định badge:
function getHieuLucBadge(doc: Document) {
  if (doc.hl === 0) 
    return { text: 'Hết hiệu lực', color: 'red' };
  
  if (doc.hieu_luc_index?.hieu_luc?.some(h => h.den_ngay !== null))
    return { text: 'Hiệu lực một phần', color: 'yellow' };
  
  return { text: 'Còn hiệu lực', color: 'green' };
}
```

Hover tooltip: hiển thị `hieu_luc_index.tom_tat_hieu_luc`

### DocDetail Panel (slide-in từ phải, 480px)

```
┌─── [X] ────────────────────────────────────┐
│ [ND] NĐ 68/2026/NĐ-CP     🟢 Còn hiệu lực│
│                                             │
│ Chính sách thuế và quản lý thuế đối        │
│ với hộ kinh doanh, cá nhân kinh doanh      │
│                                             │
│ 📅 05/03/2026  |  🏛️ Chính phủ             │
│ 🏷️ Hộ kinh doanh  |  📋 NĐ                │
│                                             │
│ ── Hiệu lực ────────────────────────────── │
│ "Hiệu lực từ 05/03/2026, thay thế..."     │
│                                             │
│ Phạm vi    | Từ ngày    | Đến ngày         │
│ Toàn bộ   | 05/03/2026 | —                │
│                                             │
│ 🔴 Thay thế: NĐ 132/2020/NĐ-CP            │
│ 🟡 Sửa đổi: NĐ 20/2025/NĐ-CP             │
│                                             │
│ [📄 Xem văn bản gốc ↗]                    │
└─────────────────────────────────────────────┘
```

Link xem gốc: `https://vntaxdoc.gpt4vn.com/docs/{github_path}`

---

## 🗂️ Sidebar Filters

### Tab Văn bản
- **Loại văn bản** (checkbox group): Luật | NĐ | TT | VBHN | QĐ | NQ
- **Hiệu lực** (radio): Tất cả | Còn hiệu lực | Hết hiệu lực
- **Năm ban hành** (range): From — To (input số)

### Tab Công văn
- **Sắc thuế** (same 9 categories)
- **Năm ban hành** range

---

## 🔍 Search UX

- Search box ở header, placeholder: "Tìm văn bản, số hiệu..."
- Khi nhập → gọi `/api/documents?q=...` hoặc `/api/cong-van?q=...` tùy tab
- Debounce 300ms
- Khi có keyword → highlight matches trong ten/so_hieu

---

## 📑 Tab: Công văn

Layout tương tự tab Văn bản nhưng CongVanCard:

```
┌────────────────────────────────────────────┐
│ [CV] 5189/TCT-CS                           │
│ Nội dung mới NĐ 126/2020/NĐ-CP hướng dẫn  │
│ Luật Quản lý thuế                          │
│ 📅 07/12/2020  •  Tổng cục Thuế            │
└────────────────────────────────────────────┘
```

---

## 🏗️ Tech Stack

**Chọn 1 trong 2 (ưu tiên option A):**

### Option A: Vanilla TypeScript + Vite (nhanh, nhẹ)
```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.ts
│   ├── api.ts          ← BASE_URL = '' (relative)
│   ├── types.ts
│   ├── state.ts        ← app state management
│   └── components/
│       ├── Header.ts
│       ├── Sidebar.ts
│       ├── DocList.ts
│       ├── DocCard.ts
│       ├── DocDetail.ts
│       └── HieuLucBadge.ts
```

### Option B: React + Vite (nếu prefer React)
```
frontend/
├── index.html
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api.ts
│   ├── types.ts
│   └── components/
│       (same as above, .tsx)
```

---

## 🐳 Dockerfile

```dockerfile
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build
# Output: /frontend/dist/

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --exclude=frontend . .
COPY --from=frontend-builder /frontend/dist ./static

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

FastAPI serve SPA (đã có trong `main.py`):
```python
# Cuối main.py — static files + SPA fallback (đã có sẵn)
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/")
async def root(): return FileResponse("static/index.html")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"): raise HTTPException(404)
    return FileResponse("static/index.html")
```

---

## ⚙️ Vite Config

```typescript
// vite.config.ts
import { defineConfig } from 'vite'

export default defineConfig({
  base: '/',
  build: {
    outDir: 'dist',
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

---

## ✅ Checklist khi hoàn thành

1. [ ] `npm run build` không lỗi
2. [ ] API calls dùng relative URL (`/api/...`), không phải `localhost`
3. [ ] `GET /api/categories` — handle plain array (không phải `{items:[...]}`)
4. [ ] HieuLucBadge hiển thị đúng 3 trạng thái (xanh/đỏ/vàng)
5. [ ] DocDetail panel slide-in khi click card
6. [ ] Pagination hoạt động (page param)
7. [ ] Filter sidebar hoạt động
8. [ ] Tab Văn bản + Công văn chuyển được
9. [ ] Responsive (mobile friendly cơ bản)
10. [ ] Commit message rõ ràng
11. [ ] **Xóa file test**: `test-openclaw.txt`
12. [ ] File này (CLAUDE.md) — có thể xóa sau khi đọc xong

---

## 🚀 Deploy

App deploy trên **Coolify** (auto-deploy khi push main branch).

- **URL:** https://dbvntax.gpt4vn.com  
- **Repo:** https://github.com/phanvuhoang/dbvntax  
- Coolify watch branch `main` → build Docker image → deploy

**Sau khi push:** Coolify tự build và deploy. Không cần làm thêm gì.
