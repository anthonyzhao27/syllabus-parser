"""Tests for text extraction service."""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.config import settings
from app.services.extraction import (
    MAX_PDF_PAGES,
    MAX_SCREENSHOT_IMAGES,
    OPENAI_VISION_TIMEOUT_SECONDS,
    _extract_docx,
    _extract_images_via_vision,
    _extract_pdf,
    _extract_pdf_text,
    _is_image,
    _pdf_pages_to_base64_images,
    classify_upload,
    detect_mime,
    extract_text,
    extract_text_from_images,
)

# ── PDF ──────────────────────────────────────────────


def test_extract_pdf_text(generated_pdf_path: Path) -> None:
    data = generated_pdf_path.read_bytes()
    text = _extract_pdf_text(data)
    assert "Homework 1" in text
    assert "January 30" in text


# ── DOCX ─────────────────────────────────────────────


def test_extract_docx(generated_docx_path: Path) -> None:
    data = generated_docx_path.read_bytes()
    text = _extract_docx(data)
    assert "Midterm Exam" in text
    assert "Quiz 1" in text


def test_extract_docx_rejects_zip_bomb(
    generated_docx_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When the total uncompressed size exceeds the cap, the DOCX is rejected
    # before python-docx decompresses it into memory (zip-bomb guard).
    monkeypatch.setattr("app.services.extraction.MAX_DOCX_UNCOMPRESSED_BYTES", 10)
    data = generated_docx_path.read_bytes()
    with pytest.raises(HTTPException) as exc:
        _extract_docx(data)
    assert exc.value.status_code == 422


# ── Dispatcher ───────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_text_pdf(generated_pdf_path: Path) -> None:
    file = AsyncMock()
    file.content_type = "application/pdf"
    file.filename = "syllabus.pdf"
    file.read = AsyncMock(return_value=generated_pdf_path.read_bytes())

    text = await extract_text(file)
    assert "Homework 1" in text


@pytest.mark.asyncio
async def test_extract_text_unsupported() -> None:
    file = AsyncMock()
    file.content_type = "image/png"
    file.filename = "photo.png"
    file.read = AsyncMock(return_value=b"fake")

    with pytest.raises(HTTPException) as exc:
        await extract_text(file)
    assert exc.value.status_code == 400


# ── Vision fallback ─────────────────────────────────


@pytest.mark.asyncio
async def test_extract_pdf_falls_back_to_vision() -> None:
    """When text extraction returns < 50 chars, vision fallback is triggered."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(50, 50, 100, 100), color=(0, 0, 0))
    scanned_pdf = doc.tobytes()
    doc.close()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Homework 1 due January 30, 2025"

    with patch("app.services.extraction.AsyncOpenAI") as MockClient:
        instance = AsyncMock()
        instance.chat.completions.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = instance

        text = await _extract_pdf(scanned_pdf)
        assert "Homework 1" in text
        instance.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_extract_pdf_skips_vision_when_text_found(
    generated_pdf_path: Path,
) -> None:
    """When text extraction succeeds, vision is NOT called."""
    data = generated_pdf_path.read_bytes()

    with patch("app.services.extraction._extract_pdf_via_vision") as mock_vision:
        text = await _extract_pdf(data)
        assert "Homework 1" in text
        mock_vision.assert_not_called()


def test_pdf_pages_to_base64_images(generated_pdf_path: Path) -> None:
    """Verify page-to-image conversion produces valid base64."""
    data = generated_pdf_path.read_bytes()
    images = _pdf_pages_to_base64_images(data, max_pages=1)
    assert len(images) == 1
    decoded = base64.b64decode(images[0])
    assert decoded[:4] == b"\x89PNG"


# ── Screenshot extraction ────────────────────────────


@pytest.mark.asyncio
async def test_extract_text_from_images() -> None:
    """Multi-image screenshot extraction calls vision with all images."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Quiz 1 due Feb 14, 2025"

    fake_png = b"\x89PNG" + b"\x00" * 100
    file1 = AsyncMock()
    file1.read = AsyncMock(return_value=fake_png)
    file2 = AsyncMock()
    file2.read = AsyncMock(return_value=fake_png)

    with patch("app.services.extraction.AsyncOpenAI") as MockClient:
        instance = AsyncMock()
        instance.chat.completions.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = instance

        text = await extract_text_from_images([file1, file2])
        assert "Quiz 1" in text

        call_args = instance.chat.completions.create.call_args
        msg_content = call_args.kwargs["messages"][0]["content"]
        image_parts = [c for c in msg_content if c["type"] == "image_url"]
        assert len(image_parts) == 2


@pytest.mark.asyncio
async def test_extract_text_from_images_too_many() -> None:
    """Reject more than 10 screenshots."""
    files = []
    for _ in range(11):
        f = AsyncMock()
        f.read = AsyncMock(return_value=b"\x89PNG" + b"\x00" * 10)
        files.append(f)

    with pytest.raises(HTTPException) as exc:
        await extract_text_from_images(files)
    assert exc.value.status_code == 400
    assert "10" in exc.value.detail


def test_is_image_detection() -> None:
    """_is_image correctly identifies image uploads."""
    img_file = MagicMock()
    img_file.content_type = "image/png"
    img_file.filename = "screenshot.png"
    assert _is_image(img_file) is True

    pdf_file = MagicMock()
    pdf_file.content_type = "application/pdf"
    pdf_file.filename = "syllabus.pdf"
    assert _is_image(pdf_file) is False


# ── Magic-byte MIME sniffing ─────────────────────────


def _mock_upload(data: bytes, filename: str = "upload"):
    file = AsyncMock()
    file.filename = filename
    file.content_type = None

    async def _read(size: int = -1) -> bytes:
        return data if size in (-1, None) or size >= len(data) else data[:size]

    file.read = _read
    file.seek = AsyncMock()
    return file


@pytest.mark.asyncio
async def test_detect_mime_pdf(generated_pdf_path: Path) -> None:
    file = _mock_upload(generated_pdf_path.read_bytes(), "syllabus.pdf")
    assert await detect_mime(file) == "application/pdf"


@pytest.mark.asyncio
async def test_detect_mime_png() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    file = _mock_upload(png, "screen.png")
    assert await detect_mime(file) == "image/png"


@pytest.mark.asyncio
async def test_detect_mime_rejects_mislabeled_executable() -> None:
    """A .exe renamed to .pdf must not be accepted as PDF."""
    file = _mock_upload(b"MZ\x90\x00<bogus>", "evil.pdf")
    file.content_type = "application/pdf"
    with pytest.raises(HTTPException) as exc:
        await detect_mime(file)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_classify_upload_rejects_zip_with_wrong_extension() -> None:
    """ZIP magic bytes but no .docx extension must be rejected."""
    file = _mock_upload(b"PK\x03\x04stuff", "evil.pdf")
    with pytest.raises(HTTPException) as exc:
        await classify_upload(file)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_classify_upload_accepts_docx_zip(
    generated_docx_path: Path,
) -> None:
    file = _mock_upload(generated_docx_path.read_bytes(), "syllabus.docx")
    assert await classify_upload(file) == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# ── PDF-bomb defense ─────────────────────────────────


def test_extract_pdf_rejects_over_page_limit() -> None:
    """A PDF claiming more than MAX_PDF_PAGES pages must be rejected with 413."""
    fake_doc = MagicMock()
    fake_doc.__len__ = lambda self: MAX_PDF_PAGES + 1
    fake_doc.__enter__ = lambda self: fake_doc
    fake_doc.__exit__ = lambda self, exc_type, exc, tb: None

    with patch("app.services.extraction.fitz.open", return_value=fake_doc):
        with patch("app.services.extraction.pdfplumber.open") as mock_pdfplumber:
            mock_pdf = MagicMock()
            mock_pdf.__enter__ = lambda self: mock_pdf
            mock_pdf.__exit__ = lambda self, exc_type, exc, tb: None
            mock_pdf.pages = [MagicMock()] * (MAX_PDF_PAGES + 1)
            mock_pdfplumber.return_value = mock_pdf

            with pytest.raises(HTTPException) as exc:
                _extract_pdf_text(b"%PDF-1.4\n" + b"\x00" * 100)
    assert exc.value.status_code == 413


# ── Cost & timeout guards ────────────────────────────


def test_pdf_page_cap_enforced_before_vision() -> None:
    """Pages beyond the vision cap are dropped before any vision call."""
    import fitz

    cap = settings.vision_max_pages
    doc = fitz.open()
    for _ in range(cap + 5):
        page = doc.new_page()
        page.draw_rect(fitz.Rect(10, 10, 20, 20), color=(0, 0, 0))
    data = doc.tobytes()
    doc.close()

    images = _pdf_pages_to_base64_images(data)
    assert len(images) == cap


@pytest.mark.asyncio
async def test_screenshot_cap_rejected_before_vision() -> None:
    """Too many screenshots is rejected without ever calling the vision API."""
    files = []
    for _ in range(MAX_SCREENSHOT_IMAGES + 1):
        f = AsyncMock()
        f.read = AsyncMock(return_value=b"\x89PNG" + b"\x00" * 10)
        files.append(f)

    with patch("app.services.extraction.AsyncOpenAI") as MockClient:
        with pytest.raises(HTTPException) as exc:
            await extract_text_from_images(files)

    assert exc.value.status_code == 400
    assert str(MAX_SCREENSHOT_IMAGES) in exc.value.detail
    MockClient.assert_not_called()


@pytest.mark.asyncio
async def test_vision_client_built_with_timeout() -> None:
    """The vision OpenAI client is constructed with an explicit timeout."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Quiz 1 due Feb 14"

    fake_png = b"\x89PNG" + b"\x00" * 50

    with patch("app.services.extraction.AsyncOpenAI") as MockClient:
        instance = AsyncMock()
        instance.chat.completions.create = AsyncMock(return_value=mock_response)
        MockClient.return_value = instance

        await _extract_images_via_vision([fake_png])

        timeout = MockClient.call_args.kwargs["timeout"]
        assert timeout == OPENAI_VISION_TIMEOUT_SECONDS


def test_vision_timeout_is_bounded() -> None:
    """Vision timeout is well under the SDK's 600s default."""
    assert 0 < OPENAI_VISION_TIMEOUT_SECONDS < 600
