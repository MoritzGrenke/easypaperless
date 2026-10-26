"""HTTP session with auth, error mapping, and pagination."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from easypaperless._internal import errors
from easypaperless.exceptions import (
    RetryExhaustedError,
    ServerError,
)

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_ON: tuple[type[Exception], ...] = (
    ServerError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


# Request-body keys whose values are never written to the log (#0047).
_SECRET_KEYS = frozenset({"password"})
_MASK = "***"


def _mask_secrets(value: Any) -> Any:
    """Return a copy of *value* with secret fields replaced by ``"***"``.

    Walks dicts and lists recursively; the original object (which is sent to
    the server) is left untouched. Only used for DEBUG logging.
    """
    if isinstance(value, dict):
        return {
            key: _MASK if str(key).lower() in _SECRET_KEYS else _mask_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [_mask_secrets(item) for item in value]
    return value


@dataclass
class _PagedRaw:
    """Internal container for a raw paged API response."""

    count: int
    next: str | None
    previous: str | None
    all_ids: list[int] | None
    items: list[dict[str, Any]]
    # ``False`` when the endpoint answered with a plain JSON array (no envelope).
    paginated: bool = True


class HttpSession:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: float = 30.0,
        *,
        retry_attempts: int = 0,
        retry_backoff: float = 1.0,
        retry_on: tuple[type[Exception], ...] | None = None,
        tenacity_retrying: Any = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # Normalize: strip trailing slash, then append /api
        self._base_url = base_url.rstrip("/") + "/api"
        self._api_token = api_token
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._retry_attempts = retry_attempts
        self._retry_backoff = retry_backoff
        self._retry_on: tuple[type[Exception], ...] = (
            retry_on if retry_on is not None else _DEFAULT_RETRY_ON
        )
        self._tenacity_retrying = tenacity_retrying
        self._transport = transport

    def __repr__(self) -> str:
        # Never include the API token (#0047).
        return f"{type(self).__name__}(base_url={self._base_url!r})"

    @property
    def base_url(self) -> str:
        """The API root URL, e.g. ``"http://localhost:8000/api"``."""
        return self._base_url

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                # No default "Accept: application/json": server_version() relies
                # on GET /api/ -> HTML schema view, which would then answer 406.
                headers={"Authorization": f"Token {self._api_token}"},
                timeout=self._timeout,
                follow_redirects=True,
                transport=self._transport,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send one request; the only place that calls the httpx client.

        Every ``httpx.HTTPError`` is translated by
        :func:`~easypaperless._internal.errors.map_transport_error`, so all
        request paths raise the same ``TransportError`` subclasses.
        """
        try:
            return await self._get_client().request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise errors.map_transport_error(exc, method, url) from exc

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: Any = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Execute a single HTTP request attempt (no retry logic)."""
        response = await self._send(
            method,
            path,
            params=params,
            json=json,
            data=data,
            files=files,
            # ``None`` means "no timeout" to httpx; fall back to the client default.
            timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
        )
        if logger.isEnabledFor(logging.DEBUG):
            body = response.text
            if len(body) > 1000:
                body = body[:1000] + "...<truncated>"
            logger.debug("%s %s %s response=%s", response.status_code, method.upper(), path, body)
        errors.raise_for_status(response, method, path)
        return response

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: Any = None,
        timeout: float | None = None,
        retry: bool = True,
    ) -> httpx.Response:
        """Send a request under the retry policy.

        ``retry=False`` sends exactly one attempt regardless of the client's
        retry configuration (built-in loop and ``tenacity_retrying``).  Used for
        requests that create something, where a retry after a lost response
        could create a duplicate (#0044).
        """
        if logger.isEnabledFor(logging.DEBUG):
            if json is not None:
                logger.debug("%s %s body=%s", method.upper(), path, _mask_secrets(json))
            elif data is not None:
                logger.debug("%s %s data=%s", method.upper(), path, _mask_secrets(data))
            elif files is not None:
                logger.debug("%s %s <multipart/form-data>", method.upper(), path)
            else:
                logger.debug("%s %s", method.upper(), path)

        return await self._retrying(
            method,
            path,
            lambda: self._do_request(
                method, path, params=params, json=json, data=data, files=files, timeout=timeout
            ),
            retry=retry,
        )

    async def _retrying(
        self,
        method: str,
        path: str,
        attempt_fn: Callable[[], Awaitable[httpx.Response]],
        *,
        retry: bool = True,
    ) -> httpx.Response:
        """Run *attempt_fn* under the configured retry policy.

        Shared by every request path (single requests, downloads and follow-up
        pages) so they all retry the same way.  With ``retry=False`` the
        attempt runs exactly once and any error propagates unchanged.
        """
        if not retry:
            return await attempt_fn()

        # tenacity-based retry path
        if self._tenacity_retrying is not None:
            async for attempt in self._tenacity_retrying:
                with attempt:
                    result = await attempt_fn()
            return result  # noqa: F821

        # built-in retry path
        backoff = self._retry_backoff
        total_attempts = self._retry_attempts + 1
        for attempt in range(1, total_attempts + 1):
            try:
                return await attempt_fn()
            except Exception as exc:
                if not isinstance(exc, self._retry_on):
                    raise
                if attempt == total_attempts:
                    if self._retry_attempts == 0:
                        raise
                    raise RetryExhaustedError(
                        f"All {self._retry_attempts} retry attempt(s) exhausted for "
                        f"{method.upper()} {path}",
                        attempts=total_attempts,
                        url=path,
                    ) from exc
                logger.debug(
                    "Retry %d/%d for %s %s after %s (backoff=%.1fs)",
                    attempt,
                    self._retry_attempts,
                    method.upper(),
                    path,
                    type(exc).__name__,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff *= 2

        raise AssertionError("unreachable")  # pragma: no cover

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        return await self.request("GET", path, params=params)

    async def get_download(self, path: str) -> httpx.Response:
        """GET for binary downloads with auth-preserving redirect handling.

        httpx strips the Authorization header when following redirects to a
        different host (a security default).  Download endpoints commonly
        redirect to a media URL served by nginx, which still needs the token.
        This method follows each redirect hop as a *fresh* request so the
        client's default Authorization header is always re-attached.

        The whole redirect chain counts as one attempt of the retry policy.
        """
        logger.debug("GET (download) %s", path)
        return await self._retrying("GET", path, lambda: self._download_once(path))

    async def _download_once(self, path: str) -> httpx.Response:
        """One download attempt: initial GET plus up to five redirect hops."""
        resp = await self._send("GET", path, follow_redirects=False)
        hops = 0
        while resp.is_redirect and hops < 5:
            location = resp.headers["location"]
            logger.debug("Redirect %d -> %s", resp.status_code, location)
            resp = await self._send("GET", location, follow_redirects=False)
            hops += 1

        logger.debug("%d GET %s", resp.status_code, path)
        errors.raise_for_status(resp, "GET", path)
        return resp

    async def post(
        self,
        path: str,
        *,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: Any = None,
        timeout: float | None = None,
        retry: bool = True,
    ) -> httpx.Response:
        return await self.request(
            "POST", path, json=json, data=data, files=files, timeout=timeout, retry=retry
        )

    async def patch(self, path: str, *, json: Any = None) -> httpx.Response:
        return await self.request("PATCH", path, json=json)

    async def delete(self, path: str, *, params: dict[str, Any] | None = None) -> httpx.Response:
        return await self.request("DELETE", path, params=params)

    def _normalise_next_url(self, next_url: str) -> str:
        """Return *next_url* with its scheme replaced by the one in *base_url*.

        When paperless-ngx runs behind a TLS-terminating reverse proxy that
        does not forward ``X-Forwarded-Proto: https``, Django returns
        pagination ``next`` URLs with an ``http://`` scheme even though the
        client configured an ``https://`` base URL.  Following those URLs
        verbatim causes the proxy to reject the request.  This method
        normalises the scheme so every page request uses the same scheme as
        the configured base URL.
        """
        base_scheme = urllib.parse.urlparse(self._base_url).scheme
        parsed = urllib.parse.urlparse(next_url)
        if parsed.scheme == base_scheme:
            return next_url
        return parsed._replace(scheme=base_scheme).geturl()

    async def get_all_pages(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_results: int | None = None,
        on_page: Callable[[int, int | None], None] | None = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        # First page — use path relative to base_url
        if params:
            logger.debug("Fetching %s (params=%s)", path, params)
        else:
            logger.debug("Fetching %s", path)
        response = await self.get(path, params=params)
        page = response.json()
        total_count: int | None = page.get("count")
        results.extend(page.get("results", []))
        if on_page is not None:
            on_page(len(results), total_count)

        if max_results is not None and len(results) >= max_results:
            logger.debug("max_results=%d reached after first page", max_results)
            return results[:max_results]

        next_url: str | None = page.get("next")
        while next_url:
            next_url = self._normalise_next_url(next_url)
            logger.debug("Fetching next page: %s", next_url)
            # next is absolute; httpx uses it as-is instead of joining base_url
            response = await self.get(next_url)
            page = response.json()
            results.extend(page.get("results", []))
            if on_page is not None:
                on_page(len(results), total_count)
            next_url = page.get("next")

            if max_results is not None and len(results) >= max_results:
                logger.debug("max_results=%d reached", max_results)
                break

        if max_results is not None:
            results = results[:max_results]

        logger.debug("Pagination complete: %d items from %s", len(results), path)
        return results

    async def get_page(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> _PagedRaw:
        """Fetch a single page and return full pagination metadata.

        Args:
            path: API path relative to the base URL.
            params: Optional query parameters including ``page``.

        Returns:
            A :class:`_PagedRaw` with ``count``, ``next``, ``previous``,
            ``all_ids``, and ``items`` from the API response.
        """
        resp = await self.get(path, params=params)
        page = resp.json()
        return _PagedRaw(
            count=page.get("count", 0),
            next=page.get("next"),
            previous=page.get("previous"),
            all_ids=page.get("all"),
            items=page.get("results", []),
        )

    async def get_all_pages_paged(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_results: int | None = None,
        on_page: Callable[[int, int | None], None] | None = None,
    ) -> _PagedRaw:
        """Fetch all pages and return items with first-page pagination metadata.

        ``next`` and ``previous`` in the returned :class:`_PagedRaw` are
        always ``None`` — they are meaningless once pagination has been fully
        consumed by the library.  ``count`` and ``all_ids`` come from the
        first page response.

        Args:
            path: API path relative to the base URL.
            params: Optional query parameters (must *not* include ``page``).
            max_results: Stop after collecting this many items.
            on_page: Callback invoked after each page fetch with
                ``(fetched_so_far, total_count)``.

        Returns:
            A :class:`_PagedRaw` with all collected items and first-page
            metadata.
        """
        if params:
            logger.debug("Fetching %s (params=%s)", path, params)
        else:
            logger.debug("Fetching %s", path)
        response = await self.get(path, params=params)
        return await self._collect_pages(
            path, response.json(), max_results=max_results, on_page=on_page
        )

    async def get_list(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        all_pages: bool = True,
    ) -> _PagedRaw:
        """Fetch a list endpoint that returns a plain JSON array *or* a paginated envelope.

        Some paperless-ngx endpoints (notes, tasks) answer with a plain JSON
        array; a paginated dict is accepted as well.  A plain array is
        returned as one page with ``paginated=False``, ``count`` set to its
        length and no ``next`` / ``previous`` / ``all_ids``.  A paginated dict
        is handled like :meth:`get_all_pages_paged` when *all_pages* is
        ``True``, or like :meth:`get_page` otherwise.

        Args:
            path: API path relative to the base URL.
            params: Optional query parameters.
            all_pages: Follow the ``next`` links of a paginated response.

        Returns:
            A :class:`_PagedRaw` with the collected items.
        """
        logger.debug("Fetching %s (params=%s)", path, params)
        data = (await self.get(path, params=params)).json()
        if isinstance(data, list):
            return _PagedRaw(len(data), None, None, None, data, paginated=False)
        if not isinstance(data, dict):
            return _PagedRaw(0, None, None, None, [], paginated=False)
        if not all_pages:
            return _PagedRaw(
                count=data.get("count", 0),
                next=data.get("next"),
                previous=data.get("previous"),
                all_ids=data.get("all"),
                items=data.get("results", []),
            )
        return await self._collect_pages(path, data)

    async def _collect_pages(
        self,
        path: str,
        page: dict[str, Any],
        *,
        max_results: int | None = None,
        on_page: Callable[[int, int | None], None] | None = None,
    ) -> _PagedRaw:
        """Collect the items of *page* and of every page linked via ``next``.

        ``next`` / ``previous`` of the result are ``None``; ``count`` and
        ``all_ids`` come from *page*.
        """
        results: list[dict[str, Any]] = []
        total_count: int = page.get("count", 0)
        all_ids: list[int] | None = page.get("all")
        results.extend(page.get("results", []))
        if on_page is not None:
            on_page(len(results), total_count)

        if max_results is not None and len(results) >= max_results:
            logger.debug("max_results=%d reached after first page", max_results)
            return _PagedRaw(total_count, None, None, all_ids, results[:max_results])

        next_url: str | None = page.get("next")
        while next_url:
            next_url = self._normalise_next_url(next_url)
            logger.debug("Fetching next page: %s", next_url)
            # next is absolute; httpx uses it as-is instead of joining base_url
            response = await self.get(next_url)
            page = response.json()
            results.extend(page.get("results", []))
            if on_page is not None:
                on_page(len(results), total_count)
            next_url = page.get("next")

            if max_results is not None and len(results) >= max_results:
                logger.debug("max_results=%d reached", max_results)
                break

        if max_results is not None:
            results = results[:max_results]

        logger.debug("Pagination complete: %d items from %s", len(results), path)
        return _PagedRaw(total_count, None, None, all_ids, results)
