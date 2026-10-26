"""Synchronous wrapper around PaperlessClient.

Note: SyncPaperlessClient cannot be used inside an already-running event loop
(e.g., Jupyter notebooks). Use the async PaperlessClient directly there.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

from easypaperless._internal.sync_resources.correspondents import SyncCorrespondentsResource
from easypaperless._internal.sync_resources.custom_fields import SyncCustomFieldsResource
from easypaperless._internal.sync_resources.document_types import SyncDocumentTypesResource
from easypaperless._internal.sync_resources.documents import SyncDocumentsResource
from easypaperless._internal.sync_resources.groups import SyncGroupsResource
from easypaperless._internal.sync_resources.storage_paths import SyncStoragePathsResource
from easypaperless._internal.sync_resources.tags import SyncTagsResource
from easypaperless._internal.sync_resources.tasks import SyncTasksResource
from easypaperless._internal.sync_resources.trash import SyncTrashResource
from easypaperless._internal.sync_resources.users import SyncUsersResource
from easypaperless.client import PaperlessClient
from easypaperless.models.system_status import SystemStatus

_T = TypeVar("_T")


class _SyncCore:
    """Background event loop, _run() helper, and context manager."""

    documents: SyncDocumentsResource
    tags: SyncTagsResource
    correspondents: SyncCorrespondentsResource
    document_types: SyncDocumentTypesResource
    storage_paths: SyncStoragePathsResource
    custom_fields: SyncCustomFieldsResource
    users: SyncUsersResource
    groups: SyncGroupsResource
    trash: SyncTrashResource
    tasks: SyncTasksResource

    def __init__(self, url: str, api_token: str, **kwargs: Any) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._async_client = PaperlessClient(url, api_token, **kwargs)

        self.documents = SyncDocumentsResource(self._async_client.documents, self._run)
        self.tags = SyncTagsResource(self._async_client.tags, self._run)
        self.correspondents = SyncCorrespondentsResource(
            self._async_client.correspondents, self._run
        )
        self.document_types = SyncDocumentTypesResource(
            self._async_client.document_types, self._run
        )
        self.storage_paths = SyncStoragePathsResource(self._async_client.storage_paths, self._run)
        self.custom_fields = SyncCustomFieldsResource(self._async_client.custom_fields, self._run)
        self.users = SyncUsersResource(self._async_client.users, self._run)
        self.groups = SyncGroupsResource(self._async_client.groups, self._run)
        self.trash = SyncTrashResource(self._async_client.trash, self._run)
        self.tasks = SyncTasksResource(self._async_client.tasks, self._run)

    def __repr__(self) -> str:
        # Never include the API token (#0047).
        return f"{type(self).__name__}(url={self._async_client._url!r})"

    def _run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Submit a coroutine to the background event loop and block until done."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def close(self) -> None:
        """Close the underlying HTTP connection pool and stop the event loop.

        Stops the internal loop and joins its thread before returning.
        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._loop.is_closed():
            return
        self._run(self._async_client.close())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()
        self._loop.close()

    def __enter__(self) -> SyncPaperlessClient:
        return self  # type: ignore[return-value]

    def __exit__(self, *args: Any) -> None:
        self.close()


class SyncPaperlessClient(_SyncCore):
    """Synchronous interface to paperless-ngx.

    Resources are accessible as attributes:

    * ``client.correspondents`` — correspondent CRUD + bulk ops -
      see `easypaperless.resources.SyncCorrespondentsResource`
    * ``client.custom_fields`` — custom field CRUD -
      see `easypaperless.resources.SyncCustomFieldsResource`
    * ``client.document_types`` — document type CRUD + bulk ops -
      see `easypaperless.resources.SyncDocumentTypesResource`
    * ``client.documents`` — document CRUD, bulk ops, upload, download -
      see `easypaperless.resources.SyncDocumentsResource`
    * ``client.documents.notes`` — document notes -
      see `easypaperless.resources.SyncNotesResource`
    * ``client.storage_paths`` — storage path CRUD + bulk ops -
      see `easypaperless.resources.SyncStoragePathsResource`
    * ``client.tags`` — tag CRUD + bulk ops -
      see `easypaperless.resources.SyncTagsResource`
    * ``client.groups`` — group CRUD -
      see `easypaperless.resources.SyncGroupsResource`
    * ``client.users`` — user CRUD -
      see `easypaperless.resources.SyncUsersResource`
    * ``client.trash`` — list, restore, and permanently delete trashed documents -
      see `easypaperless.resources.SyncTrashResource`
    * ``client.tasks`` — list, get, wait for, and acknowledge background tasks -
      see `easypaperless.resources.SyncTasksResource`

    Server information is available directly on the client:
    :meth:`server_version` (connection check) and :meth:`system_status`.

    All methods are synchronous wrappers around the async
    :class:`~easypaperless.client.PaperlessClient`.  Operations run on a
    dedicated background event loop thread so that the httpx connection pool
    is reused across calls and cleanup works correctly.

    Use as a context manager to ensure proper cleanup:

    Example:
        with SyncPaperlessClient(url="http://localhost:8000", api_token="abc") as client:
            tags = client.tags.list()
            docs = client.documents.list(search="invoice")

    Worker threads:
        It is safe to construct and use a ``SyncPaperlessClient`` from a
        worker thread while another event loop runs in the main thread (e.g.
        a synchronous worker beside FastAPI/uvicorn, or via
        ``asyncio.to_thread``).  Each client owns its own private loop thread.
        :meth:`close` (or leaving the ``with`` block) closes the connection
        pool, stops that loop and joins its thread; calling it again is a
        no-op.

    Note:
        Cannot be called directly from code running *inside* an event loop
        (e.g. Jupyter notebooks or an ``async def`` body) — that would block
        the loop.  Use :class:`~easypaperless.client.PaperlessClient` there,
        or move the sync calls into a worker thread.
    """

    def __init__(self, url: str, api_token: str, **kwargs: Any) -> None:
        """Create a synchronous paperless-ngx client.

        Args:
            url: Base URL of the paperless-ngx instance
                (e.g. ``"http://localhost:8000"``).
            api_token: API token.  Generate one in paperless-ngx under
                *Settings → API → Generate Token*.
            **kwargs: Additional keyword arguments forwarded to
                :class:`~easypaperless.client.PaperlessClient` (e.g.
                ``poll_interval``, ``poll_timeout``, ``retry_attempts``,
                ``retry_backoff``, ``retry_on``, ``tenacity_retrying``,
                ``transport``).
                When using ``tenacity_retrying``, pass a
                ``tenacity.AsyncRetrying`` instance — the sync
                ``tenacity.Retrying`` is not compatible because all requests
                run on an internal async event loop.

                ``retry_attempts`` / ``tenacity_retrying`` never apply to
                requests that create something: ``documents.upload()``, every
                resource's ``create()`` and ``documents.notes.create()`` send
                exactly one request and raise the error, because a retry after
                a lost response could create a duplicate.

                ``transport`` (``httpx.AsyncBaseTransport | None``): custom or
                mock transport for the internal ``httpx.AsyncClient``; must be
                an *async* transport.  An ``httpx.MockTransport`` works — its
                handler is invoked on the client's internal loop thread.
                Auth, base URL, timeout and retries stay under easypaperless's
                control.
        """
        super().__init__(url, api_token, **kwargs)

    def __enter__(self) -> SyncPaperlessClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def server_version(self) -> str:
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
            >>> client.server_version()
            '2.18.4'
        """
        return self._run(self._async_client.server_version())

    def system_status(self) -> SystemStatus:
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
            >>> client.system_status().database.status
            'OK'
        """
        return self._run(self._async_client.system_status())
