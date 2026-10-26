"""Tests for issue #0046: classifiable error hierarchy.

Every test goes through the public client API against a ``FakePaperless``
transport (#0043) and checks the class, ``status_code`` and message of the
raised exception.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from easypaperless import (
    AuthenticationError,
    AuthError,
    BadRequestError,
    NotFoundError,
    PaperlessError,
    PermissionDeniedError,
    RetryExhaustedError,
    ServerError,
    ServerResponseError,
    TransportError,
    TransportTimeoutError,
    ValidationError,
)
from tests._transport import FakePaperless

TAG = ("GET", "/api/tags/1/")


def _status(code: int, body: object) -> httpx.Response:
    return httpx.Response(code, json=body)


# ---------------------------------------------------------------------------
# 401 / 403
# ---------------------------------------------------------------------------


async def test_401_raises_authentication_error() -> None:
    fake = FakePaperless({TAG: _status(401, {"detail": "Invalid token."})})
    async with fake.async_client() as client:
        with pytest.raises(AuthenticationError) as exc_info:
            await client.tags.get(1)
    err = exc_info.value
    assert isinstance(err, AuthError)
    assert err.status_code == 401
    assert str(err) == "Invalid token."


async def test_403_raises_permission_denied_with_detail_verbatim() -> None:
    detail = "You do not have permission to perform this action."
    fake = FakePaperless({TAG: _status(403, {"detail": detail})})
    async with fake.async_client() as client:
        with pytest.raises(PermissionDeniedError) as exc_info:
            await client.tags.get(1)
    err = exc_info.value
    assert isinstance(err, AuthError)
    assert not isinstance(err, AuthenticationError)
    assert err.status_code == 403
    assert detail in str(err)


# ---------------------------------------------------------------------------
# 400
# ---------------------------------------------------------------------------

TAGS_POST = ("POST", "/api/tags/")


async def test_400_field_errors_are_parsed() -> None:
    body = {"name": ["This field is required."]}
    fake = FakePaperless({TAGS_POST: _status(400, body)})
    async with fake.async_client() as client:
        with pytest.raises(BadRequestError) as exc_info:
            await client.tags.create(name="")
    err = exc_info.value
    assert isinstance(err, PaperlessError)
    assert err.status_code == 400
    assert err.field_errors == {"name": ["This field is required."]}
    assert err.non_field_errors == []
    assert "name: This field is required." in str(err)


@pytest.mark.parametrize(
    ("response", "field_errors", "non_field_errors"),
    [
        pytest.param(
            _status(400, {"non_field_errors": ["Name already exists."]}),
            {},
            ["Name already exists."],
            id="non_field_errors",
        ),
        pytest.param(
            _status(400, ["Invalid document ids.", "Second problem."]),
            {},
            ["Invalid document ids.", "Second problem."],
            id="plain-list",
        ),
        pytest.param(
            _status(400, {"detail": "Malformed request."}),
            {},
            ["Malformed request."],
            id="detail",
        ),
        pytest.param(
            _status(400, {"color": "Not a valid color.", "match": ["Too long.", "Bad regex."]}),
            {"color": ["Not a valid color."], "match": ["Too long.", "Bad regex."]},
            [],
            id="field-string-and-list",
        ),
        pytest.param(
            _status(400, {"custom_fields": [{"value": ["Enter a valid date."]}]}),
            {"custom_fields": ["value: Enter a valid date."]},
            [],
            id="nested-field-errors",
        ),
        pytest.param(
            _status(400, "Bad things happened."),
            {},
            ["Bad things happened."],
            id="json-string",
        ),
        pytest.param(
            httpx.Response(400, text="Bad Request (plain text)"),
            {},
            ["Bad Request (plain text)"],
            id="non-json",
        ),
    ],
)
async def test_400_body_shapes_are_parsed(
    response: httpx.Response,
    field_errors: dict[str, list[str]],
    non_field_errors: list[str],
) -> None:
    fake = FakePaperless({TAGS_POST: response})
    async with fake.async_client() as client:
        with pytest.raises(BadRequestError) as exc_info:
            await client.tags.create(name="x")
    err = exc_info.value
    assert err.status_code == 400
    assert err.field_errors == field_errors
    assert err.non_field_errors == non_field_errors
    for msg in non_field_errors:
        assert msg in str(err)


async def test_400_empty_body_still_has_message() -> None:
    fake = FakePaperless({TAGS_POST: httpx.Response(400)})
    async with fake.async_client() as client:
        with pytest.raises(BadRequestError) as exc_info:
            await client.tags.create(name="x")
    assert str(exc_info.value)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 5xx responses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [500, 502, 503])
async def test_5xx_raises_server_response_error(code: int) -> None:
    fake = FakePaperless({TAG: httpx.Response(code, text="<html>Bad Gateway</html>")})
    async with fake.async_client() as client:
        with pytest.raises(ServerResponseError) as exc_info:
            await client.tags.get(1)
    err = exc_info.value
    assert isinstance(err, ServerError)
    assert not isinstance(err, TransportError)
    assert err.status_code == code
    assert str(err)


# ---------------------------------------------------------------------------
# Transport errors
# ---------------------------------------------------------------------------

# (httpx exception class, message, expected easypaperless class)
TRANSPORT_FAILURES = [
    pytest.param(httpx.ConnectError, "[Errno 111] Connection refused", TransportError, id="conn"),
    pytest.param(
        httpx.ConnectError, "[Errno -2] Name or service not known", TransportError, id="dns"
    ),
    pytest.param(httpx.ConnectError, "[SSL: CERTIFICATE_VERIFY_FAILED]", TransportError, id="tls"),
    pytest.param(httpx.RemoteProtocolError, "Server disconnected", TransportError, id="protocol"),
    pytest.param(httpx.ReadTimeout, "timed out", TransportTimeoutError, id="read-timeout"),
    pytest.param(httpx.ConnectTimeout, "timed out", TransportTimeoutError, id="connect-timeout"),
]


def _raising(exc_type: type[httpx.TransportError], message: str) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc_type(message, request=request)

    return handler


def _assert_transport_error(
    err: BaseException, expected: type[TransportError], exc_type: type[Exception]
) -> None:
    assert type(err) is expected
    assert isinstance(err, ServerError)
    assert isinstance(err, PaperlessError)
    assert err.status_code is None
    assert isinstance(err.__cause__, exc_type)
    assert str(err)


@pytest.mark.parametrize(("exc_type", "message", "expected"), TRANSPORT_FAILURES)
async def test_transport_error_on_single_request(
    exc_type: type[httpx.TransportError], message: str, expected: type[TransportError]
) -> None:
    fake = FakePaperless({TAG: _raising(exc_type, message)})
    async with fake.async_client() as client:
        with pytest.raises(TransportError) as exc_info:
            await client.tags.get(1)
    _assert_transport_error(exc_info.value, expected, exc_type)


# ---------------------------------------------------------------------------
# Download path (incl. redirects)
# ---------------------------------------------------------------------------

DOWNLOAD = ("GET", "/api/documents/1/download/")
MEDIA = ("GET", "/media/documents/1.pdf")
REDIRECT = httpx.Response(302, headers={"location": "http://media.test/media/documents/1.pdf"})
PDF = httpx.Response(200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"})


@pytest.mark.parametrize(("exc_type", "message", "expected"), TRANSPORT_FAILURES)
async def test_transport_error_on_download(
    exc_type: type[httpx.TransportError], message: str, expected: type[TransportError]
) -> None:
    fake = FakePaperless({DOWNLOAD: _raising(exc_type, message)})
    async with fake.async_client() as client:
        with pytest.raises(TransportError) as exc_info:
            await client.documents.download(1)
    _assert_transport_error(exc_info.value, expected, exc_type)


@pytest.mark.parametrize(("exc_type", "message", "expected"), TRANSPORT_FAILURES)
async def test_transport_error_on_download_redirect_hop(
    exc_type: type[httpx.TransportError], message: str, expected: type[TransportError]
) -> None:
    fake = FakePaperless({DOWNLOAD: REDIRECT, MEDIA: _raising(exc_type, message)})
    async with fake.async_client() as client:
        with pytest.raises(TransportError) as exc_info:
            await client.documents.download(1)
    _assert_transport_error(exc_info.value, expected, exc_type)


async def test_http_errors_on_download_redirect_target_are_classified() -> None:
    fake = FakePaperless({DOWNLOAD: REDIRECT, MEDIA: _status(403, {"detail": "Forbidden."})})
    async with fake.async_client() as client:
        with pytest.raises(PermissionDeniedError) as exc_info:
            await client.documents.download(1)
    assert exc_info.value.status_code == 403


async def test_download_is_retried_on_transient_error() -> None:
    fake = FakePaperless(
        {DOWNLOAD: FakePaperless.seq(_raising(httpx.ConnectError, "refused"), REDIRECT), MEDIA: PDF}
    )
    async with fake.async_client(retry_attempts=1, retry_backoff=0) as client:
        content = await client.documents.download(1)
    assert content == b"%PDF-1.7"


async def test_download_returning_html_page_is_a_server_response_error() -> None:
    login = httpx.Response(200, text="<!DOCTYPE html><html>login</html>")
    fake = FakePaperless({DOWNLOAD: login})
    async with fake.async_client() as client:
        with pytest.raises(ServerResponseError) as exc_info:
            await client.documents.download(1)
    assert exc_info.value.status_code == 200


# ---------------------------------------------------------------------------
# Follow-up pages of paginated lists
# ---------------------------------------------------------------------------


Handler = Callable[[httpx.Request], httpx.Response]


def _paged(path: str, *page2: httpx.Response | Handler) -> Handler:
    """Handler: page 1 links to page 2; page 2 answers with ``page2`` in turn."""
    first = {
        "count": 2,
        "next": f"http://paperless.test{path}?page=2",
        "previous": None,
        "results": [{"id": 1, "name": "acme"}],
    }
    answers = list(page2)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") != "2":
            return httpx.Response(200, json=first)
        value = answers.pop(0) if len(answers) > 1 else answers[0]
        return value if isinstance(value, httpx.Response) else value(request)

    return handler


PAGE2_OK = httpx.Response(
    200, json={"count": 2, "next": None, "previous": None, "results": [{"id": 2, "name": "b"}]}
)


@pytest.mark.parametrize(("exc_type", "message", "expected"), TRANSPORT_FAILURES)
async def test_transport_error_on_follow_up_page_of_list(
    exc_type: type[httpx.TransportError], message: str, expected: type[TransportError]
) -> None:
    fake = FakePaperless({("GET", "/api/tags/"): _paged("/api/tags/", _raising(exc_type, message))})
    async with fake.async_client() as client:
        with pytest.raises(TransportError) as exc_info:
            await client.tags.list()
    _assert_transport_error(exc_info.value, expected, exc_type)


@pytest.mark.parametrize(("exc_type", "message", "expected"), TRANSPORT_FAILURES)
async def test_transport_error_on_follow_up_page_of_name_resolution(
    exc_type: type[httpx.TransportError], message: str, expected: type[TransportError]
) -> None:
    path = "/api/correspondents/"
    fake = FakePaperless({("GET", path): _paged(path, _raising(exc_type, message))})
    async with fake.async_client() as client:
        with pytest.raises(TransportError) as exc_info:
            await client.documents.list(correspondent="acme")
    _assert_transport_error(exc_info.value, expected, exc_type)


async def test_http_error_on_follow_up_page_is_classified() -> None:
    page2 = _status(503, {"detail": "Service unavailable."})
    fake = FakePaperless({("GET", "/api/tags/"): _paged("/api/tags/", page2)})
    async with fake.async_client() as client:
        with pytest.raises(ServerResponseError) as exc_info:
            await client.tags.list()
    assert exc_info.value.status_code == 503
    assert str(exc_info.value) == "Service unavailable."


async def test_follow_up_page_is_retried_on_transient_error() -> None:
    page2 = _paged("/api/tags/", _status(503, {"detail": "busy"}), PAGE2_OK)
    fake = FakePaperless({("GET", "/api/tags/"): page2})
    async with fake.async_client(retry_attempts=1, retry_backoff=0) as client:
        result = await client.tags.list()
    assert [t.id for t in result.results] == [1, 2]


# ---------------------------------------------------------------------------
# Every exception: status_code + non-empty message; retry chaining; sync client
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("response", "expected", "code"),
    [
        pytest.param(_status(404, {"detail": "No Tag matches."}), NotFoundError, 404, id="404"),
        pytest.param(_status(409, {"detail": "Conflict."}), PaperlessError, 409, id="409"),
        pytest.param(httpx.Response(429), PaperlessError, 429, id="429-empty"),
        pytest.param(_status(422, {"name": ["Bad."]}), ValidationError, 422, id="422-fields"),
        pytest.param(httpx.Response(401), AuthenticationError, 401, id="401-empty"),
    ],
)
async def test_every_error_has_status_code_and_message(
    response: httpx.Response, expected: type[PaperlessError], code: int
) -> None:
    fake = FakePaperless({TAG: response})
    async with fake.async_client() as client:
        with pytest.raises(PaperlessError) as exc_info:
            await client.tags.get(1)
    err = exc_info.value
    assert type(err) is expected
    assert err.status_code == code
    assert str(err).strip()


async def test_transport_error_is_retried_by_default_and_chained_when_exhausted() -> None:
    fake = FakePaperless({TAG: _raising(httpx.ConnectError, "[Errno 111] Connection refused")})
    async with fake.async_client(retry_attempts=2, retry_backoff=0) as client:
        with pytest.raises(RetryExhaustedError) as exc_info:
            await client.tags.get(1)
    assert len(fake.requests) == 3
    cause = exc_info.value.__cause__
    assert isinstance(cause, TransportError)
    assert isinstance(cause.__cause__, httpx.ConnectError)


async def test_bad_request_is_not_retried() -> None:
    fake = FakePaperless({TAG: _status(400, {"detail": "nope"})})
    async with fake.async_client(retry_attempts=2, retry_backoff=0) as client:
        with pytest.raises(BadRequestError):
            await client.tags.get(1)
    assert len(fake.requests) == 1


def test_sync_client_raises_the_same_classes() -> None:
    fake = FakePaperless(
        {
            TAG: _status(403, {"detail": "Missing permission: view_tag."}),
            TAGS_POST: _status(400, {"name": ["This field is required."]}),
            DOWNLOAD: _raising(httpx.ReadTimeout, "timed out"),
        }
    )
    with fake.sync_client() as client:
        with pytest.raises(PermissionDeniedError, match="Missing permission: view_tag."):
            client.tags.get(1)
        with pytest.raises(BadRequestError) as bad:
            client.tags.create(name="")
        assert bad.value.field_errors == {"name": ["This field is required."]}
        with pytest.raises(TransportTimeoutError) as timeout:
            client.documents.download(1)
        assert timeout.value.status_code is None
        assert isinstance(timeout.value.__cause__, httpx.ReadTimeout)
