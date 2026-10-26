"""Tests for ui_settings() and the UiSettings permission helpers (issue #0055)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pytest

from easypaperless import (
    AuthenticationError,
    PermissionDeniedError,
    TransportError,
    UiSettings,
    UiSettingsServerSettings,
    UiSettingsUser,
)
from tests import test_issue_0047_secrets as secrets
from tests._transport import API_TOKEN, FakePaperless

ROUTE = ("GET", "/api/ui_settings/")

# Recorded from paperless-ngx 2.18.2 (non-admin user, username replaced).
NON_ADMIN_BODY: dict[str, Any] = {
    "user": {
        "id": 16,
        "username": "service-user",
        "is_staff": False,
        "is_superuser": False,
        "groups": [9],
    },
    "settings": {
        "update_checking": {"backend_setting": "default"},
        "trash_delay": 30,
        "version": "2.18.2",
        "app_title": None,
        "app_logo": None,
        "auditlog_enabled": True,
        "email_enabled": False,
    },
    "permissions": ["view_paperlesstask", "add_document", "view_uisettings"],
}


async def test_ui_settings_returns_user_permissions_and_settings() -> None:
    fake = FakePaperless({ROUTE: NON_ADMIN_BODY})
    async with fake.async_client() as client:
        result = await client.ui_settings()

    assert len(fake.requests) == 1
    assert fake.requests[0].method == "GET"
    assert fake.requests[0].headers["Authorization"] == f"Token {API_TOKEN}"
    assert result.user.id == 16
    assert result.user.username == "service-user"
    assert result.user.is_staff is False
    assert result.user.is_superuser is False
    assert result.user.groups == [9]
    assert result.permissions == ["view_paperlesstask", "add_document", "view_uisettings"]
    assert result.settings.version == "2.18.2"
    assert result.settings.trash_delay == 30
    assert result.settings.app_title is None
    assert result.settings.auditlog_enabled is True
    assert result.settings.email_enabled is False
    assert result.settings.update_checking == {"backend_setting": "default"}


def test_sync_ui_settings_returns_same_model() -> None:
    fake = FakePaperless({ROUTE: NON_ADMIN_BODY})
    with fake.sync_client() as client:
        result = client.ui_settings()

    assert len(fake.requests) == 1
    assert result.user.username == "service-user"
    assert result.permissions == ["view_paperlesstask", "add_document", "view_uisettings"]
    assert result.settings.version == "2.18.2"


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------


def _settings(permissions: list[str], *, is_superuser: bool = False) -> UiSettings:
    return UiSettings.model_validate(
        {
            "user": {
                "id": 1,
                "username": "u",
                "is_staff": is_superuser,
                "is_superuser": is_superuser,
                "groups": [],
            },
            "settings": {},
            "permissions": permissions,
        }
    )


def test_missing_permissions_names_the_codenames_the_user_lacks() -> None:
    settings = _settings(["add_document"])

    assert settings.missing_permissions({"add_document", "add_note"}) == {"add_note"}


def test_missing_permissions_accepts_any_iterable_and_returns_empty_set_when_complete() -> None:
    settings = _settings(["add_document", "add_note", "view_user"])

    assert settings.missing_permissions(["add_note", "view_user"]) == set()
    assert settings.missing_permissions(iter(["add_note", "delete_note"])) == {"delete_note"}


def test_has_permission_checks_the_bare_codename() -> None:
    settings = _settings(["add_document"])

    assert settings.has_permission("add_document") is True
    assert settings.has_permission("add_note") is False
    assert settings.has_permission("documents.add_document") is False


def test_superuser_has_every_permission_even_if_not_listed() -> None:
    settings = _settings([], is_superuser=True)

    assert settings.missing_permissions({"add_document", "add_note"}) == set()
    assert settings.has_permission("anything_at_all") is True


async def test_permissions_from_the_response_drive_the_helpers() -> None:
    fake = FakePaperless({ROUTE: NON_ADMIN_BODY})
    async with fake.async_client() as client:
        result = await client.ui_settings()

    required = {"add_document", "view_paperlesstask", "add_note"}
    assert result.missing_permissions(required) == {"add_note"}


# ---------------------------------------------------------------------------
# Robustness against other paperless versions
# ---------------------------------------------------------------------------


async def test_unknown_fields_at_every_level_are_ignored() -> None:
    body = {
        "user": {**NON_ADMIN_BODY["user"], "first_name": "Ann", "is_active": True},
        "settings": {**NON_ADMIN_BODY["settings"], "dark_mode": {"enabled": True}, "x": 1},
        "permissions": ["add_document"],
        "future_top_level_key": {"a": 1},
    }
    fake = FakePaperless({ROUTE: body})
    async with fake.async_client() as client:
        result = await client.ui_settings()

    assert result.user.username == "service-user"
    assert result.permissions == ["add_document"]
    assert result.settings.version == "2.18.2"


async def test_minimal_body_leaves_settings_none() -> None:
    fake = FakePaperless({ROUTE: {"user": {"id": 1, "username": "u"}}})
    async with fake.async_client() as client:
        result = await client.ui_settings()

    assert result.permissions == []
    assert result.user.is_superuser is False
    assert result.user.groups == []
    assert result.settings == UiSettingsServerSettings()
    assert result.settings.version is None
    assert isinstance(result.user, UiSettingsUser)


# ---------------------------------------------------------------------------
# Errors (#0046)
# ---------------------------------------------------------------------------


async def test_refused_token_raises_authentication_error() -> None:
    fake = FakePaperless({ROUTE: httpx.Response(401, json={"detail": "Invalid token."})})
    async with fake.async_client() as client:
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await client.ui_settings()


async def test_user_without_view_uisettings_raises_permission_denied() -> None:
    detail = "You do not have permission to perform this action."
    fake = FakePaperless({ROUTE: httpx.Response(403, json={"detail": detail})})
    async with fake.async_client() as client:
        with pytest.raises(PermissionDeniedError, match="do not have permission"):
            await client.ui_settings()


async def test_transport_failure_raises_transport_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    fake = FakePaperless({ROUTE: refuse})
    async with fake.async_client() as client:
        with pytest.raises(TransportError):
            await client.ui_settings()


def test_sync_refused_token_raises_authentication_error() -> None:
    fake = FakePaperless({ROUTE: httpx.Response(401, json={"detail": "Invalid token."})})
    with fake.sync_client() as client:
        with pytest.raises(AuthenticationError):
            client.ui_settings()


# ---------------------------------------------------------------------------
# The token never leaks (#0047 pattern)
# ---------------------------------------------------------------------------


async def test_ui_settings_result_and_logs_do_not_contain_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakePaperless({ROUTE: NON_ADMIN_BODY})
    async with secrets._async_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            result = await client.ui_settings()
    assert fake.requests[0].headers["Authorization"] == f"Token {secrets.TOKEN}"
    assert secrets.TOKEN not in repr(result)
    assert secrets.TOKEN not in result.model_dump_json()
    assert any("UI settings" in r.getMessage() for r in caplog.records)
    assert secrets.TOKEN not in secrets._log_text(caplog)


@pytest.mark.parametrize("case", ["401", "403", "500", "connect", "timeout"])
async def test_ui_settings_errors_do_not_contain_token(
    case: str, caplog: pytest.LogCaptureFixture
) -> None:
    route, expected = secrets.ERROR_ROUTES[case]
    fake = FakePaperless({ROUTE: route})
    async with secrets._async_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            with pytest.raises(expected) as exc_info:
                await client.ui_settings()
    secrets._assert_no_secret_in(exc_info.value)
    assert secrets.TOKEN not in secrets._log_text(caplog)


def test_sync_ui_settings_error_does_not_contain_token(caplog: pytest.LogCaptureFixture) -> None:
    route, _ = secrets.ERROR_ROUTES["connect"]
    fake = FakePaperless({ROUTE: route})
    with secrets._sync_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            with pytest.raises(TransportError) as exc_info:
                client.ui_settings()
    secrets._assert_no_secret_in(exc_info.value)
    assert secrets.TOKEN not in secrets._log_text(caplog)
