"""Integration tests: document bulk download (issue #0039).

Verifies that documents.bulk_download() POSTs to /api/documents/bulk_download/
and returns a valid ZIP archive for various content/compression combinations.

Uses the module-scoped ``temp_documents`` fixture (2 PDFs uploaded in conftest).
"""

from __future__ import annotations

import io
import zipfile

import pytest

from easypaperless import PaperlessClient

_ZIP_MAGIC = b"PK\x03\x04"


@pytest.mark.integration
async def test_bulk_download_default_returns_zip(
    module_client: PaperlessClient, temp_documents
) -> None:
    """bulk_download with defaults returns a valid ZIP archive."""
    doc_ids = [doc.id for doc in temp_documents]
    data = await module_client.documents.bulk_download(doc_ids)

    assert isinstance(data, bytes)
    assert len(data) > 0
    assert data[:4] == _ZIP_MAGIC, f"Expected ZIP magic bytes {_ZIP_MAGIC!r} but got {data[:4]!r}."
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert len(zf.namelist()) > 0


@pytest.mark.integration
async def test_bulk_download_originals_returns_zip(
    module_client: PaperlessClient, temp_documents
) -> None:
    """bulk_download with content='originals' returns a valid ZIP archive."""
    doc_ids = [doc.id for doc in temp_documents]
    data = await module_client.documents.bulk_download(doc_ids, content="originals")

    assert data[:4] == _ZIP_MAGIC
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert len(zf.namelist()) > 0


@pytest.mark.integration
async def test_bulk_download_both_returns_zip(
    module_client: PaperlessClient, temp_documents
) -> None:
    """bulk_download with content='both' returns a valid ZIP archive."""
    doc_ids = [doc.id for doc in temp_documents]
    data = await module_client.documents.bulk_download(doc_ids, content="both")

    assert data[:4] == _ZIP_MAGIC
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert len(zf.namelist()) > 0


@pytest.mark.integration
async def test_bulk_download_deflated_compression_returns_zip(
    module_client: PaperlessClient, temp_documents
) -> None:
    """bulk_download with compression='deflated' returns a valid ZIP archive."""
    doc_ids = [doc.id for doc in temp_documents]
    data = await module_client.documents.bulk_download(doc_ids, compression="deflated")

    assert data[:4] == _ZIP_MAGIC
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert len(zf.namelist()) > 0


@pytest.mark.integration
async def test_bulk_download_single_document(
    module_client: PaperlessClient, temp_documents
) -> None:
    """bulk_download works with a single document ID."""
    doc_id = temp_documents[0].id
    data = await module_client.documents.bulk_download([doc_id])

    assert data[:4] == _ZIP_MAGIC
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert len(zf.namelist()) >= 1
