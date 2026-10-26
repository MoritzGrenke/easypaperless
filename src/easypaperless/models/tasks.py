"""Task-related Pydantic models (paperless-ngx background tasks)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class TaskStatus(StrEnum):
    """Status values for a paperless-ngx background processing task."""

    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"
    RECEIVED = "RECEIVED"


class Task(BaseModel):
    """A paperless-ngx background task (e.g. document consumption).

    Values are taken from paperless-ngx unaltered; unknown fields are ignored.

    Attributes:
        id: Numeric database ID of the task (used by
            :meth:`~easypaperless.resources.TasksResource.acknowledge`).
        task_id: Unique Celery task identifier (UUID string), as returned by
            ``documents.upload(wait=False)``.
        task_name: Name of the task, e.g. ``"consume_file"``.
        task_file_name: Original file name submitted for processing.
        type: Task type as reported by paperless-ngx: ``"auto_task"`` (e.g.
            a document consumption), ``"scheduled_task"`` or ``"manual_task"``.
        status: Current task status as a :class:`TaskStatus` enum value.  A
            status this library does not know yet is kept as the plain string
            paperless-ngx sent (it compares equal to that string).
        result: Result or error message exactly as paperless-ngx reports it.
            Consumption failures start with ``"<task_file_name>: "``, e.g.
            ``"Success. New document id 42 created"``,
            ``"x.pdf: Not consuming x.pdf: It is a duplicate of y (#12)."``
            (a duplicate of a trashed document ends in
            ``" Note: existing document is in the trash."``) or
            ``"x.pdf: Error occurred while consuming document x.pdf: ..."``.
        acknowledged: Whether the task was acknowledged (dismissed in the UI).
        related_document: Document ID as a string, or ``None``.  On
            ``SUCCESS`` it is the new document.  On a duplicate ``FAILURE`` it
            is the *existing* document the upload duplicates (``None`` when
            that document is in the trash).  ``None`` for other failures.
        date_created: When the task was created.
        date_done: When the task finished, ``None`` while it is running.
        owner: ID of the user owning the task, if any.
    """

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    task_id: str
    task_name: str | None = None
    task_file_name: str | None = None
    type: str | None = None
    status: TaskStatus | str | None = None
    result: str | None = None
    acknowledged: bool | None = None
    related_document: str | None = None
    date_created: datetime | None = None
    date_done: datetime | None = None
    owner: int | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _known_status_as_enum(cls, value: Any) -> Any:
        """Parse known statuses as :class:`TaskStatus`; keep unknown strings as-is."""
        if isinstance(value, str) and not isinstance(value, TaskStatus):
            try:
                return TaskStatus(value)
            except ValueError:
                return value
        return value

    @field_validator("related_document", mode="before")
    @classmethod
    def _related_document_as_str(cls, value: Any) -> Any:
        """Accept an integer document ID as well (kept as a string)."""
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value
