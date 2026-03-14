#!/usr/bin/env python3
"""
crawl_congvan.py — Crawl công văn thuế từ thue.vn (Strapi v3 API)
Phân loại theo taxonomy.py, insert vào PostgreSQL (vntaxdb app)

Usage:
  python3 crawl_congvan.py [--limit N] [--dry-run] [--clear]

Options:
  --limit N    Chỉ crawl N bài (default: toàn bộ)
  --dry-run    Không insert DB, chỉ in ra màn hình
  --clear      Xóa toàn bộ cong_van table trước khi insert
  --category   Filter category slug (default: cong-van)
  --source     Tên source để tag (default: thue.vn)
"""

import asyncio
import argparse
import json
import re
import sys
import time
import os
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "https://thue.vn/api"
PAGE_SIZE = 100   # Strapi v3 max per request
DELAY = 0.3       # Giây delay giữa các request

# ── Taxonomy (inline từ taxonomy.py) ─────────────────────────────────────────
CLASSIFICATION_RULES = {
    "TNDN": ["thu nhập doanh nghiệp", "tndn", "cit", "chi phí được trừ", "doanh thu tính thuế",
             "ưu đãi thuế", "chuyển lỗ", "khấu hao", "quyết toán doanh nghiệp", "chi phí hợp lý",
             "chi phí được trừ", "ebitda", "lãi vay", "chuyển giá doanh nghiệp"],
    "GTGT": ["giá trị gia tăng", "gtgt", "vat", "hóa đơn đầu vào", "khấu trừ thuế",
             "hoàn thuế gtgt", "thuế suất 0%", "thuế suất 5%", "thuế suất 10%",
             "không chịu thuế gtgt", "giá tính thuế", "doanh nghiệp chế xuất"],
    "TNCN": ["thu nhập cá nhân", "tncn", "pit", "giảm trừ gia cảnh", "quyết toán thuế tncn",
             "người phụ thuộc", "khấu trừ tại nguồn", "ủy quyền quyết toán", "lao động nước ngoài",
             "cá nhân cư trú", "không cư trú", "183 ngày"],
    "TTDB": ["tiêu thụ đặc biệt", "ttđb", "ttdb", "sct", "rượu bia", "thuốc lá",
             "ô tô chịu thuế", "xăng dầu ttdb", "casino", "golf"],
    "FCT":  ["nhà thầu nước ngoài", "nhà thầu", "fct", "foreign contractor",
             "dịch vụ từ nước ngoài", "royalty", "bản quyền", "lãi vay nước ngoài",
             "chuyển nhượng vốn nước ngoài", "thuế nhà thầu"],
    "GDLK": ["giao dịch liên kết", "chuyển giá", "transfer pricing", "apa",
             "bên liên kết", "nghị định 132", "cbcr", "lãi vay liên kết",
             "xác định giá thị trường", "arm's length"],
    "QLT":  ["quản lý thuế", "kê khai", "nộp thuế", "hoàn thuế", "thanh tra thuế",
             "kiểm tra thuế", "xử phạt", "cưỡng chế", "khiếu nại", "mã số thuế",
             "gia hạn nộp thuế", "miễn tiền phạt", "tiền chậm nộp", "truy thu",
             "đăng ký thuế", "khai bổ sung", "gia hạn kê khai"],
    "HOA_DON": ["hóa đơn điện tử", "hđđt", "hóa đơn gtgt", "mã cơ quan thuế",
               "xuất hóa đơn", "hóa đơn sai sót", "hóa đơn thay thế", "hóa đơn điều chỉnh",
               "lập hóa đơn", "hủy hóa đơn"],
    "HKD":  ["hộ kinh doanh", "cá nhân kinh doanh", "thuế khoán", "hộ cá thể",
             "cho thuê nhà", "cho thuê tài sản", "kol", "streamer", "sàn tmđt",
             "hộ gia đình kinh doanh", "nộp thuế thay"],
    "XNK":  ["xuất nhập khẩu", "hải quan", "nhập khẩu", "xuất khẩu", "mã hs",
             "trị giá hải quan", "thông quan", "c/o", "xuất xứ", "fta",
             "chống bán phá giá", "thuế tự vệ", "biểu thuế"],
    "TAI_NGUYEN_DAT": ["tài nguyên", "tiền thuê đất", "tiền sử dụng đất",
                       "thuê mặt nước", "khoáng sản", "đất đai", "lệ phí đất"],
    "MON_BAI_PHI": ["môn bài", "lệ phí môn bài", "lệ phí trước bạ", "trước bạ",
                    "phí bảo vệ môi trường", "lệ phí hải quan"],
}

SAC_THUE_LABELS = {
    "TNDN": "Thuế Thu nhập doanh nghiệp (CIT)",
    "GTGT": "Thuế Giá trị gia tăng (VAT)",
    "TNCN": "Thuế Thu nhập cá nhân (PIT)",
    "TTDB": "Thuế Tiêu thụ đặc biệt (SCT)",
    "FCT":  "Thuế Nhà thầu nước ngoài (FCT)",
    "GDLK": "Giao dịch liên kết / Chuyển giá",
    "QLT":  "Quản lý thuế",
    "HOA_DON": "Hóa đơn điện tử",
    "HKD":  "Hộ kinh doanh / Cá nhân kinh doanh",
    "XNK":  "Thuế Xuất nhập khẩu / Hải quan",
    "TAI_NGUYEN_DAT": "Thuế Tài nguyên / Tiền thuê đất",
    "MON_BAI_PHI": "Lệ phí Môn bài / Phí & Lệ phí",
}

def classify(title: str, content: str = "") -> list[str]:
    """Phân loại tài liệu theo sắc thuế dựa trên keywords"""
    text = (title + " " + content[:2000]).lower()
    result = []
    for code, keywords in CLASSIFICATION_RULES.items():
        if any(kw in text for kw in keywords):
            result.append(code)
    return result if result else ["QLT"]


# ── HTML Text Extractor ────────────────────────────────────────────────────────
class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self._skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self._skip = False

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._parts.append(data.strip())

    def get_text(self):
        return ' '.join(self._parts)


def html_to_text(html: str) -> str:
    if not html:
        return ""
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return re.sub(r'\s+', ' ', p.get_text()).strip()


def extract_so_hieu(title: str, content: str = "") -> str:
    """Extract số hiệu công văn từ title hoặc content"""
    text = title + " " + content[:500]
    patterns = [
        r'\b(\d{1,5}/\d{4}/(?:CV|TB|QĐ|TT|NĐ|NQ|CT|HD|VBHN)-[\w]+)\b',
        r'\b(\d{1,5}/\d{4}/(?:BTC|TCT|TCHQ|UBND|HĐND|CP|BNV|BCT|BTC-TCT|BTC-CST|TCT-CS|TCT-KK|TCT-TNCN|TCT-QLN))\b',
        r'(?:Công văn|CV|Văn bản)\s+(?:số\s+)?(\d{1,5}/\d{4}[/-][\w-]+)',
        r'\bsố\s+(\d{1,5}/\d{4}[/-][\w-]{2,})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


# ── Fetch from thue.vn Strapi v3 API ──────────────────────────────────────────
def fetch_posts(category_slug: str = "cong-van", start: int = 0, limit: int = PAGE_SIZE) -> list[dict]:
    """Fetch posts from Strapi v3 API"""
    params = {
        "_limit": limit,
        "_start": start,
        "_sort": "publishedAt:DESC",
    }
    if category_slug:
        params["_where[category.slug]"] = category_slug

    try:
        resp = httpx.get(
            f"{BASE_URL}/posts",
            params=params,
            headers={"User-Agent": "Mozilla/5.0 Chrome/120", "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  ⚠️  Fetch error (start={start}): {e}")
        return []


def get_total_count(category_slug: str = "cong-van") -> int:
    """Get total post count"""
    params = {}
    if category_slug:
        params["_where[category.slug]"] = category_slug
    try:
        resp = httpx.get(
            f"{BASE_URL}/posts/count",
            params=params,
            headers={"User-Agent": "Mozilla/5.0 Chrome/120", "Accept": "application/json"},
            timeout=15,
        )
        return int(resp.text.strip())
    except Exception as e:
        print(f"  ⚠️  Count error: {e}")
        return 0


def parse_post(item: dict) -> Optional[dict]:
    """Parse Strapi post object thành dict chuẩn cho DB"""
    try:
        title = item.get("title", "").strip()
        if not title:
            return None

        slug = item.get("slug", "")
        content_html = item.get("content", item.get("body", item.get("description", ""))) or ""
        content_text = html_to_text(content_html)

        # Ngày ban hành
        pub_date = item.get("publishedAt") or item.get("created_at") or item.get("createdAt") or ""
        if pub_date:
            pub_date = pub_date[:10]  # YYYY-MM-DD

        # Source URL
        source_url = f"https://thue.vn/cong-van/{slug}" if slug else ""

        # Số hiệu
        so_hieu = extract_so_hieu(title, content_text[:500])

        # Category
        cat = item.get("category", {}) or {}
        if isinstance(cat, dict):
            cat_name = cat.get("name", cat.get("Name", ""))
            cat_slug = cat.get("slug", "")
        else:
            cat_name = ""
            cat_slug = ""

        # Tags
        tags = item.get("tags", []) or []
        if isinstance(tags, list):
            tag_names = [t.get("name", "") if isinstance(t, dict) else str(t) for t in tags]
        else:
            tag_names = []

        # Classify
        sac_thue_list = classify(title, content_text)

        return {
            "source_id": str(item.get("id", "")),
            "source": "thue.vn",
            "title": title,
            "slug": slug,
            "so_hieu": so_hieu,
            "content_html": content_html[:50000],  # Cap at 50KB
            "content_text": content_text[:10000],
            "ngay_ban_hanh": pub_date,
            "cat_name": cat_name,
            "cat_slug": cat_slug,
            "tags": json.dumps(tag_names, ensure_ascii=False),
            "sac_thue": json.dumps(sac_thue_list, ensure_ascii=False),
            "sac_thue_labels": json.dumps([SAC_THUE_LABELS.get(c, c) for c in sac_thue_list], ensure_ascii=False),
            "source_url": source_url,
            "crawled_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"  ⚠️  Parse error for item {item.get('id', '?')}: {e}")
        return None


# ── DB Operations ──────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cong_van (
    id              SERIAL PRIMARY KEY,
    source_id       VARCHAR(50),
    source          VARCHAR(100) DEFAULT 'thue.vn',
    title           TEXT NOT NULL,
    slug            VARCHAR(500),
    so_hieu         VARCHAR(200),
    content_html    TEXT,
    content_text    TEXT,
    ngay_ban_hanh   VARCHAR(20),
    cat_name        VARCHAR(200),
    cat_slug        VARCHAR(200),
    tags            JSONB DEFAULT '[]',
    sac_thue        JSONB DEFAULT '[]',
    sac_thue_labels JSONB DEFAULT '[]',
    source_url      VARCHAR(1000),
    crawled_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_cong_van_sac_thue ON cong_van USING GIN (sac_thue);
CREATE INDEX IF NOT EXISTS idx_cong_van_ngay ON cong_van (ngay_ban_hanh);
CREATE INDEX IF NOT EXISTS idx_cong_van_source ON cong_van (source, source_id);
"""

INSERT_SQL = """
INSERT INTO cong_van 
    (source_id, source, title, slug, so_hieu, content_html, content_text,
     ngay_ban_hanh, cat_name, cat_slug, tags, sac_thue, sac_thue_labels, source_url, crawled_at)
VALUES
    (:source_id, :source, :title, :slug, :so_hieu, :content_html, :content_text,
     :ngay_ban_hanh, :cat_name, :cat_slug, :tags::jsonb, :sac_thue::jsonb, :sac_thue_labels::jsonb,
     :source_url, :crawled_at)
ON CONFLICT (source, source_id) DO UPDATE SET
    title = EXCLUDED.title,
    content_html = EXCLUDED.content_html,
    content_text = EXCLUDED.content_text,
    sac_thue = EXCLUDED.sac_thue,
    sac_thue_labels = EXCLUDED.sac_thue_labels,
    crawled_at = EXCLUDED.crawled_at
"""


async def setup_db(engine):
    """Create tables if not exist"""
    async with engine.begin() as conn:
        for stmt in CREATE_TABLE_SQL.strip().split(';'):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    print("✅ DB tables ready")


async def clear_table(engine):
    """Xóa toàn bộ cong_van table"""
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM cong_van"))
        count = result.scalar()
        await conn.execute(text("TRUNCATE TABLE cong_van RESTART IDENTITY"))
    print(f"🗑️  Cleared {count} rows from cong_van")


async def insert_batch(engine, batch: list[dict]) -> int:
    """Insert một batch records, trả về số rows inserted/updated"""
    if not batch:
        return 0
    async with engine.begin() as conn:
        inserted = 0
        for row in batch:
            try:
                await conn.execute(text(INSERT_SQL), row)
                inserted += 1
            except Exception as e:
                print(f"  ⚠️  Insert error: {e} | title: {row.get('title', '')[:50]}")
    return inserted


# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    parser = argparse.ArgumentParser(description="Crawl công văn thuế từ thue.vn")
    parser.add_argument("--limit", type=int, default=0, help="Max số bài crawl (0=tất cả)")
    parser.add_argument("--dry-run", action="store_true", help="Không insert DB")
    parser.add_argument("--clear", action="store_true", help="Xóa sạch bảng trước khi insert")
    parser.add_argument("--category", default="cong-van", help="Category slug (default: cong-van)")
    args = parser.parse_args()

    print("=" * 60)
    print("📋 VNTaxDB — Crawler Công Văn Thuế")
    print(f"   Source: thue.vn | Category: {args.category}")
    print(f"   Mode: {'DRY RUN' if args.dry_run else 'LIVE INSERT'}")
    print("=" * 60)

    # Count
    total = get_total_count(args.category)
    print(f"\n📊 Total '{args.category}' posts on thue.vn: {total}")

    max_fetch = args.limit if args.limit > 0 else total
    print(f"   Will crawl: {min(max_fetch, total)}")

    if not args.dry_run:
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            print("❌ DATABASE_URL not set!")
            sys.exit(1)
        engine = create_async_engine(db_url)
        await setup_db(engine)
        if args.clear:
            await clear_table(engine)

    # Crawl loop
    total_inserted = 0
    total_fetched = 0
    start = 0
    batch_size = PAGE_SIZE

    print(f"\n🚀 Starting crawl...\n")

    while total_fetched < max_fetch:
        fetch_count = min(batch_size, max_fetch - total_fetched)
        print(f"📥 Fetching start={start}, limit={fetch_count}...")

        posts = fetch_posts(args.category, start=start, limit=fetch_count)
        if not posts:
            print("   No more posts. Done.")
            break

        # Parse
        parsed = []
        for item in posts:
            p = parse_post(item)
            if p:
                parsed.append(p)

        total_fetched += len(posts)

        if args.dry_run:
            # Print sample
            for p in parsed[:3]:
                print(f"\n  📄 [{p['source_id']}] {p['title'][:70]}")
                print(f"     so_hieu: {p['so_hieu'] or '(none)'}")
                print(f"     date: {p['ngay_ban_hanh']} | cat: {p['cat_name']}")
                print(f"     sac_thue: {p['sac_thue']}")
                print(f"     url: {p['source_url']}")
        else:
            inserted = await insert_batch(engine, parsed)
            total_inserted += inserted
            print(f"   ✅ Parsed {len(parsed)}, inserted/updated {inserted}")

        # Print taxonomy distribution in this batch
        if parsed:
            all_codes: dict[str, int] = {}
            for p in parsed:
                for code in json.loads(p['sac_thue']):
                    all_codes[code] = all_codes.get(code, 0) + 1
            top = sorted(all_codes.items(), key=lambda x: -x[1])[:5]
            print(f"   📊 Top sắc thuế: {top}")

        if len(posts) < batch_size:
            break

        start += len(posts)
        time.sleep(DELAY)

    print(f"\n{'=' * 60}")
    print(f"✅ DONE — Fetched: {total_fetched} | Inserted/Updated: {total_inserted}")
    print(f"{'=' * 60}")

    if not args.dry_run:
        # Final count
        async with engine.connect() as conn:
            r = await conn.execute(text("SELECT COUNT(*) FROM cong_van"))
            db_count = r.scalar()
            print(f"\n📊 Total cong_van in DB: {db_count}")

            # Show taxonomy distribution
            r2 = await conn.execute(text("""
                SELECT sac_thue_elem, COUNT(*) as cnt
                FROM cong_van, jsonb_array_elements_text(sac_thue) as sac_thue_elem
                GROUP BY sac_thue_elem
                ORDER BY cnt DESC
            """))
            print("\n📊 Taxonomy distribution:")
            for row in r2:
                label = SAC_THUE_LABELS.get(row[0], row[0])
                print(f"   {row[0]:15} | {label:35} | {row[1]} bài")

        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
