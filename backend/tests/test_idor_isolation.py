"""Cross-user isolation (IDOR) safety-invariant tests.

The app does NOT filter user-scoped reads/writes by ``user_id`` in service
code. It relies on Supabase Row Level Security (RLS), which is only enforced
when queries run through the *authenticated* (user-token) Supabase client
created by ``get_authenticated_client(access_token)``. The anon/service-role
key bypasses RLS, so routing a user-scoped read or write through anything other
than the user's own token would let one user read or mutate another user's
data.

These tests pin the invariants that keep RLS effective:

1. Every user-scoped service path builds its Supabase client from the caller's
   access token (and ONLY that token).
2. Resource ids handed to a service are pushed into the query filters that run
   under that same user-token client.
3. Routers forward the authenticated user's own token into the services.
4. ``app.models.db`` exposes no RLS-bypassing (service-role) client, and the
   one client it does expose attaches the user's bearer token.

A regression that swaps a user-scoped query onto a service-role client, or that
drops/forwards the wrong access token, should make these tests FAIL.
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models import db
from app.models.schemas import EventType, ParsedEvent
from app.services import storage as storage_service
from app.services import syllabi as syllabi_service

USER_TOKEN = "user-a-access-token"
OTHER_USER_TOKEN = "user-b-access-token"
SYLLABUS_ID = "syllabus-123"
EVENT_ID = "event-456"


class _RecordingQuery:
    """A Supabase query stub that records the filters applied to it.

    Every builder method (``select``, ``eq``, ``insert``, ...) returns ``self``
    so the fluent chain used in ``app/services`` keeps working, while we capture
    the ``.eq(...)`` filters and terminal calls for assertions.
    """

    def __init__(self, result_rows: list[dict[str, object]]):
        self._result_rows = result_rows
        self.eq_calls: list[tuple[str, object]] = []
        self.in_calls: list[tuple[str, object]] = []
        self.terminal_calls: list[str] = []

    def select(self, *args: object, **kwargs: object) -> "_RecordingQuery":
        return self

    def insert(self, *args: object, **kwargs: object) -> "_RecordingQuery":
        self.terminal_calls.append("insert")
        return self

    def update(self, *args: object, **kwargs: object) -> "_RecordingQuery":
        self.terminal_calls.append("update")
        return self

    def delete(self, *args: object, **kwargs: object) -> "_RecordingQuery":
        self.terminal_calls.append("delete")
        return self

    def eq(self, column: str, value: object) -> "_RecordingQuery":
        self.eq_calls.append((column, value))
        return self

    def in_(self, column: str, value: object) -> "_RecordingQuery":
        self.in_calls.append((column, value))
        return self

    def order(self, *args: object, **kwargs: object) -> "_RecordingQuery":
        return self

    def limit(self, *args: object, **kwargs: object) -> "_RecordingQuery":
        return self

    def execute(self) -> MagicMock:
        result = MagicMock()
        result.data = self._result_rows
        return result


class _RecordingClient:
    """Stand-in for the Supabase client returned by get_authenticated_client."""

    def __init__(self, result_rows: list[dict[str, object]] | None = None):
        self._result_rows = result_rows if result_rows is not None else [{"id": "ok"}]
        self.table_names: list[str] = []
        self.queries: list[_RecordingQuery] = []

    def table(self, name: str) -> _RecordingQuery:
        self.table_names.append(name)
        query = _RecordingQuery(self._result_rows)
        self.queries.append(query)
        return query


# ---------------------------------------------------------------------------
# Invariant 1 + 2: every user-scoped syllabi service call runs under the
# caller's access token and forwards resource ids into the query filters.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_syllabus_uses_caller_token_and_filters_by_id() -> None:
    client = _RecordingClient([{"id": SYLLABUS_ID}])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.get_syllabus(USER_TOKEN, SYLLABUS_ID)

    # Built from the caller's token only — never a hardcoded/other token.
    mock_client.assert_called_once_with(USER_TOKEN)
    assert client.table_names == ["syllabi"]
    # The resource id is pushed into a filter that runs under the user token.
    assert ("id", SYLLABUS_ID) in client.queries[0].eq_calls


@pytest.mark.asyncio
async def test_delete_syllabus_uses_caller_token_and_filters_by_id() -> None:
    client = _RecordingClient([{"id": SYLLABUS_ID}])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.delete_syllabus(USER_TOKEN, SYLLABUS_ID)

    mock_client.assert_called_once_with(USER_TOKEN)
    assert client.table_names == ["syllabi"]
    assert "delete" in client.queries[0].terminal_calls
    assert ("id", SYLLABUS_ID) in client.queries[0].eq_calls


@pytest.mark.asyncio
async def test_list_syllabi_uses_caller_token() -> None:
    client = _RecordingClient([])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.list_syllabi(USER_TOKEN)

    mock_client.assert_called_once_with(USER_TOKEN)
    assert client.table_names == ["syllabi"]


@pytest.mark.asyncio
async def test_update_syllabus_timezone_uses_caller_token_and_filters_by_id() -> None:
    client = _RecordingClient([{"id": SYLLABUS_ID}])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.update_syllabus_timezone(
            USER_TOKEN, SYLLABUS_ID, "America/Toronto"
        )

    mock_client.assert_called_once_with(USER_TOKEN)
    assert "update" in client.queries[0].terminal_calls
    assert ("id", SYLLABUS_ID) in client.queries[0].eq_calls


@pytest.mark.asyncio
async def test_get_events_for_syllabus_uses_caller_token_and_filters_by_id() -> None:
    client = _RecordingClient([])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.get_events_for_syllabus(USER_TOKEN, SYLLABUS_ID)

    mock_client.assert_called_once_with(USER_TOKEN)
    assert client.table_names == ["events"]
    assert ("syllabus_id", SYLLABUS_ID) in client.queries[0].eq_calls


@pytest.mark.asyncio
async def test_get_event_uses_caller_token_and_filters_by_both_ids() -> None:
    client = _RecordingClient([{"id": EVENT_ID}])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.get_event(USER_TOKEN, EVENT_ID, SYLLABUS_ID)

    mock_client.assert_called_once_with(USER_TOKEN)
    assert client.table_names == ["events"]
    eq_calls = client.queries[0].eq_calls
    assert ("id", EVENT_ID) in eq_calls
    assert ("syllabus_id", SYLLABUS_ID) in eq_calls


@pytest.mark.asyncio
async def test_update_event_uses_caller_token_and_filters_by_both_ids() -> None:
    client = _RecordingClient([{"id": EVENT_ID}])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.update_event(
            USER_TOKEN, EVENT_ID, SYLLABUS_ID, {"title": "x"}
        )

    mock_client.assert_called_once_with(USER_TOKEN)
    assert "update" in client.queries[0].terminal_calls
    eq_calls = client.queries[0].eq_calls
    assert ("id", EVENT_ID) in eq_calls
    assert ("syllabus_id", SYLLABUS_ID) in eq_calls


@pytest.mark.asyncio
async def test_soft_delete_event_uses_caller_token_and_filters_by_both_ids() -> None:
    client = _RecordingClient([{"id": EVENT_ID}])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.soft_delete_event(USER_TOKEN, EVENT_ID, SYLLABUS_ID)

    mock_client.assert_called_once_with(USER_TOKEN)
    assert "update" in client.queries[0].terminal_calls
    eq_calls = client.queries[0].eq_calls
    assert ("id", EVENT_ID) in eq_calls
    assert ("syllabus_id", SYLLABUS_ID) in eq_calls


@pytest.mark.asyncio
async def test_create_syllabus_uses_caller_token() -> None:
    client = _RecordingClient([{"id": SYLLABUS_ID}])
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.create_syllabus(
            USER_TOKEN,
            "user-a",
            name="CS101",
            source_type="file",
        )

    mock_client.assert_called_once_with(USER_TOKEN)
    assert client.table_names == ["syllabi"]
    assert "insert" in client.queries[0].terminal_calls


@pytest.mark.asyncio
async def test_save_events_uses_caller_token_and_scopes_to_syllabus() -> None:
    client = _RecordingClient([{"id": EVENT_ID}])
    events = [
        ParsedEvent(
            title="HW1",
            due_date="2025-01-30",
            course="CS101",
            event_type=EventType.ASSIGNMENT,
            description="",
            time_specified=False,
        )
    ]
    with patch.object(
        syllabi_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await syllabi_service.save_events(USER_TOKEN, SYLLABUS_ID, "user-a", events)

    mock_client.assert_called_once_with(USER_TOKEN)
    assert client.table_names == ["events"]
    assert "insert" in client.queries[0].terminal_calls


# ---------------------------------------------------------------------------
# Invariant 1: storage (file) service paths run under the caller's token too,
# so one user's bearer token can't be used to fetch another user's files.
# ---------------------------------------------------------------------------


def _storage_client_mock() -> MagicMock:
    client = MagicMock()
    bucket = client.storage.from_.return_value
    bucket.download.return_value = b"bytes"
    bucket.remove.return_value = None
    bucket.upload.return_value = None
    return client


@pytest.mark.asyncio
async def test_download_file_uses_caller_token() -> None:
    client = _storage_client_mock()
    with patch.object(
        storage_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await storage_service.download_file("user-a/file.pdf", USER_TOKEN)

    mock_client.assert_called_once_with(USER_TOKEN)
    client.storage.from_.return_value.download.assert_called_once_with(
        "user-a/file.pdf"
    )


@pytest.mark.asyncio
async def test_download_files_as_zip_uses_caller_token() -> None:
    client = _storage_client_mock()
    with patch.object(
        storage_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await storage_service.download_files_as_zip(["user-a/file.pdf"], USER_TOKEN)

    mock_client.assert_called_once_with(USER_TOKEN)


@pytest.mark.asyncio
async def test_delete_file_best_effort_uses_caller_token() -> None:
    client = _storage_client_mock()
    with patch.object(
        storage_service, "get_authenticated_client", return_value=client
    ) as mock_client:
        await storage_service.delete_file_best_effort("user-a/file.pdf", USER_TOKEN)

    mock_client.assert_called_once_with(USER_TOKEN)


# ---------------------------------------------------------------------------
# Invariant 3: routers forward the authenticated user's OWN token (and the
# requested resource id) into the service layer. If a handler dropped the token
# or passed a different/shared one, RLS would not isolate the user.
# ---------------------------------------------------------------------------


@patch("app.routers.files.syllabi_service.get_syllabus", new_callable=AsyncMock)
@patch(
    "app.routers.files.syllabi_service.get_events_for_syllabus",
    new_callable=AsyncMock,
)
def test_get_syllabus_detail_forwards_user_token_and_id(
    mock_get_events: AsyncMock,
    mock_get_syllabus: AsyncMock,
    authenticated_client: TestClient,
) -> None:
    mock_get_syllabus.return_value = {
        "id": SYLLABUS_ID,
        "name": "CS101",
        "course_code": "CS101",
        "source_type": "file",
        "original_filename": "s.pdf",
        "created_at": "2025-01-01T00:00:00+00:00",
        "storage_paths": [],
    }
    mock_get_events.return_value = []

    response = authenticated_client.get(f"/files/{SYLLABUS_ID}")

    assert response.status_code == 200
    # test_user.access_token is "test-token" (see conftest).
    assert mock_get_syllabus.await_args.args == ("test-token", SYLLABUS_ID)
    assert mock_get_events.await_args.args == ("test-token", SYLLABUS_ID)


@patch("app.routers.files.syllabi_service.soft_delete_event", new_callable=AsyncMock)
def test_delete_event_forwards_user_token_and_ids(
    mock_soft_delete: AsyncMock,
    authenticated_client: TestClient,
) -> None:
    mock_soft_delete.return_value = True

    response = authenticated_client.delete(f"/files/{SYLLABUS_ID}/events/{EVENT_ID}")

    assert response.status_code == 200
    assert mock_soft_delete.await_args.args == ("test-token", EVENT_ID, SYLLABUS_ID)


@patch("app.routers.files.syllabi_service.list_syllabi", new_callable=AsyncMock)
@patch(
    "app.routers.files.syllabi_service.get_event_counts_for_syllabi",
    new_callable=AsyncMock,
)
def test_list_syllabi_forwards_user_token(
    mock_counts: AsyncMock,
    mock_list: AsyncMock,
    authenticated_client: TestClient,
) -> None:
    mock_list.return_value = []
    mock_counts.return_value = {}

    response = authenticated_client.get("/files/")

    assert response.status_code == 200
    assert mock_list.await_args.args[0] == "test-token"


# ---------------------------------------------------------------------------
# Invariant 4: app.models.db exposes only the user-token client, and it always
# attaches the caller's bearer token. No RLS-bypassing service-role client.
# ---------------------------------------------------------------------------


def test_db_module_exposes_no_service_role_client() -> None:
    """Guard against introducing an RLS-bypassing service-role client.

    The only client factory must be the authenticated (user-token) one. A new
    factory built from a service-role/secret key would let callers bypass RLS,
    so this fails loudly the moment one is added to app.models.db.
    """
    public_callables = {
        name
        for name, obj in vars(db).items()
        if not name.startswith("_") and callable(obj) and inspect.isfunction(obj)
    }
    assert public_callables == {"get_authenticated_client"}

    source = inspect.getsource(db)
    forbidden = ("service_role", "service_key", "service-role", "SUPABASE_SERVICE")
    for token in forbidden:
        assert token not in source, f"service-role reference {token!r} found in db.py"


def test_authenticated_client_attaches_caller_bearer_token() -> None:
    """get_authenticated_client must put the caller's token in the auth header.

    Dropping the bearer header would make every request anonymous (no RLS
    subject), so this pins that the token flows into the client options.
    """
    captured: dict[str, object] = {}

    def fake_create_client(url: str, key: str, options: object) -> MagicMock:
        captured["url"] = url
        captured["key"] = key
        captured["options"] = options
        return MagicMock()

    with (
        patch.object(db, "create_client", side_effect=fake_create_client),
        patch.object(db.settings, "supabase_url", "https://example.supabase.co"),
        patch.object(db.settings, "supabase_anon_key", "anon-key"),
    ):
        db.get_authenticated_client(USER_TOKEN)

    headers = getattr(captured["options"], "headers", {})
    assert headers.get("Authorization") == f"Bearer {USER_TOKEN}"
    # Built off the anon key (RLS-enforcing), never a service-role key.
    assert captured["key"] == "anon-key"


def test_authenticated_client_is_per_token_not_shared() -> None:
    """Two different tokens must yield two distinct authenticated clients.

    If clients were cached/shared across tokens, one user's request could ride
    another user's session. Pin that each call builds a fresh client carrying
    its own token.
    """
    seen_tokens: list[str] = []

    def fake_create_client(url: str, key: str, options: object) -> MagicMock:
        headers = getattr(options, "headers", {})
        seen_tokens.append(headers.get("Authorization", ""))
        return MagicMock()

    with (
        patch.object(db, "create_client", side_effect=fake_create_client),
        patch.object(db.settings, "supabase_url", "https://example.supabase.co"),
        patch.object(db.settings, "supabase_anon_key", "anon-key"),
    ):
        client_a = db.get_authenticated_client(USER_TOKEN)
        client_b = db.get_authenticated_client(OTHER_USER_TOKEN)

    assert client_a is not client_b
    assert seen_tokens == [
        f"Bearer {USER_TOKEN}",
        f"Bearer {OTHER_USER_TOKEN}",
    ]
