"""Cleanup helpers for integration tests: leave nothing behind, not even in the trash."""

from __future__ import annotations

from easypaperless import NotFoundError, PaperlessClient


async def purge_document(client: PaperlessClient, doc_id: int) -> None:
    """Delete a document and remove it from the trash for good.

    ``documents.delete()`` only moves a document to the trash; without emptying
    it, every run leaves its documents there (and a re-upload of the same bytes
    would still fail as a duplicate).
    """
    try:
        await client.documents.delete(doc_id)
    except NotFoundError:
        pass  # already deleted (e.g. by the test itself)
    trashed = await client.trash.list()
    if any(d.id == doc_id for d in trashed.results):
        await client.trash.empty([doc_id])
