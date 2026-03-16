# BRIEF: Hide TVPL Sidebar Elements in ContentPanel

## Context
App: https://dbvntax.gpt4vn.com  
File: `frontend/src/components/ContentPanel.tsx`

Nội dung công văn được lấy từ TVPL và lưu dạng HTML raw. Khi render bằng `dangerouslySetInnerHTML`, HTML của TVPL chứa sidebar bên phải với các nút: **Lưu trữ, Ghi chú, Ý kiến, Facebook, Email, In, Theo dõi hiệu lực VB, Văn bản thay thế, So sánh VB, Văn bản song ngữ** — cần ẩn hết, chỉ giữ lại nội dung văn bản.

## What to Change

File: `frontend/src/components/ContentPanel.tsx`  
Tìm đoạn `className="prose max-w-none...dangerouslySetInnerHTML`

Thêm các Tailwind arbitrary selectors để hide sidebar TVPL:

```tsx
className="prose max-w-none text-gray-700 leading-relaxed
           [&_table]:border-collapse [&_table]:w-full [&_table]:text-sm
           [&_td]:border [&_td]:border-gray-300 [&_td]:p-2
           [&_th]:border [&_th]:border-gray-300 [&_th]:p-2 [&_th]:bg-gray-50
           [&_p]:mb-3 [&_h1]:text-base [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold
           [&_h3]:text-sm [&_h3]:font-semibold [&_b]:font-semibold
           [&_.right-col]:!hidden [&_.ct.scroll_right]:!hidden
           [&_.NoiDungChiaSe_TT_Hide]:!hidden [&_#divShare]:!hidden"
```

**Classes/IDs cần hide** (xác nhận từ HTML thực tế của TVPL):
- `.right-col` — sidebar phải (Lưu trữ, Ghi chú, Ý kiến, v.v.)
- `.ct.scroll_right` — sticky scroll sidebar
- `.NoiDungChiaSe_TT_Hide` — nút chia sẻ ẩn
- `#divShare` — share bar

## Expected Result
Khi xem công văn trong app, chỉ hiển thị nội dung văn bản (bên trái), không còn sidebar TVPL bên phải.

## Notes
- Không thay đổi logic nào khác
- Chỉ thêm CSS selectors vào className hiện có
- Test bằng cách xem 1 công văn bất kỳ trong tab Công Văn
