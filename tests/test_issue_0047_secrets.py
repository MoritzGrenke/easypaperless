"""Tests for issue #0047: the API token and passwords never leak.

A distinctive token and password are used throughout; every test asserts they
are absent from reprs, exception messages, formatted tracebacks and captured
log records. Errors are triggered through the public client API against a
``FakePaperless`` transport (#0043).
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

import httpx
import pytest

from easypaperless import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PaperlessClient,
    PaperlessError,
    PermissionDeniedError,
    RetryExhaustedError,
    ServerResponseError,
    SyncPaperlessClient,
    TaskTimeoutError,
    TransportError,
    TransportTimeoutError,
    UploadError,
    ValidationError,
)
from tests._transport import BASE_URL, FakePaperless

TOKEN = "SECRET-123-TOKEN"
PASSWORD = "PW-SECRET-456"


def _async_client(fake: FakePaperless, **kwargs: Any) -> PaperlessClient:
    return PaperlessClient(url=BASE_URL, api_token=TOKEN, transport=fake.transport, **kwargs)


def _sync_client(fake: FakePaperless, **kwargs: Any) -> SyncPaperlessClient:
    return SyncPaperlessClient(url=BASE_URL, api_token=TOKEN, transport=fake.transport, **kwargs)


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


async def test_async_client_repr_shows_url_but_not_token() -> None:
    async with _async_client(FakePaperless()) as client:
        text = repr(client)
        assert TOKEN not in text
        assert BASE_URL in text
        assert TOKEN not in repr(client._session)
        assert BASE_URL in repr(client._session)


def test_sync_client_repr_shows_url_but_not_token() -> None:
    with _sync_client(FakePaperless()) as client:
        text = repr(client)
        assert TOKEN not in text
        assert BASE_URL in text


# ---------------------------------------------------------------------------
# DEBUG logging of request bodies masks passwords
# ---------------------------------------------------------------------------

USER_BODY = {"id": 7, "username": "u", "password": "**********"}


def _log_text(caplog: pytest.LogCaptureFixture) -> str:
    """Every captured record, formatted, plus its raw msg and args."""
    return "\n".join(f"{r.getMessage()} {r.args!r} {r.msg!r}" for r in caplog.records)


async def test_users_create_debug_log_masks_password(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakePaperless({("POST", "/api/users/"): httpx.Response(201, json=USER_BODY)})
    async with _async_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            await client.users.create(username="u", password=PASSWORD)
    text = _log_text(caplog)
    assert PASSWORD not in text
    assert "'username': 'u'" in text  # other body fields are still logged
    assert "'password': '***'" in text
    # the real password is still sent to the server
    assert PASSWORD in fake.requests[0].content.decode()


async def test_users_update_debug_log_masks_password(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakePaperless({("PATCH", "/api/users/7/"): USER_BODY})
    async with _async_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            await client.users.update(7, password=PASSWORD, first_name="Ann")
    text = _log_text(caplog)
    assert PASSWORD not in text
    assert "'first_name': 'Ann'" in text
    assert PASSWORD in fake.requests[0].content.decode()


def test_sync_users_create_debug_log_masks_password(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakePaperless({("POST", "/api/users/"): httpx.Response(201, json=USER_BODY)})
    with _sync_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            client.users.create(username="u", password=PASSWORD)
    assert PASSWORD not in _log_text(caplog)


# ---------------------------------------------------------------------------
# Exceptions raised by the HTTP layer
# ---------------------------------------------------------------------------

TAG = ("GET", "/api/tags/1/")


def _raise(exc_type: type[httpx.TransportError], message: str) -> object:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc_type(message, request=request)

    return handler


ERROR_ROUTES: dict[str, tuple[object, type[PaperlessError]]] = {
    "400": (httpx.Response(400, json={"name": ["Invalid."]}), BadRequestError),
    "401": (httpx.Response(401, json={"detail": "Invalid token."}), AuthenticationError),
    "403": (httpx.Response(403, json={"detail": "Forbidden."}), PermissionDeniedError),
    "404": (httpx.Response(404, json={"detail": "Not found."}), NotFoundError),
    "422": (httpx.Response(422, json={"detail": "Unprocessable."}), ValidationError),
    "500": (httpx.Response(500, text="<html>Internal error</html>"), ServerResponseError),
    "connect": (_raise(httpx.ConnectError, "[Errno 111] Connection refused"), TransportError),
    "protocol": (_raise(httpx.RemoteProtocolError, "Server disconnected"), TransportError),
    "timeout": (_raise(httpx.ReadTimeout, "timed out"), TransportTimeoutError),
}


def _assert_no_secret_in(err: BaseException) -> None:
    """Token absent from str, repr, the formatted traceback and every cause."""
    assert TOKEN not in str(err)
    assert TOKEN not in repr(err)
    assert TOKEN not in "".join(traceback.format_exception(err))
    cause = err.__cause__
    while cause is not None:
        assert TOKEN not in str(cause)
        assert TOKEN not in repr(cause)
        request = getattr(cause, "_request", None)
        if request is not None:
            assert TOKEN not in repr(request)
            assert TOKEN not in repr(request.headers)
        cause = cause.__cause__


@pytest.mark.parametrize("case", list(ERROR_ROUTES))
async def test_http_errors_do_not_contain_token(
    case: str, caplog: pytest.LogCaptureFixture
) -> None:
    route, expected = ERROR_ROUTES[case]
    fake = FakePaperless({TAG: route})
    async with _async_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            with pytest.raises(expected) as exc_info:
                await client.tags.get(1)
    # The token really was sent, so its absence below is meaningful.
    assert fake.requests[0].headers["Authorization"] == f"Token {TOKEN}"
    _assert_no_secret_in(exc_info.value)
    assert caplog.records  # DEBUG logging actually ran
    assert TOKEN not in _log_text(caplog)


@pytest.mark.parametrize("case", ["500", "connect", "timeout"])
async def test_retry_exhausted_does_not_contain_token(
    case: str, caplog: pytest.LogCaptureFixture
) -> None:
    route, _ = ERROR_ROUTES[case]
    fake = FakePaperless({TAG: route})
    async with _async_client(fake, retry_attempts=2, retry_backoff=0.0) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            with pytest.raises(RetryExhaustedError) as exc_info:
                await client.tags.get(1)
    assert len(fake.requests) == 3
    _assert_no_secret_in(exc_info.value)
    assert TOKEN not in _log_text(caplog)


def test_sync_client_error_does_not_contain_token(caplog: pytest.LogCaptureFixture) -> None:
    route, _ = ERROR_ROUTES["connect"]
    fake = FakePaperless({TAG: route})
    with _sync_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            with pytest.raises(TransportError) as exc_info:
                client.tags.get(1)
    _assert_no_secret_in(exc_info.value)
    assert TOKEN not in _log_text(caplog)


def test_upload_and_task_timeout_errors_do_not_contain_token() -> None:
    # Constructed directly: their raising code paths are reworked in #0044/#0045.
    errors: list[PaperlessError] = [
        UploadError("Document processing failed: corrupt file"),
        TaskTimeoutError("Task abc did not finish within 60s"),
    ]
    for err in errors:
        _assert_no_secret_in(err)


async def test_full_request_cycle_debug_log_has_no_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    page1 = {
        "count": 2,
        "next": f"{BASE_URL}/api/tags/?page=2",
        "previous": None,
        "results": [{"id": 1, "name": "a"}],
    }
    page2 = {"count": 2, "next": None, "previous": None, "results": [{"id": 2, "name": "b"}]}
    fake = FakePaperless(
        {
            ("GET", "/api/tags/"): FakePaperless.seq(page1, page2),
            ("POST", "/api/tags/"): httpx.Response(201, json={"id": 3, "name": "c"}),
            ("PATCH", "/api/tags/3/"): {"id": 3, "name": "d"},
            ("DELETE", "/api/tags/3/"): httpx.Response(204),
            ("GET", "/api/documents/5/download/"): httpx.Response(
                302, headers={"location": f"{BASE_URL}/media/5.pdf"}
            ),
            ("GET", "/media/5.pdf"): httpx.Response(200, content=b"%PDF"),
            TAG: httpx.Response(401, json={"detail": "Invalid token."}),
        }
    )
    async with _async_client(fake) as client:
        with caplog.at_level(logging.DEBUG, logger="easypaperless"):
            await client.tags.list()
            await client.tags.create(name="c")
            await client.tags.update(3, name="d")
            await client.tags.delete(3)
            await client.documents.download(5)
            with pytest.raises(AuthenticationError):
                await client.tags.get(1)
    levels = {r.levelno for r in caplog.records}
    assert {logging.DEBUG, logging.INFO, logging.WARNING} <= levels
    assert TOKEN not in _log_text(caplog)
