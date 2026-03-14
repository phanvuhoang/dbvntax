# CLAUDE.md — dbvntax Frontend Fix & Complete

## Tình trạng hiện tại

Frontend đã build nhưng **không hiển thị được văn bản**. Cần debug và fix toàn bộ.

**Backend API hoạt động tốt** — đã verify:
- `GET /api/documents?limit=5` → trả về `{"items": [...], "total": 294, "page": 1}` ✅
- `GET /api/categories` → trả về array `[{"code":"QLT","name":"Quản lý thuế","count":86}, ...]` ✅
- `GET /api/documents/{id}` → trả về document đầy đủ với `hieu_luc_index` ✅

---

## Bugs cần fix ngay

### Bug 1: API base URL hardcoded
Trong `frontend/src/api.ts`, `BASE_URL` đang là `http://localhost:8000`.  
→ **Fix:** Đổi thành `''` (empty string — relative URL, tự động dùng cùng domain)

### Bug 2: Vite proxy config
Thêm vào `frontend/vite.config.ts`:
```typescript
server: {
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```
Để dev mode hoạt động, còn production dùng relative URL.

### Bug 3: Response format handling
`/api/categories` trả về **plain array**, không phải `{items: [...]}`.  
Frontend phải handle: `const cats = Array.isArray(data) ? data : data.items || []`

### Bug 4: Dockerfile — frontend chưa build vào image
Kiểm tra `Dockerfile`: frontend build output phải copy vào `/app/static/`.  
FastAPI phải serve static files. Xem template dưới.

---

## Database Schema (đã có sẵn, không cần tạo lại)

```sql
documents (
  id, so_hieu, ten, loai, ngay_ban_hanh,
  tinh_trang, hl,              -- hl: 1=còn HL, 0=hết HL
  sac_thue,                    -- "QLT"|"CIT"|"VAT"|"HDDT"|"PIT"|"SCT"|"FCT"|"TP"|"HKD"
  category_name,               -- "Quản lý thuế"|"Thuế TNDN"|...
  github_path,                 -- unique path
  hieu_luc_index               -- jsonb, xem cấu trúc dưới
)
```

`hieu_luc_index` structure:
```json
{
  "hieu_luc": [{"pham_vi":"Toàn bộ","tu_ngay":"2020-10-19","den_ngay":null,"ghi_chu":""}],
  "van_ban_thay_the": ["83/2013/NĐ-CP"],
  "van_ban_sua_doi": [],
  "tom_tat_hieu_luc": "Hiệu lực từ 05/12/2020, thay thế NĐ 83/2013."
}
```

---

## API Endpoints

```
GET /api/documents
    ?category=CIT     -- filter by sac_thue code
    &loai=TT          -- filter by loai (TT|ND|LUAT|QD|NQ|VBHN|CV)
    &hl=1             -- 1=còn HL, 0=hết HL
    &search=keyword   -- tìm trong ten + so_hieu
    &page=1&limit=20
    → {"items": [...], "total": 294, "page": 1}

GET /api/documents/{id}   → Document object đầy đủ

GET /api/categories       → [{code, name, count}, ...]  (plain array!)

GET /api/cong-van         → {"items": [...], "total": N, "page": 1}
    ?category=CIT&search=...&page=1&limit=20
```

---

## Cấu trúc app cần build

```
frontend/
├── package.json
├── vite.config.ts       ← thêm proxy
├── tailwind.config.js
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── types.ts
    ├── api.ts           ← fix BASE_URL + response handling
    └── components/
        ├── Sidebar.tsx
        ├── DocList.tsx
        ├── DocCard.tsx
        ├── DocDetail.tsx
        ├── HieuLucBadge.tsx
        └── HieuLucDetail.tsx
```

---

## Dockerfile (fix nếu cần)

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
COPY . .
# Copy frontend build
COPY --from=frontend-builder /frontend/dist ./static

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Trong `main.py`, thêm ở cuối (sau tất cả API routes):
```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/")
    async def root():
        return FileResponse("static/index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        return FileResponse("static/index.html")
```

---

## UI Spec

### Layout
```
┌──────────┬─────────────────────────────────────────┐
│ Sidebar  │  [Văn bản] [Công văn]    [Search   🔍] │
│          ├─────────────────────────────────────────┤
│ 9 mục    │  DocCard  DocCard  DocCard  DocCard     │
│ thuế     │  DocCard  DocCard  ...                  │
│          │                      [< 1 2 3 ... >]   │
│ Filters  │─────────────────────────────────────────│
│ Loại VB  │  DocDetail panel (slide-in khi click)   │
│ Hiệu lực │                                         │
│ Tại ngày │                                         │
└──────────┴─────────────────────────────────────────┘
```

### Primary color: `#028a39` — dùng cho tất cả accent, button, link active

### 9 Categories
```typescript
const CATEGORIES = [
  { code: 'QLT',  name: 'Quản lý thuế',      count: 86 },
  { code: 'CIT',  name: 'Thuế TNDN',          count: 37 },
  { code: 'VAT',  name: 'Thuế GTGT',          count: 32 },
  { code: 'HDDT', name: 'Hóa đơn điện tử',    count: 31 },
  { code: 'PIT',  name: 'Thuế TNCN',          count: 41 },
  { code: 'SCT',  name: 'Thuế TTĐB',          count: 22 },
  { code: 'FCT',  name: 'Thuế nhà thầu',      count: 13 },
  { code: 'TP',   name: 'Giao dịch liên kết', count: 18 },
  { code: 'HKD',  name: 'Hộ kinh doanh',      count: 14 },
];
```

### DocCard
- Số hiệu (bold, `#028a39`) + Loại badge (TT/NĐ/Luật...)
- Tên (2 dòng, truncate)
- Ngày ban hành (DD/MM/YYYY)
- HieuLucBadge

### HieuLucBadge (quan trọng!)
```
hl=1 + không có hieu_luc_index → "Còn hiệu lực" (xanh)
hl=0                           → "Hết hiệu lực" (đỏ)
có hieu_luc_index với den_ngay → "Hiệu lực một phần" (vàng)
```
Hover tooltip: hiển thị `hieu_luc_index.tom_tat_hieu_luc`

### DocDetail panel (slide-in, width 480px)
- Header: số hiệu + badge + nút đóng
- Tên đầy đủ
- Meta: ngày, loại, category
- **HieuLucDetail** (nếu có hieu_luc_index):
  - Tóm tắt `tom_tat_hieu_luc`
  - Bảng `hieu_luc[]`: Phạm vi | Từ ngày | Đến ngày | Ghi chú
  - `van_ban_thay_the`: "🔴 Thay thế: NĐ 83/2013"
  - `van_ban_sua_doi`: "🟡 Sửa đổi: TT 96/2015"
- Link: "📄 Xem văn bản gốc ↗" → `https://vntaxdoc.gpt4vn.com/docs/{github_path}`

---

## Yêu cầu khi hoàn thành

1. Test `npm run build` chạy thành công không lỗi
2. Verify frontend call đúng `/api/documents` (relative URL, không phải localhost)
3. **Commit tất cả changes** với message rõ ràng
4. **Xóa file rác**: CLAUDE.md sau khi đọc xong, bất kỳ file test/debug nào
5. Repo sau khi xong phải clean: chỉ có backend (`main.py`, etc.) + `frontend/` + `Dockerfile`
