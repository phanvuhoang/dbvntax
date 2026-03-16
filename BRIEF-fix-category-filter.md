# BRIEF: Fix Category Filter — "Không có kết quả" khi click Sidebar

**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-16  
**Priority:** Critical — ảnh hưởng 8/10 categories trên tab Văn bản

---

## Vấn đề

Khi user click category sidebar (Thuế TNDN, Thuế GTGT, Hóa đơn điện tử, Thuế TNCN, Thuế TTĐB, Giao dịch liên kết...) → kết quả **"Không có kết quả"**.

Chỉ **QLT** và **HKD** hoạt động đúng.

---

## Root Cause

**3 lớp code không đồng nhất:**

| Lớp | Code dùng |
|-----|-----------|
| Frontend `CATEGORIES` (types.ts) | `CIT`, `VAT`, `HDDT`, `PIT`, `SCT`, `TP` |
| DB column `sac_thue` | `TNDN`, `GTGT`, `HOA_DON`, `TNCN`, `TTDB`, `GDLK` |
| API search filter | Nhận `sac_thue` → query `= ANY(sac_thue)` |

**Flow hiện tại (sai):**
```
User click "Thuế TNDN" → category = "CIT"
HomePage.tsx: sac_thue = category = "CIT"
api.ts: GET /api/search?sac_thue=CIT
search.py: WHERE 'CIT' = ANY(sac_thue)  ← DB có {TNDN} → 0 results ❌
```

**Flow đúng:**
```
User click "Thuế TNDN" → category = "CIT"
HomePage.tsx: sac_thue = CANONICAL_TO_DB[category] = "TNDN"
api.ts: GET /api/search?sac_thue=TNDN
search.py: WHERE 'TNDN' = ANY(sac_thue)  ← DB có {TNDN} → ✅
```

---

## Fix

### File: `frontend/src/pages/HomePage.tsx`

`Sidebar.tsx` đã có `CANONICAL_TO_DB` map — **import và dùng lại** trong HomePage.

```typescript
// Thêm import ở đầu file
import { CANONICAL_TO_DB } from '../components/Sidebar';

// Tìm đoạn khai báo useSearch params (~dòng 35-45):
// Thay:
  sac_thue: category,

// Bằng:
  sac_thue: category ? (CANONICAL_TO_DB[category] ?? category) : undefined,
```

Áp dụng cho **cả 2 chỗ** dùng `sac_thue: category` trong file (tab Văn bản và tab Công văn).

### File: `frontend/src/components/Sidebar.tsx`

Export `CANONICAL_TO_DB` để HomePage import được:

```typescript
// Tìm dòng khai báo CANONICAL_TO_DB (~dòng 5-15):
// Thay:
const CANONICAL_TO_DB: Record<string, string> = {

// Bằng:
export const CANONICAL_TO_DB: Record<string, string> = {
```

---

## Map đầy đủ (đã có trong Sidebar.tsx, chỉ cần export)

```typescript
export const CANONICAL_TO_DB: Record<string, string> = {
  CIT:     'TNDN',
  VAT:     'GTGT',
  HDDT:    'HOA_DON',
  PIT:     'TNCN',
  SCT:     'TTDB',
  FCT:     'FCT',
  TP:      'GDLK',
  HKD:     'HKD',
  QLT:     'QLT',
  THUE_QT: 'THUE_QT',
};
```

---

## Files cần thay đổi

| File | Action |
|------|--------|
| `frontend/src/components/Sidebar.tsx` | Thêm `export` vào `CANONICAL_TO_DB` |
| `frontend/src/pages/HomePage.tsx` | Import + apply map khi pass `sac_thue` |

---

## Verify sau fix

```bash
# Expected: đều > 0
curl "https://dbvntax.gpt4vn.com/api/search?sac_thue=TNDN&limit=1"   # CIT
curl "https://dbvntax.gpt4vn.com/api/search?sac_thue=GTGT&limit=1"   # VAT
curl "https://dbvntax.gpt4vn.com/api/search?sac_thue=HOA_DON&limit=1" # HDDT
curl "https://dbvntax.gpt4vn.com/api/search?sac_thue=TNCN&limit=1"   # PIT
curl "https://dbvntax.gpt4vn.com/api/search?sac_thue=TTDB&limit=1"   # SCT
curl "https://dbvntax.gpt4vn.com/api/search?sac_thue=GDLK&limit=1"   # TP
```

---

_Brief by ThanhAI — 2026-03-16_
