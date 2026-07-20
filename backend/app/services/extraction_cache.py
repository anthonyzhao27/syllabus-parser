"""Content-hash cache for extracted text.

Runs under the caller's authenticated (user-token) client + RLS — no
service-role key. The cache is global/shared across users; the key is
sha256(file bytes), so a lookup only succeeds for a file you already possess.
"""

import hashlib
import logging
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.models.db import get_authenticated_client

logger = logging.getLogger(__name__)

TABLE = "extraction_cache"


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_hash_multi(parts: list[bytes]) -> str:
    """Order-sensitive hash across multiple byte blobs (e.g., screenshot set)."""
    h = hashlib.sha256()
    for part in parts:
        h.update(hashlib.sha256(part).digest())
    return h.hexdigest()


def _select_sync(content_hash: str, access_token: str) -> str | None:
    client = get_authenticated_client(access_token)
    res = (
        client.table(TABLE)
        .select("extracted_text")
        .eq("content_hash", content_hash)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    text = rows[0].get("extracted_text") if isinstance(rows[0], dict) else None
    return text if isinstance(text, str) else None


def _touch_sync(content_hash: str, access_token: str) -> None:
    client = get_authenticated_client(access_token)
    client.table(TABLE).update(
        {"last_hit_at": datetime.now(timezone.utc).isoformat()}
    ).eq("content_hash", content_hash).execute()


def _upsert_sync(
    content_hash: str,
    extracted_text: str,
    source_mime: str,
    vision_model: str | None,
    vision_used: bool,
    byte_size: int,
    access_token: str,
) -> None:
    client = get_authenticated_client(access_token)
    client.table(TABLE).upsert(
        {
            "content_hash": content_hash,
            "extracted_text": extracted_text,
            "source_mime": source_mime,
            "vision_model": vision_model,
            "vision_used": vision_used,
            "byte_size": byte_size,
        },
        on_conflict="content_hash",
        ignore_duplicates=True,
    ).execute()


async def get_cached(content_hash: str, access_token: str) -> str | None:
    if not settings.extraction_cache_enabled:
        return None
    try:
        text = await run_in_threadpool(_select_sync, content_hash, access_token)
    except Exception:
        logger.warning("extraction_cache lookup failed", exc_info=True)
        return None
    if not text:
        return None
    try:
        await run_in_threadpool(_touch_sync, content_hash, access_token)
    except Exception:
        logger.warning("extraction_cache touch failed", exc_info=True)
    return text


async def put_cached(
    content_hash: str,
    extracted_text: str,
    source_mime: str,
    vision_model: str | None,
    vision_used: bool,
    byte_size: int,
    access_token: str,
) -> None:
    if not settings.extraction_cache_enabled:
        return
    if not extracted_text:
        return
    try:
        await run_in_threadpool(
            _upsert_sync,
            content_hash,
            extracted_text,
            source_mime,
            vision_model,
            vision_used,
            byte_size,
            access_token,
        )
    except Exception:
        logger.warning("extraction_cache write failed", exc_info=True)
