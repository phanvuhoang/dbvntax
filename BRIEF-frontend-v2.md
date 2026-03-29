# BRIEF: dbvntax Frontend Enhancement + RAG UI

## Context
- **Repo:** github.com/phanvuhoang/dbvntax
- **Stack:** React + TypeScript + Vite + Tailwind CSS
- **Backend:** FastAPI tại https://dbvntax.gpt4vn.com
- **Đọc code hiện tại trước** để hiểu structure, đừng rewrite những gì đang work

---

## Task 1: Thêm tab "Hỏi đáp AI" (RAG)

### API đã có sẵn:
```
POST /api/ask
Body: { "question": "string", "top_k": 15 }
Response: {
  "question": "...",
  "answer": "...",
  "model_used": "claudible/claude-haiku-4-5",
  "sources_count": 10,
  "sources": [{ "so_hieu", "ten", "ngay_ban_hanh", "link_nguon", "score" }]
}
```

### UI cần làm:
- Thêm tab "🤖 Hỏi đáp AI" vào navigation chính (cạnh tab Văn bản / Công văn)
- **Input area:** textarea lớn, placeholder "Nhập câu hỏi thuế... ví dụ: Dịch vụ xuất khẩu nào được thuế suất GTGT 0%?"
- **Button:** "Hỏi" — loading spinner khi đang xử lý
- **Answer box:** hiển thị answer với markdown rendering (xuống dòng, bold, list)
- **Sources panel:** danh sách CV nguồn dạng cards nhỏ, mỗi card:
  - so_hieu (bold) + ten (truncate 80 chars)
  - ngay_ban_hanh + score badge (color theo score: xanh ≥0.7, vàng 0.5-0.7)
  - link_nguon → click mở tab mới
- **Example questions:** 4-5 câu hỏi mẫu dạng chips, click để fill vào textarea:
  - "Dịch vụ xuất khẩu nào được thuế suất GTGT 0%?"
  - "Chi phí trả phí dịch vụ cho công ty mẹ nước ngoài có được trừ không?"
  - "Điều kiện để được ưu đãi thuế TNDN cho dự án đầu tư mới?"
  - "Thuế nhà thầu áp dụng khi nào? Cách tính như thế nào?"
  - "Transfer pricing — hồ sơ xác định giá giao dịch liên kết cần gì?"
- **Error handling:** hiển thị friendly error nếu API fail

---

## Task 2: Sort search results

Trong tab Văn bản và Công văn, khi có search query, thêm dropdown sort:
- **"Liên quan nhất"** (default khi search) — sort by score DESC
- **"Mới nhất"** — sort by ngay_ban_hanh DESC
- **"Cũ nhất"** — sort by ngay_ban_hanh ASC

API đã support `sort` param: `?sort=relevance|date_desc|date_asc`
(Nếu backend chưa có, thêm sort param vào API calls; frontend có thể sort client-side nếu cần)

---

## Task 3: Jump-to-page pagination

Thay pagination hiện tại (chỉ có Prev/Next) bằng:
```
[Prev]  [1] [2] ... [5] [6] [7] ... [20] [Next]   Đến trang: [__] [Go]
```
- Hiển thị tối đa 7 page buttons (first, last, current ±2, dấu ...)
- Ô "Đến trang" — nhập số → Enter hoặc click Go → nhảy thẳng đến trang đó
- Validate: không cho nhập ngoài range 1-totalPages

---

## Task 4: Date picker cải tiến

Thay input date text thuần bằng component hỗ trợ **cả gõ tay lẫn calendar picker**:
- Dùng `<input type="date">` native (hỗ trợ cả keyboard và calendar popup)
- Format hiển thị: DD/MM/YYYY (locale VN)
- **Fix bug quan trọng:** Filter hiện tại lọc theo năm thay vì ngày cụ thể
  - API params đang dùng: `year_from`, `year_to` (chỉ theo năm)
  - Cần đổi thành: `date_from=YYYY-MM-DD`, `date_to=YYYY-MM-DD`
  - **Update backend** `main.py` + `search.py` để accept `date_from`/`date_to` thay `year_from`/`year_to`
  - DB query: `ngay_ban_hanh >= :date_from AND ngay_ban_hanh <= :date_to`

---

## Task 5: Gợi ý UX thêm (implement nếu còn time)

### 5a. Search suggestions / autocomplete
- Khi gõ vào search box, suggest các cụm từ phổ biến liên quan (hardcode 20-30 cụm)
- Ví dụ: "thuế GTGT", "thuế TNDN", "nhà thầu nước ngoài", "transfer pricing"...

### 5b. Recent searches
- Lưu 5 query gần nhất vào localStorage
- Hiển thị dưới search box khi focus

### 5c. Score badge trên search results
- Khi đang search (mode=semantic), hiển thị score badge nhỏ trên mỗi card kết quả
- Color: xanh lá (≥0.7), xanh dương (0.6-0.7), vàng (0.5-0.6)
- Tooltip: "Độ liên quan: XX%"

### 5d. "Hỏi AI về văn bản này" button
- Trên mỗi CV card trong search results, thêm button nhỏ "🤖 Hỏi AI"
- Click → chuyển sang tab Hỏi đáp AI với câu hỏi pre-filled:
  "Giải thích nội dung của công văn [so_hieu]: [ten]"

---

## Important notes
- Đọc `src/api.ts` trước để hiểu interfaces hiện tại
- Không xóa/rewrite code đang work, chỉ extend
- Dùng Tailwind classes nhất quán với existing code
- Test build (`npm run build`) trước khi commit
- Commit message: "feat: RAG ask UI + sort + pagination + date picker improvements"
- **Sau khi commit + push, XÓA file BRIEF này**
