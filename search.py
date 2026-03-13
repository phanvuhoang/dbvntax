"""
Search module: keyword, semantic (pgvector), hybrid
"""
import os
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

async def embed_text(text_input: str) -> Optional[list]:
    if not OPENAI_KEY or not text_input.strip():
        return None
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=OPENAI_KEY)
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text_input[:8000]
        )
        return resp.data[0].embedding
    except Exception as e:
        print(f"Embed error: {e}")
        return None

def build_filters(filters: dict) -> tuple:
    where = []
    params = {}
    if filters.get("sac_thue"):
        where.append(":sac_thue = ANY(sac_thue)")
        params["sac_thue"] = filters["sac_thue"]
    if filters.get("loai"):
        where.append("loai = :loai")
        params["loai"] = filters["loai"]
    if filters.get("year_from"):
        where.append("EXTRACT(YEAR FROM ngay_ban_hanh) >= :year_from")
        params["year_from"] = filters["year_from"]
    if filters.get("year_to"):
        where.append("EXTRACT(YEAR FROM ngay_ban_hanh) <= :year_to")
        params["year_to"] = filters["year_to"]
    if filters.get("tinh_trang"):
        where.append("tinh_trang = :tinh_trang")
        params["tinh_trang"] = filters["tinh_trang"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return clause, params

async def search_keyword(db: AsyncSession, q: str, filters: dict, limit: int, offset: int):
    where, params = build_filters(filters)
    if q:
        tsq_clause = "to_tsvector('simple', coalesce(so_hieu,'') || ' ' || coalesce(ten,'') || ' ' || coalesce(tom_tat,'')) @@ plainto_tsquery('simple', :q)"
        params["q"] = q
        if where:
            where += f" AND {tsq_clause}"
        else:
            where = f"WHERE {tsq_clause}"
    count_q = f"SELECT COUNT(*) FROM documents {where}"
    r_count = await db.execute(text(count_q), params)
    total = r_count.scalar()
    params["limit"] = limit
    params["offset"] = offset
    r = await db.execute(text(f"""
        SELECT id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
               github_path, LEFT(tom_tat, 300) as snippet, 'documents' as source, 0.5 as score
        FROM documents {where}
        ORDER BY ngay_ban_hanh DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params)
    rows = [dict(row) for row in r.mappings().all()]
    return rows, total

async def search_semantic(db: AsyncSession, q: str, filters: dict, limit: int, offset: int):
    emb = await embed_text(q)
    if not emb:
        return await search_keyword(db, q, filters, limit, offset)
    where, params = build_filters(filters)
    params["emb"] = str(emb)
    params["limit"] = limit + offset
    r = await db.execute(text(f"""
        SELECT id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
               github_path, LEFT(tom_tat, 300) as snippet, 'documents' as source,
               1-(embedding<=>:emb::vector) AS score
        FROM documents
        {where}
        {"AND" if where else "WHERE"} embedding IS NOT NULL
        ORDER BY embedding<=>:emb::vector
        LIMIT :limit
    """), params)
    rows = [dict(row) for row in r.mappings().all()]
    total = len(rows)
    return rows[offset:offset+limit], total

async def do_search(db: AsyncSession, q: str, type: str, filters: dict, mode: str, limit: int, offset: int):
    if not q:
        # Default: return latest docs
        where, params = build_filters(filters)
        params["limit"] = limit
        params["offset"] = offset
        r_count = await db.execute(text(f"SELECT COUNT(*) FROM documents {where}"), params)
        total = r_count.scalar()
        r = await db.execute(text(f"""
            SELECT id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, sac_thue,
                   github_path, LEFT(tom_tat, 300) as snippet, 'documents' as source, 1.0 as score
            FROM documents {where}
            ORDER BY ngay_ban_hanh DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """), params)
        return [dict(row) for row in r.mappings().all()], total

    if mode == "semantic":
        return await search_semantic(db, q, filters, limit, offset)
    else:
        return await search_keyword(db, q, filters, limit, offset)

async def get_doc_by_id(db: AsyncSession, doc_id: int):
    r = await db.execute(text("SELECT * FROM documents WHERE id=:id"), {"id": doc_id})
    row = r.mappings().first()
    return dict(row) if row else None

async def get_cv_by_id(db: AsyncSession, cv_id: int):
    r = await db.execute(text("SELECT * FROM cong_van WHERE id=:id"), {"id": cv_id})
    row = r.mappings().first()
    return dict(row) if row else None

async def get_article_by_id(db: AsyncSession, art_id: int):
    r = await db.execute(text("SELECT * FROM articles WHERE id=:id"), {"id": art_id})
    row = r.mappings().first()
    return dict(row) if row else None
