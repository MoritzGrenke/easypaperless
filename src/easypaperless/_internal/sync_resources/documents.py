"""Sync documents resource."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Literal, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless._internal.sync_resources.notes import SyncNotesResource
from easypaperless.models.documents import AuditLogEntry, Document, DocumentMetadata
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.permissions import SetPermissions

if TYPE_CHECKING:
    from easypaperless._internal.resources.documents import DocumentsResource

__all__ = ["SyncDocumentsResource", "SyncNotesResource"]


class SyncDocumentsResource:
    """Sync accessor for documents: ``client.documents``."""

    def __init__(self, async_documents: DocumentsResource, run: Any) -> None:
        self._async_documents = async_documents
        self._run = run
        self.notes = SyncNotesResource(async_documents.notes, run)

    def history(
        self,
        document_id: int,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> PagedResult[AuditLogEntry]:
        """Fetch the audit log for a document.

        The paperless-ngx ``/api/documents/{id}/history/`` endpoint returns a
        plain JSON array rather than a paginated envelope.  This method wraps
        the response into a :class:`~easypaperless.models.paged_result.PagedResult`
        so callers always receive a consistent return type.

        Args:
            document_id: Numeric ID of the document whose history to retrieve.
            page: Forwarded to the API as a query parameter when provided.
                Effect depends on the paperless-ngx version; the server may
                ignore this parameter.
            page_size: Forwarded to the API as a query parameter when provided.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.documents.AuditLogEntry` objects,
            ordered by timestamp descending.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        return cast(
            PagedResult[AuditLogEntry],
            self._run(self._async_documents.history(document_id, page=page, page_size=page_size)),
        )

    def get(self, id: int, *, include_metadata: bool = False) -> Document:
        """Fetch a single document by its ID.

        Args:
            id: Numeric paperless-ngx document ID.
            include_metadata: When ``True``, the extended file-level metadata
                is fetched concurrently and attached to the document.
                Default: ``False``.

        Returns:
            The :class:`~easypaperless.models.documents.Document` with the
            given ID.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        return cast(
            Document, self._run(self._async_documents.get(id, include_metadata=include_metadata))
        )

    def get_metadata(self, id: int) -> DocumentMetadata:
        """Fetch the extended file-level metadata for a document.

        Args:
            id: Numeric paperless-ngx document ID.

        Returns:
            A :class:`~easypaperless.models.documents.DocumentMetadata` instance.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        return cast(DocumentMetadata, self._run(self._async_documents.get_metadata(id)))

    def list(
        self,
        *,
        search: str | None = None,
        search_mode: str = "title_or_content",
        ids: List[int] | None = None,
        tags: List[int | str] | None = None,
        any_tags: List[int | str] | None = None,
        exclude_tags: List[int | str] | None = None,
        correspondent: int | str | None | Unset = UNSET,
        any_correspondent: List[int | str] | None = None,
        exclude_correspondents: List[int | str] | None = None,
        document_type: int | str | None | Unset = UNSET,
        document_type_name_contains: str | None = None,
        document_type_name_exact: str | None = None,
        any_document_type: List[int | str] | None = None,
        exclude_document_types: List[int | str] | None = None,
        storage_path: int | str | None | Unset = UNSET,
        any_storage_paths: List[int | str] | None = None,
        exclude_storage_paths: List[int | str] | None = None,
        owner: int | None | Unset = UNSET,
        exclude_owners: List[int] | None = None,
        custom_fields: List[int | str] | None = None,
        any_custom_fields: List[int | str] | None = None,
        exclude_custom_fields: List[int | str] | None = None,
        custom_field_query: List[Any] | None = None,
        archive_serial_number: int | None | Unset = UNSET,
        archive_serial_number_from: int | None = None,
        archive_serial_number_till: int | None = None,
        created_after: date | str | None = None,
        created_before: date | str | None = None,
        added_after: date | datetime | str | None = None,
        added_from: date | datetime | str | None = None,
        added_before: date | datetime | str | None = None,
        added_until: date | datetime | str | None = None,
        modified_after: date | datetime | str | None = None,
        modified_from: date | datetime | str | None = None,
        modified_before: date | datetime | str | None = None,
        modified_until: date | datetime | str | None = None,
        checksum: str | None = None,
        page_size: int = 25,
        page: int | None = None,
        ordering: str | None = None,
        descending: bool = False,
        max_results: int | None = None,
        on_page: Callable[[int, int | None], None] | None = None,
    ) -> PagedResult[Document]:
        """Return a filtered list of documents.

        All tag, correspondent, document-type, storage-path, and custom-field
        parameters accept either integer IDs or string names.

        When ``page`` is ``None`` (the default), all pages are fetched
        automatically and ``next`` / ``previous`` in the returned
        :class:`~easypaperless.models.paged_result.PagedResult` are always
        ``None`` — even if ``max_results`` truncates the final result set.
        ``count`` always reflects the server total, not the truncated length.
        When ``page`` is set to a specific integer, only that one page is
        fetched and ``next`` / ``previous`` contain the raw API values.

        Args:
            search: Search string.  Behaviour depends on ``search_mode``.
            search_mode: How ``search`` is applied.  One of:
                ``"title_or_content"`` *(default)*, ``"title"``, ``"query"``,
                ``"original_filename"``.
            ids: Return only documents whose ID is in this list.
            tags: Documents must have **all** of these tags (AND semantics).
            any_tags: Documents must have **at least one** of these tags.
            exclude_tags: Documents must have **none** of these tags.
            correspondent: Filter to documents assigned to this correspondent.
                Pass ``None`` to return only documents with no correspondent set.
            any_correspondent: Filter to documents assigned to any of these.
            exclude_correspondents: Exclude documents assigned to any of these.
            document_type: Filter to documents of exactly this type.
                Pass ``None`` to return only documents with no document type set.
            document_type_name_contains: Case-insensitive substring filter on document type name.
            document_type_name_exact: Case-insensitive exact match on document type name.
            any_document_type: Filter to documents whose type is any of these.
            exclude_document_types: Exclude documents whose type is any of these.
            storage_path: Filter to documents assigned to this storage path.
                Pass ``None`` to return only documents with no storage path set.
            any_storage_paths: Filter to documents assigned to any of these paths.
            exclude_storage_paths: Exclude documents assigned to any of these paths.
            owner: Filter to documents owned by this user ID.
                Pass ``None`` to return only documents with no owner set.
            exclude_owners: Exclude documents owned by any of these user IDs.
            custom_fields: Documents must have **all** of these custom fields set.
            any_custom_fields: Documents must have **at least one** of these fields.
            exclude_custom_fields: Documents must have **none** of these fields.
            custom_field_query: Filter documents by custom field values using a nested
                query structure. See the `paperless-ngx API docs
                <https://docs.paperless-ngx.com/api/#filtering-by-custom-fields>`_ for
                the query format.
            archive_serial_number: Filter by exact archive serial number.
                Pass ``None`` to return only documents with no ASN set.
            archive_serial_number_from: Filter by ASN >= this value.
            archive_serial_number_till: Filter by ASN <= this value.
            created_after: Only documents created after this date.
                String input must be ISO-8601: ``"YYYY-MM-DD"``.
            created_before: Only documents created before this date.
                String input must be ISO-8601: ``"YYYY-MM-DD"``.
            added_after: Only documents added after this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` for date precision or
                ``"YYYY-MM-DDTHH:MM:SS"`` for datetime precision.
            added_from: Only documents added on or after this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``.
            added_before: Only documents added before this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``.
            added_until: Only documents added on or before this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``.
            modified_after: Only documents modified after this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``.
            modified_from: Only documents modified on or after this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``.
            modified_before: Only documents modified before this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``.
            modified_until: Only documents modified on or before this date/time.
                String input must be ISO-8601: ``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``.
            checksum: MD5 checksum of the original file (exact match).
            page_size: Number of results per API page.  Default: ``25``.
            page: Return only this specific page (1-based).
            ordering: Field name to sort by.
            descending: When ``True``, reverses the sort direction.
            max_results: Stop after collecting this many documents.
            on_page: Callback invoked after each page fetch.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.documents.Document` objects.
        """
        return cast(
            PagedResult[Document],
            self._run(
                self._async_documents.list(
                    search=search,
                    search_mode=search_mode,
                    ids=ids,
                    tags=tags,
                    any_tags=any_tags,
                    exclude_tags=exclude_tags,
                    correspondent=correspondent,
                    any_correspondent=any_correspondent,
                    exclude_correspondents=exclude_correspondents,
                    document_type=document_type,
                    document_type_name_contains=document_type_name_contains,
                    document_type_name_exact=document_type_name_exact,
                    any_document_type=any_document_type,
                    exclude_document_types=exclude_document_types,
                    storage_path=storage_path,
                    any_storage_paths=any_storage_paths,
                    exclude_storage_paths=exclude_storage_paths,
                    owner=owner,
                    exclude_owners=exclude_owners,
                    custom_fields=custom_fields,
                    any_custom_fields=any_custom_fields,
                    exclude_custom_fields=exclude_custom_fields,
                    custom_field_query=custom_field_query,
                    archive_serial_number=archive_serial_number,
                    archive_serial_number_from=archive_serial_number_from,
                    archive_serial_number_till=archive_serial_number_till,
                    created_after=created_after,
                    created_before=created_before,
                    added_after=added_after,
                    added_from=added_from,
                    added_before=added_before,
                    added_until=added_until,
                    modified_after=modified_after,
                    modified_from=modified_from,
                    modified_before=modified_before,
                    modified_until=modified_until,
                    checksum=checksum,
                    page_size=page_size,
                    page=page,
                    ordering=ordering,
                    descending=descending,
                    max_results=max_results,
                    on_page=on_page,
                )
            ),
        )

    def update(
        self,
        id: int,
        *,
        title: str | Unset = UNSET,
        content: str | Unset = UNSET,
        created: date | str | None | Unset = UNSET,
        correspondent: int | str | None | Unset = UNSET,
        document_type: int | str | None | Unset = UNSET,
        storage_path: int | str | None | Unset = UNSET,
        tags: List[int | str] | None | Unset = UNSET,
        archive_serial_number: int | None | Unset = UNSET,
        custom_fields: List[dict[str, Any]] | None | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        set_permissions: SetPermissions | None | Unset = UNSET,
        remove_inbox_tags: bool | None | Unset = UNSET,
    ) -> Document:
        """Partially update a document (PATCH semantics).

        Args:
            id: Numeric ID of the document to update.
            title: New document title.
            content: OCR text content of the document.
            created: Creation date as an ISO-8601 string (``"YYYY-MM-DD"``) or a
                :class:`~datetime.date` object.
            correspondent: Correspondent to assign, as an ID or name.
                Pass ``None`` to clear the correspondent.
            document_type: Document type to assign, as an ID or name.
                Pass ``None`` to clear the document type.
            storage_path: Storage path to assign, as an ID or name.
                Pass ``None`` to clear the storage path.
            tags: Full replacement list of tags (IDs or names).
            archive_serial_number: Archive serial number to assign.
                Pass ``None`` to clear the archive serial number.
            custom_fields: List of ``{"field": <field_id>, "value": ...}`` dicts.
            owner: Numeric user ID to assign as document owner.
                Pass ``None`` to clear the owner.
            set_permissions: Explicit view/change permission sets.
                Pass ``None`` to clear all permissions (overwrite with empty).
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            remove_inbox_tags: When ``True``, removes all inbox tags from the document.

        Returns:
            The updated :class:`~easypaperless.models.documents.Document`.
        """
        return cast(
            Document,
            self._run(
                self._async_documents.update(
                    id,
                    title=title,
                    content=content,
                    created=created,
                    correspondent=correspondent,
                    document_type=document_type,
                    storage_path=storage_path,
                    tags=tags,
                    archive_serial_number=archive_serial_number,
                    custom_fields=custom_fields,
                    owner=owner,
                    set_permissions=set_permissions,
                    remove_inbox_tags=remove_inbox_tags,
                )
            ),
        )

    def delete(self, id: int) -> None:
        """Permanently delete a document.

        Args:
            id: Numeric ID of the document to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        self._run(self._async_documents.delete(id))

    def download(self, id: int, *, original: bool = False) -> bytes:
        """Download the binary content of a document.

        Args:
            id: Numeric ID of the document to download.
            original: If ``False`` *(default)*, returns the archived PDF
                (``GET /documents/{id}/download/``).
                If ``True``, returns the original uploaded file
                (``GET /documents/{id}/download/?original=true``).

        Returns:
            Raw file bytes.
        """
        return cast(bytes, self._run(self._async_documents.download(id, original=original)))

    def thumbnail(self, id: int) -> bytes:
        """Fetch the thumbnail image of a document.

        Args:
            id: Numeric ID of the document whose thumbnail to retrieve.

        Returns:
            Raw binary content of the thumbnail image.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
            ~easypaperless.exceptions.ServerResponseError: If the server returns an
                HTML page (e.g. an auth redirect) instead of the image.
        """
        return cast(bytes, self._run(self._async_documents.thumbnail(id)))

    def upload(
        self,
        file: str | Path | bytes,
        *,
        filename: str | None = None,
        content_type: str | None = None,
        request_timeout: float | None = None,
        title: str | Unset = UNSET,
        created: date | str | None = None,
        correspondent: int | str | None | Unset = UNSET,
        document_type: int | str | None | Unset = UNSET,
        storage_path: int | str | None | Unset = UNSET,
        tags: List[int | str] | None = None,
        archive_serial_number: int | None | Unset = UNSET,
        custom_fields: List[dict[str, Any]] | None = None,
        wait: bool = False,
        poll_interval: float | None = None,
        poll_timeout: float | None = None,
    ) -> str | Document:
        """Upload a document to paperless-ngx.

        The upload request is never retried automatically, whatever the
        client's ``retry_attempts`` / ``tenacity_retrying`` settings: if the
        connection fails after paperless-ngx has accepted the file, a retry
        would create a duplicate.  A failed upload raises (e.g.
        :exc:`~easypaperless.exceptions.TransportTimeoutError`) so you can
        decide whether to check for the document and upload again.

        Args:
            file: Path to the file to upload (``str`` or :class:`~pathlib.Path`),
                or the file content as ``bytes``.  Bytes are sent directly; no
                temporary file is written.
            filename: File name sent to paperless-ngx.  Required when *file* is
                ``bytes`` (omitting it raises
                :exc:`~easypaperless.exceptions.ValidationError` before any
                request).  For a path, overrides the name taken from the path.
            content_type: MIME type of the file part, sent as given (e.g.
                ``"application/pdf"``).  When omitted, it is guessed from the
                file name as before.
            request_timeout: HTTP timeout in seconds for the upload request
                only, overriding the client's ``timeout`` for this call.  Does
                not affect task polling (see ``poll_timeout``).  When omitted,
                the client's ``timeout`` applies.
            title: Title to assign to the document.
            created: Creation date as an ISO-8601 string (``"YYYY-MM-DD"``) or a
                :class:`~datetime.date` object.
            correspondent: Correspondent to assign, as an ID or name.
            document_type: Document type to assign, as an ID or name.
            storage_path: Storage path to assign, as an ID or name.
            tags: Tags to assign, as IDs or names.
            archive_serial_number: Archive serial number to assign.
            custom_fields: List of ``{"field": <field_id>, "value": ...}`` dicts.
            wait: If ``False`` *(default)*, returns immediately with the task ID.
                If ``True``, polls until processing completes.
            poll_interval: Seconds between task-status checks while waiting for
                processing to complete (requires ``wait=True``). Overrides the
                client-level default. When omitted, falls back to the client-level
                ``poll_interval`` (``2.0`` s unless changed at construction).
            poll_timeout: Maximum seconds to wait before raising
                :exc:`~easypaperless.exceptions.TaskTimeoutError` (requires
                ``wait=True``). Overrides the client-level default. When omitted,
                falls back to the client-level ``poll_timeout`` (``60.0`` s unless
                changed at construction).

        Returns:
            The Celery task ID string when ``wait=False``, or the fully
            processed :class:`~easypaperless.models.documents.Document`
            when ``wait=True``.

        Raises:
            ~easypaperless.exceptions.ValidationError: If *file* is ``bytes``
                and no *filename* is given.
            ~easypaperless.exceptions.UploadError: If processing fails;
                ``err.task`` holds the task with paperless-ngx's ``result``
                unaltered (e.g. to recognise a duplicate).
            ~easypaperless.exceptions.TaskTimeoutError: If timeout is exceeded;
                resume with ``client.tasks.wait(err.task_id)``.
        """
        return cast(
            str | Document,
            self._run(
                self._async_documents.upload(
                    file,
                    filename=filename,
                    content_type=content_type,
                    request_timeout=request_timeout,
                    title=title,
                    created=created,
                    correspondent=correspondent,
                    document_type=document_type,
                    storage_path=storage_path,
                    tags=tags,
                    archive_serial_number=archive_serial_number,
                    custom_fields=custom_fields,
                    wait=wait,
                    poll_interval=poll_interval,
                    poll_timeout=poll_timeout,
                )
            ),
        )

    def bulk_add_tag(self, document_ids: List[int], tag: int | str) -> None:
        """Add a tag to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to tag.
            tag: Tag to add, as an ID or name.
        """
        self._run(self._async_documents.bulk_add_tag(document_ids, tag))

    def bulk_remove_tag(self, document_ids: List[int], tag: int | str) -> None:
        """Remove a tag from multiple documents in a single request.

        Args:
            document_ids: List of document IDs to un-tag.
            tag: Tag to remove, as an ID or name.
        """
        self._run(self._async_documents.bulk_remove_tag(document_ids, tag))

    def bulk_modify_tags(
        self,
        document_ids: List[int],
        *,
        add_tags: List[int | str] | None = None,
        remove_tags: List[int | str] | None = None,
    ) -> None:
        """Add and/or remove tags on multiple documents atomically.

        Args:
            document_ids: List of document IDs to modify.
            add_tags: Tags to add, as IDs or names.
            remove_tags: Tags to remove, as IDs or names.
        """
        self._run(
            self._async_documents.bulk_modify_tags(
                document_ids, add_tags=add_tags, remove_tags=remove_tags
            )
        )

    def bulk_delete(self, document_ids: List[int]) -> None:
        """Permanently delete multiple documents in a single request.

        Args:
            document_ids: List of document IDs to delete.
        """
        self._run(self._async_documents.bulk_delete(document_ids))

    def bulk_set_correspondent(
        self, document_ids: List[int], correspondent: int | str | None
    ) -> None:
        """Assign a correspondent to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to modify.
            correspondent: Correspondent to assign, as an ID or name.
                Pass ``None`` to clear.
        """
        self._run(self._async_documents.bulk_set_correspondent(document_ids, correspondent))

    def bulk_set_document_type(
        self, document_ids: List[int], document_type: int | str | None
    ) -> None:
        """Assign a document type to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to modify.
            document_type: Document type to assign, as an ID or name.
                Pass ``None`` to clear.
        """
        self._run(self._async_documents.bulk_set_document_type(document_ids, document_type))

    def bulk_set_storage_path(
        self, document_ids: List[int], storage_path: int | str | None
    ) -> None:
        """Assign a storage path to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to modify.
            storage_path: Storage path to assign, as an ID or name.
                Pass ``None`` to clear.
        """
        self._run(self._async_documents.bulk_set_storage_path(document_ids, storage_path))

    def bulk_modify_custom_fields(
        self,
        document_ids: List[int],
        *,
        add_fields: List[dict[str, Any]] | None = None,
        remove_fields: List[int] | None = None,
    ) -> None:
        """Add and/or remove custom field values on multiple documents.

        Args:
            document_ids: List of document IDs to modify.
            add_fields: Custom-field value dicts to add.
            remove_fields: Custom-field IDs whose values should be removed.
        """
        self._run(
            self._async_documents.bulk_modify_custom_fields(
                document_ids, add_fields=add_fields, remove_fields=remove_fields
            )
        )

    def bulk_set_permissions(
        self,
        document_ids: List[int],
        *,
        set_permissions: SetPermissions | Unset = UNSET,
        owner: int | None | Unset = UNSET,
        merge: bool = False,
    ) -> None:
        """Set permissions and/or owner on multiple documents.

        Args:
            document_ids: List of document IDs to modify.
            set_permissions: Explicit view/change permission sets.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            owner: Numeric user ID to assign as document owner.
                Pass ``None`` to clear the owner.
                Omit (or pass :data:`~easypaperless.UNSET`) to leave unchanged.
            merge: When ``True``, new permissions are merged with existing ones.
        """
        self._run(
            self._async_documents.bulk_set_permissions(
                document_ids,
                set_permissions=set_permissions,
                owner=owner,
                merge=merge,
            )
        )

    def bulk_download(
        self,
        document_ids: List[int],
        *,
        content: Literal["archive", "originals", "both"] = "archive",
        compression: Literal["none", "deflated", "bzip2", "lzma"] = "none",
        follow_formatting: bool = False,
    ) -> bytes:
        """Download multiple documents as a single ZIP archive.

        Args:
            document_ids: List of document IDs to include in the ZIP.
            content: File variant to include.  One of ``"archive"`` *(default)*,
                ``"originals"``, or ``"both"``.
            compression: ZIP compression algorithm.  One of ``"none"`` *(default)*,
                ``"deflated"``, ``"bzip2"``, or ``"lzma"``.
            follow_formatting: When ``True``, filenames inside the ZIP follow
                the storage path formatting configured in paperless-ngx.
                Default: ``False``.

        Returns:
            Raw bytes of the ZIP archive.
        """
        return cast(
            bytes,
            self._run(
                self._async_documents.bulk_download(
                    document_ids,
                    content=content,
                    compression=compression,
                    follow_formatting=follow_formatting,
                )
            ),
        )
