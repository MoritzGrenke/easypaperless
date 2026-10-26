"""Tests for the injectable HTTP transport (issue #0043)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from easypaperless import PaperlessClient
from easypaperless.exceptions import NotFoundError
from tests._transport import FakePaperless

BASE_URL = "http://paperless.test"
API_TOKEN = "test-token"
TAG_LIST = {"count": 1, "next": None, "previous": None, "results": [{"id": 1, "name": "inbox"}]}


async def test_async_client_routes_requests_through_injected_transport() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=TAG_LIST)

    async with PaperlessClient(
        url=BASE_URL, api_token=API_TOKEN, transport=httpx.MockTransport(handler)
    ) as client:
        result = await client.tags.list()

    assert [t.name for t in result.results] == ["inbox"]
    assert len(seen) == 1
    assert seen[0].url.path == "/api/tags/"
    assert seen[0].headers["Authorization"] == "Token test-token"


async def test_injected_transport_keeps_configured_timeout() -> None:
    fake = FakePaperless({("GET", "/api/tags/"): TAG_LIST})

    async with fake.async_client(timeout=12.5) as client:
        await client.tags.list()

    assert fake.requests[0].extensions["timeout"]["read"] == 12.5


async def test_retry_configuration_applies_with_injected_transport() -> None:
    fake = FakePaperless({("GET", "/api/tags/"): FakePaperless.seq(httpx.Response(503), TAG_LIST)})

    async with fake.async_client(retry_attempts=1, retry_backoff=0.0) as client:
        result = await client.tags.list()

    assert result.count == 1
    assert len(fake.requests) == 2


def test_sync_client_routes_requests_through_injected_transport() -> None:
    fake = FakePaperless({("GET", "/api/tags/"): TAG_LIST})

    with fake.sync_client() as client:
        result = client.tags.list()

    assert [t.name for t in result.results] == ["inbox"]
    assert len(fake.requests) == 1
    assert fake.requests[0].headers["Authorization"] == "Token test-token"
    assert str(fake.requests[0].url).startswith(BASE_URL + "/api/tags/")


async def test_sync_client_works_from_worker_thread_while_main_loop_runs() -> None:
    # This test body runs inside a running asyncio loop (pytest-asyncio).
    fake = FakePaperless({("GET", "/api/tags/"): TAG_LIST})

    def worker() -> int:
        with fake.sync_client() as client:
            return client.tags.list().count

    assert asyncio.get_running_loop().is_running()
    count = await asyncio.to_thread(worker)

    assert count == 1


def test_sync_close_stops_loop_thread_and_is_idempotent() -> None:
    fake = FakePaperless({("GET", "/api/tags/"): TAG_LIST})
    client = fake.sync_client()
    client.tags.list()
    thread = client._thread

    client.close()
    client.close()

    assert not thread.is_alive()


async def test_helper_answers_unrouted_requests_with_404() -> None:
    fake = FakePaperless()

    async with fake.async_client() as client:
        with pytest.raises(NotFoundError, match="no route for GET /api/tags/"):
            await client.tags.list()
