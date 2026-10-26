# [FEATURE] Groups Resource CRUD

## Summary
Add a `groups` resource (list, get, create, update, delete) to both clients, analogous to the existing `users` resource, so that the group side of object permissions (`set_permissions`) can be managed and looked up through easypaperless.

Part of the 0.7.0 milestone, added to make the permissions area complete.

---

## Problem Statement
`documents.update(set_permissions=...)` and `bulk_set_permissions()` accept user and group IDs, and `users` exposes a user's groups, but there is no way to list, look up or manage groups through easypaperless. Callers have to find group IDs elsewhere.

---

## Proposed Solution
- `client.groups` resource (async and sync) with:
  - `list(...)` — returns a `PagedResult` like the other `list()` methods, with paperless's available filters (at least name filters) and pagination parameters.
  - `get(id) -> Group`
  - `create(*, name, permissions=...) -> Group`
  - `update(id, *, name=UNSET, permissions=UNSET) -> Group`
  - `delete(id) -> None`
- Public `Group` model with at least id, name and permissions.
- Conventions (UNSET semantics, logging, naming) as in `users` and `dev/api-conventions.md`.

---

## User Stories
- As a developer, I want to list groups so that I can grant view/change permissions on a document to a group by name lookup.
- As an administrator-tool developer, I want to create and update groups so that I can provision paperless from code.

---

## Scope

### In Scope
- `GroupsResource` / `SyncGroupsResource` with full CRUD.
- `Group` model, exports, docstrings, user docs.
- Tests via the injected transport (#0043).

### Out of Scope
- Name-to-ID resolution of groups inside `set_permissions` (possible follow-up).
- Bulk operations on groups.
- Managing the global permission catalogue.

---

## Acceptance Criteria
- [ ] `groups.list()` returns a `PagedResult[Group]`; name filters are passed as paperless filter parameters.
- [ ] `groups.get(id)` returns the group; an unknown ID raises `NotFoundError`.
- [ ] `groups.create(name="Accounting")` creates a group and returns it with its ID.
- [ ] `groups.update(id, name="New")` only sends the changed fields.
- [ ] `groups.delete(id)` deletes the group.
- [ ] The sync client provides the identical API.
- [ ] `Group` and the resources are exported/documented like `User` / `UsersResource`.

---

## Dependencies & Constraints
- Follows the pattern of #0035 (Users Resource CRUD).

---

## Priority
`Medium`

---

## Additional Notes
- Not requested by ThruCapture directly; added so that permissions (Must-item 10) are fully covered by the library.
