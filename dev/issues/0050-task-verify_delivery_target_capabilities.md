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
- [ ] `documents.list(checksum="<md5>")` returns exactly the document whose original has that MD5; the spike result about trashed documents is documented in the docstring.
- [ ] `users.list()` / `users.get(id)` expose id, username, first name and last name (verified against a live instance).
- [ ] `notes.create(document_id, note="x")` returns a `DocumentNote` whose ID is the ID of the note just created, even when the document already has other notes.
- [ ] `notes.delete(document_id, note_id)` succeeds for a note written by the token's user; the documented permission behaviour matches the spike.
- [ ] `documents.update(id, owner=<user>, set_permissions=<view+change for another user>)` sends exactly one PATCH and, on a live instance, results in the new owner and the other user's view and change permissions.
- [ ] Spike findings for all four items are recorded in this issue.

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
