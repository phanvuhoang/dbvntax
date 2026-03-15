# CLAUDE.md — Sprint: Fix categories API + Add THUE_QT to frontend

## Context

App: https://dbvntax.gpt4vn.com  
Repo: phanvuhoang/dbvntax  
Stack: FastAPI (main.py) + React/TypeScript (frontend/src/)

---

## Task 1: Fix `/api/categories` in `main.py`

**Problem:** The current implementation does `unnest(sac_thue)` and returns raw DB codes, causing duplicate/alias categories to appear in the sidebar (e.g. `TNCN` and `PIT` both show as "Thuế TNCN", `TNDN` appears separately from `CIT`).

**Fix:** Replace the `SAC_NAMES` dict + return logic with canonical codes, alias merging, and fixed display order.

Find this block in `main.py` (inside `async def categories(...)`):

```python
    SAC_NAMES = {
        'QLT': 'Quản lý thuế', 'CIT': 'Thuế TNDN', 'TNDN': 'Thuế TNDN',
        'VAT': 'Thuế GTGT', 'GTGT': 'Thuế GTGT', 'HDDT': 'Hóa đơn điện tử',
        'HOA_DON': 'Hóa đơn', 'PIT': 'Thuế TNCN', 'TNCN': 'Thuế TNCN',
        'SCT': 'Thuế TTĐB', 'TTDB': 'Thuế TTĐB', 'FCT': 'Thuế nhà thầu',
        'NHA_THAU': 'Nhà thầu', 'TP': 'Giao dịch liên kết', 'GDLK': 'Giao dịch LK',
        'HKD': 'Hộ kinh doanh',
    }
    return [{"code": row["code"], "name": SAC_NAMES.get(row["code"], row["code"]), "count": row["count"]}
            for row in r.mappings().all()]
```

Replace with:

```python
    # Canonical codes & display order (sidebar)
    CANONICAL = [
        ('QLT',     'Quản lý thuế'),
        ('CIT',     'Thuế TNDN'),
        ('VAT',     'Thuế GTGT'),
        ('HDDT',    'Hóa đơn điện tử'),
        ('PIT',     'Thuế TNCN'),
        ('SCT',     'Thuế TTĐB'),
        ('FCT',     'Thuế nhà thầu'),
        ('TP',      'Giao dịch liên kết'),
        ('HKD',     'Hộ kinh doanh'),
        ('THUE_QT', 'Thuế Quốc tế'),
    ]
    # Alias map: raw DB code → canonical code
    ALIAS = {
        'TNDN': 'CIT', 'GTGT': 'VAT', 'HOA_DON': 'HDDT',
        'TNCN': 'PIT', 'TTDB': 'SCT', 'NHA_THAU': 'FCT', 'GDLK': 'TP',
        'TAI_NGUYEN': 'THUE_QT',
    }
    # Aggregate counts by canonical code
    counts: dict = {}
    for row in r.mappings().all():
        code = ALIAS.get(row["code"], row["code"])
        counts[code] = counts.get(code, 0) + row["count"]
    return [
        {"code": code, "name": name, "count": counts.get(code, 0)}
        for code, name in CANONICAL
        if counts.get(code, 0) > 0
    ]
```

---

## Task 2: Add `THUE_QT` to `frontend/src/types.ts`

### 2a. Add to `CATEGORIES` array

Find:
```typescript
  { code: 'HKD', name: 'Hộ kinh doanh', color: 'pink' },
] as const;
```

Replace with:
```typescript
  { code: 'HKD', name: 'Hộ kinh doanh', color: 'pink' },
  { code: 'THUE_QT', name: 'Thuế Quốc tế', color: 'sky' },
] as const;
```

### 2b. Add to `SAC_THUE_MAP`

Add this entry to the `SAC_THUE_MAP` object:
```typescript
  THUE_QT: 'Thuế Quốc tế',
```

---

## Commit message
`feat: fix categories API (canonical codes + THUE_QT), add THUE_QT to frontend sidebar`

---

## Notes
- Do NOT change any other logic, UI layout, or styling
- Do NOT redeploy or restart anything — Coolify handles that automatically on push
- Verify: after push, `GET /api/categories` should return exactly 10 items with no duplicate TNCN/TNDN
