"""Rate-limit smoke tests."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _ics_payload() -> dict[str, object]:
    return {
        "events": [
            {
                "title": "HW1",
                "due_date": "2025-01-30T23:59:00",
                "course": "CSC413",
                "event_type": "assignment",
                "description": "",
                "time_specified": False,
            }
        ],
        "filename": "syllabus.ics",
        "timezone": "America/Toronto",
    }


def test_ics_export_rate_limited_after_30_requests(
    authenticated_client: TestClient,
) -> None:
    """30/hour limit on /export/ics — 31st should return 429."""
    payload = _ics_payload()
    statuses: list[int] = []
    for _ in range(31):
        resp = authenticated_client.post("/export/ics", json=payload)
        statuses.append(resp.status_code)

    assert statuses[:30].count(200) == 30
    assert statuses[-1] == 429


@patch(
    "app.routers.reminders.setup_reminders",
    new_callable=AsyncMock,
)
def test_reminders_rate_limited_after_60_requests(
    _mock_handler: AsyncMock,
    authenticated_client: TestClient,
) -> None:
    """60/hour limit on /reminders — 61st should return 429."""
    body = {"events": [], "phone_number": "+15555550100"}
    statuses: list[int] = []
    for _ in range(61):
        resp = authenticated_client.post("/reminders/", json=body)
        statuses.append(resp.status_code)

    # First 60 hit the handler (which returns 501); 61st gets 429 from limiter.
    assert statuses[-1] == 429
