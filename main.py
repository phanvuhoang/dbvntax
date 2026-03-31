"""
VNTaxDB — TaxKnowledge Platform
FastAPI backend + SQLAlchemy async + pgvector
"""
import os, json, logging, asyncio
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
from search import (
    do_search, get_doc_by_id, get_cv_by_id, get_article_by_id,
    list_cong_van, search_semantic_cv,
    search_semantic_docs_for_rag,
    search_multi_query_docs,
    search_hybrid_cv,
)
from rag import rag_answer, analyze_intent, load_anchor_docs
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
            await db.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_anchor BOOLEAN DEFAULT FALSE"))
            await db.execute(text("CREATE INDEX IF NOT EXISTS idx_documents_anchor ON documents(is_anchor, sac_thue) WHERE is_anchor = TRUE"))
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

class BulkDeleteRequest(BaseModel):
    ids: List[int]
    source: str  # "documents" or "cong_van"

class CorpusImportRequest(BaseModel):
    paths: List[str]

class TVPLImportRequest(BaseModel):
    url: str
    html_content: Optional[str] = None
    loai_override: Optional[str] = None
    sac_thue_override: Optional[List[str]] = None

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
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    tinh_trang: Optional[str] = None, hl: Optional[int] = None,
    date_at: Optional[str] = None, mode: str = "hybrid",
    limit: int = Query(20, le=100), offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_optional_user),
):
    filters = {"sac_thue": sac_thue, "loai": loai,
               "year_from": year_from, "year_to": year_to,
               "date_from": date_from, "date_to": date_to,
               "tinh_trang": tinh_trang, "hl": hl, "date_at": date_at}
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
    date_from: Optional[str] = None, date_to: Optional[str] = None,
    mode: Optional[str] = None,
    limit: int = Query(20, le=100), offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if q and mode in ("semantic", "hybrid"):
        filters = {}
        if sac_thue: filters["sac_thue"] = sac_thue
        if date_from: filters["date_from"] = date_from
        elif year_from: filters["year_from"] = year_from
        if date_to: filters["date_to"] = date_to
        elif year_to: filters["year_to"] = year_to
        results, total = await search_semantic_cv(db, q, filters, limit, offset)
        return {"total": total, "items": results}
    results, total = await list_cong_van(
        db, q, sac_thue, nguon, limit, offset,
        year_from=year_from, year_to=year_to,
        chu_de=chu_de, tinh_trang=tinh_trang,
        date_from=date_from, date_to=date_to,
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

@app.delete("/api/admin/documents")
async def bulk_delete_docs(
    req: BulkDeleteRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if req.source not in ("documents", "cong_van"):
        raise HTTPException(400, "Invalid source")
    if not req.ids:
        raise HTTPException(400, "No ids provided")
    table = "documents" if req.source == "documents" else "cong_van"
    result = await db.execute(
        text(f"DELETE FROM {table} WHERE id = ANY(:ids) RETURNING id"),
        {"ids": req.ids}
    )
    deleted = [r[0] for r in result.fetchall()]
    await db.commit()
    return {"deleted": deleted, "count": len(deleted)}

@app.get("/api/admin/corpus-new")
async def corpus_new_docs(
    since: Optional[str] = None,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import httpx
    if not since:
        r = await db.execute(text("SELECT MAX(import_date)::date FROM documents"))
        max_date = r.scalar()
        since = str(max_date) if max_date else "2026-03-25"

    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    url = f"https://api.github.com/repos/phanvuhoang/vn-tax-corpus/commits?since={since}T00:00:00Z&per_page=100"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
    commits = resp.json() if resp.status_code == 200 else []

    changed_paths: set = set()
    for commit in commits[:20]:
        sha = commit["sha"]
        async with httpx.AsyncClient(timeout=30) as client:
            detail = (await client.get(
                f"https://api.github.com/repos/phanvuhoang/vn-tax-corpus/commits/{sha}",
                headers=headers
            )).json()
        for f in detail.get("files", []):
            fname = f.get("filename", "")
            if fname.startswith("docs/") and fname.endswith(".html"):
                changed_paths.add(fname[5:])

    if not changed_paths:
        return {"items": [], "since": since, "total": 0}

    r = await db.execute(text("SELECT github_path FROM documents"))
    existing = {row[0] for row in r.fetchall() if row[0]}
    r2 = await db.execute(text("SELECT github_path FROM cong_van"))
    existing |= {row[0] for row in r2.fetchall() if row[0]}
    new_paths = [p for p in changed_paths if p not in existing]

    async with httpx.AsyncClient(timeout=30) as client:
        index_raw = (await client.get(
            "https://raw.githubusercontent.com/phanvuhoang/vn-tax-corpus/main/index.json"
        )).json()
    path_map = {item.get("p", ""): item for item in index_raw if item.get("p")}

    items = []
    for path in new_paths:
        meta = path_map.get(path, {})
        items.append({
            "github_path": path,
            "name": meta.get("n", path.split("/")[-1]),
            "so_hieu": meta.get("so_hieu", ""),
            "loai": meta.get("t", ""),
            "tx": meta.get("tx", ""),
            "date_id": meta.get("id", ""),
        })
    items.sort(key=lambda x: x.get("date_id", "") or "", reverse=True)
    return {"items": items, "since": since, "total": len(items)}


@app.post("/api/admin/corpus-import")
async def corpus_import(
    req: CorpusImportRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    import httpx, re
    from bs4 import BeautifulSoup

    async with httpx.AsyncClient(timeout=30) as client:
        index_raw = (await client.get(
            "https://raw.githubusercontent.com/phanvuhoang/vn-tax-corpus/main/index.json"
        )).json()
    path_map = {item.get("p", ""): item for item in index_raw if item.get("p")}

    TYPE_MAP = {"NĐ": "ND", "Nghị định": "ND", "TT": "TT", "Luật": "Luat",
                "VBHN": "VBHN", "QĐ": "QD", "NQ": "NQ", "CV": "CV", "Khác": "Khac"}
    TX_MAP = {"TNDN": "TNDN", "GTGT": "GTGT", "TNCN": "TNCN", "TTDB": "TTDB",
              "NhaThau": "FCT", "GDLK": "GDLK", "QLT": "QLT", "HoaDon": "HOA_DON",
              "HKD": "HKD", "CIT": "TNDN"}
    IMP_MAP = {"ND": 1, "TT": 1, "Luat": 2, "VBHN": 2, "NQ": 2, "QD": 3, "CV": 4, "Khac": 3}

    results = []
    for path in req.paths:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://raw.githubusercontent.com/phanvuhoang/vn-tax-corpus/main/docs/{path}"
                )
            if resp.status_code != 200:
                results.append({"path": path, "status": "error", "msg": f"HTTP {resp.status_code}"})
                continue

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text("\n", strip=True)
            meta = path_map.get(path, {})
            name = meta.get("n", "").strip()
            so_hieu = meta.get("so_hieu") or ""
            if not so_hieu:
                m = re.search(r'(\d{1,5}/\d{4}/[\wĐ\-]+)', name)
                if m:
                    so_hieu = m.group(1)

            date_match = re.search(
                r'[Hh]à\s*[Nn]ội[,\s]+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(20\d{2})',
                text_content
            )
            if date_match:
                d, mo, y = date_match.groups()
                ngay_ban_hanh = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
            else:
                date_id = str(meta.get("id", "") or "")
                ngay_ban_hanh = f"{date_id[:4]}-{date_id[4:6]}-{date_id[6:8]}" if len(date_id) == 8 else None

            loai = TYPE_MAP.get(meta.get("t", ""), "Khac")
            tx = meta.get("tx", "")
            sac_thue = [TX_MAP[tx]] if tx in TX_MAP else ["QLT"]
            importance = IMP_MAP.get(loai, 3)
            content_div = soup.find("div", id="divContentDoc") or soup.find("body")
            noi_dung = str(content_div) if content_div else html
            tvpl_url = f"https://thuvienphapluat.vn/van-ban/{path.replace('/', '-')}"

            if loai == "CV":
                await db.execute(text("""
                    INSERT INTO cong_van (so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, chu_de,
                        nguon, link_nguon, github_path, doc_type, importance, import_date, keywords, noi_dung)
                    VALUES (:so_hieu, :ten, 'Tổng cục Thuế', :ngay::date, :sac_thue, '{}',
                        'corpus', :github_path, :github_path, 'congvan', :importance, NOW(), '{}', :noi_dung)
                    ON CONFLICT (link_nguon) DO NOTHING
                """), {"so_hieu": so_hieu, "ten": name, "ngay": ngay_ban_hanh,
                       "sac_thue": sac_thue, "github_path": path, "importance": importance, "noi_dung": noi_dung})
            else:
                await db.execute(text("""
                    INSERT INTO documents (so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
                        github_path, doc_type, importance, import_date, keywords, noi_dung, tvpl_url)
                    VALUES (:so_hieu, :ten, :loai, :ngay::date, 'con_hieu_luc', :sac_thue,
                        :github_path, 'vanban', :importance, NOW(), '{}', :noi_dung, :tvpl_url)
                    ON CONFLICT (github_path) DO NOTHING
                """), {"so_hieu": so_hieu, "ten": name, "loai": loai, "ngay": ngay_ban_hanh,
                       "sac_thue": sac_thue, "github_path": path, "importance": importance,
                       "noi_dung": noi_dung, "tvpl_url": tvpl_url})
            await db.commit()
            results.append({"path": path, "status": "ok", "so_hieu": so_hieu, "ten": name[:60]})
        except Exception as e:
            results.append({"path": path, "status": "error", "msg": str(e)})

    return {"results": results}


async def _parse_tvpl(url: str, html_content: Optional[str], loai_override: Optional[str], sac_thue_override: Optional[List[str]]):
    """Shared parse logic for tvpl-preview and tvpl-import."""
    import httpx, re, hashlib
    from bs4 import BeautifulSoup

    html = html_content
    fetch_error = None
    if not html:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36",
                "Accept-Language": "vi-VN,vi;q=0.9",
            }
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                html = resp.text
            else:
                fetch_error = f"HTTP {resp.status_code}"
        except Exception as e:
            fetch_error = str(e)

    if not html:
        return None, fetch_error

    soup = BeautifulSoup(html, "html.parser")
    text_content = soup.get_text("\n", strip=True)
    lines = [l.strip() for l in text_content.split("\n") if l.strip()]

    so_hieu = ""
    for line in lines[:50]:
        m = re.search(r'Số:\s*(\d{1,5}/\d{4}/[\wĐ\-]+)', line)
        if m:
            so_hieu = m.group(1)
            break

    title = ""
    for i, line in enumerate(lines[:80]):
        if line.upper() in ("NGHỊ ĐỊNH", "THÔNG TƯ", "LUẬT", "QUYẾT ĐỊNH", "NGHỊ QUYẾT", "VĂN BẢN HỢP NHẤT"):
            title_parts = []
            for j in range(i + 1, min(i + 6, len(lines))):
                if lines[j] and not lines[j].startswith("Căn cứ"):
                    title_parts.append(lines[j])
                else:
                    break
            title = " ".join(title_parts).strip()
            break
    if not title and so_hieu:
        title = so_hieu

    loai = loai_override or "Khac"
    if not loai_override:
        url_lower = url.lower()
        if "nghi-dinh" in url_lower or "/nd-" in so_hieu.lower():
            loai = "ND"
        elif "thong-tu" in url_lower or "/tt-" in so_hieu.lower():
            loai = "TT"
        elif "luat" in url_lower:
            loai = "Luat"
        elif "quyet-dinh" in url_lower:
            loai = "QD"
        elif "nghi-quyet" in url_lower:
            loai = "NQ"
        elif "van-ban-hop-nhat" in url_lower:
            loai = "VBHN"
        elif "cong-van" in url_lower or "chi-thi" in url_lower:
            loai = "CV"

    type_prefix = {"ND": "NĐ", "TT": "TT", "Luat": "Luật", "VBHN": "VBHN"}
    pfx = type_prefix.get(loai, "")
    ten = f"{pfx} {so_hieu} — {title}".strip(" —") if so_hieu else title

    date_match = re.search(
        r'[Hh]à\s*[Nn]ội[,\s]+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(20\d{2})',
        text_content
    )
    ngay_ban_hanh = None
    if date_match:
        d, mo, y = date_match.groups()
        ngay_ban_hanh = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"

    sac_thue = sac_thue_override or []
    if not sac_thue:
        KEYWORDS = {
            "TNDN": ["thu nhập doanh nghiệp", "tndn"],
            "GTGT": ["giá trị gia tăng", "gtgt", "vat"],
            "TNCN": ["thu nhập cá nhân", "tncn"],
            "TTDB": ["tiêu thụ đặc biệt", "ttdb", "ttđb"],
            "FCT": ["nhà thầu nước ngoài", "nhà thầu"],
            "GDLK": ["giao dịch liên kết", "chuyển giá"],
            "QLT": ["quản lý thuế", "kê khai", "nộp thuế"],
            "HOA_DON": ["hóa đơn điện tử", "hóa đơn"],
            "HKD": ["hộ kinh doanh"],
            "XNK": ["xuất nhập khẩu", "hải quan"],
        }
        text_lower = text_content[:2000].lower()
        for code, kws in KEYWORDS.items():
            if any(kw in text_lower for kw in kws):
                sac_thue.append(code)
        if not sac_thue:
            sac_thue = ["QLT"]

    IMP_MAP = {"ND": 1, "TT": 1, "Luat": 2, "VBHN": 2, "NQ": 2, "QD": 3, "CV": 4, "Khac": 3}
    importance = IMP_MAP.get(loai, 3)

    content_div = soup.find("div", id="divContentDoc") or soup.find("body")
    noi_dung = str(content_div) if content_div else html
    noi_dung = re.sub(r'width:\s*\d+\.?\d*(pt|px|%)\s*;?\s*', '', noi_dung)
    noi_dung = re.sub(r'float:\s*\w+\s*;?\s*', '', noi_dung)

    url_slug = url.split("/van-ban/")[-1].split(".aspx")[0] if "/van-ban/" in url else __import__('hashlib').md5(url.encode()).hexdigest()[:16]
    github_path = f"tvpl/{url_slug}.html"

    return {
        "so_hieu": so_hieu, "ten": ten, "loai": loai,
        "ngay_ban_hanh": ngay_ban_hanh, "sac_thue": sac_thue,
        "importance": importance, "noi_dung": noi_dung, "github_path": github_path,
    }, None


@app.post("/api/admin/tvpl-preview")
async def tvpl_preview(req: TVPLImportRequest, current_user=Depends(require_admin)):
    parsed, err = await _parse_tvpl(req.url, req.html_content, req.loai_override, req.sac_thue_override)
    if err:
        return {"status": "error", "msg": f"Không fetch được TVPL: {err}. Vui lòng paste HTML thủ công."}
    return {"status": "ok", **{k: parsed[k] for k in ("so_hieu", "ten", "loai", "ngay_ban_hanh", "sac_thue")}}


@app.post("/api/admin/tvpl-import")
async def tvpl_import(
    req: TVPLImportRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    parsed, err = await _parse_tvpl(req.url, req.html_content, req.loai_override, req.sac_thue_override)
    if err:
        return {"status": "error", "msg": f"Không fetch được: {err}. Vui lòng paste HTML thủ công."}

    so_hieu = parsed["so_hieu"]
    ten = parsed["ten"]
    loai = parsed["loai"]
    ngay_ban_hanh = parsed["ngay_ban_hanh"]
    sac_thue = parsed["sac_thue"]
    importance = parsed["importance"]
    noi_dung = parsed["noi_dung"]
    github_path = parsed["github_path"]

    try:
        if loai == "CV":
            await db.execute(text("""
                INSERT INTO cong_van (so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, chu_de,
                    nguon, link_nguon, github_path, doc_type, importance, import_date, keywords, noi_dung, link_tvpl)
                VALUES (:so_hieu, :ten, 'Tổng cục Thuế', :ngay::date, :sac_thue, '{}',
                    'tvpl', :url, :github_path, 'congvan', :importance, NOW(), '{}', :noi_dung, :url)
                ON CONFLICT (link_nguon) DO NOTHING
            """), {"so_hieu": so_hieu, "ten": ten, "ngay": ngay_ban_hanh, "sac_thue": sac_thue,
                   "url": req.url, "github_path": github_path, "importance": importance, "noi_dung": noi_dung})
        else:
            await db.execute(text("""
                INSERT INTO documents (so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
                    github_path, doc_type, importance, import_date, keywords, noi_dung, tvpl_url)
                VALUES (:so_hieu, :ten, :loai, :ngay::date, 'con_hieu_luc', :sac_thue,
                    :github_path, 'vanban', :importance, NOW(), '{}', :noi_dung, :url)
                ON CONFLICT (github_path) DO NOTHING
            """), {"so_hieu": so_hieu, "ten": ten, "loai": loai, "ngay": ngay_ban_hanh,
                   "sac_thue": sac_thue, "github_path": github_path, "importance": importance,
                   "noi_dung": noi_dung, "url": req.url})
        await db.commit()
    except Exception as e:
        return {"status": "error", "msg": str(e),
                "preview": {"so_hieu": so_hieu, "ten": ten, "loai": loai}}

    return {"status": "ok", "preview": {
        "so_hieu": so_hieu, "ten": ten, "loai": loai,
        "ngay_ban_hanh": ngay_ban_hanh, "sac_thue": sac_thue, "importance": importance,
    }}



# ── Embedding Push Endpoint (called by Colab) ────────────────────────────────
EMBED_TOKEN = os.environ.get("EMBED_TOKEN", "colab-embed-2026")

class EmbeddingItem(BaseModel):
    id: int
    embedding: list

class EmbeddingBatch(BaseModel):
    table: str
    embeddings: list[EmbeddingItem]

@app.post("/api/admin/update-embeddings")
async def update_embeddings(
    req: EmbeddingBatch,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Simple token auth
    token = request.headers.get("X-Embed-Token", "")
    if token != EMBED_TOKEN:
        raise HTTPException(403, "Invalid embed token")

    if req.table not in ("documents", "cong_van"):
        raise HTTPException(400, "Invalid table")

    if not req.embeddings:
        return {"updated": 0}

    updated = 0
    errors = 0
    for item in req.embeddings:
        try:
            emb_str = "[" + ",".join(str(x) for x in item.embedding) + "]"
            await db.execute(
                text(f"UPDATE {req.table} SET embedding = CAST(:emb AS vector) WHERE id = :id"),
                {"emb": emb_str, "id": item.id}
            )
            updated += 1
        except Exception as e:
            errors += 1
            log.warning(f"Embedding update error id={item.get('id')}: {e}")

    await db.commit()
    return {"updated": updated, "errors": errors, "table": req.table}

@app.get("/api/admin/embedding-status")
async def embedding_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = request.headers.get("X-Embed-Token", "")
    if token != EMBED_TOKEN:
        raise HTTPException(403, "Invalid embed token")

    r = await db.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM documents) AS docs_total,
          (SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL) AS docs_embedded,
          (SELECT COUNT(*) FROM cong_van) AS cv_total,
          (SELECT COUNT(*) FROM cong_van WHERE embedding IS NOT NULL) AS cv_embedded
    """))
    row = r.mappings().first()
    return dict(row)


@app.get("/api/admin/docs-missing-embed")
async def docs_missing_embed(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    token = request.headers.get("X-Embed-Token", "")
    if token != EMBED_TOKEN:
        raise HTTPException(403, "Invalid embed token")
    r = await db.execute(text("""
        SELECT id, so_hieu, ten FROM documents WHERE embedding IS NULL ORDER BY id
    """))
    rows = r.fetchall()
    return {"items": [{"id": row.id, "so_hieu": row.so_hieu or "", "ten": row.ten or ""} for row in rows],
            "total": len(rows)}

import os as _os
from fastapi.responses import FileResponse as _FileResponse

# Serve static assets (JS/CSS bundles)
if _os.path.isdir("static/assets"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

@app.get("/")
async def spa_root():
    return _FileResponse("static/index.html")


class AskRequest(BaseModel):
    question: str
    top_k: int = 15
    docs_top_k: int = 5
    use_intent: bool = True
    model: str = "anthropic/claude-haiku-4-5"

class DocRelationCreate(BaseModel):
    source_id: int
    target_so_hieu: str
    target_id: Optional[int] = None
    relation_type: str
    ghi_chu: Optional[str] = None
    verified: bool = False

class DocRelationUpdate(BaseModel):
    target_so_hieu: Optional[str] = None
    target_id: Optional[int] = None
    relation_type: Optional[str] = None
    ghi_chu: Optional[str] = None
    verified: Optional[bool] = None

class DocumentUpdate(BaseModel):
    so_hieu: Optional[str] = None
    ten: Optional[str] = None
    loai: Optional[str] = None
    co_quan: Optional[str] = None
    nguoi_ky: Optional[str] = None
    ngay_ban_hanh: Optional[str] = None
    hieu_luc_tu: Optional[str] = None
    het_hieu_luc_tu: Optional[str] = None
    ngay_cong_bao: Optional[str] = None
    so_cong_bao: Optional[str] = None
    tinh_trang: Optional[str] = None
    sac_thue: Optional[List[str]] = None
    tom_tat: Optional[str] = None
    importance: Optional[int] = None
    is_anchor: Optional[bool] = None

class MissingDocUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = None
    notes: Optional[str] = None
    tvpl_url: Optional[str] = None

async def _empty_list():
    return []


@app.post("/api/ask")
async def ask(req: AskRequest, db: AsyncSession = Depends(get_db)):
    """RAG v5: Haiku default + anchor docs + hybrid search."""
    if not req.question or len(req.question.strip()) < 5:
        raise HTTPException(400, "Câu hỏi quá ngắn")

    # Step 1: Analyze intent
    if req.use_intent:
        intent = await analyze_intent(req.question)
    else:
        intent = {
            "sac_thue": [], "chu_de": req.question,
            "search_queries": [req.question], "is_timeline": False,
        }

    queries   = intent.get("search_queries", [req.question])
    sac_thue  = intent.get("sac_thue", [])
    filter_st = sac_thue[0] if sac_thue else None
    is_timeline = intent.get("is_timeline", False)

    # Step 2: Load anchor docs theo tất cả sắc thuế detect được
    # Claudible Sonnet: giảm context/doc để tránh Cloudflare 524 timeout
    is_claudible_sonnet = req.model == "claudible/claude-sonnet-4.6"
    article_max_chars = 10_000 if is_claudible_sonnet else 20_000
    anchor_docs = await (
        load_anchor_docs(db, sac_thue, question=req.question, article_max_chars=article_max_chars)
        if not is_timeline else _empty_list()
    )

    # Step 3: Nếu không có anchor → fallback vector search docs
    docs = []
    if not anchor_docs:
        docs = await search_multi_query_docs(db, queries, top_k=req.docs_top_k)

    # Step 4: RAG answer
    answer_data = await rag_answer(
        req.question, [], docs=docs, anchor_docs=anchor_docs,
        model=req.model
    )

    return {
        "question":      req.question,
        "answer":        answer_data["answer"],
        "model_used":    answer_data["model_used"],
        "is_timeline":   answer_data["is_timeline"],
        "intent":        intent,
        "sources_count": len(answer_data["sources"]),
        "anchor_count":  len(anchor_docs),
        "docs_count":    len(docs),
        "cv_count":      0,
        "sources":       answer_data["sources"],
    }

# ── Doc Relations ─────────────────────────────────────────────────────────────

@app.get("/api/admin/documents/{doc_id}/relations")
async def get_doc_relations(doc_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    r = await db.execute(text("""
        SELECT dr.*, d2.ten as target_ten, d2.loai as target_loai
        FROM doc_relations dr
        LEFT JOIN documents d2 ON dr.target_id = d2.id
        WHERE dr.source_id = :doc_id
        ORDER BY dr.relation_type, dr.created_at
    """), {"doc_id": doc_id})
    return [dict(row) for row in r.mappings().all()]

@app.post("/api/admin/relations")
async def create_relation(req: DocRelationCreate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    if not req.target_id and req.target_so_hieu:
        r = await db.execute(text("SELECT id FROM documents WHERE so_hieu = :sh"), {"sh": req.target_so_hieu})
        row = r.fetchone()
        if row:
            req.target_id = row[0]
    r = await db.execute(text("""
        INSERT INTO doc_relations (source_id, target_so_hieu, target_id, relation_type, ghi_chu, verified)
        VALUES (:source_id, :target_so_hieu, :target_id, :relation_type, :ghi_chu, :verified)
        ON CONFLICT (source_id, target_so_hieu, relation_type) DO UPDATE
            SET ghi_chu=EXCLUDED.ghi_chu, verified=EXCLUDED.verified, updated_at=NOW()
        RETURNING id
    """), req.model_dump())
    await db.commit()
    return {"id": r.scalar(), "status": "created"}

@app.put("/api/admin/relations/{rel_id}")
async def update_relation(rel_id: int, req: DocRelationUpdate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Không có field nào để update")
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates["rel_id"] = rel_id
    await db.execute(text(f"UPDATE doc_relations SET {set_clause}, updated_at=NOW() WHERE id=:rel_id"), updates)
    await db.commit()
    return {"status": "updated"}

@app.delete("/api/admin/relations/{rel_id}")
async def delete_relation(rel_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    await db.execute(text("DELETE FROM doc_relations WHERE id=:id"), {"id": rel_id})
    await db.commit()
    return {"status": "deleted"}

# ── Document update ────────────────────────────────────────────────────────────

@app.put("/api/admin/documents/{doc_id}")
async def update_document(doc_id: int, req: DocumentUpdate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Không có field nào để update")
    date_fields = {"ngay_ban_hanh", "hieu_luc_tu", "het_hieu_luc_tu", "ngay_cong_bao"}
    set_parts = []
    for k in updates:
        set_parts.append(f"{k}=:{k}::date" if k in date_fields else f"{k}=:{k}")
    updates["doc_id"] = doc_id
    await db.execute(text(f"UPDATE documents SET {', '.join(set_parts)}, updated_at=NOW() WHERE id=:doc_id"), updates)
    await db.commit()
    return {"status": "updated"}

# ── Extract + Save relations ───────────────────────────────────────────────────

@app.post("/api/admin/documents/{doc_id}/extract-relations")
async def extract_relations(doc_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    import openai
    r = await db.execute(text("SELECT so_hieu, ten, loai, noi_dung, tom_tat FROM documents WHERE id=:id"), {"id": doc_id})
    doc = r.mappings().first()
    if not doc:
        raise HTTPException(404, "Không tìm thấy văn bản")
    content = (doc["noi_dung"] or doc["tom_tat"] or "")[:6000]
    prompt = f"""Phân tích văn bản pháp luật Việt Nam sau và extract các quan hệ pháp lý.

Văn bản: {doc["so_hieu"]} — {doc["ten"]}
Nội dung (trích):
{content}

Hãy tìm tất cả các văn bản pháp luật khác được đề cập và xác định quan hệ:
- huong_dan, duoc_huong_dan, sua_doi, bi_sua_doi, thay_the, bi_thay_the, hop_nhat, can_cu, dinh_chinh, lien_quan

Trả về JSON object: {{"relations": [{{"target_so_hieu": "...", "relation_type": "...", "ghi_chu": "..."}}]}}
Chỉ trả về JSON, không giải thích thêm."""
    client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    resp = await client.chat.completions.create(
        model="gpt-4o-mini", max_tokens=1500,
        messages=[
            {"role": "system", "content": "Bạn là chuyên gia pháp lý Việt Nam. Trả về JSON chính xác."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    raw = resp.choices[0].message.content
    try:
        parsed = json.loads(raw)
        relations = parsed if isinstance(parsed, list) else parsed.get("relations", [])
    except Exception:
        relations = []
    missing = []
    for rel in relations:
        sh = rel.get("target_so_hieu", "")
        if sh:
            r2 = await db.execute(text("SELECT id FROM documents WHERE so_hieu = :sh"), {"sh": sh})
            row = r2.fetchone()
            rel["target_id"] = row[0] if row else None
            if not row:
                r3 = await db.execute(text("SELECT id FROM missing_docs_watchlist WHERE so_hieu = :sh"), {"sh": sh})
                if not r3.fetchone():
                    missing.append({"so_hieu": sh, "relation_type": rel.get("relation_type"), "mentioned_in": doc["so_hieu"]})
    return {"doc_id": doc_id, "so_hieu": doc["so_hieu"], "relations_found": relations, "missing_docs": missing, "count": len(relations)}

@app.post("/api/admin/documents/{doc_id}/save-relations")
async def save_relations(doc_id: int, body: dict, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    relations = body.get("relations", [])
    missing_docs = body.get("missing_docs", [])
    saved = 0
    for rel in relations:
        sh = rel.get("target_so_hieu", "")
        if not sh:
            continue
        r2 = await db.execute(text("SELECT id FROM documents WHERE so_hieu=:sh"), {"sh": sh})
        row = r2.fetchone()
        target_id = row[0] if row else None
        await db.execute(text("""
            INSERT INTO doc_relations (source_id, target_so_hieu, target_id, relation_type, ghi_chu, verified)
            VALUES (:source_id, :target_so_hieu, :target_id, :relation_type, :ghi_chu, TRUE)
            ON CONFLICT (source_id, target_so_hieu, relation_type) DO NOTHING
        """), {"source_id": doc_id, "target_so_hieu": sh, "target_id": target_id,
               "relation_type": rel.get("relation_type", "lien_quan"), "ghi_chu": rel.get("ghi_chu")})
        saved += 1
    added_missing = 0
    for m in missing_docs:
        sh = m.get("so_hieu", "")
        if not sh:
            continue
        await db.execute(text("""
            INSERT INTO missing_docs_watchlist (so_hieu, ten, mentioned_in_ids, relation_types, priority)
            VALUES (:so_hieu, :ten, ARRAY[:doc_id]::int[], ARRAY[:rel_type], 2)
            ON CONFLICT (so_hieu) DO UPDATE SET
                mentioned_in_ids = array_append(missing_docs_watchlist.mentioned_in_ids, :doc_id),
                updated_at = NOW()
        """), {"so_hieu": sh, "ten": m.get("ten"), "doc_id": doc_id, "rel_type": m.get("relation_type", "lien_quan")})
        added_missing += 1
    await db.commit()
    return {"saved_relations": saved, "added_to_watchlist": added_missing}

# ── Missing Docs Watchlist ─────────────────────────────────────────────────────

@app.get("/api/admin/missing-docs")
async def get_missing_docs(
    status: Optional[str] = Query(None),
    priority: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin)
):
    where = ["1=1"]
    params: dict = {}
    if status:
        where.append("status = :status")
        params["status"] = status
    if priority:
        where.append("priority = :priority")
        params["priority"] = priority
    clause = "WHERE " + " AND ".join(where)
    r = await db.execute(text(f"SELECT * FROM missing_docs_watchlist {clause} ORDER BY priority ASC, created_at DESC"), params)
    return [dict(row) for row in r.mappings().all()]

@app.put("/api/admin/missing-docs/{item_id}")
async def update_missing_doc(item_id: int, req: MissingDocUpdate, db: AsyncSession = Depends(get_db), user=Depends(require_admin)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Không có field nào")
    set_clause = ", ".join(f"{k}=:{k}" for k in updates)
    updates["item_id"] = item_id
    await db.execute(text(f"UPDATE missing_docs_watchlist SET {set_clause}, updated_at=NOW() WHERE id=:item_id"), updates)
    await db.commit()
    return {"status": "updated"}

# ── Documents list for admin ───────────────────────────────────────────────────

@app.get("/api/admin/documents-list")
async def admin_documents_list(
    q: Optional[str] = None,
    loai: Optional[str] = None,
    sac_thue: Optional[str] = None,
    anchor_only: Optional[bool] = False,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_admin)
):
    where = ["1=1"]
    params: dict = {"limit": limit, "offset": offset}
    if q:
        where.append("(so_hieu ILIKE :q OR ten ILIKE :q)")
        params["q"] = f"%{q}%"
    if loai:
        where.append("loai = :loai")
        params["loai"] = loai
    if sac_thue:
        where.append(":sac_thue = ANY(sac_thue)")
        params["sac_thue"] = sac_thue
    if anchor_only:
        where.append("is_anchor = TRUE")
    clause = "WHERE " + " AND ".join(where)
    r = await db.execute(text(f"""
        SELECT id, so_hieu, ten, loai, co_quan, nguoi_ky, ngay_ban_hanh,
               hieu_luc_tu, het_hieu_luc_tu, tinh_trang, sac_thue,
               importance, ngay_cong_bao, so_cong_bao, tom_tat, is_anchor
        FROM documents {clause}
        ORDER BY is_anchor DESC NULLS LAST, ngay_ban_hanh DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params)
    rows = [dict(row) for row in r.mappings().all()]
    r2 = await db.execute(text(f"SELECT COUNT(*) FROM documents {clause}"), params)
    total = r2.scalar()
    return {"items": rows, "total": total}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    index = "static/index.html"
    if _os.path.exists(index):
        return _FileResponse(index)
    raise HTTPException(status_code=404, detail="Frontend not built")
