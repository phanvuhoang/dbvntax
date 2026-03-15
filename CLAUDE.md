# CLAUDE.md — dbvntax Sprint 2 Patch: HTML Content Rendering
> Version: 2.2 | Date: 2026-03-15

---

## 🎯 Việc 1: Render HTML thay vì plain text

### Context
- `noi_dung` trong DB **đã chứa HTML** (extracted từ vn-tax-corpus, stripped nav/script/style)
- `ContentPanel.tsx` hiện dùng `<pre>` → hiển thị raw HTML tags, trông rất xấu
- Cần đổi sang `dangerouslySetInnerHTML`

### Fix: `frontend/src/components/ContentPanel.tsx`

Tìm đoạn render `noi_dung` (khoảng line 130-140):

```typescript
// HIỆN TẠI (SAI):
<pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">
  {content}
</pre>

// ĐỔI THÀNH:
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

### Fix: `frontend/src/components/DocDetail.tsx`

Tìm chỗ render `noi_dung_day_du` của cong_van:

```typescript
// HIỆN TẠI:
<p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
  {(detail as CongVan).noi_dung_day_du}
</p>

// ĐỔI THÀNH:
<div
  className="prose prose-sm max-w-none text-gray-600 leading-relaxed [&_p]:mb-2 [&_b]:font-semibold"
  dangerouslySetInnerHTML={{ __html: (detail as CongVan).noi_dung_day_du ?? '' }}
/>
```

### Install @tailwindcss/typography

```bash
cd frontend && npm install @tailwindcss/typography
```

Thêm vào `tailwind.config.ts`:
```typescript
plugins: [require('@tailwindcss/typography')],
```

---

## 🎯 Việc 2: Hiệu lực — dùng tinh_trang + hl khi chưa có hieu_luc[]

### Context
- `hieu_luc_index.hieu_luc` hiện tại đều `[]` rỗng (AI extract chưa chạy)
- Nhưng mỗi doc đã có `tinh_trang` (`con_hieu_luc` / `het_hieu_luc`) và `hl` (1/0)
- Hiện tại section "Hiệu lực chi tiết" trong `ContentPanel.tsx` hiện "Chưa có thông tin" → xấu

### Fix: `frontend/src/components/ContentPanel.tsx`

Thay đoạn hiện lực (khoảng line 100-110):

```typescript
{tab === 'vanban' && (
  <div className="px-4 flex-shrink-0">
    {doc.hieu_luc_index && (doc.hieu_luc_index.hieu_luc ?? []).length > 0 ? (
      <HieuLucDetail index={doc.hieu_luc_index} />
    ) : (
      // Fallback: dùng tinh_trang + hl khi chưa có AI extract
      <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-100">
        <div className="flex items-center gap-2 text-sm">
          <span className="font-medium text-gray-600">Tình trạng hiệu lực:</span>
          {doc.hl === 1 || doc.tinh_trang === 'con_hieu_luc' ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs font-medium">
              ✓ Còn hiệu lực
            </span>
          ) : doc.hl === 0 || doc.tinh_trang === 'het_hieu_luc' ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-medium">
              ✗ Hết hiệu lực
            </span>
          ) : (
            <span className="text-gray-400 text-xs italic">Chưa xác định</span>
          )}
        </div>
        <p className="text-xs text-gray-400 mt-1.5 italic">
          Thông tin hiệu lực chi tiết (ngày áp dụng, điều khoản chuyển tiếp) đang được xử lý
        </p>
      </div>
    )}
  </div>
)}
```

Cũng cần thêm `tinh_trang` và `hl` vào type `Document` nếu chưa có:
```typescript
// types.ts — thêm vào Document interface nếu thiếu:
tinh_trang?: string;
hl?: number;
```

---

## ✅ Checklist

1. [ ] `ContentPanel.tsx` — `<pre>` → `dangerouslySetInnerHTML` cho `noi_dung`
2. [ ] `DocDetail.tsx` — `<p whitespace-pre-wrap>` → `dangerouslySetInnerHTML` cho `noi_dung_day_du`
3. [ ] Install + config `@tailwindcss/typography`
4. [ ] `ContentPanel.tsx` — hiệu lực fallback dùng `tinh_trang`/`hl` thay vì "Chưa có thông tin"
5. [ ] `types.ts` — verify `tinh_trang` và `hl` có trong `Document` interface
6. [ ] `npm run build` không lỗi
7. [ ] **Commit + push** (`git push origin main`)
8. [ ] **Xóa CLAUDE.md** sau khi push
