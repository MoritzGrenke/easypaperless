"""Sync tasks resource."""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.tasks import Task, TaskStatus

if TYPE_CHECKING:
    from easypaperless._internal.resources.tasks import TasksResource


class SyncTasksResource:
    """Sync accessor for paperless-ngx background tasks: ``client.tasks``."""

    def __init__(self, async_tasks: TasksResource, run: Any) -> None:
        self._async_tasks = async_tasks
        self._run = run

    def list(
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
        return cast(
            PagedResult[Task],
            self._run(
                self._async_tasks.list(
                    task_id=task_id,
                    status=status,
                    task_name=task_name,
                    type=type,
                    acknowledged=acknowledged,
                )
            ),
        )

    def get(self, task_id: str) -> Task:
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
        return cast(Task, self._run(self._async_tasks.get(task_id)))

    def wait(
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
        return cast(
            Task,
            self._run(
                self._async_tasks.wait(
                    task_id, poll_interval=poll_interval, poll_timeout=poll_timeout
                )
            ),
        )

    def acknowledge(self, ids: builtins.list[int]) -> int:
        """Mark tasks as acknowledged, as the paperless-ngx UI's "Dismiss" does.

        Args:
            ids: Numeric task IDs (:attr:`Task.id
                <easypaperless.models.tasks.Task.id>`, not the UUID
                ``task_id``).

        Returns:
            The number of tasks paperless-ngx acknowledged.
        """
        return cast(int, self._run(self._async_tasks.acknowledge(ids)))
