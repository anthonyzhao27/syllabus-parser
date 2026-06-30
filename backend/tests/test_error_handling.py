"""Tests for the generic exception handler and request-id correlation."""

import uuid

from fastapi.testclient import TestClient

from app.main import app


def _add_boom_route() -> None:
    """Register a throwaway route that always raises (idempotent)."""
    if any(getattr(r, "path", None) == "/_boom" for r in app.router.routes):
        return

    @app.get("/_boom")
    async def _boom():
        raise RuntimeError("kaboom")


def test_unhandled_exception_returns_clean_500_json(
    api_client: TestClient,
) -> None:
    _add_boom_route()

    resp = api_client.get("/_boom")

    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"] == "Internal server error"
    # request_id is present in the body and is a valid uuid4 string.
    assert "request_id" in body
    uuid.UUID(body["request_id"])

    # No traceback leaks into the response body.
    text = resp.text
    assert "Traceback" not in text
    assert "kaboom" not in text
    assert "RuntimeError" not in text


def test_unhandled_exception_includes_request_id_header(
    api_client: TestClient,
) -> None:
    _add_boom_route()

    resp = api_client.get("/_boom")

    assert "X-Request-ID" in resp.headers
    header_id = resp.headers["X-Request-ID"]
    uuid.UUID(header_id)
    # The header id matches the id reported in the JSON body.
    assert resp.json()["request_id"] == header_id


def test_successful_request_sets_request_id_header(
    api_client: TestClient,
) -> None:
    resp = api_client.get("/health")

    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    uuid.UUID(resp.headers["X-Request-ID"])
