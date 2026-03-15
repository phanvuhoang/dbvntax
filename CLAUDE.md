# CLAUDE.md — dbvntax Sprint 3
> Version: 3.0 | Date: 2026-03-15 | Author: ThanhAI

---

## ⚠️ Lesson learned từ trước — LUÔN nhớ

```typescript
// LUÔN guard arrays từ API với ?? []
(doc.hieu_luc_index?.hieu_luc ?? []).length   // ĐÚNG
doc.hieu_luc_index.hieu_luc.length            // SAI — crash
```

---

## Bug fix cần làm ngay: bcrypt/passlib conflict

`main.py` lifespan dùng `passlib` để hash password → crash với bcrypt version mới. Fix bằng cách dùng `bcrypt` trực tiếp:

```python
# requirements.txt: bỏ passlib, thêm bcrypt
# THAY:
# from passlib.context import CryptContext
# pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
# pw = pwd_ctx.hash(ADMIN_PASS)
# pwd_ctx.verify(password, hash)

# BẰNG:
import bcrypt
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
```

Áp dụng cho tất cả chỗ dùng `pwd_ctx` trong `main.py` và `auth.py`.

Cập nhật `requirements.txt`:
```
# Xóa: passlib==1.7.4
# Giữ: bcrypt>=4.0.0  (hoặc thêm nếu chưa có)
```

---

## 1. UI: Compact header + font size controls

### ContentPanel header — hiện chiếm 3 dòng, cần thu về 2

```typescript
// HIỆN TẠI (3 dòng):
// Line 1: tên văn bản
// Line 2: ngày, cơ quan, HieuLucBadge
// Line 3: loại thuế (sac_thue)

// MỤC TIÊU (2 dòng + font controls):
// Line 1: [tên văn bản] + [A- btn] [A+ btn] ở góc phải
// Line 2: [ngày] • [loại thuế badge] • [HieuLucBadge] — gộp tất cả vào 1 dòng, bỏ cơ quan riêng
```

**Font size buttons** (thêm vào header row 1, góc phải):
```typescript
const [fontSize, setFontSize] = useState(14); // px

// Buttons:
<div className="flex items-center gap-1 ml-auto flex-shrink-0">
  <button
    onClick={() => setFontSize(s => Math.max(11, s - 1))}
    className="px-1.5 py-0.5 text-xs border rounded hover:bg-gray-100 font-mono"
    title="Giảm font"
  >A−</button>
  <span className="text-xs text-gray-400 w-6 text-center">{fontSize}</span>
  <button
    onClick={() => setFontSize(s => Math.min(20, s + 1))}
    className="px-1.5 py-0.5 text-xs border rounded hover:bg-gray-100 font-mono"
    title="Tăng font"
  >A+</button>
</div>

// Apply to content div:
<div style={{ fontSize: `${fontSize}px` }} dangerouslySetInnerHTML={{ __html: content ?? '' }} />
```

### Hiệu lực — expandable box (1 dòng mặc định)

```typescript
const [hieuLucExpanded, setHieuLucExpanded] = useState(false);

// Collapsed (1 dòng):
<div className="border rounded-lg overflow-hidden mt-2 flex-shrink-0">
  <button
    onClick={() => setHieuLucExpanded(!hieuLucExpanded)}
    className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 text-sm"
  >
    <span className="flex items-center gap-2">
      <span className="font-medium text-gray-600">Hiệu lực</span>
      {/* Badge tóm tắt */}
      {doc.hl === 1 ? (
        <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded">✓ Còn hiệu lực</span>
      ) : (
        <span className="text-xs px-2 py-0.5 bg-red-100 text-red-700 rounded">✗ Hết hiệu lực</span>
      )}
      {/* Nếu có hieu_luc data: */}
      {(doc.hieu_luc_index?.hieu_luc ?? []).length > 0 && (
        <span className="text-xs text-gray-400">{doc.hieu_luc_index.tom_tat_hieu_luc?.slice(0,50)}</span>
      )}
    </span>
    <span className="text-gray-400">{hieuLucExpanded ? '▲' : '▼'}</span>
  </button>

  {/* Expanded: chi tiết */}
  {hieuLucExpanded && (
    <div className="px-3 py-2 border-t border-gray-100">
      {(doc.hieu_luc_index?.hieu_luc ?? []).length > 0 ? (
        <HieuLucDetail index={doc.hieu_luc_index} />
      ) : (
        <p className="text-xs text-gray-400 italic">
          Thông tin hiệu lực chi tiết đang được xử lý
        </p>
      )}
    </div>
  )}
</div>
```

---

## 2. Sidebar DANH MỤC — thêm resize

Sidebar danh mục (panel trái nhất) hiện không resize được. Thêm drag divider như các panel khác:

```typescript
// App.tsx hoặc layout component — thêm state + divider cho sidebar trái:
const [categoryW, setCategoryW] = useState(180); // px, min 120, max 280

// Render:
<div style={{ width: categoryW, minWidth: 120, maxWidth: 280 }} className="flex-shrink-0 overflow-y-auto border-r">
  <CategorySidebar ... />
</div>
<Divider onDrag={(dx) => setCategoryW(w => Math.min(280, Math.max(120, w + dx)))} />
```

---

## 3. Blank so_hieu — extract từ HTML content

Còn ~32 docs có `so_hieu` trống mà không extract được từ filename. Extract từ nội dung HTML:

```python
# Script để chạy riêng (không cần Claude Code làm):
# Pattern trong HTML: sau "Độc lập - Tự do - Hạnh phúc", sau "Số: ", trước "Hà Nội, ngày"
# Ví dụ: "Số: 94/2025/TT-BTC" → "TT 94/2025"
```

**Claude Code KHÔNG cần làm việc này** — ThanhAI sẽ chạy script riêng.

---

## 4. Auth: Signup + Forgot Password

### Signup
```typescript
// AuthModal.tsx — thêm tab "Đăng ký":
// Form: email + password + ho_ten
// POST /api/auth/register (đã có endpoint)
// Sau khi register thành công → auto login
```

### Forgot Password flow
Backend cần thêm 2 endpoints:

```python
# main.py
@app.post("/api/auth/forgot-password")
async def forgot_password(body: ForgotBody, db: AsyncSession = Depends(get_db)):
    # 1. Check email tồn tại
    # 2. Generate reset token (random 32 chars), lưu vào DB (column reset_token, expires 1h)
    # 3. Gửi email qua Mailgun SMTP
    # 4. Return {"ok": true} (không tiết lộ email có tồn tại hay không)

@app.post("/api/auth/reset-password")
async def reset_password(body: ResetBody, db: AsyncSession = Depends(get_db)):
    # 1. Verify token + chưa expire
    # 2. Hash password mới
    # 3. Update DB, xóa reset_token
```

**Email config** (dùng Mailgun SMTP — đã config trong Coolify):
```python
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.mailgun.org")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "thanhai@mg.gpt4vn.com")
SMTP_PASS = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = "ThanhAI <thanhai@mg.gpt4vn.com>"

# Thêm vào Coolify env vars (ThanhAI sẽ add):
# SMTP_HOST=smtp.mailgun.org
# SMTP_PORT=465
# SMTP_USER=thanhai@mg.gpt4vn.com
# SMTP_PASSWORD=<mailgun_password>
```

**DB migration** — thêm columns vào users table:
```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMPTZ;
```

**Frontend** — AuthModal thêm:
1. Tab "Đăng ký" (register form)
2. Link "Quên mật khẩu?" → form nhập email → POST forgot-password
3. Route `/reset-password?token=xxx` → form nhập mật khẩu mới

---

## 5. TVPL link mapping (thêm field vào DB)

**DB migration:**
```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS tvpl_url TEXT;
```

**Pattern URL TVPL:**
```
https://thuvienphapluat.vn/van-ban/<slug>-<so_hieu-normalized>.aspx
```

Ví dụ: `NĐ 132/2020/NĐ-CP` → `https://thuvienphapluat.vn/van-ban/Thue/Nghi-dinh-132-2020-ND-CP-...`

**API endpoint:**
```python
# GET /api/documents/{id} — thêm tvpl_url vào response
# Nếu tvpl_url có → hiện nút "Xem trên TVPL ↗" trong ContentPanel footer
```

**Frontend** — ContentPanel footer:
```typescript
{doc.tvpl_url && (
  <a href={doc.tvpl_url} target="_blank" rel="noopener"
     className="btn-outline text-xs">
    🔗 Xem trên TVPL ↗
  </a>
)}
```

**ThanhAI sẽ làm riêng:** populate `tvpl_url` bằng script crawl TVPL sau.

---

## ✅ Checklist Sprint 3

### Bắt buộc làm:
1. [ ] Fix bcrypt/passlib — đổi sang `import bcrypt` trực tiếp
2. [ ] ContentPanel header compact: 2 dòng + A+/A- buttons
3. [ ] Hiệu lực expandable box (collapsed = 1 dòng)
4. [ ] Sidebar DANH MỤC: thêm resize divider
5. [ ] AuthModal: thêm tab Đăng ký
6. [ ] Forgot Password: endpoint + email + frontend flow
7. [ ] DB migration: `reset_token`, `reset_token_expires`, `tvpl_url`
8. [ ] `npm run build` không lỗi
9. [ ] **Commit + push** (`git push origin main`)
10. [ ] **Xóa CLAUDE.md** sau khi push

### ThanhAI làm riêng (KHÔNG cần Claude Code):
- Populate `tvpl_url` bằng script
- Fix 32 docs blank `so_hieu` còn lại
- Thêm Coolify env vars cho SMTP
