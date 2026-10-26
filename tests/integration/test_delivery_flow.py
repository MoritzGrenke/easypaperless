"""Integration tests: the delivery-target flow verified in #0050.

A delivery uploads a file from memory, must never create it twice (checksum
lookup, duplicate detection), sets owner and permissions, adds a note and
tidies the task list.  Everything created here is removed again, documents
also from the trash.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio

from easypaperless import (
    Document,
    NotFoundError,
    PaperlessClient,
    PermissionSet,
    ServerResponseError,
    SetPermissions,
    TaskStatus,
    UploadError,
)
from tests.integration._cleanup import purge_document
from tests.integration.conftest import _make_pdf, _random_text, _require_env

pytestmark = pytest.mark.integration

DUPLICATE_MARKER = ": It is a duplicate of "


@dataclass
class Delivery:
    doc: Document
    content: bytes
    md5: str
    filename: str


def _unique_pdf() -> bytes:
    return _make_pdf(f"{uuid.uuid4().hex} {_random_text()}").getvalue()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def delivery() -> AsyncIterator[Delivery]:
    """One document uploaded from bytes with ``wait=True``; purged afterwards."""
    url, key = _require_env()
    content = _unique_pdf()
    filename = f"__integration_delivery_{uuid.uuid4().hex[:8]}.pdf"
    async with PaperlessClient(url=url, api_token=key) as setup_client:
        doc = await setup_client.documents.upload(
            content,
            filename=filename,
            content_type="application/pdf",
            title=filename.removesuffix(".pdf"),
            wait=True,
            poll_timeout=120.0,
        )
        assert isinstance(doc, Document)
        try:
            yield Delivery(doc, content, hashlib.md5(content).hexdigest(), filename)
        finally:
            await purge_document(setup_client, doc.id)


# --- upload + checksum ------------------------------------------------------------------


async def test_upload_from_bytes_with_wait_returns_the_document(
    client: PaperlessClient, delivery: Delivery
) -> None:
    fetched = await client.documents.get(delivery.doc.id)
    assert fetched.title == delivery.filename.removesuffix(".pdf")
    assert fetched.original_file_name == delivery.filename


async def test_list_by_checksum_finds_exactly_the_uploaded_document(
    client: PaperlessClient, delivery: Delivery
) -> None:
    result = await client.documents.list(checksum=delivery.md5)
    assert [d.id for d in result.results] == [delivery.doc.id]

    upper = await client.documents.list(checksum=delivery.md5.upper())
    assert [d.id for d in upper.results] == [delivery.doc.id]

    none = await client.documents.list(checksum="0" * 32)
    assert none.results == []


async def test_duplicate_upload_raises_upload_error_carrying_the_task(
    client: PaperlessClient, delivery: Delivery
) -> None:
    with pytest.raises(UploadError) as exc_info:
        await client.documents.upload(
            delivery.content,
            filename=f"dup-{delivery.filename}",
            wait=True,
            poll_timeout=120.0,
        )

    task = exc_info.value.task
    assert task is not None
    assert task.status == TaskStatus.FAILURE
    assert task.result is not None
    assert DUPLICATE_MARKER in task.result
    assert task.result.startswith(f"dup-{delivery.filename}: ")
    assert task.related_document == str(delivery.doc.id)  # the existing document
    assert task.id is not None
    assert await client.tasks.acknowledge([task.id]) == 1


# --- notes -----------------------------------------------------------------------------------


async def test_notes_create_returns_new_note_id_and_delete_works(
    client: PaperlessClient, delivery: Delivery
) -> None:
    doc_id = delivery.doc.id
    first = await client.documents.notes.create(doc_id, note="__integration_note_1")
    second = await client.documents.notes.create(doc_id, note="__integration_note_2")
    try:
        assert first.id is not None and second.id is not None
        assert second.id != first.id
        assert second.note == "__integration_note_2"
        listed = await client.documents.notes.list(doc_id)
        by_id = {n.id: n.note for n in listed.results}
        assert by_id[first.id] == "__integration_note_1"
        assert by_id[second.id] == "__integration_note_2"
    finally:
        await client.documents.notes.delete(doc_id, second.id)  # type: ignore[arg-type]
        await client.documents.notes.delete(doc_id, first.id)  # type: ignore[arg-type]

    remaining = await client.documents.notes.list(doc_id)
    assert {first.id, second.id}.isdisjoint(n.id for n in remaining.results)


async def test_notes_delete_unknown_note_raises_server_response_error(
    client: PaperlessClient, delivery: Delivery
) -> None:
    # paperless-ngx answers an unknown note id with 500, not 404.
    with pytest.raises(ServerResponseError) as exc_info:
        await client.documents.notes.delete(delivery.doc.id, 999_999_999)
    assert exc_info.value.status_code == 500


# --- owner + permissions ----------------------------------------------------------------


async def test_owner_and_permissions_in_one_patch_are_applied(
    client: PaperlessClient, delivery: Delivery, uid: str
) -> None:
    doc_id = delivery.doc.id
    original_owner = (await client.documents.get(doc_id)).owner
    owner = await client.users.create(
        username=f"__integration_owner_{uid}", password=uuid.uuid4().hex
    )
    grantee = await client.users.create(
        username=f"__integration_grantee_{uid}",
        password=uuid.uuid4().hex,
        first_name="Inte",
        last_name="Gration",
    )
    try:
        fetched = await client.users.get(grantee.id)
        assert (fetched.username, fetched.first_name, fetched.last_name) == (
            f"__integration_grantee_{uid}",
            "Inte",
            "Gration",
        )

        perms = SetPermissions(
            view=PermissionSet(users=[grantee.id]),
            change=PermissionSet(users=[grantee.id]),
        )
        updated = await client.documents.update(doc_id, owner=owner.id, set_permissions=perms)
        assert updated.owner == owner.id

        # Document has no permissions field; read them back as paperless reports them.
        resp = await client._session.get(f"/documents/{doc_id}/", params={"full_perms": "true"})
        body = resp.json()
        assert body["owner"] == owner.id
        assert body["permissions"]["view"]["users"] == [grantee.id]
        assert body["permissions"]["change"]["users"] == [grantee.id]
    finally:
        await client.documents.update(doc_id, owner=original_owner, set_permissions=None)
        await client.users.delete(grantee.id)
        await client.users.delete(owner.id)


# --- tasks --------------------------------------------------------------------------------------


async def test_tasks_list_get_and_acknowledge(client: PaperlessClient, delivery: Delivery) -> None:
    listed = await client.tasks.list(task_name="consume_file", type="auto_task")
    mine = [t for t in listed.results if t.task_file_name == delivery.filename]
    assert len(mine) == 1
    task = mine[0]
    assert task.status == TaskStatus.SUCCESS
    assert task.related_document == str(delivery.doc.id)

    fetched = await client.tasks.get(task.task_id)
    assert fetched.id == task.id

    by_status = await client.tasks.list(task_id=task.task_id, status=TaskStatus.SUCCESS)
    assert [t.id for t in by_status.results] == [task.id]

    assert task.id is not None
    assert await client.tasks.acknowledge([task.id]) == 1
    assert (await client.tasks.get(task.task_id)).acknowledged is True

    with pytest.raises(NotFoundError):
        await client.tasks.get(str(uuid.uuid4()))


# --- groups --------------------------------------------------------------------------------------


async def test_groups_crud(client: PaperlessClient, uid: str) -> None:
    name = f"__integration_group_{uid}"
    group = await client.groups.create(name=name)  # no permissions: [] is sent
    try:
        assert group.permissions == []
        assert (await client.groups.get(group.id)).name == name

        listed = await client.groups.list(name_exact=name)
        assert [g.id for g in listed.results] == [group.id]

        updated = await client.groups.update(group.id, permissions=["view_document"])
        assert updated.permissions == ["view_document"]
    finally:
        await client.groups.delete(group.id)

    with pytest.raises(NotFoundError):
        await client.groups.get(group.id)


# --- server info ----------------------------------------------------------------------------------


async def test_server_version_and_system_status(client: PaperlessClient) -> None:
    version = await client.server_version()
    assert version.count(".") >= 1

    status = await client.system_status()
    assert status.version == version
    assert status.database is not None
    assert status.database.status == "OK"


# --- trash + checksum + duplicate ---------------------------------------------------------------


async def test_trashed_document_not_found_by_checksum_but_reupload_is_duplicate(
    client: PaperlessClient,
) -> None:
    content = _unique_pdf()
    md5 = hashlib.md5(content).hexdigest()
    filename = f"__integration_trashdup_{uuid.uuid4().hex[:8]}.pdf"
    doc = await client.documents.upload(content, filename=filename, wait=True, poll_timeout=120.0)
    assert isinstance(doc, Document)
    try:
        await client.documents.delete(doc.id)  # moves it to the trash
        assert (await client.documents.list(checksum=md5)).results == []
        trashed = await client.trash.list()
        assert any(d.id == doc.id for d in trashed.results)

        with pytest.raises(UploadError) as exc_info:
            await client.documents.upload(
                content, filename=f"dup-{filename}", wait=True, poll_timeout=120.0
            )
        task = exc_info.value.task
        assert task is not None
        assert task.result is not None
        assert DUPLICATE_MARKER in task.result
        assert task.result.endswith("Note: existing document is in the trash.")
        assert task.related_document is None
        assert task.id is not None
        await client.tasks.acknowledge([task.id])
    finally:
        await purge_document(client, doc.id)
