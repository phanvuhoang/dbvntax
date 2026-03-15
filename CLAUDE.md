# CLAUDE.md — dbvntax Sprint 2 Brief
> Version: 2.1 | Date: 2026-03-15 | Author: ThanhAI

---

## ⚠️ Lesson learned Sprint 1 — đọc trước khi code

**Luôn guard arrays từ API bằng `?? []`:**
```typescript
// SAI — crash nếu server trả null
index.hieu_luc.length
entries.map(...)

// ĐÚNG
(index.hieu_luc ?? []).length
(entries ?? []).map(...)
```
Áp dụng cho **tất cả** arrays từ API/DB trong toàn bộ codebase.

---

## 🎯 Sprint 2 — 3 việc cần làm

---

## 1. Content Panel — 3-panel layout, render nội dung từ DB

### Context
- `noi_dung` column trong DB đã có plain text content (159 docs, avg 56KB)
- Content được import từ HTML files trong vn-tax-corpus (đã strip tags)
- **Không dùng iframe** — render trực tiếp từ `GET /api/documents/{id}` (trả `noi_dung`)
- Công văn cũng lưu `noi_dung_day_du` trong bảng `cong_van`

### Yêu cầu: Layout 3 panel resizable

```
┌──────────┬──────────────┬─────────────────────────────────────┐
│ SIDEBAR  │  DANH SÁCH   │  NỘI DUNG VĂN BẢN                  │
│ (200px)  │  (280px)     │  (flex-1, min 300px)               │
│          │              │                                     │
│ Category │  DocCard     │  [Tên văn bản - bold]              │
│ Filters  │  DocCard     │  [Metadata: ngày, cơ quan...]      │
│          │  ...         │  ─────────────────────────────────  │
│          │              │  [Nội dung plain text, scrollable] │
└──────────┴──────────────┴─────────────────────────────────────┘
          ↕ drag divider   ↕ drag divider
```

### Resize dividers (drag to resize)

```typescript
// State
const [sidebarW, setSidebarW] = useState(200);   // px
const [listW, setListW] = useState(280);          // px
// Content = flex-1 (remainder)

// Divider component
function Divider({ onDrag }: { onDrag: (dx: number) => void }) {
  const onMouseDown = (e: React.MouseEvent) => {
    const startX = e.clientX;
    const onMove = (ev: MouseEvent) => onDrag(ev.clientX - startX);
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };
  return <div onMouseDown={onMouseDown} className="w-1 cursor-col-resize bg-gray-200 hover:bg-primary flex-shrink-0 transition-colors" />;
}
```

### ContentPanel component

```typescript
// Khi chưa chọn doc:
<div className="flex-1 flex flex-col items-center justify-center text-gray-400 gap-2">
  <span className="text-4xl">📄</span>
  <span className="text-sm">Chọn văn bản để xem nội dung</span>
</div>

// Khi đã chọn doc — gọi GET /api/documents/{id} lấy noi_dung:
<div className="flex-1 flex flex-col overflow-hidden">
  {/* Header */}
  <div className="px-4 py-3 border-b border-gray-200 flex-shrink-0 bg-white">
    <h2 className="font-semibold text-gray-800 text-sm leading-snug">{doc.ten}</h2>
    <div className="flex gap-3 mt-1 text-xs text-gray-500">
      <span>{formatDate(doc.ngay_ban_hanh)}</span>
      <span>•</span>
      <span>{doc.co_quan}</span>
      <HieuLucBadge doc={doc} />
    </div>
  </div>
  {/* Content */}
  <div className="flex-1 overflow-y-auto px-4 py-3">
    <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">
      {doc.noi_dung}
    </pre>
  </div>
  {/* Footer actions */}
  <div className="px-4 py-2 border-t border-gray-100 flex gap-2 flex-shrink-0">
    <button onClick={() => setShowAIPanel(true)} className="btn-primary text-xs">
      🤖 Phân tích AI
    </button>
    <a href={`https://vntaxdoc.gpt4vn.com/docs/${doc.github_path}`}
       target="_blank" rel="noopener"
       className="btn-outline text-xs">
      📄 Xem gốc ↗
    </a>
  </div>
</div>
```

### API note
`GET /api/documents/{id}` đã trả về `noi_dung` (plain text, stripped HTML).
Với công văn: `GET /api/cong_van/{id}` trả `noi_dung_day_du`.

---

## 2. Hiệu lực văn bản — hieu_luc_index

### Hiện trạng
- DB: 159 docs, tất cả `hieu_luc = []` (chưa extract)
- **Script extract sẽ chạy riêng trên VPS sau** — không cần Claude Code làm

### Việc Claude Code cần làm (frontend only)

**DocDetail:** Thay vì ẩn section khi trống, hiện placeholder:

```typescript
// DocDetail.tsx
{doc.hieu_luc_index && (doc.hieu_luc_index.hieu_luc ?? []).length > 0 ? (
  <HieuLucDetail index={doc.hieu_luc_index} />
) : (
  <div className="mt-3 p-3 bg-gray-50 rounded text-sm text-gray-400 italic">
    Chưa có thông tin hiệu lực chi tiết
  </div>
)}
```

**HieuLucDetail.tsx** — guard tất cả arrays:
```typescript
{(index.hieu_luc ?? []).length > 0 && (   // thay index.hieu_luc.length
  ...
  (index.hieu_luc ?? []).map(...)           // thay index.hieu_luc.map
)}
{(index.van_ban_thay_the ?? []).length > 0 && (...)}
{(index.van_ban_sua_doi ?? []).length > 0 && (...)}
```

---

## 3. Auth & AI Analysis

### Login
```
Email:    vuhoang04@gmail.com
Password: Hoang@2026  (set qua API bên dưới)
```

**Set password** — gọi 1 lần:
```bash
curl -X POST https://dbvntax.gpt4vn.com/api/auth/set-password \
  -H "Content-Type: application/json" \
  -d '{"email":"vuhoang04@gmail.com","new_password":"Hoang@2026"}'
```

### AI Analysis — đã có backend

```python
# ai.py đã implement:
POST /api/ai/quick-analysis    → streaming (requires auth)
POST /api/ai/analyze-document  → streaming (requires auth)
POST /api/ai/factcheck         → sync (requires auth)
POST /api/ai/related           → sync (no auth needed)
```

### Frontend AI — việc cần fix/verify

1. **Auth gate:** Nếu chưa login → hiện nút "Đăng nhập để dùng AI"
2. **Streaming pattern đúng:**
```typescript
const response = await fetch('/api/ai/quick-analysis', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${localStorage.getItem('vntaxdb_token')}`,
  },
  body: JSON.stringify({ question, context_doc_ids: [] }),
});
const reader = response.body!.getReader();
const decoder = new TextDecoder();
let result = '';
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  result += decoder.decode(value, { stream: true });
  setStreamText(result);
}
```
3. **Error handling:** 401 → prompt login; 500 → hiện lỗi, không crash

---

## ✅ Checklist Sprint 2

1. [ ] 3-panel layout với drag resize dividers
2. [ ] ContentPanel render `noi_dung` từ DB (không dùng iframe)
3. [ ] Công văn: ContentPanel render `noi_dung_day_du`
4. [ ] `(array ?? [])` guard trên tất cả arrays từ API — toàn bộ codebase
5. [ ] HieuLucDetail: hiện placeholder khi `hieu_luc = []`
6. [ ] Auth modal hoạt động (login/register)
7. [ ] AI analysis auth gate — redirect login thay vì 401 crash
8. [ ] Streaming AI response real-time
9. [ ] `npm run build` không lỗi, không warning
10. [ ] **Commit + push** (`git push origin main`)
11. [ ] **Xóa CLAUDE.md** sau khi push
