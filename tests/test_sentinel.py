"""Tests for the UNSET sentinel (issue #0019).

Covers:
- Sentinel identity and repr
- Public export from easypaperless namespace
- UNSET vs None behaviour in resource update() methods (tags, correspondents,
  document_types, storage_paths, custom_fields): owner nullable field
- Tags parent nullable field
- create() owner sentinel behaviour
- Sync client pass-through
- Edge cases: explicit UNSET ≡ omitted; mixed UNSET/None in one call;
  any_correspondent takes priority over correspondent=None
"""

from __future__ import annotations

import json

import pytest
import respx
from httpx import Response

from easypaperless._internal.sentinel import UNSET, _Unset
from easypaperless.client import PaperlessClient
from easypaperless.sync import SyncPaperlessClient

BASE_URL = "http://paperless.test"
API_KEY = "test-api-key"
API_BASE = BASE_URL + "/api"

TAG_DATA = {"id": 1, "name": "invoice"}
CORR_DATA = {"id": 1, "name": "ACME"}
DT_DATA = {"id": 1, "name": "Invoice"}
SP_DATA = {"id": 1, "name": "archive", "path": "/archive/{title}"}
CF_DATA = {"id": 1, "name": "Amount", "data_type": "string"}
DOC_DATA = {"id": 1, "title": "Test Document", "tags": []}
DOC_LIST = {"count": 1, "next": None, "previous": None, "results": [DOC_DATA]}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_capture(captured: dict, response_data: dict, *, status: int = 200):
    """Side-effect that stores the parsed JSON body and returns response_data."""

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(status, json=response_data)

    return _side_effect


def _params_capture(captured: dict, response_data: dict):
    """Side-effect that stores query params and returns response_data."""

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=response_data)

    return _side_effect


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_router():
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
async def client(mock_router):
    async with PaperlessClient(url=BASE_URL, api_token=API_KEY) as c:
        yield c


# ===========================================================================
# 1. Sentinel identity and repr
# ===========================================================================


def test_unset_repr():
    assert repr(UNSET) == "UNSET"


def test_unset_is_singleton():
    """Importing UNSET twice yields the same object."""
    from easypaperless._internal.sentinel import UNSET as UNSET2

    assert UNSET is UNSET2


def test_unset_is_instance_of_unset_class():
    assert isinstance(UNSET, _Unset)


def test_unset_is_not_none():
    assert UNSET is not None


def test_unset_is_not_false():
    assert UNSET is not False


# ===========================================================================
# 2. Public export from easypaperless namespace
# ===========================================================================


def test_unset_importable_from_public_namespace():
    from easypaperless import UNSET as public_UNSET

    assert public_UNSET is UNSET


def test_unset_in_package_all():
    import easypaperless

    assert "UNSET" in easypaperless.__all__


# ===========================================================================
# 3. tags.update — owner nullable field
# ===========================================================================


async def test_update_tag_owner_none_sends_null(client, mock_router):
    """owner=None must include owner: null in the PATCH body."""
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_json_capture(captured, TAG_DATA))
    await client.tags.update(1, owner=None)
    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


async def test_update_tag_owner_int_sends_value(client, mock_router):
    """owner=5 must include owner: 5 in the PATCH body."""
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_json_capture(captured, TAG_DATA))
    await client.tags.update(1, owner=5)
    assert captured["body"]["owner"] == 5


async def test_update_tag_owner_omitted_not_in_body(client, mock_router):
    """Omitting owner (UNSET default) must NOT include owner in the PATCH body."""
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_json_capture(captured, TAG_DATA))
    await client.tags.update(1, name="receipt")
    assert "owner" not in captured["body"]


async def test_update_tag_unset_explicit_same_as_omitted(client, mock_router):
    """Passing owner=UNSET explicitly is identical to omitting the parameter."""
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_json_capture(captured, TAG_DATA))
    await client.tags.update(1, owner=UNSET)
    assert "owner" not in captured["body"]


# ===========================================================================
# 4. tags.update — parent nullable field
# ===========================================================================


async def test_update_tag_parent_none_sends_null(client, mock_router):
    """parent=None must send parent: null to clear the parent tag."""
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_json_capture(captured, TAG_DATA))
    await client.tags.update(1, parent=None)
    assert "parent" in captured["body"]
    assert captured["body"]["parent"] is None


async def test_update_tag_parent_omitted_not_in_body(client, mock_router):
    """Omitting parent must NOT include parent in the PATCH body."""
    captured: dict = {}
    mock_router.patch("/tags/1/").mock(side_effect=_json_capture(captured, TAG_DATA))
    await client.tags.update(1, name="receipt")
    assert "parent" not in captured["body"]


# ===========================================================================
# 5. correspondents.update — owner nullable field
# ===========================================================================


async def test_update_correspondent_owner_none_sends_null(client, mock_router):
    captured: dict = {}
    mock_router.patch("/correspondents/1/").mock(side_effect=_json_capture(captured, CORR_DATA))
    await client.correspondents.update(1, owner=None)
    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


async def test_update_correspondent_owner_int_sends_value(client, mock_router):
    captured: dict = {}
    mock_router.patch("/correspondents/1/").mock(side_effect=_json_capture(captured, CORR_DATA))
    await client.correspondents.update(1, owner=7)
    assert captured["body"]["owner"] == 7


async def test_update_correspondent_owner_omitted_not_in_body(client, mock_router):
    captured: dict = {}
    mock_router.patch("/correspondents/1/").mock(side_effect=_json_capture(captured, CORR_DATA))
    await client.correspondents.update(1, name="ACME Inc.")
    assert "owner" not in captured["body"]


# ===========================================================================
# 6. document_types.update — owner nullable field
# ===========================================================================


async def test_update_document_type_owner_none_sends_null(client, mock_router):
    captured: dict = {}
    mock_router.patch("/document_types/1/").mock(side_effect=_json_capture(captured, DT_DATA))
    await client.document_types.update(1, owner=None)
    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


async def test_update_document_type_owner_omitted_not_in_body(client, mock_router):
    captured: dict = {}
    mock_router.patch("/document_types/1/").mock(side_effect=_json_capture(captured, DT_DATA))
    await client.document_types.update(1, name="Invoice")
    assert "owner" not in captured["body"]


# ===========================================================================
# 7. storage_paths.update — owner nullable field
# ===========================================================================


async def test_update_storage_path_owner_none_sends_null(client, mock_router):
    captured: dict = {}
    mock_router.patch("/storage_paths/1/").mock(side_effect=_json_capture(captured, SP_DATA))
    await client.storage_paths.update(1, owner=None)
    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


async def test_update_storage_path_owner_omitted_not_in_body(client, mock_router):
    captured: dict = {}
    mock_router.patch("/storage_paths/1/").mock(side_effect=_json_capture(captured, SP_DATA))
    await client.storage_paths.update(1, name="new-archive")
    assert "owner" not in captured["body"]


# ===========================================================================
# 8. create() owner sentinel behaviour
# ===========================================================================


async def test_create_tag_owner_none_sends_null(client, mock_router):
    """Explicitly passing owner=None on create sends owner: null."""
    captured: dict = {}
    mock_router.post("/tags/").mock(side_effect=_json_capture(captured, TAG_DATA, status=201))
    await client.tags.create(name="test", owner=None)
    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


async def test_create_tag_owner_int_sends_value(client, mock_router):
    """Passing owner=3 on create sends owner: 3."""
    captured: dict = {}
    mock_router.post("/tags/").mock(side_effect=_json_capture(captured, TAG_DATA, status=201))
    await client.tags.create(name="test", owner=3)
    assert captured["body"]["owner"] == 3


async def test_create_tag_owner_omitted_not_in_body(client, mock_router):
    """Omitting owner (UNSET default) on create must NOT include owner in body."""
    captured: dict = {}
    mock_router.post("/tags/").mock(side_effect=_json_capture(captured, TAG_DATA, status=201))
    await client.tags.create(name="test")
    assert "owner" not in captured["body"]


async def test_create_correspondent_owner_omitted_not_in_body(client, mock_router):
    captured: dict = {}
    mock_router.post("/correspondents/").mock(
        side_effect=_json_capture(captured, CORR_DATA, status=201)
    )
    await client.correspondents.create(name="ACME")
    assert "owner" not in captured["body"]


async def test_create_document_type_owner_none_sends_null(client, mock_router):
    captured: dict = {}
    mock_router.post("/document_types/").mock(
        side_effect=_json_capture(captured, DT_DATA, status=201)
    )
    await client.document_types.create(name="Invoice", owner=None)
    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


# ===========================================================================
# 9. Sync client pass-through
# ===========================================================================


def test_sync_update_document_owner_none_sends_null():
    """Sync wrapper correctly passes owner=None through to the async update."""
    captured: dict = {}

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(200, json=DOC_DATA)

    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/documents/1/").mock(side_effect=_side_effect)
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.documents.update(1, owner=None)

    assert "owner" in captured["body"]
    assert captured["body"]["owner"] is None


def test_sync_update_document_owner_omitted_not_in_body():
    """Sync wrapper: omitting owner must not include it in the PATCH body."""
    captured: dict = {}

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(200, json=DOC_DATA)

    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/documents/1/").mock(side_effect=_side_effect)
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.documents.update(1, title="New Title")

    assert "owner" not in captured["body"]


def test_sync_list_documents_owner_none_applies_isnull_filter():
    """Sync wrapper: owner=None adds owner__isnull=true to query params."""
    captured: dict = {}

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=DOC_LIST)

    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.get("/documents/").mock(side_effect=_side_effect)
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.documents.list(owner=None)

    assert captured["params"].get("owner__isnull") == "true"
    assert "owner__id__in" not in captured["params"]


def test_sync_list_documents_owner_omitted_no_filter():
    """Sync wrapper: omitting owner applies no owner filter."""
    captured: dict = {}

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=DOC_LIST)

    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.get("/documents/").mock(side_effect=_side_effect)
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            client.documents.list()

    assert "owner__isnull" not in captured["params"]
    assert "owner__id__in" not in captured["params"]


# ===========================================================================
# 10. Edge cases
# ===========================================================================


async def test_update_document_mixed_unset_and_none(client, mock_router):
    """Mixing UNSET (omitted) and None (explicit null) in one call works correctly."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(side_effect=_json_capture(captured, DOC_DATA))
    # title provided, correspondent cleared, owner omitted
    await client.documents.update(1, title="My Doc", correspondent=None)
    body = captured["body"]
    assert body["title"] == "My Doc"
    assert "correspondent" in body
    assert body["correspondent"] is None
    assert "owner" not in body


async def test_list_documents_any_correspondent_overrides_correspondent_none(client, mock_router):
    """any_correspondent takes priority over correspondent=None (no isnull filter added)."""
    captured: dict = {}
    corr_resp = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 3, "name": "ACME"}],
    }
    mock_router.get("/correspondents/").mock(return_value=Response(200, json=corr_resp))
    mock_router.get("/documents/").mock(side_effect=_params_capture(captured, DOC_LIST))

    await client.documents.list(any_correspondent=[3], correspondent=None)

    assert "correspondent__id__in" in captured["params"]  # from any_correspondent
    assert "correspondent__isnull" not in captured["params"]


async def test_update_document_none_clears_multiple_nullable_fields(client, mock_router):
    """Passing None for several nullable fields at once clears all of them."""
    captured: dict = {}
    mock_router.patch("/documents/1/").mock(side_effect=_json_capture(captured, DOC_DATA))
    await client.documents.update(
        1,
        correspondent=None,
        document_type=None,
        storage_path=None,
        owner=None,
        archive_serial_number=None,
    )
    body = captured["body"]
    assert body.get("correspondent") is None
    assert body.get("document_type") is None
    assert body.get("storage_path") is None
    assert body.get("owner") is None
    assert body.get("archive_serial_number") is None


async def test_list_documents_correspondent_id_not_isnull_when_value_given(client, mock_router):
    """Passing a real correspondent ID must NOT add isnull filter."""
    captured: dict = {}
    corr_resp = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{"id": 5, "name": "ACME"}],
    }
    mock_router.get("/correspondents/").mock(return_value=Response(200, json=corr_resp))
    mock_router.get("/documents/").mock(side_effect=_params_capture(captured, DOC_LIST))

    await client.documents.list(correspondent=5)

    assert "correspondent__isnull" not in captured["params"]
    assert "correspondent__id" in captured["params"]
