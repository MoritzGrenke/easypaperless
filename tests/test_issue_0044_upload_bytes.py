"""Tests for issue #0044: upload from bytes, filename/content_type, request_timeout, no retry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from email.message import Message
from email.parser import BytesParser
from email.policy import HTTP
from pathlib import Path
from typing import Any

import httpx
import pytest

from easypaperless import (
    RetryExhaustedError,
    TransportError,
    TransportTimeoutError,
    ValidationError,
)
from tests._transport import FakePaperless

UPLOAD = ("POST", "/api/documents/post_document/")


def _document_part(request: httpx.Request) -> Message:
    """Parse the recorded multipart body and return the ``document`` part."""
    raw = (
        b"Content-Type: " + request.headers["content-type"].encode() + b"\r\n\r\n" + request.read()
    )
    message = BytesParser(policy=HTTP).parsebytes(raw)
    for part in message.iter_parts():
        if part.get_param("name", header="content-disposition") == "document":
            return part
    raise AssertionError("no 'document' part in multipart body")


def _upload_fake() -> FakePaperless:
    return FakePaperless({UPLOAD: httpx.Response(200, json="task-123")})


async def test_bytes_upload_sends_filename_and_bytes() -> None:
    fake = _upload_fake()
    async with fake.async_client() as client:
        result = await client.documents.upload(b"%PDF-1.4 data", filename="capture.pdf")

    assert result == "task-123"
    part = _document_part(fake.requests[0])
    assert part.get_filename() == "capture.pdf"
    assert part.get_payload(decode=True) == b"%PDF-1.4 data"


async def test_bytes_upload_without_filename_raises_locally() -> None:
    fake = _upload_fake()
    async with fake.async_client() as client:
        with pytest.raises(ValidationError, match="filename"):
            await client.documents.upload(b"%PDF-1.4 data")

    assert fake.requests == []


async def test_bytes_upload_sends_given_content_type() -> None:
    fake = _upload_fake()
    async with fake.async_client() as client:
        await client.documents.upload(b"data", filename="x.pdf", content_type="application/pdf")

    part = _document_part(fake.requests[0])
    assert part.get_content_type() == "application/pdf"
    assert part.get_filename() == "x.pdf"


async def test_path_upload_filename_overrides_path_name(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF a")
    fake = _upload_fake()
    async with fake.async_client() as client:
        await client.documents.upload(pdf, filename="b.pdf")

    part = _document_part(fake.requests[0])
    assert part.get_filename() == "b.pdf"
    assert part.get_payload(decode=True) == b"%PDF a"


async def test_path_upload_without_new_params_unchanged(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF scan")
    fake = _upload_fake()
    async with fake.async_client() as client:
        result = await client.documents.upload(str(pdf), title="Scan")

    assert result == "task-123"
    part = _document_part(fake.requests[0])
    assert part.get_filename() == "scan.pdf"
    assert part.get_content_type() == "application/pdf"  # guessed from the name, as before
    assert part.get_payload(decode=True) == b"%PDF scan"
    assert b'name="title"' in fake.requests[0].read()


async def test_bytes_upload_writes_no_temporary_file(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    import tempfile

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("temporary file created")

    for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile"):
        monkeypatch.setattr(tempfile, name, _forbidden)
    real_open = builtins.open

    def _guarded_open(file: object, mode: str = "r", *args: object, **kwargs: object) -> object:
        if any(flag in mode for flag in "wax+"):
            raise AssertionError(f"file opened for writing: {file!r}")
        return real_open(file, mode, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(builtins, "open", _guarded_open)

    fake = _upload_fake()
    async with fake.async_client() as client:
        await client.documents.upload(b"%PDF mem", filename="mem.pdf")

    assert _document_part(fake.requests[0]).get_payload(decode=True) == b"%PDF mem"


def _read_timeout(request: httpx.Request) -> object:
    return request.extensions["timeout"]["read"]


async def test_request_timeout_applies_to_upload_only() -> None:
    fake = _upload_fake()
    fake.routes[("GET", "/api/tags/")] = {"count": 0, "next": None, "previous": None, "results": []}
    async with fake.async_client(timeout=30.0) as client:
        await client.documents.upload(b"data", filename="x.pdf", request_timeout=120)
        await client.tags.list()
        await client.documents.upload(b"data", filename="x.pdf")

    upload_with, tags_list, upload_without = fake.requests
    assert _read_timeout(upload_with) == 120
    assert _read_timeout(tags_list) == 30.0
    assert _read_timeout(upload_without) == 30.0


def _raising(exc: Exception) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return handler


_TRANSPORT_FAILURES = [
    pytest.param(httpx.ConnectError("refused"), TransportError, id="connect-error"),
    pytest.param(httpx.ReadTimeout("slow"), TransportTimeoutError, id="read-timeout"),
]


@pytest.mark.parametrize(("failure", "expected"), _TRANSPORT_FAILURES)
async def test_upload_is_not_retried(failure: Exception, expected: type[Exception]) -> None:
    fake = FakePaperless({UPLOAD: _raising(failure)})
    async with fake.async_client(retry_attempts=3, retry_backoff=0) as client:
        with pytest.raises(expected) as info:
            await client.documents.upload(b"data", filename="x.pdf")

    assert not isinstance(info.value, RetryExhaustedError)
    assert len(fake.requests) == 1


def _tenacity_retrying(attempts: int) -> Any:
    tenacity = pytest.importorskip("tenacity")
    return tenacity.AsyncRetrying(
        stop=tenacity.stop_after_attempt(attempts), wait=tenacity.wait_none(), reraise=True
    )


@pytest.mark.parametrize(("failure", "expected"), _TRANSPORT_FAILURES)
async def test_upload_is_not_retried_with_tenacity(
    failure: Exception, expected: type[Exception]
) -> None:
    fake = FakePaperless({UPLOAD: _raising(failure)})
    async with fake.async_client(tenacity_retrying=_tenacity_retrying(4)) as client:
        with pytest.raises(expected):
            await client.documents.upload(b"data", filename="x.pdf")

    assert len(fake.requests) == 1


_EMPTY_TAGS = {"count": 0, "next": None, "previous": None, "results": []}


async def test_get_is_still_retried() -> None:
    fake = FakePaperless(
        {("GET", "/api/tags/"): FakePaperless.seq(_raising(httpx.ConnectError("x")), _EMPTY_TAGS)}
    )
    async with fake.async_client(retry_attempts=3, retry_backoff=0) as client:
        await client.tags.list()

    assert len(fake.requests) == 2


async def test_get_is_still_retried_with_tenacity() -> None:
    fake = FakePaperless(
        {("GET", "/api/tags/"): FakePaperless.seq(_raising(httpx.ConnectError("x")), _EMPTY_TAGS)}
    )
    async with fake.async_client(tenacity_retrying=_tenacity_retrying(4)) as client:
        await client.tags.list()

    assert len(fake.requests) == 2


_CREATE_CALLS = [
    pytest.param("/api/tags/", lambda c: c.tags.create(name="t"), id="tags"),
    pytest.param("/api/correspondents/", lambda c: c.correspondents.create(name="c"), id="corr"),
    pytest.param("/api/document_types/", lambda c: c.document_types.create(name="d"), id="dt"),
    pytest.param("/api/storage_paths/", lambda c: c.storage_paths.create(name="s"), id="sp"),
    pytest.param(
        "/api/custom_fields/",
        lambda c: c.custom_fields.create(name="f", data_type="string"),
        id="cf",
    ),
    pytest.param("/api/users/", lambda c: c.users.create(username="u"), id="users"),
    pytest.param("/api/groups/", lambda c: c.groups.create(name="g"), id="groups"),
    pytest.param(
        "/api/documents/7/notes/", lambda c: c.documents.notes.create(7, note="n"), id="notes"
    ),
]


@pytest.mark.parametrize(("path", "call"), _CREATE_CALLS)
async def test_create_requests_are_not_retried(
    path: str, call: Callable[[Any], Awaitable[Any]]
) -> None:
    fake = FakePaperless({("POST", path): _raising(httpx.ReadTimeout("slow"))})
    async with fake.async_client(retry_attempts=3, retry_backoff=0) as client:
        with pytest.raises(TransportTimeoutError):
            await call(client)

    assert len(fake.requests) == 1


@pytest.mark.parametrize(("path", "call"), _CREATE_CALLS)
async def test_create_requests_are_not_retried_with_tenacity(
    path: str, call: Callable[[Any], Awaitable[Any]]
) -> None:
    fake = FakePaperless({("POST", path): _raising(httpx.ReadTimeout("slow"))})
    async with fake.async_client(tenacity_retrying=_tenacity_retrying(4)) as client:
        with pytest.raises(TransportTimeoutError):
            await call(client)

    assert len(fake.requests) == 1


async def test_bulk_edit_post_is_still_retried() -> None:
    fake = FakePaperless(
        {
            ("POST", "/api/documents/bulk_edit/"): FakePaperless.seq(
                _raising(httpx.ConnectError("x")), {"result": "OK"}
            )
        }
    )
    async with fake.async_client(retry_attempts=3, retry_backoff=0) as client:
        await client.documents.bulk_delete([1])

    assert len(fake.requests) == 2


# ---------------------------------------------------------------------------
# Sync client: same parameters, same behaviour
# ---------------------------------------------------------------------------


def test_sync_bytes_upload_sends_filename_content_type_and_timeout() -> None:
    fake = _upload_fake()
    with fake.sync_client(timeout=30.0) as client:
        result = client.documents.upload(
            b"%PDF sync", filename="s.pdf", content_type="application/pdf", request_timeout=90
        )

    assert result == "task-123"
    part = _document_part(fake.requests[0])
    assert part.get_filename() == "s.pdf"
    assert part.get_content_type() == "application/pdf"
    assert part.get_payload(decode=True) == b"%PDF sync"
    assert _read_timeout(fake.requests[0]) == 90


def test_sync_path_upload_filename_override(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF a")
    fake = _upload_fake()
    with fake.sync_client() as client:
        client.documents.upload(pdf, filename="b.pdf")

    assert _document_part(fake.requests[0]).get_filename() == "b.pdf"


def test_sync_bytes_upload_without_filename_raises_locally() -> None:
    fake = _upload_fake()
    with fake.sync_client() as client:
        with pytest.raises(ValidationError, match="filename"):
            client.documents.upload(b"data")

    assert fake.requests == []


def test_sync_upload_is_not_retried() -> None:
    fake = FakePaperless({UPLOAD: _raising(httpx.ReadTimeout("slow"))})
    with fake.sync_client(retry_attempts=3, retry_backoff=0) as client:
        with pytest.raises(TransportTimeoutError):
            client.documents.upload(b"data", filename="x.pdf")

    assert len(fake.requests) == 1


def test_sync_create_is_not_retried() -> None:
    fake = FakePaperless({("POST", "/api/tags/"): _raising(httpx.ReadTimeout("slow"))})
    with fake.sync_client(retry_attempts=3, retry_backoff=0) as client:
        with pytest.raises(TransportTimeoutError):
            client.tags.create(name="t")

    assert len(fake.requests) == 1
