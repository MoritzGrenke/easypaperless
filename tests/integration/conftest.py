"""Fixtures for integration tests against a live paperless-ngx instance."""

from __future__ import annotations

import io
import os
import random
import string
import tempfile
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from easypaperless import PaperlessClient, SyncPaperlessClient
from tests.integration._cleanup import purge_document

load_dotenv(dotenv_path=Path(__file__).parent / ".env")


def _make_pdf(text: str) -> io.BytesIO:
    """Build a minimal valid PDF containing the given text, no external libs needed."""
    # PDF content stream
    safe_text = text.replace("(", r"\(").replace(")", r"\)").replace("\\", r"\\")
    stream = f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET"
    stream_bytes = stream.encode()

    # Build objects
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    obj4 = (
        b"4 0 obj\n<< /Length " + str(len(stream_bytes)).encode() + b" >>\n"
        b"stream\n" + stream_bytes + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    header = b"%PDF-1.4\n"
    body = obj1 + obj2 + obj3 + obj4 + obj5

    # xref
    offsets = []
    pos = len(header)
    for obj in (obj1, obj2, obj3, obj4, obj5):
        offsets.append(pos)
        pos += len(obj)

    xref_offset = len(header) + len(body)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for o in offsets:
        xref += f"{o:010d} 00000 n \n".encode()

    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF\n"
    )

    buf = io.BytesIO(header + body + xref + trailer)
    buf.name = "document.pdf"
    return buf


def _random_text(length: int = 60) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits + " ", k=length))


def _require_env() -> tuple[str, str]:
    url = os.getenv("PAPERLESS_URL")
    key = os.getenv("PAPERLESS_API_KEY")
    if not url or not key:
        pytest.skip("Integration env vars not set (PAPERLESS_URL, PAPERLESS_API_KEY)")
    return url, key


@pytest_asyncio.fixture
async def client() -> object:
    url, key = _require_env()
    async with PaperlessClient(url=url, api_token=key) as c:
        yield c


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def temp_documents():
    """Two uploaded PDFs shared by a test module; purged (incl. trash) afterwards.

    The fixture runs in the module's event loop and keeps its own client to
    itself.  Tests must use the function-scoped ``client`` fixture: an
    ``httpx.AsyncClient`` created in one event loop cannot be used from
    another (its pooled connections fail with "Event loop is closed").
    """
    url, key = _require_env()
    created_docs = []
    tmp_files = []
    async with PaperlessClient(url=url, api_token=key) as setup_client:
        try:
            for i in range(2):
                pdf_bytes = _make_pdf(_random_text()).getvalue()
                tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp.write(pdf_bytes)
                tmp.close()
                tmp_files.append(tmp.name)

                doc = await setup_client.documents.upload(
                    file=Path(tmp.name),
                    title=f"__integration_test_{i}__",
                    wait=True,
                    poll_timeout=120.0,
                )
                created_docs.append(doc)

            yield created_docs
        finally:
            for doc in created_docs:
                await purge_document(setup_client, doc.id)
            for path in tmp_files:
                Path(path).unlink(missing_ok=True)


@pytest.fixture
def uid() -> str:
    """Short unique ID to avoid name collisions between test runs."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def sync_client() -> object:
    url, key = _require_env()
    with SyncPaperlessClient(url=url, api_token=key) as c:
        yield c
