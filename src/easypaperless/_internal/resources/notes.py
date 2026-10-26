"""Document notes resource for PaperlessClient: ``client.documents.notes``."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from easypaperless.exceptions import PaperlessError, ServerResponseError
from easypaperless.models.documents import DocumentNote
from easypaperless.models.paged_result import PagedResult

if TYPE_CHECKING:
    from easypaperless.client import _ClientCore

logger = logging.getLogger(__name__)


def _note_sort_key(note: DocumentNote) -> int:
    """Sort key: note ID (paperless assigns ascending IDs), missing IDs first."""
    return note.id if note.id is not None else -1


class NotesResource:
    """Accessor for document notes: ``client.documents.notes``."""

    def __init__(self, core: _ClientCore) -> None:
        self._core = core
        # Token user's ID; ``None`` = not looked up yet or lookup failed.
        self._user_id: int | None = None
        self._user_lookup_done = False

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

        paperless-ngx answers with the document's full note list, not with
        the new note alone.  The created note is picked from that list as the
        note whose text equals ``note``, so a note another user adds to the
        same document at the same moment is not returned by mistake.  Only if
        that text occurs more than once does the client look up the token's
        user once (``GET /api/ui_settings/``, cached per client) and keep only
        that user's notes; of the remaining notes the newest (highest ID) is
        returned.

        Telling identical texts of different users apart needs the
        ``view_uisettings`` permission (or a superuser), because that lookup
        uses ``/api/ui_settings/``.  Without it the lookup fails (403), the
        failure is cached per client and logged as a warning, no error is
        raised (the note already exists), and the newest note with that text
        is returned, which may belong to another user.

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
        logger.info("Creating note for document id=%d", document_id)
        resp = await self._core._session.post(
            f"/documents/{document_id}/notes/",
            json={"note": note},
            retry=False,  # a retry after a lost response could add the note twice
        )
        data = resp.json()
        if not isinstance(data, list):
            return DocumentNote.model_validate(data)
        notes = [DocumentNote.model_validate(item) for item in data]
        if not notes:
            raise ServerResponseError(
                f"paperless-ngx returned no notes after creating a note on document {document_id}",
                status_code=resp.status_code,
            )
        candidates = [n for n in notes if n.note == note]
        if not candidates:
            logger.warning(
                "Created note not found in the response for document id=%d; "
                "returning the newest note instead",
                document_id,
            )
            candidates = notes
        elif len(candidates) > 1:
            user_id = await self._current_user_id()
            if user_id is None:
                logger.warning(
                    "Several notes with the same text on document id=%d and the current "
                    "user is unknown (needs view_uisettings); returning the newest one",
                    document_id,
                )
            else:
                candidates = [n for n in candidates if n.user == user_id] or candidates
        return max(candidates, key=_note_sort_key)

    async def _current_user_id(self) -> int | None:
        """ID of the token's user, or ``None`` if the lookup failed (cached per client)."""
        if not self._user_lookup_done:
            self._user_lookup_done = True
            try:
                self._user_id = (await self._core._get_ui_settings()).user.id
            except (PaperlessError, ValidationError) as exc:
                # The note already exists; do not turn a failed lookup into an error.
                logger.warning(
                    "Could not look up the current user via /ui_settings/ "
                    "(needs view_uisettings): %s",
                    exc,
                )
        return self._user_id

    async def delete(self, document_id: int, note_id: int) -> None:
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
        logger.info("Deleting note id=%d from document id=%d", note_id, document_id)
        await self._core._session.delete(f"/documents/{document_id}/notes/", params={"id": note_id})
