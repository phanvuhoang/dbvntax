# BRIEF: ContentPanel — TomTat/HieuLuc after doc + Floating header on mobile

**Date:** 2026-03-25 (v2 update)  
**Scope:** Frontend only — ContentPanel.tsx  
**Priority:** HIGH  
**Context:** Sidebar icons + collapsible panels đã implement xong (commit e57b9ba). Brief này chỉ fix riêng ContentPanel.

---

## Fix 3a: TomTat + HieuLuc — đặt SAU nội dung văn bản (cuối trang scroll)

### Vấn đề hiện tại
`TomTatBox` và `HieuLucDetail` đang render ở đầu trang, phía trên content → chiếm ~30% màn hình mobile trước khi đọc.

### Yêu cầu
- Di chuyển cả 2 vào **bên trong** vùng scroll (`flex-1 overflow-y-auto`), đặt **SAU** `dangerouslySetInnerHTML` content
- Người dùng phải scroll qua hết văn bản mới thấy
- Nếu không có `noi_dung` → không render gì cả

### Implementation

**Xóa** các block hiện tại ra khỏi vị trí giữa header và content scroll area:
```tsx
// XÓA block này:
{tab === 'vanban' && doc.hieu_luc_index && (
  <div className="px-4 mt-2 flex-shrink-0">
    <HieuLucDetail index={doc.hieu_luc_index} />
  </div>
)}

// XÓA block này:
{(doc as Document).tom_tat && (
  <div className="px-4 flex-shrink-0">
    <TomTatBox text={(doc as Document).tom_tat!} />
  </div>
)}
```

**Thêm** vào cuối vùng scroll, SAU content HTML:

```tsx
<div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">

  {/* Document content */}
  {content ? (
    <div className="prose max-w-none ..." dangerouslySetInnerHTML={{ __html: content }} />
  ) : (
    <div className="flex flex-col items-center justify-center h-full text-gray-300 gap-2">
      <span className="text-3xl">📝</span>
      <span className="text-sm">Chưa có nội dung văn bản</span>
    </div>
  )}

  {/* ── SAU NỘI DUNG VĂN BẢN ── chỉ hiện khi có content */}
  {content && (
    <div className="mt-8 pt-6 border-t-2 border-dashed border-gray-200 space-y-3">

      {/* Tóm tắt */}
      {(doc as Document).tom_tat && (
        <div>
          <button
            onClick={() => setTomTatOpen(o => !o)}
            className="w-full flex items-center justify-between py-2 text-left group"
          >
            <span className="text-xs font-bold text-gray-400 uppercase tracking-widest group-hover:text-primary transition">
              📝 Tóm tắt văn bản
            </span>
            <span className="text-gray-300 text-xs">{tomTatOpen ? '▲' : '▼'}</span>
          </button>
          {tomTatOpen && (
            <div className="mt-2 text-sm text-gray-600 leading-relaxed bg-gray-50 rounded-lg p-4">
              {(doc as Document).tom_tat}
            </div>
          )}
        </div>
      )}

      {/* Hiệu lực chi tiết */}
      {tab === 'vanban' && doc.hieu_luc_index && (
        <div>
          <button
            onClick={() => setHieuLucOpen(o => !o)}
            className="w-full flex items-center justify-between py-2 text-left group"
          >
            <span className="text-xs font-bold text-gray-400 uppercase tracking-widest group-hover:text-primary transition">
              ⚡ Hiệu lực chi tiết
            </span>
            <span className="text-gray-300 text-xs">{hieuLucOpen ? '▲' : '▼'}</span>
          </button>
          {hieuLucOpen && (
            <div className="mt-2">
              <HieuLucDetail index={doc.hieu_luc_index} />
            </div>
          )}
        </div>
      )}

    </div>
  )}
</div>
```

Add state variables:
```tsx
const [tomTatOpen, setTomTatOpen] = useState(false);
const [hieuLucOpen, setHieuLucOpen] = useState(false);
```

---

## Fix 3b: Floating/auto-hide header on mobile scroll

### Yêu cầu
- Mobile: header (tiêu đề + ngày + loại văn bản) ẩn khi cuộn xuống, hiện lại khi cuộn lên hoặc về đầu
- Desktop: header luôn hiện (không thay đổi)

### Implementation

Add `useRef` + scroll listener on the content scroll div:

```tsx
const scrollRef = useRef<HTMLDivElement>(null);
const [headerVisible, setHeaderVisible] = useState(true);
const lastScrollY = useRef(0);

useEffect(() => {
  const el = scrollRef.current;
  if (!el) return;
  const handler = () => {
    const currentY = el.scrollTop;
    if (currentY < 10) {
      setHeaderVisible(true);              // đầu trang → luôn hiện
    } else if (currentY < lastScrollY.current) {
      setHeaderVisible(true);              // cuộn lên → hiện
    } else if (currentY > lastScrollY.current + 5) {
      setHeaderVisible(false);             // cuộn xuống → ẩn
    }
    lastScrollY.current = currentY;
  };
  el.addEventListener('scroll', handler, { passive: true });
  return () => el.removeEventListener('scroll', handler);
}, [item]);

// Reset khi đổi item
useEffect(() => {
  setHeaderVisible(true);
  lastScrollY.current = 0;
  if (scrollRef.current) scrollRef.current.scrollTop = 0;
}, [item]);
```

Apply to the document header div:
```tsx
<div
  className={`
    px-4 py-2 border-b border-gray-200 flex-shrink-0 bg-white
    transition-all duration-200 ease-in-out overflow-hidden
    md:max-h-none md:opacity-100 md:py-2
    ${headerVisible ? 'max-h-24 opacity-100' : 'max-h-0 opacity-0 border-b-0 py-0 px-0'}
  `}
>
  {/* ...existing header content unchanged... */}
</div>
```

Attach ref to scroll div:
```tsx
<div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
```

---

## Do NOT change

- Sidebar code (already done in e57b9ba)
- Admin import UI (already done in ec7e8bb)
- Search logic, API hooks, auth
- Footer action buttons (AI, Xem gốc, TVPL, Mở tab mới)

---

*Brief by Thanh AI — 2026-03-25 v2*
