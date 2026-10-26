"""Document notes resource for PaperlessClient: ``client.documents.notes``."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from easypaperless.models.documents import DocumentNote
from easypaperless.models.paged_result import PagedResult

if TYPE_CHECKING:
    from easypaperless.client import _ClientCore

logger = logging.getLogger(__name__)


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

        raw = await self._core._session.get_list(
            path, params=params or None, all_pages=page is None
        )
        notes = [DocumentNote.model_validate(item) for item in raw.items]
        all_ids = raw.all_ids
        if not raw.paginated:
            # paperless-ngx answers with a plain JSON array: list the note IDs.
            all_ids = [n.id for n in notes if n.id is not None] or None
        return PagedResult(
            count=raw.count,
            next=raw.next,
            previous=raw.previous,
            all=all_ids,
            results=notes,
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
            retry=False,  # a retry after a lost response could add the note twice
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
