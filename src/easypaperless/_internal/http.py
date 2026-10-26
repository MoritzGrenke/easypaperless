"""HTTP session with auth, error mapping, and pagination."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from easypaperless.exceptions import (
    AuthError,
    NotFoundError,
    PaperlessError,
    RetryExhaustedError,
    ServerError,
    ValidationError,
)

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_ON: tuple[type[Exception], ...] = (
    ServerError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


@dataclass
class _PagedRaw:
    """Internal container for a raw paged API response."""

    count: int
    next: str | None
    previous: str | None
    all_ids: list[int] | None
    items: list[dict[str, Any]]


def _sanitise_body(body: str) -> str:
    """Return a safe representation of a response body.

    If the body looks like HTML, replaces it with a human-readable note and
    a short excerpt to avoid flooding logs or exception messages with raw HTML.
    """
    stripped = body.lstrip()
    if stripped.lower().startswith("<!") or stripped.lower().startswith("<html"):
        excerpt = body[:200]
        return (
            "response body appears to be an HTML page — this may indicate a "
            f"proxy or gateway error. Excerpt: {excerpt!r}"
        )
    return body


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

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Token {self._api_token}"},
                timeout=self._timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _raise_for_status(self, response: httpx.Response, method: str, path: str) -> None:
        if response.is_success:
            return
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = _sanitise_body(response.text)

        status = response.status_code
        logger.warning("HTTP %s on %s %s — %s", status, method.upper(), path, detail)
        if status in (401, 403):
            raise AuthError(detail, status_code=status)
        elif status == 404:
            raise NotFoundError(detail, status_code=status)
        elif status == 422:
            raise ValidationError(detail, status_code=status)
        elif status >= 500:
            raise ServerError(detail, status_code=status)
        else:
            raise PaperlessError(detail, status_code=status)

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
        client = self._get_client()
        try:
            response = await client.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                files=files,
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise ServerError(
                f"Request timed out ({method.upper()} {path}). "
                "The operation may have completed on the server despite this error."
            ) from exc
        except httpx.HTTPError as exc:
            msg = str(exc) or f"HTTP error on {method.upper()} {path}"
            raise ServerError(msg) from exc
        if logger.isEnabledFor(logging.DEBUG):
            body = response.text
            if len(body) > 1000:
                body = body[:1000] + "...<truncated>"
            logger.debug("%s %s %s response=%s", response.status_code, method.upper(), path, body)
        self._raise_for_status(response, method, path)
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
    ) -> httpx.Response:
        if logger.isEnabledFor(logging.DEBUG):
            if json is not None:
                logger.debug("%s %s body=%s", method.upper(), path, json)
            elif data is not None:
                logger.debug("%s %s data=%s", method.upper(), path, data)
            elif files is not None:
                logger.debug("%s %s <multipart/form-data>", method.upper(), path)
            else:
                logger.debug("%s %s", method.upper(), path)

        # tenacity-based retry path
        if self._tenacity_retrying is not None:
            async for attempt in self._tenacity_retrying:
                with attempt:
                    result = await self._do_request(
                        method,
                        path,
                        params=params,
                        json=json,
                        data=data,
                        files=files,
                        timeout=timeout,
                    )
            return result  # noqa: F821

        # built-in retry path
        backoff = self._retry_backoff
        total_attempts = self._retry_attempts + 1
        for attempt in range(1, total_attempts + 1):
            try:
                return await self._do_request(
                    method, path, params=params, json=json, data=data, files=files, timeout=timeout
                )
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
        """
        client = self._get_client()
        logger.debug("GET (download) %s", path)
        try:
            resp = await client.request("GET", path, follow_redirects=False)
        except httpx.TimeoutException as exc:
            raise ServerError(f"Request timed out (GET {path})") from exc
        except httpx.HTTPError as exc:
            raise ServerError(str(exc) or f"HTTP error on GET {path}") from exc

        hops = 0
        while resp.is_redirect and hops < 5:
            location = resp.headers["location"]
            logger.debug("Redirect %d -> %s", resp.status_code, location)
            try:
                resp = await client.request("GET", location, follow_redirects=False)
            except httpx.TimeoutException as exc:
                raise ServerError(f"Request timed out (GET {location})") from exc
            except httpx.HTTPError as exc:
                raise ServerError(str(exc) or f"HTTP error on GET {location}") from exc
            hops += 1

        logger.debug("%d GET %s", resp.status_code, path)
        self._raise_for_status(resp, "GET", path)
        return resp

    async def post(
        self,
        path: str,
        *,
        json: Any = None,
        data: dict[str, Any] | None = None,
        files: Any = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        return await self.request("POST", path, json=json, data=data, files=files, timeout=timeout)

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
            # next is absolute; pass it directly to the client
            client = self._get_client()
            try:
                response = await client.get(next_url)
            except httpx.TimeoutException as exc:
                raise ServerError(f"Request timed out (GET {next_url})") from exc
            except httpx.HTTPError as exc:
                raise ServerError(str(exc) or f"HTTP error on GET {next_url}") from exc
            self._raise_for_status(response, "GET", next_url)
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
        results: list[dict[str, Any]] = []
        if params:
            logger.debug("Fetching %s (params=%s)", path, params)
        else:
            logger.debug("Fetching %s", path)
        response = await self.get(path, params=params)
        page = response.json()
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
            client = self._get_client()
            try:
                response = await client.get(next_url)
            except httpx.TimeoutException as exc:
                raise ServerError(f"Request timed out (GET {next_url})") from exc
            except httpx.HTTPError as exc:
                raise ServerError(str(exc) or f"HTTP error on GET {next_url}") from exc
            self._raise_for_status(response, "GET", next_url)
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
