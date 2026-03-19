# BRIEF: ContentPanel Fixes — Hide TVPL Sidebar + Full Width + Open in New Tab

**Repo:** phanvuhoang/dbvntax  
**Date:** 2026-03-19  
**Priority:** HIGH — app hiện đang DOWN (container bị drop khi attempt deploy), cần rebuild ngay

---

## ⚠️ Tình trạng hiện tại

Container `h2hondf1axrj2fyx8jheyknl` đang DOWN. Sau khi Claude Code commit + push xong, Anh Hoàng sẽ trigger redeploy từ Coolify dashboard tại `cl.gpt4vn.com`.

---

## Mục tiêu

Sửa `frontend/src/components/ContentPanel.tsx` để:

1. **Ẩn các phần thừa của TVPL** khi render HTML công văn (sidebar, share buttons, ads...)
2. **Fix `#divContentDoc` bị fixed width 530px** → full width
3. **Thêm button "Mở tab mới"** bên cạnh button "Xem nguồn" — cho cả Văn bản lẫn Công văn

---

## Phân tích HTML từ TVPL

Khi fetch công văn từ TVPL, HTML trả về có cấu trúc:

```html
<div id="ctl00_Content_ThongTinVB_pnlDocContent">
  <!-- Content chính — CẦN GIỮ -->
  <div class="cldivContentDocVn" id="divContentDoc" style="width: 530px; float: left; ...">
    <div class="content1"> ... nội dung văn bản ... </div>
  </div>

  <!-- Sidebar TVPL — CẦN ẨN -->
  <div class="NoiDungChiaSe" style="width: 190px; float: right; ...">
    <!-- share buttons, bookmark, social -->
  </div>
  <div class="ulnhch ulnhch01"> ... </div>
  <div class="ulnhch ulnhch02"> ... </div>
  <div class="GgADS"> ... </div>
  <div class="LawNote"> ... </div>
  <div class="ykien SendFeedBack_vb"> ... </div>
  <div class="ttlq"> ... </div>
  <div class="download1"> ... </div>
  <div id="hd-save-doc"> ... </div>
  <div id="btTheoDoiHieuLuc"> ... </div>
  <div id="btnSoSanhThayThe"> ... </div>
  <div id="btnSongNgu"> ... </div>
  <div id="TVNDWidget"> ... </div>
</div>
```

**Vấn đề:**
- `#divContentDoc` có `style="width: 530px; float: left;"` → content bị cắt, không dùng full width
- `.NoiDungChiaSe` và các div khác là sidebar/ads của TVPL → cần ẩn

---

## Fix 1: CSS Overrides trong className

Trong `ContentPanel.tsx`, tìm đoạn `dangerouslySetInnerHTML` và update className của wrapper div:

**Tìm:**
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

**Thay bằng:**
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

## Fix 2: Thêm Button "Mở tab mới"

### Logic

- Với **Văn bản (tab vanban):** mở `tvpl_url` nếu có, fallback là `link_tvpl`
- Với **Công văn (tab congvan):** mở `link_nguon` (URL TVPL của công văn đó)
- Nếu không có URL → button ẩn đi (giống "Xem nguồn" hiện tại)

### Vị trí

Button đặt **bên cạnh** button "Xem nguồn" (hoặc "TVPL ↗") hiện có trong header của ContentPanel.

### Tìm vị trí trong code

Tìm đoạn button "Xem nguồn" / "TVPL ↗" hiện tại — thường nằm trong phần header của ContentPanel sau phần metadata (so_hieu, ngay, sắc thuế). Thêm button mới ngay bên cạnh:

```tsx
{/* Button Mở tab mới */}
{(() => {
  const openUrl = tab === 'vanban'
    ? ((doc as Document).tvpl_url || (doc as Document).link_tvpl)
    : (cv as CongVan).link_nguon;
  return openUrl ? (
    <a
      href={openUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 hover:border-primary hover:text-primary transition text-gray-500"
      title="Mở trong tab mới"
    >
      <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
      </svg>
      Mở tab mới
    </a>
  ) : null;
})()}
```

**Đặt ngay SAU** button "Xem nguồn" / "TVPL ↗" hiện có. Nếu không tìm thấy button đó, đặt cuối dòng action buttons trong header.

---

## Tóm tắt files cần sửa

| File | Thay đổi |
|------|----------|
| `frontend/src/components/ContentPanel.tsx` | (1) Update className — thêm CSS hide selectors + fix divContentDoc width; (2) Thêm button "Mở tab mới" |

**Chỉ 1 file duy nhất cần sửa.**

---

## Sau khi xong

1. Commit với message: `fix: hide TVPL sidebar, fix content width, add open-in-new-tab button`
2. Push lên `main`
3. Xóa file BRIEF này
4. Nhắn anh Hoàng: "Done, anh deploy trên Coolify nhé"

---

_Brief by ThanhAI — 2026-03-19_
