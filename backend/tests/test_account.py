"""Endpoint tests for self-serve account deletion.

The critical invariant under test: storage objects (which hold user PII)
are fully purged *before* the auth user is deleted, and a storage failure
aborts the deletion so it stays retryable instead of orphaning files.

Deletion now runs through the ``delete_current_user`` SECURITY DEFINER RPC
using the caller's own token — no service-role key in the backend.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

USER_ID = "00000000-0000-0000-0000-000000000001"


class FakeBucket:
    """Minimal stand-in for a Supabase storage bucket.

    ``tree`` maps a prefix to the entries ``list(prefix)`` should return, paged
    in chunks of ``page_size`` to exercise the pagination loop. Each entry is a
    dict shaped like the Supabase response: files carry an ``id``; folders do
    not. ``remove`` records and drops the requested paths.
    """

    def __init__(self, tree: dict[str, list[dict]], page_size: int = 100) -> None:
        self.tree = tree
        self.page_size = page_size
        self.removed: list[str] = []
        self.list_calls: list[tuple[str, dict]] = []

    def list(self, prefix, options=None):  # noqa: A003 - mirror SDK name
        options = options or {}
        self.list_calls.append((prefix, options))
        entries = list(self.tree.get(prefix, []))
        limit = options.get("limit", len(entries) or 1)
        offset = options.get("offset", 0)
        return entries[offset : offset + limit]  # noqa: E203

    def remove(self, paths):
        self.removed.extend(paths)
        # Drop removed files from the tree so a follow-up verification list is
        # empty, mimicking a successful delete.
        removed = set(paths)
        for prefix, entries in list(self.tree.items()):
            self.tree[prefix] = [
                e for e in entries if f"{prefix}/{e['name']}" not in removed
            ]


def _make_client(bucket: FakeBucket) -> MagicMock:
    client = MagicMock()
    client.storage.from_.return_value = bucket
    return client


def _file(name: str) -> dict:
    return {"name": name, "id": name}


def _folder(name: str) -> dict:
    return {"name": name, "id": None}


def test_delete_account_requires_auth(api_client: TestClient) -> None:
    response = api_client.delete("/account/")
    assert response.status_code == 401


@patch("app.routers.account.get_authenticated_client")
def test_delete_account_purges_storage_then_deletes_auth_user(
    mock_get_auth_client: MagicMock,
    authenticated_client: TestClient,
) -> None:
    bucket = FakeBucket({USER_ID: [_file("syllabus-1.pdf"), _file("syllabus-2.pdf")]})
    client = _make_client(bucket)
    mock_get_auth_client.return_value = client

    response = authenticated_client.delete("/account/")

    assert response.status_code == 204
    assert sorted(bucket.removed) == [
        f"{USER_ID}/syllabus-1.pdf",
        f"{USER_ID}/syllabus-2.pdf",
    ]
    # Auth user removed via the RPC (caller's token), not a service-role admin call.
    client.rpc.assert_called_once_with("delete_current_user", {})
    client.rpc.return_value.execute.assert_called_once()


@patch("app.routers.account.get_authenticated_client")
def test_storage_failure_aborts_auth_user_deletion(
    mock_get_auth_client: MagicMock,
    authenticated_client: TestClient,
) -> None:
    bucket = MagicMock()
    bucket.list.side_effect = RuntimeError("storage offline")
    client = _make_client(bucket)
    mock_get_auth_client.return_value = client

    response = authenticated_client.delete("/account/")

    # Storage purge failed -> we must NOT delete the auth user, and surface a
    # 500 so the client can retry.
    assert response.status_code == 500
    client.rpc.assert_not_called()


@patch("app.routers.account.get_authenticated_client")
def test_incomplete_purge_aborts_auth_user_deletion(
    mock_get_auth_client: MagicMock,
    authenticated_client: TestClient,
) -> None:
    # remove() is a no-op here, so objects remain after the purge attempt; the
    # verification pass must catch this and abort.
    bucket = MagicMock()
    bucket.list.return_value = [_file("leftover.pdf")]
    bucket.remove.return_value = None
    client = _make_client(bucket)
    mock_get_auth_client.return_value = client

    response = authenticated_client.delete("/account/")

    assert response.status_code == 500
    client.rpc.assert_not_called()


@patch("app.routers.account.get_authenticated_client")
def test_pagination_collects_more_than_one_page(
    mock_get_auth_client: MagicMock,
    authenticated_client: TestClient,
) -> None:
    # 250 objects > the 100-object page cap that the old buggy code stopped at.
    files = [_file(f"file-{i}.pdf") for i in range(250)]
    bucket = FakeBucket({USER_ID: files}, page_size=100)
    mock_get_auth_client.return_value = _make_client(bucket)

    response = authenticated_client.delete("/account/")

    assert response.status_code == 204
    # Every object across all pages must be removed, not just the first 100.
    assert len(bucket.removed) == 250
    assert f"{USER_ID}/file-249.pdf" in bucket.removed


@patch("app.routers.account.get_authenticated_client")
def test_pagination_recurses_into_nested_folders(
    mock_get_auth_client: MagicMock,
    authenticated_client: TestClient,
) -> None:
    bucket = FakeBucket(
        {
            USER_ID: [_file("top.pdf"), _folder("course-1")],
            f"{USER_ID}/course-1": [_file("nested.pdf")],
        }
    )
    mock_get_auth_client.return_value = _make_client(bucket)

    response = authenticated_client.delete("/account/")

    assert response.status_code == 204
    assert sorted(bucket.removed) == [
        f"{USER_ID}/course-1/nested.pdf",
        f"{USER_ID}/top.pdf",
    ]
