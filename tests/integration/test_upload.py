"""Integration tests: upload a document, wait for processing, then clean up."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

from easypaperless import PaperlessClient
from tests.integration._cleanup import purge_document


def _make_unique_pdf() -> bytes:
    """Return a minimal valid PDF with a unique ID embedded to avoid duplicate detection."""
    unique_id = uuid.uuid4().hex
    # Embed the ID as a PDF comment so the checksum differs on every run.
    header = f"%PDF-1.4\n%unique:{unique_id}\n".encode()
    body = (
        b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type /Pages /Kids[3 0 R] /Count 1>>endobj\n"
        b"3 0 obj<</Type /Page /MediaBox[0 0 612 792] /Parent 2 0 R /Resources<<>>>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f\r\n"
        b"0000000009 00000 n\r\n"
        b"0000000058 00000 n\r\n"
        b"0000000115 00000 n\r\n"
        b"trailer<</Size 4 /Root 1 0 R>>\n"
        b"startxref\n206\n%%EOF\n"
    )
    return header + body


@pytest.mark.integration
async def test_upload_and_cleanup(client: PaperlessClient, uid: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(_make_unique_pdf())
        tmp_path = Path(f.name)

    doc = None
    try:
        result = await client.documents.upload(
            tmp_path,
            title=f"__integration_upload_{uid}__",
            wait=True,
            poll_interval=2.0,
            poll_timeout=120.0,
        )
        # upload with wait=True returns a Document
        from easypaperless import Document  # noqa: PLC0415

        assert isinstance(result, Document)
        doc = result
        assert doc.id is not None
    finally:
        tmp_path.unlink(missing_ok=True)
        if doc is not None:
            await purge_document(client, doc.id)
