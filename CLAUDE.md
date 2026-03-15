# CLAUDE.md — dbvntax Sprint 2 Brief
> Version: 2 | Date: 2026-03-15 | Author: ThanhAI

---

## ⚠️ Ghi nhớ từ Sprint 1 — đọc trước khi code

Khi dùng optional chaining với arrays từ API/DB, **luôn dùng `?? []`** trước khi gọi `.length` hay `.map`:

```typescript
// SAI — crash nếu server trả null thay vì []
index.hieu_luc.length
entries.length

// ĐÚNG
(index.hieu_luc ?? []).length
(entries ?? []).length
```

**Quy tắc chung:** Mọi array từ API đều phải guard bằng `?? []`. Mọi object từ API đều phải guard bằng `?.`.

---

## 🎯 Sprint 2 — 3 việc cần làm

---

## 1. Content Panel — Xem nội dung văn bản trong app

### Hiện trạng
- Nút "Xem văn bản gốc" đang mở link ra `vntaxdoc.gpt4vn.com` (tab mới)
- `noi_dung` column trong DB **hoàn toàn trống** (chưa import)
- File HTML gốc nằm trong repo `vn-tax-corpus`, path lưu trong `documents.github_path`

### Yêu cầu
Thay đổi layout từ 2 panel → **3 panel** (giống vntaxdoc.gpt4vn.com), tất cả có thể **kéo resize**:

```
┌──────────┬─────────────────┬──────────────────────────────┐
│ SIDEBAR  │   DANH SÁCH     │   NỘI DUNG VĂN BẢN           │
│ (200px)  │   (280px)       │   (flex-1)                   │
│          │                 │                              │
│ Categories│  DocCard       │  [Hiển thị HTML content]     │
│ Filters  │  DocCard       │                              │
│          │  DocCard       │  (load từ vntaxdoc hoặc      │
│          │  ...           │   iframe/fetch)              │
│          │                 │                              │
└──────────┴─────────────────┴──────────────────────────────┘
  ↕ resize  ↕ resize          ↕ resize (drag dividers)
```

### Cách hiển thị content (dùng iframe)

Vì `noi_dung` trong DB trống, load content từ static site:

```typescript
// URL pattern cho iframe:
const contentUrl = `https://vntaxdoc.gpt4vn.com/docs/${doc.github_path}`;

// Component ContentPanel:
<iframe
  src={contentUrl}
  className="w-full h-full border-0"
  title={doc.ten}
/>
```

### Resize dividers

Dùng CSS + mouse drag (không cần thư viện):

```typescript
// Lưu widths vào state
const [sidebarW, setSidebarW] = useState(200);
const [listW, setListW] = useState(280);
// Content panel = flex-1 (phần còn lại)

// Divider: <div onMouseDown={startDrag} className="w-1 cursor-col-resize bg-gray-200 hover:bg-primary" />
```

### Khi chưa chọn văn bản
Content panel hiển thị:
```
┌─────────────────────────────┐
│         📄                  │
│  Chọn văn bản để xem        │
│  nội dung                   │
└─────────────────────────────┘
```

---

## 2. Hiệu lực văn bản — hieu_luc_index

### Hiện trạng
- `hieu_luc_index` column đã có trong DB (jsonb)
- **Tất cả 159 docs đều có `hieu_luc = []`** (array rỗng, chưa extract)
- Phần "Hiệu lực văn bản" trong DocDetail hiện ra trống

### Yêu cầu: Script extract bằng AI (Claudible)

Viết file `scripts/extract_hieu_luc.py`:

```python
"""
Extract hieu_luc_index cho 159 documents bằng Claudible Sonnet
Đọc HTML từ vn-tax-corpus repo (đã clone tại /tmp/vntaxcorpus)
Gọi Claudible để extract → lưu vào PostgreSQL
"""

CORPUS_DIR = "/tmp/vntaxcorpus/docs"   # HTML files
DB_URL = os.environ["DATABASE_URL"]     # từ env
CLAUDIBLE_KEY = os.environ["CLAUDIBLE_API_KEY"]
CLAUDIBLE_URL = os.environ.get("CLAUDIBLE_BASE_URL", "https://claudible.io/v1")

SYSTEM_PROMPT = """Bạn là chuyên gia pháp luật thuế Việt Nam.
Nhiệm vụ: Đọc văn bản pháp luật và extract thông tin hiệu lực.
Trả về JSON thuần túy, không có markdown, không giải thích."""

USER_PROMPT = """Đọc phần cuối văn bản (Điều khoản thi hành, Điều khoản chuyển tiếp, Hiệu lực thi hành).
Extract ra mảng hieu_luc[] theo format:

{
  "hieu_luc": [
    {
      "pham_vi": "Mô tả phạm vi áp dụng",
      "tu_ngay": "YYYY-MM-DD hoặc null",
      "den_ngay": "YYYY-MM-DD hoặc null (null = còn hiệu lực)",
      "ghi_chu": "Ghi chú thêm nếu có"
    }
  ],
  "van_ban_thay_the": ["NĐ 218/2013", ...],
  "van_ban_sua_doi": ["NĐ 91/2022", ...],
  "tom_tat_hieu_luc": "Tóm tắt 1-2 câu về hiệu lực"
}

Nội dung văn bản:
{content}"""
```

**Logic extract:**

```python
for doc in all_docs:
    # 1. Đọc HTML file
    html_path = f"{CORPUS_DIR}/{doc['github_path']}"
    if not os.path.exists(html_path): continue
    
    # 2. Extract text từ HTML (dùng BeautifulSoup)
    soup = BeautifulSoup(open(html_path), 'html.parser')
    text = soup.get_text()
    
    # 3. Lấy 3000 ký tự cuối (phần điều khoản thi hành thường ở cuối)
    content = text[-3000:]
    
    # 4. Gọi Claudible
    client = anthropic.Anthropic(api_key=CLAUDIBLE_KEY, base_url=CLAUDIBLE_URL)
    response = client.messages.create(
        model="claude-sonnet-4.6",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": USER_PROMPT.format(content=content)}]
    )
    
    # 5. Parse JSON và update DB
    result = json.loads(response.content[0].text)
    # UPDATE documents SET hieu_luc_index = result WHERE id = doc.id
```

**Chạy script này trên VPS** (không phải trong container app):
```bash
cd /tmp/dbvntax-debug
DATABASE_URL="postgresql+asyncpg://..." CLAUDIBLE_API_KEY="..." python3 scripts/extract_hieu_luc.py
```

### Frontend — hiển thị khi có data

Phần HieuLucDetail đã có, chỉ cần đảm bảo:

```typescript
// DocDetail.tsx — chỉ hiện section này khi có data thực
{doc.hieu_luc_index && (doc.hieu_luc_index.hieu_luc ?? []).length > 0 && (
  <HieuLucDetail index={doc.hieu_luc_index} />
)}

// Nếu trống thì hiện placeholder
{(!doc.hieu_luc_index || (doc.hieu_luc_index.hieu_luc ?? []).length === 0) && (
  <p className="text-sm text-gray-400 italic">Chưa có thông tin hiệu lực chi tiết</p>
)}
```

---

## 3. Auth & AI Analysis

### Login credentials (đã có user trong DB)

```
Email:    vuhoang04@gmail.com
Password: [anh tự set — xem mục Set Password bên dưới]
Role:     admin
Plan:     enterprise
```

**Set password** (chạy 1 lần):
```bash
# Trong container hoặc qua API
POST /api/auth/set-password
body: { "email": "vuhoang04@gmail.com", "new_password": "your_password" }
```

### AI features đã có trong backend

```python
# ai.py — đã implement đầy đủ:
stream_quick_analysis(db, question, context_ids)   # streaming
stream_analyze_doc(db, source, doc_id)             # streaming  
do_factcheck(db, text_input)                       # sync
do_related(db, source, doc_id)                     # sync
```

### Frontend — AI panel

Đã có `AIAnalysis.tsx` và `QuickAnalysis.tsx`. Kiểm tra và đảm bảo:

1. **Auth gate:** Nếu chưa login → hiện "Đăng nhập để dùng AI" thay vì lỗi 401
2. **Streaming display:** Dùng `fetch` với `ReadableStream`, append text từng chunk vào state
3. **Error handling:** Nếu AI call fail → hiện message lỗi rõ ràng (không crash)

```typescript
// Pattern đúng cho streaming:
const response = await fetch('/api/ai/quick-analysis', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  },
  body: JSON.stringify({ question, context_doc_ids: [] }),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();
let result = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  result += decoder.decode(value);
  setStreamText(result);  // update UI real-time
}
```

---

## ✅ Checklist Sprint 2

1. [ ] 3-panel layout với resize dividers (sidebar / list / content)
2. [ ] Content panel load iframe từ `https://vntaxdoc.gpt4vn.com/docs/{github_path}`
3. [ ] `(array ?? [])` guard trên **tất cả** arrays từ API — không để `.length` trần
4. [ ] HieuLucDetail: hiện "Chưa có dữ liệu" khi array rỗng
5. [ ] Script `scripts/extract_hieu_luc.py` hoạt động (test với 3 docs trước)
6. [ ] Auth gate cho AI features — redirect login thay vì crash
7. [ ] Streaming AI response hiển thị real-time
8. [ ] **Commit + push** (`git push origin main`)
9. [ ] **Xóa CLAUDE.md** sau khi xong
