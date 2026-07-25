"""Tests for /reminders auth gate and stub behavior."""

from fastapi.testclient import TestClient


def test_reminders_requires_auth(api_client: TestClient) -> None:
    resp = api_client.post(
        "/reminders/",
        json={"events": [], "phone_number": "+15555550100"},
    )
    assert resp.status_code == 401


def test_reminders_returns_501_when_authed(
    authenticated_client: TestClient,
) -> None:
    resp = authenticated_client.post(
        "/reminders/",
        json={"events": [], "phone_number": "+15555550100"},
    )
    assert resp.status_code == 501
    assert resp.json()["detail"] == "SMS reminders not yet implemented"
