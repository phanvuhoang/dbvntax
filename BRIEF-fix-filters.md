# BRIEF: Fix chu_de + tinh_trang Filters

**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-16  
**Priority:** High — filters return 0 results despite data existing

---

## Vấn đề

Sau khi deploy taxonomy sidebar, 2 filters trong `/api/cong-van` không hoạt động:

```
GET /api/cong-van?chu_de=Hoàn thuế  → Total: 0  (expected: ~250+)
GET /api/cong-van?tinh_trang=con_hieu_luc → Total: 0  (expected: ~9,754)
```

`/api/cong-van/taxonomy` hoạt động đúng — data có trong DB.

---

## Root Cause (likely)

`list_cong_van()` trong `search.py` chưa nhận `chu_de` + `tinh_trang` params, hoặc chưa truyền đúng từ `main.py` xuống.

---

## Fix

### 1. `search.py` — update `list_cong_van`

Thêm 2 params và filter SQL:

```python
async def list_cong_van(
    db, q, sac_thue, nguon, limit, offset,
    year_from=None, year_to=None,
    chu_de: str = None,       # ← THÊM
    tinh_trang: str = None,   # ← THÊM
):
    where = ["1=1"]
    params = {}

    # ... (giữ nguyên các where hiện tại) ...

    # THÊM VÀO SAU CÁC FILTER HIỆN TẠI:
    if chu_de:
        where.append(":chu_de = ANY(chu_de)")
        params["chu_de"] = chu_de

    if tinh_trang:
        where.append("tinh_trang = :tinh_trang")
        params["tinh_trang"] = tinh_trang
```

> ⚠️ `chu_de` là `text[]` array — PHẢI dùng `= ANY()`, không dùng `LIKE` hay `=`

### 2. `main.py` — đảm bảo truyền params xuống

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

---

## Giá trị `tinh_trang` thực tế trong DB

```
"Còn hiệu lực"   → 9,268 CVs  (chữ hoa C)
"còn hiệu lực"   →   486 CVs  (chữ thường c)
""               →    90 CVs  (null/empty)
"hết hiệu lực"   →     1 CV
```

> ⚠️ Case inconsistency! Cần normalize khi filter — dùng `LOWER()` hoặc `ILIKE`:

```python
if tinh_trang:
    where.append("LOWER(tinh_trang) = LOWER(:tinh_trang)")
    params["tinh_trang"] = tinh_trang
```

Frontend nên truyền `tinh_trang=Còn hiệu lực` (hoặc lowercase đều được nhờ LOWER()).

---

## Verify sau fix

```bash
# chu_de filter
curl "https://dbvntax.gpt4vn.com/api/cong-van?sac_thue=GTGT&chu_de=Ho%C3%A0n+thu%E1%BA%BF&limit=1"
# Expected: total > 200

# tinh_trang filter
curl "https://dbvntax.gpt4vn.com/api/cong-van?tinh_trang=C%C3%B2n+hi%E1%BB%87u+l%E1%BB%B1c&limit=1"
# Expected: total ~9,754
```

---

## Files cần thay đổi

| File | Action |
|------|--------|
| `search.py` | Thêm `chu_de`, `tinh_trang` params + filter SQL vào `list_cong_van` |
| `main.py` | Đảm bảo endpoint nhận + truyền `chu_de`, `tinh_trang` xuống |

