"""
VNTaxDB — TaxKnowledge Platform
FastAPI backend + SQLAlchemy async + pgvector
"""
import os, json, logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt
import bcrypt as _bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, engine
from search import do_search, get_doc_by_id, get_cv_by_id, get_article_by_id, list_cong_van
from ai import stream_quick_analysis, stream_analyze_doc, do_factcheck, do_related

log = logging.getLogger("vntaxdb")
logging.basicConfig(level=logging.INFO)

JWT_SECRET = os.environ.get("JWT_SECRET", "vntaxdb-secret-2026")
JWT_ALGO   = "HS256"
JWT_EXP    = 30
def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(12)).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@vntaxdb.com")
ADMIN_PASS  = os.environ.get("ADMIN_PASSWORD", "VNTax@Admin2026")

# SMTP config for password reset emails
SMTP_HOST  = os.environ.get("SMTP_HOST", "smtp.mailgun.org")
SMTP_PORT  = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER  = os.environ.get("SMTP_USER", "thanhai@mg.gpt4vn.com")
SMTP_PASS  = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "ThanhAI <thanhai@mg.gpt4vn.com>")
APP_URL    = os.environ.get("APP_URL", "https://dbvntax.gpt4vn.com")

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("VNTaxDB starting...")
    # Seed admin account
    try:
        async with AsyncSession(engine) as db:
            r = await db.execute(text("SELECT id, role FROM users WHERE email=:e"), {"e": ADMIN_EMAIL})
            row = r.mappings().first()
            pw = hash_password(ADMIN_PASS)
            if not row:
                await db.execute(text("""
                    INSERT INTO users (email, password_hash, ho_ten, role, plan, query_limit)
                    VALUES (:e, :p, 'Admin', 'admin', 'unlimited', 9999)
                """), {"e": ADMIN_EMAIL, "p": pw})
                log.info(f"Admin account created: {ADMIN_EMAIL}")
            else:
                # Ensure admin role + reset password
                await db.execute(text(
                    "UPDATE users SET password_hash=:p, role='admin' WHERE email=:e"
                ), {"e": ADMIN_EMAIL, "p": pw})
                log.info(f"Admin account updated: {ADMIN_EMAIL}")
            await db.commit()
    except Exception as e:
        log.error(f"Admin seed failed (non-fatal): {e}")
    # DB migrations
    try:
        async with AsyncSession(engine) as db:
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
            await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(64)"))
            await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMPTZ"))
            await db.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS tvpl_url TEXT"))
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_documents_fts
                ON documents USING GIN (
                    to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || coalesce(ten,'') || ' ' || coalesce(tom_tat,'')))
                )
            """))
            await db.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_cong_van_fts
                ON cong_van USING GIN (
                    to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || ten))
                )
            """))
            await db.commit()
            log.info("DB migrations applied")
    except Exception as e:
        log.error(f"DB migration failed (non-fatal): {e}")
    yield
    await engine.dispose()

app = FastAPI(title="VNTaxDB", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def create_token(user_id: int, email: str, role: str) -> str:
    payload = {"sub": str(user_id), "email": email, "role": role,
               "exp": datetime.utcnow() + timedelta(days=JWT_EXP)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        raise HTTPException(401, "Token không hợp lệ hoặc đã hết hạn")

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Chưa đăng nhập")
    payload = decode_token(auth[7:])
    r = await db.execute(text("SELECT id, email, ho_ten, role, plan, query_count, query_limit FROM users WHERE id=:id"),
                         {"id": int(payload["sub"])})
    u = r.mappings().first()
    if not u:
        raise HTTPException(401, "Người dùng không tồn tại")
    return dict(u)

async def get_optional_user(request: Request, db: AsyncSession = Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = decode_token(auth[7:])
        r = await db.execute(text("SELECT id, email, ho_ten, role, plan, query_count, query_limit FROM users WHERE id=:id"),
                             {"id": int(payload["sub"])})
        u = r.mappings().first()
        return dict(u) if u else None
    except:
        return None

async def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền này")
    return user

async def log_query(db, user_id, query_text, query_type, results_count=0, tokens_used=0):
    try:
        await db.execute(text("""
            INSERT INTO query_log (user_id, query_text, query_type, results_count, tokens_used, cost_usd)
            VALUES (:uid, :q, :t, :r, :tok, :cost)
        """), {"uid": user_id, "q": query_text[:500], "t": query_type,
               "r": results_count, "tok": tokens_used, "cost": tokens_used * 0.000002})
        await db.commit()
    except:
        pass

class RegisterBody(BaseModel):
    email: str
    password: str
    ho_ten: Optional[str] = ""

class LoginBody(BaseModel):
    email: str
    password: str

class SetPasswordBody(BaseModel):
    email: str
    new_password: str

class ForgotPasswordBody(BaseModel):
    email: str

class ResetPasswordBody(BaseModel):
    token: str
    new_password: str

class QuickAnalysisBody(BaseModel):
    question: str
    context_ids: Optional[List[dict]] = []

class AnalyzeDocBody(BaseModel):
    source: str
    id: int

class FactcheckBody(BaseModel):
    text: str

class RelatedBody(BaseModel):
    source: str
    id: int

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    r = await db.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM documents) AS docs,
          (SELECT COUNT(*) FROM cong_van)  AS cvs,
          (SELECT COUNT(*) FROM articles)  AS arts
    """))
    row = r.mappings().first()
    return {"status": "ok", "documents": row["docs"], "cong_van": row["cvs"], "articles": row["arts"]}

@app.post("/api/auth/register")
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    r = await db.execute(text("SELECT id FROM users WHERE email=:e"), {"e": body.email})
    if r.first():
        raise HTTPException(400, "Email đã tồn tại")
    pw = hash_password(body.password)
    r2 = await db.execute(text("""
        INSERT INTO users (email, password_hash, ho_ten, role, plan, query_limit)
        VALUES (:e, :p, :n, 'user', 'free', 50) RETURNING id, role
    """), {"e": body.email, "p": pw, "n": body.ho_ten or ""})
    row = r2.mappings().first()
    await db.commit()
    token = create_token(row["id"], body.email, row["role"])
    return {"token": token, "user": {"id": row["id"], "email": body.email, "ho_ten": body.ho_ten, "role": row["role"]}}

@app.post("/api/auth/login")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    r = await db.execute(text("SELECT id, password_hash, ho_ten, role, plan FROM users WHERE email=:e"), {"e": body.email})
    u = r.mappings().first()
    if not u:
        raise HTTPException(401, "Email không tồn tại")
    if not u["password_hash"] or not verify_password(body.password, u["password_hash"]):
        raise HTTPException(401, "Sai mật khẩu")
    await db.execute(text("UPDATE users SET last_active=NOW() WHERE id=:id"), {"id": u["id"]})
    await db.commit()
    token = create_token(u["id"], body.email, u["role"])
    return {"token": token, "user": {"id": u["id"], "email": body.email, "ho_ten": u["ho_ten"], "role": u["role"], "plan": u["plan"]}}

@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    return {"user": user}

@app.post("/api/auth/set-password")
async def set_password(body: SetPasswordBody, db: AsyncSession = Depends(get_db)):
    pw = hash_password(body.new_password)
    r = await db.execute(text("UPDATE users SET password_hash=:p WHERE email=:e RETURNING id"), {"p": pw, "e": body.email})
    if not r.first():
        raise HTTPException(404, "Email không tồn tại")
    await db.commit()
    return {"message": "Đặt mật khẩu thành công"}

@app.post("/api/auth/forgot-password")
async def forgot_password(body: ForgotPasswordBody, db: AsyncSession = Depends(get_db)):
    """Generate reset token and send email. Always returns ok to not leak email existence."""
    import secrets, smtplib
    from email.mime.text import MIMEText
    r = await db.execute(text("SELECT id FROM users WHERE email=:e"), {"e": body.email})
    user = r.first()
    if user:
        token = secrets.token_urlsafe(32)
        await db.execute(text("""
            UPDATE users SET reset_token=:t, reset_token_expires=NOW() + INTERVAL '1 hour'
            WHERE email=:e
        """), {"t": token, "e": body.email})
        await db.commit()
        # Send email
        if SMTP_PASS:
            try:
                reset_url = f"{APP_URL}/reset-password?token={token}"
                msg = MIMEText(
                    f"Xin chào,\n\nBạn đã yêu cầu đặt lại mật khẩu VNTaxDB.\n\n"
                    f"Nhấn vào link sau để đặt mật khẩu mới:\n{reset_url}\n\n"
                    f"Link có hiệu lực trong 1 giờ.\n\n"
                    f"Nếu bạn không yêu cầu, vui lòng bỏ qua email này.\n\n"
                    f"— VNTaxDB",
                    "plain", "utf-8"
                )
                msg["Subject"] = "Đặt lại mật khẩu VNTaxDB"
                msg["From"] = EMAIL_FROM
                msg["To"] = body.email
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
                    smtp.login(SMTP_USER, SMTP_PASS)
                    smtp.send_message(msg)
                log.info(f"Reset email sent to {body.email}")
            except Exception as e:
                log.error(f"Failed to send reset email: {e}")
        else:
            log.warning(f"SMTP not configured. Reset token for {body.email}: {token}")
    return {"ok": True}

@app.post("/api/auth/reset-password")
async def reset_password(body: ResetPasswordBody, db: AsyncSession = Depends(get_db)):
    r = await db.execute(text("""
        SELECT id, email FROM users
        WHERE reset_token=:t AND reset_token_expires > NOW()
    """), {"t": body.token})
    user = r.mappings().first()
    if not user:
        raise HTTPException(400, "Link đã hết hạn hoặc không hợp lệ")
    pw = hash_password(body.new_password)
    await db.execute(text("""
        UPDATE users SET password_hash=:p, reset_token=NULL, reset_token_expires=NULL
        WHERE id=:id
    """), {"p": pw, "id": user["id"]})
    await db.commit()
    return {"message": "Đặt mật khẩu mới thành công. Vui lòng đăng nhập lại."}

@app.get("/api/categories")
async def categories(db: AsyncSession = Depends(get_db)):
    r = await db.execute(text("""
        SELECT unnest(sac_thue) AS code, COUNT(*) AS count
        FROM documents
        GROUP BY code ORDER BY count DESC
    """))
    # Canonical codes & display order (sidebar)
    CANONICAL = [
        ('QLT',     'Quản lý thuế'),
        ('CIT',     'Thuế TNDN'),
        ('VAT',     'Thuế GTGT'),
        ('HDDT',    'Hóa đơn điện tử'),
        ('PIT',     'Thuế TNCN'),
        ('SCT',     'Thuế TTĐB'),
        ('FCT',     'Thuế nhà thầu'),
        ('TP',      'Giao dịch liên kết'),
        ('HKD',     'Hộ kinh doanh'),
        ('THUE_QT', 'Thuế Quốc tế'),
    ]
    # Alias map: raw DB code → canonical code
    ALIAS = {
        'TNDN': 'CIT', 'GTGT': 'VAT', 'HOA_DON': 'HDDT',
        'TNCN': 'PIT', 'TTDB': 'SCT', 'NHA_THAU': 'FCT', 'GDLK': 'TP',
        'TAI_NGUYEN': 'THUE_QT',
    }
    # Aggregate counts by canonical code
    counts: dict = {}
    for row in r.mappings().all():
        code = ALIAS.get(row["code"], row["code"])
        counts[code] = counts.get(code, 0) + row["count"]
    return [
        {"code": code, "name": name, "count": counts.get(code, 0)}
        for code, name in CANONICAL
        if counts.get(code, 0) > 0
    ]

@app.get("/api/search")
async def search(
    q: str = "", type: str = "all",
    sac_thue: Optional[str] = None, loai: Optional[str] = None,
    year_from: Optional[int] = None, year_to: Optional[int] = None,
    tinh_trang: Optional[str] = None, hl: Optional[int] = None,
    date_at: Optional[str] = None, mode: str = "hybrid",
    limit: int = Query(20, le=100), offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    filters = {"sac_thue": sac_thue, "loai": loai,
               "year_from": year_from, "year_to": year_to, "tinh_trang": tinh_trang,
               "hl": hl, "date_at": date_at}
    results, total = await do_search(db, q, type, filters, mode, limit, offset)
    if user and q:
        await log_query(db, user["id"], q, f"search_{mode}", total)
    return {"total": total, "results": results, "q": q, "mode": mode}

@app.get("/api/documents")
async def documents_list(
    q: str = "",
    category: Optional[str] = None,    # sac_thue code e.g. "CIT","VAT"
    loai: Optional[str] = None,         # TT/ND/Luat/VBHN/QD/NQ/CV
    hl: Optional[int] = None,           # 1=còn HL, 0=hết HL
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * limit
    # Map canonical frontend code → actual DB sac_thue code
    CANONICAL_TO_DB = {
        'CIT': 'TNDN', 'VAT': 'GTGT', 'HDDT': 'HOA_DON',
        'PIT': 'TNCN', 'SCT': 'TTDB', 'FCT': 'FCT',
        'TP':  'GDLK', 'HKD': 'HKD',  'QLT': 'QLT', 'THUE_QT': 'THUE_QT',
    }
    db_sac_thue = CANONICAL_TO_DB.get(category, category) if category else None
    filters = {"sac_thue": db_sac_thue, "loai": loai, "hl": hl,
               "year_from": year_from, "year_to": year_to}
    results, total = await do_search(db, q, "documents", filters, "keyword", limit, offset)
    return {"items": results, "total": total, "page": page, "limit": limit}

@app.get("/api/documents/{doc_id}")
async def doc_detail(doc_id: int, db: AsyncSession = Depends(get_db)):
    d = await get_doc_by_id(db, doc_id)
    if not d: raise HTTPException(404, "Không tìm thấy văn bản")
    return d

@app.get("/api/cong-van/taxonomy")
async def cong_van_taxonomy(
    sac_thue: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    where_parts = ["cd IS NOT NULL AND cd != ''"]
    params: dict = {}
    if sac_thue:
        where_parts.append(":sac_thue = ANY(sac_thue)")
        params["sac_thue"] = sac_thue

    where_clause = "WHERE " + " AND ".join(where_parts)

    r = await db.execute(text(f"""
        SELECT
            st  AS sac_thue,
            cd  AS chu_de,
            COUNT(*) AS count
        FROM cong_van
        CROSS JOIN LATERAL unnest(sac_thue) AS st
        CROSS JOIN LATERAL unnest(chu_de)   AS cd
        {where_clause}
        GROUP BY st, cd
        ORDER BY st, count DESC
    """), params)

    rows = r.mappings().all()
    result: dict[str, list] = {}
    for row in rows:
        st = row["sac_thue"]
        if st not in result:
            result[st] = []
        result[st].append({"chu_de": row["chu_de"], "count": row["count"]})
    return result

@app.get("/api/cong-van")
async def cong_van_list(
    q: str = "", sac_thue: Optional[str] = None, nguon: Optional[str] = None,
    chu_de: Optional[str] = None, tinh_trang: Optional[str] = None,
    year_from: Optional[int] = None, year_to: Optional[int] = None,
    limit: int = Query(20, le=100), offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    results, total = await list_cong_van(
        db, q, sac_thue, nguon, limit, offset,
        year_from=year_from, year_to=year_to,
        chu_de=chu_de, tinh_trang=tinh_trang,
    )
    return {"total": total, "items": results}

@app.get("/api/cong_van/{cv_id}")
async def cv_detail(cv_id: int, db: AsyncSession = Depends(get_db)):
    d = await get_cv_by_id(db, cv_id)
    if not d: raise HTTPException(404, "Không tìm thấy công văn")
    return d

@app.get("/api/articles/{art_id}")
async def article_detail(art_id: int, db: AsyncSession = Depends(get_db)):
    d = await get_article_by_id(db, art_id)
    if not d: raise HTTPException(404, "Không tìm thấy bài viết")
    return d

@app.post("/api/ai/quick-analysis")
async def quick_analysis(body: QuickAnalysisBody, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    if user["plan"] == "free" and user["query_count"] >= user["query_limit"]:
        raise HTTPException(429, f"Đã dùng hết {user['query_limit']} lượt.")
    async def gen():
        async for chunk in stream_quick_analysis(db, body.question, body.context_ids or []):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        await db.execute(text("UPDATE users SET query_count=query_count+1 WHERE id=:id"), {"id": user["id"]})
        await db.commit()
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/api/ai/analyze-document")
async def analyze_document(body: AnalyzeDocBody, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    async def gen():
        async for chunk in stream_analyze_doc(db, body.source, body.id):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        await db.execute(text("UPDATE users SET query_count=query_count+1 WHERE id=:id"), {"id": user["id"]})
        await db.commit()
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/api/ai/factcheck")
async def factcheck(body: FactcheckBody, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await do_factcheck(db, body.text)
    await log_query(db, user["id"], body.text[:100], "factcheck", len(result.get("citations", [])))
    return result

@app.post("/api/ai/related")
async def related(body: RelatedBody, db: AsyncSession = Depends(get_db)):
    return await do_related(db, body.source, body.id)

@app.get("/api/admin/stats")
async def admin_stats(db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    r = await db.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM documents) AS docs,
          (SELECT COUNT(*) FROM cong_van)  AS cvs,
          (SELECT COUNT(*) FROM articles)  AS arts,
          (SELECT COUNT(*) FROM users)     AS users_total,
          (SELECT COUNT(*) FROM query_log WHERE created_at > NOW() - INTERVAL '1 day') AS queries_today
    """))
    return dict(r.mappings().first())

import os as _os
from fastapi.responses import FileResponse as _FileResponse

# Serve static assets (JS/CSS bundles)
if _os.path.isdir("static/assets"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

# SPA fallback — all non-API routes return index.html
@app.get("/")
async def spa_root():
    return _FileResponse("static/index.html")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # Don't intercept API routes (return 404 via normal FastAPI handling)
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    index = "static/index.html"
    if _os.path.exists(index):
        return _FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built")
