"""Tests for reading object permissions back via ``full_perms`` (issue #0053).

The fake answers like paperless-ngx 2.18.2 (verified live in the #0053 spike): with
``full_perms`` set to a truthy value the object carries a ``permissions`` block and
``user_can_change`` is dropped; without it there is no ``permissions`` key.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from easypaperless import PermissionSet, SetPermissions
from tests._transport import FakePaperless

PERMS_JSON = {
    "view": {"users": [14], "groups": [6]},
    "change": {"users": [], "groups": [6]},
}
PERMS = SetPermissions(
    view=PermissionSet(users=[14], groups=[6]),
    change=PermissionSet(users=[], groups=[6]),
)
DOCUMENT = {"id": 42, "title": "Invoice", "owner": 3}


def _like_paperless(obj: dict[str, Any]) -> Any:
    """Detail handler: add ``permissions`` only when ``full_perms`` is truthy."""

    def handler(request: httpx.Request) -> httpx.Response:
        full = request.url.params.get("full_perms", "").lower() in ("true", "1")
        if full:
            return httpx.Response(200, json={**obj, "permissions": PERMS_JSON})
        return httpx.Response(200, json={**obj, "user_can_change": True})

    return handler


async def test_documents_get_full_perms_sends_flag_and_returns_permissions() -> None:
    fake = FakePaperless({("GET", "/api/documents/42/"): _like_paperless(DOCUMENT)})
    async with fake.async_client() as client:
        doc = await client.documents.get(42, full_perms=True)

    assert fake.requests[0].url.params["full_perms"] == "true"
    assert doc.owner == 3
    assert doc.permissions == PERMS


async def test_documents_get_without_full_perms_sends_no_flag_and_permissions_is_none() -> None:
    fake = FakePaperless({("GET", "/api/documents/42/"): _like_paperless(DOCUMENT)})
    async with fake.async_client() as client:
        doc = await client.documents.get(42)

    assert "full_perms" not in fake.requests[0].url.params
    assert doc.permissions is None
    assert doc.user_can_change is True


def _list_like_paperless(obj: dict[str, Any]) -> Any:
    """List handler: one page holding ``obj``, shaped by ``full_perms`` like the detail."""
    detail = _like_paperless(obj)

    def handler(request: httpx.Request) -> httpx.Response:
        item = detail(request).json()
        return httpx.Response(
            200, json={"count": 1, "next": None, "previous": None, "results": [item]}
        )

    return handler


async def test_documents_list_full_perms_returns_documents_with_permissions() -> None:
    fake = FakePaperless({("GET", "/api/documents/"): _list_like_paperless(DOCUMENT)})
    async with fake.async_client() as client:
        result = await client.documents.list(full_perms=True)

    assert fake.requests[0].url.params["full_perms"] == "true"
    assert [d.permissions for d in result.results] == [PERMS]


async def test_documents_list_without_full_perms_sends_no_flag() -> None:
    fake = FakePaperless({("GET", "/api/documents/"): _list_like_paperless(DOCUMENT)})
    async with fake.async_client() as client:
        result = await client.documents.list()

    assert "full_perms" not in fake.requests[0].url.params
    assert [d.permissions for d in result.results] == [None]


async def test_documents_list_full_perms_returns_permissions_on_every_page() -> None:
    # paperless-ngx keeps full_perms in the ``next`` URL; documents of page 2 must
    # carry permissions as well.
    detail = _like_paperless(DOCUMENT)

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        item = {**detail(request).json(), "id": 40 + page}
        next_url = (
            "http://paperless.test/api/documents/?full_perms=true&page=2" if page == 1 else None
        )
        return httpx.Response(
            200, json={"count": 2, "next": next_url, "previous": None, "results": [item]}
        )

    fake = FakePaperless({("GET", "/api/documents/"): handler})
    async with fake.async_client() as client:
        result = await client.documents.list(full_perms=True)

    assert [d.id for d in result.results] == [41, 42]
    assert [d.permissions for d in result.results] == [PERMS, PERMS]
    assert [r.url.params.get("full_perms") for r in fake.requests] == ["true", "true"]


def test_sync_documents_get_and_list_full_perms() -> None:
    fake = FakePaperless(
        {
            ("GET", "/api/documents/42/"): _like_paperless(DOCUMENT),
            ("GET", "/api/documents/"): _list_like_paperless(DOCUMENT),
        }
    )
    with fake.sync_client() as client:
        doc = client.documents.get(42, full_perms=True)
        listed = client.documents.list(full_perms=True)
        plain = client.documents.get(42)

    assert doc.permissions == PERMS
    assert [d.permissions for d in listed.results] == [PERMS]
    assert plain.permissions is None
    assert [r.url.params.get("full_perms") for r in fake.requests] == ["true", "true", None]


# --- other owned objects: tags, correspondents, document types, storage paths ----------

OWNED = {
    "tags": {"id": 5, "name": "inbox", "owner": 3},
    "correspondents": {"id": 5, "name": "ACME", "owner": 3},
    "document_types": {"id": 5, "name": "Invoice", "owner": 3},
    "storage_paths": {"id": 5, "name": "Archive", "path": "{title}", "owner": 3},
}
RESOURCES = pytest.mark.parametrize("resource", sorted(OWNED))


def _owned_fake(resource: str) -> FakePaperless:
    obj = OWNED[resource]
    return FakePaperless(
        {
            ("GET", f"/api/{resource}/5/"): _like_paperless(obj),
            ("GET", f"/api/{resource}/"): _list_like_paperless(obj),
        }
    )


@RESOURCES
async def test_owned_resource_get_and_list_full_perms(resource: str) -> None:
    fake = _owned_fake(resource)
    async with fake.async_client() as client:
        res = getattr(client, resource)
        got = await res.get(5, full_perms=True)
        listed = await res.list(full_perms=True)

    assert got.owner == 3
    assert got.permissions == PERMS
    assert [o.permissions for o in listed.results] == [PERMS]
    assert [r.url.params.get("full_perms") for r in fake.requests] == ["true", "true"]


@RESOURCES
async def test_owned_resource_without_full_perms_sends_no_flag(resource: str) -> None:
    fake = _owned_fake(resource)
    async with fake.async_client() as client:
        res = getattr(client, resource)
        got = await res.get(5)
        listed = await res.list()

    assert got.permissions is None
    assert got.user_can_change is True
    assert [o.permissions for o in listed.results] == [None]
    assert ["full_perms" in r.url.params for r in fake.requests] == [False, False]


@RESOURCES
def test_sync_owned_resource_get_and_list_full_perms(resource: str) -> None:
    fake = _owned_fake(resource)
    with fake.sync_client() as client:
        res = getattr(client, resource)
        got = res.get(5, full_perms=True)
        listed = res.list(full_perms=True)
        plain = res.get(5)

    assert got.permissions == PERMS
    assert [o.permissions for o in listed.results] == [PERMS]
    assert plain.permissions is None
    assert [r.url.params.get("full_perms") for r in fake.requests] == ["true", "true", None]
