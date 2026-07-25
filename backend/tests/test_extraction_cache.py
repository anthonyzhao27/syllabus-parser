"""Tests for the extraction cache (authenticated-client + RLS, no service-role)."""

from unittest.mock import MagicMock, patch

import pytest

from app.services import extraction_cache


def _client_returning(rows: list[dict]) -> MagicMock:
    client = MagicMock()
    chain = client.table.return_value.select.return_value
    chain = chain.eq.return_value.limit.return_value
    chain.execute.return_value.data = rows
    return client


def test_compute_hash_is_content_addressed() -> None:
    assert extraction_cache.compute_hash(b"abc") == extraction_cache.compute_hash(
        b"abc"
    )
    assert extraction_cache.compute_hash(b"abc") != extraction_cache.compute_hash(
        b"abd"
    )


@pytest.mark.asyncio
async def test_get_cached_hit_uses_authenticated_client() -> None:
    client = _client_returning([{"extracted_text": "cached text"}])
    with patch(
        "app.services.extraction_cache.get_authenticated_client", return_value=client
    ) as mock_auth:
        result = await extraction_cache.get_cached("hash123", "user-token")

    assert result == "cached text"
    # Must build the client from the caller's token (RLS), not a service-role key.
    mock_auth.assert_called_with("user-token")


@pytest.mark.asyncio
async def test_get_cached_miss_returns_none() -> None:
    client = _client_returning([])
    with patch(
        "app.services.extraction_cache.get_authenticated_client", return_value=client
    ):
        result = await extraction_cache.get_cached("missing", "user-token")
    assert result is None


@pytest.mark.asyncio
async def test_cache_disabled_skips_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extraction_cache.settings, "extraction_cache_enabled", False)
    with patch("app.services.extraction_cache.get_authenticated_client") as mock_auth:
        assert await extraction_cache.get_cached("h", "tok") is None
        await extraction_cache.put_cached(
            content_hash="h",
            extracted_text="t",
            source_mime="application/pdf",
            vision_model=None,
            vision_used=False,
            byte_size=1,
            access_token="tok",
        )
    # No DB client is constructed at all when the cache is disabled.
    mock_auth.assert_not_called()


@pytest.mark.asyncio
async def test_get_cached_fails_open_on_db_error() -> None:
    with patch(
        "app.services.extraction_cache.get_authenticated_client",
        side_effect=RuntimeError("db down"),
    ):
        # A cache failure must never break a parse — it degrades to a miss.
        assert await extraction_cache.get_cached("h", "tok") is None
