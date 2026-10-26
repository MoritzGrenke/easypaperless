"""Tests for the groups resource (issue #0049)."""

from __future__ import annotations

import json

import httpx
import pytest

from easypaperless import Group, PagedResult
from easypaperless.exceptions import NotFoundError
from tests._transport import FakePaperless

GROUP = {"id": 3, "name": "Accounting", "permissions": ["view_document"]}
PAGE = {"count": 1, "next": None, "previous": None, "results": [GROUP]}


async def test_list_returns_paged_result_of_groups_and_sends_name_filters() -> None:
    fake = FakePaperless({("GET", "/api/groups/"): PAGE})
    async with fake.async_client() as client:
        result = await client.groups.list(name_contains="acc", name_exact="Accounting")

    assert isinstance(result, PagedResult)
    assert result.count == 1
    assert result.results == [Group(id=3, name="Accounting", permissions=["view_document"])]
    params = fake.requests[0].url.params
    assert params["name__icontains"] == "acc"
    assert params["name__iexact"] == "Accounting"


async def test_get_returns_group() -> None:
    fake = FakePaperless({("GET", "/api/groups/3/"): GROUP})
    async with fake.async_client() as client:
        group = await client.groups.get(3)

    assert group == Group(id=3, name="Accounting", permissions=["view_document"])


async def test_get_unknown_id_raises_not_found() -> None:
    fake = FakePaperless()  # unrouted -> 404
    async with fake.async_client() as client:
        with pytest.raises(NotFoundError):
            await client.groups.get(999)


def _create_group_like_paperless(request: httpx.Request) -> httpx.Response:
    """POST /api/groups/ as paperless-ngx 2.18.2 answers it (verified live, #0050)."""
    body = json.loads(request.content)
    if "permissions" not in body:
        return httpx.Response(400, json={"permissions": ["This field is required."]})
    return httpx.Response(201, json={"id": 7, **body})


async def test_create_without_permissions_sends_empty_list_and_returns_group() -> None:
    # paperless-ngx rejects a group POST without "permissions" (400), so the
    # client sends [] when the caller omits them.
    fake = FakePaperless({("POST", "/api/groups/"): _create_group_like_paperless})
    async with fake.async_client() as client:
        group = await client.groups.create(name="Accounting")

    assert group == Group(id=7, name="Accounting", permissions=[])
    assert json.loads(fake.requests[0].content) == {"name": "Accounting", "permissions": []}


def test_sync_create_without_permissions_sends_empty_list() -> None:
    fake = FakePaperless({("POST", "/api/groups/"): _create_group_like_paperless})
    with fake.sync_client() as client:
        group = client.groups.create(name="Accounting")

    assert group.permissions == []
    assert json.loads(fake.requests[0].content) == {"name": "Accounting", "permissions": []}


async def test_create_sends_permissions() -> None:
    fake = FakePaperless({("POST", "/api/groups/"): httpx.Response(201, json=GROUP)})
    async with fake.async_client() as client:
        await client.groups.create(name="Accounting", permissions=["view_document"])

    assert json.loads(fake.requests[0].content) == {
        "name": "Accounting",
        "permissions": ["view_document"],
    }


async def test_update_patches_only_changed_fields() -> None:
    updated = {**GROUP, "name": "New"}
    fake = FakePaperless({("PATCH", "/api/groups/3/"): updated})
    async with fake.async_client() as client:
        group = await client.groups.update(3, name="New")

    assert group.name == "New"
    assert json.loads(fake.requests[0].content) == {"name": "New"}


async def test_update_can_clear_permissions_with_empty_list() -> None:
    fake = FakePaperless({("PATCH", "/api/groups/3/"): {**GROUP, "permissions": []}})
    async with fake.async_client() as client:
        group = await client.groups.update(3, permissions=[])

    assert group.permissions == []
    assert json.loads(fake.requests[0].content) == {"permissions": []}


async def test_delete_sends_delete_request() -> None:
    fake = FakePaperless({("DELETE", "/api/groups/3/"): httpx.Response(204)})
    async with fake.async_client() as client:
        result = await client.groups.delete(3)

    assert result is None
    assert [(r.method, r.url.path) for r in fake.requests] == [("DELETE", "/api/groups/3/")]


async def test_delete_unknown_id_raises_not_found() -> None:
    fake = FakePaperless()
    async with fake.async_client() as client:
        with pytest.raises(NotFoundError):
            await client.groups.delete(999)


def test_sync_client_provides_full_crud() -> None:
    fake = FakePaperless(
        {
            ("GET", "/api/groups/"): PAGE,
            ("GET", "/api/groups/3/"): GROUP,
            ("POST", "/api/groups/"): httpx.Response(201, json=GROUP),
            ("PATCH", "/api/groups/3/"): {**GROUP, "name": "New"},
            ("DELETE", "/api/groups/3/"): httpx.Response(204),
        }
    )
    with fake.sync_client() as client:
        listed = client.groups.list(name_exact="Accounting", page=1, page_size=10)
        fetched = client.groups.get(3)
        created = client.groups.create(name="Accounting", permissions=["view_document"])
        updated = client.groups.update(3, name="New")
        deleted = client.groups.delete(3)
        with pytest.raises(NotFoundError):
            client.groups.get(999)

    assert listed.results[0].name == "Accounting"
    assert fetched.id == 3
    assert created.permissions == ["view_document"]
    assert updated.name == "New"
    assert deleted is None
    list_params = fake.requests[0].url.params
    assert list_params["name__iexact"] == "Accounting"
    assert list_params["page"] == "1"
    assert list_params["page_size"] == "10"
    assert json.loads(fake.requests[2].content) == {
        "name": "Accounting",
        "permissions": ["view_document"],
    }
    assert json.loads(fake.requests[3].content) == {"name": "New"}


def test_group_and_resources_are_public() -> None:
    import easypaperless
    from easypaperless import models, resources

    assert "Group" in easypaperless.__all__
    assert "Group" in models.__all__
    assert "GroupsResource" in resources.__all__
    assert "SyncGroupsResource" in resources.__all__
