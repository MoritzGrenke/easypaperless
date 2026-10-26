"""Integration tests: document download — regression for issue #0037.

Verifies that documents.download(original=True) returns the original uploaded
file and documents.download(original=False) returns the archived PDF.
"""

from __future__ import annotations

import struct
import tempfile
import zlib
from pathlib import Path

import pytest

from easypaperless import PaperlessClient
from tests.integration._cleanup import purge_document

# ---------------------------------------------------------------------------
# Minimal PNG helper (pure Python, no external deps)
# ---------------------------------------------------------------------------


def _make_png(uid: str, width: int = 50, height: int = 50, dpi: int = 72) -> bytes:
    """Build a minimal valid RGB PNG with DPI metadata and a unique ID.

    Uses only stdlib (struct + zlib) so no Pillow dependency is needed.
    The ``uid`` is embedded as a PNG tEXt chunk so every call with a different
    uid produces distinct bytes — Paperless-ngx duplicate detection won't fire.
    """

    def _chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    # IHDR — dimensions, 8-bit RGB, no interlace
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

    # pHYs — DPI → pixels per metre (1 inch = 0.0254 m)
    ppm = round(dpi / 0.0254)
    phys = _chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))

    # tEXt — embed uid so each call produces unique bytes
    text = _chunk(b"tEXt", b"Comment\x00" + uid.encode())

    # IDAT — solid white image
    raw = b""
    for _ in range(height):
        raw += b"\x00" + b"\xff\xff\xff" * width  # filter=None + RGB white
    idat = _chunk(b"IDAT", zlib.compress(raw))

    iend = _chunk(b"IEND", b"")

    return b"\x89PNG\r\n\x1a\n" + ihdr + phys + text + idat + iend


_PNG_MAGIC = b"\x89PNG"
_PDF_MAGIC = b"%PDF-"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_download_original_returns_png_not_pdf(client: PaperlessClient, uid: str) -> None:
    """Regression test for #0037.

    Uploads a PNG document and verifies that download(original=True) returns
    the original PNG bytes, not the archived PDF.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(_make_png(uid))
        tmp_path = Path(f.name)

    doc = None
    try:
        result = await client.documents.upload(
            tmp_path,
            title=f"__integration_download_original_{uid}__",
            wait=True,
            poll_interval=2.0,
            poll_timeout=120.0,
        )
        from easypaperless import Document  # noqa: PLC0415

        assert isinstance(result, Document)
        doc = result

        original_bytes = await client.documents.download(doc.id, original=True)

        assert original_bytes[:4] == _PNG_MAGIC, (
            f"Expected PNG magic bytes {_PNG_MAGIC!r} but got {original_bytes[:5]!r}. "
            "download(original=True) appears to be returning the archived PDF instead of the "
            "original file (regression: issue #0037)."
        )
        assert not original_bytes[:5].startswith(_PDF_MAGIC), (
            "download(original=True) returned PDF bytes — original flag is not honoured."
        )
    finally:
        tmp_path.unlink(missing_ok=True)
        if doc is not None:
            await purge_document(client, doc.id)


@pytest.mark.integration
async def test_download_archive_returns_pdf(client: PaperlessClient, uid: str) -> None:
    """Companion to the #0037 regression: archive download must still return a PDF."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(_make_png(uid + "_archive"))
        tmp_path = Path(f.name)

    doc = None
    try:
        result = await client.documents.upload(
            tmp_path,
            title=f"__integration_download_archive_{uid}__",
            wait=True,
            poll_interval=2.0,
            poll_timeout=120.0,
        )
        from easypaperless import Document  # noqa: PLC0415

        assert isinstance(result, Document)
        doc = result

        archived_bytes = await client.documents.download(doc.id, original=False)

        assert archived_bytes[:5] == _PDF_MAGIC, (
            f"Expected PDF magic {_PDF_MAGIC!r} from archive download but got "
            f"{archived_bytes[:5]!r}."
        )
    finally:
        tmp_path.unlink(missing_ok=True)
        if doc is not None:
            await purge_document(client, doc.id)
