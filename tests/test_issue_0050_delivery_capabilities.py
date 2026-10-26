"""Tests for issue #0050: delivery-target capabilities, as verified live.

Every fake response here reproduces what paperless-ngx 2.18.2 answered in the
#0050 spikes (see the issue's "Spike Findings").
"""

from __future__ import annotations

import json

import httpx
import pytest

from easypaperless import (
    BadRequestError,
    PermissionDeniedError,
    ServerResponseError,
    SetPermissions,
)
from easypaperless.models.permissions import PermissionSet
from tests._transport import FakePaperless

MD5 = "3f8a0c1e5b7d9f2a4c6e8b0d1f3a5c7e"


def _doc(id: int, title: str, checksum: str) -> dict[str, object]:
    # The document JSON has no checksum field; the fake keeps it on the side.
    return {"id": id, "title": title, "_checksum": checksum}


def _documents_like_paperless(docs: list[dict[str, object]]) -> object:
    """GET /api/documents/: checksum__iexact matches, plain ``checksum`` is ignored."""

    def handler(request: httpx.Request) -> httpx.Response:
        wanted = request.url.params.get("checksum__iexact")
        hits = [d for d in docs if wanted is None or str(d["_checksum"]).lower() == wanted.lower()]
        results = [{k: v for k, v in d.items() if k != "_checksum"} for d in hits]
        body = {"count": len(results), "next": None, "previous": None, "results": results}
        return httpx.Response(200, json=body)

    return handler


# --- checksum -------------------------------------------------------------------


async def test_list_by_checksum_returns_exactly_the_matching_document() -> None:
    docs = [_doc(14, "capture", MD5), _doc(15, "other", "0" * 32)]
    fake = FakePaperless({("GET", "/api/documents/"): _documents_like_paperless(docs)})
    async with fake.async_client() as client:
        result = await client.documents.list(checksum=MD5.upper())

    assert [d.id for d in result.results] == [14]
    params = fake.requests[0].url.params
    assert params["checksum__iexact"] == MD5.upper()
    assert "checksum" not in params  # paperless ignores it and would return everything


async def test_list_by_checksum_does_not_find_a_trashed_document() -> None:
    # After DELETE the document is in the trash and drops out of /api/documents/.
    fake = FakePaperless({("GET", "/api/documents/"): _documents_like_paperless([])})
    async with fake.async_client() as client:
        result = await client.documents.list(checksum=MD5)

    assert result.count == 0
    assert result.results == []


# --- upload rejected before a task exists -------------------------------------------


async def test_upload_of_empty_file_raises_bad_request_with_document_field_error() -> None:
    body = {"document": ["The submitted file is empty."]}
    fake = FakePaperless(
        {("POST", "/api/documents/post_document/"): httpx.Response(400, json=body)}
    )
    async with fake.async_client() as client:
        with pytest.raises(BadRequestError) as exc_info:
            await client.documents.upload(b"", filename="empty.pdf", wait=True)

    assert exc_info.value.field_errors == body
    assert len(fake.requests) == 1  # no task polling


# --- notes ---------------------------------------------------------------------------

NOTES_PATH = "/api/documents/14/notes/"


def _note(id: int, text: str) -> dict[str, object]:
    return {
        "id": id,
        "note": text,
        "created": f"2026-10-26T17:26:{40 + id}.000000+01:00",
        "user": {"id": 3, "username": "admin", "first_name": "", "last_name": ""},
    }


async def test_notes_create_returns_the_new_note_when_others_exist() -> None:
    # POST answers with the document's full note list, oldest first.
    existing = [_note(7, "note 1"), _note(8, "note 2")]
    fake = FakePaperless({("POST", NOTES_PATH): [*existing, _note(9, "note 3")]})
    async with fake.async_client() as client:
        note = await client.documents.notes.create(14, note="note 3")

    assert note.id == 9
    assert note.note == "note 3"
    assert note.user == 3
    assert json.loads(fake.requests[0].content) == {"note": "note 3"}


async def test_notes_delete_own_note_accepts_remaining_list_response() -> None:
    # DELETE answers 200 with the remaining notes, not 204.
    fake = FakePaperless({("DELETE", NOTES_PATH): [_note(7, "note 1")]})
    async with fake.async_client() as client:
        result = await client.documents.notes.delete(14, 9)

    assert result is None
    assert fake.requests[0].url.params["id"] == "9"


SERVER_ERROR_PAGE = httpx.Response(
    500,
    text='\n<!doctype html>\n<html lang="en">\n<head>\n  <title>Server Error (500)</title>\n'
    "</head>\n<body>\n  <h1>Server Error (500)</h1><p></p>\n</body>\n</html>\n",
    headers={"Content-Type": "text/html; charset=utf-8"},
)


async def test_notes_delete_unknown_note_raises_server_response_error() -> None:
    fake = FakePaperless({("DELETE", NOTES_PATH): SERVER_ERROR_PAGE})
    async with fake.async_client() as client:
        with pytest.raises(ServerResponseError) as exc_info:
            await client.documents.notes.delete(14, 999999)

    assert exc_info.value.status_code == 500
    assert "<html" not in str(exc_info.value).split("Excerpt:")[0]
    assert len(fake.requests) == 1  # retries are off by default


def test_sync_notes_delete_unknown_note_raises_server_response_error() -> None:
    fake = FakePaperless({("DELETE", NOTES_PATH): SERVER_ERROR_PAGE})
    with fake.sync_client() as client, pytest.raises(ServerResponseError):
        client.documents.notes.delete(14, 999999)


# --- owner + permissions in one PATCH -------------------------------------------------


async def test_update_owner_and_permissions_sends_exactly_one_patch() -> None:
    perms = SetPermissions(
        view=PermissionSet(users=[7], groups=[1]),
        change=PermissionSet(users=[7]),
    )
    fake = FakePaperless(
        {("PATCH", "/api/documents/14/"): {"id": 14, "title": "capture", "owner": 6}}
    )
    async with fake.async_client() as client:
        doc = await client.documents.update(14, owner=6, set_permissions=perms)

    assert doc.owner == 6
    assert [r.method for r in fake.requests] == ["PATCH"]
    assert json.loads(fake.requests[0].content) == {
        "owner": 6,
        "set_permissions": {
            "view": {"users": [7], "groups": [1]},
            "change": {"users": [7], "groups": []},
        },
    }


# --- server_version: no JSON Accept header ------------------------------------------


def _schema_view(request: httpx.Request) -> httpx.Response:
    """paperless-ngx's /api/schema/view/: 406 for a JSON-only Accept header."""
    headers = {"X-Version": "2.18.2", "X-Api-Version": "9"}
    if "application/json" in request.headers.get("accept", ""):
        return httpx.Response(406, text="Not Acceptable", headers=headers)
    return httpx.Response(200, text="<html>schema</html>", headers=headers)


SERVER_INFO_ROUTES = {
    ("GET", "/api/"): httpx.Response(302, headers={"Location": "/api/schema/view/"}),
    ("GET", "/api/schema/view/"): _schema_view,
}


async def test_server_version_sends_no_json_accept_header() -> None:
    fake = FakePaperless(dict(SERVER_INFO_ROUTES))
    async with fake.async_client() as client:
        version = await client.server_version()

    assert version == "2.18.2"
    assert [r.url.path for r in fake.requests] == ["/api/", "/api/schema/view/"]
    for request in fake.requests:
        assert "application/json" not in request.headers.get("accept", "")


def test_sync_server_version_sends_no_json_accept_header() -> None:
    fake = FakePaperless(dict(SERVER_INFO_ROUTES))
    with fake.sync_client() as client:
        assert client.server_version() == "2.18.2"

    assert all("application/json" not in r.headers.get("accept", "") for r in fake.requests)


# --- system_status: HTML 403 for non-admins --------------------------------------------

STATUS_FORBIDDEN = httpx.Response(
    403,
    text="Insufficient permissions",
    headers={"Content-Type": "text/html; charset=utf-8", "X-Version": "2.18.2"},
)


async def test_system_status_non_admin_html_403_has_readable_message() -> None:
    fake = FakePaperless({("GET", "/api/status/"): STATUS_FORBIDDEN})
    async with fake.async_client() as client:
        with pytest.raises(PermissionDeniedError) as exc_info:
            await client.system_status()

    assert str(exc_info.value) == "Insufficient permissions"
    assert exc_info.value.status_code == 403


def test_sync_system_status_non_admin_html_403_has_readable_message() -> None:
    fake = FakePaperless({("GET", "/api/status/"): STATUS_FORBIDDEN})
    with fake.sync_client() as client, pytest.raises(PermissionDeniedError) as exc_info:
        client.system_status()

    assert str(exc_info.value) == "Insufficient permissions"


# --- users: enough to pick an owner -----------------------------------------------------


async def test_users_list_and_get_expose_id_username_and_full_name() -> None:
    user = {
        "id": 6,
        "username": "spike-070-owner",
        "email": "",
        "password": "**********",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "date_joined": "2026-10-26T17:26:45.123456+01:00",
        "is_staff": False,
        "is_active": True,
        "is_superuser": False,
        "groups": [],
        "user_permissions": ["view_document"],
        "inherited_permissions": [],
    }
    page = {"count": 1, "next": None, "previous": None, "all": [6], "results": [user]}
    fake = FakePaperless({("GET", "/api/users/"): page, ("GET", "/api/users/6/"): user})
    async with fake.async_client() as client:
        listed = await client.users.list()
        fetched = await client.users.get(6)

    for u in (listed.results[0], fetched):
        assert (u.id, u.username, u.first_name, u.last_name) == (
            6,
            "spike-070-owner",
            "Ada",
            "Lovelace",
        )
