# CLAUDE.md — dbvntax Sprint 2 Patch: HTML Content Rendering
> Version: 2.2 | Date: 2026-03-15

---

## 🎯 Một việc duy nhất: Render HTML thay vì plain text

### Context
- `noi_dung` trong DB **đã chứa HTML** (extracted từ vn-tax-corpus, stripped nav/script/style)
- `ContentPanel.tsx` hiện dùng `<pre>` → hiển thị raw HTML tags, trông rất xấu
- Cần đổi sang `dangerouslySetInnerHTML` để render đúng

---

## Fix: `frontend/src/components/ContentPanel.tsx`

Tìm đoạn render `noi_dung` (khoảng line 130-140):

```typescript
// HIỆN TẠI (SAI — render plain text):
<pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">
  {content}
</pre>

// ĐỔI THÀNH (render HTML):
<div
  className="prose prose-sm max-w-none text-gray-700 leading-relaxed
             [&_table]:border-collapse [&_table]:w-full [&_table]:text-sm
             [&_td]:border [&_td]:border-gray-300 [&_td]:p-2
             [&_th]:border [&_th]:border-gray-300 [&_th]:p-2 [&_th]:bg-gray-50
             [&_p]:mb-3 [&_h1]:text-base [&_h1]:font-bold [&_h2]:text-base [&_h2]:font-bold
             [&_h3]:text-sm [&_h3]:font-semibold [&_b]:font-semibold"
  dangerouslySetInnerHTML={{ __html: content ?? '' }}
/>
```

---

## Cũng fix: `frontend/src/components/DocDetail.tsx`

Tìm chỗ render `noi_dung_day_du` của cong_van (plain text) — đổi tương tự:

```typescript
// HIỆN TẠI:
<p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
  {(detail as CongVan).noi_dung_day_du}
</p>

// ĐỔI THÀNH:
<div
  className="prose prose-sm max-w-none text-gray-600 leading-relaxed
             [&_p]:mb-2 [&_b]:font-semibold"
  dangerouslySetInnerHTML={{ __html: (detail as CongVan).noi_dung_day_du ?? '' }}
/>
```

---

## Install @tailwindcss/typography (nếu chưa có)

```bash
cd frontend
npm install @tailwindcss/typography
```

Thêm vào `tailwind.config.ts`:
```typescript
plugins: [require('@tailwindcss/typography')],
```

---

## ✅ Checklist

1. [ ] `ContentPanel.tsx` — đổi `<pre>` thành `dangerouslySetInnerHTML`
2. [ ] `DocDetail.tsx` — đổi `<p whitespace-pre-wrap>` thành `dangerouslySetInnerHTML`
3. [ ] Install + config `@tailwindcss/typography`
4. [ ] `npm run build` không lỗi
5. [ ] **Commit + push** (`git push origin main`)
6. [ ] **Xóa CLAUDE.md** sau khi push
