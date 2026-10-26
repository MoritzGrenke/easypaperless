"""Tests for issue #0020 — missing parameters across resource methods.

Verifies that each new parameter is accepted by the method, forwarded to
the correct API query-param or request-body field, and that UNSET values
are never leaked into the request.
"""

from __future__ import annotations

import json

import respx
from httpx import Response

from easypaperless.models.permissions import PermissionSet, SetPermissions
from easypaperless.sync import SyncPaperlessClient

BASE_URL = "http://paperless.test"
API_KEY = "test-api-key"
API_BASE = BASE_URL + "/api"

# ---------------------------------------------------------------------------
# Shared response stubs
# ---------------------------------------------------------------------------

CORR_DATA = {"id": 1, "name": "ACME"}
DOCTYPE_DATA = {"id": 1, "name": "Invoice"}
CF_DATA = {"id": 1, "name": "Amount", "data_type": "string"}
SP_DATA = {"id": 1, "name": "archive", "path": "/archive/{title}"}
TAG_DATA = {"id": 1, "name": "invoice"}
DOC_DATA = {"id": 1, "title": "Test Document", "tags": []}
DOC_LIST = {"count": 1, "next": None, "previous": None, "results": [DOC_DATA]}
CF_LIST = {"count": 1, "next": None, "previous": None, "results": [CF_DATA]}
SP_LIST = {"count": 1, "next": None, "previous": None, "results": [SP_DATA]}

PERMS = SetPermissions(
    view=PermissionSet(users=[2], groups=[]),
    change=PermissionSet(users=[], groups=[1]),
)
PERMS_DICT = {
    "view": {"users": [2], "groups": []},
    "change": {"users": [], "groups": [1]},
}
EMPTY_PERMS_DICT = {
    "view": {"users": [], "groups": []},
    "change": {"users": [], "groups": []},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capturing_params(captured: dict, response_data: dict, *, status: int = 200):
    """respx side-effect that stores query params and returns response_data."""

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(status, json=response_data)

    return _side_effect


def _capturing_body(captured: dict, response_data: dict, *, status: int = 200):
    """respx side-effect that stores the JSON body and returns response_data."""

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(status, json=response_data)

    return _side_effect


# ===========================================================================
# CorrespondentsResource.update() — set_permissions
# ===========================================================================


async def test_update_correspondent_set_permissions_sends_serialized_payload(client, mock_router):
    captured: dict = {}
    mock_router.patch("/correspondents/1/").mock(side_effect=_capturing_body(captured, CORR_DATA))
    await client.correspondents.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT


async def test_update_correspondent_set_permissions_unset_not_sent(client, mock_router):
    captured: dict = {}
    mock_router.patch("/correspondents/1/").mock(side_effect=_capturing_body(captured, CORR_DATA))
    await client.correspondents.update(1, name="ACME")
    assert "set_permissions" not in captured["body"]


async def test_update_correspondent_set_permissions_none_sends_empty_dict(client, mock_router):
    captured: dict = {}
    mock_router.patch("/correspondents/1/").mock(side_effect=_capturing_body(captured, CORR_DATA))
    await client.correspondents.update(1, set_permissions=SetPermissions())
    assert captured["body"]["set_permissions"] == EMPTY_PERMS_DICT


# ===========================================================================
# CustomFieldsResource.list() — name_contains, name_exact
# ===========================================================================


async def test_list_custom_fields_name_contains_sends_correct_param(client, mock_router):
    captured: dict = {}
    mock_router.get("/custom_fields/").mock(side_effect=_capturing_params(captured, CF_LIST))
    await client.custom_fields.list(name_contains="amount")
    assert captured["params"].get("name__icontains") == "amount"


async def test_list_custom_fields_name_exact_sends_correct_param(client, mock_router):
    captured: dict = {}
    mock_router.get("/custom_fields/").mock(side_effect=_capturing_params(captured, CF_LIST))
    await client.custom_fields.list(name_exact="Amount")
    assert captured["params"].get("name__iexact") == "Amount"


async def test_list_custom_fields_name_filters_omitted_when_not_provided(client, mock_router):
    captured: dict = {}
    mock_router.get("/custom_fields/").mock(side_effect=_capturing_params(captured, CF_LIST))
    await client.custom_fields.list()
    assert "name__icontains" not in captured["params"]
    assert "name__iexact" not in captured["params"]


# ===========================================================================
# CustomFieldsResource.update() — data_type
# ===========================================================================


async def test_update_custom_field_data_type_sends_in_body(client, mock_router):
    captured: dict = {}
    mock_router.patch("/custom_fields/1/").mock(side_effect=_capturing_body(captured, CF_DATA))
    await client.custom_fields.update(1, data_type="integer")
    assert captured["body"]["data_type"] == "integer"


async def test_update_custom_field_data_type_unset_not_sent(client, mock_router):
    captured: dict = {}
    mock_router.patch("/custom_fields/1/").mock(side_effect=_capturing_body(captured, CF_DATA))
    await client.custom_fields.update(1, name="Amount")
    assert "data_type" not in captured["body"]


# ===========================================================================
# DocumentTypesResource.update() — set_permissions
# ===========================================================================


async def test_update_document_type_set_permissions_sends_serialized_payload(client, mock_router):
    captured: dict = {}
    mock_router.patch("/document_types/1/").mock(
        side_effect=_capturing_body(captured, DOCTYPE_DATA)
    )
    await client.document_types.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT


async def test_update_document_type_set_permissions_unset_not_sent(client, mock_router):
    captured: dict = {}
    mock_router.patch("/document_types/1/").mock(
        side_effect=_capturing_body(captured, DOCTYPE_DATA)
    )
    await client.document_types.update(1, name="Invoice")
    assert "set_permissions" not in captured["body"]


async def test_update_document_type_set_permissions_none_sends_empty_dict(client, mock_router):
    captured: dict = {}
    mock_router.patch("/document_types/1/").mock(
        side_effect=_capturing_body(captured, DOCTYPE_DATA)
    )
    await client.document_types.update(1, set_permissions=SetPermissions())
    assert captured["body"]["set_permissions"] == EMPTY_PERMS_DICT


# ===========================================================================
# DocumentsResource.list() — document_type_name_contains, document_type_name_exact
# ===========================================================================


async def test_list_documents_document_type_name_contains_sends_correct_param(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_params(captured, DOC_LIST))
    await client.documents.list(document_type_name_contains="invoice")
    assert captured["params"].get("document_type__name__icontains") == "invoice"


async def test_list_documents_document_type_name_exact_sends_correct_param(client, mock_router):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_params(captured, DOC_LIST))
    await client.documents.list(document_type_name_exact="Invoice")
    assert captured["params"].get("document_type__name__iexact") == "Invoice"


async def test_list_documents_document_type_name_filters_omitted_when_not_provided(
    client, mock_router
):
    captured: dict = {}
    mock_router.get("/documents/").mock(side_effect=_capturing_params(captured, DOC_LIST))
    await client.documents.list()
    assert "document_type__name__icontains" not in captured["params"]
    assert "document_type__name__iexact" not in captured["params"]


# ===========================================================================
# DocumentsResource.update() — remove_inbox_tags
# ===========================================================================


async def test_update_document_remove_inbox_tags_true_sends_in_body(client, mock_router):
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(side_effect=_capturing_body(captured, DOC_DATA))
    await client.documents.update(1, remove_inbox_tags=True)
    assert captured["body"]["remove_inbox_tags"] is True


async def test_update_document_remove_inbox_tags_false_sends_in_body(client, mock_router):
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(side_effect=_capturing_body(captured, DOC_DATA))
    await client.documents.update(1, remove_inbox_tags=False)
    assert captured["body"]["remove_inbox_tags"] is False


async def test_update_document_remove_inbox_tags_unset_not_sent(client, mock_router):
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(side_effect=_capturing_body(captured, DOC_DATA))
    await client.documents.update(1, title="Updated")
    assert "remove_inbox_tags" not in captured["body"]


# ===========================================================================
# DocumentsResource.upload() — custom_fields
# ===========================================================================


async def test_upload_custom_fields_json_encoded_in_body(client, mock_router, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    route = mock_router.post("/documents/post_document/").mock(
        return_value=Response(200, text='"upload-task"')
    )
    custom_fields = [{"field": 1, "value": "hello"}, {"field": 2, "value": 42}]
    result = await client.documents.upload(pdf, custom_fields=custom_fields)
    assert result == "upload-task"

    body = route.calls.last.request.content.decode("utf-8", errors="replace")
    # custom_fields should be JSON-encoded in the multipart body
    assert json.dumps(custom_fields) in body


async def test_upload_custom_fields_empty_list_json_encoded(client, mock_router, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    route = mock_router.post("/documents/post_document/").mock(
        return_value=Response(200, text='"upload-task"')
    )
    result = await client.documents.upload(pdf, custom_fields=[])
    assert result == "upload-task"

    body = route.calls.last.request.content.decode("utf-8", errors="replace")
    assert "[]" in body


async def test_upload_custom_fields_none_not_sent(client, mock_router, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    route = mock_router.post("/documents/post_document/").mock(
        return_value=Response(200, text='"upload-task"')
    )
    await client.documents.upload(pdf)

    body = route.calls.last.request.content.decode("utf-8", errors="replace")
    assert "custom_fields" not in body


# ===========================================================================
# StoragePathsResource.list() — path_contains, path_exact
# ===========================================================================


async def test_list_storage_paths_path_contains_sends_correct_param(client, mock_router):
    captured: dict = {}
    mock_router.get("/storage_paths/").mock(side_effect=_capturing_params(captured, SP_LIST))
    await client.storage_paths.list(path_contains="archive")
    assert captured["params"].get("path__icontains") == "archive"


async def test_list_storage_paths_path_exact_sends_correct_param(client, mock_router):
    captured: dict = {}
    mock_router.get("/storage_paths/").mock(side_effect=_capturing_params(captured, SP_LIST))
    await client.storage_paths.list(path_exact="/archive/{title}")
    assert captured["params"].get("path__iexact") == "/archive/{title}"


async def test_list_storage_paths_path_filters_omitted_when_not_provided(client, mock_router):
    captured: dict = {}
    mock_router.get("/storage_paths/").mock(side_effect=_capturing_params(captured, SP_LIST))
    await client.storage_paths.list()
    assert "path__icontains" not in captured["params"]
    assert "path__iexact" not in captured["params"]


# ===========================================================================
# StoragePathsResource.update() — set_permissions
# ===========================================================================


async def test_update_storage_path_set_permissions_sends_serialized_payload(client, mock_router):
    captured: dict = {}
    mock_router.patch("/storage_paths/1/").mock(side_effect=_capturing_body(captured, SP_DATA))
    await client.storage_paths.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT


async def test_update_storage_path_set_permissions_unset_not_sent(client, mock_router):
    captured: dict = {}
    mock_router.patch("/storage_paths/1/").mock(side_effect=_capturing_body(captured, SP_DATA))
    await client.storage_paths.update(1, name="archive")
    assert "set_permissions" not in captured["body"]


async def test_update_storage_path_set_permissions_none_sends_empty_dict(client, mock_router):
    captured: dict = {}
    mock_router.patch("/storage_paths/1/").mock(side_effect=_capturing_body(captured, SP_DATA))
    await client.storage_paths.update(1, set_permissions=SetPermissions())
    assert captured["body"]["set_permissions"] == EMPTY_PERMS_DICT


# ===========================================================================
# TagsResource.update() — set_permissions
# ===========================================================================


async def test_update_tag_set_permissions_sends_serialized_payload(client, mock_router):
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_capturing_body(captured, TAG_DATA))
    await client.tags.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT


async def test_update_tag_set_permissions_unset_not_sent(client, mock_router):
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_capturing_body(captured, TAG_DATA))
    await client.tags.update(1, name="invoice")
    assert "set_permissions" not in captured["body"]


async def test_update_tag_set_permissions_none_sends_empty_dict(client, mock_router):
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_capturing_body(captured, TAG_DATA))
    await client.tags.update(1, set_permissions=SetPermissions())
    assert captured["body"]["set_permissions"] == EMPTY_PERMS_DICT


# ===========================================================================
# Sync counterparts — forwarding verification
# ===========================================================================


def _sync_client(router):
    return SyncPaperlessClient(url=BASE_URL, api_token=API_KEY)


def test_sync_update_correspondent_set_permissions_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/correspondents/1/").mock(side_effect=_capturing_body(captured, CORR_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.correspondents.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT


def test_sync_list_custom_fields_name_contains_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.get("/custom_fields/").mock(side_effect=_capturing_params(captured, CF_LIST))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.custom_fields.list(name_contains="amount")
    assert captured["params"].get("name__icontains") == "amount"


def test_sync_update_custom_field_data_type_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/custom_fields/1/").mock(side_effect=_capturing_body(captured, CF_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.custom_fields.update(1, data_type="integer")
    assert captured["body"]["data_type"] == "integer"


def test_sync_update_document_type_set_permissions_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/document_types/1/").mock(side_effect=_capturing_body(captured, DOCTYPE_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.document_types.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT


def test_sync_list_documents_document_type_name_contains_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.get("/documents/").mock(side_effect=_capturing_params(captured, DOC_LIST))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.documents.list(document_type_name_contains="invoice")
    assert captured["params"].get("document_type__name__icontains") == "invoice"


def test_sync_update_document_remove_inbox_tags_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/documents/1/").mock(side_effect=_capturing_body(captured, DOC_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.documents.update(1, remove_inbox_tags=True)
    assert captured["body"]["remove_inbox_tags"] is True


def test_sync_upload_custom_fields_forwarded(tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    custom_fields = [{"field": 1, "value": "x"}]

    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        route = router.post("/documents/post_document/").mock(
            return_value=Response(200, text='"upload-task"')
        )
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            result = client.documents.upload(pdf, custom_fields=custom_fields)

    assert result == "upload-task"
    body = route.calls.last.request.content.decode("utf-8", errors="replace")
    assert json.dumps(custom_fields) in body


def test_sync_list_storage_paths_path_contains_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.get("/storage_paths/").mock(side_effect=_capturing_params(captured, SP_LIST))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.storage_paths.list(path_contains="archive")
    assert captured["params"].get("path__icontains") == "archive"


def test_sync_update_storage_path_set_permissions_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/storage_paths/1/").mock(side_effect=_capturing_body(captured, SP_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.storage_paths.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT


def test_sync_update_tag_set_permissions_forwarded():
    captured: dict = {}
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/tags/1/").mock(side_effect=_capturing_body(captured, TAG_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.tags.update(1, set_permissions=PERMS)
    assert captured["body"]["set_permissions"] == PERMS_DICT
