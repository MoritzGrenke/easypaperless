"""Issue #0054: ``notes.create()`` returns the note this call created.

paperless-ngx answers ``POST /api/documents/{id}/notes/`` with the document's full
note list (oldest first). Response shapes recorded live on paperless-ngx 2.18.2:
``user`` is a nested object, there is no ``document`` field.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from easypaperless.exceptions import ServerResponseError
from tests._transport import FakePaperless

NOTES_PATH = "/api/documents/14/notes/"
UI_SETTINGS_PATH = "/api/ui_settings/"
ME = {"id": 3, "username": "admin", "first_name": "", "last_name": ""}
OTHER = {"id": 7, "username": "bob", "first_name": "", "last_name": ""}


def _note(id: int, text: str, user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": id,
        "note": text,
        "created": f"2026-10-26T18:17:{id:02d}.000000+01:00",
        "user": user,
    }


UI_SETTINGS = {
    "user": {"id": 3, "username": "admin", "is_staff": True, "is_superuser": True, "groups": []},
    "settings": {},
    "permissions": [],
}


async def test_returns_own_note_when_another_users_note_is_last() -> None:
    fake = FakePaperless(
        {
            ("POST", NOTES_PATH): [
                _note(1, "old", ME),
                _note(2, "from A", ME),
                _note(3, "from B", OTHER),
            ]
        }
    )
    async with fake.async_client() as client:
        note = await client.documents.notes.create(14, note="from A")
    assert (note.id, note.note, note.user) == (2, "from A", 3)
    assert [r.method for r in fake.requests] == ["POST"]


async def test_normal_case_returns_new_last_note_with_a_single_request() -> None:
    notes = [_note(1, "older", OTHER), _note(2, "checked", ME)]
    fake = FakePaperless({("POST", NOTES_PATH): notes})
    async with fake.async_client() as client:
        note = await client.documents.notes.create(14, note="checked")
    assert (note.id, note.note, note.user) == (2, "checked", 3)
    assert len(fake.requests) == 1


async def test_same_text_from_another_user_is_told_apart_by_the_token_user() -> None:
    fake = FakePaperless(
        {
            ("POST", NOTES_PATH): [_note(4, "ok", ME), _note(5, "ok", OTHER)],
            ("GET", UI_SETTINGS_PATH): UI_SETTINGS,
        }
    )
    async with fake.async_client() as client:
        note = await client.documents.notes.create(14, note="ok")
    assert (note.id, note.note, note.user) == (4, "ok", 3)
    assert [(r.method, r.url.path) for r in fake.requests] == [
        ("POST", NOTES_PATH),
        ("GET", UI_SETTINGS_PATH),
    ]


async def test_ambiguous_same_text_same_user_returns_newest_of_own_notes() -> None:
    # Documented ambiguity: an older identical note of the token's user, or one it
    # posted concurrently, cannot be told apart; the newest of them (highest ID) wins.
    fake = FakePaperless(
        {
            ("POST", NOTES_PATH): [_note(4, "ok", ME), _note(6, "ok", ME), _note(7, "ok", OTHER)],
            ("GET", UI_SETTINGS_PATH): UI_SETTINGS,
        }
    )
    async with fake.async_client() as client:
        note = await client.documents.notes.create(14, note="ok")
    assert (note.id, note.user) == (6, 3)


async def test_no_note_with_the_sent_text_falls_back_to_newest_and_warns(caplog: Any) -> None:
    fake = FakePaperless({("POST", NOTES_PATH): [_note(2, "b", OTHER), _note(1, "a", ME)]})
    async with fake.async_client() as client:
        with caplog.at_level("WARNING", logger="easypaperless"):
            note = await client.documents.notes.create(14, note="missing")
    assert note.id == 2
    assert any(r.levelname == "WARNING" and "note" in r.getMessage() for r in caplog.records)


async def test_empty_note_list_response_raises_server_response_error() -> None:
    fake = FakePaperless({("POST", NOTES_PATH): []})
    async with fake.async_client() as client:
        with pytest.raises(ServerResponseError):
            await client.documents.notes.create(14, note="lost")


async def test_failed_user_lookup_still_returns_newest_note_with_the_text() -> None:
    # The note already exists; a failing lookup must not turn that into an error.
    fake = FakePaperless(
        {
            ("POST", NOTES_PATH): [_note(4, "ok", ME), _note(5, "ok", OTHER)],
            ("GET", UI_SETTINGS_PATH): httpx.Response(403, json={"detail": "nope"}),
        }
    )
    async with fake.async_client() as client:
        note = await client.documents.notes.create(14, note="ok")
    assert (note.id, note.note) == (5, "ok")


def test_sync_client_identifies_own_note_and_looks_up_the_user_once() -> None:
    fake = FakePaperless(
        {
            ("POST", NOTES_PATH): FakePaperless.seq(
                [_note(4, "ok", ME), _note(5, "ok", OTHER)],
                [_note(4, "ok", ME), _note(5, "ok", OTHER), _note(9, "ok", ME)],
                [_note(10, "from A", ME), _note(11, "from B", OTHER)],
            ),
            ("GET", UI_SETTINGS_PATH): UI_SETTINGS,
        }
    )
    with fake.sync_client() as client:
        first = client.documents.notes.create(14, note="ok")
        second = client.documents.notes.create(14, note="ok")
        third = client.documents.notes.create(14, note="from A")
    assert [(n.id, n.user) for n in (first, second, third)] == [(4, 3), (9, 3), (10, 3)]
    ui_calls = [r for r in fake.requests if r.url.path == UI_SETTINGS_PATH]
    assert len(ui_calls) == 1
