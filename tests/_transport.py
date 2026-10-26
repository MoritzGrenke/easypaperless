"""Test helper: a fake paperless-ngx server behind an injected ``httpx.MockTransport``.

Use this for new tests instead of respx (see issue #0043). It routes requests by
``(METHOD, path)`` and records every request it receives::

    from tests._transport import FakePaperless

    fake = FakePaperless({("GET", "/api/tags/"): {"count": 0, "next": None,
                                                    "previous": None, "results": []}})
    async with fake.async_client() as client:
        await client.tags.list()
    assert fake.requests[0].url.params == ...

    with fake.sync_client(retry_attempts=1) as client:   # same routes, sync client
        client.tags.list()

Route values (the path is the URL path incl. ``/api`` prefix and trailing slash;
the query string is ignored for matching, inspect ``fake.requests`` instead):

* ``dict`` / ``list`` -> 200 JSON response with that body
* ``httpx.Response``  -> returned as-is
* callable            -> ``handler(request) -> httpx.Response``
* ``Sequence`` wrapper -> ``FakePaperless.seq(r1, r2, ...)`` returns the items one
  per call (each item may be any of the above); the last one repeats. Useful for
  retries and polling.

Unrouted requests get a 404 ``{"detail": "no route for METHOD path"}`` so a test
fails loudly instead of hanging.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from easypaperless import PaperlessClient, SyncPaperlessClient

BASE_URL = "http://paperless.test"
API_TOKEN = "test-token"

Handler = Callable[[httpx.Request], httpx.Response]


class _Seq:
    """Successive responses for one route; the last one repeats."""

    def __init__(self, items: tuple[Any, ...]) -> None:
        self._items = list(items)

    def next(self) -> Any:
        return self._items.pop(0) if len(self._items) > 1 else self._items[0]


class FakePaperless:
    """Route table + request log, exposed as an ``httpx.MockTransport``."""

    def __init__(self, routes: dict[tuple[str, str], Any] | None = None) -> None:
        self.routes: dict[tuple[str, str], Any] = dict(routes or {})
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    @staticmethod
    def seq(*items: Any) -> _Seq:
        """Route value that answers with ``items`` in order (last one repeats)."""
        return _Seq(items)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        value = self.routes.get((request.method, request.url.path))
        if isinstance(value, _Seq):
            value = value.next()
        if value is None:
            detail = f"no route for {request.method} {request.url.path}"
            return httpx.Response(404, json={"detail": detail})
        if isinstance(value, httpx.Response):
            return value
        if callable(value):
            response: httpx.Response = value(request)
            return response
        return httpx.Response(200, json=value)

    def async_client(self, **kwargs: Any) -> PaperlessClient:
        """A ``PaperlessClient`` wired to this fake; kwargs go to the constructor."""
        return PaperlessClient(
            url=BASE_URL, api_token=API_TOKEN, transport=self.transport, **kwargs
        )

    def sync_client(self, **kwargs: Any) -> SyncPaperlessClient:
        """A ``SyncPaperlessClient`` wired to this fake; close it (use ``with``)."""
        return SyncPaperlessClient(
            url=BASE_URL, api_token=API_TOKEN, transport=self.transport, **kwargs
        )
