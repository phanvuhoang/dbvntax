# BRIEF: Fix Filter Sắc Thuế Tab Công Văn Trả 0 Kết Quả

**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-16  
**Priority:** High — bug UX rõ ràng

---

## Vấn đề

Khi user chuyển từ tab **Văn bản** sang tab **Công văn** rồi click vào một sắc thuế (VD: "Quản lý thuế"), kết quả trả về **0 văn bản**.

## Root Cause

`handleTabChange` trong `HomePage.tsx` không reset `category` state khi đổi tab.

**Flow lỗi:**
1. User đang ở tab Văn bản, chọn category `"CIT"` → `category = "CIT"`
2. User chuyển sang tab Công văn → `category` vẫn là `"CIT"`
3. `useCongVan({ sac_thue: "CIT" })` → API query `?sac_thue=CIT`
4. DB công văn dùng codes `TNDN/GTGT/QLT` (không có `CIT`) → **0 results**

Tab Văn bản dùng codes: `CIT, VAT, PIT, HDDT, SCT, TP, QLT, FCT, HKD, THUE_QT`  
Tab Công văn dùng codes: `TNDN, GTGT, TNCN, HOA_DON, TTDB, GDLK, QLT, FCT, HKD, THUE_QT, XNK, TAI_NGUYEN_DAT, MON_BAI_PHI`

## Fix

**File:** `frontend/src/pages/HomePage.tsx`

Tìm `handleTabChange` (khoảng dòng 74):

```typescript
// TRƯỚC (bị lỗi)
const handleTabChange = useCallback((t: Tab) => {
  setTab(t); setPage(1); setSelectedItem(null);
  setSelectedChuDe('');
}, []);

// SAU (đã fix)
const handleTabChange = useCallback((t: Tab) => {
  setTab(t); setPage(1); setSelectedItem(null);
  setSelectedChuDe('');
  setCategory('');  // reset category khi đổi tab — tránh mismatch CIT vs TNDN
}, []);
```

## Verify sau fix

1. Vào dbvntax.gpt4vn.com, chọn tab Văn bản → click "Thuế TNDN"
2. Chuyển sang tab Công văn → sidebar phải hiện "Tất cả" (không còn chọn gì)
3. Click "Quản lý thuế" ở sidebar → phải ra ~4,000+ kết quả
4. Chuyển lại tab Văn bản → sidebar reset về "Tất cả"

## Files cần thay đổi

| File | Action |
|------|--------|
| `frontend/src/pages/HomePage.tsx` | Thêm `setCategory('')` vào `handleTabChange` |

