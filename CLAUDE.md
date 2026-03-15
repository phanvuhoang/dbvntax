# CLAUDE.md — Fix 2 vấn đề UI còn lại

## Vấn đề 1: TomTatBox và HieuLucDetail — thứ tự + expandable

### Hiện tại (sai)
- `TomTatBox` nằm TRƯỚC `HieuLucDetail` trong DocDetail
- `HieuLucDetail` luôn hiển thị (không collapse được)
- Kết quả: Tóm tắt hiện ở giữa, Hiệu lực chi tiết luôn mở

### Yêu cầu
- **Thứ tự:** Hiệu lực chi tiết TRƯỚC, Tóm tắt SAU
- **Cả hai đều là expandable collapsible** — mặc định collapsed, click header để toggle
- Style nhất quán giữa hai box

### Fix trong `frontend/src/components/DocDetail.tsx`

**Bước 1:** Đổi thứ tự render — HieuLucDetail trước, TomTatBox sau:

```tsx
{/* Hiệu lực chi tiết — expandable, mặc định collapsed */}
{tab === 'vanban' && doc.hieu_luc_index && (
  <HieuLucDetail index={doc.hieu_luc_index} />
)}

{/* Tóm tắt — expandable, mặc định collapsed */}
{(doc as Document).tom_tat && (
  <TomTatBox text={(doc as Document).tom_tat!} />
)}
```

**Bước 2:** Sửa `HieuLucDetail` thành expandable.

**File:** `frontend/src/components/HieuLucDetail.tsx`

Wrap toàn bộ nội dung trong collapsible — mặc định `open = false`:

```tsx
import { useState } from 'react';
import type { HieuLucIndex } from '../types';
import { formatDate } from '../api';

export default function HieuLucDetail({ index }: { index: HieuLucIndex }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-gray-200 rounded mb-4 overflow-hidden">
      {/* Header — clickable toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition text-left"
      >
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">⚖️ Hiệu lực chi tiết</span>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>

      {/* Nội dung — chỉ hiện khi open */}
      {open && (
        <div className="px-3 py-3">
          {index.tom_tat_hieu_luc && (
            <p className="text-sm text-gray-600 italic mb-3">{index.tom_tat_hieu_luc}</p>
          )}

          {(index.hieu_luc ?? []).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="text-left p-2 font-medium text-gray-600 border-b">Phạm vi</th>
                    <th className="text-left p-2 font-medium text-gray-600 border-b">Từ ngày</th>
                    <th className="text-left p-2 font-medium text-gray-600 border-b">Đến ngày</th>
                    <th className="text-left p-2 font-medium text-gray-600 border-b">Ghi chú</th>
                  </tr>
                </thead>
                <tbody>
                  {(index.hieu_luc ?? []).map((entry, i) => (
                    <tr key={i} className={entry.den_ngay ? 'bg-red-50' : ''}>
                      <td className="p-2 border-b border-gray-100">{entry.pham_vi}</td>
                      <td className="p-2 border-b border-gray-100">
                        {entry.tu_ngay ? formatDate(entry.tu_ngay) : '—'}
                      </td>
                      <td className="p-2 border-b border-gray-100">
                        {entry.den_ngay ? formatDate(entry.den_ngay) : (
                          <span className="text-green-600 font-medium">Hiện nay</span>
                        )}
                      </td>
                      <td className="p-2 border-b border-gray-100 text-gray-500">{entry.ghi_chu || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(index.van_ban_thay_the ?? []).length > 0 && (
            <div className="mt-3 text-sm">
              <span className="font-medium text-red-700">Thay thế hoàn toàn: </span>
              {(index.van_ban_thay_the ?? []).join(', ')}
            </div>
          )}
          {(index.van_ban_sua_doi ?? []).length > 0 && (
            <div className="mt-1 text-sm">
              <span className="font-medium text-yellow-700">Sửa đổi một phần: </span>
              {(index.van_ban_sua_doi ?? []).join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

**Bước 3:** Đảm bảo `TomTatBox` trong DocDetail có style nhất quán (đã đúng):
```tsx
function TomTatBox({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded mb-4 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition text-left"
      >
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">📝 Tóm tắt</span>
        <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 py-2 text-sm text-gray-600 leading-relaxed">{text}</div>
      )}
    </div>
  );
}
```

---

## Vấn đề 2: Sidebar "Sắc Thuế" chưa resize được

### Root cause
Sidebar dùng `position: fixed` trên mobile, `position: static` trên desktop (`md:static`). Khi `static`, nó nằm trong flex container `div.flex.flex-1.overflow-hidden.relative`. Tuy nhiên `overflow-hidden` trên parent **clip** việc drag của Divider ra ngoài bounds — mouse events bị mất khi con trỏ đi ra ngoài container.

### Fix trong `frontend/src/pages/HomePage.tsx`

Tìm main content div (ngay sau `</header>`):
```tsx
<div className="flex flex-1 overflow-hidden relative">
```

Thay thành:
```tsx
<div className="flex flex-1 overflow-hidden relative select-none">
```

Thêm `select-none` để tránh text selection khi drag.

**Quan trọng hơn:** Divider hiện wrap trong `<div className="hidden md:flex h-full">`. Div này cần `flex-shrink-0`:

```tsx
{/* Divider: Sidebar | DocList */}
<div className="hidden md:flex h-full flex-shrink-0">
  <Divider onResize={handleSidebarResize} />
</div>
```

**Và sửa `Divider.tsx`** để mouse events bám vào `document` đúng cách (hiện đã đúng), nhưng thêm `touch` support và đảm bảo `cursor` không bị override:

```tsx
export default function Divider({ onResize }: Props) {
  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    let lastX = e.clientX;
    const onMove = (ev: MouseEvent) => {
      const dx = ev.clientX - lastX;
      lastX = ev.clientX;
      onResize(dx);
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  return (
    <div
      onMouseDown={onMouseDown}
      className="w-1.5 cursor-col-resize bg-gray-200 hover:bg-primary active:bg-primary flex-shrink-0 transition-colors"
      style={{ cursor: 'col-resize' }}
    />
  );
}
```

Key fixes:
- `document.body.style.cursor = 'col-resize'` trong drag để cursor không đổi khi ra ngoài divider
- `document.body.style.userSelect = 'none'` để không bị bôi chọn text khi drag
- Reset cả hai khi mouseup
- Tăng width từ `w-1` lên `w-1.5` để dễ grab hơn

---

## Commit message
`fix: HieuLucDetail expandable collapsed, TomTat after HieuLuc, sidebar divider drag fix`
