# [FEATURE] UI Settings Endpoint: Current User and Effective Permissions (`client.ui_settings()`)

## Summary
Expose paperless-ngx's `GET /api/ui_settings/` on both clients so that a caller can find out which user the token belongs to and which permissions that user effectively has. Add a helper that names missing permissions for a given set of required ones. Target release: **0.7.1**.

---

## Problem Statement
A service that uses easypaperless with a dedicated service user (e.g. the ThruCapture Backend's `--check-connections`, thru-capture-backend #408) must tell an operator *which* permission is missing. paperless-ngx's 403 responses never name the missing permission (e.g. "You do not have permission to perform this action."), and easypaperless 0.7.0 offers no call that returns the token user's permissions. The only paperless endpoint that does is `GET /api/ui_settings/`. Without it, callers must either guess from 403s (unreliable, and it requires real write attempts) or call the endpoint directly next to easypaperless, duplicating auth, base URL and the injected transport (#0043).

---

## Proposed Solution
- `client.ui_settings() -> UiSettings` on `PaperlessClient` and `SyncPaperlessClient`, reading `GET /api/ui_settings/`.
- `UiSettings` model with:
  - `user`: the token's user — `id`, `username`, `is_staff`, `is_superuser`, `groups`;
  - `permissions`: the user's effective permission codenames as paperless returns them (bare codenames such as `"add_document"`, `"view_paperlesstask"`);
  - `settings`: the server-side settings paperless includes (e.g. `app_title`, `trash_delay`, `version`, `update_checking`, `auditlog_enabled`, `email_enabled`), all optional, unknown fields ignored.
- Helpers on the model:
  - `has_permission(codename: str) -> bool`;
  - `missing_permissions(required: Iterable[str]) -> set[str]` — returns the required codenames the user lacks; always empty for a superuser.
- Errors follow the #0046 hierarchy (401 → `AuthenticationError`, transport errors → `TransportError`, …).
- Documentation includes a short "check the service user's permissions" example (e.g. the set needed for a delivery: `add_document`, `view_document`, `change_document`, `add_note`, `delete_note`, `view_user`, `view_paperlesstask`).

---

## User Stories
- As a developer of a service with a dedicated paperless user, I want to list the permissions the token's user has so that a connection check can name exactly which permission is missing.
- As an operator, I want a "missing: add_note, view_paperlesstask" message instead of an unexplained 403 during a delivery.
- As a developer, I want to know whether the token belongs to a superuser or staff user so that I can skip or adapt permission checks (e.g. `system_status()` needs staff).

---

## Scope

### In Scope
- `ui_settings()` on both clients, `UiSettings` model (+ nested user/settings models), exports from `easypaperless`.
- `has_permission()` and `missing_permissions()` helpers.
- Docstrings, README section with the permission-check example, CHANGELOG entry for 0.7.1.
- Unit tests via `FakePaperless` (tests/_transport.py) with a recorded paperless response.
- Integration test against the live test instance with a **non-admin** user (created and deleted by the test) that has a known subset of permissions directly and another via a group — verifying that `permissions` contains the effective permissions including group permissions, and that `missing_permissions()` names the rest.
- Release as **0.7.1** (version bump, CHANGELOG, pdoc, PR, tag, PyPI) after approval.

### Out of Scope
- Writing UI settings (`POST /api/ui_settings/`) — it stores the web frontend's per-user preferences and is not useful for API clients.
- `GET /api/profile/` — its response contains the user's `auth_token` in plain text; exposing it would conflict with #0047. If ever added, the token must be excluded.
- Mapping paperless permission codenames to human-readable descriptions.
- Changing the `PaperlessPermission` type (app-labelled form, used for `User.inherited_permissions`).

---

## Acceptance Criteria
- [x] `client.ui_settings()` sends one authenticated `GET /api/ui_settings/` and returns a `UiSettings` whose `user`, `permissions` and `settings` match the response.
- [x] `permissions` contains the codenames exactly as paperless returns them (bare, e.g. `"add_document"`).
- [x] `missing_permissions({"add_document", "add_note"})` returns `{"add_note"}` for a user who has only `add_document`.
- [x] `missing_permissions(...)` returns an empty set for a superuser, and `has_permission(...)` returns `True` for any codename.
- [x] Unknown extra fields in the response (top level, `user`, `settings`) do not cause errors.
- [x] A refused token raises `AuthenticationError`; a transport failure raises `TransportError`.
- [x] On a live instance, for a non-admin user with one permission granted directly and one only via a group, both appear in `permissions` (or, if paperless does not include group permissions, this is documented and `missing_permissions()` accounts for it).
- [x] The token never appears in reprs, exceptions or logs of the new call (covered by the #0047 test pattern).
- [x] The sync client offers the identical API.
- [x] Released as 0.7.1 on PyPI.

---

## Dependencies & Constraints
- Builds on #0043 (transport/test helper), #0046 (errors), #0047 (secrets), #0049 (groups — used to set up the integration test).
- Live verification observed on paperless-ngx 2.18.2: the response has the keys `user`, `permissions`, `settings`; `user` = `{id, username, is_staff, is_superuser, groups}`; the admin user has 176 bare codenames.
- Integration test must clean up the user and group it creates.

---

## Priority
`High` — blocks the ThruCapture Backend's `--check-connections` (thru-capture-backend #408).

---

## Additional Notes
- Requested by the ThruCapture Backend after the 0.7.0 handover.
- Related: #0035 (users), #0048 (server info), #0050 (permission codename format).
