# VNTaxDB — Claude Code Task Brief

## Setup
```bash
git clone https://github.com/phanvuhoang/dbvntax.git
cd dbvntax
```

## Files already done — DO NOT modify
`main.py`, `database.py`, `search.py`, `ai.py`, `requirements.txt`, `Dockerfile`

## Your ONLY task: write `static/index.html`

Complete SPA. All CSS + JS inline. No external libraries/CDN.

### API Endpoints
- `GET /health` → `{documents:N, cong_van:N, articles:N}`
- `POST /api/auth/login` `{email, password}` → `{token, user}`
- `POST /api/auth/register` `{email, password, ho_ten}` → `{token, user}`
- `GET /api/auth/me` (Authorization: Bearer token)
- `GET /api/search?q=&type=all|documents|cong_van|articles&sac_thue=&loai=&year_from=&year_to=&tinh_trang=&mode=keyword|semantic|hybrid&limit=20&offset=0`
- `GET /api/documents/{id}`
- `GET /api/cong_van/{id}`
- `POST /api/ai/quick-analysis` `{question, context_ids?}` → SSE stream
- `POST /api/ai/analyze-document` `{source, id}` → SSE stream
- `POST /api/ai/factcheck` `{text}` → `{citations:[]}`
- `POST /api/ai/related` `{source, id}` → `{related:[]}`

### SSE POST — use fetch + ReadableStream (NOT EventSource)
```javascript
const resp = await fetch('/api/ai/quick-analysis', {
  method: 'POST',
  headers: {'Content-Type':'application/json','Authorization':'Bearer '+token},
  body: JSON.stringify({question})
});
const reader = resp.body.getReader();
const dec = new TextDecoder();
while(true){
  const {done,value} = await reader.read();
  if(done) break;
  for(const line of dec.decode(value).split('\n')){
    if(!line.startsWith('data: ')) continue;
    const d = JSON.parse(line.slice(6));
    if(d.type==='text') appendText(d.content);
    if(d.type==='citations') showCitations(d.docs);
    if(d.type==='done') return;
  }
}
```

### Data shapes
Search result: `{id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue:[], github_path, snippet, source, score}`

```js
const SAC_THUE = {QLT:'Quản lý thuế',TNDN:'Thuế TNDN',GTGT:'Thuế GTGT',TNCN:'Thuế TNCN',
  TTDB:'Thuế TTDB',NHA_THAU:'Nhà thầu',GDLK:'Giao dịch LK',HKD:'Hộ KD',HOA_DON:'Hóa đơn'};
const LOAI_ICON = {Luat:'🏛️',ND:'📋',TT:'📄',VBHN:'🔗',QD:'📌',NQ:'📜',CV:'📧',Khac:'📎'};
```

### Layout — 3 columns, full viewport height
```
┌──────────────────────────────────────────────────────┐
│ HEADER: logo + nav tabs + search + filters + login   │
├──────────────┬──────────────────┬────────────────────┤
│ sidebar 200px│ results list 340 │ preview flex-1     │
│              │                  │                    │
│ DANH MỤC    │ result cards     │ iframe / HTML view │
│ sac_thue    │ with snippets    │ + AI analyze btn   │
│ categories  │                  │                    │
│ + counts    │ pagination       │                    │
└──────────────┴──────────────────┴────────────────────┘
```
Height: `calc(100vh - headerHeight)`. Drag handles between columns to resize.

### Header details
- Logo: ⚖️ VNTaxDB (color `#028a39`)
- Nav tabs: `[🔍 Tra cứu]` `[🤖 AI Phân tích]` `[✅ Fact-check]`
- Search: full-width, Google-style (`+TNDN "chi phí được trừ" -hết hiệu lực`), debounce 300ms
- Filter row: Loại VB ▼ | Sắc thuế ▼ | Năm ▼ | Hiệu lực ▼ | Nguồn ▼ | `○Keyword ●Hybrid ○Semantic` | `↺ Reset`
- Stats: "296 văn bản · 0 công văn · 0 bài viết" (from `/health` on load)
- Login button top-right

### Sidebar
- Title: **DANH MỤC**
- List sac_thue categories with doc counts from current results
- Click → filter; active = green highlight

### Result card
- `ten` bold green, click = load preview
- Badges: loai+icon (gray), sac_thue (each unique color), year (blue), tinh_trang (✅green / ❌red)
- snippet 2 lines ellipsis
- Active card: green left border + `#e8f5ee` bg

### Preview panel
- Empty state: "📄 Chọn một văn bản để xem nội dung"
- Toolbar: `[doc title]` `[🤖 Phân tích VB này]` `[↗ Mở tab mới]`
- `source=documents` with `github_path` → `<iframe src="https://vntaxdoc.gpt4vn.com/docs/{github_path}">`
- `source=cong_van` or `source=articles` → render `noi_dung` as HTML in scrollable div
- "🤖 Phân tích" button → switch to AI tab, auto-submit question

### AI Phân tích tab
- Textarea 8 rows placeholder "Nhập câu hỏi về thuế..."
- Example chips: "Tiền thuê nhà có được khấu trừ TNDN?" | "Lãi vay vượt 30% EBITDA?" | "Hóa đơn điện tử xuất sai ngày?"
- Submit → SSE stream → render markdown (regex only: `**bold**` → `<strong>`, `## h` → `<h3>`, `- item` → `<li>`)
- Citations chips (clickable → load doc in preview)
- Copy + Download (.txt) buttons

### Fact-check tab
- Large textarea "Paste đoạn văn cần kiểm tra..."
- Submit → POST `/api/ai/factcheck`
- Results table: VB trích dẫn | Tìm thấy trong DB | Trạng thái (✅ Hợp lệ / ⚠️ Hết hiệu lực / ❌ Không tìm thấy)

### Auth modal
- Email + password fields
- On success: store JWT in `localStorage('vntaxdb_token')`
- Show `Xin chào, {ho_ten}` + logout button when logged in
- AI features: if not logged in → show "🔒 Đăng nhập để sử dụng tính năng AI"

### CSS Design
- Primary: `#028a39` | Light: `#e8f5ee` | Dark: `#016b2c`
- Font: `'Segoe UI', Arial, sans-serif`
- Card shadow: `0 2px 8px rgba(0,0,0,0.08)`
- Smooth transitions: `0.15s`
- Clean, professional, Vietnamese UI

### On page load
1. `GET /health` → update stats in header
2. `GET /api/search` (no params, mode=hybrid) → load first 20 docs
3. Debounce search 300ms

### After done
```bash
git add static/index.html
git commit -m "feat: complete VNTaxDB SPA frontend"
git push origin main
```
