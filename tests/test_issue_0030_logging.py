"""Tests for issue #0030 — structured logging support."""

from __future__ import annotations

import logging

import pytest
import respx
from httpx import Response

from easypaperless._internal.http import HttpSession

BASE_URL = "http://paperless.test"
API_BASE = BASE_URL + "/api"
API_KEY = "secret-token-abc"


@pytest.fixture
async def session():
    s = HttpSession(base_url=BASE_URL, api_token=API_KEY)
    yield s
    await s.close()


# ---------------------------------------------------------------------------
# HTTP layer — DEBUG logging
# ---------------------------------------------------------------------------


async def test_debug_log_emitted_for_outgoing_request(session, caplog):
    """DEBUG message is emitted containing method and path for every request."""
    with caplog.at_level(logging.DEBUG, logger="easypaperless._internal.http"):
        with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
            router.get("/tags/").mock(return_value=Response(200, json={"results": []}))
            await session.get("/tags/")

    assert any("GET" in r.message and "/tags/" in r.message for r in caplog.records)


async def test_debug_log_emitted_for_response(session, caplog):
    """DEBUG message is emitted containing the response status code."""
    with caplog.at_level(logging.DEBUG, logger="easypaperless._internal.http"):
        with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
            router.get("/tags/").mock(return_value=Response(200, json={"results": []}))
            await session.get("/tags/")

    assert any("200" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# HTTP layer — WARNING on error responses
# ---------------------------------------------------------------------------


async def test_warning_logged_on_http_error_response(session, caplog):
    """WARNING is logged when _raise_for_status fires before raising the exception."""
    with caplog.at_level(logging.WARNING, logger="easypaperless._internal.http"):
        with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
            router.get("/tags/").mock(return_value=Response(404, json={"detail": "Not found"}))
            with pytest.raises(Exception):
                await session.get("/tags/")

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "Expected at least one WARNING log record"
    assert any("404" in r.message for r in warnings)


# ---------------------------------------------------------------------------
# Security — auth token must not appear in logs
# ---------------------------------------------------------------------------


async def test_auth_token_not_in_debug_logs(session, caplog):
    """The Authorization token value must never appear in log output."""
    with caplog.at_level(logging.DEBUG, logger="easypaperless"):
        with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
            router.post("/tags/").mock(return_value=Response(201, json={"id": 1}))
            await session.post("/tags/", json={"name": "test"})

    for record in caplog.records:
        assert API_KEY not in record.message, f"API key leaked in log message: {record.message!r}"


# ---------------------------------------------------------------------------
# Library convention — no handlers configured by the library
# ---------------------------------------------------------------------------


def test_easypaperless_logger_has_no_non_null_handlers():
    """The library must not attach real handlers — only a NullHandler is allowed (PEP 282)."""
    import easypaperless  # noqa: F401 — ensure package is imported

    root_logger = logging.getLogger("easypaperless")
    real_handlers = [h for h in root_logger.handlers if not isinstance(h, logging.NullHandler)]
    assert real_handlers == [], (
        "Library must not configure real handlers on the easypaperless logger; "
        f"found: {real_handlers}"
    )


# ---------------------------------------------------------------------------
# Logger hierarchy
# ---------------------------------------------------------------------------


def test_http_module_logger_name():
    """HttpSession's logger is named 'easypaperless._internal.http'."""
    from easypaperless._internal import http as http_module

    assert http_module.logger.name == "easypaperless._internal.http"


# ---------------------------------------------------------------------------
# Resource layer — INFO logging
# ---------------------------------------------------------------------------


async def test_info_log_emitted_by_resource_method(caplog):
    """tags.list() emits an INFO-level log record."""
    from easypaperless.client import PaperlessClient

    paged_data = {"count": 0, "next": None, "previous": None, "all": None, "results": []}

    with caplog.at_level(logging.INFO, logger="easypaperless"):
        with respx.mock(base_url=API_BASE, assert_all_called=False) as router:
            router.get("/tags/").mock(return_value=Response(200, json=paged_data))
            async with PaperlessClient(url=BASE_URL, api_token="key") as client:
                await client.tags.list()

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert info_records, "Expected at least one INFO log record from tags.list()"
