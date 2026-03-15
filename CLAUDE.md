# CLAUDE.md — dbvntax: Redeploy để apply ai.py fix
> Version: 2.3 | Date: 2026-03-15

## Chỉ 1 việc: Rebuild + redeploy Docker image

### Context
`ai.py` và `requirements.txt` vừa được cập nhật (Anthropic SDK → AsyncOpenAI).
Claude Code **không cần sửa code gì** — chỉ cần trigger rebuild để Docker image cài đúng dependencies.

### Làm theo thứ tự:

**1. Verify requirements.txt đúng (không có anthropic):**
```bash
cat requirements.txt | grep -E "openai|anthropic"
# Expected: chỉ thấy openai==1.51.0, KHÔNG thấy anthropic
```

**2. Verify ai.py dùng AsyncOpenAI:**
```bash
head -15 ai.py
# Expected: "from openai import AsyncOpenAI", KHÔNG thấy "import anthropic"
```

**3. Commit empty trigger nếu cần:**
```bash
# Nếu chưa có gì để commit, tạo 1 commit nhỏ để trigger Coolify rebuild:
git commit --allow-empty -m "chore: trigger rebuild for ai.py AsyncOpenAI fix"
git push origin main
```

**4. Xóa CLAUDE.md rồi push:**
```bash
rm CLAUDE.md
git add -A && git commit -m "chore: remove CLAUDE.md" && git push
```

Coolify sẽ tự động detect push → rebuild Docker image với requirements mới → redeploy.

---
*Không cần sửa bất kỳ file code nào khác.*
