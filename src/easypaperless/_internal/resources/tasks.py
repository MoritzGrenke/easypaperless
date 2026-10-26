"""Tasks resource for PaperlessClient."""

from __future__ import annotations

import asyncio
import builtins
import logging
import time
from typing import TYPE_CHECKING, Any

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.exceptions import NotFoundError, TaskTimeoutError, UploadError
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.tasks import Task, TaskStatus

if TYPE_CHECKING:
    from easypaperless.client import _ClientCore

logger = logging.getLogger(__name__)


class TasksResource:
    """Accessor for paperless-ngx background tasks: ``client.tasks``."""

    def __init__(self, core: _ClientCore) -> None:
        self._core = core

    async def list(
        self,
        *,
        task_id: str | Unset = UNSET,
        status: TaskStatus | str | Unset = UNSET,
        task_name: str | Unset = UNSET,
        type: str | Unset = UNSET,
        acknowledged: bool | Unset = UNSET,
    ) -> PagedResult[Task]:
        """Return background tasks, optionally filtered.

        paperless-ngx returns the task list as a plain JSON array (not
        paginated); it is wrapped into a
        :class:`~easypaperless.models.paged_result.PagedResult` with
        ``next`` / ``previous`` set to ``None``.  A paginated response is
        accepted as well, and all its pages are fetched.

        Args:
            task_id: Only the task with this Celery task ID (UUID string).
            status: Only tasks with this status, e.g. ``TaskStatus.FAILURE``
                or ``"FAILURE"``.
            task_name: Only tasks with this name: ``"consume_file"``,
                ``"train_classifier"``, ``"check_sanity"`` or
                ``"index_optimize"``.
            type: Only tasks of this type: ``"auto_task"``,
                ``"scheduled_task"`` or ``"manual_task"``.
            acknowledged: ``False`` for tasks not yet acknowledged (as shown
                in the paperless-ngx UI), ``True`` for acknowledged ones.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.tasks.Task` objects.

        Raises:
            ~easypaperless.exceptions.BadRequestError: If ``status``,
                ``task_name`` or ``type`` is not one of paperless-ngx's values.
                These filters are case-sensitive (``"success"`` is rejected).
        """
        logger.info("Listing tasks")
        filters = {
            "task_id": task_id,
            "status": status,
            "task_name": task_name,
            "type": type,
            "acknowledged": acknowledged,
        }
        params: dict[str, Any] = {k: v for k, v in filters.items() if not isinstance(v, Unset)}
        raw = await self._core._session.get_list("/tasks/", params=params or None)
        return PagedResult(
            count=raw.count,
            all=raw.all_ids,
            results=[Task.model_validate(item) for item in raw.items],
        )

    async def get(self, task_id: str) -> Task:
        """Fetch a single task by its Celery task ID.

        Args:
            task_id: The task's UUID string, e.g. as returned by
                ``documents.upload(wait=False)``.

        Returns:
            The :class:`~easypaperless.models.tasks.Task`.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If paperless-ngx does not
                know a task with this ID.
        """
        logger.info("Getting task task_id=%r", task_id)
        task = await self._fetch(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id!r} not found")
        return task

    async def wait(
        self,
        task_id: str,
        *,
        poll_interval: float | None = None,
        poll_timeout: float | None = None,
    ) -> Task:
        """Poll a task until it reaches a terminal state and return it.

        Use this to resume waiting for an upload started with
        ``documents.upload(wait=False)``, or after a
        :exc:`~easypaperless.exceptions.TaskTimeoutError`.  A task that
        paperless-ngx does not list yet (right after an upload) is polled
        again rather than treated as missing.  The task is checked at least
        once, even with ``poll_timeout=0``.  A status this library does not
        know is treated as not finished yet.  An unknown ``task_id`` therefore
        keeps being polled until ``poll_timeout`` and then raises
        :exc:`~easypaperless.exceptions.TaskTimeoutError`.

        Args:
            task_id: The task's UUID string, e.g. as returned by
                ``documents.upload(wait=False)``.
            poll_interval: Seconds between status checks.  When omitted, falls
                back to the client-level ``poll_interval`` (``2.0`` s unless
                changed at construction).
            poll_timeout: Maximum seconds to wait.  When omitted, falls back to
                the client-level ``poll_timeout`` (``60.0`` s unless changed at
                construction).

        Returns:
            The final :class:`~easypaperless.models.tasks.Task` with status
            ``SUCCESS``.

        Raises:
            ~easypaperless.exceptions.UploadError: If the task reports
                ``FAILURE`` or ``REVOKED``; ``err.task`` holds the task with
                paperless-ngx's ``status`` and ``result`` unaltered.
            ~easypaperless.exceptions.TaskTimeoutError: If the task does not
                finish within ``poll_timeout`` seconds; ``err.task_id`` and
                ``err.timeout`` are set so the caller can wait again.
        """
        interval = poll_interval if poll_interval is not None else self._core._poll_interval
        timeout = poll_timeout if poll_timeout is not None else self._core._poll_timeout
        logger.info("Waiting for task task_id=%r (timeout=%.1fs)", task_id, timeout)
        start = time.monotonic()
        deadline = start + timeout
        while True:
            task = await self._fetch(task_id)
            elapsed = time.monotonic() - start
            status = task.status if task is not None else None
            logger.debug(
                "Polling task %r (status=%s, elapsed=%.1fs)",
                task_id,
                status if status is not None else "unknown",
                elapsed,
            )
            if task is not None and status == TaskStatus.SUCCESS:
                logger.info("Task %r succeeded", task_id)
                return task
            if task is not None and status == TaskStatus.FAILURE:
                logger.warning("Task %r failed: %s", task_id, task.result)
                raise UploadError(f"Document processing failed: {task.result}", task=task)
            if task is not None and status == TaskStatus.REVOKED:
                logger.warning("Task %r was revoked", task_id)
                raise UploadError(f"Task {task_id!r} was revoked", task=task)
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(interval)

        logger.warning("Task %r timed out after %.1fs", task_id, time.monotonic() - start)
        raise TaskTimeoutError(
            f"Task {task_id!r} did not complete within {timeout}s",
            task_id=task_id,
            timeout=timeout,
        )

    async def acknowledge(self, ids: builtins.list[int]) -> int:
        """Mark tasks as acknowledged, as the paperless-ngx UI's "Dismiss" does.

        Args:
            ids: Numeric task IDs (:attr:`Task.id
                <easypaperless.models.tasks.Task.id>`, not the UUID
                ``task_id``).

        Returns:
            The number of tasks paperless-ngx acknowledged.
        """
        logger.info("Acknowledging %d task(s)", len(ids))
        resp = await self._core._session.post("/tasks/acknowledge/", json={"tasks": ids})
        body = resp.json()
        result = body.get("result") if isinstance(body, dict) else None
        return result if isinstance(result, int) else len(ids)

    async def _fetch(self, task_id: str) -> Task | None:
        """Return the task with ``task_id``, or ``None`` if paperless has none."""
        raw = await self._core._session.get_list(
            "/tasks/", params={"task_id": task_id}, all_pages=False
        )
        if not raw.items:
            return None
        return Task.model_validate(raw.items[0])
