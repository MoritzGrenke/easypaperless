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

        paperless-ngx answers with the document's full note list, not with
        the new note alone.  The created note is picked from that list as the
        note whose text equals ``note``, so a note another user adds to the
        same document at the same moment is not returned by mistake.  Only if
        that text occurs more than once does the client look up the token's
        user once (``GET /api/ui_settings/``, cached per client) and keep only
        that user's notes (all of them if the lookup fails); of the remaining
        notes the newest (highest ID) is returned.

        Ambiguous case: if the token's user already has a note with the same
        text on the document, or creates one concurrently, the notes cannot be
        told apart and the newest one is returned.  It has the same text, user
        and document; only ``id`` and ``created`` may differ from the note this
        call created.  If no note in the response has the sent text (not
        observed with paperless-ngx 2.18), the newest note is returned and a
        warning is logged.

        Args:
            document_id: Numeric ID of the document to annotate.
            note: Text content of the note.

        Returns:
            The newly created :class:`~easypaperless.models.documents.DocumentNote`.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists
                with that ID.
            ~easypaperless.exceptions.ServerResponseError: If paperless-ngx
                answers with an empty note list.
        """
        return cast(DocumentNote, self._run(self._async_notes.create(document_id, note=note)))

    def delete(self, document_id: int, note_id: int) -> None:
        """Delete a note from a document.

        Args:
            document_id: Numeric ID of the document that owns the note.
            note_id: Numeric ID of the note to delete.

        Raises:
            ~easypaperless.exceptions.NotFoundError: If no document exists with
                that ID.
            ~easypaperless.exceptions.ServerResponseError: If the document has
                no note with ``note_id``.  paperless-ngx answers an unknown note
                ID with ``500 Server Error`` instead of 404 (verified against
                paperless-ngx 2.18.2), so it cannot be told apart from a real
                server error.  With ``retry_attempts`` set, the 500 is retried
                like any other and ends in
                :exc:`~easypaperless.exceptions.RetryExhaustedError`.  Use
                ``notes.list(document_id)`` first if you need to be sure the
                note exists.
        """
        self._run(self._async_notes.delete(document_id, note_id))
