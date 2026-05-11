"""Shared helpers used across the canonical backend layer."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
from datetime import datetime
from typing import Iterable, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("vntaxdb.backend.common")


def now_utc() -> datetime:
    return datetime.utcnow()


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def short_hash(data: str | bytes, n: int = 16) -> str:
    return sha256_hex(data)[:n]


def normalize_html(html: str) -> str:
    """Strip inline width/float style noise but keep block structure."""
    if not html:
        return ""
    out = re.sub(r"width:\s*\d+\.?\d*(pt|px|%)\s*;?\s*", "", html)
    out = re.sub(r"float:\s*\w+\s*;?\s*", "", out)
    return out


def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html or "", "html.parser").get_text("\n", strip=True)
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", html or "")


# ---------------------------------------------------------------------------
# Loại / sắc thuế canonical maps. Mirror what `main.py` and the frontend use.
# ---------------------------------------------------------------------------

LOAI_CANONICAL = {
    "NĐ": "ND", "Nghị định": "ND", "ND": "ND",
    "TT": "TT", "Thông tư": "TT",
    "Luật": "Luat", "LUAT": "Luat", "Luat": "Luat",
    "VBHN": "VBHN",
    "QĐ": "QD", "QD": "QD", "Quyết định": "QD",
    "NQ": "NQ", "Nghị quyết": "NQ",
    "CV": "CV", "Công văn": "CV",
    "Khác": "Khac", "Khac": "Khac",
}

SAC_THUE_DB_CANONICAL = {
    # frontend canonical -> DB
    "CIT": "TNDN", "VAT": "GTGT", "HDDT": "HOA_DON",
    "PIT": "TNCN", "SCT": "TTDB", "FCT": "FCT",
    "TP": "GDLK", "HKD": "HKD", "QLT": "QLT", "THUE_QT": "THUE_QT",
}

DB_TO_FE_SAC_THUE = {v: k for k, v in SAC_THUE_DB_CANONICAL.items()}

SAC_THUE_KEYWORDS = {
    "TNDN":    ["thu nhập doanh nghiệp", "tndn"],
    "GTGT":    ["giá trị gia tăng", "gtgt", "vat"],
    "TNCN":    ["thu nhập cá nhân", "tncn"],
    "TTDB":    ["tiêu thụ đặc biệt", "ttdb", "ttđb"],
    "FCT":     ["nhà thầu nước ngoài", "nhà thầu"],
    "GDLK":    ["giao dịch liên kết", "chuyển giá", "transfer pricing"],
    "QLT":     ["quản lý thuế", "kê khai", "nộp thuế"],
    "HOA_DON": ["hóa đơn điện tử", "hóa đơn"],
    "HKD":     ["hộ kinh doanh"],
    "XNK":     ["xuất nhập khẩu", "hải quan"],
}


def fe_sac_thue(db_code: str) -> str:
    return DB_TO_FE_SAC_THUE.get(db_code, db_code)


def db_sac_thue(fe_code: str) -> str:
    return SAC_THUE_DB_CANONICAL.get(fe_code, fe_code)


def classify_sac_thue_from_text(text_body: str) -> list[str]:
    out: list[str] = []
    low = (text_body or "")[:4000].lower()
    for code, kws in SAC_THUE_KEYWORDS.items():
        if any(kw in low for kw in kws):
            out.append(code)
    return out or ["QLT"]


IMPORTANCE_BY_LOAI = {
    "ND": 1, "TT": 1, "Luat": 2, "VBHN": 2,
    "NQ": 2, "QD": 3, "CV": 4, "Khac": 3,
}


def importance_for(loai: str) -> int:
    return IMPORTANCE_BY_LOAI.get(loai, 3)


# ---------------------------------------------------------------------------
# Source detection
# ---------------------------------------------------------------------------

SOURCE_SITES = {
    "thuvienphapluat.vn": ("tvpl", "thuvienphapluat.vn"),
    "luatvietnam.vn":     ("luatvietnam", "luatvietnam.vn"),
    "vbpl.vn":            ("vbpl", "vbpl.vn"),
    "chinhphu.vn":        ("chinhphu", "chinhphu.vn"),
    "mof.gov.vn":         ("mof", "mof.gov.vn"),
    "gdt.gov.vn":         ("gdt", "gdt.gov.vn"),
}


def detect_source(url: str | None) -> tuple[str, str | None]:
    if not url:
        return "manual", None
    low = url.lower()
    for host, (src, site) in SOURCE_SITES.items():
        if host in low:
            return src, site
    return "url", low.split("/")[2] if "//" in low else None


# ---------------------------------------------------------------------------
# Effective-status helpers
# ---------------------------------------------------------------------------

EFFECTIVE_STATES = {
    "con_hieu_luc": "Còn hiệu lực",
    "het_hieu_luc": "Hết hiệu lực",
    "chua_hieu_luc": "Chưa có hiệu lực",
    "het_hieu_luc_phan": "Hết hiệu lực một phần",
    "unknown": "Chưa xác định",
}


# ---------------------------------------------------------------------------
# HTTP fetch with TVPL-friendly headers
# ---------------------------------------------------------------------------

DEFAULT_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}


async def fetch_html(url: str, timeout: float = 30.0, max_bytes: int = 6_000_000) -> tuple[str | None, str | None]:
    """Return (html, error). Streams and rejects oversized responses."""
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers=DEFAULT_FETCH_HEADERS
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None, f"HTTP {resp.status_code}"
            content = resp.content
            if len(content) > max_bytes:
                return None, f"response too large ({len(content)} bytes)"
            charset = resp.charset_encoding or "utf-8"
            try:
                return content.decode(charset, errors="replace"), None
            except LookupError:
                return content.decode("utf-8", errors="replace"), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


# ---------------------------------------------------------------------------
# Sync-token helpers (header `X-Sync-Token`)
# ---------------------------------------------------------------------------


def hash_token(token: str) -> str:
    return sha256_hex(token)


def generate_token() -> str:
    """Generate a 40-char URL-safe sync token (prefix 'sk_canon_' + 32 chars)."""
    return "sk_canon_" + secrets.token_urlsafe(24)[:32]


async def resolve_sync_key(db: AsyncSession, raw_token: str) -> dict | None:
    """Look up an active export key by its raw token; bump last_used_at; return key row or None."""
    if not raw_token or len(raw_token) < 12:
        return None
    h = hash_token(raw_token)
    r = await db.execute(
        text(
            """
            SELECT id, app_name, scopes, webhook_url, webhook_secret, revoked_at
            FROM documents_export_keys WHERE token_hash = :h
            """
        ),
        {"h": h},
    )
    row = r.mappings().first()
    if not row:
        return None
    if row["revoked_at"]:
        return None
    await db.execute(
        text("UPDATE documents_export_keys SET last_used_at = NOW() WHERE id = :id"),
        {"id": row["id"]},
    )
    await db.commit()
    return dict(row)


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


async def write_audit(
    db: AsyncSession,
    *,
    source: str,
    doc_id: int,
    event: str,
    actor_id: Optional[int] = None,
    actor_kind: str = "user",
    actor_label: Optional[str] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    commit: bool = True,
) -> None:
    import json

    try:
        await db.execute(
            text(
                """
                INSERT INTO documents_audit
                  (source, doc_id, event, actor_id, actor_kind, actor_label, old_values, new_values)
                VALUES (:s, :d, :e, :aid, :ak, :al, CAST(:ov AS JSONB), CAST(:nv AS JSONB))
                """
            ),
            {
                "s": source,
                "d": doc_id,
                "e": event,
                "aid": actor_id,
                "ak": actor_kind,
                "al": actor_label,
                "ov": json.dumps(old_values, default=str, ensure_ascii=False) if old_values else None,
                "nv": json.dumps(new_values, default=str, ensure_ascii=False) if new_values else None,
            },
        )
        if commit:
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("audit write failed: %s", e)


# ---------------------------------------------------------------------------
# JSON-safe row helpers
# ---------------------------------------------------------------------------


def serialize_row(row: dict) -> dict:
    """Convert datetime/array fields to JSON-friendly values."""
    out: dict = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, (list, tuple)):
            out[k] = list(v)
        else:
            out[k] = v
    return out


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        # accept 2026-05-11T12:00:00Z or with offset
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
