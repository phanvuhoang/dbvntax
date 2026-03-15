# CLAUDE.md — Fix Search: unaccent + FTS index

## Context
App dbvntax.gpt4vn.com hiện có search bị broken:
- `/api/search?q=thue+TNDN` trả về `{"total":0,"results":[]}`
- Nguyên nhân: `plainto_tsquery('simple', 'thue TNDN')` tạo ra token `'thue'` nhưng DB lưu `'thuế'` (có dấu tiếng Việt) → không match

## Việc cần làm (2 phần)

---

## Phần 1: Enable `unaccent` extension + Fix search.py

### Bước 1: Thêm migration enable unaccent vào database.py

Mở `database.py`, tìm hàm `init_db()` (hoặc nơi create tables). Thêm đoạn này vào đầu hàm, TRƯỚC khi create tables:

```python
# Enable unaccent extension for Vietnamese diacritic-insensitive search
await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
```

### Bước 2: Sửa search.py — wrap tất cả tsvector/tsquery với unaccent()

Tìm tất cả chỗ dùng `to_tsvector` và `plainto_tsquery` trong `search.py`, thay thế theo pattern:

**TRƯỚC:**
```python
"to_tsvector('simple', coalesce(so_hieu,'') || ' ' || coalesce(ten,'') || ' ' || coalesce(tom_tat,'')) @@ plainto_tsquery('simple', :q)"
```

**SAU:**
```python
"to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || coalesce(ten,'') || ' ' || coalesce(tom_tat,''))) @@ plainto_tsquery('simple', unaccent(:q))"
```

Áp dụng cho TẤT CẢ chỗ trong `search.py` (cả trong `search_keyword` lẫn `list_cong_van`).

### Bước 3: Tương tự cho cong_van search

Trong hàm `list_cong_van`, cũng wrap unaccent:
```python
"to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || ten)) @@ plainto_tsquery('simple', unaccent(:q))"
```

### Bước 4: Thêm GIN index để tăng tốc search (tùy chọn nhưng nên làm)

Trong `database.py`, sau khi enable unaccent, thêm:
```python
await conn.execute(text("""
    CREATE INDEX IF NOT EXISTS idx_documents_fts 
    ON documents USING GIN (
        to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || coalesce(ten,'') || ' ' || coalesce(tom_tat,'')))
    )
"""))
await conn.execute(text("""
    CREATE INDEX IF NOT EXISTS idx_cong_van_fts
    ON cong_van USING GIN (
        to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || ten))
    )
"""))
```

---

## Phần 2: Fix `mode=hybrid` fallback

Hiện tại khi gọi `/api/search?q=...&mode=hybrid`, do `embedding IS NULL` cho tất cả docs, hàm `search_semantic` được gọi nhưng trả về rỗng.

Trong `search.py`, hàm `do_search()`, sửa logic hybrid để fallback về keyword khi không có embeddings:

**TRƯỚC:**
```python
if mode == "semantic":
    return await search_semantic(db, q, filters, limit, offset)
else:
    return await search_keyword(db, q, filters, limit, offset)
```

**SAU:**
```python
if mode == "semantic":
    return await search_semantic(db, q, filters, limit, offset)
elif mode == "hybrid":
    # Try semantic first, fallback to keyword if no results
    results, total = await search_semantic(db, q, filters, limit, offset)
    if total == 0:
        return await search_keyword(db, q, filters, limit, offset)
    return results, total
else:
    return await search_keyword(db, q, filters, limit, offset)
```

---

## Test sau khi fix

Sau khi deploy, verify bằng các query này (tất cả phải trả về kết quả > 0):

```bash
curl "https://dbvntax.gpt4vn.com/api/search?q=thue+TNDN" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"
curl "https://dbvntax.gpt4vn.com/api/search?q=thuế+TNDN" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"
curl "https://dbvntax.gpt4vn.com/api/search?q=GTGT&mode=hybrid" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"
curl "https://dbvntax.gpt4vn.com/api/search?q=chuyen+gia" | python3 -c "import json,sys; d=json.load(sys.stdin); print('total:', d['total'])"
```

Tất cả phải > 0.

---

## Notes
- KHÔNG xóa hàm `search_semantic` — giữ để sau này add embeddings
- `unaccent` là PostgreSQL built-in extension, không cần install thêm package
- Commit message: `fix: Vietnamese diacritic-insensitive search with unaccent, hybrid fallback`
