"""Sync document notes resource: ``client.documents.notes``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from easypaperless.models.documents import DocumentNote
from easypaperless.models.paged_result import PagedResult

if TYPE_CHECKING:
    from easypaperless._internal.resources.notes import NotesResource


class SyncNotesResource:
    """Sync accessor for document notes: ``client.documents.notes``."""

    def __init__(self, async_notes: NotesResource, run: Any) -> None:
        self._async_notes = async_notes
        self._run = run

    def list(
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
        return cast(
            PagedResult[DocumentNote],
            self._run(self._async_notes.list(document_id, page=page, page_size=page_size)),
        )

    def create(self, document_id: int, *, note: str) -> DocumentNote:
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
        return cast(DocumentNote, self._run(self._async_notes.create(document_id, note=note)))

    def delete(self, document_id: int, note_id: int) -> None:
        """Delete a note from a document.

        Args:
            document_id: Numeric ID of the document that owns the note.
            note_id: Numeric ID of the note to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document or note
                exists with the given IDs.
        """
        self._run(self._async_notes.delete(document_id, note_id))
