# [TASK] Verify Existing Capabilities Needed by a Delivery Target (Checksum, Users, Notes, Owner/Permissions)

## Summary
Several capabilities requested by the ThruCapture Backend already exist in 0.6.0. Verify each against a real paperless-ngx instance (spikes), fix any deviation, and cover them with tests that use the injected transport.

Part of the 0.7.0 "Delivery Target" milestone requested by the ThruCapture Backend.

---

## Task Description
Verify and, where necessary, fix:

1. **Find a document by checksum** — `documents.list(checksum=...)` maps to paperless's checksum filter on the original file's MD5.
   Spike: the exact filter name paperless honours, and whether a document in the trash is found (and if not, how a caller can detect a trashed duplicate, e.g. via the `trash` resource).
2. **Users** — `users.list()` and `users.get(id)` return id, username and full name (first/last name), sufficient to choose a document's owner.
3. **Notes** — `notes.create()` returns the *newly created* note with its ID; `notes.delete(document_id, note_id)` works on a note written by the token's user.
   Spike: what paperless returns on create (currently the code takes the last element of a list — verify ordering is reliable) and what paperless permits on delete (own notes vs. others', required permissions).
4. **Owner and permissions** — `documents.update(id, owner=..., set_permissions=...)` sets the owner and grants view and change to another user in **one** PATCH request.
   Spike: the exact payload shape paperless accepts and whether the owner change and permissions are applied together.

---

## Motivation
A Delivery must never create a document twice (checksum lookup) and must set ownership/permissions and a note reliably. The features exist but have not been verified for these exact use cases; the notes `create` result in particular relies on an unverified ordering assumption.

---

## Scope

### In Scope
- Spikes against a live paperless-ngx instance for the four items; findings documented in this issue.
- Bug fixes where behaviour deviates from the expectations above.
- Docstring clarifications (e.g. checksum is MD5 of the original; trash behaviour; notes permissions).
- Tests via the injected transport (#0043) reproducing the verified paperless responses; integration tests where useful.

### Out of Scope
- New features beyond fixing deviations (e.g. groups → #0049).

---

## Acceptance Criteria
- [x] `documents.list(checksum="<md5>")` returns exactly the document whose original has that MD5; the spike result about trashed documents is documented in the docstring.
- [x] `users.list()` / `users.get(id)` expose id, username, first name and last name (verified against a live instance).
- [x] `notes.create(document_id, note="x")` returns a `DocumentNote` whose ID is the ID of the note just created, even when the document already has other notes.
- [x] `notes.delete(document_id, note_id)` succeeds for a note written by the token's user; the documented permission behaviour matches the spike.
- [x] `documents.update(id, owner=<user>, set_permissions=<view+change for another user>)` sends exactly one PATCH and, on a live instance, results in the new owner and the other user's view and change permissions.
- [x] Spike findings for all four items are recorded in this issue.

---

## Spike Findings
Run on 2026-10-26 against paperless-ngx **2.18.2** (API version 9, Docker, SQLite) with a superuser token. Everything created was removed again, documents also from the trash.

### 1. Checksum
- `checksum__iexact=<md5>` (what `documents.list(checksum=...)` sends) gives exactly one hit, also for upper-case input. The value is the MD5 of the uploaded original bytes. The document JSON has no checksum field.
- Plain `checksum=` and `original_checksum=` are **silently ignored**: all documents come back. So the current parameter name must stay.
- A deleted (trashed) document is **not** found by the checksum filter, and `GET /documents/{id}/` gives 404. It shows up in `GET /api/trash/`.
- A re-upload of a trashed document's bytes **still fails as a duplicate**. Result: `"<file>: Not consuming <file>: It is a duplicate of <title> (#<id>). Note: existing document is in the trash."`, with `related_document: null`. A caller detects it from the `UploadError`'s `task.result` and finds the document with `client.trash.list()`. Documented in the docstring and README.

### 2. Users
- User objects carry `id`, `username`, `first_name` and `last_name`, plus `email`, `date_joined`, `is_staff`, `is_active`, `is_superuser`, `groups`, `user_permissions` and `inherited_permissions`. This is enough to choose an owner.
- **Permission format:** `user_permissions` and group `permissions` are **bare codenames** (`"view_document"`), both on read and on write. `"documents.view_document"` gives `400 {"user_permissions": ["Object with codename=documents.view_document does not exist."]}`. Only `inherited_permissions` uses the app-labelled form (`"documents.view_document"`), which is what `PaperlessPermission` lists. The docstrings were wrong and are fixed.

### 3. Notes
- `POST /documents/{id}/notes/` answers 200 with the document's **full note list, oldest first**. The new note is the last element, so `create()` taking `data[-1]` is correct, also when other notes exist.
- `{"note": ""}` creates an empty note. Without a `note` key paperless answers `200 {"error": "Error saving note, ..."}`, which the API cannot trigger because `note` is required.
- `DELETE ...?id=<own note>` answers 200 with the remaining list. Deleting a note on a document requires change permission on it: a user without it gets 403 on create. Deleting another user's note was not tested.
- **An unknown note id gives `500` (HTML "Server Error"), not 404.** Decision: keep the resulting `ServerResponseError`, because a pre-check would cost an extra request on every delete and could not rule out races. The docstring now says so, including `RetryExhaustedError` when retries are on. Unit and integration tests lock the behaviour in.

### 4. Owner and permissions
- `PATCH /documents/{id}/ {"owner": 6, "set_permissions": {"view": {"users": [7], "groups": [1]}, "change": {"users": [7], "groups": []}}}` → 200. Owner and permissions are applied together, and `GET ?full_perms=true` shows exactly those sets. `documents.update(id, owner=..., set_permissions=...)` sends this payload in one PATCH.
- The given sets replace the old ones. A partial dict would leave the omitted sets alone, but `SetPermissions` always sends all four lists. `owner: null` clears the owner, and an unknown owner gives `400 {"owner": ["Invalid pk ..."]}`.
- The `Document` model has no `permissions` field, so reading them back needs `full_perms=true` on a raw request (see "left open").

### Related findings (other 0.7.0 tickets)
- **Tasks (#0045):** `/api/tasks/` is a plain array. The valid `type` values are `auto_task`, `scheduled_task` and `manual_task` (not `file`). `status`, `task_name` and `type` are case-sensitive enums, and an invalid value gives 400. `RECEIVED` is a valid status (added to `TaskStatus`). A duplicate `FAILURE` carries the **existing** document's ID in `related_document`. Every failure result starts with `"<task_file_name>: "`. The test fixtures now use the live texts.
- **Upload (#0044):** paperless detects the file type from the bytes. An unsupported or empty file gives a synchronous `400 {"document": [...]}` → `BadRequestError`, before any task exists.
- **Groups (#0049):** `POST /api/groups/` without `permissions` gives `400 "This field is required."`, so `create()` now sends `[]`.
- **Server info (#0048):** `GET /api/` redirects to the HTML schema view. With `Accept: application/json` it answers 406, so no JSON `Accept` header may be added; a unit test locks this in. `/api/status/` needs a staff or superuser account, and others get `403 text/html "Insufficient permissions"` → `PermissionDeniedError("Insufficient permissions")`.
- **Errors (#0046):** every observed body shape (field dicts, `detail`, HTML 403/500) is mapped correctly.

### Integration suite
- 17 tests in `tests/integration/test_documents.py` still expected `list` from `documents.list()`. They are updated to `PagedResult`.
- 3 `bulk_download` failures ("Event loop is closed", plus a spurious `WriteTimeout`) came from the module-scoped `module_client`. It was created in the module's event loop but used from the tests' function loops. The fixture is removed. `temp_documents` now uses its own client in the module loop, and the tests use the function-scoped `client`.
- Fixtures and upload tests now also empty the trash (`tests/integration/_cleanup.py::purge_document`).
- New `tests/integration/test_delivery_flow.py` covers the delivery flow end to end: bytes upload with `wait=True`, checksum lookup, duplicate `UploadError` with task, notes, owner+permissions, tasks, groups, server info, and the trashed-duplicate case.
- Result: `pytest tests/integration -m integration` → **65 passed**.

### Left open
- `Document` has no `permissions` field and `documents.get()` has no `full_perms` option, so a caller cannot read permissions back through the public API.
- `notes.create()` takes the last list element. Under concurrent writers on the same document, another user's newer note could be returned.
- Empty notes are not rejected locally.

---

## Dependencies & Constraints
- Requires a live paperless-ngx instance (`tests/integration`, `tests/.env`).
- Tests use the injected transport from #0043.

---

## Priority
`High`

---

## Additional Notes
- Requester: ThruCapture Backend, Must-items 4, 6, 9 and 10.
