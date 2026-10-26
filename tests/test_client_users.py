"""Tests for PaperlessClient and SyncPaperlessClient users resource."""

from __future__ import annotations

import json

import respx
from httpx import Response

from easypaperless import PaperlessPermission, User
from easypaperless.sync import SyncPaperlessClient

BASE_URL = "http://paperless.test"
API_BASE = BASE_URL + "/api"
API_KEY = "test-api-key"

USER_DATA = {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "password": None,
    "first_name": "Alice",
    "last_name": "Smith",
    "date_joined": "2024-01-01T00:00:00Z",
    "is_staff": False,
    "is_active": True,
    "is_superuser": False,
    "groups": [],
    "user_permissions": ["view_document"],
    "inherited_permissions": ["documents.view_document", "documents.view_tag"],
    "is_mfa_enabled": False,
}
USER_LIST = {"count": 1, "next": None, "previous": None, "results": [USER_DATA]}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_user_model_parses():
    user = User.model_validate(USER_DATA)
    assert user.id == 1
    assert user.username == "alice"
    assert user.user_permissions == ["view_document"]
    assert user.inherited_permissions == ["documents.view_document", "documents.view_tag"]
    assert user.is_mfa_enabled is False


def test_user_model_extra_fields_ignored():
    data = {**USER_DATA, "unknown_future_field": "value"}
    user = User.model_validate(data)
    assert not hasattr(user, "unknown_future_field")


def test_paperless_permission_is_literal_type():
    # PaperlessPermission should be usable as a type; spot-check some values
    perms: list[PaperlessPermission] = [
        "documents.view_document",
        "auth.add_user",
        "documents.delete_tag",
    ]
    assert len(perms) == 3


# ---------------------------------------------------------------------------
# Async resource tests
# ---------------------------------------------------------------------------


async def test_users_list(client, mock_router):
    mock_router.get("/users/").mock(return_value=Response(200, json=USER_LIST))
    result = await client.users.list()
    assert result.count == 1
    assert isinstance(result.results[0], User)
    assert result.results[0].username == "alice"


async def test_users_list_with_filters(client, mock_router):
    captured: dict = {}

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=USER_LIST)

    mock_router.get("/users/").mock(side_effect=_side_effect)
    await client.users.list(username_contains="ali", ordering="username", page=1, page_size=10)
    assert captured["params"]["username__icontains"] == "ali"
    assert captured["params"]["ordering"] == "username"
    assert captured["params"]["page"] == "1"
    assert captured["params"]["page_size"] == "10"


async def test_users_list_username_exact_filter(client, mock_router):
    captured: dict = {}

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=USER_LIST)

    mock_router.get("/users/").mock(side_effect=_side_effect)
    await client.users.list(username_exact="alice")
    assert captured["params"]["username__iexact"] == "alice"
    assert "username__icontains" not in captured["params"]


async def test_users_list_unset_params_omitted(client, mock_router):
    captured: dict = {}

    def _side_effect(request):
        captured["params"] = dict(request.url.params)
        return Response(200, json=USER_LIST)

    mock_router.get("/users/").mock(side_effect=_side_effect)
    await client.users.list()
    assert captured["params"] == {}


async def test_users_get(client, mock_router):
    mock_router.get("/users/1/").mock(return_value=Response(200, json=USER_DATA))
    user = await client.users.get(1)
    assert user.id == 1
    assert user.username == "alice"


async def test_users_create(client, mock_router):
    captured: dict = {}

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(201, json=USER_DATA)

    mock_router.post("/users/").mock(side_effect=_side_effect)
    user = await client.users.create(username="alice", email="alice@example.com", is_active=True)
    assert isinstance(user, User)
    assert captured["body"]["username"] == "alice"
    assert captured["body"]["email"] == "alice@example.com"
    assert captured["body"]["is_active"] is True
    # UNSET fields must not appear in the payload
    assert "password" not in captured["body"]
    assert "groups" not in captured["body"]


async def test_users_create_only_username(client, mock_router):
    captured: dict = {}

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(201, json=USER_DATA)

    mock_router.post("/users/").mock(side_effect=_side_effect)
    await client.users.create(username="alice")
    assert captured["body"] == {"username": "alice"}


async def test_users_update(client, mock_router):
    captured: dict = {}

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(200, json=USER_DATA)

    mock_router.patch("/users/1/").mock(side_effect=_side_effect)
    user = await client.users.update(1, email="new@example.com", is_staff=True)
    assert isinstance(user, User)
    assert captured["body"]["email"] == "new@example.com"
    assert captured["body"]["is_staff"] is True
    assert "username" not in captured["body"]


async def test_users_update_empty_body(client, mock_router):
    captured: dict = {}

    def _side_effect(request):
        captured["body"] = json.loads(request.content)
        return Response(200, json=USER_DATA)

    mock_router.patch("/users/1/").mock(side_effect=_side_effect)
    await client.users.update(1)
    assert captured["body"] == {}


async def test_users_delete(client, mock_router):
    mock_router.delete("/users/1/").mock(return_value=Response(204))
    result = await client.users.delete(1)
    assert result is None


# ---------------------------------------------------------------------------
# Sync resource tests
# ---------------------------------------------------------------------------


def test_sync_users_list():
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.get("/users/").mock(return_value=Response(200, json=USER_LIST))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            result = client.users.list()
    assert result.count == 1
    assert isinstance(result.results[0], User)
    assert result.results[0].username == "alice"


def test_sync_users_get():
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.get("/users/1/").mock(return_value=Response(200, json=USER_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            user = client.users.get(1)
    assert user.id == 1


def test_sync_users_create():
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.post("/users/").mock(return_value=Response(201, json=USER_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            user = client.users.create(username="alice")
    assert isinstance(user, User)


def test_sync_users_update():
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.patch("/users/1/").mock(return_value=Response(200, json=USER_DATA))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            user = client.users.update(1, first_name="Alice")
    assert isinstance(user, User)


def test_sync_users_delete():
    with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
        router.delete("/users/1/").mock(return_value=Response(204))
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            result = client.users.delete(1)
    assert result is None


# ---------------------------------------------------------------------------
# Public API exports
# ---------------------------------------------------------------------------


def test_user_importable_from_easypaperless():
    from easypaperless import User as U

    assert U is User


def test_paperless_permission_importable_from_easypaperless():
    import easypaperless

    assert easypaperless.PaperlessPermission is PaperlessPermission


def test_users_resource_on_async_client(client):
    from easypaperless._internal.resources.users import UsersResource

    assert isinstance(client.users, UsersResource)


def test_users_resource_on_sync_client():
    from easypaperless._internal.sync_resources.users import SyncUsersResource

    with respx.mock(base_url=API_BASE, assert_all_called=False):
        with SyncPaperlessClient(url=BASE_URL, api_token=API_KEY) as client:
            assert isinstance(client.users, SyncUsersResource)
