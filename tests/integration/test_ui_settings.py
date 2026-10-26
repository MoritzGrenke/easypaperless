"""Integration tests for ``ui_settings()`` and its permission helpers (#0055).

A temporary non-admin user is created with some permissions granted directly
and one only via a temporary group.  Its token is fetched from paperless's
``/api/token/`` endpoint; the user and the group are deleted afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from easypaperless import PaperlessClient, PermissionDeniedError, SyncPaperlessClient
from tests.integration.conftest import _require_env

pytestmark = pytest.mark.integration

# Permissions a delivery needs (README example) plus the one ui_settings() needs.
DELIVERY = {
    "add_document",
    "view_document",
    "change_document",
    "add_note",
    "delete_note",
    "view_user",
    "view_paperlesstask",
    "view_uisettings",
}


@asynccontextmanager
async def _temp_user_client(
    admin: PaperlessClient,
    url: str,
    *,
    user_permissions: list[str],
    group_permissions: list[str],
) -> AsyncIterator[PaperlessClient]:
    """Yield a client authenticated as a fresh non-admin user in a fresh group."""
    uid = uuid.uuid4().hex[:8]
    password = f"Pw-{uuid.uuid4().hex}"
    group = await admin.groups.create(name=f"__it_0055_{uid}", permissions=group_permissions)
    try:
        user = await admin.users.create(
            username=f"__it_0055_{uid}",
            password=password,
            user_permissions=user_permissions,
            groups=[group.id],
        )
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                resp = await http.post(
                    f"{url.rstrip('/')}/api/token/",
                    data={"username": user.username, "password": password},
                )
            resp.raise_for_status()
            token = resp.json()["token"]
            async with PaperlessClient(url=url, api_token=token) as client:
                yield client
        finally:
            await admin.users.delete(user.id)
    finally:
        await admin.groups.delete(group.id)


async def test_ui_settings_includes_direct_and_group_permissions() -> None:
    url, key = _require_env()
    async with PaperlessClient(url=url, api_token=key) as admin:
        async with _temp_user_client(
            admin,
            url,
            user_permissions=["add_document", "view_uisettings"],
            group_permissions=["view_paperlesstask"],
        ) as client:
            settings = await client.ui_settings()

    assert settings.user.username.startswith("__it_0055_")
    assert settings.user.is_superuser is False
    assert settings.user.is_staff is False
    assert len(settings.user.groups) == 1
    # granted directly
    assert settings.has_permission("add_document")
    # granted only via the group
    assert settings.has_permission("view_paperlesstask")
    assert settings.missing_permissions(DELIVERY) == {
        "view_document",
        "change_document",
        "add_note",
        "delete_note",
        "view_user",
    }
    assert settings.settings.version


async def test_ui_settings_without_view_uisettings_raises_permission_denied() -> None:
    url, key = _require_env()
    async with PaperlessClient(url=url, api_token=key) as admin:
        async with _temp_user_client(
            admin, url, user_permissions=["add_document"], group_permissions=[]
        ) as client:
            with pytest.raises(PermissionDeniedError):
                await client.ui_settings()


def test_sync_ui_settings_for_admin_token() -> None:
    url, key = _require_env()
    with SyncPaperlessClient(url=url, api_token=key) as client:
        settings = client.ui_settings()

    assert settings.permissions  # bare codenames
    assert all("." not in p for p in settings.permissions)
    if settings.user.is_superuser:
        assert settings.missing_permissions(DELIVERY) == set()
