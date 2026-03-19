# BRIEF: Add "Mở tab mới" Button to ContentPanel

**File cần sửa:** `frontend/src/components/ContentPanel.tsx`

---

## Mục tiêu

Thêm button **"Mở tab mới"** bên cạnh button "Xem nguồn" hiện tại, trong cả 2 tab (Văn bản + Công văn).

Button này lấy HTML content đang render trong panel → tạo Blob URL → `window.open()`. **Không redirect ra TVPL.**

---

## Step 1: Thêm hàm helper

Thêm hàm này vào component, trước phần `return`:

```tsx
const openContentInNewTab = () => {
  if (!content) return;
  const title = (activeDoc?.ten ?? activeCv?.ten) ?? 'Văn bản';
  const html = `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 14px; line-height: 1.8;
           padding: 24px 48px; max-width: 900px; margin: 0 auto; color: #333; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; }
    td, th { border: 1px solid #ccc; padding: 6px 10px; }
    p { margin-bottom: 10px; }
    .NoiDungChiaSe, .ulnhch, .GgADS, .LawNote, .ykien, .ttlq,
    .download1, #hd-save-doc, #btTheoDoiHieuLuc, #btnSoSanhThayThe,
    #btnSongNgu, #TVNDWidget, .clr, .info-red { display: none !important; }
    #divContentDoc { float: none !important; width: 100% !important; margin: 0 !important; }
  </style>
</head>
<body>${content}</body>
</html>`;
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
};
```

Note: `content` là state/prop đang giữ HTML string của văn bản/công văn đang xem. `activeDoc` và `activeCv` là object đang active — dùng cái đúng tùy theo cách component đang đặt tên.

---

## Step 2: Thêm button vào toolbar

Tìm button "Xem nguồn" trong JSX (có `link_nguon` hoặc `link_tvpl`), thêm button "Mở tab mới" **ngay bên cạnh**:

```tsx
{/* Existing "Xem nguồn" button */}
<a href={...} target="_blank" ...>Xem nguồn</a>

{/* NEW: Mở tab mới */}
{content && (
  <button
    onClick={openContentInNewTab}
    className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors"
    title="Mở nội dung trong tab mới"
  >
    <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none"
         viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round"
            d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
    Mở tab mới
  </button>
)}
```

---

## Notes

- Button chỉ hiện khi có `content` (không hiện khi panel trống)
- Áp dụng cho **cả tab Văn bản lẫn tab Công văn** — cùng component nên chỉ làm 1 lần
- CSS trong Blob HTML đã include hide TVPL sidebar elements → tab mới render sạch
- Không cần backend changes
