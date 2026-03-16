# BRIEF: Fix Tab Switch + Filter Bug + Notes

**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-16 (updated)  
**Priority:** High

---

## Việc cần làm (2 bugs + 1 note)

---

## Bug 1: Filter Sắc Thuế Tab Công Văn Trả 0 Kết Quả

### Vấn đề
Khi user chuyển từ tab **Văn bản** → tab **Công văn** rồi click sắc thuế → kết quả 0.

### Root Cause
`handleTabChange` trong `HomePage.tsx` không reset `category` state khi đổi tab.

Tab Văn bản dùng codes: `CIT, VAT, PIT...`  
Tab Công văn dùng codes: `TNDN, GTGT, QLT...`  
→ Khi chuyển tab, `category = "CIT"` cũ vẫn còn → `?sac_thue=CIT` → 0 results.

### Fix
**File:** `frontend/src/pages/HomePage.tsx`

```typescript
// Tìm handleTabChange (~dòng 74), thêm setCategory(''):
const handleTabChange = useCallback((t: Tab) => {
  setTab(t); setPage(1); setSelectedItem(null);
  setSelectedChuDe('');
  setCategory('');  // ← THÊM DÒNG NÀY
}, []);
```

---

## Bug 2: Filter `chu_de` và `tinh_trang` Trả 0 Kết Quả

### Vấn đề
```
GET /api/cong-van?chu_de=Hoàn thuế    → Total: 0  (expected: ~250+)
GET /api/cong-van?tinh_trang=Còn hiệu lực → Total: 0  (expected: ~9,700+)
```

### Root Cause
`list_cong_van()` trong `search.py` chưa nhận/xử lý 2 params này.

### Fix

**`search.py`** — thêm params + filter SQL vào `list_cong_van`:

```python
async def list_cong_van(
    db, q, sac_thue, nguon, limit, offset,
    year_from=None, year_to=None,
    chu_de: str = None,       # ← THÊM
    tinh_trang: str = None,   # ← THÊM
):
    # ... giữ nguyên phần hiện tại ...

    # THÊM sau các filter hiện tại:
    if chu_de:
        where.append(":chu_de = ANY(chu_de)")
        params["chu_de"] = chu_de

    if tinh_trang:
        # Dùng LOWER() vì DB có cả "Còn hiệu lực" và "còn hiệu lực"
        where.append("LOWER(tinh_trang) = LOWER(:tinh_trang)")
        params["tinh_trang"] = tinh_trang
```

> ⚠️ `chu_de` là `text[]` array → PHẢI dùng `= ANY()`, không dùng `=` hay `LIKE`

**`main.py`** — đảm bảo endpoint nhận và truyền 2 params xuống:

```python
@app.get("/api/cong-van")
async def cong_van_list(
    q: str = "",
    sac_thue: Optional[str] = None,
    nguon: Optional[str] = None,
    chu_de: Optional[str] = None,       # ← ĐẢM BẢO CÓ
    tinh_trang: Optional[str] = None,   # ← ĐẢM BẢO CÓ
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    results, total = await list_cong_van(
        db, q, sac_thue, nguon, limit, offset,
        year_from=year_from, year_to=year_to,
        chu_de=chu_de,           # ← TRUYỀN XUỐNG
        tinh_trang=tinh_trang,   # ← TRUYỀN XUỐNG
    )
    return {"total": total, "items": results}
```

### Verify sau fix
```bash
curl "https://dbvntax.gpt4vn.com/api/cong-van?sac_thue=GTGT&chu_de=Ho%C3%A0n+thu%E1%BA%BF&limit=1"
# Expected: total > 200

curl "https://dbvntax.gpt4vn.com/api/cong-van?tinh_trang=C%C3%B2n+hi%E1%BB%87u+l%E1%BB%B1c&limit=1"
# Expected: total ~9,700+
```

---

## Note quan trọng — KHÔNG restore cron sync corpus

Cron `sync_corpus.py` đã bị **tắt có chủ đích** trên VPS (2026-03-16).  
**Lý do:** Script sync toàn bộ vn-tax-corpus (1,129 docs) vào DB, gây import rác.  
**KHÔNG thêm lại** cron này dưới bất kỳ hình thức nào.  

Workflow mới: Anh Hoàng add văn bản qua Google Sheet → ThanhAI import thủ công có kiểm soát.

---

## Files cần thay đổi

| File | Action |
|------|--------|
| `frontend/src/pages/HomePage.tsx` | Thêm `setCategory('')` vào `handleTabChange` |
| `search.py` | Thêm `chu_de`, `tinh_trang` params + filter SQL vào `list_cong_van` |
| `main.py` | Đảm bảo endpoint nhận + truyền `chu_de`, `tinh_trang` |

