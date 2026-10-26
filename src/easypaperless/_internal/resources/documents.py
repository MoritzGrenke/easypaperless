"""Documents resource for PaperlessClient."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Literal, cast

from easypaperless._internal.sentinel import UNSET, Unset
from easypaperless.exceptions import ServerResponseError, UploadError
from easypaperless.models.documents import (
    AuditLogEntry,
    Document,
    DocumentMetadata,
    DocumentNote,
)
from easypaperless.models.paged_result import PagedResult
from easypaperless.models.permissions import SetPermissions

if TYPE_CHECKING:
    from easypaperless.client import _ClientCore

logger = logging.getLogger(__name__)

_DATETIME_STR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")

_SEARCH_MODE_MAP = {
    "title": "title__icontains",
    "title_or_content": "search",
    "query": "query",
    "original_filename": "original_filename__icontains",
}


class NotesResource:
    """Accessor for document notes: ``client.documents.notes``."""

    def __init__(self, core: _ClientCore) -> None:
        self._core = core

    async def list(
        self,
        document_id: int,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> PagedResult[DocumentNote]:
        """Fetch notes attached to a document.

        When ``page`` is ``None`` (the default), all pages are fetched
        automatically and ``next`` / ``previous`` in the returned
        :class:`~easypaperless.models.paged_result.PagedResult` are always
        ``None``.  When ``page`` is set to a specific integer, only that one
        page is fetched and ``next`` / ``previous`` contain the raw API values.

        Args:
            document_id: Numeric ID of the document whose notes to retrieve.
            page: Return only this specific page (1-based).
            page_size: Number of results per page.

        Returns:
            :class:`~easypaperless.models.paged_result.PagedResult` of
            :class:`~easypaperless.models.documents.DocumentNote` objects,
            ordered by creation time.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        logger.info("Listing notes for document id=%d", document_id)
        path = f"/documents/{document_id}/notes/"
        params: dict[str, Any] = {}
        if page_size is not None:
            params["page_size"] = page_size
        if page is not None:
            params["page"] = page

        resp = await self._core._session.get(path, params=params or None)
        data = resp.json()

        if isinstance(data, list):
            # The paperless-ngx notes endpoint returns a plain JSON array rather
            # than a paginated envelope.  Build a synthetic PagedResult so callers
            # always receive a consistent return type regardless of API version.
            notes = [DocumentNote.model_validate(item) for item in data]
            note_ids = [n.id for n in notes if n.id is not None]
            all_ids: list[int] | None = note_ids if note_ids else None
            return PagedResult(
                count=len(notes),
                next=None,
                previous=None,
                all=all_ids,
                results=notes,
            )

        # Paginated dict envelope — forward-compatible with potential future API changes.
        items: list[Any] = list(data.get("results", []))
        count: int = data.get("count", 0)
        page_all_ids: list[int] | None = data.get("all")

        if page is None:
            next_url: str | None = data.get("next")
            while next_url:
                next_url = self._core._session._normalise_next_url(next_url)
                page_resp = await self._core._session.get(next_url)
                page_data = page_resp.json()
                items.extend(page_data.get("results", []))
                next_url = page_data.get("next")
            return PagedResult(
                count=count,
                next=None,
                previous=None,
                all=page_all_ids,
                results=[DocumentNote.model_validate(item) for item in items],
            )

        return cast(
            PagedResult[DocumentNote],
            PagedResult(
                count=count,
                next=data.get("next"),
                previous=data.get("previous"),
                all=page_all_ids,
                results=[DocumentNote.model_validate(item) for item in items],
            ),
        )

    async def create(self, document_id: int, *, note: str) -> DocumentNote:
        """Create a new note on a document.

        Args:
            document_id: Numeric ID of the document to annotate.
            note: Text content of the note.

        Returns:
            The newly created :class:`~easypaperless.models.documents.DocumentNote`.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        logger.info("Creating note for document id=%d", document_id)
        resp = await self._core._session.post(
            f"/documents/{document_id}/notes/",
            json={"note": note},
        )
        data = resp.json()
        if isinstance(data, list):
            return DocumentNote.model_validate(data[-1])
        return DocumentNote.model_validate(data)

    async def delete(self, document_id: int, note_id: int) -> None:
        """Delete a note from a document.

        Args:
            document_id: Numeric ID of the document that owns the note.
            note_id: Numeric ID of the note to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document or note
                exists with the given IDs.
        """
        logger.info("Deleting note id=%d from document id=%d", note_id, document_id)
        await self._core._session.delete(f"/documents/{document_id}/notes/", params={"id": note_id})


class DocumentsResource:
    """Accessor for documents: ``client.documents``."""

    def __init__(self, core: _ClientCore) -> None:
        self._core = core
        self.notes = NotesResource(core)

    async def history(
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
        logger.info("Fetching history for document id=%d", document_id)
        path = f"/documents/{document_id}/history/"
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size

        resp = await self._core._session.get(path, params=params or None)
        data = resp.json()

        if isinstance(data, list):
            entries = [AuditLogEntry.model_validate(item) for item in data]
            entry_ids: list[int] = [e.id for e in entries]
            return PagedResult(
                count=len(entries),
                next=None,
                previous=None,
                all=entry_ids if entry_ids else None,
                results=entries,
            )

        # Forward-compatible: handle a paginated envelope if the API ever adds one.
        items: list[Any] = list(data.get("results", []))
        count: int = data.get("count", 0)
        all_ids: list[int] | None = data.get("all")
        return PagedResult(
            count=count,
            next=data.get("next"),
            previous=data.get("previous"),
            all=all_ids,
            results=[AuditLogEntry.model_validate(item) for item in items],
        )

    @staticmethod
    def _format_date_value(value: date | datetime | str) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return value

    @staticmethod
    def _is_datetime(value: date | datetime | str) -> bool:
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            return bool(_DATETIME_STR_RE.match(value))
        return False

    async def get(self, id: int, *, include_metadata: bool = False) -> Document:
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
        logger.info("Getting document id=%d", id)
        if include_metadata:
            doc_resp, meta_resp = await asyncio.gather(
                self._core._session.get(f"/documents/{id}/"),
                self._core._session.get(f"/documents/{id}/metadata/"),
            )
            data = doc_resp.json()
            data["metadata"] = meta_resp.json()
        else:
            resp = await self._core._session.get(f"/documents/{id}/")
            data = resp.json()
        return Document.model_validate(data)

    async def get_metadata(self, id: int) -> DocumentMetadata:
        """Fetch the extended file-level metadata for a document.

        Args:
            id: Numeric paperless-ngx document ID.

        Returns:
            A :class:`~easypaperless.models.documents.DocumentMetadata` instance.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        logger.info("Getting metadata for document id=%d", id)
        resp = await self._core._session.get(f"/documents/{id}/metadata/")
        return DocumentMetadata.model_validate(resp.json())

    async def list(
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
        logger.info("Listing documents")
        resolver = self._core._resolver
        params: dict[str, Any] = {"page_size": page_size}

        if search is not None:
            api_param = _SEARCH_MODE_MAP.get(search_mode, "search")
            params[api_param] = search

        if ids is not None:
            params["id__in"] = ",".join(str(i) for i in ids)

        if tags is not None:
            resolved = await resolver.resolve_list("tags", tags)
            params["tags__id__all"] = ",".join(str(t) for t in resolved)

        if any_tags is not None:
            resolved = await resolver.resolve_list("tags", any_tags)
            params["tags__id__in"] = ",".join(str(t) for t in resolved)

        if exclude_tags is not None:
            resolved = await resolver.resolve_list("tags", exclude_tags)
            params["tags__id__none"] = ",".join(str(t) for t in resolved)

        if any_correspondent is not None:
            resolved = await resolver.resolve_list("correspondents", any_correspondent)
            params["correspondent__id__in"] = ",".join(str(c) for c in resolved)
        elif not isinstance(correspondent, Unset):
            if correspondent is None:
                params["correspondent__isnull"] = "true"
            else:
                resolved_id = await resolver.resolve("correspondents", correspondent)
                params["correspondent__id"] = resolved_id

        if exclude_correspondents is not None:
            resolved = await resolver.resolve_list("correspondents", exclude_correspondents)
            params["correspondent__id__none"] = ",".join(str(c) for c in resolved)

        if document_type_name_contains is not None:
            params["document_type__name__icontains"] = document_type_name_contains
        if document_type_name_exact is not None:
            params["document_type__name__iexact"] = document_type_name_exact

        if any_document_type is not None:
            resolved = await resolver.resolve_list("document_types", any_document_type)
            params["document_type__id__in"] = ",".join(str(d) for d in resolved)
        elif not isinstance(document_type, Unset):
            if document_type is None:
                params["document_type__isnull"] = "true"
            else:
                resolved_id = await resolver.resolve("document_types", document_type)
                params["document_type__id"] = resolved_id

        if exclude_document_types is not None:
            resolved = await resolver.resolve_list("document_types", exclude_document_types)
            params["document_type__id__none"] = ",".join(str(d) for d in resolved)

        if any_storage_paths is not None:
            resolved = await resolver.resolve_list("storage_paths", any_storage_paths)
            params["storage_path__id__in"] = ",".join(str(s) for s in resolved)
        elif not isinstance(storage_path, Unset):
            if storage_path is None:
                params["storage_path__isnull"] = "true"
            else:
                resolved_id = await resolver.resolve("storage_paths", storage_path)
                params["storage_path__id"] = resolved_id

        if exclude_storage_paths is not None:
            resolved = await resolver.resolve_list("storage_paths", exclude_storage_paths)
            params["storage_path__id__none"] = ",".join(str(s) for s in resolved)

        if not isinstance(owner, Unset):
            if owner is None:
                params["owner__isnull"] = "true"
            else:
                params["owner__id"] = owner

        if exclude_owners is not None:
            params["owner__id__none"] = ",".join(str(o) for o in exclude_owners)

        if custom_fields is not None:
            resolved = await resolver.resolve_list("custom_fields", custom_fields)
            params["custom_fields__id__all"] = ",".join(str(f) for f in resolved)

        if any_custom_fields is not None:
            resolved = await resolver.resolve_list("custom_fields", any_custom_fields)
            params["custom_fields__id__in"] = ",".join(str(f) for f in resolved)

        if exclude_custom_fields is not None:
            resolved = await resolver.resolve_list("custom_fields", exclude_custom_fields)
            params["custom_fields__id__none"] = ",".join(str(f) for f in resolved)

        if custom_field_query is not None:
            params["custom_field_query"] = json.dumps(custom_field_query)

        if not isinstance(archive_serial_number, Unset):
            if archive_serial_number is None:
                params["archive_serial_number__isnull"] = "true"
            else:
                params["archive_serial_number"] = archive_serial_number

        if archive_serial_number_from is not None:
            params["archive_serial_number__gte"] = archive_serial_number_from

        if archive_serial_number_till is not None:
            params["archive_serial_number__lte"] = archive_serial_number_till

        if created_after is not None:
            params["created__date__gt"] = self._format_date_value(created_after)

        if created_before is not None:
            params["created__date__lt"] = self._format_date_value(created_before)

        if added_after is not None:
            key = "added__gt" if self._is_datetime(added_after) else "added__date__gt"
            params[key] = self._format_date_value(added_after)

        if added_from is not None:
            key = "added__gte" if self._is_datetime(added_from) else "added__date__gte"
            params[key] = self._format_date_value(added_from)

        if added_before is not None:
            key = "added__lt" if self._is_datetime(added_before) else "added__date__lt"
            params[key] = self._format_date_value(added_before)

        if added_until is not None:
            key = "added__lte" if self._is_datetime(added_until) else "added__date__lte"
            params[key] = self._format_date_value(added_until)

        if modified_after is not None:
            key = "modified__gt" if self._is_datetime(modified_after) else "modified__date__gt"
            params[key] = self._format_date_value(modified_after)

        if modified_from is not None:
            key = "modified__gte" if self._is_datetime(modified_from) else "modified__date__gte"
            params[key] = self._format_date_value(modified_from)

        if modified_before is not None:
            key = "modified__lt" if self._is_datetime(modified_before) else "modified__date__lt"
            params[key] = self._format_date_value(modified_before)

        if modified_until is not None:
            key = "modified__lte" if self._is_datetime(modified_until) else "modified__date__lte"
            params[key] = self._format_date_value(modified_until)

        if checksum is not None:
            params["checksum__iexact"] = checksum

        if ordering is not None:
            params["ordering"] = f"-{ordering}" if descending else ordering

        if page is not None:
            params["page"] = page
            raw = await self._core._session.get_page("/documents/", params=params)
            items = raw.items
            if max_results is not None:
                items = items[:max_results]
            return PagedResult(
                count=raw.count,
                next=raw.next,
                previous=raw.previous,
                all=raw.all_ids,
                results=[Document.model_validate(item) for item in items],
            )

        raw = await self._core._session.get_all_pages_paged(
            "/documents/", params, max_results=max_results, on_page=on_page
        )
        return PagedResult(
            count=raw.count,
            next=raw.next,
            previous=raw.previous,
            all=raw.all_ids,
            results=[Document.model_validate(item) for item in raw.items],
        )

    async def update(
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
        logger.info("Updating document id=%d", id)
        resolver = self._core._resolver
        payload: dict[str, Any] = {}

        if not isinstance(title, Unset):
            payload["title"] = title
        if not isinstance(content, Unset):
            payload["content"] = content
        if not isinstance(created, Unset):
            payload["created"] = self._format_date_value(created) if created is not None else None
        if not isinstance(correspondent, Unset):
            payload["correspondent"] = (
                None
                if correspondent is None
                else await resolver.resolve("correspondents", correspondent)
            )
        if not isinstance(document_type, Unset):
            payload["document_type"] = (
                None
                if document_type is None
                else await resolver.resolve("document_types", document_type)
            )
        if not isinstance(storage_path, Unset):
            payload["storage_path"] = (
                None
                if storage_path is None
                else await resolver.resolve("storage_paths", storage_path)
            )
        if not isinstance(tags, Unset):
            payload["tags"] = await resolver.resolve_list("tags", tags or [])
        if not isinstance(archive_serial_number, Unset):
            payload["archive_serial_number"] = archive_serial_number
        if not isinstance(custom_fields, Unset):
            payload["custom_fields"] = custom_fields
        if not isinstance(owner, Unset):
            payload["owner"] = owner
        if not isinstance(set_permissions, Unset):
            payload["set_permissions"] = (
                SetPermissions().model_dump()
                if set_permissions is None
                else set_permissions.model_dump()
            )
        if not isinstance(remove_inbox_tags, Unset):
            payload["remove_inbox_tags"] = remove_inbox_tags

        resp = await self._core._session.patch(f"/documents/{id}/", json=payload)
        return Document.model_validate(resp.json())

    async def delete(self, id: int) -> None:
        """Permanently delete a document.

        Args:
            id: Numeric ID of the document to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
        """
        logger.info("Deleting document id=%d", id)
        await self._core._session.delete(f"/documents/{id}/")

    async def download(self, id: int, *, original: bool = False) -> bytes:
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
        logger.info("Downloading document id=%d (original=%s)", id, original)
        path = f"/documents/{id}/download/"
        if original:
            path += "?original=true"
        resp = await self._core._session.get_download(path)
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type or resp.content[:9].lower().startswith(b"<!doctype"):
            raise ServerResponseError(
                f"Download returned an HTML page (content-type: {content_type!r}). "
                "The server redirected to a login page even after re-attaching auth.",
                status_code=resp.status_code,
            )
        return resp.content

    async def thumbnail(self, id: int) -> bytes:
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
        logger.info("Fetching thumbnail for document id=%d", id)
        resp = await self._core._session.get_download(f"/documents/{id}/thumb/")
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type or resp.content[:9].lower().startswith(b"<!doctype"):
            raise ServerResponseError(
                f"Thumbnail returned an HTML page (content-type: {content_type!r}). "
                "The server redirected to a login page even after re-attaching auth.",
                status_code=resp.status_code,
            )
        return resp.content

    async def upload(
        self,
        file: str | Path,
        *,
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

        Args:
            file: Path to the file to upload.
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
            ~easypaperless.exceptions.UploadError: If processing fails;
                ``err.task`` holds the task with paperless-ngx's ``result``
                unaltered (e.g. to recognise a duplicate).
            ~easypaperless.exceptions.TaskTimeoutError: If timeout is exceeded;
                resume with ``client.tasks.wait(err.task_id)``.
        """
        resolver = self._core._resolver
        file_path = Path(file)
        file_bytes = file_path.read_bytes()
        logger.info("Uploading %r (%d bytes)", file_path.name, len(file_bytes))

        data: dict[str, Any] = {}
        if not isinstance(title, Unset):
            data["title"] = title
        if created is not None:
            data["created"] = self._format_date_value(created)
        if not isinstance(correspondent, Unset) and correspondent is not None:
            data["correspondent"] = await resolver.resolve("correspondents", correspondent)
        if not isinstance(document_type, Unset) and document_type is not None:
            data["document_type"] = await resolver.resolve("document_types", document_type)
        if not isinstance(storage_path, Unset) and storage_path is not None:
            data["storage_path"] = await resolver.resolve("storage_paths", storage_path)
        if tags is not None:
            resolved = await resolver.resolve_list("tags", tags)
            data["tags"] = resolved
        if not isinstance(archive_serial_number, Unset) and archive_serial_number is not None:
            data["archive_serial_number"] = archive_serial_number
        if custom_fields is not None:
            data["custom_fields"] = json.dumps(custom_fields)

        files = {"document": (file_path.name, file_bytes)}
        resp = await self._core._session.post("/documents/post_document/", data=data, files=files)
        task_id: str = resp.text.strip('"')
        logger.debug("Upload accepted, task_id=%r", task_id)

        if not wait:
            return task_id

        task = await self._core.tasks.wait(
            task_id, poll_interval=poll_interval, poll_timeout=poll_timeout
        )
        if task.related_document is None:
            raise UploadError(f"Task {task_id!r} succeeded but returned no document ID", task=task)
        doc_id = int(task.related_document)
        logger.info("Task %r produced document_id=%d", task_id, doc_id)
        return await self.get(doc_id)

    # -------------------------------------------------------------------------
    # Document bulk operations
    # -------------------------------------------------------------------------

    async def _bulk_edit(self, document_ids: List[int], method: str, **parameters: Any) -> None:
        """Execute a bulk-edit operation on a list of documents.

        Args:
            document_ids: List of document IDs to operate on.
            method: Bulk-edit method name (e.g. ``"add_tag"``, ``"delete"``).
            **parameters: Additional keyword arguments forwarded to the API.
        """
        payload = {"documents": document_ids, "method": method, "parameters": parameters}
        await self._core._session.post("/documents/bulk_edit/", json=payload, timeout=120.0)

    async def bulk_add_tag(self, document_ids: List[int], tag: int | str) -> None:
        """Add a tag to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to tag.
            tag: Tag to add, as an ID or name.
        """
        logger.info("Bulk adding tag %r to %d documents", tag, len(document_ids))
        tag_id = await self._core._resolver.resolve("tags", tag)
        await self._bulk_edit(document_ids, "add_tag", tag=tag_id)

    async def bulk_remove_tag(self, document_ids: List[int], tag: int | str) -> None:
        """Remove a tag from multiple documents in a single request.

        Args:
            document_ids: List of document IDs to un-tag.
            tag: Tag to remove, as an ID or name.
        """
        logger.info("Bulk removing tag %r from %d documents", tag, len(document_ids))
        tag_id = await self._core._resolver.resolve("tags", tag)
        await self._bulk_edit(document_ids, "remove_tag", tag=tag_id)

    async def bulk_modify_tags(
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
        logger.info("Bulk modifying tags on %d documents", len(document_ids))
        resolver = self._core._resolver
        add_ids = await resolver.resolve_list("tags", add_tags or [])
        remove_ids = await resolver.resolve_list("tags", remove_tags or [])
        await self._bulk_edit(document_ids, "modify_tags", add_tags=add_ids, remove_tags=remove_ids)

    async def bulk_delete(self, document_ids: List[int]) -> None:
        """Permanently delete multiple documents in a single request.

        Args:
            document_ids: List of document IDs to delete.
        """
        logger.info("Bulk deleting %d documents", len(document_ids))
        await self._bulk_edit(document_ids, "delete")

    async def bulk_set_correspondent(
        self, document_ids: List[int], correspondent: int | str | None
    ) -> None:
        """Assign a correspondent to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to modify.
            correspondent: Correspondent to assign, as an ID or name.
                Pass ``None`` to clear.
        """
        logger.info(
            "Bulk setting correspondent %r on %d documents", correspondent, len(document_ids)
        )
        cor_id: int | None = None
        if correspondent is not None:
            cor_id = await self._core._resolver.resolve("correspondents", correspondent)
        await self._bulk_edit(document_ids, "set_correspondent", correspondent=cor_id)

    async def bulk_set_document_type(
        self, document_ids: List[int], document_type: int | str | None
    ) -> None:
        """Assign a document type to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to modify.
            document_type: Document type to assign, as an ID or name.
                Pass ``None`` to clear.
        """
        logger.info(
            "Bulk setting document type %r on %d documents", document_type, len(document_ids)
        )
        dt_id: int | None = None
        if document_type is not None:
            dt_id = await self._core._resolver.resolve("document_types", document_type)
        await self._bulk_edit(document_ids, "set_document_type", document_type=dt_id)

    async def bulk_set_storage_path(
        self, document_ids: List[int], storage_path: int | str | None
    ) -> None:
        """Assign a storage path to multiple documents in a single request.

        Args:
            document_ids: List of document IDs to modify.
            storage_path: Storage path to assign, as an ID or name.
                Pass ``None`` to clear.
        """
        logger.info("Bulk setting storage path %r on %d documents", storage_path, len(document_ids))
        sp_id: int | None = None
        if storage_path is not None:
            sp_id = await self._core._resolver.resolve("storage_paths", storage_path)
        await self._bulk_edit(document_ids, "set_storage_path", storage_path=sp_id)

    async def bulk_modify_custom_fields(
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
        logger.info("Bulk modifying custom fields on %d documents", len(document_ids))
        await self._bulk_edit(
            document_ids,
            "modify_custom_fields",
            add_custom_fields=add_fields or [],
            remove_custom_fields=remove_fields or [],
        )

    async def bulk_set_permissions(
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
        logger.info("Bulk setting permissions on %d documents", len(document_ids))
        params: dict[str, Any] = {"merge": merge}
        if not isinstance(set_permissions, Unset):
            params["set_permissions"] = set_permissions.model_dump()
        if not isinstance(owner, Unset):
            params["owner"] = owner
        await self._bulk_edit(document_ids, "set_permissions", **params)

    async def bulk_download(
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
        logger.info(
            "Bulk downloading %d documents (content=%s, compression=%s)",
            len(document_ids),
            content,
            compression,
        )
        payload: dict[str, Any] = {
            "documents": document_ids,
            "content": content,
            "compression": compression,
            "follow_formatting": follow_formatting,
        }
        resp = await self._core._session.post("/documents/bulk_download/", json=payload)
        return resp.content
