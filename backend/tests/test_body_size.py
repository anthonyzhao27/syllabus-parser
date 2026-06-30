"""Tests for the request body size cap in BodySizeLimitMiddleware."""

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.config import settings
from app.middleware.limiter import MAX_BODY_BYTES, BodySizeLimitMiddleware


def test_max_body_bytes_is_file_limit_plus_one_mb_margin() -> None:
    """The cap should be the file limit + a 1MB multipart overhead margin.

    Guards against the regression where a stray ``* 11`` inflated the body
    cap to ~110MB and defeated the intended ~10MB file limit.
    """
    file_limit = settings.max_file_size_mb * 1024 * 1024
    assert MAX_BODY_BYTES == file_limit + 1024 * 1024
    # Sanity: nowhere near the ~110MB the buggy multiplier produced.
    assert MAX_BODY_BYTES < 2 * file_limit


def _client() -> TestClient:
    async def ok(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/upload", ok, methods=["POST"])])
    app.add_middleware(BodySizeLimitMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_body_just_over_cap_returns_413() -> None:
    client = _client()
    resp = client.post(
        "/upload",
        content=b"",
        headers={"content-length": str(MAX_BODY_BYTES + 1)},
    )
    assert resp.status_code == 413
    assert resp.json()["detail"] == "Request body too large"


def test_body_at_cap_passes() -> None:
    client = _client()
    resp = client.post(
        "/upload",
        content=b"",
        headers={"content-length": str(MAX_BODY_BYTES)},
    )
    assert resp.status_code == 200


def test_body_under_cap_passes() -> None:
    client = _client()
    # A 10MB-ish file plus a little form overhead, under the cap.
    under = settings.max_file_size_mb * 1024 * 1024 + 512 * 1024
    resp = client.post(
        "/upload",
        content=b"",
        headers={"content-length": str(under)},
    )
    assert resp.status_code == 200
