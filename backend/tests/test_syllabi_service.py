"""Unit tests for syllabi service threadpool-wrapped Supabase calls."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.schemas import ParsedEvent
from app.services import syllabi


def _fluent_client(data: object) -> MagicMock:
    """A Supabase client whose fluent query chain ends in execute() -> data.

    Every chained builder method (table/select/insert/update/eq/...) returns
    the same mock, so the test does not depend on the exact call order, and
    ``.execute()`` yields a result object carrying ``data``.
    """
    result = MagicMock()
    result.data = data

    chain = MagicMock()
    chain.table.return_value = chain
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = result
    return chain


@pytest.mark.asyncio
async def test_create_syllabus_returns_first_row() -> None:
    client = _fluent_client([{"id": "syllabus-1"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        row = await syllabi.create_syllabus("token-1", "user-1", "CS101", "file")

    assert row == {"id": "syllabus-1"}


@pytest.mark.asyncio
async def test_create_syllabus_raises_when_empty() -> None:
    client = _fluent_client([])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        with pytest.raises(RuntimeError):
            await syllabi.create_syllabus("token-1", "user-1", "CS101", "file")


@pytest.mark.asyncio
async def test_get_syllabus_found() -> None:
    client = _fluent_client([{"id": "syllabus-1"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        row = await syllabi.get_syllabus("token-1", "syllabus-1")

    assert row == {"id": "syllabus-1"}


@pytest.mark.asyncio
async def test_get_syllabus_missing_returns_none() -> None:
    client = _fluent_client([])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        row = await syllabi.get_syllabus("token-1", "syllabus-1")

    assert row is None


@pytest.mark.asyncio
async def test_list_syllabi_returns_rows() -> None:
    client = _fluent_client([{"id": "a"}, {"id": "b"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        rows = await syllabi.list_syllabi("token-1")

    assert rows == [{"id": "a"}, {"id": "b"}]


@pytest.mark.asyncio
async def test_delete_syllabus_truthiness() -> None:
    client = _fluent_client([{"id": "a"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        assert await syllabi.delete_syllabus("token-1", "a") is True


@pytest.mark.asyncio
async def test_save_events_empty_short_circuits() -> None:
    with patch.object(syllabi, "get_authenticated_client") as mock_client:
        result = await syllabi.save_events("token-1", "syllabus-1", "user-1", [])

    assert result == []
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_save_events_inserts_records() -> None:
    client = _fluent_client([{"id": "event-1"}])
    events = [
        ParsedEvent(
            title="Homework 1",
            due_date=datetime(2025, 1, 30),
            course="CS 101",
            event_type="assignment",
        )
    ]

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        rows = await syllabi.save_events("token-1", "syllabus-1", "user-1", events)

    assert rows == [{"id": "event-1"}]


@pytest.mark.asyncio
async def test_get_events_for_syllabus() -> None:
    client = _fluent_client([{"id": "event-1"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        rows = await syllabi.get_events_for_syllabus("token-1", "syllabus-1")

    assert rows == [{"id": "event-1"}]


@pytest.mark.asyncio
async def test_get_event_counts_empty_input() -> None:
    with patch.object(syllabi, "get_authenticated_client") as mock_client:
        counts = await syllabi.get_event_counts_for_syllabi("token-1", [])

    assert counts == {}
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_get_event_counts_tallies_rows() -> None:
    client = _fluent_client(
        [
            {"syllabus_id": "a"},
            {"syllabus_id": "a"},
            {"syllabus_id": "b"},
        ]
    )

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        counts = await syllabi.get_event_counts_for_syllabi("token-1", ["a", "b"])

    assert counts == {"a": 2, "b": 1}


@pytest.mark.asyncio
async def test_get_event_found() -> None:
    client = _fluent_client([{"id": "event-1"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        row = await syllabi.get_event("token-1", "event-1", "syllabus-1")

    assert row == {"id": "event-1"}


@pytest.mark.asyncio
async def test_update_event_returns_row() -> None:
    client = _fluent_client([{"id": "event-1", "is_edited": True}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        row = await syllabi.update_event(
            "token-1", "event-1", "syllabus-1", {"title": "x"}
        )

    assert row == {"id": "event-1", "is_edited": True}


@pytest.mark.asyncio
async def test_soft_delete_event_truthiness() -> None:
    client = _fluent_client([{"id": "event-1"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        assert await syllabi.soft_delete_event("token-1", "event-1", "syllabus-1")


@pytest.mark.asyncio
async def test_update_syllabus_timezone() -> None:
    client = _fluent_client([{"id": "syllabus-1", "timezone": "UTC"}])

    with patch.object(syllabi, "get_authenticated_client", return_value=client):
        row = await syllabi.update_syllabus_timezone("token-1", "syllabus-1", "UTC")

    assert row == {"id": "syllabus-1", "timezone": "UTC"}
