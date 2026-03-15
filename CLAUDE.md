# CLAUDE.md — dbvntax Frontend BUG FIX

> **Last updated:** 2026-03-15 — Fix blank screen after deploy
> **Priority:** HIGH — app hiện tại deploy lên Coolify nhưng blank screen

---

## 🐛 Bugs cần fix ngay

### Bug 1 (CRITICAL — gây blank screen): `CongVanResponse` sai field name

Trong `frontend/src/types.ts`:
```typescript
// HIỆN TẠI (SAI):
export interface CongVanResponse {
  total: number;
  results: CongVan[];  // ← SAI
}
```

API `/api/cong-van` thực tế trả về:
```json
{"items": [...], "total": 93}
```

**Fix:**
```typescript
// ĐÚNG:
export interface CongVanResponse {
  total: number;
  items: CongVan[];
}
```

Sau đó update `frontend/src/pages/HomePage.tsx` — chỗ dùng `congVanResult.data?.results` → đổi thành `congVanResult.data?.items`.

Tìm và thay tất cả references: `congVanResult.data?.results` → `congVanResult.data?.items`

---

### Bug 2: `border-l-3` không phải Tailwind standard class

Trong `frontend/src/components/DocList.tsx`:
```
className={`... border-l-3 ...`}
```

Tailwind không có `border-l-3`. Fix: đổi thành `border-l-4` hoặc dùng `border-l-[3px]`.

---

### Bug 3: SPA fallback trong `main.py` (đã fix, verify lại)

Đảm bảo cuối `main.py` có đúng như sau (KHÔNG dùng `app.mount("/", StaticFiles(...))`):

```python
import os as _os
from fastapi.responses import FileResponse as _FileResponse

if _os.path.isdir("static/assets"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/")
async def spa_root():
    return _FileResponse("static/index.html")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    index = "static/index.html"
    if _os.path.exists(index):
        return _FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built")
```

---

## ✅ Sau khi fix

1. [ ] `npm run build` không lỗi
2. [ ] Verify `CongVanResponse.items` (không phải `.results`) được dùng nhất quán trong toàn bộ codebase
3. [ ] Verify `main.py` KHÔNG có `app.mount("/", StaticFiles(...))` 
4. [ ] **Commit** với message: `fix: blank screen — CongVanResponse items field + border-l + SPA fallback`
5. [ ] **Push** lên GitHub (`git push origin main`)
6. [ ] **Xóa file này** (CLAUDE.md) sau khi push
