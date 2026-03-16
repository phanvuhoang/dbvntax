# BRIEF: Cleanup Documents Table — Loại Bỏ Văn Bản Không Liên Quan

**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-16  
**Priority:** Medium — data quality issue

---

## Vấn đề

Hiện tại `documents` table có **1,065 văn bản**, nhưng chỉ **145/1,065** (14%) có `category_name` hợp lệ.  
**920 văn bản** có `category_name = NULL` — đây là rác sync từ vn-tax-corpus vào gồm:

- Quy trình nội bộ Cục Thuế (KY_NANG, KIEM_TRA_NOI_BO, CHUC_NANG_NHIEM_VU)
- Giá tài nguyên địa phương (QĐ UBND tỉnh Quảng Ninh)
- Văn bản kế toán, xây dựng, môi trường, không liên quan thuế
- Mẫu biểu nội bộ (Botieuchi, Phuluc, v.v.)
- Văn bản hết hiệu lực cũ (folder `0001.HET_HIEU_LUC`)

Mục tiêu của dbvntax là **văn bản pháp luật thuế chính thức** — 10 categories canonical:
`QLT, CIT, VAT, HDDT, PIT, SCT, FCT, TP, HKD, THUE_QT`

---

## Fix: 2 bước

### Bước 1 — Script cleanup DB (backend/scripts)

Tạo file `scripts/cleanup_documents.py`:

```python
"""
Xóa các văn bản không liên quan khỏi documents table.
Chỉ giữ lại các docs có category_name hợp lệ (10 canonical categories).
"""
import asyncio
from sqlalchemy import text
from database import engine  # dùng engine từ database.py

VALID_CATEGORIES = {
    'Quản lý thuế', 'Thuế TNDN', 'Thuế GTGT', 'Hóa đơn điện tử',
    'Thuế TNCN', 'Thuế TTĐB', 'Thuế nhà thầu', 'Giao dịch liên kết',
    'Hộ kinh doanh', 'Thuế Quốc tế'
}

async def main():
    async with engine.begin() as conn:
        # Đếm trước
        r = await conn.execute(text("SELECT COUNT(*) FROM documents WHERE category_name IS NULL OR category_name = ''"))
        count = r.scalar()
        print(f"Sẽ xóa {count} văn bản không có category")

        # Confirm
        ans = input("Xác nhận xóa? (yes/no): ")
        if ans.lower() != 'yes':
            print("Hủy.")
            return

        # Xóa
        await conn.execute(text("""
            DELETE FROM documents
            WHERE category_name IS NULL OR category_name = ''
        """))
        print(f"Đã xóa {count} văn bản.")

        # Verify
        r2 = await conn.execute(text("SELECT category_name, COUNT(*) FROM documents GROUP BY category_name ORDER BY count DESC"))
        rows = r2.fetchall()
        print("\nKết quả sau cleanup:")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")

asyncio.run(main())
```

### Bước 2 — Chạy cleanup trực tiếp trên VPS (KHÔNG cần script)

Để an toàn, thực hiện bằng SQL trực tiếp (ThanhAI sẽ chạy sau khi anh confirm):

```sql
-- Preview trước
SELECT category_name, COUNT(*) 
FROM documents 
WHERE category_name IS NULL OR category_name = ''
GROUP BY category_name;

-- Xóa (chạy sau khi anh OK)
DELETE FROM documents
WHERE category_name IS NULL OR category_name = '';
```

---

## Kết quả kỳ vọng sau cleanup

| | Trước | Sau |
|---|---|---|
| Total docs | 1,065 | ~145 |
| Có category | 145 (14%) | 145 (100%) |
| Rác (NULL category) | 920 | 0 |

---

## Lưu ý

- **Không xóa từ vn-tax-corpus** — chỉ xóa khỏi DB
- vn-tax-corpus giữ nguyên để tham khảo
- Sau cleanup, `/api/categories` count sẽ chính xác hơn
- Sidebar tab Văn bản sẽ chỉ hiện 10 categories thuế chính thức

---

## Files cần thay đổi

| File | Action |
|------|--------|
| `scripts/cleanup_documents.py` | Tạo mới (script cleanup) |
| DB trực tiếp | Chạy DELETE query sau khi anh Hoàng confirm |

