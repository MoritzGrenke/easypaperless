# [FEATURE] Read Back Object Permissions (`full_perms`) for Documents and Other Owned Objects

## Summary
Allow callers to read the view/change permissions of documents (and other owned objects such as tags, correspondents, document types and storage paths) through the public API, by supporting paperless-ngx's `full_perms` option and exposing the returned permissions on the models.

---

## Problem Statement
`documents.update(id, owner=..., set_permissions=...)` can set an owner and view/change permissions, but there is no public way to read them back. The `Document` model only has `owner` and `user_can_change`; `documents.get()` and `documents.list()` do not support `full_perms=true`. Callers who need to verify a delivery (e.g. the ThruCapture Backend checking that a document's permissions are as intended) or display who can see a document must fall back to raw requests through private internals. The 0.7.0 integration test for owner/permissions (`tests/integration/test_delivery_flow.py`) has to use `client._session` for this reason.

---

## Proposed Solution
- `documents.get(id, *, full_perms: bool = False)` and `documents.list(..., full_perms: bool = False)` send paperless's `full_perms=true` when requested.
- The models expose the returned permissions as an optional, typed field (e.g. `permissions: PermissionSet | None`, reusing the existing permission models where they fit). The field is `None` when `full_perms` was not requested.
- The same option and field are offered on the other resources whose objects have owners and permissions in paperless (tags, correspondents, document types, storage paths, and any other resource that supports `full_perms` — verified by spike), so the permission area is covered consistently.
- Async and sync clients behave identically.

---

## User Stories
- As a developer delivering documents into paperless, I want to read a document's permissions back so that I can verify the owner and the users/groups with view and change access after an update.
- As a developer building an admin tool, I want to list documents or tags with their full permissions so that I can audit who can see what.

---

## Scope

### In Scope
- `full_perms` option on `get()` and `list()` of documents and of every other resource that supports it (spike decides the list).
- Typed permission field on the corresponding models.
- Docstrings, README section, CHANGELOG.
- Unit tests via `FakePaperless` (tests/_transport.py) with recorded paperless responses; integration test that replaces the private `client._session` call in `test_delivery_flow.py` with the public API.
- Spike: which endpoints support `full_perms`, and the exact response shape (`permissions: {view: {users, groups}, change: {users, groups}}`).

### Out of Scope
- Changing how permissions are *set* (`set_permissions` stays as is).
- Resolving user/group names inside the permission field (IDs only).
- Bulk permission reads beyond what `list(full_perms=True)` returns.

---

## Acceptance Criteria
- [x] `documents.get(id, full_perms=True)` sends `full_perms=true` and returns a `Document` whose permission field contains the view and change users and groups from paperless's response.
- [x] `documents.get(id)` without the option sends no `full_perms` parameter and the permission field is `None`.
- [x] `documents.list(full_perms=True)` returns documents with populated permission fields.
- [x] Every other resource that supports `full_perms` (as found by the spike) offers the same option on `get()` and `list()` with the same behaviour.
- [x] After `documents.update(id, owner=a, set_permissions=<view+change for user b>)`, `documents.get(id, full_perms=True)` reflects owner `a` and user `b` in view and change (integration test against a live instance).
- [x] `tests/integration/test_delivery_flow.py` no longer uses private client internals to read permissions.
- [x] The sync client offers the identical API.

---

## Dependencies & Constraints
- Builds on #0005 (update document), #0050 (verified owner/permissions PATCH shape) and the test helper from #0043.
- Spike against the test instance (tests/integration/.env) required; clean up created objects including the trash.

---

## Priority
`Medium`

---

## Additional Notes
- Found during #0050 (live verification, "Left open"). Requested context: ThruCapture Backend Delivery Target.
