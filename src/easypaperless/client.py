"""Async PaperlessClient — the primary public interface."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from easypaperless._internal.http import HttpSession
from easypaperless._internal.resolvers import NameResolver
from easypaperless._internal.resources.correspondents import CorrespondentsResource
from easypaperless._internal.resources.custom_fields import CustomFieldsResource
from easypaperless._internal.resources.document_types import DocumentTypesResource
from easypaperless._internal.resources.documents import DocumentsResource
from easypaperless._internal.resources.groups import GroupsResource
from easypaperless._internal.resources.storage_paths import StoragePathsResource
from easypaperless._internal.resources.tags import TagsResource
from easypaperless._internal.resources.trash import TrashResource
from easypaperless._internal.resources.users import UsersResource
from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.exceptions import NotFoundError, NotPaperlessError
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.permissions import SetPermissions
from easypaperless.models.system_status import SystemStatus

logger = logging.getLogger(__name__)


class _ClientCore:
    """Base class: constructor, context manager, and internal CRUD helpers."""

    documents: DocumentsResource
    tags: TagsResource
    correspondents: CorrespondentsResource
    document_types: DocumentTypesResource
    storage_paths: StoragePathsResource
    custom_fields: CustomFieldsResource
    users: UsersResource
    groups: GroupsResource
    trash: TrashResource

    def __init__(
        self,
        url: str,
        api_token: str,
        *,
        timeout: float = 30.0,
        poll_interval: float = 2.0,
        poll_timeout: float = 60.0,
        retry_attempts: int = 0,
        retry_backoff: float = 1.0,
        retry_on: tuple[type[Exception], ...] | None = None,
        tenacity_retrying: Any = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._session = HttpSession(
            base_url=url,
            api_token=api_token,
            timeout=timeout,
            retry_attempts=retry_attempts,
            retry_backoff=retry_backoff,
            retry_on=retry_on,
            tenacity_retrying=tenacity_retrying,
            transport=transport,
        )
        self._resolver = NameResolver(self._session)
        self._poll_interval = poll_interval
        self._poll_timeout = poll_timeout

        self.documents = DocumentsResource(self)
        self.tags = TagsResource(self)
        self.correspondents = CorrespondentsResource(self)
        self.document_types = DocumentTypesResource(self)
        self.storage_paths = StoragePathsResource(self)
        self.custom_fields = CustomFieldsResource(self)
        self.users = UsersResource(self)
        self.groups = GroupsResource(self)
        self.trash = TrashResource(self)

    def __repr__(self) -> str:
        # Never include the API token (#0047).
        return f"{type(self).__name__}(url={self._url!r})"

    async def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._session.close()

    async def __aenter__(self) -> PaperlessClient:
        return self  # type: ignore[return-value]

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _list_resource(
        self,
        resource: str,
        model_class: type[Any],
        params: dict[str, Any] | None = None,
    ) -> PagedResult[Any]:
        if params and "page" in params:
            raw = await self._session.get_page(f"/{resource}/", params=params)
        else:
            raw = await self._session.get_all_pages_paged(f"/{resource}/", params)
        return PagedResult(
            count=raw.count,
            next=raw.next,
            previous=raw.previous,
            all=raw.all_ids,
            results=[model_class.model_validate(item) for item in raw.items],
        )

    async def _get_resource(self, resource: str, id: int, model_class: type[Any]) -> Any:
        resp = await self._session.get(f"/{resource}/{id}/")
        return model_class.model_validate(resp.json())

    async def _create_resource(
        self,
        resource: str,
        model_class: type[Any],
        *,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
        **kwargs: Any,
    ) -> Any:
        logger.debug("Creating %s resource", resource)
        payload = {k: v for k, v in kwargs.items() if not isinstance(v, Unset)}
        if not isinstance(owner, Unset):
            payload["owner"] = owner
        if not isinstance(set_permissions, Unset):
            payload["set_permissions"] = (
                SetPermissions().model_dump()
                if set_permissions is None
                else set_permissions.model_dump()
            )
        resp = await self._session.post(f"/{resource}/", json=payload)
        self._resolver.invalidate(resource)
        return model_class.model_validate(resp.json())

    async def _update_resource(
        self,
        resource: str,
        id: int,
        model_class: type[Any],
        *,
        set_permissions: SetPermissions | None | Unset = UNSET,
        **kwargs: Any,
    ) -> Any:
        logger.debug("Updating %s resource id=%d", resource, id)
        payload = {k: v for k, v in kwargs.items() if not isinstance(v, Unset)}
        if not isinstance(set_permissions, Unset):
            payload["set_permissions"] = (
                SetPermissions().model_dump()
                if set_permissions is None
                else set_permissions.model_dump()
            )
        resp = await self._session.patch(f"/{resource}/{id}/", json=payload)
        self._resolver.invalidate(resource)
        return model_class.model_validate(resp.json())

    async def _delete_resource(self, resource: str, id: int) -> None:
        logger.debug("Deleting %s resource id=%d", resource, id)
        await self._session.delete(f"/{resource}/{id}/")
        self._resolver.invalidate(resource)

    async def _bulk_edit_objects(
        self,
        object_type: str,
        object_ids: list[int],
        operation: str,
        **parameters: Any,
    ) -> None:
        payload = {
            "objects": object_ids,
            "object_type": object_type,
            "operation": operation,
            **parameters,
        }
        await self._session.post("/bulk_edit_objects/", json=payload)


class PaperlessClient(_ClientCore):
    """Async client for the paperless-ngx API.

    Resources are accessible as attributes:

    * ``client.correspondents`` — correspondent CRUD + bulk ops -
      see `easypaperless.resources.CorrespondentsResource`
    * ``client.custom_fields`` — custom field CRUD -
      see `easypaperless.resources.CustomFieldsResource`
    * ``client.document_types`` — document type CRUD + bulk ops -
      see `easypaperless.resources.DocumentTypesResource`
    * ``client.documents`` — document CRUD, bulk ops, upload, download, history -
      see `easypaperless.resources.DocumentsResource`
    * ``client.documents.notes`` — document notes -
      see `easypaperless.resources.NotesResource`
    * ``client.storage_paths`` — storage path CRUD + bulk ops -
      see `easypaperless.resources.StoragePathsResource`
    * ``client.tags`` — tag CRUD + bulk ops -
      see `easypaperless.resources.TagsResource`
    * ``client.groups`` — group CRUD -
      see `easypaperless.resources.GroupsResource`
    * ``client.users`` — user CRUD -
      see `easypaperless.resources.UsersResource`
    * ``client.trash`` — list, restore, and permanently delete trashed documents -
      see `easypaperless.resources.TrashResource`

    Server information is available directly on the client:
    :meth:`server_version` (connection check) and :meth:`system_status`.

    Use as an async context manager to ensure the underlying HTTP connection
    pool is closed when you are done:

    Example:
        async with PaperlessClient(url="http://localhost:8000", api_token="abc") as client:
            docs = await client.documents.list(max_results=10)
    """

    def __init__(
        self,
        url: str,
        api_token: str,
        *,
        timeout: float = 30.0,
        poll_interval: float = 2.0,
        poll_timeout: float = 60.0,
        retry_attempts: int = 0,
        retry_backoff: float = 1.0,
        retry_on: tuple[type[Exception], ...] | None = None,
        tenacity_retrying: Any = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        """Create an async paperless-ngx client.

        Args:
            url: Base URL of the paperless-ngx instance
                (e.g. ``"http://localhost:8000"``).
            api_token: API token.  Generate one in paperless-ngx under
                *Settings → API → Generate Token*.
            timeout: Default request timeout in seconds.  Default: ``30.0``.
            poll_interval: Seconds between status checks when ``wait=True``
                is passed to :meth:`documents.upload`.  Default: ``2.0``.
            poll_timeout: Maximum seconds to wait for a document to finish
                processing before raising
                :exc:`~easypaperless.exceptions.TaskTimeoutError`.
                Default: ``60.0``.
            retry_attempts: Maximum number of retry attempts after the first
                failure.  ``0`` (the default) disables retrying entirely,
                preserving backward-compatible behaviour.
            retry_backoff: Initial sleep in seconds between retry attempts;
                doubles on each subsequent attempt.  Default: ``1.0``.
            retry_on: Tuple of exception types that trigger a retry.  Defaults
                to ``(ServerError, httpx.TimeoutException, httpx.ConnectError)``.
                ``NotFoundError`` is intentionally excluded from the default set
                so that genuine 404 responses are never silently retried.
                Note: every ``httpx`` exception is converted inside the HTTP
                layer before the retry loop sees it — timeouts become
                :exc:`~easypaperless.exceptions.TransportTimeoutError`, all
                other ``httpx`` errors (connection refused, DNS, TLS, protocol)
                become :exc:`~easypaperless.exceptions.TransportError`; both are
                ``ServerError`` subclasses. The ``httpx`` entries therefore
                never match on their own: to retry only transport failures but
                not 5xx responses, pass ``retry_on=(TransportError,)``; to
                retry only 5xx responses, pass
                ``retry_on=(ServerResponseError,)``.  Retries apply to every
                request path, including downloads and follow-up pages of
                paginated lists.
            tenacity_retrying: An optional pre-configured
                ``tenacity.AsyncRetrying`` instance.  When supplied, the
                ``retry_attempts``, ``retry_backoff``, and ``retry_on``
                parameters are ignored and tenacity drives the retry loop
                instead.  Must be ``AsyncRetrying`` — the sync
                ``tenacity.Retrying`` is not compatible with the async HTTP
                layer used internally.
            transport: Optional ``httpx.AsyncBaseTransport`` passed to the
                internal ``httpx.AsyncClient`` — e.g. an ``httpx.MockTransport``
                for tests, or an ``httpx.AsyncHTTPTransport`` with custom proxy,
                local address or TLS settings.  easypaperless still sets the
                ``Authorization`` header, base URL, timeout, redirect handling
                and retries.  Default: ``None`` (httpx's default transport).

        Example:
            Testing with a mock transport::

                def handler(request: httpx.Request) -> httpx.Response:
                    return httpx.Response(200, json={"count": 0, "next": None,
                                                     "previous": None, "results": []})

                client = PaperlessClient(url="http://paperless.test", api_token="t",
                                         transport=httpx.MockTransport(handler))
        """
        super().__init__(
            url,
            api_token,
            timeout=timeout,
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
            retry_attempts=retry_attempts,
            retry_backoff=retry_backoff,
            retry_on=retry_on,
            tenacity_retrying=tenacity_retrying,
            transport=transport,
        )

    async def __aenter__(self) -> PaperlessClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def server_version(self) -> str:
        """Return the paperless-ngx version and verify URL and token.

        Sends one authenticated ``GET /api/`` and reads the ``X-Version``
        response header. This is a cheap "test connection" call.

        Returns:
            The paperless-ngx version string, e.g. ``"2.18.4"``.

        Raises:
            ~easypaperless.exceptions.NotPaperlessError: The URL does not point
                to a paperless-ngx instance: the API root answered with 404, or
                with a response (e.g. an HTML page, also after a redirect) that
                lacks the ``X-Version`` header.
            ~easypaperless.exceptions.AuthenticationError: The token was
                refused (401).
            ~easypaperless.exceptions.PermissionDeniedError: The token lacks
                permission (403).
            ~easypaperless.exceptions.TransportError: The server could not be
                reached (connection refused, DNS, TLS, timeout).

        Example:
            >>> version = await client.server_version()
            >>> print(version)
            2.18.4
        """
        logger.info("Getting server version")
        url = f"{self._session._base_url}/"
        try:
            resp = await self._session.get("/")
        except NotFoundError as exc:
            raise NotPaperlessError(
                f"{url} does not appear to be a paperless-ngx instance: "
                "the API root answered with 404 Not Found.",
                status_code=exc.status_code,
            ) from exc
        version: str | None = resp.headers.get("X-Version")
        if not version:
            raise NotPaperlessError(
                f"{url} does not appear to be a paperless-ngx instance: "
                "the response carries no X-Version header.",
                status_code=resp.status_code,
            )
        return version

    async def system_status(self) -> SystemStatus:
        """Return paperless-ngx's system status (``GET /api/status/``).

        Covers version, install type, server OS, storage, database, and the
        health of Redis, Celery, the search index and the classifier. Every
        field of the returned model is optional; fields a paperless version
        does not send stay ``None``, unknown fields are ignored.

        Returns:
            A :class:`~easypaperless.models.system_status.SystemStatus`.

        Raises:
            ~easypaperless.exceptions.PermissionDeniedError: The token's user
                is not an administrator (403).
            ~easypaperless.exceptions.AuthenticationError: The token was
                refused (401).

        Example:
            >>> status = await client.system_status()
            >>> status.database.status
            'OK'
        """
        logger.info("Getting system status")
        resp = await self._session.get("/status/")
        return SystemStatus.model_validate(resp.json())
