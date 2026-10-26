"""Document-related Pydantic models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Task models live in models/tasks.py; re-exported here for backward compatibility.
from easypaperless.models.tasks import Task as Task
from easypaperless.models.tasks import TaskStatus as TaskStatus


class SearchHit(BaseModel):
    """Full-text search relevance metadata returned alongside a document.

    Attributes:
        score: Relevance score assigned by the Whoosh FTS engine.
        highlights: HTML snippet with matching terms highlighted.
        rank: Position in the result set by relevance.
    """

    model_config = ConfigDict(extra="ignore")

    score: float | None = None
    highlights: str | None = None
    note_highlights: str | None = None
    rank: int | None = None


class CustomFieldValue(BaseModel):
    """A custom field value attached to a document.

    Attributes:
        field: ID of the :class:`~easypaperless.models.custom_fields.CustomField`
            definition.
        value: The stored value; its Python type depends on the field's
            ``data_type``.
    """

    model_config = ConfigDict(extra="ignore")

    field: int
    value: Any = None


class AuditLogActor(BaseModel):
    """The user who performed an audited action.

    Attributes:
        id: Numeric user ID.
        username: Username of the actor.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    username: str


class AuditLogEntry(BaseModel):
    """A single entry in a document's audit log.

    Attributes:
        id: Unique audit log entry ID.
        timestamp: When the action occurred.
        action: Action type (e.g. ``"create"``, ``"update"``).
        changes: Free-form dict describing what changed.  Keys and value
            shapes vary by action type.
        actor: The user who performed the action, or ``None`` for
            system-generated entries.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    timestamp: datetime
    action: str
    changes: dict[str, Any]
    actor: AuditLogActor | None = None


class DocumentNote(BaseModel):
    """A user note attached to a document.

    Attributes:
        id: Unique note ID.
        note: Text content of the note.
        created: Timestamp when the note was created.
        document: ID of the parent document.
        user: ID of the user who created the note.
    """

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    note: str
    created: datetime | None = None
    document: int | None = None
    user: int | None = None

    @field_validator("user", mode="before")
    @classmethod
    def _coerce_user(cls, v: object) -> int | None:
        if isinstance(v, dict):
            return v.get("id")
        return v  # type: ignore[return-value]


class FileMetadataEntry(BaseModel):
    """A single embedded metadata key-value pair from a document file.

    Paperless-ngx reads file-level metadata (e.g. PDF XMP/info tags) and
    exposes each entry in this format.  ``namespace`` and ``prefix`` are
    ``None`` for non-namespaced entries.

    Attributes:
        namespace: XML namespace URI, or ``None``.
        prefix: Namespace prefix (e.g. ``"pdf"``), or ``None``.
        key: Metadata key (e.g. ``"Producer"``).
        value: Metadata value as a string.
    """

    model_config = ConfigDict(extra="ignore")

    namespace: str | None = None
    prefix: str | None = None
    key: str
    value: str


class DocumentMetadata(BaseModel):
    """Extended file-level metadata for a document.

    Returned by ``GET /api/documents/{id}/metadata/`` and optionally attached
    to a :class:`Document` when
    :meth:`~easypaperless._internal.resources.documents.DocumentsResource.get`
    is called with ``include_metadata=True``.

    Because reading metadata requires disk I/O it is **not** included in
    document list responses; it must be requested explicitly.

    Attributes:
        original_checksum: MD5 checksum of the original uploaded file.
        original_size: Size of the original file in bytes.
        original_mime_type: MIME type of the original file
            (e.g. ``"application/pdf"``).
        media_filename: Path of the archived file relative to the
            paperless-ngx media root.
        has_archive_version: ``True`` when paperless-ngx has produced an
            archived (post-processed) PDF in addition to the original.
        original_metadata: File-level metadata entries extracted from the
            original document (PDF XMP/info tags, etc.).
        archive_checksum: MD5 checksum of the archived file, or ``None`` if
            no archive version exists.
        archive_size: Size of the archived file in bytes, or ``None``.
        archive_metadata: File-level metadata entries from the archived
            document, or ``None``.
    """

    model_config = ConfigDict(extra="ignore")

    original_checksum: str | None = None
    original_size: int | None = None
    original_mime_type: str | None = None
    media_filename: str | None = None
    has_archive_version: bool | None = None
    original_metadata: list[FileMetadataEntry] = Field(default_factory=list)
    archive_checksum: str | None = None
    archive_size: int | None = None
    archive_metadata: list[FileMetadataEntry] | None = None


class Document(BaseModel):
    """A paperless-ngx document.

    Attributes:
        id: Unique document ID.
        title: Document title.
        content: Full OCR text content, if available.
        tags: List of tag IDs assigned to this document.
        document_type: ID of the assigned document type, or ``None``.
        correspondent: ID of the assigned correspondent, or ``None``.
        storage_path: ID of the assigned storage path, or ``None``.
        created: Document creation date (``date`` object). Changed from
            ``datetime`` to ``date`` in paperless-ngx API v9.
        created_date: Date portion of creation. **Deprecated** by
            paperless-ngx as of v9 — use ``created`` instead. Will be
            removed in a future API version.
        archive_serial_number: Archive serial number (ASN), or ``None``.
        custom_fields: List of :class:`CustomFieldValue` instances.
        notes: User notes attached to this document.
        search_hit: Full-text search relevance metadata, populated only when
            the document was returned by a full-text search.
        metadata: Extended file-level metadata (checksums, sizes, MIME type).
            ``None`` unless the document was fetched with
            ``include_metadata=True`` or retrieved via
            :meth:`~easypaperless._internal.resources.documents.DocumentsResource.get_metadata`.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    title: str
    content: str | None = None
    tags: list[int] = Field(default_factory=list)
    document_type: int | None = None
    correspondent: int | None = None
    storage_path: int | None = None
    created: date | None = None
    created_date: date | None = None
    modified: datetime | None = None
    added: datetime | None = None
    archive_serial_number: int | None = None
    original_file_name: str | None = None
    archived_file_name: str | None = None
    owner: int | None = None
    user_can_change: bool | None = None
    is_shared_by_requester: bool | None = None
    notes: list[DocumentNote] = Field(default_factory=list)
    custom_fields: list[CustomFieldValue] = Field(default_factory=list)
    search_hit: SearchHit | None = Field(default=None, alias="__search_hit__")
    metadata: DocumentMetadata | None = None
