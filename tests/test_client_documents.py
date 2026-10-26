"""Tests for PaperlessClient document methods."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from httpx import Response

from easypaperless.exceptions import NotFoundError, ServerError
from easypaperless.models.documents import Document, DocumentMetadata
from easypaperless.models.permissions import PermissionSet, SetPermissions

DOC_DATA = {"id": 1, "title": "Test Document", "tags": []}
DOC_LIST = {
    "count": 1,
    "next": None,
    "previous": None,
    "results": [DOC_DATA],
}

META_DATA = {
    "original_checksum": "abc123",
    "original_size": 204800,
    "original_mime_type": "application/pdf",
    "media_filename": "documents/archive/2024/invoice.pdf",
    "has_archive_version": True,
    "original_metadata": [
        {"namespace": None, "prefix": None, "key": "Producer", "value": "FancyPDF"},
    ],
    "archive_checksum": "def456",
    "archive_size": 102400,
    "archive_metadata": [],
}


async def test_get_document(client, mock_router):
    mock_router.get("/documents/1/").mock(return_value=Response(200, json=DOC_DATA))
    doc = await client.documents.get(1)
    assert isinstance(doc, Document)
    assert doc.id == 1
    assert doc.title == "Test Document"
    assert doc.metadata is None


async def test_get_document_without_metadata_does_not_call_metadata_endpoint(client, mock_router):
    mock_router.get("/documents/1/").mock(return_value=Response(200, json=DOC_DATA))
    # metadata endpoint is NOT registered — would raise if called
    doc = await client.documents.get(1)
    assert doc.metadata is None


async def test_get_document_with_metadata(client, mock_router):
    mock_router.get("/documents/1/").mock(return_value=Response(200, json=DOC_DATA))
    mock_router.get("/documents/1/metadata/").mock(return_value=Response(200, json=META_DATA))
    doc = await client.documents.get(1, include_metadata=True)
    assert isinstance(doc, Document)
    assert doc.metadata is not None
    assert isinstance(doc.metadata, DocumentMetadata)
    assert doc.metadata.original_checksum == "abc123"
    assert doc.metadata.original_size == 204800
    assert doc.metadata.original_mime_type == "application/pdf"
    assert doc.metadata.has_archive_version is True
    assert doc.metadata.archive_checksum == "def456"
    assert len(doc.metadata.original_metadata) == 1
    assert doc.metadata.original_metadata[0].key == "Producer"
    assert doc.metadata.original_metadata[0].value == "FancyPDF"


async def test_get_document_metadata_standalone(client, mock_router):
    mock_router.get("/documents/1/metadata/").mock(return_value=Response(200, json=META_DATA))
    meta = await client.documents.get_metadata(1)
    assert isinstance(meta, DocumentMetadata)
    assert meta.original_checksum == "abc123"
    assert meta.archive_checksum == "def456"
    assert meta.archive_size == 102400
    assert meta.media_filename == "documents/archive/2024/invoice.pdf"


async def test_get_document_metadata_no_archive_version(client, mock_router):
    no_archive = {
        **META_DATA,
        "has_archive_version": False,
        "archive_checksum": None,
        "archive_size": None,
        "archive_metadata": None,
    }
    mock_router.get("/documents/1/metadata/").mock(return_value=Response(200, json=no_archive))
    meta = await client.documents.get_metadata(1)
    assert meta.has_archive_version is False
    assert meta.archive_checksum is None
    assert meta.archive_size is None
    assert meta.archive_metadata is None


async def test_get_document_not_found(client, mock_router):
    mock_router.get("/documents/999/").mock(
        return_value=Response(404, json={"detail": "Not found."})
    )
    with pytest.raises(NotFoundError):
        await client.documents.get(999)


async def test_get_document_metadata_not_found(client, mock_router):
    mock_router.get("/documents/999/metadata/").mock(
        return_value=Response(404, json={"detail": "Not found."})
    )
    with pytest.raises(NotFoundError):
        await client.documents.get_metadata(999)


async def test_list_documents(client, mock_router):
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))
    result = await client.documents.list()
    assert result.count == 1
    assert len(result.results) == 1
    assert result.results[0].id == 1


async def test_list_documents_with_search(client, mock_router):
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))
    result = await client.documents.list(search="invoice", search_mode="title")
    assert len(result.results) == 1


async def test_list_documents_with_title_or_content_search(client, mock_router):
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))
    result = await client.documents.list(search="invoice")  # default mode
    assert len(result.results) == 1


async def test_list_documents_with_asn(client, mock_router):
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))
    result = await client.documents.list(archive_serial_number=42)
    assert len(result.results) == 1


async def test_list_documents_with_date_range(client, mock_router):
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))
    result = await client.documents.list(created_after="2024-01-01", created_before="2024-12-31")
    assert len(result.results) == 1


async def test_update_document(client, mock_router):
    mock_router.patch("/documents/1/").mock(
        return_value=Response(200, json={**DOC_DATA, "title": "Updated"})
    )
    doc = await client.documents.update(1, title="Updated")
    assert doc.title == "Updated"


async def test_delete_document(client, mock_router):
    mock_router.delete("/documents/1/").mock(return_value=Response(204))
    await client.documents.delete(1)


async def test_delete_document_not_found(client, mock_router):
    """delete_document raises NotFoundError when the document ID does not exist."""
    mock_router.delete("/documents/999/").mock(
        return_value=Response(404, json={"detail": "Not found."})
    )
    with pytest.raises(NotFoundError):
        await client.documents.delete(999)


async def test_download_document_archive(client, mock_router):
    mock_router.get("/documents/1/download/").mock(return_value=Response(200, content=b"PDF"))
    content = await client.documents.download(1)
    assert content == b"PDF"


async def test_download_document_original(client, mock_router):
    mock_router.get("/documents/1/download/", params={"original": "true"}).mock(
        return_value=Response(200, content=b"ORIG")
    )
    content = await client.documents.download(1, original=True)
    assert content == b"ORIG"


async def test_download_document_not_found(client, mock_router):
    mock_router.get("/documents/999/download/").mock(
        return_value=Response(404, json={"detail": "Not found."})
    )
    with pytest.raises(NotFoundError):
        await client.documents.download(999)


async def test_download_document_html_content_type(client, mock_router):
    """HTML content-type indicates a login-page redirect — should raise ServerError."""
    mock_router.get("/documents/1/download/").mock(
        return_value=Response(
            200,
            content=b"<html><body>Login</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    with pytest.raises(ServerError, match="HTML page"):
        await client.documents.download(1)


async def test_download_document_html_body_prefix(client, mock_router):
    """Body starting with <!doctype should raise ServerError even without HTML content-type."""
    mock_router.get("/documents/1/download/").mock(
        return_value=Response(
            200,
            content=b"<!DOCTYPE html><html><body>Login</body></html>",
            headers={"content-type": "application/octet-stream"},
        )
    )
    with pytest.raises(ServerError, match="HTML page"):
        await client.documents.download(1)


async def test_thumbnail_document(client, mock_router):
    mock_router.get("/documents/1/thumb/").mock(
        return_value=Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})
    )
    content = await client.documents.thumbnail(1)
    assert content == b"\x89PNG"


async def test_thumbnail_document_not_found(client, mock_router):
    mock_router.get("/documents/999/thumb/").mock(
        return_value=Response(404, json={"detail": "Not found."})
    )
    with pytest.raises(NotFoundError):
        await client.documents.thumbnail(999)


async def test_thumbnail_document_html_content_type(client, mock_router):
    """HTML content-type on thumb endpoint indicates auth redirect — should raise ServerError."""
    mock_router.get("/documents/1/thumb/").mock(
        return_value=Response(
            200,
            content=b"<html><body>Login</body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
    )
    with pytest.raises(ServerError, match="HTML page"):
        await client.documents.thumbnail(1)


async def test_thumbnail_document_html_body_prefix(client, mock_router):
    """Body starting with <!doctype should raise ServerError even without HTML content-type."""
    mock_router.get("/documents/1/thumb/").mock(
        return_value=Response(
            200,
            content=b"<!DOCTYPE html><html><body>Login</body></html>",
            headers={"content-type": "application/octet-stream"},
        )
    )
    with pytest.raises(ServerError, match="HTML page"):
        await client.documents.thumbnail(1)


async def test_thumbnail_document_webp(client, mock_router):
    """Thumbnail is returned as raw bytes regardless of MIME type (e.g. image/webp)."""
    webp_magic = b"RIFF\x00\x00\x00\x00WEBP"
    mock_router.get("/documents/1/thumb/").mock(
        return_value=Response(200, content=webp_magic, headers={"content-type": "image/webp"})
    )
    content = await client.documents.thumbnail(1)
    assert content == webp_magic


async def test_thumbnail_document_html_body_prefix_lowercase(client, mock_router):
    """Lowercase <!doctype prefix must also trigger ServerError (case-insensitive detection)."""
    mock_router.get("/documents/1/thumb/").mock(
        return_value=Response(
            200,
            content=b"<!doctype html><html><body>Login</body></html>",
            headers={"content-type": "application/octet-stream"},
        )
    )
    with pytest.raises(ServerError, match="HTML page"):
        await client.documents.thumbnail(1)


async def test_list_documents_with_tag_id(client, mock_router):
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))
    result = await client.documents.list(tags=[3])
    assert len(result.results) == 1


async def test_list_documents_with_tag_name(client, mock_router):
    # Resolver will fetch tags list first
    tags_resp = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 3, "name": "invoice"}],
    }
    mock_router.get("/tags/").mock(return_value=Response(200, json=tags_resp))
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))
    result = await client.documents.list(tags=["invoice"])
    assert len(result.results) == 1


async def test_update_document_with_correspondent_name(client, mock_router):
    corr_resp = {"count": 1, "next": None, "previous": None, "results": [{"id": 5, "name": "ACME"}]}
    mock_router.get("/correspondents/").mock(return_value=Response(200, json=corr_resp))
    mock_router.patch("/documents/1/").mock(
        return_value=Response(200, json={**DOC_DATA, "correspondent": 5})
    )
    doc = await client.documents.update(1, correspondent="ACME")
    assert doc.correspondent == 5


def _patch_capturing_side_effect(captured: dict, response_data: dict = DOC_DATA):
    """Return a respx side-effect that stores the request JSON body."""

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(200, json=response_data)

    return _side_effect


async def test_update_document_with_owner(client, mock_router):
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, {**DOC_DATA, "owner": 42})
    )
    doc = await client.documents.update(1, owner=42)
    assert doc.owner == 42
    assert captured["body"]["owner"] == 42


async def test_update_document_with_set_permissions(client, mock_router):
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    perms = SetPermissions(
        view=PermissionSet(users=[1, 2], groups=[]),
        change=PermissionSet(users=[1], groups=[3]),
    )
    await client.documents.update(1, set_permissions=perms)
    body = captured["body"]
    assert body["set_permissions"] == {
        "view": {"users": [1, 2], "groups": []},
        "change": {"users": [1], "groups": [3]},
    }


async def test_update_document_owner_and_permissions_not_sent_when_omitted(client, mock_router):
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, {**DOC_DATA, "title": "New"})
    )
    await client.documents.update(1, title="New")
    body = captured["body"]
    assert "owner" not in body
    assert "set_permissions" not in body
    assert body == {"title": "New"}


async def test_update_document_created_sent_as_created(client, mock_router):
    """created parameter is sent as 'created' in the PATCH payload."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, created="2024-06-15")
    assert captured["body"]["created"] == "2024-06-15"


async def test_update_document_created_accepts_date_object(client, mock_router):
    """created parameter accepts a date object and formats it as ISO-8601."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, created=date(2024, 6, 15))
    assert captured["body"]["created"] == "2024-06-15"


async def test_update_document_archive_serial_number_sent_correctly(client, mock_router):
    """archive_serial_number parameter is sent as 'archive_serial_number' in the PATCH payload."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, archive_serial_number=42)
    assert captured["body"]["archive_serial_number"] == 42


async def test_update_document_tags_with_name_resolution(client, mock_router):
    """tags with string names are resolved to IDs via resolve_list."""
    tags_resp = {
        "count": 2,
        "next": None,
        "previous": None,
        "results": [{"id": 3, "name": "invoice"}, {"id": 7, "name": "urgent"}],
    }
    mock_router.get("/tags/").mock(return_value=Response(200, json=tags_resp))
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, {**DOC_DATA, "tags": [3, 7]})
    )
    await client.documents.update(1, tags=["invoice", "urgent"])
    assert captured["body"]["tags"] == [3, 7]


async def test_update_document_document_type_with_name_resolution(client, mock_router):
    """document_type with a string name is resolved to an ID."""
    dt_resp = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 10, "name": "Invoice"}],
    }
    mock_router.get("/document_types/").mock(return_value=Response(200, json=dt_resp))
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, {**DOC_DATA, "document_type": 10})
    )
    await client.documents.update(1, document_type="Invoice")
    assert captured["body"]["document_type"] == 10


async def test_update_document_storage_path_with_name_resolution(client, mock_router):
    """storage_path with a string name is resolved to an ID."""
    sp_resp = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 20, "name": "Archive"}],
    }
    mock_router.get("/storage_paths/").mock(return_value=Response(200, json=sp_resp))
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, {**DOC_DATA, "storage_path": 20})
    )
    await client.documents.update(1, storage_path="Archive")
    assert captured["body"]["storage_path"] == 20


async def test_update_document_custom_fields_sent_in_payload(client, mock_router):
    """custom_fields list is sent as-is in the PATCH payload."""
    captured: dict = {}
    cf = [{"field": 1, "value": "hello"}, {"field": 2, "value": 99}]
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, custom_fields=cf)
    assert captured["body"]["custom_fields"] == cf


async def test_update_document_correspondent_zero_clears(client, mock_router):
    """Passing correspondent=0 sends 0 in the payload (not skipped as falsy)."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, {**DOC_DATA, "correspondent": None})
    )
    await client.documents.update(1, correspondent=0)
    assert captured["body"]["correspondent"] == 0


async def test_update_document_empty_kwargs_sends_empty_body(client, mock_router):
    """Calling update_document with no kwargs sends an empty PATCH payload."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1)
    assert captured["body"] == {}


async def test_update_document_not_found(client, mock_router):
    """update_document raises NotFoundError when the document ID does not exist."""
    mock_router.patch("/documents/999/").mock(
        return_value=Response(404, json={"detail": "Not found."})
    )
    with pytest.raises(NotFoundError):
        await client.documents.update(999, title="Does not matter")


async def test_update_document_nonexistent_tag_name_raises_resolver_error(client, mock_router):
    """Passing a tag name that does not exist raises NotFoundError before HTTP."""
    tags_resp = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 3, "name": "invoice"}],
    }
    mock_router.get("/tags/").mock(return_value=Response(200, json=tags_resp))
    # No PATCH mock — the request should never be made
    with pytest.raises(NotFoundError):
        await client.documents.update(1, tags=["nonexistent"])


# ---------------------------------------------------------------------------
# Shared mock data for new-parameter tests
# ---------------------------------------------------------------------------

_CORR_RESP = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [{"id": 5, "name": "ACME"}, {"id": 6, "name": "Bank"}],
}
_DOCTYPE_RESP = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [{"id": 10, "name": "Invoice"}, {"id": 11, "name": "Receipt"}],
}


def _capturing_side_effect(captured: dict, response_data: dict = DOC_LIST):
    """Return a respx side-effect that stores the request URL params."""

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=response_data)

    return _side_effect


# ---------------------------------------------------------------------------
# any_correspondent
# ---------------------------------------------------------------------------


async def test_list_documents_any_correspondent_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_correspondent=[5, 6])
    assert captured["params"]["correspondent__id__in"] == "5,6"


async def test_list_documents_any_correspondent_by_name(client, mock_router):
    mock_router.get("/correspondents/").mock(return_value=Response(200, json=_CORR_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_correspondent=["ACME", "Bank"])
    assert captured["params"]["correspondent__id__in"] == "5,6"


async def test_list_documents_any_correspondent_overrides_correspondent(client, mock_router):
    """When both are given, any_correspondent takes precedence."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(correspondent=99, any_correspondent=[5, 6])
    assert captured["params"]["correspondent__id__in"] == "5,6"


# ---------------------------------------------------------------------------
# correspondent (single-value)
# ---------------------------------------------------------------------------


async def test_list_documents_correspondent_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(correspondent=5)
    assert captured["params"]["correspondent__id"] == "5"
    assert "correspondent__id__in" not in captured["params"]


async def test_list_documents_correspondent_by_name(client, mock_router):
    mock_router.get("/correspondents/").mock(return_value=Response(200, json=_CORR_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(correspondent="ACME")
    assert captured["params"]["correspondent__id"] == "5"
    assert "correspondent__id__in" not in captured["params"]


# ---------------------------------------------------------------------------
# exclude_correspondents
# ---------------------------------------------------------------------------


async def test_list_documents_exclude_correspondents_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_correspondents=[5, 6])
    assert captured["params"]["correspondent__id__none"] == "5,6"


async def test_list_documents_exclude_correspondents_by_name(client, mock_router):
    mock_router.get("/correspondents/").mock(return_value=Response(200, json=_CORR_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_correspondents=["ACME"])
    assert captured["params"]["correspondent__id__none"] == "5"


# ---------------------------------------------------------------------------
# any_document_type
# ---------------------------------------------------------------------------


async def test_list_documents_any_document_type_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_document_type=[10, 11])
    assert captured["params"]["document_type__id__in"] == "10,11"


async def test_list_documents_any_document_type_by_name(client, mock_router):
    mock_router.get("/document_types/").mock(return_value=Response(200, json=_DOCTYPE_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_document_type=["Invoice", "Receipt"])
    assert captured["params"]["document_type__id__in"] == "10,11"


async def test_list_documents_any_document_type_overrides_document_type(client, mock_router):
    """When both are given, any_document_type takes precedence."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(document_type=99, any_document_type=[10, 11])
    assert captured["params"]["document_type__id__in"] == "10,11"
    assert "document_type__id" not in captured["params"]


# ---------------------------------------------------------------------------
# document_type (single-value)
# ---------------------------------------------------------------------------


async def test_list_documents_document_type_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(document_type=10)
    assert captured["params"]["document_type__id"] == "10"
    assert "document_type" not in captured["params"]
    assert "document_type__id__in" not in captured["params"]


async def test_list_documents_document_type_by_name(client, mock_router):
    mock_router.get("/document_types/").mock(return_value=Response(200, json=_DOCTYPE_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(document_type="Invoice")
    assert captured["params"]["document_type__id"] == "10"
    assert "document_type" not in captured["params"]
    assert "document_type__id__in" not in captured["params"]


# ---------------------------------------------------------------------------
# exclude_document_types
# ---------------------------------------------------------------------------


async def test_list_documents_exclude_document_types_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_document_types=[10, 11])
    assert captured["params"]["document_type__id__none"] == "10,11"


async def test_list_documents_exclude_document_types_by_name(client, mock_router):
    mock_router.get("/document_types/").mock(return_value=Response(200, json=_DOCTYPE_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_document_types=["Invoice"])
    assert captured["params"]["document_type__id__none"] == "10"


# ---------------------------------------------------------------------------
# added_after / added_before
# ---------------------------------------------------------------------------


async def test_list_documents_added_date_range(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_after="2024-01-01", added_before="2024-12-31")
    assert captured["params"]["added__date__gt"] == "2024-01-01"
    assert captured["params"]["added__date__lt"] == "2024-12-31"


async def test_list_documents_added_after_only(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_after="2024-06-01")
    assert captured["params"]["added__date__gt"] == "2024-06-01"
    assert "added__date__lt" not in captured["params"]


# ---------------------------------------------------------------------------
# modified_after / modified_before
# ---------------------------------------------------------------------------


async def test_list_documents_modified_date_range(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_after="2024-03-01", modified_before="2024-09-30")
    assert captured["params"]["modified__date__gt"] == "2024-03-01"
    assert captured["params"]["modified__date__lt"] == "2024-09-30"


# ---------------------------------------------------------------------------
# page_size
# ---------------------------------------------------------------------------


async def test_list_documents_default_page_size(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list()
    assert captured["params"]["page_size"] == "25"


async def test_list_documents_custom_page_size(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(page_size=100)
    assert captured["params"]["page_size"] == "100"


# ---------------------------------------------------------------------------
# max_results
# ---------------------------------------------------------------------------


async def test_list_documents_max_results_within_first_page(client, mock_router):
    """max_results smaller than the page — returns only that many docs."""
    many = {
        "count": 5,
        "next": None,
        "previous": None,
        "results": [{"id": i, "title": f"Doc{i}", "tags": []} for i in range(1, 6)],
    }
    mock_router.get("/documents/").mock(return_value=Response(200, json=many))
    result = await client.documents.list(max_results=3)
    assert result.count == 5
    assert len(result.results) == 3
    assert [d.id for d in result.results] == [1, 2, 3]


async def test_list_documents_max_results_stops_pagination(client, mock_router):
    """max_results spanning two pages — fetches second page then stops."""
    page1 = {
        "count": 4,
        "next": "http://paperless.test/api/documents/?page=2",
        "previous": None,
        "results": [{"id": 1, "title": "A", "tags": []}, {"id": 2, "title": "B", "tags": []}],
    }
    page2 = {
        "count": 4,
        "next": None,
        "previous": None,
        "results": [{"id": 3, "title": "C", "tags": []}, {"id": 4, "title": "D", "tags": []}],
    }
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        return Response(200, json=page1 if call_count == 1 else page2)

    mock_router.get("/documents/").mock(side_effect=side_effect)
    result = await client.documents.list(max_results=3)
    assert result.count == 4
    assert len(result.results) == 3
    assert [d.id for d in result.results] == [1, 2, 3]
    assert call_count == 2


async def test_list_documents_max_results_exact_first_page(client, mock_router):
    """max_results == first page count — second page must NOT be fetched."""
    page1 = {
        "count": 4,
        "next": "http://paperless.test/api/documents/?page=2",
        "previous": None,
        "results": [{"id": 1, "title": "A", "tags": []}, {"id": 2, "title": "B", "tags": []}],
    }
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        return Response(200, json=page1)

    mock_router.get("/documents/").mock(side_effect=side_effect)
    result = await client.documents.list(max_results=2)
    assert len(result.results) == 2
    assert call_count == 1


# ---------------------------------------------------------------------------
# checksum / page / ordering / search_mode=original_filename
# ---------------------------------------------------------------------------


async def test_list_documents_checksum(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(checksum="abc123")
    assert captured["params"]["checksum__iexact"] == "abc123"


async def test_list_documents_ordering_asc(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(ordering="created")
    assert captured["params"]["ordering"] == "created"


async def test_list_documents_ordering_desc(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(ordering="created", descending=True)
    assert captured["params"]["ordering"] == "-created"


async def test_list_documents_page(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured, DOC_LIST))
    result = await client.documents.list(page=2)
    assert captured["params"]["page"] == "2"
    assert len(result.results) == 1


async def test_list_documents_page_suppresses_autopagination(client, mock_router):
    """With page= set, only one request should be made regardless of next."""
    page_resp = {
        "count": 100,
        "next": "http://paperless.test/api/documents/?page=3",
        "previous": None,
        "results": [{"id": 1, "title": "A", "tags": []}],
    }
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        return Response(200, json=page_resp)

    mock_router.get("/documents/").mock(side_effect=side_effect)
    result = await client.documents.list(page=2)
    assert call_count == 1
    assert len(result.results) == 1


async def test_list_documents_search_mode_original_filename(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(search="invoice.pdf", search_mode="original_filename")
    assert captured["params"]["original_filename__icontains"] == "invoice.pdf"


# ---------------------------------------------------------------------------
# ids filter
# ---------------------------------------------------------------------------


async def test_list_documents_ids(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(ids=[1, 5, 10])
    assert captured["params"]["id__in"] == "1,5,10"


# ---------------------------------------------------------------------------
# storage_path filters
# ---------------------------------------------------------------------------

_SPATH_RESP = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [{"id": 20, "name": "Archive"}, {"id": 21, "name": "Inbox"}],
}


async def test_list_documents_storage_path_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(storage_path=20)
    assert captured["params"]["storage_path__id"] == "20"
    assert "storage_path__id__in" not in captured["params"]


async def test_list_documents_storage_path_by_name(client, mock_router):
    mock_router.get("/storage_paths/").mock(return_value=Response(200, json=_SPATH_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(storage_path="Archive")
    assert captured["params"]["storage_path__id"] == "20"
    assert "storage_path__id__in" not in captured["params"]


async def test_list_documents_any_storage_paths_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_storage_paths=[20, 21])
    assert captured["params"]["storage_path__id__in"] == "20,21"


async def test_list_documents_any_storage_paths_by_name(client, mock_router):
    mock_router.get("/storage_paths/").mock(return_value=Response(200, json=_SPATH_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_storage_paths=["Archive", "Inbox"])
    assert captured["params"]["storage_path__id__in"] == "20,21"


async def test_list_documents_any_storage_paths_overrides_storage_path(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(storage_path=99, any_storage_paths=[20, 21])
    assert captured["params"]["storage_path__id__in"] == "20,21"


async def test_list_documents_exclude_storage_paths_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_storage_paths=[20])
    assert captured["params"]["storage_path__id__none"] == "20"


async def test_list_documents_exclude_storage_paths_by_name(client, mock_router):
    mock_router.get("/storage_paths/").mock(return_value=Response(200, json=_SPATH_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_storage_paths=["Archive"])
    assert captured["params"]["storage_path__id__none"] == "20"


# ---------------------------------------------------------------------------
# owner filters
# ---------------------------------------------------------------------------


async def test_list_documents_owner(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(owner=42)
    assert captured["params"]["owner__id"] == "42"
    assert "owner__id__in" not in captured["params"]


async def test_list_documents_exclude_owners(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_owners=[1, 2])
    assert captured["params"]["owner__id__none"] == "1,2"


# ---------------------------------------------------------------------------
# custom_fields filters
# ---------------------------------------------------------------------------

_CF_RESP = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [{"id": 30, "name": "Amount"}, {"id": 31, "name": "Status"}],
}


async def test_list_documents_custom_fields_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(custom_fields=[30, 31])
    assert captured["params"]["custom_fields__id__all"] == "30,31"


async def test_list_documents_custom_fields_by_name(client, mock_router):
    mock_router.get("/custom_fields/").mock(return_value=Response(200, json=_CF_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(custom_fields=["Amount", "Status"])
    assert captured["params"]["custom_fields__id__all"] == "30,31"


async def test_list_documents_any_custom_fields_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_custom_fields=[30])
    assert captured["params"]["custom_fields__id__in"] == "30"


async def test_list_documents_any_custom_fields_by_name(client, mock_router):
    mock_router.get("/custom_fields/").mock(return_value=Response(200, json=_CF_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(any_custom_fields=["Amount"])
    assert captured["params"]["custom_fields__id__in"] == "30"


async def test_list_documents_exclude_custom_fields_by_id(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_custom_fields=[30, 31])
    assert captured["params"]["custom_fields__id__none"] == "30,31"


async def test_list_documents_exclude_custom_fields_by_name(client, mock_router):
    mock_router.get("/custom_fields/").mock(return_value=Response(200, json=_CF_RESP))
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(exclude_custom_fields=["Amount"])
    assert captured["params"]["custom_fields__id__none"] == "30"


# ---------------------------------------------------------------------------
# custom_field_query
# ---------------------------------------------------------------------------


async def test_list_documents_custom_field_query_simple(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    query = ["Invoice Amount", "gt", 100]
    await client.documents.list(custom_field_query=query)
    assert captured["params"]["custom_field_query"] == json.dumps(query)


async def test_list_documents_custom_field_query_compound(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    query = ["AND", [["Amount", "gt", 100], ["Status", "exact", "paid"]]]
    await client.documents.list(custom_field_query=query)
    assert captured["params"]["custom_field_query"] == json.dumps(query)


# ---------------------------------------------------------------------------
# archive_serial_number range filters
# ---------------------------------------------------------------------------


async def test_list_documents_archive_serial_number_from(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(archive_serial_number_from=100)
    assert captured["params"]["archive_serial_number__gte"] == "100"


async def test_list_documents_archive_serial_number_till(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(archive_serial_number_till=200)
    assert captured["params"]["archive_serial_number__lte"] == "200"


async def test_list_documents_archive_serial_number_range(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(archive_serial_number_from=100, archive_serial_number_till=200)
    assert captured["params"]["archive_serial_number__gte"] == "100"
    assert captured["params"]["archive_serial_number__lte"] == "200"


# ---------------------------------------------------------------------------
# added_from / added_until
# ---------------------------------------------------------------------------


async def test_list_documents_added_from(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_from="2024-01-01")
    assert captured["params"]["added__date__gte"] == "2024-01-01"


async def test_list_documents_added_until(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_until="2024-12-31")
    assert captured["params"]["added__date__lte"] == "2024-12-31"


# ---------------------------------------------------------------------------
# modified_from / modified_until
# ---------------------------------------------------------------------------


async def test_list_documents_modified_from(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_from="2024-03-01")
    assert captured["params"]["modified__date__gte"] == "2024-03-01"


async def test_list_documents_modified_until(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_until="2024-09-30")
    assert captured["params"]["modified__date__lte"] == "2024-09-30"


# ---------------------------------------------------------------------------
# datetime vs date distinction for added/modified filters
# ---------------------------------------------------------------------------


async def test_list_documents_added_after_with_datetime(client, mock_router):
    """datetime objects should use added__gt (not added__date__gt)."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 6, 15, 10, 30, 0)
    await client.documents.list(added_after=dt)
    assert "added__gt" in captured["params"]
    assert "added__date__gt" not in captured["params"]
    assert captured["params"]["added__gt"] == dt.isoformat()


async def test_list_documents_added_after_with_date(client, mock_router):
    """date objects should use added__date__gt (not added__gt)."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    d = date(2024, 6, 15)
    await client.documents.list(added_after=d)
    assert "added__date__gt" in captured["params"]
    assert "added__gt" not in captured["params"]
    assert captured["params"]["added__date__gt"] == "2024-06-15"


async def test_list_documents_added_before_with_datetime(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 12, 31, 23, 59, 59)
    await client.documents.list(added_before=dt)
    assert "added__lt" in captured["params"]
    assert "added__date__lt" not in captured["params"]
    assert captured["params"]["added__lt"] == dt.isoformat()


async def test_list_documents_added_from_with_datetime(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 1, 1, 0, 0, 0)
    await client.documents.list(added_from=dt)
    assert "added__gte" in captured["params"]
    assert "added__date__gte" not in captured["params"]


async def test_list_documents_added_until_with_datetime(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 12, 31, 23, 59, 59)
    await client.documents.list(added_until=dt)
    assert "added__lte" in captured["params"]
    assert "added__date__lte" not in captured["params"]


async def test_list_documents_modified_after_with_datetime(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 3, 1, 12, 0, 0)
    await client.documents.list(modified_after=dt)
    assert "modified__gt" in captured["params"]
    assert "modified__date__gt" not in captured["params"]
    assert captured["params"]["modified__gt"] == dt.isoformat()


async def test_list_documents_modified_after_with_date(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    d = date(2024, 3, 1)
    await client.documents.list(modified_after=d)
    assert "modified__date__gt" in captured["params"]
    assert "modified__gt" not in captured["params"]


async def test_list_documents_modified_before_with_datetime(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 9, 30, 18, 0, 0)
    await client.documents.list(modified_before=dt)
    assert "modified__lt" in captured["params"]
    assert "modified__date__lt" not in captured["params"]


async def test_list_documents_modified_from_with_datetime(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 3, 1, 0, 0, 0)
    await client.documents.list(modified_from=dt)
    assert "modified__gte" in captured["params"]
    assert "modified__date__gte" not in captured["params"]


async def test_list_documents_modified_until_with_datetime(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    dt = datetime(2024, 9, 30, 23, 59, 59)
    await client.documents.list(modified_until=dt)
    assert "modified__lte" in captured["params"]
    assert "modified__date__lte" not in captured["params"]


# ---------------------------------------------------------------------------
# ISO datetime strings for added/modified filters
# ---------------------------------------------------------------------------


async def test_list_documents_added_after_with_iso_datetime_string(client, mock_router):
    """ISO datetime string should use added__gt (not added__date__gt)."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_after="2026-02-22T16:25:00+00:00")
    assert "added__gt" in captured["params"]
    assert "added__date__gt" not in captured["params"]
    assert captured["params"]["added__gt"] == "2026-02-22T16:25:00+00:00"


async def test_list_documents_added_after_with_iso_date_string(client, mock_router):
    """Plain ISO date string should use added__date__gt (not added__gt)."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_after="2026-02-22")
    assert "added__date__gt" in captured["params"]
    assert "added__gt" not in captured["params"]
    assert captured["params"]["added__date__gt"] == "2026-02-22"


async def test_list_documents_added_before_with_iso_datetime_string(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_before="2026-02-22T23:59:59Z")
    assert "added__lt" in captured["params"]
    assert "added__date__lt" not in captured["params"]


async def test_list_documents_added_from_with_iso_datetime_string(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_from="2026-01-01T00:00:00+00:00")
    assert "added__gte" in captured["params"]
    assert "added__date__gte" not in captured["params"]


async def test_list_documents_added_until_with_iso_datetime_string(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(added_until="2026-12-31T23:59:59+00:00")
    assert "added__lte" in captured["params"]
    assert "added__date__lte" not in captured["params"]


async def test_list_documents_modified_after_with_iso_datetime_string(client, mock_router):
    """ISO datetime string should use modified__gt (not modified__date__gt)."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_after="2026-02-22T16:25:00+00:00")
    assert "modified__gt" in captured["params"]
    assert "modified__date__gt" not in captured["params"]
    assert captured["params"]["modified__gt"] == "2026-02-22T16:25:00+00:00"


async def test_list_documents_modified_after_with_iso_date_string(client, mock_router):
    """Plain ISO date string should use modified__date__gt (not modified__gt)."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_after="2026-02-22")
    assert "modified__date__gt" in captured["params"]
    assert "modified__gt" not in captured["params"]


async def test_list_documents_modified_before_with_iso_datetime_string(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_before="2026-02-22T16:25:00+00:00")
    assert "modified__lt" in captured["params"]
    assert "modified__date__lt" not in captured["params"]


async def test_list_documents_modified_from_with_iso_datetime_string(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_from="2026-01-01T00:00:00+00:00")
    assert "modified__gte" in captured["params"]
    assert "modified__date__gte" not in captured["params"]


async def test_list_documents_modified_until_with_iso_datetime_string(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(modified_until="2026-12-31T23:59:59+00:00")
    assert "modified__lte" in captured["params"]
    assert "modified__date__lte" not in captured["params"]


# ---------------------------------------------------------------------------
# search_mode="query"
# ---------------------------------------------------------------------------


async def test_list_documents_search_mode_query(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_side_effect(captured))
    await client.documents.list(search="tag:invoice date:[2024 TO *]", search_mode="query")
    assert captured["params"]["query"] == "tag:invoice date:[2024 TO *]"
    assert "search" not in captured["params"]
    assert "title__icontains" not in captured["params"]


# ---------------------------------------------------------------------------
# on_page callback
# ---------------------------------------------------------------------------


async def test_list_documents_on_page_callback(client, mock_router):
    """on_page callback is invoked with (fetched_so_far, total) per page."""
    page1 = {
        "count": 3,
        "next": "http://paperless.test/api/documents/?page=2",
        "previous": None,
        "results": [
            {"id": 1, "title": "A", "tags": []},
            {"id": 2, "title": "B", "tags": []},
        ],
    }
    page2 = {
        "count": 3,
        "next": None,
        "previous": None,
        "results": [{"id": 3, "title": "C", "tags": []}],
    }
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        return Response(200, json=page1 if call_count == 1 else page2)

    mock_router.get("/documents/").mock(side_effect=side_effect)

    page_calls: list[tuple[int, int | None]] = []

    def on_page(fetched: int, total: int | None) -> None:
        page_calls.append((fetched, total))

    result = await client.documents.list(on_page=on_page)
    assert len(result.results) == 3
    assert len(page_calls) == 2
    assert page_calls[0] == (2, 3)
    assert page_calls[1] == (3, 3)


async def test_list_documents_on_page_not_called_when_page_set(client, mock_router):
    """on_page is ignored when a specific page is requested."""
    mock_router.get("/documents/").mock(return_value=Response(200, json=DOC_LIST))

    page_calls: list[tuple[int, int | None]] = []

    def on_page(fetched: int, total: int | None) -> None:
        page_calls.append((fetched, total))

    await client.documents.list(page=1, on_page=on_page)
    assert len(page_calls) == 0


# ---------------------------------------------------------------------------
# UNSET / None sentinel regression tests (issue #0019)
# ---------------------------------------------------------------------------


def _list_capturing_side_effect(captured: dict, response_data: dict):
    """Store query params from a list request."""

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=response_data)

    return _side_effect


async def test_update_document_omitting_nullable_field_does_not_send_it(client, mock_router):
    """Omitting a nullable field (UNSET default) must NOT include it in the payload."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, title="Only title")
    body = captured["body"]
    assert body == {"title": "Only title"}
    assert "correspondent" not in body
    assert "document_type" not in body
    assert "storage_path" not in body
    assert "owner" not in body
    assert "archive_serial_number" not in body


async def test_update_document_none_correspondent_sends_null(client, mock_router):
    """Passing correspondent=None must send null in the payload to clear the field."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, correspondent=None)
    assert "correspondent" in captured["body"]
    assert captured["body"]["correspondent"] is None


async def test_update_document_none_document_type_sends_null(client, mock_router):
    """Passing document_type=None must send null in the payload."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, document_type=None)
    assert captured["body"]["document_type"] is None


async def test_update_document_none_storage_path_sends_null(client, mock_router):
    """Passing storage_path=None must send null in the payload."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, storage_path=None)
    assert captured["body"]["storage_path"] is None


async def test_update_document_none_owner_sends_null(client, mock_router):
    """Passing owner=None must send null in the payload to clear the owner."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, owner=None)
    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


async def test_update_document_none_archive_serial_number_sends_null(client, mock_router):
    """Passing archive_serial_number=None must send null in the payload to clear the ASN."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(
        side_effect=_patch_capturing_side_effect(captured, DOC_DATA)
    )
    await client.documents.update(1, archive_serial_number=None)
    assert "archive_serial_number" in captured["body"]
    assert captured["body"]["archive_serial_number"] is None


async def test_list_documents_none_owner_filters_no_owner(client, mock_router):
    """Passing owner=None to list must add owner__isnull=true to the query params."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_list_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(owner=None)
    assert captured["params"].get("owner__isnull") == "true"
    assert "owner__id" not in captured["params"]


async def test_list_documents_owner_id_filters_by_id(client, mock_router):
    """Passing owner=5 must add owner__id=5 (not isnull)."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_list_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(owner=5)
    assert captured["params"].get("owner__id") == "5"
    assert "owner__isnull" not in captured["params"]


async def test_list_documents_omitting_owner_applies_no_owner_filter(client, mock_router):
    """Omitting owner must not add any owner filter to the query params."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_list_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list()
    assert "owner__isnull" not in captured["params"]
    assert "owner__id" not in captured["params"]


async def test_list_documents_none_correspondent_filters_no_correspondent(client, mock_router):
    """Passing correspondent=None must add correspondent__isnull=true to params."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_list_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(correspondent=None)
    assert captured["params"].get("correspondent__isnull") == "true"


async def test_list_documents_none_document_type_filters_no_type(client, mock_router):
    """Passing document_type=None must add document_type__isnull=true to params."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_list_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(document_type=None)
    assert captured["params"].get("document_type__isnull") == "true"


async def test_list_documents_none_storage_path_filters_no_path(client, mock_router):
    """Passing storage_path=None must add storage_path__isnull=true to params."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_list_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(storage_path=None)
    assert captured["params"].get("storage_path__isnull") == "true"


async def test_list_documents_none_archive_serial_number_filters_no_asn(client, mock_router):
    """Passing archive_serial_number=None must add archive_serial_number__isnull=true."""
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_list_capturing_side_effect(captured, DOC_LIST))
    await client.documents.list(archive_serial_number=None)
    assert captured["params"].get("archive_serial_number__isnull") == "true"
