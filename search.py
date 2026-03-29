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
        where.append("LOWER(tinh_trang) = LOWER(:tinh_trang)")
        params["tinh_trang"] = filters["tinh_trang"]
    if filters.get("hl") is not None:
        where.append("hl = :hl")
        params["hl"] = int(filters["hl"])
    if filters.get("date_at"):
        # Filter documents whose hieu_luc covers the given date:
        # At least one hieu_luc entry where tu_ngay <= date AND (den_ngay IS NULL OR den_ngay >= date)
        where.append("""EXISTS (
            SELECT 1 FROM jsonb_array_elements(hieu_luc_index->'hieu_luc') AS e
            WHERE (e->>'tu_ngay' IS NULL OR e->>'tu_ngay' <= :date_at)
              AND (e->>'den_ngay' IS NULL OR e->>'den_ngay' >= :date_at)
        )""")
        params["date_at"] = filters["date_at"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return clause, params

async def search_keyword(db: AsyncSession, q: str, filters: dict, limit: int, offset: int):
    where, params = build_filters(filters)
    if q:
        tsq_clause = "to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || coalesce(ten,'') || ' ' || coalesce(tom_tat,''))) @@ plainto_tsquery('simple', unaccent(:q))"
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
        SELECT id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, hl, sac_thue,
               category_name, github_path, hieu_luc_index, LEFT(tom_tat, 300) as snippet, 'documents' as source, 0.5 as score
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
    try:
        r = await db.execute(text(f"""
            SELECT id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, hl, sac_thue,
                   category_name, github_path, hieu_luc_index, LEFT(tom_tat, 300) as snippet, 'documents' as source,
                   1-(embedding <=> CAST(:emb AS vector)) AS score
            FROM documents
            {where}
            {"AND" if where else "WHERE"} embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :limit
        """), params)
        rows = [dict(row) for row in r.mappings().all()]
        total = len(rows)
        return rows[offset:offset+limit], total
    except Exception as e:
        print(f"Semantic search error (fallback to keyword): {e}")
        return await search_keyword(db, q, filters, limit, offset)


async def search_semantic_cv(db: AsyncSession, q: str, filters: dict, limit: int, offset: int):
    emb = await embed_text(q)
    if not emb:
        return await search_keyword_cv(db, q, filters, limit, offset)
    where_parts = ['embedding IS NOT NULL']
    params = {}
    if filters.get('sac_thue'):
        where_parts.append(':sac_thue = ANY(sac_thue)')
        params['sac_thue'] = filters['sac_thue']
    where = 'WHERE ' + ' AND '.join(where_parts)
    params['emb'] = str(emb)
    params['limit'] = limit + offset
    try:
        r = await db.execute(text(f"""
            SELECT id, so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, nguon, link_nguon,
                   1-(embedding <=> CAST(:emb AS vector)) AS score
            FROM cong_van
            {where}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :limit
        """), params)
        rows = [dict(row) for row in r.mappings().all()]
        total = len(rows)
        return rows[offset:offset+limit], total
    except Exception as e:
        print(f'Semantic CV error: {e}')
        return await search_keyword_cv(db, q, filters, limit, offset)

async def search_keyword_cv(db: AsyncSession, q: str, filters: dict, limit: int, offset: int):
    where_parts = ['1=1']
    params = {}
    if q:
        where_parts.append("to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || ten)) @@ plainto_tsquery('simple', unaccent(:q))")
        params['q'] = q
    if filters.get('sac_thue'):
        where_parts.append(':sac_thue = ANY(sac_thue)')
        params['sac_thue'] = filters['sac_thue']
    where = 'WHERE ' + ' AND '.join(where_parts)
    params['limit'] = limit
    params['offset'] = offset
    r_count = await db.execute(text(f'SELECT COUNT(*) FROM cong_van {where}'), params)
    total = r_count.scalar()
    r = await db.execute(text(f"""
        SELECT id, so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, nguon, link_nguon, 0.5 as score
        FROM cong_van {where}
        ORDER BY ngay_ban_hanh DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params)
    rows = [dict(row) for row in r.mappings().all()]
    return rows, total

async def do_search(db: AsyncSession, q: str, type: str, filters: dict, mode: str, limit: int, offset: int):
    is_cv = type in ("cong_van", "all")
    is_doc = type in ("documents", "all")

    if not q:
        # Default: return latest
        if is_cv and not is_doc:
            return await search_keyword_cv(db, "", filters, limit, offset)
        where, params = build_filters(filters)
        params["limit"] = limit
        params["offset"] = offset
        r_count = await db.execute(text(f"SELECT COUNT(*) FROM documents {where}"), params)
        total = r_count.scalar()
        r = await db.execute(text(f"""
            SELECT id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, hl, sac_thue,
                   category_name, github_path, hieu_luc_index, LEFT(tom_tat, 300) as snippet, 'documents' as source, 1.0 as score
            FROM documents {where}
            ORDER BY ngay_ban_hanh DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """), params)
        return [dict(row) for row in r.mappings().all()], total

    # cong_van search
    if is_cv and not is_doc:
        if mode in ("semantic", "hybrid"):
            return await search_semantic_cv(db, q, filters, limit, offset)
        return await search_keyword_cv(db, q, filters, limit, offset)

    # documents search (default)
    if mode == "semantic":
        return await search_semantic(db, q, filters, limit, offset)
    elif mode == "hybrid":
        results, total = await search_semantic(db, q, filters, limit, offset)
        if total == 0:
            return await search_keyword(db, q, filters, limit, offset)
        return results, total
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

async def list_cong_van(db: AsyncSession, q: str, sac_thue: str, nguon: str, limit: int, offset: int, year_from: int = None, year_to: int = None, chu_de: str = None, tinh_trang: str = None):
    where = ["1=1"]
    params = {}
    if q:
        where.append("to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || ten)) @@ plainto_tsquery('simple', unaccent(:q))")
        params['q'] = q
    if sac_thue:
        where.append(":sac_thue = ANY(sac_thue)")
        params['sac_thue'] = sac_thue
    if nguon:
        where.append("nguon = :nguon")
        params['nguon'] = nguon
    if year_from:
        where.append("EXTRACT(YEAR FROM ngay_ban_hanh) >= :year_from")
        params["year_from"] = year_from
    if year_to:
        where.append("EXTRACT(YEAR FROM ngay_ban_hanh) <= :year_to")
        params["year_to"] = year_to
    if chu_de:
        where.append(":chu_de = ANY(chu_de)")
        params["chu_de"] = chu_de
    if tinh_trang:
        where.append("LOWER(tinh_trang) = LOWER(:tinh_trang)")
        params["tinh_trang"] = tinh_trang
    clause = 'WHERE ' + ' AND '.join(where)
    r_count = await db.execute(text(f'SELECT COUNT(*) FROM cong_van {clause}'), params)
    total = r_count.scalar()
    params['limit'] = limit
    params['offset'] = offset
    r = await db.execute(text(f'''
        SELECT id, so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, nguon, link_nguon
        FROM cong_van {clause}
        ORDER BY ngay_ban_hanh DESC NULLS LAST, id DESC
        LIMIT :limit OFFSET :offset
    '''), params)
    rows = [dict(row) for row in r.mappings().all()]
    return rows, total
