"""
Webhook dispatcher — best-effort fire-and-log delivery for document events.

We do NOT block ingestion on webhook delivery. The router exposes a manual
trigger for debugging; production triggers come from canonical.py mutations.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("vntaxdb.webhooks")


async def fire_event(
    db: AsyncSession,
    event: str,
    payload: dict[str, Any],
) -> None:
    """Look up all active keys with webhook_url and event in scopes,
    POST the payload signed with HMAC-SHA256 in X-Webhook-Signature."""
    try:
        r = await db.execute(text("""
            SELECT id, app_name, webhook_url, webhook_secret, scopes
            FROM documents_export_keys
            WHERE revoked_at IS NULL AND webhook_url IS NOT NULL
              AND 'webhook' = ANY(scopes)
        """))
        targets = r.mappings().all()
    except Exception as e:
        log.warning("fire_event lookup failed: %s", e)
        return

    if not targets:
        return

    body = json.dumps({"event": event, "data": payload}, default=str, ensure_ascii=False).encode("utf-8")

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [_deliver(db, client, dict(t), event, body, payload) for t in targets]
        await asyncio.gather(*tasks, return_exceptions=True)


async def _deliver(
    db: AsyncSession,
    client: httpx.AsyncClient,
    key: dict,
    event: str,
    body: bytes,
    payload: dict,
) -> None:
    sig = ""
    if key.get("webhook_secret"):
        sig = hmac.new(
            key["webhook_secret"].encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
    status = 0
    resp_text = ""
    try:
        r = await client.post(
            key["webhook_url"],
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": sig,
                "X-Webhook-Event": event,
                "X-Webhook-App": key.get("app_name", ""),
            },
        )
        status = r.status_code
        resp_text = r.text[:2000]
    except Exception as e:
        resp_text = f"err: {e}"
    try:
        await db.execute(text("""
            INSERT INTO documents_webhook_deliveries
              (key_id, event, payload, url, status_code, response)
            VALUES (:k, :e, CAST(:p AS JSONB), :u, :s, :r)
        """), {
            "k": key["id"], "e": event, "p": json.dumps(payload, default=str, ensure_ascii=False),
            "u": key.get("webhook_url"), "s": status, "r": resp_text,
        })
        await db.commit()
    except Exception as e:
        log.warning("webhook delivery log failed: %s", e)
