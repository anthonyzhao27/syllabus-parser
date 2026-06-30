"""Unit tests for storage service threadpool-wrapped Supabase calls."""

import io
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services import storage


def _make_upload_file(
    content: bytes, content_type: str = "application/pdf"
) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename="syllabus.pdf",
        headers={"content-type": content_type},
    )


def _mock_bucket(client: MagicMock) -> MagicMock:
    bucket = MagicMock()
    client.storage.from_.return_value = bucket
    return bucket


@pytest.mark.asyncio
async def test_upload_file_runs_sync_call_in_threadpool() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)

    with patch.object(storage, "get_authenticated_client", return_value=client):
        result = await storage.upload_file(
            _make_upload_file(b"pdf-bytes"), "user-1", "token-1"
        )

    bucket.upload.assert_called_once()
    assert result["size"] == len(b"pdf-bytes")
    assert str(result["path"]).startswith("user-1/")


@pytest.mark.asyncio
async def test_upload_file_wraps_failure_in_http_exception() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)
    bucket.upload.side_effect = RuntimeError("boom")

    with patch.object(storage, "get_authenticated_client", return_value=client):
        with pytest.raises(HTTPException) as exc:
            await storage.upload_file(_make_upload_file(b"x"), "user-1", "token-1")

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_download_file_returns_bytes() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)
    bucket.download.return_value = b"file-content"

    with patch.object(storage, "get_authenticated_client", return_value=client):
        content = await storage.download_file("user-1/file.pdf", "token-1")

    assert content == b"file-content"
    bucket.download.assert_called_once_with("user-1/file.pdf")


@pytest.mark.asyncio
async def test_download_file_missing_raises_404() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)
    bucket.download.side_effect = RuntimeError("missing")

    with patch.object(storage, "get_authenticated_client", return_value=client):
        with pytest.raises(HTTPException) as exc:
            await storage.download_file("user-1/file.pdf", "token-1")

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_file_removes_path() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)

    with patch.object(storage, "get_authenticated_client", return_value=client):
        await storage.delete_file("user-1/file.pdf", "token-1")

    bucket.remove.assert_called_once_with(["user-1/file.pdf"])


@pytest.mark.asyncio
async def test_delete_file_failure_raises_503() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)
    bucket.remove.side_effect = RuntimeError("boom")

    with patch.object(storage, "get_authenticated_client", return_value=client):
        with pytest.raises(HTTPException) as exc:
            await storage.delete_file("user-1/file.pdf", "token-1")

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_delete_file_best_effort_swallows_errors() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)
    bucket.remove.side_effect = RuntimeError("boom")

    with patch.object(storage, "get_authenticated_client", return_value=client):
        ok = await storage.delete_file_best_effort("user-1/file.pdf", "token-1")

    assert ok is False


@pytest.mark.asyncio
async def test_download_files_as_zip_packs_files() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)
    bucket.download.side_effect = [b"one", b"two"]

    with patch.object(storage, "get_authenticated_client", return_value=client):
        zip_bytes = await storage.download_files_as_zip(
            ["user-1/a.pdf", "user-1/b.pdf"], "token-1"
        )

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert sorted(zf.namelist()) == ["a.pdf", "b.pdf"]
        assert zf.read("a.pdf") == b"one"
        assert zf.read("b.pdf") == b"two"


@pytest.mark.asyncio
async def test_download_files_as_zip_failure_raises_503() -> None:
    client = MagicMock()
    bucket = _mock_bucket(client)
    bucket.download.side_effect = RuntimeError("boom")

    with patch.object(storage, "get_authenticated_client", return_value=client):
        with pytest.raises(HTTPException) as exc:
            await storage.download_files_as_zip(["user-1/a.pdf"], "token-1")

    assert exc.value.status_code == 503
