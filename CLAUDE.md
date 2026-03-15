# CLAUDE.md — Thêm THUE_QT (Thuế Quốc tế) vào frontend

## Việc cần làm: chỉ sửa `frontend/src/types.ts`

---

## Sửa `CATEGORIES` — thêm THUE_QT

Tìm mảng `CATEGORIES` trong `frontend/src/types.ts`:

```ts
export const CATEGORIES = [
  { code: 'QLT', name: 'Quản lý thuế', color: 'blue' },
  { code: 'CIT', name: 'Thuế TNDN', color: 'green' },
  { code: 'VAT', name: 'Thuế GTGT', color: 'teal' },
  { code: 'HDDT', name: 'Hóa đơn điện tử', color: 'purple' },
  { code: 'PIT', name: 'Thuế TNCN', color: 'orange' },
  { code: 'SCT', name: 'Thuế TTĐB', color: 'red' },
  { code: 'FCT', name: 'Thuế nhà thầu', color: 'yellow' },
  { code: 'TP', name: 'Giao dịch liên kết', color: 'indigo' },
  { code: 'HKD', name: 'Hộ kinh doanh', color: 'pink' },
] as const;
```

Thêm `THUE_QT` vào cuối danh sách:

```ts
export const CATEGORIES = [
  { code: 'QLT', name: 'Quản lý thuế', color: 'blue' },
  { code: 'CIT', name: 'Thuế TNDN', color: 'green' },
  { code: 'VAT', name: 'Thuế GTGT', color: 'teal' },
  { code: 'HDDT', name: 'Hóa đơn điện tử', color: 'purple' },
  { code: 'PIT', name: 'Thuế TNCN', color: 'orange' },
  { code: 'SCT', name: 'Thuế TTĐB', color: 'red' },
  { code: 'FCT', name: 'Thuế nhà thầu', color: 'yellow' },
  { code: 'TP', name: 'Giao dịch liên kết', color: 'indigo' },
  { code: 'HKD', name: 'Hộ kinh doanh', color: 'pink' },
  { code: 'THUE_QT', name: 'Thuế Quốc tế', color: 'sky' },
] as const;
```

---

## Sửa `SAC_THUE_MAP` — thêm mapping THUE_QT

Tìm `SAC_THUE_MAP` trong cùng file, thêm entry:

```ts
export const SAC_THUE_MAP: Record<string, string> = {
  // ... existing entries ...
  THUE_QT: 'Thuế Quốc tế',
};
```

---

## Commit message
`feat: add THUE_QT (Thuế Quốc tế) category to sidebar and SAC_THUE_MAP`
