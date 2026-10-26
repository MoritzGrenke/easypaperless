"""Tests for server_version() and system_status() (issue #0048)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from easypaperless import (
    AuthenticationError,
    NotFoundError,
    NotPaperlessError,
    PermissionDeniedError,
    ServerError,
    SystemStatus,
    TransportError,
)
from tests._transport import API_TOKEN, FakePaperless

API_ROOT = {"documents": "http://paperless.test/api/documents/"}


def _version_response(version: str = "2.18.4") -> httpx.Response:
    return httpx.Response(200, json=API_ROOT, headers={"X-Version": version, "X-Api-Version": "9"})


async def test_server_version_returns_x_version_header_with_one_authenticated_request() -> None:
    fake = FakePaperless({("GET", "/api/"): _version_response("2.18.4")})
    async with fake.async_client() as client:
        version = await client.server_version()

    assert version == "2.18.4"
    assert len(fake.requests) == 1
    assert fake.requests[0].headers["Authorization"] == f"Token {API_TOKEN}"


async def test_server_version_without_header_raises_not_paperless() -> None:
    fake = FakePaperless({("GET", "/api/"): httpx.Response(200, json={"hello": "world"})})
    async with fake.async_client() as client:
        with pytest.raises(NotPaperlessError, match="not appear to be a paperless-ngx instance"):
            await client.server_version()


async def test_server_version_404_raises_not_paperless_not_not_found() -> None:
    fake = FakePaperless({("GET", "/api/"): httpx.Response(404, text="Not Found")})
    async with fake.async_client() as client:
        with pytest.raises(NotPaperlessError, match="paperless-ngx") as exc_info:
            await client.server_version()

    assert not isinstance(exc_info.value, NotFoundError)
    assert exc_info.value.status_code == 404


async def test_server_version_html_page_after_redirect_raises_not_paperless() -> None:
    # A foreign web server redirects /api/ to an HTML page; the client follows it.
    html = "<!DOCTYPE html><html><body>Welcome to nginx!</body></html>"
    fake = FakePaperless(
        {
            ("GET", "/api/"): httpx.Response(302, headers={"Location": "/welcome/"}),
            ("GET", "/welcome/"): httpx.Response(
                200, text=html, headers={"Content-Type": "text/html; charset=utf-8"}
            ),
        }
    )
    async with fake.async_client() as client:
        with pytest.raises(NotPaperlessError, match="not appear to be a paperless-ngx instance"):
            await client.server_version()

    assert [r.url.path for r in fake.requests] == ["/api/", "/welcome/"]


async def test_server_version_refused_token_raises_authentication_error() -> None:
    fake = FakePaperless({("GET", "/api/"): httpx.Response(401, json={"detail": "Invalid token."})})
    async with fake.async_client() as client:
        with pytest.raises(AuthenticationError, match="Invalid token."):
            await client.server_version()


async def test_server_version_transport_failure_raises_transport_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    fake = FakePaperless({("GET", "/api/"): refuse})
    async with fake.async_client() as client:
        with pytest.raises(TransportError) as exc_info:
            await client.server_version()

    assert isinstance(exc_info.value, ServerError)
    assert exc_info.value.status_code is None


# Modelled on paperless-ngx 2.x ``GET /api/status/`` (SystemStatusView). The live
# instance was unreachable, so this is not a captured response. "future_key" and
# "future_section" check that unknown fields are ignored.
STATUS = {
    "pngx_version": "2.18.4",
    "server_os": "Linux-6.8.0-x86_64-with-glibc2.36",
    "install_type": "docker",
    "storage": {"total": 1000000000, "available": 250000000},
    "database": {
        "type": "postgresql",
        "url": "paperless",
        "status": "OK",
        "error": None,
        "migration_status": {
            "latest_migration": "documents.1061_workflowactionwebhook_as_json",
            "unapplied_migrations": [],
        },
    },
    "tasks": {
        "redis_url": "redis://broker:6379",
        "redis_status": "OK",
        "redis_error": None,
        "celery_status": "OK",
        "celery_url": "celery@worker",
        "celery_error": None,
        "index_status": "OK",
        "index_last_modified": "2026-10-26T08:15:00.123456+01:00",
        "index_error": None,
        "classifier_status": "WARNING",
        "classifier_last_trained": None,
        "classifier_error": "Classifier file does not exist (yet).",
        "sanity_check_status": "OK",
        "sanity_check_last_run": "2026-10-25T23:30:00Z",
        "sanity_check_error": None,
        "future_key": "ignored",
    },
    "future_section": {"anything": 1},
}


async def test_system_status_returns_populated_model() -> None:
    fake = FakePaperless({("GET", "/api/status/"): STATUS})
    async with fake.async_client() as client:
        status = await client.system_status()

    assert isinstance(status, SystemStatus)
    assert status.version == "2.18.4"
    assert status.install_type == "docker"
    assert status.server_os == "Linux-6.8.0-x86_64-with-glibc2.36"
    assert status.storage is not None
    assert status.storage.total == 1000000000
    assert status.storage.available == 250000000
    assert status.database is not None
    assert status.database.type == "postgresql"
    assert status.database.status == "OK"
    assert status.database.migration_status is not None
    assert status.database.migration_status.unapplied_migrations == []
    assert status.tasks is not None
    assert status.tasks.redis_status == "OK"
    assert status.tasks.celery_status == "OK"
    assert status.tasks.index_last_modified == datetime(
        2026, 10, 26, 7, 15, 0, 123456, tzinfo=timezone.utc
    )
    assert status.tasks.classifier_status == "WARNING"
    assert status.tasks.classifier_last_trained is None
    assert status.tasks.classifier_error == "Classifier file does not exist (yet)."


async def test_system_status_minimal_body_leaves_fields_none() -> None:
    fake = FakePaperless({("GET", "/api/status/"): {"pngx_version": "2.0.0"}})
    async with fake.async_client() as client:
        status = await client.system_status()

    assert status == SystemStatus(version="2.0.0")
    assert status.database is None


FORBIDDEN = httpx.Response(
    403, json={"detail": "You do not have permission to perform this action."}
)


async def test_system_status_non_admin_raises_permission_denied() -> None:
    fake = FakePaperless({("GET", "/api/status/"): FORBIDDEN})
    async with fake.async_client() as client:
        with pytest.raises(PermissionDeniedError, match="do not have permission"):
            await client.system_status()


# ---------------------------------------------------------------------------
# Sync client behaves identically
# ---------------------------------------------------------------------------


def test_sync_server_version_returns_header() -> None:
    fake = FakePaperless({("GET", "/api/"): _version_response("2.18.4")})
    with fake.sync_client() as client:
        assert client.server_version() == "2.18.4"
    assert len(fake.requests) == 1


def test_sync_server_version_404_raises_not_paperless() -> None:
    fake = FakePaperless({("GET", "/api/"): httpx.Response(404, text="Not Found")})
    with fake.sync_client() as client, pytest.raises(NotPaperlessError):
        client.server_version()


def test_sync_server_version_refused_token_raises_authentication_error() -> None:
    fake = FakePaperless({("GET", "/api/"): httpx.Response(401, json={"detail": "Invalid token."})})
    with fake.sync_client() as client, pytest.raises(AuthenticationError):
        client.server_version()


def test_sync_system_status_returns_model() -> None:
    fake = FakePaperless({("GET", "/api/status/"): STATUS})
    with fake.sync_client() as client:
        status = client.system_status()
    assert isinstance(status, SystemStatus)
    assert status.version == "2.18.4"
    assert status.tasks is not None
    assert status.tasks.celery_status == "OK"


def test_sync_system_status_non_admin_raises_permission_denied() -> None:
    fake = FakePaperless({("GET", "/api/status/"): FORBIDDEN})
    with fake.sync_client() as client, pytest.raises(PermissionDeniedError):
        client.system_status()
