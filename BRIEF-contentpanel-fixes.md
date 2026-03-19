# BRIEF: ContentPanel Fixes — Hide TVPL Sidebar + Full Width + Open HTML in New Tab

**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-19  
**File duy nhất cần sửa:** `frontend/src/components/ContentPanel.tsx`

---

## Fix 1: Ẩn sidebar TVPL + Fix content full width

Trong `ContentPanel.tsx`, tìm đoạn `dangerouslySetInnerHTML` và update className của wrapper div.

**Tìm dòng có:**
```
[&_.right-col]:!hidden [&_.ct.scroll_right]:!hidden
[&_.NoiDungChiaSe_TT_Hide]:!hidden [&_#divShare]:!hidden
```

**Thay toàn bộ className thành:**
```tsx
className="prose max-w-none text-gray-700 leading-relaxed
           [&_table]:border-collapse [&_table]:w-full [&_table]:text-sm
           [&_td]:border [&_td]:border-gray-300 [&_td]:p-2
           [&_th]:border [&_th]:border-gray-300 [&_th]:p-2 [&_th]:bg-gray-50
           [&_p]:mb-3 [&_h1]:text-base [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold
           [&_h3]:text-sm [&_h3]:font-semibold [&_b]:font-semibold
           [&_.NoiDungChiaSe]:!hidden
           [&_.ulnhch]:!hidden
           [&_.GgADS]:!hidden
           [&_.LawNote]:!hidden
           [&_.ykien]:!hidden
           [&_.ttlq]:!hidden
           [&_.download1]:!hidden
           [&_#hd-save-doc]:!hidden
           [&_#btTheoDoiHieuLuc]:!hidden
           [&_#btnSoSanhThayThe]:!hidden
           [&_#btnSongNgu]:!hidden
           [&_#TVNDWidget]:!hidden
           [&_.clr]:!hidden
           [&_#divContentDoc]:!float-none [&_#divContentDoc]:!w-full [&_#divContentDoc]:!mr-0"
```

---

## Fix 2: Button "Mở tab mới" — mở HTML content trong tab mới

### Mục đích

Button này mở **nội dung HTML đang render trong panel** vào một tab trình duyệt mới — không phải redirect ra TVPL hay bất kỳ URL nào. Tức là lấy `content` (HTML string từ DB) → tạo Blob URL → `window.open()`.

Button có mặt trong **cả hai tab: Văn bản và Công văn**.

### Implementation

**Thêm hàm helper** vào component (trước phần return):

```tsx
const openContentInNewTab = () => {
  if (!content) return;
  const html = `<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${(tab === 'vanban' ? doc.ten : cv.ten) || 'Văn bản'}</title>
  <style>
    body { font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6; padding: 24px 40px; max-width: 900px; margin: 0 auto; color: #333; }
    table { border-collapse: collapse; width: 100%; }
    td, th { border: 1px solid #ccc; padding: 6px 10px; }
    p { margin-bottom: 10px; }
    /* Hide TVPL sidebar elements */
    .NoiDungChiaSe, .ulnhch, .GgADS, .LawNote, .ykien, .ttlq, .download1,
    #hd-save-doc, #btTheoDoiHieuLuc, #btnSoSanhThayThe, #btnSongNgu, #TVNDWidget, .clr { display: none !important; }
    #divContentDoc { float: none !important; width: 100% !important; margin: 0 !important; }
  </style>
</head>
<body>
${content}
</body>
</html>`;
  const blob = new Blob([html], { type: 'text/html; charset=utf-8' });
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
};
```

**Thêm button** vào header của ContentPanel, ngay cạnh button "Xem nguồn" / "TVPL ↗" hiện có:

```tsx
{content && (
  <button
    onClick={openContentInNewTab}
    className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 hover:border-primary hover:text-primary transition text-gray-500 whitespace-nowrap"
    title="Mở nội dung trong tab mới"
  >
    <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
    Mở tab mới
  </button>
)}
```

**Lưu ý vị trí:**
- `content` đã được define ở dòng: `const content = tab === 'vanban' ? doc.noi_dung : cv.noi_dung_day_du;`
- Button chỉ hiện khi `content` có giá trị (truthy) → tự động ẩn nếu chưa có nội dung
- Đặt button trong phần header, cùng hàng với các action buttons khác (font size, AI, Xem nguồn)

---

## Tóm tắt

| Fix | File | Mô tả |
|-----|------|-------|
| 1 | `ContentPanel.tsx` | CSS override: ẩn sidebar TVPL, fix `#divContentDoc` full width |
| 2 | `ContentPanel.tsx` | Thêm `openContentInNewTab()` + button "Mở tab mới" (Blob URL) — có trong cả Văn bản lẫn Công văn |

---

## Sau khi xong

1. Commit: `fix: hide TVPL sidebar, fix content width, add open-html-in-new-tab button`
2. Push lên `main`
3. Xóa file BRIEF này

_Brief by ThanhAI — 2026-03-19_
