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
    if filters.get("date_from"):
        where.append("ngay_ban_hanh >= :date_from")
        params["date_from"] = filters["date_from"]
    elif filters.get("year_from"):
        where.append("EXTRACT(YEAR FROM ngay_ban_hanh) >= :year_from")
        params["year_from"] = filters["year_from"]
    if filters.get("date_to"):
        where.append("ngay_ban_hanh <= :date_to")
        params["date_to"] = filters["date_to"]
    elif filters.get("year_to"):
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

SEMANTIC_THRESHOLD_MIN = 0.45  # floor
SEMANTIC_THRESHOLD_GAP = 0.15  # top_score - gap = adaptive threshold

def adaptive_threshold(top_score: float) -> float:
    """Tính threshold động: max(floor, top_score - gap)"""
    return max(SEMANTIC_THRESHOLD_MIN, top_score - SEMANTIC_THRESHOLD_GAP)

async def search_semantic(db: AsyncSession, q: str, filters: dict, limit: int, offset: int):
    emb = await embed_text(q)
    if not emb:
        return await search_keyword(db, q, filters, limit, offset)
    where, params = build_filters(filters)
    and_kw = "AND" if where else "WHERE"
    params["emb"] = str(emb)
    # Get top score first for adaptive threshold
    params["top_limit"] = 1
    r_top = await db.execute(text(f"""
        SELECT 1-(embedding <=> CAST(:emb AS vector)) AS score
        FROM documents {where} {and_kw} embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:emb AS vector) LIMIT 1
    """), params)
    top_row = r_top.fetchone()
    if not top_row:
        return await search_keyword(db, q, filters, limit, offset)
    threshold = adaptive_threshold(float(top_row[0]))
    params["threshold"] = threshold
    try:
        # Count total matching above threshold
        r_count = await db.execute(text(f"""
            SELECT COUNT(*) FROM documents
            {where} {and_kw} embedding IS NOT NULL
            AND 1-(embedding <=> CAST(:emb AS vector)) >= :threshold
        """), params)
        total = r_count.scalar() or 0
        params["limit"] = limit
        params["offset"] = offset
        r = await db.execute(text(f"""
            SELECT id, so_hieu, ten, loai, ngay_ban_hanh, tinh_trang, hl, sac_thue,
                   category_name, github_path, hieu_luc_index, LEFT(tom_tat, 300) as snippet, 'documents' as source,
                   1-(embedding <=> CAST(:emb AS vector)) AS score
            FROM documents
            {where} {and_kw} embedding IS NOT NULL
            AND 1-(embedding <=> CAST(:emb AS vector)) >= :threshold
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :limit OFFSET :offset
        """), params)
        rows = [dict(row) for row in r.mappings().all()]
        if total == 0:
            return await search_keyword(db, q, filters, limit, offset)
        return rows, total
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
    try:
        # Adaptive threshold: get top score first
        r_top = await db.execute(text(f"""
            SELECT 1-(embedding <=> CAST(:emb AS vector)) AS score
            FROM cong_van {where} ORDER BY embedding <=> CAST(:emb AS vector) LIMIT 1
        """), params)
        top_row = r_top.fetchone()
        if not top_row:
            return await search_keyword_cv(db, q, filters, limit, offset)
        threshold = adaptive_threshold(float(top_row[0]))
        where_parts.append('1-(embedding <=> CAST(:emb AS vector)) >= :threshold')
        where = 'WHERE ' + ' AND '.join(where_parts)
        params['threshold'] = threshold
        r_count = await db.execute(text(f'SELECT COUNT(*) FROM cong_van {where}'), params)
        total = r_count.scalar() or 0
        params['limit'] = limit
        params['offset'] = offset
        r = await db.execute(text(f"""
            SELECT id, so_hieu, ten, co_quan, ngay_ban_hanh, sac_thue, nguon, link_nguon,
                   noi_dung_day_du,
                   1-(embedding <=> CAST(:emb AS vector)) AS score
            FROM cong_van
            {where}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :limit OFFSET :offset
        """), params)
        rows = [dict(row) for row in r.mappings().all()]
        if total == 0:
            return await search_keyword_cv(db, q, filters, limit, offset)
        return rows, total
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

async def search_semantic_docs_for_rag(db: AsyncSession, q: str, top_k: int = 5) -> list:
    """Semantic search on documents table for RAG. Returns top_k docs with content."""
    emb = await embed_text(q)
    if not emb:
        return []
    try:
        r = await db.execute(text("""
            SELECT id, so_hieu, ten, loai, co_quan,
                   ngay_ban_hanh, hieu_luc_tu, het_hieu_luc_tu,
                   tinh_trang, sac_thue, tvpl_url,
                   LEFT(COALESCE(noi_dung, tom_tat, ''), 2000) as noi_dung,
                   1-(embedding <=> CAST(:emb AS vector)) AS score
            FROM documents
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :top_k
        """), {"emb": str(emb), "top_k": top_k})
        rows = [dict(row) for row in r.mappings().all()]
        for row in rows:
            row["source"] = "document"
        return rows
    except Exception as e:
        print(f"search_semantic_docs_for_rag error: {e}")
        return []

async def search_multi_query_cv(db: AsyncSession, queries: list[str], sac_thue: str = None,
                                top_k: int = 15) -> list[dict]:
    """
    Multi-query semantic search trên cong_van.
    Search song song với nhiều queries, merge + dedup theo id, re-rank theo max score.
    """
    import asyncio as _asyncio

    async def _search_one(q: str) -> list[dict]:
        filters = {"sac_thue": sac_thue} if sac_thue else {}
        rows, _ = await search_semantic_cv(db, q, filters, limit=top_k, offset=0)
        return rows

    # Search song song tất cả queries
    all_results_lists = await _asyncio.gather(*[_search_one(q) for q in queries])

    # Merge + dedup: giữ score cao nhất cho mỗi id
    seen = {}
    for results in all_results_lists:
        for row in results:
            rid = row.get("id")
            if rid not in seen or float(row.get("score", 0)) > float(seen[rid].get("score", 0)):
                seen[rid] = row

    # Sort by score desc, lấy top_k
    merged = sorted(seen.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
    return merged[:top_k]


async def search_multi_query_docs(db: AsyncSession, queries: list[str], top_k: int = 5) -> list[dict]:
    """
    Multi-query semantic search trên documents.
    Search song song, merge + dedup, re-rank.
    """
    import asyncio as _asyncio

    all_results_lists = await _asyncio.gather(
        *[search_semantic_docs_for_rag(db, q, top_k=top_k) for q in queries]
    )

    seen = {}
    for results in all_results_lists:
        for row in results:
            rid = row.get("id")
            if rid not in seen or float(row.get("score", 0)) > float(seen[rid].get("score", 0)):
                seen[rid] = row

    merged = sorted(seen.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
    return merged[:top_k]


async def list_cong_van(db: AsyncSession, q: str, sac_thue: str, nguon: str, limit: int, offset: int, year_from: int = None, year_to: int = None, chu_de: str = None, tinh_trang: str = None, date_from: str = None, date_to: str = None):
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
    if date_from:
        where.append("ngay_ban_hanh >= :date_from")
        params["date_from"] = date_from
    elif year_from:
        where.append("EXTRACT(YEAR FROM ngay_ban_hanh) >= :year_from")
        params["year_from"] = year_from
    if date_to:
        where.append("ngay_ban_hanh <= :date_to")
        params["date_to"] = date_to
    elif year_to:
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
