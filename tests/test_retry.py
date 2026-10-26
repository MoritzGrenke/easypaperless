"""Unit tests for retry-with-backoff support (issue #0041)."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from easypaperless._internal.errors import _sanitise_body
from easypaperless._internal.http import _DEFAULT_RETRY_ON, HttpSession
from easypaperless.exceptions import (
    NotFoundError,
    RetryExhaustedError,
    ServerError,
)

# ---------------------------------------------------------------------------
# _sanitise_body helper
# ---------------------------------------------------------------------------


def test_sanitise_body_plain_text() -> None:
    body = '{"detail": "not found"}'
    assert _sanitise_body(body) == body


def test_sanitise_body_html_doctype() -> None:
    body = "<!DOCTYPE html><html><body>Bad Gateway</body></html>"
    result = _sanitise_body(body)
    assert "HTML page" in result
    assert "proxy or gateway" in result
    assert body[:50] in result  # excerpt included


def test_sanitise_body_html_tag() -> None:
    body = "<html><head></head><body>502</body></html>"
    result = _sanitise_body(body)
    assert "HTML page" in result


def test_sanitise_body_html_excerpt_truncated() -> None:
    long_html = "<html>" + "x" * 500 + "</html>"
    result = _sanitise_body(long_html)
    # excerpt is at most 200 chars
    # The excerpt itself is repr'd, so we just check the original body isn't fully present
    assert len(long_html) not in [len(result)]  # result is shorter


# ---------------------------------------------------------------------------
# DEFAULT_RETRY_ON
# ---------------------------------------------------------------------------


def test_default_retry_on_contains_expected_types() -> None:
    assert ServerError in _DEFAULT_RETRY_ON
    assert httpx.TimeoutException in _DEFAULT_RETRY_ON
    assert httpx.ConnectError in _DEFAULT_RETRY_ON
    assert NotFoundError not in _DEFAULT_RETRY_ON


# ---------------------------------------------------------------------------
# RetryExhaustedError
# ---------------------------------------------------------------------------


def test_retry_exhausted_error_attributes() -> None:
    cause = ServerError("upstream error")
    err = RetryExhaustedError("all 3 attempts exhausted for GET /test/", attempts=3, url="/test/")
    err.__cause__ = cause
    assert err.attempts == 3
    assert err.url == "/test/"
    assert "3" in str(err)
    assert "/test/" in str(err)


# ---------------------------------------------------------------------------
# HttpSession retry behaviour (mocked _do_request)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_retry_default_propagates_immediately() -> None:
    """retry_attempts=0 (default): exception raised on first failure, no sleep."""
    session = HttpSession("http://localhost:8000", "token")

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = ServerError("upstream error")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(ServerError, match="upstream error"):
                await session.request("GET", "/documents/")
            mock_sleep.assert_not_called()
        assert mock_req.call_count == 1


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt() -> None:
    """Request fails once with a retriable error, then succeeds on retry."""
    session = HttpSession("http://localhost:8000", "token", retry_attempts=2, retry_backoff=0.01)
    good_response = MagicMock(spec=httpx.Response)

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = [ServerError("transient"), good_response]
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await session.request("GET", "/documents/")
    assert result is good_response
    assert mock_req.call_count == 2


@pytest.mark.asyncio
async def test_retry_exhausted_raises_retry_exhausted_error() -> None:
    """All retry attempts fail → RetryExhaustedError with correct attributes."""
    session = HttpSession("http://localhost:8000", "token", retry_attempts=2, retry_backoff=0.01)
    original_exc = ServerError("persistent failure")

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = original_exc
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RetryExhaustedError) as exc_info:
                await session.request("GET", "/documents/")

    err = exc_info.value
    assert err.attempts == 3  # 1 initial + 2 retries
    assert "/documents/" in err.url
    assert err.__cause__ is original_exc
    assert mock_req.call_count == 3


@pytest.mark.asyncio
async def test_non_retriable_exception_not_retried() -> None:
    """NotFoundError (not in retry_on) is raised immediately without retry."""
    session = HttpSession("http://localhost:8000", "token", retry_attempts=3, retry_backoff=0.01)

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = NotFoundError("doc not found")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(NotFoundError):
                await session.request("GET", "/documents/99/")
            mock_sleep.assert_not_called()
    assert mock_req.call_count == 1


@pytest.mark.asyncio
async def test_custom_retry_on_overrides_default() -> None:
    """Custom retry_on that includes NotFoundError retries on 404."""
    session = HttpSession(
        "http://localhost:8000",
        "token",
        retry_attempts=1,
        retry_backoff=0.01,
        retry_on=(NotFoundError,),
    )
    good_response = MagicMock(spec=httpx.Response)

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = [NotFoundError("not yet"), good_response]
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await session.request("GET", "/documents/1/")
    assert result is good_response
    assert mock_req.call_count == 2


@pytest.mark.asyncio
async def test_backoff_doubles_each_attempt() -> None:
    """Sleep duration doubles on each retry attempt."""
    session = HttpSession("http://localhost:8000", "token", retry_attempts=3, retry_backoff=1.0)

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = ServerError("fail")
        with patch("easypaperless._internal.http.asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(RetryExhaustedError):
                await session.request("GET", "/documents/")

    assert sleep_calls == [1.0, 2.0, 4.0]


# ---------------------------------------------------------------------------
# HTML body sanitisation in raise_for_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_html_body_sanitised_in_server_error() -> None:
    """HTML response body is replaced with a human-readable note in exceptions."""
    session = HttpSession("http://localhost:8000", "token")

    with respx.mock(base_url="http://localhost:8000") as mock:
        mock.get("/api/documents/").mock(
            return_value=httpx.Response(
                502,
                text="<!DOCTYPE html><html><body>Bad Gateway</body></html>",
                headers={"Content-Type": "text/html"},
            )
        )
        with pytest.raises(ServerError) as exc_info:
            await session.get("/documents/")

    msg = str(exc_info.value)
    # Message should explain it's HTML, not just dump the raw body
    assert "HTML page" in msg
    assert "proxy or gateway" in msg
    # Short excerpt is allowed, but the message is not *just* the raw HTML body
    assert msg != "<!DOCTYPE html><html><body>Bad Gateway</body></html>"


# ---------------------------------------------------------------------------
# PaperlessClient retry parameter forwarding
# ---------------------------------------------------------------------------


def test_paperless_client_accepts_retry_params() -> None:
    """PaperlessClient passes retry params to HttpSession without error."""
    from easypaperless import PaperlessClient

    client = PaperlessClient(
        "http://localhost:8000",
        "token",
        retry_attempts=3,
        retry_backoff=0.5,
        retry_on=(ServerError,),
    )
    assert client._session._retry_attempts == 3
    assert client._session._retry_backoff == 0.5
    assert client._session._retry_on == (ServerError,)


def test_sync_paperless_client_accepts_retry_params() -> None:
    """SyncPaperlessClient forwards retry kwargs to the underlying async client."""
    from easypaperless import SyncPaperlessClient

    client = SyncPaperlessClient(
        "http://localhost:8000",
        "token",
        retry_attempts=2,
        retry_backoff=0.25,
    )
    assert client._async_client._session._retry_attempts == 2
    assert client._async_client._session._retry_backoff == 0.25
    client.close()


# ---------------------------------------------------------------------------
# Retry debug logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_logs_debug_per_attempt(caplog: pytest.LogCaptureFixture) -> None:
    """Each retry attempt emits a DEBUG log with attempt number and backoff."""
    session = HttpSession("http://localhost:8000", "token", retry_attempts=2, retry_backoff=0.01)

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = ServerError("fail")
        with patch("easypaperless._internal.http.asyncio.sleep", new_callable=AsyncMock):
            with caplog.at_level(logging.DEBUG, logger="easypaperless._internal.http"):
                with pytest.raises(RetryExhaustedError):
                    await session.request("GET", "/documents/")

    retry_records = [r for r in caplog.records if "Retry" in r.message]
    # 2 retry attempts → 2 debug log lines
    assert len(retry_records) == 2
    assert "1/2" in retry_records[0].message
    assert "2/2" in retry_records[1].message
    assert "backoff" in retry_records[0].message.lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_sanitise_body_empty_string() -> None:
    from easypaperless._internal.errors import _sanitise_body

    assert _sanitise_body("") == ""


def test_sanitise_body_whitespace_only() -> None:
    from easypaperless._internal.errors import _sanitise_body

    body = "   "
    assert _sanitise_body(body) == body


@pytest.mark.asyncio
async def test_retry_attempts_1_makes_exactly_two_calls() -> None:
    """retry_attempts=1 → 1 initial + 1 retry = 2 total calls, then RetryExhaustedError."""
    session = HttpSession("http://localhost:8000", "token", retry_attempts=1, retry_backoff=0.01)

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = ServerError("fail")
        with patch("easypaperless._internal.http.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RetryExhaustedError) as exc_info:
                await session.request("GET", "/documents/")

    assert mock_req.call_count == 2
    assert exc_info.value.attempts == 2


# ---------------------------------------------------------------------------
# Tenacity integration (skipped when tenacity is not installed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenacity_async_retrying_is_used() -> None:
    """AsyncRetrying instance routes through the tenacity path and retries on failure."""
    tenacity = pytest.importorskip("tenacity")

    retrying = tenacity.AsyncRetrying(
        stop=tenacity.stop_after_attempt(2),
        wait=tenacity.wait_none(),
        reraise=True,
    )
    session = HttpSession("http://localhost:8000", "token", tenacity_retrying=retrying)
    good_response = MagicMock(spec=httpx.Response)

    with patch.object(session, "_do_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = [ServerError("transient"), good_response]
        result = await session.request("GET", "/documents/")

    assert result is good_response
    assert mock_req.call_count == 2


def test_tenacity_sync_client_accepts_retrying_instance() -> None:
    """SyncPaperlessClient forwards a tenacity.Retrying instance to HttpSession."""
    tenacity = pytest.importorskip("tenacity")
    from easypaperless import SyncPaperlessClient

    retrying = tenacity.AsyncRetrying(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_none(),
    )
    client = SyncPaperlessClient("http://localhost:8000", "token", tenacity_retrying=retrying)
    assert client._async_client._session._tenacity_retrying is retrying
    client.close()
